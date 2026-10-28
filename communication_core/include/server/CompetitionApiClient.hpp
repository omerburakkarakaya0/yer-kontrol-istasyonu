#pragma once

#include <mutex>
#include <memory>
#include <string>
#include <httplib.h>
#include "core/AppContext.hpp"
#include "server/ICompetitionApi.hpp"
#include "storage/JsonlPacketLogger.hpp"
#include "utils/RetryPolicy.hpp"

namespace comm::server {

class AuthManager;

class CompetitionApiClient : public ICompetitionApi {
 public:
  CompetitionApiClient(core::ServerConfig config, storage::JsonlPacketLogger& packet_logger);

  void setAuthManager(AuthManager* auth_manager);
  static nlohmann::json loginPayload(const std::string& username, const std::string& password);

  ApiResult login(const std::string& username, const std::string& password) override;
  ApiResult getServerTime() override;
  ApiResult sendTelemetry(const TelemetryPacket& packet) override;
  ApiResult sendLockInfo(const LockPacket& packet) override;
  ApiResult sendKamikazeInfo(const KamikazePacket& packet) override;
  ApiResult getQrCoordinate() override;
  ApiResult getHssCoordinates() override;

 private:
  ApiResult postJson(const std::string& endpoint, const nlohmann::json& payload, bool allow_reauth);
  ApiResult postJsonText(const std::string& endpoint, const std::string& payload, nlohmann::json log_payload, bool allow_reauth);
  ApiResult getJson(const std::string& endpoint, bool allow_reauth);
  ApiResult classify(int status, nlohmann::json body, std::string error = {}) const;
  httplib::Headers headers() const;
  void updateSessionCookie(const httplib::Result& response);
  static std::string telemetryPayloadText(const TelemetryPacket& packet);
  static nlohmann::json telemetryLogPayload(const TelemetryPacket& packet);

  core::ServerConfig config_;
  storage::JsonlPacketLogger& packet_logger_;
  AuthManager* auth_manager_{nullptr};
  mutable std::mutex session_mutex_;
  std::string session_cookie_;
};

}  // namespace comm::server
