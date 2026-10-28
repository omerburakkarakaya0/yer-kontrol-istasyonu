#pragma once

#include <filesystem>
#include <memory>
#include <string>
#include "core/EventBus.hpp"
#include "core/StateStore.hpp"

namespace comm::core {

struct ServerConfig {
  std::string base_url;
  std::string username;
  std::string password;
  int timeout_ms{1000};
  int max_retries{3};
};

struct VehicleManagerConfig {
  bool enabled{false};
  std::string telemetry_source{"mavlink"};
  std::string bind_host{"0.0.0.0"};
  int heartbeat_port{9100};
  int event_port{9101};
  std::string vehicle_command_host{"192.168.1.50"};
  int vehicle_command_port{9102};
  int heartbeat_timeout_ms{3000};
  int command_timeout_ms{500};
};

struct AppConfig {
  ServerConfig server;
  VehicleManagerConfig vehicle_manager;
  int team_number{1};
  double telemetry_upload_hz{1.0};
  double telemetry_max_allowed_hz{2.0};
  std::string mavlink_connection_url{"udp://:14550"};
  std::string log_dir{"./logs"};
  std::string sqlite_path{"./logs/events.db"};
  std::string packet_log_path{"./logs/packets.jsonl"};
  int websocket_port{8765};
  int rest_port{8090};
};

AppConfig loadConfig(const std::filesystem::path& path);

class AppContext {
 public:
  explicit AppContext(AppConfig config);

  AppConfig& config();
  StateStore& state();
  EventBus& events();

 private:
  AppConfig config_;
  StateStore state_;
  EventBus events_;
};

}  // namespace comm::core
