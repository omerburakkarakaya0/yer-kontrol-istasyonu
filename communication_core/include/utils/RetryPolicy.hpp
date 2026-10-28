#pragma once

#include <chrono>
#include <thread>

namespace comm::utils {

struct RetryPolicy {
  int max_retries{3};
  std::chrono::milliseconds base_delay{100};
  std::chrono::milliseconds max_delay{1500};

  std::chrono::milliseconds delayForAttempt(int attempt) const {
    auto delay = base_delay * (1 << attempt);
    return delay > max_delay ? max_delay : delay;
  }

  template <typename Fn>
  auto run(Fn&& fn) const {
    decltype(fn()) result{};
    for (int attempt = 0; attempt <= max_retries; ++attempt) {
      result = fn();
      if (!result.should_retry || attempt == max_retries) {
        return result;
      }
      std::this_thread::sleep_for(delayForAttempt(attempt));
    }
    return result;
  }
};

}  // namespace comm::utils
