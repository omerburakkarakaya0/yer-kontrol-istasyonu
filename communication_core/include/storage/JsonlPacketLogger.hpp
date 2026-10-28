#pragma once

#include <filesystem>
#include <fstream>
#include <mutex>
#include <nlohmann/json.hpp>
#include <string>

namespace comm::storage {

class JsonlPacketLogger {
 public:
  explicit JsonlPacketLogger(std::filesystem::path path);

  void log(std::string direction,
           std::string endpoint,
           int http_status,
           const nlohmann::json& payload,
           std::string error_message = {});

 private:
  std::mutex mutex_;
  std::ofstream stream_;
};

}  // namespace comm::storage
