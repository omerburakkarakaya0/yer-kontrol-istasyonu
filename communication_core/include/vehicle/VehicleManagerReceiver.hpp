#pragma once

#include <atomic>
#include <chrono>
#include <mutex>
#include <string>
#include <thread>
#include <unordered_set>
#include "core/AppContext.hpp"
#include "server/ICompetitionApi.hpp"

namespace comm::vehicle {

class VehicleManagerReceiver {
 public:
  VehicleManagerReceiver(core::AppContext& context, server::ICompetitionApi& api, core::VehicleManagerConfig config);
  ~VehicleManagerReceiver();

  void start();
  void stop();
  bool handleStatusJson(const nlohmann::json& json);
  bool handleEventJson(const nlohmann::json& json);
  void checkHeartbeatTimeout();

 private:
  void heartbeatLoop();
  void eventLoop();
  void timeoutLoop();
  bool acceptEventId(const std::string& event_id);

  core::AppContext& context_;
  server::ICompetitionApi& api_;
  core::VehicleManagerConfig config_;
  std::atomic_bool running_{false};
  std::thread heartbeat_thread_;
  std::thread event_thread_;
  std::thread timeout_thread_;
  std::mutex duplicate_mutex_;
  std::unordered_set<std::string> processed_events_;
};

}  // namespace comm::vehicle
