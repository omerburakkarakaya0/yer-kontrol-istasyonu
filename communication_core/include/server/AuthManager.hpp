#pragma once

#include <mutex>
#include <string>
#include "core/EventBus.hpp"

namespace comm::server {

class ICompetitionApi;

class AuthManager {
 public:
  AuthManager(ICompetitionApi& api, core::EventBus& events, std::string username, std::string password);

  bool ensureLoggedIn();
  bool relogin();
  void markExpired();
  bool loggedIn() const;

 private:
  ICompetitionApi& api_;
  core::EventBus& events_;
  std::string username_;
  std::string password_;
  mutable std::mutex mutex_;
  bool logged_in_{false};
};

}  // namespace comm::server
