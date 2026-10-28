#include "server/TelemetryUploader.hpp"

#include <spdlog/spdlog.h>
#include "mavlink/TelemetryMapper.hpp"
#include "utils/Validation.hpp"

namespace {

const nlohmann::json* findOpponentPositions(const nlohmann::json& body, int depth = 0) {
  if (!body.is_object() || depth > 6) return nullptr;

  static constexpr const char* kPositionKeys[] = {
      "konumBilgileri",
      "konum_bilgileri",
      "rakip_iha_konumlari",
      "rakipIhaKonumlari",
      "opponent_positions",
      "opponents",
      "rakipler",
  };
  for (const auto* key : kPositionKeys) {
    auto it = body.find(key);
    if (it != body.end() && (it->is_array() || it->is_object())) return &(*it);
  }

  static constexpr const char* kWrapperKeys[] = {
      "data", "result", "results", "payload", "response", "body"};
  for (const auto* key : kWrapperKeys) {
    auto it = body.find(key);
    if (it == body.end()) continue;
    if (const auto* positions = findOpponentPositions(*it, depth + 1)) return positions;
  }
  return nullptr;
}

}  // namespace

namespace comm::server {

TelemetryUploader::TelemetryUploader(core::AppContext& context, ICompetitionApi& api)
    : context_(context), api_(api), limiter_(context.config().telemetry_max_allowed_hz) {}

TelemetryUploader::~TelemetryUploader() { stop(); }

void TelemetryUploader::start() {
  if (running_.exchange(true)) return;
  worker_ = std::thread(&TelemetryUploader::loop, this);
}

void TelemetryUploader::stop() {
  running_ = false;
  if (worker_.joinable()) worker_.join();
}

bool TelemetryUploader::uploadOnce() {
  if (!limiter_.allow()) return false;
  auto state = context_.state().vehicleState();
  if (!state) return false;
  auto packet = mavlink::TelemetryMapper::map(context_.config().team_number, *state);
  auto validation = utils::validateTelemetry(packet);
  if (!validation.valid) {
    context_.events().publish({core::EventType::VALIDATION_ERROR, "TelemetryUploader", "Telemetry validation failed", {{"errors", validation.errors}}});
    context_.events().publish({core::EventType::TELEMETRY_REJECTED, "TelemetryUploader", "Telemetry packet rejected"});
    return false;
  }
  auto result = api_.sendTelemetry(packet);
  if (result.ok) {
    context_.state().markSuccessfulServerRequest();
    context_.state().markSuccessfulTelemetry();
    context_.state().markServerConnected(true);
    if (result.body.contains("sunucusaati")) {
      context_.state().setServerTime(result.body["sunucusaati"].get<utils::ServerTime>());
    }
    if (const auto* positions = findOpponentPositions(result.body)) {
      context_.state().setOpponentPositions(*positions);
    }
    context_.events().publish({core::EventType::TELEMETRY_SENT, "TelemetryUploader", "Telemetry sent", {{"http_status", result.http_status}}});
    return true;
  }
  context_.state().markServerConnected(false);
  context_.events().publish({core::EventType::SERVER_DISCONNECTED, "TelemetryUploader", "Telemetry upload failed", {{"http_status", result.http_status}, {"error", result.error_message}}});
  return false;
}

void TelemetryUploader::loop() {
  const auto period = std::chrono::duration<double>(1.0 / context_.config().telemetry_upload_hz);
  while (running_) {
    uploadOnce();
    std::this_thread::sleep_for(period);
  }
}

}  // namespace comm::server
