#pragma once

#include <nlohmann/json.hpp>
#include <string>
#include <vector>
#include "utils/TimeUtils.hpp"

namespace comm::server {

struct TelemetryPacket {
  int takim_numarasi{};
  double iha_enlem{};
  double iha_boylam{};
  double iha_irtifa{};
  double iha_dikilme{};
  double iha_yonelme{};
  double iha_yatis{};
  double iha_hiz{};
  int iha_batarya{};
  int iha_otonom{};
  int iha_kilitlenme{};
  int hedef_merkez_X{};
  int hedef_merkez_Y{};
  int hedef_genislik{};
  int hedef_yukseklik{};
  utils::DayTime gps_saati;
};

struct LockPacket {
  utils::DayTime kilitlenmeBitisZamani;
  int otonom_kilitlenme{};
};

struct KamikazePacket {
  utils::DayTime kamikazeBaslangicZamani;
  utils::DayTime kamikazeBitisZamani;
  std::string qrMetni;
};

struct QrCoordinate {
  double qrEnlem{};
  double qrBoylam{};
};

struct HssCoordinate {
  int id{};
  double hssEnlem{};
  double hssBoylam{};
  double hssYaricap{};
};

void to_json(nlohmann::json& j, const TelemetryPacket& p);
void from_json(const nlohmann::json& j, TelemetryPacket& p);
void to_json(nlohmann::json& j, const LockPacket& p);
void from_json(const nlohmann::json& j, LockPacket& p);
void to_json(nlohmann::json& j, const KamikazePacket& p);
void from_json(const nlohmann::json& j, KamikazePacket& p);
void to_json(nlohmann::json& j, const QrCoordinate& p);
void from_json(const nlohmann::json& j, QrCoordinate& p);
void to_json(nlohmann::json& j, const HssCoordinate& p);
void from_json(const nlohmann::json& j, HssCoordinate& p);

}  // namespace comm::server
