#include "core/StateStore.hpp"

namespace comm::core {

void StateStore::updateVehicleState(const mavlink::VehicleState& state) {
  std::lock_guard<std::mutex> lock(mutex_);
  vehicle_state_ = state;
  status_.mavlink_connected = true;
  status_.last_mavlink_packet = state.received_at;
}

std::optional<mavlink::VehicleState> StateStore::vehicleState() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return vehicle_state_;
}

std::chrono::milliseconds StateStore::vehicleStateAge() const {
  std::lock_guard<std::mutex> lock(mutex_);
  if (!vehicle_state_) return std::chrono::milliseconds::max();
  return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - vehicle_state_->received_at);
}

void StateStore::setServerTime(const utils::ServerTime& time) {
  std::lock_guard<std::mutex> lock(mutex_);
  server_time_ = time;
  server_time_set_at_ = std::chrono::steady_clock::now();
}

std::optional<utils::ServerTime> StateStore::serverTime() const {
  std::lock_guard<std::mutex> lock(mutex_);
  if (!server_time_) return std::nullopt;

  auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
      std::chrono::steady_clock::now() - server_time_set_at_);
  auto total_ms = static_cast<int64_t>(server_time_->milisaniye) +
                  static_cast<int64_t>(server_time_->saniye) * 1000 +
                  static_cast<int64_t>(server_time_->dakika) * 60 * 1000 +
                  static_cast<int64_t>(server_time_->saat) * 60 * 60 * 1000 +
                  elapsed.count();

  constexpr int64_t day_ms = 24LL * 60 * 60 * 1000;
  auto days_added = total_ms / day_ms;
  total_ms %= day_ms;
  if (total_ms < 0) {
    total_ms += day_ms;
    --days_added;
  }

  utils::ServerTime current = *server_time_;
  current.gun += static_cast<int>(days_added);
  current.saat = static_cast<int>(total_ms / (60 * 60 * 1000));
  total_ms %= 60 * 60 * 1000;
  current.dakika = static_cast<int>(total_ms / (60 * 1000));
  total_ms %= 60 * 1000;
  current.saniye = static_cast<int>(total_ms / 1000);
  current.milisaniye = static_cast<int>(total_ms % 1000);
  return current;
}
void StateStore::setQrCoordinate(const server::QrCoordinate& coordinate) { std::lock_guard<std::mutex> lock(mutex_); qr_coordinate_ = coordinate; }
std::optional<server::QrCoordinate> StateStore::qrCoordinate() const { std::lock_guard<std::mutex> lock(mutex_); return qr_coordinate_; }
void StateStore::setHssCoordinates(std::vector<server::HssCoordinate> coordinates) { std::lock_guard<std::mutex> lock(mutex_); hss_coordinates_ = std::move(coordinates); }
std::vector<server::HssCoordinate> StateStore::hssCoordinates() const { std::lock_guard<std::mutex> lock(mutex_); return hss_coordinates_; }
void StateStore::setOpponentPositions(nlohmann::json positions) { std::lock_guard<std::mutex> lock(mutex_); opponent_positions_ = std::move(positions); }
nlohmann::json StateStore::opponentPositions() const { std::lock_guard<std::mutex> lock(mutex_); return opponent_positions_; }
void StateStore::markVehicleManagerConnected(bool connected) { std::lock_guard<std::mutex> lock(mutex_); status_.vehicle_manager_connected = connected; }
void StateStore::markVehicleManagerHeartbeat() {
  std::lock_guard<std::mutex> lock(mutex_);
  status_.vehicle_manager_connected = true;
  status_.last_vehicle_manager_heartbeat = std::chrono::steady_clock::now();
}
void StateStore::setVehicleManagerLastStatus(nlohmann::json status) { std::lock_guard<std::mutex> lock(mutex_); vehicle_manager_last_status_ = std::move(status); }
nlohmann::json StateStore::vehicleManagerLastStatus() const { std::lock_guard<std::mutex> lock(mutex_); return vehicle_manager_last_status_; }
void StateStore::setVehicleManagerLastEvent(nlohmann::json event) { std::lock_guard<std::mutex> lock(mutex_); vehicle_manager_last_event_ = std::move(event); }
nlohmann::json StateStore::vehicleManagerLastEvent() const { std::lock_guard<std::mutex> lock(mutex_); return vehicle_manager_last_event_; }
void StateStore::setVehicleManagerLastCommandResult(nlohmann::json result) { std::lock_guard<std::mutex> lock(mutex_); vehicle_manager_last_command_result_ = std::move(result); }
nlohmann::json StateStore::vehicleManagerLastCommandResult() const { std::lock_guard<std::mutex> lock(mutex_); return vehicle_manager_last_command_result_; }
std::chrono::milliseconds StateStore::vehicleManagerLastSeenAge() const {
  std::lock_guard<std::mutex> lock(mutex_);
  if (status_.last_vehicle_manager_heartbeat.time_since_epoch().count() == 0) return std::chrono::milliseconds::max();
  return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - status_.last_vehicle_manager_heartbeat);
}
void StateStore::markMavlinkConnected(bool connected) { std::lock_guard<std::mutex> lock(mutex_); status_.mavlink_connected = connected; }
void StateStore::markServerConnected(bool connected) { std::lock_guard<std::mutex> lock(mutex_); status_.server_connected = connected; }
void StateStore::markSuccessfulServerRequest() { std::lock_guard<std::mutex> lock(mutex_); status_.server_connected = true; status_.last_successful_server_request = std::chrono::steady_clock::now(); }
void StateStore::markSuccessfulTelemetry() { std::lock_guard<std::mutex> lock(mutex_); status_.last_successful_telemetry = std::chrono::steady_clock::now(); }
ConnectionStatus StateStore::connectionStatus() const { std::lock_guard<std::mutex> lock(mutex_); return status_; }

}  // namespace comm::core
