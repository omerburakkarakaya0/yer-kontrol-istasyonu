#include <filesystem>
#include <iostream>
#include <thread>
#include <spdlog/sinks/basic_file_sink.h>
#include <spdlog/sinks/stdout_color_sinks.h>
#include <spdlog/spdlog.h>
#include "core/AppContext.hpp"
#include "core/Watchdog.hpp"
#include "ipc/LocalWebSocketServer.hpp"
#include "mavlink/MavlinkReceiver.hpp"
#include "server/AuthManager.hpp"
#include "server/CompetitionApiClient.hpp"
#include "server/HssCoordinateClient.hpp"
#include "server/QrCoordinateClient.hpp"
#include "server/ServerClockSync.hpp"
#include "server/TelemetryUploader.hpp"
#include "storage/JsonlPacketLogger.hpp"
#include "storage/SqliteLogger.hpp"
#include "vehicle/VehicleManagerCommandSender.hpp"
#include "vehicle/VehicleManagerReceiver.hpp"

int main(int argc, char** argv) {
  const std::filesystem::path config_path = argc > 1 ? argv[1] : "config/config.yaml";
  auto config = comm::core::loadConfig(config_path);
  std::filesystem::create_directories(config.log_dir);

  auto console_sink = std::make_shared<spdlog::sinks::stdout_color_sink_mt>();
  auto file_sink = std::make_shared<spdlog::sinks::basic_file_sink_mt>(config.log_dir + "/service.log", true);
  auto logger = std::make_shared<spdlog::logger>("communication_core", spdlog::sinks_init_list{console_sink, file_sink});
  spdlog::set_default_logger(logger);

  comm::core::AppContext context(config);
  comm::storage::JsonlPacketLogger packet_logger(config.packet_log_path);
  comm::storage::SqliteLogger sqlite_logger(config.sqlite_path);
  int event_subscription = context.events().subscribe([&](const comm::core::Event& event) {
    spdlog::info("[{}] {}", comm::core::toString(event.type), event.message);
    sqlite_logger.logEvent("INFO", event.module, comm::core::toString(event.type), event.message, event.metadata);
  });

  comm::server::CompetitionApiClient api(config.server, packet_logger);
  comm::server::AuthManager auth(api, context.events(), config.server.username, config.server.password);
  api.setAuthManager(&auth);
  auth.ensureLoggedIn();

  comm::server::ServerClockSync clock(api, context.state());
  clock.sync();
  std::thread([&clock] {
    while (true) {
      std::this_thread::sleep_for(std::chrono::seconds(5));
      clock.sync();
    }
  }).detach();
  if (auto server_time = context.state().serverTime()) {
    // Sent again after command sender construction below.
  }

  comm::mavlink::MavlinkReceiver mavlink(config.mavlink_connection_url);
  mavlink.setCallback([&](const comm::mavlink::VehicleState& state) { context.state().updateVehicleState(state); });
  if (!config.vehicle_manager.enabled || config.vehicle_manager.telemetry_source == "mavlink") {
    mavlink.start();
  }

  comm::vehicle::VehicleManagerCommandSender vehicle_sender(context, config.vehicle_manager);
  comm::vehicle::VehicleManagerReceiver vehicle_receiver(context, api, config.vehicle_manager);
  comm::server::QrCoordinateClient qr_client(context, api);
  comm::server::HssCoordinateClient hss_client(context, api);
  if (config.vehicle_manager.enabled) {
    vehicle_receiver.start();
    if (auto server_time = context.state().serverTime()) vehicle_sender.sendTimeSync(*server_time);
  }
  comm::server::TelemetryUploader uploader(context, api);
  comm::core::Watchdog watchdog(context.state(), context.events());
  comm::ipc::LocalWebSocketServer ipc(context);
  ipc.setVehicleIntegrations(&qr_client, &hss_client, &vehicle_sender);
  ipc.start();
  uploader.start();
  watchdog.start();

  spdlog::info("Communication Core Service is running. Local REST: http://127.0.0.1:{}", config.rest_port);
  std::cout << "Communication Core Service is running. Stop the process to exit.\n";
  while (true) {
    std::this_thread::sleep_for(std::chrono::seconds(1));
  }

  watchdog.stop();
  uploader.stop();
  vehicle_receiver.stop();
  mavlink.stop();
  ipc.stop();
  context.events().unsubscribe(event_subscription);
  return 0;
}
