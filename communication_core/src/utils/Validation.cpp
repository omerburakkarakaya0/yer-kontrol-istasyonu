#include "utils/Validation.hpp"

namespace comm::utils {

static void range(ValidationResult& r, const char* name, double value, double min, double max) {
  if (value < min || value > max) {
    r.valid = false;
    r.errors.emplace_back(std::string(name) + " out of range");
  }
}

static void dayTime(ValidationResult& r, const char* name, const DayTime& time) {
  range(r, (std::string(name) + ".saat").c_str(), time.saat, 0, 23);
  range(r, (std::string(name) + ".dakika").c_str(), time.dakika, 0, 59);
  range(r, (std::string(name) + ".saniye").c_str(), time.saniye, 0, 59);
  range(r, (std::string(name) + ".milisaniye").c_str(), time.milisaniye, 0, 999);
}

ValidationResult validateTelemetry(const server::TelemetryPacket& packet) {
  ValidationResult result;
  range(result, "pitch", packet.iha_dikilme, -90.0, 90.0);
  range(result, "roll", packet.iha_yatis, -90.0, 90.0);
  range(result, "yaw", packet.iha_yonelme, 0.0, 360.0);
  range(result, "battery", packet.iha_batarya, 0, 100);
  range(result, "autonomous", packet.iha_otonom, 0, 1);
  range(result, "lock", packet.iha_kilitlenme, 0, 1);
  range(result, "latitude", packet.iha_enlem, -90.0, 90.0);
  range(result, "longitude", packet.iha_boylam, -180.0, 180.0);
  range(result, "altitude", packet.iha_irtifa, -500.0, 10000.0);
  range(result, "speed", packet.iha_hiz, 0.0, 300.0);
  range(result, "target_center_x", packet.hedef_merkez_X, 0, 10000);
  range(result, "target_center_y", packet.hedef_merkez_Y, 0, 10000);
  range(result, "target_width", packet.hedef_genislik, 0, 10000);
  range(result, "target_height", packet.hedef_yukseklik, 0, 10000);
  dayTime(result, "gps_saati", packet.gps_saati);
  return result;
}

ValidationResult validateLock(const server::LockPacket& packet) {
  ValidationResult result;
  dayTime(result, "kilitlenmeBitisZamani", packet.kilitlenmeBitisZamani);
  range(result, "otonom_kilitlenme", packet.otonom_kilitlenme, 0, 1);
  return result;
}

ValidationResult validateKamikaze(const server::KamikazePacket& packet) {
  ValidationResult result;
  dayTime(result, "kamikazeBaslangicZamani", packet.kamikazeBaslangicZamani);
  dayTime(result, "kamikazeBitisZamani", packet.kamikazeBitisZamani);
  if (packet.qrMetni.empty()) {
    result.valid = false;
    result.errors.emplace_back("qrMetni empty");
  }
  return result;
}

ValidationResult validateHss(const server::HssCoordinate& coordinate) {
  ValidationResult result;
  range(result, "id", coordinate.id, 0, 100000);
  range(result, "hssEnlem", coordinate.hssEnlem, -90.0, 90.0);
  range(result, "hssBoylam", coordinate.hssBoylam, -180.0, 180.0);
  range(result, "hssYaricap", coordinate.hssYaricap, 0.0, 100000.0);
  return result;
}

ValidationResult validateQr(const server::QrCoordinate& coordinate) {
  ValidationResult result;
  range(result, "qrEnlem", coordinate.qrEnlem, -90.0, 90.0);
  range(result, "qrBoylam", coordinate.qrBoylam, -180.0, 180.0);
  return result;
}

}  // namespace comm::utils
