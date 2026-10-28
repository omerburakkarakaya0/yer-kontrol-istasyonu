#include "vehicle/VehicleManagerPackets.hpp"

#include <functional>

namespace comm::vehicle {

std::optional<VehicleManagerStatus> parseStatus(const nlohmann::json& json) {
  if (!json.is_object() || json.value("type", "") != "status") return std::nullopt;
  VehicleManagerStatus status;
  status.raw = json;
  status.vehicle_id = json.value("vehicle_id", "");
  status.timestamp_ms = json.value("timestamp_ms", static_cast<std::int64_t>(0));
  status.mavlink_connected = json.value("mavlink_connected", false);
  status.server_connected = json.value("server_connected", false);
  if (json.contains("vehicle_state") && json["vehicle_state"].is_object()) {
    const auto& v = json["vehicle_state"];
    mavlink::VehicleState state;
    state.latitude = v.value("latitude", 0.0);
    state.longitude = v.value("longitude", 0.0);
    state.altitude = v.value("altitude", 0.0);
    state.pitch = v.value("pitch", 0.0);
    state.yaw = v.value("yaw", 0.0);
    state.roll = v.value("roll", 0.0);
    state.ground_speed = v.value("ground_speed", 0.0);
    state.battery_percent = v.value("battery_percent", 0);
    state.autonomous_mode = v.value("autonomous_mode", false);
    state.lock_active = v.value("lock_active", false);
    state.target_center_x = v.value("target_center_x", 0);
    state.target_center_y = v.value("target_center_y", 0);
    state.target_width = v.value("target_width", 0);
    state.target_height = v.value("target_height", 0);
    if (v.contains("gps_time")) state.gps_time = v["gps_time"].get<utils::DayTime>();
    state.received_at = std::chrono::steady_clock::now();
    status.vehicle_state = state;
  }
  if (json.contains("qr_coordinate") && json["qr_coordinate"].is_object()) {
    status.qr_coordinate = json["qr_coordinate"].get<server::QrCoordinate>();
  }
  if (json.contains("hss_coordinates") && json["hss_coordinates"].is_array()) {
    status.hss_coordinates_present = true;
    status.hss_coordinates = json["hss_coordinates"].get<std::vector<server::HssCoordinate>>();
  }
  if (json.contains("opponent_positions")) {
    status.opponent_positions_present = true;
    status.opponent_positions = json["opponent_positions"];
  }
  return status;
}

std::optional<VehicleManagerEvent> parseEvent(const nlohmann::json& json) {
  if (!json.is_object() || !json.contains("type")) return std::nullopt;
  VehicleManagerEvent event;
  event.raw = json;
  event.type = json.value("type", "");
  event.vehicle_id = json.value("vehicle_id", "");
  event.event_id = json.value("event_id", "");
  event.timestamp_ms = json.value("timestamp_ms", static_cast<std::int64_t>(0));
  event.payload = json.value("payload", nlohmann::json::object());
  return event;
}

std::string stableEventId(const VehicleManagerEvent& event) {
  if (!event.event_id.empty()) return event.event_id;
  auto material = event.type + "|" + std::to_string(event.timestamp_ms) + "|" + event.payload.dump();
  return std::to_string(std::hash<std::string>{}(material));
}

nlohmann::json makeSetHssCommand(const std::vector<server::HssCoordinate>& coordinates) {
  return {{"type", "SET_HSS"}, {"payload", {{"hss_koordinatlari", coordinates}}}};
}

nlohmann::json makeQrTargetCommand(const server::QrCoordinate& coordinate) {
  return {{"type", "QR_TARGET"}, {"payload", coordinate}};
}

nlohmann::json makeMissionCommand(const std::string& type, nlohmann::json payload) {
  return {{"type", type}, {"payload", std::move(payload)}};
}

nlohmann::json makeTimeSyncCommand(const utils::ServerTime& server_time) {
  return {{"type", "TIME_SYNC"}, {"payload", {{"sunucusaati", server_time}}}};
}

}  // namespace comm::vehicle
