#include <gtest/gtest.h>
#include "FakeCompetitionApi.hpp"
#include "core/AppContext.hpp"
#include "server/AuthManager.hpp"
#include "server/HssCoordinateClient.hpp"
#include "utils/RetryPolicy.hpp"

struct RetryResult {
  bool should_retry{false};
  int value{0};
};

TEST(RetryPolicy, RetriesRecoverableErrors) {
  int calls = 0;
  comm::utils::RetryPolicy retry{2, std::chrono::milliseconds(0), std::chrono::milliseconds(0)};
  auto result = retry.run([&] {
    ++calls;
    return RetryResult{calls < 3, calls};
  });
  EXPECT_EQ(calls, 3);
  EXPECT_EQ(result.value, 3);
}

TEST(AuthManager, ReloginAfterExpiredSession) {
  FakeCompetitionApi api;
  comm::core::EventBus events;
  comm::server::AuthManager auth(api, events, "user", "pass");
  EXPECT_TRUE(auth.ensureLoggedIn());
  auth.markExpired();
  EXPECT_TRUE(auth.ensureLoggedIn());
  EXPECT_EQ(api.login_calls, 2);
}

TEST(HssCoordinateClient, HandlesEmptyAndNonEmptyLists) {
  comm::core::AppConfig cfg;
  comm::core::AppContext context(cfg);
  FakeCompetitionApi api;
  api.next.body = nlohmann::json::array();
  comm::server::HssCoordinateClient client(context, api);
  EXPECT_TRUE(client.fetchOnce());
  EXPECT_TRUE(context.state().hssCoordinates().empty());

  api.next.body = nlohmann::json::array({comm::server::HssCoordinate{1, 39.9, 32.8, 100.0}});
  EXPECT_TRUE(client.fetchOnce());
  EXPECT_EQ(context.state().hssCoordinates().size(), 1);
}
