#pragma once

#include <chrono>
#include <mutex>

namespace comm::utils {

class RateLimiter {
 public:
  explicit RateLimiter(double max_hz)
      : min_interval_(std::chrono::duration_cast<std::chrono::steady_clock::duration>(
            std::chrono::duration<double>(1.0 / max_hz))) {}

  bool allow(std::chrono::steady_clock::time_point now = std::chrono::steady_clock::now()) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!has_last_ || now - last_ >= min_interval_) {
      last_ = now;
      has_last_ = true;
      return true;
    }
    return false;
  }

  std::chrono::steady_clock::duration minInterval() const { return min_interval_; }

 private:
  std::chrono::steady_clock::duration min_interval_;
  std::chrono::steady_clock::time_point last_{};
  bool has_last_{false};
  mutable std::mutex mutex_;
};

}  // namespace comm::utils
