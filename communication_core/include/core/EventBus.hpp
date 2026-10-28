#pragma once

#include <functional>
#include <mutex>
#include <nlohmann/json.hpp>
#include <string>
#include <unordered_map>
#include <vector>

namespace comm::core {

enum class EventType {
  MAVLINK_CONNECTED,
  MAVLINK_DISCONNECTED,
  SERVER_CONNECTED,
  SERVER_DISCONNECTED,
  LOGIN_SUCCESS,
  LOGIN_FAILED,
  TELEMETRY_SENT,
  TELEMETRY_REJECTED,
  LOCK_PACKET_SENT,
  LOCK_PACKET_REJECTED,
  KAMIKAZE_PACKET_SENT,
  KAMIKAZE_PACKET_REJECTED,
  QR_UPDATED,
  HSS_UPDATED,
  VALIDATION_ERROR,
  WATCHDOG_TIMEOUT,
  VEHICLE_MANAGER_CONNECTED,
  VEHICLE_MANAGER_DISCONNECTED,
  VEHICLE_MANAGER_STATUS_UPDATED,
  VEHICLE_MANAGER_EVENT_RECEIVED,
  VEHICLE_MANAGER_COMMAND_SENT,
  VEHICLE_MANAGER_COMMAND_FAILED
};

std::string toString(EventType type);

struct Event {
  EventType type;
  std::string module;
  std::string message;
  nlohmann::json metadata{nlohmann::json::object()};
};

class EventBus {
 public:
  using Handler = std::function<void(const Event&)>;

  int subscribe(Handler handler);
  void unsubscribe(int id);
  void publish(const Event& event);

 private:
  std::mutex mutex_;
  int next_id_{1};
  std::unordered_map<int, Handler> handlers_;
};

}  // namespace comm::core
