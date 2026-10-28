#include "core/Watchdog.hpp"

namespace comm::core {

Watchdog::Watchdog(StateStore& state, EventBus& events) : state_(state), events_(events) {}
Watchdog::~Watchdog() { stop(); }

void Watchdog::start() {
  if (running_.exchange(true)) return;
  worker_ = std::thread(&Watchdog::loop, this);
}

void Watchdog::stop() {
  running_ = false;
  if (worker_.joinable()) worker_.join();
}

void Watchdog::loop() {
  while (running_) {
    auto now = std::chrono::steady_clock::now();
    auto status = state_.connectionStatus();
    if (status.mavlink_connected && now - status.last_mavlink_packet > mavlink_timeout_) {
      state_.markMavlinkConnected(false);
      events_.publish({EventType::MAVLINK_DISCONNECTED, "Watchdog", "MAVLink data timeout"});
    }
    if (status.last_successful_telemetry.time_since_epoch().count() != 0 &&
        now - status.last_successful_telemetry > telemetry_timeout_) {
      events_.publish({EventType::WATCHDOG_TIMEOUT, "Watchdog", "Telemetry upload has failed for more than 10 seconds"});
    }
    std::this_thread::sleep_for(std::chrono::seconds(1));
  }
}

}  // namespace comm::core
