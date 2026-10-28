#include "mavlink/TelemetryMapper.hpp"

namespace comm::mavlink {

server::TelemetryPacket TelemetryMapper::map(int team_number, const VehicleState& state) {
  return server::TelemetryPacket{
      .takim_numarasi = team_number,
      .iha_enlem = state.latitude,
      .iha_boylam = state.longitude,
      .iha_irtifa = state.altitude,
      .iha_dikilme = state.pitch,
      .iha_yonelme = state.yaw,
      .iha_yatis = state.roll,
      .iha_hiz = state.ground_speed,
      .iha_batarya = state.battery_percent,
      .iha_otonom = state.autonomous_mode ? 1 : 0,
      .iha_kilitlenme = state.lock_active ? 1 : 0,
      .hedef_merkez_X = state.target_center_x,
      .hedef_merkez_Y = state.target_center_y,
      .hedef_genislik = state.target_width,
      .hedef_yukseklik = state.target_height,
      .gps_saati = state.gps_time};
}

void to_json(nlohmann::json& j, const VehicleState& s) {
  j = {{"latitude", s.latitude}, {"longitude", s.longitude}, {"altitude", s.altitude},
       {"pitch", s.pitch}, {"yaw", s.yaw}, {"roll", s.roll}, {"ground_speed", s.ground_speed},
       {"battery_percent", s.battery_percent}, {"autonomous_mode", s.autonomous_mode},
       {"lock_active", s.lock_active}, {"target_center_x", s.target_center_x},
       {"target_center_y", s.target_center_y}, {"target_width", s.target_width},
       {"target_height", s.target_height}, {"gps_time", s.gps_time}};
}

}  // namespace comm::mavlink
