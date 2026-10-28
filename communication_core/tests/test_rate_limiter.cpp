#include <gtest/gtest.h>
#include "utils/RateLimiter.hpp"

TEST(RateLimiter, AllowsOneHzIntervals) {
  comm::utils::RateLimiter limiter(1.0);
  auto t = std::chrono::steady_clock::now();
  EXPECT_TRUE(limiter.allow(t));
  EXPECT_FALSE(limiter.allow(t + std::chrono::milliseconds(999)));
  EXPECT_TRUE(limiter.allow(t + std::chrono::milliseconds(1000)));
}

TEST(RateLimiter, NeverAllowsAboveTwoHz) {
  comm::utils::RateLimiter limiter(2.0);
  auto t = std::chrono::steady_clock::now();
  EXPECT_TRUE(limiter.allow(t));
  EXPECT_FALSE(limiter.allow(t + std::chrono::milliseconds(499)));
  EXPECT_TRUE(limiter.allow(t + std::chrono::milliseconds(500)));
}
