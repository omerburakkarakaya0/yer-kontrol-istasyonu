#pragma once

#include "server/ICompetitionApi.hpp"

namespace comm::server {

class KamikazeReporter {
 public:
  explicit KamikazeReporter(ICompetitionApi& api) : api_(api) {}
  ApiResult report(const KamikazePacket& packet) { return api_.sendKamikazeInfo(packet); }

 private:
  ICompetitionApi& api_;
};

}  // namespace comm::server
