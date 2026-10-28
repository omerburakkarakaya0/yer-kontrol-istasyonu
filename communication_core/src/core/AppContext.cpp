#include "core/AppContext.hpp"

#include <yaml-cpp/yaml.h>

namespace comm::core {

AppConfig loadConfig(const std::filesystem::path& path) {
  auto y = YAML::LoadFile(path.string());
  AppConfig c;
  c.server.base_url = y["server"]["base_url"].as<std::string>();
  c.server.username = y["server"]["username"].as<std::string>();
  c.server.password = y["server"]["password"].as<std::string>();
  c.server.timeout_ms = y["server"]["timeout_ms"].as<int>();
  c.server.max_retries = y["server"]["max_retries"].as<int>();
  if (y["vehicle_manager"]) {
    auto vm = y["vehicle_manager"];
    c.vehicle_manager.enabled = vm["enabled"].as<bool>(c.vehicle_manager.enabled);
    c.vehicle_manager.telemetry_source = vm["telemetry_source"].as<std::string>(c.vehicle_manager.telemetry_source);
    c.vehicle_manager.bind_host = vm["bind_host"].as<std::string>(c.vehicle_manager.bind_host);
    c.vehicle_manager.heartbeat_port = vm["heartbeat_port"].as<int>(c.vehicle_manager.heartbeat_port);
    c.vehicle_manager.event_port = vm["event_port"].as<int>(c.vehicle_manager.event_port);
    c.vehicle_manager.vehicle_command_host = vm["vehicle_command_host"].as<std::string>(c.vehicle_manager.vehicle_command_host);
    c.vehicle_manager.vehicle_command_port = vm["vehicle_command_port"].as<int>(c.vehicle_manager.vehicle_command_port);
    c.vehicle_manager.heartbeat_timeout_ms = vm["heartbeat_timeout_ms"].as<int>(c.vehicle_manager.heartbeat_timeout_ms);
    c.vehicle_manager.command_timeout_ms = vm["command_timeout_ms"].as<int>(c.vehicle_manager.command_timeout_ms);
  }
  c.team_number = y["team"]["team_number"].as<int>();
  c.telemetry_upload_hz = y["telemetry"]["upload_hz"].as<double>();
  c.telemetry_max_allowed_hz = y["telemetry"]["max_allowed_hz"].as<double>();
  c.mavlink_connection_url = y["mavlink"]["connection_url"].as<std::string>();
  c.log_dir = y["logging"]["log_dir"].as<std::string>();
  c.sqlite_path = y["logging"]["sqlite_path"].as<std::string>();
  c.packet_log_path = y["logging"]["packet_log_path"].as<std::string>();
  c.websocket_port = y["ipc"]["websocket_port"].as<int>();
  c.rest_port = y["ipc"]["rest_port"].as<int>();
  return c;
}

AppContext::AppContext(AppConfig config) : config_(std::move(config)) {}
AppConfig& AppContext::config() { return config_; }
StateStore& AppContext::state() { return state_; }
EventBus& AppContext::events() { return events_; }

}  // namespace comm::core
