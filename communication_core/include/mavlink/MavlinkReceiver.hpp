#pragma once

#include <atomic>
#include <functional>
#include <string>
#include <thread>
#include "mavlink/VehicleState.hpp"

namespace comm::mavlink {

class MavlinkReceiver {
 public:
  using Callback = std::function<void(const VehicleState&)>;

  explicit MavlinkReceiver(std::string connection_url);
  ~MavlinkReceiver();

  void setCallback(Callback callback);
  void start();
  void stop();

 private:
  std::string connection_url_;
  Callback callback_;
  std::atomic_bool running_{false};
  std::thread worker_;
};

}  // namespace comm::mavlink
