#pragma once

#include <atomic>
#include <thread>
#include "core/AppContext.hpp"

namespace comm::ipc {

namespace detail {
class ServerHolder;
}

}  // namespace comm::ipc

namespace comm::server {
class QrCoordinateClient;
class HssCoordinateClient;
}

namespace comm::vehicle {
class VehicleManagerCommandSender;
}

namespace comm::ipc {

class LocalWebSocketServer {
 public:
  explicit LocalWebSocketServer(core::AppContext& context);
  ~LocalWebSocketServer();

  void setVehicleIntegrations(server::QrCoordinateClient* qr_client,
                              server::HssCoordinateClient* hss_client,
                              vehicle::VehicleManagerCommandSender* command_sender);
  void start();
  void stop();

 private:
  core::AppContext& context_;
  server::QrCoordinateClient* qr_client_{nullptr};
  server::HssCoordinateClient* hss_client_{nullptr};
  vehicle::VehicleManagerCommandSender* command_sender_{nullptr};
  std::atomic_bool running_{false};
  std::thread worker_;
};

}  // namespace comm::ipc
