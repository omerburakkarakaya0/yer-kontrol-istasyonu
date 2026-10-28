#pragma once

#include <optional>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include "mavlink/VehicleState.hpp"
#include "server/Packets.hpp"

namespace comm::vehicle {

struct VehicleManagerStatus {
  std::string vehicle_id;
  std::int64_t timestamp_ms{};
  bool mavlink_connected{false};
  bool server_connected{false};
  std::optional<mavlink::VehicleState> vehicle_state;
  std::optional<server::QrCoordinate> qr_coordinate;
  bool hss_coordinates_present{false};
  std::vector<server::HssCoordinate> hss_coordinates;
  bool opponent_positions_present{false};
  nlohmann::json opponent_positions{nlohmann::json::array()};
  nlohmann::json raw{nlohmann::json::object()};
};

struct VehicleManagerEvent {
  std::string type;
  std::string vehicle_id;
  std::string event_id;
  std::int64_t timestamp_ms{};
  nlohmann::json payload{nlohmann::json::object()};
  nlohmann::json raw{nlohmann::json::object()};
};

std::optional<VehicleManagerStatus> parseStatus(const nlohmann::json& json);
std::optional<VehicleManagerEvent> parseEvent(const nlohmann::json& json);
std::string stableEventId(const VehicleManagerEvent& event);

nlohmann::json makeSetHssCommand(const std::vector<server::HssCoordinate>& coordinates);
nlohmann::json makeQrTargetCommand(const server::QrCoordinate& coordinate);
nlohmann::json makeMissionCommand(const std::string& type, nlohmann::json payload = nlohmann::json::object());
nlohmann::json makeTimeSyncCommand(const utils::ServerTime& server_time);

}  // namespace comm::vehicle
