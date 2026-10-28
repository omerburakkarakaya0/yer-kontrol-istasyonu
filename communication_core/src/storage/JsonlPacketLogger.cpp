#include "storage/JsonlPacketLogger.hpp"

#include <chrono>
#include <filesystem>
#include "utils/TimeUtils.hpp"

namespace comm::storage {

JsonlPacketLogger::JsonlPacketLogger(std::filesystem::path path) {
  std::filesystem::create_directories(path.parent_path());
  stream_.open(path, std::ios::app);
}

void JsonlPacketLogger::log(std::string direction,
                            std::string endpoint,
                            int http_status,
                            const nlohmann::json& payload,
                            std::string error_message) {
  std::lock_guard<std::mutex> lock(mutex_);
  nlohmann::json row = {
      {"timestamp", utils::epochMillis(std::chrono::system_clock::now()).count()},
      {"direction", std::move(direction)},
      {"endpoint", std::move(endpoint)},
      {"http_status", http_status},
      {"payload", payload},
      {"error_message", std::move(error_message)}};
  stream_ << row.dump() << '\n';
  stream_.flush();
}

}  // namespace comm::storage
