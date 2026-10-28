#pragma once

#include <filesystem>
#include <mutex>
#include <nlohmann/json.hpp>
#include <sqlite3.h>
#include <string>

namespace comm::storage {

class SqliteLogger {
 public:
  explicit SqliteLogger(const std::filesystem::path& path);
  ~SqliteLogger();

  SqliteLogger(const SqliteLogger&) = delete;
  SqliteLogger& operator=(const SqliteLogger&) = delete;

  void logEvent(std::string severity,
                std::string module,
                std::string event_type,
                std::string message,
                const nlohmann::json& metadata = nlohmann::json::object());

 private:
  void initialize();

  std::mutex mutex_;
  sqlite3* db_{nullptr};
};

}  // namespace comm::storage
