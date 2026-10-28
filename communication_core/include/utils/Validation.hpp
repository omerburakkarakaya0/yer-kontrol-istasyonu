#pragma once

#include <string>
#include <vector>
#include "server/Packets.hpp"

namespace comm::utils {

struct ValidationResult {
  bool valid{true};
  std::vector<std::string> errors;
};

ValidationResult validateTelemetry(const server::TelemetryPacket& packet);
ValidationResult validateLock(const server::LockPacket& packet);
ValidationResult validateKamikaze(const server::KamikazePacket& packet);
ValidationResult validateHss(const server::HssCoordinate& coordinate);
ValidationResult validateQr(const server::QrCoordinate& coordinate);

}  // namespace comm::utils
