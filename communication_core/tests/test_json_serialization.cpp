#include <gtest/gtest.h>
#include "server/Packets.hpp"

TEST(JsonSerialization, TelemetryRoundTrip) {
  comm::server::TelemetryPacket p;
  p.takim_numarasi = 1;
  p.iha_enlem = 39.9;
  p.iha_boylam = 32.8;
  p.iha_batarya = 77;
  p.gps_saati = {10, 11, 12, 13};
  nlohmann::json j = p;
  auto decoded = j.get<comm::server::TelemetryPacket>();
  EXPECT_EQ(decoded.takim_numarasi, 1);
  EXPECT_DOUBLE_EQ(decoded.iha_enlem, 39.9);
  EXPECT_EQ(decoded.gps_saati.milisaniye, 13);
}

TEST(JsonSerialization, CoordinateRoundTrip) {
  comm::server::HssCoordinate h{4, 1.2, 3.4, 50};
  auto decoded = nlohmann::json(h).get<comm::server::HssCoordinate>();
  EXPECT_EQ(decoded.id, 4);
  EXPECT_DOUBLE_EQ(decoded.hssYaricap, 50);
}
