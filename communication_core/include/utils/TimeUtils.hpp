#pragma once

#include <chrono>
#include <cstdint>
#include <nlohmann/json.hpp>

namespace comm::utils {

struct ServerTime {
  int gun{0};
  int saat{0};
  int dakika{0};
  int saniye{0};
  int milisaniye{0};
};

struct DayTime {
  int saat{0};
  int dakika{0};
  int saniye{0};
  int milisaniye{0};
};

void to_json(nlohmann::json& j, const ServerTime& t);
void from_json(const nlohmann::json& j, ServerTime& t);
void to_json(nlohmann::json& j, const DayTime& t);
void from_json(const nlohmann::json& j, DayTime& t);

DayTime dayTimeFromSystem(std::chrono::system_clock::time_point tp);
ServerTime serverTimeFromSystem(std::chrono::system_clock::time_point tp);
std::chrono::milliseconds epochMillis(std::chrono::system_clock::time_point tp);

}  // namespace comm::utils
