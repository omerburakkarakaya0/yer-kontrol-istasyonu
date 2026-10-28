#include "server/HssCoordinateClient.hpp"

namespace comm::server {

HssCoordinateClient::HssCoordinateClient(core::AppContext& context, ICompetitionApi& api) : context_(context), api_(api) {}

bool HssCoordinateClient::fetchOnce() {
  auto result = api_.getHssCoordinates();
  if (!result.ok) return false;
  std::vector<HssCoordinate> coordinates;
  if (result.body.is_array()) coordinates = result.body.get<std::vector<HssCoordinate>>();
  if (result.body.contains("sunucusaati")) context_.state().setServerTime(result.body["sunucusaati"].get<utils::ServerTime>());
  if (result.body.contains("hss_koordinat_bilgileri")) coordinates = result.body["hss_koordinat_bilgileri"].get<std::vector<HssCoordinate>>();
  if (result.body.contains("hss_koordinatlari")) coordinates = result.body["hss_koordinatlari"].get<std::vector<HssCoordinate>>();
  context_.state().setHssCoordinates(coordinates);
  context_.events().publish({core::EventType::HSS_UPDATED, "HssCoordinateClient", coordinates.empty() ? "HSS list empty" : "HSS coordinates updated", {{"count", coordinates.size()}}});
  return true;
}

}  // namespace comm::server
