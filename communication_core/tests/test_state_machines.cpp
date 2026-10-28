#include <gtest/gtest.h>
#include "FakeCompetitionApi.hpp"
#include "mission/KamikazeStateMachine.hpp"
#include "mission/LockStateMachine.hpp"

TEST(LockStateMachine, SendsOnlyOnePacketForSameLock) {
  FakeCompetitionApi api;
  comm::server::LockReporter reporter(api);
  comm::core::EventBus events;
  comm::mission::LockStateMachine sm(reporter, events);
  comm::mavlink::VehicleState vehicle;
  vehicle.autonomous_mode = true;
  comm::mission::TargetObservation obs;
  obs.lock_condition = true;
  EXPECT_TRUE(sm.update(obs, vehicle, {1, 2, 3, 4}).has_value());
  EXPECT_FALSE(sm.update(obs, vehicle, {1, 2, 4, 4}).has_value());
  EXPECT_EQ(api.lock_calls, 1);
}

TEST(KamikazeStateMachine, SendsOnlyOnePacketAndRejectsEmptyQr) {
  FakeCompetitionApi api;
  comm::server::KamikazeReporter reporter(api);
  comm::core::EventBus events;
  comm::mission::KamikazeStateMachine sm(reporter, events);
  EXPECT_FALSE(sm.update({true, true, ""}, {1, 2, 3, 4}).has_value());
  EXPECT_TRUE(sm.update({false, true, "QR-42"}, {1, 2, 4, 4}).has_value());
  EXPECT_FALSE(sm.update({false, true, "QR-42"}, {1, 2, 5, 4}).has_value());
  EXPECT_EQ(api.kamikaze_calls, 1);
}
