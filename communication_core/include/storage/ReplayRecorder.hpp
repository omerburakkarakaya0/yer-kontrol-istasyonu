#pragma once

#include "storage/JsonlPacketLogger.hpp"

namespace comm::storage {

class ReplayRecorder {
 public:
  explicit ReplayRecorder(JsonlPacketLogger& logger) : logger_(logger) {}
  void recordVehicleSnapshot(const nlohmann::json& payload);

 private:
  JsonlPacketLogger& logger_;
};

}  // namespace comm::storage
