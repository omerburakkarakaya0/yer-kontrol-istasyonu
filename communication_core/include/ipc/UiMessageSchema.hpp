#pragma once

#include <nlohmann/json.hpp>
#include "core/StateStore.hpp"

namespace comm::ipc {

nlohmann::json makeStatusMessage(const core::StateStore& state);

}  // namespace comm::ipc
