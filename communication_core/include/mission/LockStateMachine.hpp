#pragma once

#include <optional>
#include "core/EventBus.hpp"
#include "mavlink/VehicleState.hpp"
#include "mission/MissionEvent.hpp"
#include "server/LockReporter.hpp"

namespace comm::mission {

class LockStateMachine {
 public:
  LockStateMachine(server::LockReporter& reporter, core::EventBus& events);

  std::optional<server::LockPacket> update(const TargetObservation& observation,
                                           const mavlink::VehicleState& vehicle,
                                           utils::DayTime server_time);
  void resetForNewTarget();
  bool packetSent() const;

 private:
  server::LockReporter& reporter_;
  core::EventBus& events_;
  bool sent_for_current_lock_{false};
};

}  // namespace comm::mission
