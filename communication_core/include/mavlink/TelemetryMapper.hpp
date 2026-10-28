#pragma once

#include "mavlink/VehicleState.hpp"
#include "server/Packets.hpp"

namespace comm::mavlink {

class TelemetryMapper {
 public:
  static server::TelemetryPacket map(int team_number, const VehicleState& state);
};

}  // namespace comm::mavlink
