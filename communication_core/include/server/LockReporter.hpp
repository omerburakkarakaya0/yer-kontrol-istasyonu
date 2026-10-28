#pragma once

#include "server/ICompetitionApi.hpp"

namespace comm::server {

class LockReporter {
 public:
  explicit LockReporter(ICompetitionApi& api) : api_(api) {}
  ApiResult report(const LockPacket& packet) { return api_.sendLockInfo(packet); }

 private:
  ICompetitionApi& api_;
};

}  // namespace comm::server
