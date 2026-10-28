#include "server/Packets.hpp"

namespace comm::server {

void to_json(nlohmann::json& j, const TelemetryPacket& p) {
  j = {
      {"takim_numarasi", p.takim_numarasi},
      {"iha_enlem", p.iha_enlem},
      {"iha_boylam", p.iha_boylam},
      {"iha_irtifa", p.iha_irtifa},
      {"iha_dikilme", p.iha_dikilme},
      {"iha_yonelme", p.iha_yonelme},
      {"iha_yatis", p.iha_yatis},
      {"iha_hiz", p.iha_hiz},
      {"iha_batarya", p.iha_batarya},
      {"iha_otonom", p.iha_otonom},
      {"iha_kilitlenme", p.iha_kilitlenme},
      {"hedef_merkez_X", p.hedef_merkez_X},
      {"hedef_merkez_Y", p.hedef_merkez_Y},
      {"hedef_genislik", p.hedef_genislik},
      {"hedef_yukseklik", p.hedef_yukseklik},
      {"gps_saati", p.gps_saati}};
}

void from_json(const nlohmann::json& j, TelemetryPacket& p) {
  j.at("takim_numarasi").get_to(p.takim_numarasi);
  j.at("iha_enlem").get_to(p.iha_enlem);
  j.at("iha_boylam").get_to(p.iha_boylam);
  j.at("iha_irtifa").get_to(p.iha_irtifa);
  j.at("iha_dikilme").get_to(p.iha_dikilme);
  j.at("iha_yonelme").get_to(p.iha_yonelme);
  j.at("iha_yatis").get_to(p.iha_yatis);
  j.at("iha_hiz").get_to(p.iha_hiz);
  j.at("iha_batarya").get_to(p.iha_batarya);
  j.at("iha_otonom").get_to(p.iha_otonom);
  j.at("iha_kilitlenme").get_to(p.iha_kilitlenme);
  j.at("hedef_merkez_X").get_to(p.hedef_merkez_X);
  j.at("hedef_merkez_Y").get_to(p.hedef_merkez_Y);
  j.at("hedef_genislik").get_to(p.hedef_genislik);
  j.at("hedef_yukseklik").get_to(p.hedef_yukseklik);
  j.at("gps_saati").get_to(p.gps_saati);
}

void to_json(nlohmann::json& j, const LockPacket& p) {
  j = {{"kilitlenmeBitisZamani", p.kilitlenmeBitisZamani}, {"otonom_kilitlenme", p.otonom_kilitlenme}};
}
void from_json(const nlohmann::json& j, LockPacket& p) {
  j.at("kilitlenmeBitisZamani").get_to(p.kilitlenmeBitisZamani);
  j.at("otonom_kilitlenme").get_to(p.otonom_kilitlenme);
}
void to_json(nlohmann::json& j, const KamikazePacket& p) {
  j = {{"kamikazeBaslangicZamani", p.kamikazeBaslangicZamani}, {"kamikazeBitisZamani", p.kamikazeBitisZamani}, {"qrMetni", p.qrMetni}};
}
void from_json(const nlohmann::json& j, KamikazePacket& p) {
  j.at("kamikazeBaslangicZamani").get_to(p.kamikazeBaslangicZamani);
  j.at("kamikazeBitisZamani").get_to(p.kamikazeBitisZamani);
  j.at("qrMetni").get_to(p.qrMetni);
}
void to_json(nlohmann::json& j, const QrCoordinate& p) { j = {{"qrEnlem", p.qrEnlem}, {"qrBoylam", p.qrBoylam}}; }
void from_json(const nlohmann::json& j, QrCoordinate& p) {
  j.at("qrEnlem").get_to(p.qrEnlem);
  j.at("qrBoylam").get_to(p.qrBoylam);
}
void to_json(nlohmann::json& j, const HssCoordinate& p) {
  j = {{"id", p.id}, {"hssEnlem", p.hssEnlem}, {"hssBoylam", p.hssBoylam}, {"hssYaricap", p.hssYaricap}};
}
void from_json(const nlohmann::json& j, HssCoordinate& p) {
  j.at("id").get_to(p.id);
  j.at("hssEnlem").get_to(p.hssEnlem);
  j.at("hssBoylam").get_to(p.hssBoylam);
  j.at("hssYaricap").get_to(p.hssYaricap);
}

}  // namespace comm::server
