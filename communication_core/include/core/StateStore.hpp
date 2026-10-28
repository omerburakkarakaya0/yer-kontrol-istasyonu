#pragma once

#include <chrono>
#include <mutex>
#include <optional>
#include <vector>
#include "mavlink/VehicleState.hpp"
#include "server/Packets.hpp"
#include "utils/TimeUtils.hpp"

namespace comm::core {

struct ConnectionStatus {
  bool mavlink_connected{false};
  bool server_connected{false};
  bool vehicle_manager_connected{false};
  std::chrono::steady_clock::time_point last_mavlink_packet{};
  std::chrono::steady_clock::time_point last_successful_server_request{};
  std::chrono::steady_clock::time_point last_successful_telemetry{};
  std::chrono::steady_clock::time_point last_vehicle_manager_heartbeat{};
};

class StateStore {
 public:
  void updateVehicleState(const mavlink::VehicleState& state);
  std::optional<mavlink::VehicleState> vehicleState() const;
  std::chrono::milliseconds vehicleStateAge() const;

  void setServerTime(const utils::ServerTime& time);
  std::optional<utils::ServerTime> serverTime() const;

  void setQrCoordinate(const server::QrCoordinate& coordinate);
  std::optional<server::QrCoordinate> qrCoordinate() const;

  void setHssCoordinates(std::vector<server::HssCoordinate> coordinates);
  std::vector<server::HssCoordinate> hssCoordinates() const;

  void setOpponentPositions(nlohmann::json positions);
  nlohmann::json opponentPositions() const;

  void markVehicleManagerConnected(bool connected);
  void markVehicleManagerHeartbeat();
  void setVehicleManagerLastStatus(nlohmann::json status);
  nlohmann::json vehicleManagerLastStatus() const;
  void setVehicleManagerLastEvent(nlohmann::json event);
  nlohmann::json vehicleManagerLastEvent() const;
  void setVehicleManagerLastCommandResult(nlohmann::json result);
  nlohmann::json vehicleManagerLastCommandResult() const;
  std::chrono::milliseconds vehicleManagerLastSeenAge() const;

  void markMavlinkConnected(bool connected);
  void markServerConnected(bool connected);
  void markSuccessfulServerRequest();
  void markSuccessfulTelemetry();
  ConnectionStatus connectionStatus() const;

 private:
  mutable std::mutex mutex_;
  std::optional<mavlink::VehicleState> vehicle_state_;
  std::optional<utils::ServerTime> server_time_;
  std::chrono::steady_clock::time_point server_time_set_at_{};
  std::optional<server::QrCoordinate> qr_coordinate_;
  std::vector<server::HssCoordinate> hss_coordinates_;
  nlohmann::json opponent_positions_{nlohmann::json::array()};
  nlohmann::json vehicle_manager_last_status_{nlohmann::json::object()};
  nlohmann::json vehicle_manager_last_event_{nlohmann::json::object()};
  nlohmann::json vehicle_manager_last_command_result_{nlohmann::json::object()};
  ConnectionStatus status_;
};

}  // namespace comm::core
