#include "mission/LockStateMachine.hpp"

namespace comm::mission {

LockStateMachine::LockStateMachine(server::LockReporter& reporter, core::EventBus& events)
    : reporter_(reporter), events_(events) {}

std::optional<server::LockPacket> LockStateMachine::update(const TargetObservation& observation,
                                                           const mavlink::VehicleState& vehicle,
                                                           utils::DayTime server_time) {
  if (!observation.lock_condition || sent_for_current_lock_) return std::nullopt;
  server::LockPacket packet{server_time, vehicle.autonomous_mode ? 1 : 0};
  auto result = reporter_.report(packet);
  if (result.ok) {
    sent_for_current_lock_ = true;
    events_.publish({core::EventType::LOCK_PACKET_SENT, "LockStateMachine", "Lock packet sent", {{"http_status", result.http_status}}});
    return packet;
  }
  return std::nullopt;
}

void LockStateMachine::resetForNewTarget() { sent_for_current_lock_ = false; }
bool LockStateMachine::packetSent() const { return sent_for_current_lock_; }

}  // namespace comm::mission
