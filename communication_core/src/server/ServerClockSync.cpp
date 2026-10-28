#include "server/ServerClockSync.hpp"

#include "utils/TimeUtils.hpp"

namespace comm::server {

ServerClockSync::ServerClockSync(ICompetitionApi& api, core::StateStore& state) : api_(api), state_(state) {}

bool ServerClockSync::sync() {
  auto before = std::chrono::system_clock::now();
  auto result = api_.getServerTime();
  auto after = std::chrono::system_clock::now();
  if (!result.ok) return false;
  auto server_time = result.body.get<utils::ServerTime>();
  auto local_mid = before + (after - before) / 2;
  auto local_time = utils::serverTimeFromSystem(local_mid);
  auto server_ms = (((server_time.saat * 60 + server_time.dakika) * 60 + server_time.saniye) * 1000 + server_time.milisaniye);
  auto local_ms = (((local_time.saat * 60 + local_time.dakika) * 60 + local_time.saniye) * 1000 + local_time.milisaniye);
  {
    std::lock_guard<std::mutex> lock(mutex_);
    offset_ = std::chrono::milliseconds(server_ms - local_ms);
  }
  state_.setServerTime(server_time);
  return true;
}

utils::ServerTime ServerClockSync::serverNow() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return utils::serverTimeFromSystem(std::chrono::system_clock::now() + offset_);
}

std::chrono::milliseconds ServerClockSync::offset() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return offset_;
}

}  // namespace comm::server
