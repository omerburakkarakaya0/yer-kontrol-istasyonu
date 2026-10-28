#include "mission/KamikazeStateMachine.hpp"

namespace comm::mission {

KamikazeStateMachine::KamikazeStateMachine(server::KamikazeReporter& reporter, core::EventBus& events)
    : reporter_(reporter), events_(events) {}

std::optional<server::KamikazePacket> KamikazeStateMachine::update(const KamikazeEvent& event, utils::DayTime server_time) {
  if (sent_) return std::nullopt;
  if (event.dive_started && !diving_) {
    diving_ = true;
    start_time_ = server_time;
  }
  if (!diving_ || !event.qr_read || event.qr_text.empty()) return std::nullopt;
  server::KamikazePacket packet{start_time_, server_time, event.qr_text};
  auto result = reporter_.report(packet);
  if (result.ok) {
    sent_ = true;
    events_.publish({core::EventType::KAMIKAZE_PACKET_SENT, "KamikazeStateMachine", "Kamikaze packet sent", {{"http_status", result.http_status}}});
    return packet;
  }
  return std::nullopt;
}

void KamikazeStateMachine::reset() {
  diving_ = false;
  sent_ = false;
  start_time_ = {};
}

bool KamikazeStateMachine::packetSent() const { return sent_; }

}  // namespace comm::mission
