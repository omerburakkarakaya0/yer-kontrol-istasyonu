#pragma once

#include "server/ICompetitionApi.hpp"

class FakeCompetitionApi : public comm::server::ICompetitionApi {
 public:
  comm::server::ApiResult next{200, true, false, nlohmann::json::object(), ""};
  int login_calls{0};
  int telemetry_calls{0};
  int lock_calls{0};
  int kamikaze_calls{0};

  comm::server::ApiResult login(const std::string&, const std::string&) override {
    ++login_calls;
    return next;
  }
  comm::server::ApiResult getServerTime() override { return next; }
  comm::server::ApiResult sendTelemetry(const comm::server::TelemetryPacket&) override {
    ++telemetry_calls;
    return next;
  }
  comm::server::ApiResult sendLockInfo(const comm::server::LockPacket&) override {
    ++lock_calls;
    return next;
  }
  comm::server::ApiResult sendKamikazeInfo(const comm::server::KamikazePacket&) override {
    ++kamikaze_calls;
    return next;
  }
  comm::server::ApiResult getQrCoordinate() override { return next; }
  comm::server::ApiResult getHssCoordinates() override { return next; }
};
