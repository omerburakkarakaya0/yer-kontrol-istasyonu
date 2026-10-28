#include "vehicle/VehicleManagerReceiver.hpp"

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
#endif
#include <cstring>
#include "utils/Validation.hpp"
#include "vehicle/VehicleManagerPackets.hpp"

namespace comm::vehicle {

namespace {
#ifdef _WIN32
using SocketHandle = SOCKET;
constexpr SocketHandle invalidSocket = INVALID_SOCKET;
void closeSocket(SocketHandle fd) { ::closesocket(fd); }
bool socketInvalid(SocketHandle fd) { return fd == INVALID_SOCKET; }
int lastSocketError() { return WSAGetLastError(); }
void ensureSocketsReady() {
  static bool initialized = [] {
    WSADATA data{};
    return WSAStartup(MAKEWORD(2, 2), &data) == 0;
  }();
  (void)initialized;
}
#else
using SocketHandle = int;
constexpr SocketHandle invalidSocket = -1;
void closeSocket(SocketHandle fd) { ::close(fd); }
bool socketInvalid(SocketHandle fd) { return fd < 0; }
int lastSocketError() { return errno; }
void ensureSocketsReady() {}
#endif

sockaddr_in bindAddress(const std::string& host, int port) {
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(static_cast<uint16_t>(port));
  if (host == "0.0.0.0") {
    addr.sin_addr.s_addr = INADDR_ANY;
  } else {
    ::inet_pton(AF_INET, host.c_str(), &addr.sin_addr);
  }
  return addr;
}
}  // namespace

VehicleManagerReceiver::VehicleManagerReceiver(core::AppContext& context, server::ICompetitionApi& api, core::VehicleManagerConfig config)
    : context_(context), api_(api), config_(std::move(config)) {}

VehicleManagerReceiver::~VehicleManagerReceiver() { stop(); }

void VehicleManagerReceiver::start() {
  if (running_.exchange(true)) return;
  heartbeat_thread_ = std::thread(&VehicleManagerReceiver::heartbeatLoop, this);
  event_thread_ = std::thread(&VehicleManagerReceiver::eventLoop, this);
  timeout_thread_ = std::thread(&VehicleManagerReceiver::timeoutLoop, this);
}

void VehicleManagerReceiver::stop() {
  running_ = false;
  if (heartbeat_thread_.joinable()) heartbeat_thread_.join();
  if (event_thread_.joinable()) event_thread_.join();
  if (timeout_thread_.joinable()) timeout_thread_.join();
}

bool VehicleManagerReceiver::handleStatusJson(const nlohmann::json& json) {
  auto status = parseStatus(json);
  if (!status) {
    context_.events().publish({core::EventType::VALIDATION_ERROR, "VehicleManagerReceiver", "Invalid Vehicle Manager status", {{"raw", json}}});
    return false;
  }
  if (status->vehicle_state) context_.state().updateVehicleState(*status->vehicle_state);
  if (status->qr_coordinate) context_.state().setQrCoordinate(*status->qr_coordinate);
  if (status->hss_coordinates_present) context_.state().setHssCoordinates(status->hss_coordinates);
  // A successful direct referee response is authoritative. Vehicle Manager
  // positions are a fallback and must not replace a fuller referee snapshot.
  if (status->opponent_positions_present && !context_.state().connectionStatus().server_connected) {
    context_.state().setOpponentPositions(status->opponent_positions);
  }
  context_.state().markVehicleManagerHeartbeat();
  context_.state().setVehicleManagerLastStatus(status->raw);
  context_.events().publish({core::EventType::VEHICLE_MANAGER_CONNECTED, "VehicleManagerReceiver", "Vehicle Manager heartbeat received", {{"vehicle_id", status->vehicle_id}}});
  context_.events().publish({core::EventType::VEHICLE_MANAGER_STATUS_UPDATED, "VehicleManagerReceiver", "Vehicle Manager status updated", status->raw});
  return true;
}

bool VehicleManagerReceiver::handleEventJson(const nlohmann::json& json) {
  auto event = parseEvent(json);
  if (!event) {
    context_.events().publish({core::EventType::VALIDATION_ERROR, "VehicleManagerReceiver", "Invalid Vehicle Manager event", {{"raw", json}}});
    return false;
  }
  auto event_id = stableEventId(*event);
  if (!acceptEventId(event_id)) return false;
  context_.state().setVehicleManagerLastEvent(event->raw);
  context_.events().publish({core::EventType::VEHICLE_MANAGER_EVENT_RECEIVED, "VehicleManagerReceiver", "Vehicle Manager event received", {{"type", event->type}, {"event_id", event_id}}});

  try {
  if (event->type == "LOCK_CONFIRMED") {
    auto packet = event->payload.get<server::LockPacket>();
    auto validation = utils::validateLock(packet);
    if (!validation.valid) {
      context_.events().publish({core::EventType::LOCK_PACKET_REJECTED, "VehicleManagerReceiver", "Lock packet rejected", {{"errors", validation.errors}}});
      return false;
    }
    auto result = api_.sendLockInfo(packet);
    auto delay_ms = static_cast<std::int64_t>(0);
    if (event->timestamp_ms > 0) {
      auto now = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
      delay_ms = now - event->timestamp_ms;
    }
    context_.events().publish({result.ok ? core::EventType::LOCK_PACKET_SENT : core::EventType::LOCK_PACKET_REJECTED,
                               "VehicleManagerReceiver",
                               result.ok ? "Lock packet forwarded" : "Lock packet forward failed",
                               {{"http_status", result.http_status}, {"delay_ms", delay_ms}}});
    return result.ok;
  }

  if (event->type == "KAMIKAZE_CONFIRMED") {
    auto packet = event->payload.get<server::KamikazePacket>();
    auto validation = utils::validateKamikaze(packet);
    if (!validation.valid) {
      context_.events().publish({core::EventType::KAMIKAZE_PACKET_REJECTED, "VehicleManagerReceiver", "Kamikaze packet rejected", {{"errors", validation.errors}}});
      return false;
    }
    auto result = api_.sendKamikazeInfo(packet);
    auto delay_ms = static_cast<std::int64_t>(0);
    if (event->timestamp_ms > 0) {
      auto now = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
      delay_ms = now - event->timestamp_ms;
    }
    context_.events().publish({result.ok ? core::EventType::KAMIKAZE_PACKET_SENT : core::EventType::KAMIKAZE_PACKET_REJECTED,
                               "VehicleManagerReceiver",
                               result.ok ? "Kamikaze packet forwarded" : "Kamikaze packet forward failed",
                               {{"http_status", result.http_status}, {"delay_ms", delay_ms}}});
    return result.ok;
  }
  } catch (const std::exception& e) {
    context_.events().publish({core::EventType::VALIDATION_ERROR, "VehicleManagerReceiver", "Vehicle Manager event parse failed", {{"error", e.what()}, {"type", event->type}}});
    return false;
  }

  return true;
}

void VehicleManagerReceiver::checkHeartbeatTimeout() {
  auto status = context_.state().connectionStatus();
  if (!status.vehicle_manager_connected) return;
  auto age = std::chrono::steady_clock::now() - status.last_vehicle_manager_heartbeat;
  if (age > std::chrono::milliseconds(config_.heartbeat_timeout_ms)) {
    context_.state().markVehicleManagerConnected(false);
    context_.events().publish({core::EventType::VEHICLE_MANAGER_DISCONNECTED, "VehicleManagerReceiver", "Vehicle Manager heartbeat timeout"});
  }
}

bool VehicleManagerReceiver::acceptEventId(const std::string& event_id) {
  std::lock_guard<std::mutex> lock(duplicate_mutex_);
  return processed_events_.insert(event_id).second;
}

void VehicleManagerReceiver::heartbeatLoop() {
  ensureSocketsReady();
  SocketHandle fd = ::socket(AF_INET, SOCK_DGRAM, 0);
  if (socketInvalid(fd)) return;
  auto addr = bindAddress(config_.bind_host, config_.heartbeat_port);
  int reuse = 1;
  ::setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, reinterpret_cast<const char*>(&reuse), sizeof(reuse));
  if (::bind(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
    closeSocket(fd);
    return;
  }
  timeval timeout{0, 250000};
  ::setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
  while (running_) {
    char buffer[65536];
    auto n = ::recvfrom(fd, buffer, sizeof(buffer) - 1, 0, nullptr, nullptr);
    if (n <= 0) continue;
    buffer[n] = '\0';
    auto json = nlohmann::json::parse(buffer, nullptr, false);
    if (json.is_discarded()) {
      context_.events().publish({core::EventType::VALIDATION_ERROR, "VehicleManagerReceiver", "Invalid heartbeat JSON"});
      continue;
    }
    handleStatusJson(json);
  }
  closeSocket(fd);
}

void VehicleManagerReceiver::eventLoop() {
  ensureSocketsReady();
  SocketHandle fd = ::socket(AF_INET, SOCK_STREAM, 0);
  if (socketInvalid(fd)) return;
  auto addr = bindAddress(config_.bind_host, config_.event_port);
  int reuse = 1;
  ::setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, reinterpret_cast<const char*>(&reuse), sizeof(reuse));
  if (::bind(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0 || ::listen(fd, 4) != 0) {
    closeSocket(fd);
    return;
  }
  timeval timeout{0, 250000};
  ::setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout), sizeof(timeout));
  while (running_) {
    SocketHandle client = ::accept(fd, nullptr, nullptr);
    if (socketInvalid(client)) continue;
    std::string line;
    char c;
    while (running_ && ::recv(client, &c, 1, 0) == 1) {
      if (c == '\n') {
        auto json = nlohmann::json::parse(line, nullptr, false);
        if (!json.is_discarded()) handleEventJson(json);
        line.clear();
      } else {
        line.push_back(c);
      }
    }
    if (!line.empty()) {
      auto json = nlohmann::json::parse(line, nullptr, false);
      if (!json.is_discarded()) handleEventJson(json);
    }
    closeSocket(client);
  }
  closeSocket(fd);
}

void VehicleManagerReceiver::timeoutLoop() {
  while (running_) {
    checkHeartbeatTimeout();
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
  }
}

}  // namespace comm::vehicle
