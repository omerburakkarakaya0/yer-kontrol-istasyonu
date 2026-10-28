#pragma once

#include "core/AppContext.hpp"
#include "server/ICompetitionApi.hpp"

namespace comm::server {

class QrCoordinateClient {
 public:
  QrCoordinateClient(core::AppContext& context, ICompetitionApi& api);
  bool fetchOnce();

 private:
  core::AppContext& context_;
  ICompetitionApi& api_;
};

}  // namespace comm::server
