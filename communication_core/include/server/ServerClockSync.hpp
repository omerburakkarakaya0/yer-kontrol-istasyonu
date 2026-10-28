#pragma once

#include <chrono>
#include <mutex>
#include "core/StateStore.hpp"
#include "server/ICompetitionApi.hpp"

namespace comm::server {

class ServerClockSync {
 public:
  ServerClockSync(ICompetitionApi& api, core::StateStore& state);

  bool sync();
  utils::ServerTime serverNow() const;
  std::chrono::milliseconds offset() const;

 private:
  ICompetitionApi& api_;
  core::StateStore& state_;
  mutable std::mutex mutex_;
  std::chrono::milliseconds offset_{0};
};

}  // namespace comm::server
