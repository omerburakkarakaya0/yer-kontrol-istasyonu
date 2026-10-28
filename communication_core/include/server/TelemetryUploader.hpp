#pragma once

#include <atomic>
#include <thread>
#include "core/AppContext.hpp"
#include "server/ICompetitionApi.hpp"
#include "utils/RateLimiter.hpp"

namespace comm::server {

class TelemetryUploader {
 public:
  TelemetryUploader(core::AppContext& context, ICompetitionApi& api);
  ~TelemetryUploader();

  void start();
  void stop();
  bool uploadOnce();

 private:
  void loop();

  core::AppContext& context_;
  ICompetitionApi& api_;
  utils::RateLimiter limiter_;
  std::atomic_bool running_{false};
  std::thread worker_;
};

}  // namespace comm::server
