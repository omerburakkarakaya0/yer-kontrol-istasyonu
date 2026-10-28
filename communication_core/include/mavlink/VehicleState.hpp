#pragma once

#include <chrono>
#include <nlohmann/json.hpp>
#include "utils/TimeUtils.hpp"

namespace comm::mavlink {

struct VehicleState {
  double latitude{};
  double longitude{};
  double altitude{};
  double pitch{};
  double yaw{};
  double roll{};
  double ground_speed{};
  int battery_percent{};
  bool autonomous_mode{};
  bool lock_active{};
  int target_center_x{};
  int target_center_y{};
  int target_width{};
  int target_height{};
  utils::DayTime gps_time;
  std::chrono::steady_clock::time_point received_at{std::chrono::steady_clock::now()};
};

void to_json(nlohmann::json& j, const VehicleState& s);

}  // namespace comm::mavlink
