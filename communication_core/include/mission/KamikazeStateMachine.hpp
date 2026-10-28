#pragma once

#include <optional>
#include "core/EventBus.hpp"
#include "mission/MissionEvent.hpp"
#include "server/KamikazeReporter.hpp"

namespace comm::mission {

class KamikazeStateMachine {
 public:
  KamikazeStateMachine(server::KamikazeReporter& reporter, core::EventBus& events);

  std::optional<server::KamikazePacket> update(const KamikazeEvent& event, utils::DayTime server_time);
  void reset();
  bool packetSent() const;

 private:
  server::KamikazeReporter& reporter_;
  core::EventBus& events_;
  bool diving_{false};
  bool sent_{false};
  utils::DayTime start_time_{};
};

}  // namespace comm::mission
