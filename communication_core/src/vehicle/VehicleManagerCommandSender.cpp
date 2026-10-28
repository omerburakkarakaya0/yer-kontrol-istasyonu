#include "vehicle/VehicleManagerCommandSender.hpp"

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>
#endif
#include "core/EventBus.hpp"
#include "vehicle/VehicleManagerPackets.hpp"

namespace comm::vehicle {

namespace {
#ifdef _WIN32
using SocketHandle = SOCKET;
void closeSocket(SocketHandle fd) { ::closesocket(fd); }
bool socketInvalid(SocketHandle fd) { return fd == INVALID_SOCKET; }
void ensureSocketsReady() {
  static bool initialized = [] {
    WSADATA data{};
    return WSAStartup(MAKEWORD(2, 2), &data) == 0;
  }();
  (void)initialized;
}
#else
using SocketHandle = int;
void closeSocket(SocketHandle fd) { ::close(fd); }
bool socketInvalid(SocketHandle fd) { return fd < 0; }
void ensureSocketsReady() {}
#endif
}  // namespace

VehicleManagerCommandSender::VehicleManagerCommandSender(core::AppContext& context, core::VehicleManagerConfig config)
    : context_(context), config_(std::move(config)) {}

bool VehicleManagerCommandSender::sendHss(const std::vector<server::HssCoordinate>& coordinates) {
  return sendJson(makeSetHssCommand(coordinates));
}

bool VehicleManagerCommandSender::sendQr(const server::QrCoordinate& coordinate) {
  return sendJson(makeQrTargetCommand(coordinate));
}

bool VehicleManagerCommandSender::sendMissionCommand(const std::string& type, nlohmann::json payload) {
  return sendJson(makeMissionCommand(type, std::move(payload)));
}

bool VehicleManagerCommandSender::sendTimeSync(const utils::ServerTime& server_time) {
  return sendJson(makeTimeSyncCommand(server_time));
}

bool VehicleManagerCommandSender::sendJson(const nlohmann::json& command) {
  ensureSocketsReady();
  SocketHandle fd = ::socket(AF_INET, SOCK_DGRAM, 0);
  if (socketInvalid(fd)) {
    context_.events().publish({core::EventType::VEHICLE_MANAGER_COMMAND_FAILED, "VehicleManagerCommandSender", "UDP socket create failed"});
    return false;
  }
  sockaddr_in addr{};
  addr.sin_family = AF_INET;
  addr.sin_port = htons(static_cast<uint16_t>(config_.vehicle_command_port));
  if (::inet_pton(AF_INET, config_.vehicle_command_host.c_str(), &addr.sin_addr) != 1) {
    closeSocket(fd);
    context_.events().publish({core::EventType::VEHICLE_MANAGER_COMMAND_FAILED, "VehicleManagerCommandSender", "Invalid Vehicle Manager host", {{"host", config_.vehicle_command_host}}});
    return false;
  }
  auto payload = command.dump();
  auto sent = ::sendto(fd, payload.data(), static_cast<int>(payload.size()), 0, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
  closeSocket(fd);
  bool ok = sent == static_cast<int>(payload.size());
  context_.state().setVehicleManagerLastCommandResult({{"ok", ok}, {"command", command}, {"host", config_.vehicle_command_host}, {"port", config_.vehicle_command_port}});
  context_.events().publish({ok ? core::EventType::VEHICLE_MANAGER_COMMAND_SENT : core::EventType::VEHICLE_MANAGER_COMMAND_FAILED,
                             "VehicleManagerCommandSender",
                             ok ? "Vehicle Manager command sent" : "Vehicle Manager command failed",
                             {{"command", command.value("type", "")}}});
  return ok;
}

}  // namespace comm::vehicle
