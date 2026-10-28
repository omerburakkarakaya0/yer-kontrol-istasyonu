#include "storage/SqliteLogger.hpp"

#include <chrono>
#include <filesystem>
#include <stdexcept>
#include "utils/TimeUtils.hpp"

namespace comm::storage {

SqliteLogger::SqliteLogger(const std::filesystem::path& path) {
  std::filesystem::create_directories(path.parent_path());
  if (sqlite3_open(path.string().c_str(), &db_) != SQLITE_OK) {
    throw std::runtime_error("sqlite open failed");
  }
  initialize();
}

SqliteLogger::~SqliteLogger() {
  if (db_) sqlite3_close(db_);
}

void SqliteLogger::initialize() {
  const char* sql =
      "CREATE TABLE IF NOT EXISTS event_log ("
      "id INTEGER PRIMARY KEY AUTOINCREMENT,"
      "timestamp INTEGER NOT NULL,"
      "severity TEXT NOT NULL,"
      "module TEXT NOT NULL,"
      "event_type TEXT NOT NULL,"
      "message TEXT NOT NULL,"
      "metadata_json TEXT NOT NULL);";
  char* err = nullptr;
  if (sqlite3_exec(db_, sql, nullptr, nullptr, &err) != SQLITE_OK) {
    std::string msg = err ? err : "sqlite initialize failed";
    sqlite3_free(err);
    throw std::runtime_error(msg);
  }
}

void SqliteLogger::logEvent(std::string severity,
                            std::string module,
                            std::string event_type,
                            std::string message,
                            const nlohmann::json& metadata) {
  std::lock_guard<std::mutex> lock(mutex_);
  const char* sql =
      "INSERT INTO event_log(timestamp,severity,module,event_type,message,metadata_json)"
      "VALUES(?,?,?,?,?,?);";
  sqlite3_stmt* stmt = nullptr;
  sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr);
  auto ts = utils::epochMillis(std::chrono::system_clock::now()).count();
  sqlite3_bind_int64(stmt, 1, static_cast<sqlite3_int64>(ts));
  sqlite3_bind_text(stmt, 2, severity.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(stmt, 3, module.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(stmt, 4, event_type.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(stmt, 5, message.c_str(), -1, SQLITE_TRANSIENT);
  auto meta = metadata.dump();
  sqlite3_bind_text(stmt, 6, meta.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_step(stmt);
  sqlite3_finalize(stmt);
}

}  // namespace comm::storage
