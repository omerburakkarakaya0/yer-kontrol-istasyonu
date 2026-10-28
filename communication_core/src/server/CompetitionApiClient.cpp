#include "server/CompetitionApiClient.hpp"

#include <cmath>
#include <iomanip>
#include <httplib.h>
#include <sstream>
#include "server/AuthManager.hpp"

namespace comm::server {

CompetitionApiClient::CompetitionApiClient(core::ServerConfig config, storage::JsonlPacketLogger& packet_logger)
    : config_(std::move(config)), packet_logger_(packet_logger) {}

void CompetitionApiClient::setAuthManager(AuthManager* auth_manager) { auth_manager_ = auth_manager; }

nlohmann::json CompetitionApiClient::loginPayload(const std::string& username, const std::string& password) {
  return {{"kadi", username}, {"sifre", password}};
}

httplib::Headers CompetitionApiClient::headers() const {
  std::lock_guard<std::mutex> lock(session_mutex_);
  if (session_cookie_.empty()) return {};
  return {{"Cookie", session_cookie_}};
}

void CompetitionApiClient::updateSessionCookie(const httplib::Result& response) {
  if (!response) return;
  auto cookie = response->get_header_value("Set-Cookie");
  if (cookie.empty()) return;
  auto separator = cookie.find(';');
  if (separator != std::string::npos) cookie = cookie.substr(0, separator);
  std::lock_guard<std::mutex> lock(session_mutex_);
  session_cookie_ = std::move(cookie);
}

static int roundedInt(double value) {
  return static_cast<int>(std::lround(value));
}

std::string CompetitionApiClient::telemetryPayloadText(const TelemetryPacket& packet) {
  std::ostringstream out;
  out << std::setprecision(10);
  out << "{";
  out << "\"takim_numarasi\":" << packet.takim_numarasi << ",";
  out << "\"iha_enlem\":" << packet.iha_enlem << ",";
  out << "\"iha_boylam\":" << packet.iha_boylam << ",";
  out << "\"iha_irtifa\":" << roundedInt(packet.iha_irtifa) << ",";
  out << "\"iha_dikilme\":" << roundedInt(packet.iha_dikilme) << ",";
  out << "\"iha_yonelme\":" << roundedInt(packet.iha_yonelme) << ",";
  out << "\"iha_yatis\":" << roundedInt(packet.iha_yatis) << ",";
  out << "\"iha_hiz\":" << roundedInt(packet.iha_hiz) << ",";
  out << "\"iha_batarya\":" << packet.iha_batarya << ",";
  out << "\"iha_otonom\":" << packet.iha_otonom << ",";
  out << "\"iha_kilitlenme\":" << packet.iha_kilitlenme << ",";
  out << "\"hedef_merkez_X\":" << packet.hedef_merkez_X << ",";
  out << "\"hedef_merkez_Y\":" << packet.hedef_merkez_Y << ",";
  out << "\"hedef_genislik\":" << packet.hedef_genislik << ",";
  out << "\"hedef_yukseklik\":" << packet.hedef_yukseklik << ",";
  out << "\"gps_saati\":{";
  out << "\"saat\":" << packet.gps_saati.saat << ",";
  out << "\"dakika\":" << packet.gps_saati.dakika << ",";
  out << "\"saniye\":" << packet.gps_saati.saniye << ",";
  out << "\"milisaniye\":" << packet.gps_saati.milisaniye;
  out << "}}";
  return out.str();
}

nlohmann::json CompetitionApiClient::telemetryLogPayload(const TelemetryPacket& packet) {
  return nlohmann::json::parse(telemetryPayloadText(packet), nullptr, false);
}

ApiResult CompetitionApiClient::classify(int status, nlohmann::json body, std::string error) const {
  ApiResult r{status, status == 200, false, std::move(body), std::move(error)};
  if (status == 401) r.error_message = "login required";
  if (status == 204) r.error_message = "format error";
  if (status == 400) r.error_message = "invalid request";
  if (status == 403) r.error_message = "unauthorized";
  if (status == 404) r.error_message = "wrong URL";
  if (status >= 500 || status == 400 || status == 0) r.should_retry = true;
  return r;
}

ApiResult CompetitionApiClient::postJson(const std::string& endpoint, const nlohmann::json& payload, bool allow_reauth) {
  return postJsonText(endpoint, payload.dump(), payload, allow_reauth);
}

ApiResult CompetitionApiClient::postJsonText(const std::string& endpoint,
                                             const std::string& payload,
                                             nlohmann::json log_payload,
                                             bool allow_reauth) {
  packet_logger_.log("outgoing", endpoint, 0, std::move(log_payload));
  utils::RetryPolicy retry{config_.max_retries};
  return retry.run([&] {
    httplib::Client cli(config_.base_url);
    cli.set_connection_timeout(0, config_.timeout_ms * 1000);
    cli.set_read_timeout(0, config_.timeout_ms * 1000);
    auto res = cli.Post(endpoint, headers(), payload, "application/json");
    if (!res) {
      auto r = classify(0, {}, "transport error");
      packet_logger_.log("incoming", endpoint, 0, {}, r.error_message);
      return r;
    }
    updateSessionCookie(res);
    nlohmann::json body = nlohmann::json::object();
    if (!res->body.empty()) body = nlohmann::json::parse(res->body, nullptr, false);
    auto r = classify(res->status, body.is_discarded() ? nlohmann::json::object() : body);
    packet_logger_.log("incoming", endpoint, res->status, r.body, r.error_message);
    if (res->status == 401 && allow_reauth && auth_manager_ && auth_manager_->relogin()) {
      r.should_retry = true;
    }
    return r;
  });
}

ApiResult CompetitionApiClient::getJson(const std::string& endpoint, bool allow_reauth) {
  packet_logger_.log("outgoing", endpoint, 0, nlohmann::json::object());
  utils::RetryPolicy retry{config_.max_retries};
  return retry.run([&] {
    httplib::Client cli(config_.base_url);
    cli.set_connection_timeout(0, config_.timeout_ms * 1000);
    cli.set_read_timeout(0, config_.timeout_ms * 1000);
    auto res = cli.Get(endpoint, headers());
    if (!res) {
      auto r = classify(0, {}, "transport error");
      packet_logger_.log("incoming", endpoint, 0, {}, r.error_message);
      return r;
    }
    updateSessionCookie(res);
    nlohmann::json body = nlohmann::json::object();
    if (!res->body.empty()) body = nlohmann::json::parse(res->body, nullptr, false);
    auto r = classify(res->status, body.is_discarded() ? nlohmann::json::object() : body);
    packet_logger_.log("incoming", endpoint, res->status, r.body, r.error_message);
    if (res->status == 401 && allow_reauth && auth_manager_ && auth_manager_->relogin()) {
      r.should_retry = true;
    }
    return r;
  });
}

ApiResult CompetitionApiClient::login(const std::string& username, const std::string& password) {
  return postJson("/api/giris", loginPayload(username, password), false);
}
ApiResult CompetitionApiClient::getServerTime() { return getJson("/api/sunucusaati", true); }
ApiResult CompetitionApiClient::sendTelemetry(const TelemetryPacket& packet) {
  return postJsonText("/api/telemetri_gonder", telemetryPayloadText(packet), telemetryLogPayload(packet), true);
}
ApiResult CompetitionApiClient::sendLockInfo(const LockPacket& packet) { return postJson("/api/kilitlenme_bilgisi", packet, true); }
ApiResult CompetitionApiClient::sendKamikazeInfo(const KamikazePacket& packet) { return postJson("/api/kamikaze_bilgisi", packet, true); }
ApiResult CompetitionApiClient::getQrCoordinate() { return getJson("/api/qr_koordinati", true); }
ApiResult CompetitionApiClient::getHssCoordinates() { return getJson("/api/hss_koordinatlari", true); }

}  // namespace comm::server
