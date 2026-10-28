#include <gtest/gtest.h>
#include "FakeCompetitionApi.hpp"
#include "core/AppContext.hpp"
#include "ipc/UiMessageSchema.hpp"
#include "server/CompetitionApiClient.hpp"
#include "server/HssCoordinateClient.hpp"
#include "server/TelemetryUploader.hpp"
#include "vehicle/VehicleManagerPackets.hpp"
#include "vehicle/VehicleManagerReceiver.hpp"

TEST(VehicleManagerPackets, ParsesStatusAndMapsVehicleState) {
  nlohmann::json j = {
      {"type", "status"},
      {"vehicle_id", "vehicle-1"},
      {"timestamp_ms", 1700000000000},
      {"mavlink_connected", true},
      {"vehicle_state", {{"latitude", 39.9}, {"longitude", 32.8}, {"altitude", 120.0}, {"pitch", 1.0}, {"yaw", 2.0}, {"roll", 3.0}, {"ground_speed", 24.0}, {"battery_percent", 87}, {"autonomous_mode", true}, {"lock_active", false}, {"gps_time", {{"saat", 12}, {"dakika", 34}, {"saniye", 56}, {"milisaniye", 123}}}}},
      {"qr_coordinate", {{"qrEnlem", 39.91}, {"qrBoylam", 32.81}}},
      {"hss_coordinates", nlohmann::json::array({{{"id", 1}, {"hssEnlem", 39.92}, {"hssBoylam", 32.82}, {"hssYaricap", 50.0}}})},
      {"opponent_positions", nlohmann::json::array()}};
  auto status = comm::vehicle::parseStatus(j);
  ASSERT_TRUE(status.has_value());
  ASSERT_TRUE(status->vehicle_state.has_value());
  EXPECT_DOUBLE_EQ(status->vehicle_state->latitude, 39.9);
  EXPECT_TRUE(status->vehicle_state->autonomous_mode);
  EXPECT_TRUE(status->qr_coordinate.has_value());
  EXPECT_TRUE(status->hss_coordinates_present);
  EXPECT_EQ(status->hss_coordinates.size(), 1);
  EXPECT_TRUE(status->opponent_positions_present);
}

TEST(VehicleManagerReceiver, DoesNotReplaceDirectRefereeOpponents) {
  comm::core::AppConfig cfg;
  comm::core::AppContext context(cfg);
  FakeCompetitionApi api;
  comm::vehicle::VehicleManagerReceiver receiver(context, api, cfg.vehicle_manager);

  nlohmann::json referee_positions = nlohmann::json::array();
  for (int team = 1; team <= 30; ++team) {
    referee_positions.push_back({{"takim_numarasi", team}});
  }
  context.state().setOpponentPositions(referee_positions);
  context.state().markServerConnected(true);

  ASSERT_TRUE(receiver.handleStatusJson({
      {"type", "status"},
      {"vehicle_id", "vehicle-1"},
      {"opponent_positions", nlohmann::json::array({{{"takim_numarasi", 2}}, {{"takim_numarasi", 3}}, {{"takim_numarasi", 4}}})},
  }));

  EXPECT_EQ(context.state().opponentPositions().size(), 30);
}

TEST(VehicleManagerPackets, ParsesLockAndKamikazeEvents) {
  nlohmann::json lock = {{"type", "LOCK_CONFIRMED"}, {"timestamp_ms", 1700000000000}, {"payload", {{"kilitlenmeBitisZamani", {{"saat", 12}, {"dakika", 34}, {"saniye", 56}, {"milisaniye", 123}}}, {"otonom_kilitlenme", 1}}}};
  auto event = comm::vehicle::parseEvent(lock);
  ASSERT_TRUE(event.has_value());
  auto packet = event->payload.get<comm::server::LockPacket>();
  EXPECT_EQ(packet.otonom_kilitlenme, 1);

  nlohmann::json kamikaze = {{"type", "KAMIKAZE_CONFIRMED"}, {"payload", {{"kamikazeBaslangicZamani", {{"saat", 12}, {"dakika", 34}, {"saniye", 50}, {"milisaniye", 0}}}, {"kamikazeBitisZamani", {{"saat", 12}, {"dakika", 34}, {"saniye", 56}, {"milisaniye", 123}}}, {"qrMetni", "ABC123"}}}};
  auto k_event = comm::vehicle::parseEvent(kamikaze);
  ASSERT_TRUE(k_event.has_value());
  auto k_packet = k_event->payload.get<comm::server::KamikazePacket>();
  EXPECT_EQ(k_packet.qrMetni, "ABC123");
}

TEST(VehicleManagerReceiver, RejectsDuplicateLockEvent) {
  comm::core::AppConfig cfg;
  comm::core::AppContext context(cfg);
  FakeCompetitionApi api;
  comm::vehicle::VehicleManagerReceiver receiver(context, api, cfg.vehicle_manager);
  nlohmann::json lock = {{"type", "LOCK_CONFIRMED"}, {"event_id", "same-event"}, {"timestamp_ms", 1700000000000}, {"payload", {{"kilitlenmeBitisZamani", {{"saat", 12}, {"dakika", 34}, {"saniye", 56}, {"milisaniye", 123}}}, {"otonom_kilitlenme", 1}}}};
  EXPECT_TRUE(receiver.handleEventJson(lock));
  EXPECT_FALSE(receiver.handleEventJson(lock));
  EXPECT_EQ(api.lock_calls, 1);
}

TEST(VehicleManagerReceiver, InvalidJsonObjectsDoNotCrashHandlers) {
  comm::core::AppConfig cfg;
  comm::core::AppContext context(cfg);
  FakeCompetitionApi api;
  comm::vehicle::VehicleManagerReceiver receiver(context, api, cfg.vehicle_manager);
  EXPECT_FALSE(receiver.handleStatusJson({{"type", "not-status"}}));
  EXPECT_FALSE(receiver.handleEventJson(nlohmann::json::array()));
}

TEST(VehicleManagerReceiver, HeartbeatTimeoutMarksDisconnected) {
  comm::core::AppConfig cfg;
  cfg.vehicle_manager.heartbeat_timeout_ms = 0;
  comm::core::AppContext context(cfg);
  FakeCompetitionApi api;
  comm::vehicle::VehicleManagerReceiver receiver(context, api, cfg.vehicle_manager);
  ASSERT_TRUE(receiver.handleStatusJson({{"type", "status"}, {"vehicle_id", "vehicle-1"}}));
  receiver.checkHeartbeatTimeout();
  EXPECT_FALSE(context.state().connectionStatus().vehicle_manager_connected);
}

TEST(VehicleManagerCommands, SerializesHssQrAndTimeSyncCommands) {
  auto hss = comm::vehicle::makeSetHssCommand({comm::server::HssCoordinate{1, 39.92, 32.82, 50.0}});
  EXPECT_EQ(hss["type"], "SET_HSS");
  EXPECT_EQ(hss["payload"]["hss_koordinatlari"].size(), 1);

  auto qr = comm::vehicle::makeQrTargetCommand(comm::server::QrCoordinate{39.91, 32.81});
  EXPECT_EQ(qr["type"], "QR_TARGET");
  EXPECT_DOUBLE_EQ(qr["payload"]["qrEnlem"], 39.91);

  auto time = comm::vehicle::makeTimeSyncCommand(comm::utils::ServerTime{19, 15, 51, 43, 775});
  EXPECT_EQ(time["type"], "TIME_SYNC");
  EXPECT_EQ(time["payload"]["sunucusaati"]["gun"], 19);
}

TEST(OfficialApiCompatibility, LoginPayloadUsesOfficialKeys) {
  auto payload = comm::server::CompetitionApiClient::loginPayload("takimkadi", "takimsifresi");
  EXPECT_EQ(payload["kadi"], "takimkadi");
  EXPECT_EQ(payload["sifre"], "takimsifresi");
  EXPECT_FALSE(payload.contains("username"));
}

TEST(OfficialApiCompatibility, ParsesOfficialHssResponse) {
  comm::core::AppConfig cfg;
  comm::core::AppContext context(cfg);
  FakeCompetitionApi api;
  api.next.body = {{"sunucusaati", {{"gun", 19}, {"saat", 15}, {"dakika", 51}, {"saniye", 43}, {"milisaniye", 775}}},
                   {"hss_koordinat_bilgileri", nlohmann::json::array({{{"id", 1}, {"hssEnlem", 39.92}, {"hssBoylam", 32.82}, {"hssYaricap", 50.0}}})}};
  comm::server::HssCoordinateClient client(context, api);
  EXPECT_TRUE(client.fetchOnce());
  EXPECT_EQ(context.state().hssCoordinates().size(), 1);
  EXPECT_TRUE(context.state().serverTime().has_value());
}

TEST(OfficialApiCompatibility, ParsesOfficialTelemetryResponse) {
  comm::core::AppConfig cfg;
  comm::core::AppContext context(cfg);
  comm::mavlink::VehicleState state;
  state.latitude = 39.9;
  state.longitude = 32.8;
  state.battery_percent = 80;
  state.gps_time = {12, 0, 0, 0};
  context.state().updateVehicleState(state);
  FakeCompetitionApi api;
  api.next.body = {{"sunucusaati", {{"gun", 19}, {"saat", 15}, {"dakika", 51}, {"saniye", 43}, {"milisaniye", 775}}},
                   {"konumBilgileri", nlohmann::json::array({{{"takim_numarasi", 2}, {"iha_enlem", 39.91}}})}};
  comm::server::TelemetryUploader uploader(context, api);
  EXPECT_TRUE(uploader.uploadOnce());
  EXPECT_EQ(context.state().opponentPositions().size(), 1);
  EXPECT_TRUE(context.state().serverTime().has_value());
}

TEST(OfficialApiCompatibility, KeepsAllNestedOpponentPositions) {
  comm::core::AppConfig cfg;
  comm::core::AppContext context(cfg);
  comm::mavlink::VehicleState state;
  state.latitude = 39.9;
  state.longitude = 32.8;
  state.battery_percent = 80;
  state.gps_time = {12, 0, 0, 0};
  context.state().updateVehicleState(state);

  nlohmann::json positions = nlohmann::json::array();
  for (int team = 1; team <= 30; ++team) {
    positions.push_back({
        {"takim_numarasi", team},
        {"iha_enlem", 39.9 + team * 0.0001},
        {"iha_boylam", 32.8 + team * 0.0001},
    });
  }

  FakeCompetitionApi api;
  api.next.body = {{"data", {{"konumBilgileri", positions}}}};
  comm::server::TelemetryUploader uploader(context, api);

  EXPECT_TRUE(uploader.uploadOnce());
  EXPECT_EQ(context.state().opponentPositions().size(), 30);
}

TEST(VehicleManagerStatus, StatusMessageIncludesVehicleManagerFields) {
  comm::core::StateStore state;
  state.markVehicleManagerHeartbeat();
  state.setVehicleManagerLastStatus({{"type", "status"}});
  auto message = comm::ipc::makeStatusMessage(state);
  EXPECT_TRUE(message.contains("vehicle_manager_connected"));
  EXPECT_TRUE(message.contains("vehicle_manager_last_seen_age_ms"));
  EXPECT_TRUE(message.contains("vehicle_manager_last_status"));
}
