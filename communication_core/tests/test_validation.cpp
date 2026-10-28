#include <gtest/gtest.h>
#include "utils/Validation.hpp"

TEST(Validation, AcceptsValidTelemetryPacket) {
  comm::server::TelemetryPacket p;
  p.iha_dikilme = 10;
  p.iha_yatis = -5;
  p.iha_yonelme = 180;
  p.iha_batarya = 90;
  p.iha_otonom = 1;
  p.iha_kilitlenme = 0;
  EXPECT_TRUE(comm::utils::validateTelemetry(p).valid);
}

TEST(Validation, RejectsOutOfRangeTelemetryPacket) {
  comm::server::TelemetryPacket p;
  p.iha_dikilme = 91;
  p.iha_yatis = -91;
  p.iha_yonelme = 361;
  p.iha_batarya = 101;
  p.iha_otonom = 2;
  p.iha_kilitlenme = -1;
  auto result = comm::utils::validateTelemetry(p);
  EXPECT_FALSE(result.valid);
  EXPECT_EQ(result.errors.size(), 6);
}
