#include <gtest/gtest.h>
#include "FakeCompetitionApi.hpp"
#include "core/StateStore.hpp"
#include "server/ServerClockSync.hpp"

TEST(ServerClockSync, StoresOffsetAndServerTime) {
  FakeCompetitionApi api;
  api.next.body = comm::utils::ServerTime{18, 12, 0, 0, 0};
  comm::core::StateStore state;
  comm::server::ServerClockSync sync(api, state);
  EXPECT_TRUE(sync.sync());
  EXPECT_TRUE(state.serverTime().has_value());
}
