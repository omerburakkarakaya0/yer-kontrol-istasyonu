#include "utils/TimeUtils.hpp"

#include <ctime>

namespace comm::utils {

void to_json(nlohmann::json& j, const ServerTime& t) {
  j = {{"gun", t.gun}, {"saat", t.saat}, {"dakika", t.dakika}, {"saniye", t.saniye}, {"milisaniye", t.milisaniye}};
}

void from_json(const nlohmann::json& j, ServerTime& t) {
  t.gun = j.value("gun", 0);
  t.saat = j.value("saat", 0);
  t.dakika = j.value("dakika", 0);
  t.saniye = j.value("saniye", 0);
  t.milisaniye = j.value("milisaniye", 0);
}

void to_json(nlohmann::json& j, const DayTime& t) {
  j = {{"saat", t.saat}, {"dakika", t.dakika}, {"saniye", t.saniye}, {"milisaniye", t.milisaniye}};
}

void from_json(const nlohmann::json& j, DayTime& t) {
  t.saat = j.value("saat", 0);
  t.dakika = j.value("dakika", 0);
  t.saniye = j.value("saniye", 0);
  t.milisaniye = j.value("milisaniye", 0);
}

DayTime dayTimeFromSystem(std::chrono::system_clock::time_point tp) {
  auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(tp.time_since_epoch()) % 1000;
  std::time_t tt = std::chrono::system_clock::to_time_t(tp);
  std::tm tm{};
#ifdef _WIN32
  localtime_s(&tm, &tt);
#else
  localtime_r(&tt, &tm);
#endif
  return DayTime{tm.tm_hour, tm.tm_min, tm.tm_sec, static_cast<int>(ms.count())};
}

ServerTime serverTimeFromSystem(std::chrono::system_clock::time_point tp) {
  auto day = dayTimeFromSystem(tp);
  std::time_t tt = std::chrono::system_clock::to_time_t(tp);
  std::tm tm{};
#ifdef _WIN32
  localtime_s(&tm, &tt);
#else
  localtime_r(&tt, &tm);
#endif
  return ServerTime{tm.tm_mday, day.saat, day.dakika, day.saniye, day.milisaniye};
}

std::chrono::milliseconds epochMillis(std::chrono::system_clock::time_point tp) {
  return std::chrono::duration_cast<std::chrono::milliseconds>(tp.time_since_epoch());
}

}  // namespace comm::utils
