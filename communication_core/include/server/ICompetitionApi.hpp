#pragma once

#include <optional>
#include <vector>
#include "server/Packets.hpp"
#include "utils/TimeUtils.hpp"

namespace comm::server {

struct ApiResult {
  int http_status{0};
  bool ok{false};
  bool should_retry{false};
  nlohmann::json body{nlohmann::json::object()};
  std::string error_message;
};

class ICompetitionApi {
 public:
  virtual ~ICompetitionApi() = default;
  virtual ApiResult login(const std::string& username, const std::string& password) = 0;
  virtual ApiResult getServerTime() = 0;
  virtual ApiResult sendTelemetry(const TelemetryPacket& packet) = 0;
  virtual ApiResult sendLockInfo(const LockPacket& packet) = 0;
  virtual ApiResult sendKamikazeInfo(const KamikazePacket& packet) = 0;
  virtual ApiResult getQrCoordinate() = 0;
  virtual ApiResult getHssCoordinates() = 0;
};

}  // namespace comm::server
