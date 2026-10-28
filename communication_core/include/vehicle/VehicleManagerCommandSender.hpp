#pragma once

#include <string>
#include <vector>
#include "core/AppContext.hpp"
#include "server/Packets.hpp"
#include "utils/TimeUtils.hpp"

namespace comm::vehicle {

class VehicleManagerCommandSender {
 public:
  VehicleManagerCommandSender(core::AppContext& context, core::VehicleManagerConfig config);

  bool sendHss(const std::vector<server::HssCoordinate>& coordinates);
  bool sendQr(const server::QrCoordinate& coordinate);
  bool sendMissionCommand(const std::string& type, nlohmann::json payload = nlohmann::json::object());
  bool sendTimeSync(const utils::ServerTime& server_time);
  bool sendJson(const nlohmann::json& command);

 private:
  core::AppContext& context_;
  core::VehicleManagerConfig config_;
};

}  // namespace comm::vehicle
