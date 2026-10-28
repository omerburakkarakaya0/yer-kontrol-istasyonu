#include "server/QrCoordinateClient.hpp"

namespace comm::server {

QrCoordinateClient::QrCoordinateClient(core::AppContext& context, ICompetitionApi& api) : context_(context), api_(api) {}

bool QrCoordinateClient::fetchOnce() {
  auto result = api_.getQrCoordinate();
  if (!result.ok) return false;
  auto coordinate = result.body.get<QrCoordinate>();
  context_.state().setQrCoordinate(coordinate);
  context_.events().publish({core::EventType::QR_UPDATED, "QrCoordinateClient", "QR coordinate updated", result.body});
  return true;
}

}  // namespace comm::server
