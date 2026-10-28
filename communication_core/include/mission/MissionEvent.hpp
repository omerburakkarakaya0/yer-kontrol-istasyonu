#pragma once

#include <string>
#include "utils/TimeUtils.hpp"

namespace comm::mission {

struct TargetObservation {
  bool target_visible{false};
  bool lock_condition{false};
  int center_x{};
  int center_y{};
  int width{};
  int height{};
};

struct KamikazeEvent {
  bool dive_started{false};
  bool qr_read{false};
  std::string qr_text;
};

}  // namespace comm::mission
