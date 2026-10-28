#include "core/EventBus.hpp"

namespace comm::core {

std::string toString(EventType type) {
  switch (type) {
    case EventType::MAVLINK_CONNECTED: return "MAVLINK_CONNECTED";
    case EventType::MAVLINK_DISCONNECTED: return "MAVLINK_DISCONNECTED";
    case EventType::SERVER_CONNECTED: return "SERVER_CONNECTED";
    case EventType::SERVER_DISCONNECTED: return "SERVER_DISCONNECTED";
    case EventType::LOGIN_SUCCESS: return "LOGIN_SUCCESS";
    case EventType::LOGIN_FAILED: return "LOGIN_FAILED";
    case EventType::TELEMETRY_SENT: return "TELEMETRY_SENT";
    case EventType::TELEMETRY_REJECTED: return "TELEMETRY_REJECTED";
    case EventType::LOCK_PACKET_SENT: return "LOCK_PACKET_SENT";
    case EventType::LOCK_PACKET_REJECTED: return "LOCK_PACKET_REJECTED";
    case EventType::KAMIKAZE_PACKET_SENT: return "KAMIKAZE_PACKET_SENT";
    case EventType::KAMIKAZE_PACKET_REJECTED: return "KAMIKAZE_PACKET_REJECTED";
    case EventType::QR_UPDATED: return "QR_UPDATED";
    case EventType::HSS_UPDATED: return "HSS_UPDATED";
    case EventType::VALIDATION_ERROR: return "VALIDATION_ERROR";
    case EventType::WATCHDOG_TIMEOUT: return "WATCHDOG_TIMEOUT";
    case EventType::VEHICLE_MANAGER_CONNECTED: return "VEHICLE_MANAGER_CONNECTED";
    case EventType::VEHICLE_MANAGER_DISCONNECTED: return "VEHICLE_MANAGER_DISCONNECTED";
    case EventType::VEHICLE_MANAGER_STATUS_UPDATED: return "VEHICLE_MANAGER_STATUS_UPDATED";
    case EventType::VEHICLE_MANAGER_EVENT_RECEIVED: return "VEHICLE_MANAGER_EVENT_RECEIVED";
    case EventType::VEHICLE_MANAGER_COMMAND_SENT: return "VEHICLE_MANAGER_COMMAND_SENT";
    case EventType::VEHICLE_MANAGER_COMMAND_FAILED: return "VEHICLE_MANAGER_COMMAND_FAILED";
  }
  return "UNKNOWN";
}

int EventBus::subscribe(Handler handler) {
  std::lock_guard<std::mutex> lock(mutex_);
  int id = next_id_++;
  handlers_[id] = std::move(handler);
  return id;
}

void EventBus::unsubscribe(int id) {
  std::lock_guard<std::mutex> lock(mutex_);
  handlers_.erase(id);
}

void EventBus::publish(const Event& event) {
  std::vector<Handler> handlers;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    for (auto& [_, handler] : handlers_) handlers.push_back(handler);
  }
  for (auto& handler : handlers) handler(event);
}

}  // namespace comm::core
