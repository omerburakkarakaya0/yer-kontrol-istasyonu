#include "server/AuthManager.hpp"

#include "server/ICompetitionApi.hpp"

namespace comm::server {

AuthManager::AuthManager(ICompetitionApi& api, core::EventBus& events, std::string username, std::string password)
    : api_(api), events_(events), username_(std::move(username)), password_(std::move(password)) {}

bool AuthManager::ensureLoggedIn() {
  std::lock_guard<std::mutex> lock(mutex_);
  if (logged_in_) return true;
  auto result = api_.login(username_, password_);
  logged_in_ = result.ok;
  events_.publish({logged_in_ ? core::EventType::LOGIN_SUCCESS : core::EventType::LOGIN_FAILED,
                   "AuthManager",
                   logged_in_ ? "Login successful" : "Login failed",
                   {{"http_status", result.http_status}, {"error", result.error_message}}});
  return logged_in_;
}

bool AuthManager::relogin() {
  std::lock_guard<std::mutex> lock(mutex_);
  logged_in_ = false;
  auto result = api_.login(username_, password_);
  logged_in_ = result.ok;
  events_.publish({logged_in_ ? core::EventType::LOGIN_SUCCESS : core::EventType::LOGIN_FAILED,
                   "AuthManager",
                   logged_in_ ? "Relogin successful" : "Relogin failed",
                   {{"http_status", result.http_status}}});
  return logged_in_;
}

void AuthManager::markExpired() { std::lock_guard<std::mutex> lock(mutex_); logged_in_ = false; }
bool AuthManager::loggedIn() const { std::lock_guard<std::mutex> lock(mutex_); return logged_in_; }

}  // namespace comm::server
