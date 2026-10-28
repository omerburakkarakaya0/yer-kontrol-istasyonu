#pragma once

#include <atomic>
#include <chrono>
#include <thread>
#include "core/EventBus.hpp"
#include "core/StateStore.hpp"

namespace comm::core {

class Watchdog {
 public:
  Watchdog(StateStore& state, EventBus& events);
  ~Watchdog();

  void start();
  void stop();

 private:
  void loop();

  StateStore& state_;
  EventBus& events_;
  std::atomic_bool running_{false};
  std::thread worker_;
  std::chrono::seconds mavlink_timeout_{3};
  std::chrono::seconds telemetry_timeout_{10};
};

}  // namespace comm::core
