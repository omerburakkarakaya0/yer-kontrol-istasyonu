#include "mavlink/MavlinkReceiver.hpp"

#include <chrono>
#include <thread>

namespace comm::mavlink {

MavlinkReceiver::MavlinkReceiver(std::string connection_url) : connection_url_(std::move(connection_url)) {}
MavlinkReceiver::~MavlinkReceiver() { stop(); }

void MavlinkReceiver::setCallback(Callback callback) { callback_ = std::move(callback); }

void MavlinkReceiver::start() {
  if (running_.exchange(true)) return;
  worker_ = std::thread([this] {
    while (running_) {
      // Placeholder adapter point for MAVSDK or generated MAVLink C decoder.
      std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }
  });
}

void MavlinkReceiver::stop() {
  running_ = false;
  if (worker_.joinable()) worker_.join();
}

}  // namespace comm::mavlink
