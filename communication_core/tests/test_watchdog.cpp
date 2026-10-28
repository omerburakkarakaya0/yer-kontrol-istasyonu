#include <gtest/gtest.h>
#include "core/Watchdog.hpp"

TEST(WatchdogState, VehicleAgeIsReported) {
  comm::core::StateStore state;
  comm::mavlink::VehicleState vehicle;
  vehicle.received_at = std::chrono::steady_clock::now() - std::chrono::milliseconds(25);
  state.updateVehicleState(vehicle);
  EXPECT_LT(state.vehicleStateAge().count(), 1000);
}
