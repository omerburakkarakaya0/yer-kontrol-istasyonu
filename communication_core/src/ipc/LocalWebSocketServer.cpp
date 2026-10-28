#include "ipc/LocalWebSocketServer.hpp"

#include <chrono>
#include <httplib.h>
#include "ipc/UiMessageSchema.hpp"
#include "mavlink/VehicleState.hpp"
#include "server/HssCoordinateClient.hpp"
#include "server/QrCoordinateClient.hpp"
#include "utils/TimeUtils.hpp"
#include "vehicle/VehicleManagerCommandSender.hpp"

namespace comm::ipc {

nlohmann::json makeStatusMessage(const core::StateStore& state) {
  auto status = state.connectionStatus();
  return {
      {"type", "status"},
      {"mavlink_connected", status.mavlink_connected},
      {"server_connected", status.server_connected},
      {"vehicle_manager_connected", status.vehicle_manager_connected},
      {"vehicle_manager_last_seen_age_ms", state.vehicleManagerLastSeenAge().count()},
      {"vehicle_manager_last_status", state.vehicleManagerLastStatus()},
      {"vehicle_manager_last_event", state.vehicleManagerLastEvent()},
      {"vehicle_manager_last_command_result", state.vehicleManagerLastCommandResult()},
      {"vehicle_state_age_ms", state.vehicleStateAge().count()},
      {"server_time", state.serverTime().has_value() ? nlohmann::json(*state.serverTime()) : nlohmann::json(nullptr)},
      {"vehicle_state", state.vehicleState().has_value() ? nlohmann::json(*state.vehicleState()) : nlohmann::json(nullptr)},
      {"qr_coordinate", state.qrCoordinate().has_value() ? nlohmann::json(*state.qrCoordinate()) : nlohmann::json(nullptr)},
      {"hss_coordinates", state.hssCoordinates()},
      {"opponent_positions", state.opponentPositions()}};
}

double numberOr(const nlohmann::json& body, const char* key, double fallback = 0.0) {
  if (!body.contains(key) || body[key].is_null()) return fallback;
  if (body[key].is_number()) return body[key].get<double>();
  if (body[key].is_string()) {
    try {
      return std::stod(body[key].get<std::string>());
    } catch (...) {
      return fallback;
    }
  }
  return fallback;
}

int intOr(const nlohmann::json& body, const char* key, int fallback = 0) {
  return static_cast<int>(numberOr(body, key, fallback));
}

LocalWebSocketServer::LocalWebSocketServer(core::AppContext& context) : context_(context) {}
LocalWebSocketServer::~LocalWebSocketServer() { stop(); }

void LocalWebSocketServer::setVehicleIntegrations(server::QrCoordinateClient* qr_client,
                                                  server::HssCoordinateClient* hss_client,
                                                  vehicle::VehicleManagerCommandSender* command_sender) {
  qr_client_ = qr_client;
  hss_client_ = hss_client;
  command_sender_ = command_sender;
}

void LocalWebSocketServer::start() {
  if (running_.exchange(true)) return;
  worker_ = std::thread([this] {
    httplib::Server server;
    server.Get("/status", [this](const httplib::Request&, httplib::Response& res) {
      auto msg = makeStatusMessage(context_.state());
      msg["vehicle_command_host"] = context_.config().vehicle_manager.vehicle_command_host;
      msg["vehicle_command_port"] = context_.config().vehicle_manager.vehicle_command_port;
      res.set_content(msg.dump(), "application/json");
    });
    server.Get("/healthz", [](const httplib::Request&, httplib::Response& res) {
      res.set_content(R"({"ok":true})", "application/json");
    });
    server.Post("/vehicle/state", [this](const httplib::Request& req, httplib::Response& res) {
      auto body = nlohmann::json::parse(req.body, nullptr, false);
      if (body.is_discarded() || !body.is_object()) {
        res.status = 400;
        res.set_content(R"({"ok":false,"error":"invalid json"})", "application/json");
        return;
      }

      comm::mavlink::VehicleState state;
      state.latitude = numberOr(body, "latitude");
      state.longitude = numberOr(body, "longitude");
      state.altitude = numberOr(body, "altitude");
      state.pitch = numberOr(body, "pitch");
      state.yaw = numberOr(body, "yaw");
      state.roll = numberOr(body, "roll");
      state.ground_speed = numberOr(body, "ground_speed");
      state.battery_percent = intOr(body, "battery_percent");
      state.autonomous_mode = body.value("autonomous_mode", false);
      state.lock_active = body.value("lock_active", false);
      state.target_center_x = intOr(body, "target_center_x");
      state.target_center_y = intOr(body, "target_center_y");
      state.target_width = intOr(body, "target_width");
      state.target_height = intOr(body, "target_height");
      if (body.contains("gps_time") && body["gps_time"].is_object()) {
        state.gps_time = body["gps_time"].get<comm::utils::DayTime>();
      } else {
        state.gps_time = comm::utils::dayTimeFromSystem(std::chrono::system_clock::now());
      }
      state.received_at = std::chrono::steady_clock::now();
      context_.state().updateVehicleState(state);
      context_.state().setVehicleManagerLastStatus(body);
      res.set_content(nlohmann::json{{"ok", true}}.dump(), "application/json");
    });
    server.Post("/vehicle/send_qr", [this](const httplib::Request&, httplib::Response& res) {
      bool fetched = qr_client_ && qr_client_->fetchOnce();
      auto qr = context_.state().qrCoordinate();
      bool sent = command_sender_ && qr && command_sender_->sendQr(*qr);
      res.status = fetched ? 200 : 500;
      res.set_content(nlohmann::json{{"fetched", fetched}, {"sent", sent}}.dump(), "application/json");
    });
    server.Post("/vehicle/send_hss", [this](const httplib::Request&, httplib::Response& res) {
      bool fetched = hss_client_ && hss_client_->fetchOnce();
      auto hss = context_.state().hssCoordinates();
      bool sent = command_sender_ && command_sender_->sendHss(hss);
      res.status = fetched ? 200 : 500;
      res.set_content(nlohmann::json{{"fetched", fetched}, {"sent", sent}, {"count", hss.size()}}.dump(), "application/json");
    });
    server.listen("127.0.0.1", context_.config().rest_port);
    running_ = false;
  });
}

void LocalWebSocketServer::stop() {
  running_ = false;
  if (worker_.joinable()) worker_.detach();
}

}  // namespace comm::ipc
