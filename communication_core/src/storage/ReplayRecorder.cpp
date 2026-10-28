#include "storage/ReplayRecorder.hpp"

namespace comm::storage {

void ReplayRecorder::recordVehicleSnapshot(const nlohmann::json& payload) {
  logger_.log("snapshot", "vehicle_state", 0, payload);
}

}  // namespace comm::storage
