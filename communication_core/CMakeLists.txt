cmake_minimum_required(VERSION 3.22)
project(communication_core LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POLICY_VERSION_MINIMUM 3.5)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

include(FetchContent)

option(COMM_CORE_BUILD_TESTS "Build unit tests" ON)
option(COMM_CORE_FETCH_DEPS "Fetch third-party dependencies with CMake" ON)

if(COMM_CORE_FETCH_DEPS)
  FetchContent_Declare(nlohmann_json URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
  FetchContent_Declare(spdlog URL https://github.com/gabime/spdlog/archive/refs/tags/v1.14.1.tar.gz DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
  FetchContent_Declare(yaml_cpp URL https://github.com/jbeder/yaml-cpp/archive/refs/tags/0.8.0.tar.gz DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
  FetchContent_Declare(cpp_httplib URL https://github.com/yhirose/cpp-httplib/archive/refs/tags/v0.16.3.tar.gz DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
  FetchContent_MakeAvailable(nlohmann_json spdlog yaml_cpp cpp_httplib)
else()
  find_package(nlohmann_json REQUIRED)
  find_package(spdlog REQUIRED)
  find_package(yaml-cpp REQUIRED)
  find_package(httplib REQUIRED)
endif()

find_package(Threads REQUIRED)

add_library(sqlite3_vendor STATIC third_party/sqlite/sqlite3.c)
target_include_directories(sqlite3_vendor PUBLIC third_party/sqlite)

add_library(comm_core
  src/core/AppContext.cpp
  src/core/EventBus.cpp
  src/core/StateStore.cpp
  src/core/Watchdog.cpp
  src/mavlink/MavlinkReceiver.cpp
  src/mavlink/TelemetryMapper.cpp
  src/server/Packets.cpp
  src/server/AuthManager.cpp
  src/server/CompetitionApiClient.cpp
  src/server/ServerClockSync.cpp
  src/server/TelemetryUploader.cpp
  src/server/LockReporter.cpp
  src/server/KamikazeReporter.cpp
  src/server/QrCoordinateClient.cpp
  src/server/HssCoordinateClient.cpp
  src/vehicle/VehicleManagerPackets.cpp
  src/vehicle/VehicleManagerReceiver.cpp
  src/vehicle/VehicleManagerCommandSender.cpp
  src/mission/LockStateMachine.cpp
  src/mission/KamikazeStateMachine.cpp
  src/ipc/LocalWebSocketServer.cpp
  src/storage/SqliteLogger.cpp
  src/storage/JsonlPacketLogger.cpp
  src/storage/ReplayRecorder.cpp
  src/utils/TimeUtils.cpp
  src/utils/Validation.cpp
)

target_include_directories(comm_core PUBLIC include)
target_link_libraries(comm_core
  PUBLIC
    nlohmann_json::nlohmann_json
    spdlog::spdlog
    yaml-cpp
    httplib::httplib
    sqlite3_vendor
    Threads::Threads
)

if(WIN32)
  target_link_libraries(comm_core PUBLIC ws2_32)
endif()

add_executable(communication_core_service app/main.cpp)
target_link_libraries(communication_core_service PRIVATE comm_core)

if(COMM_CORE_BUILD_TESTS)
  enable_testing()
  FetchContent_Declare(googletest URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.tar.gz DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
  set(INSTALL_GTEST OFF CACHE BOOL "" FORCE)
  FetchContent_MakeAvailable(googletest)

  add_executable(comm_core_tests
    tests/test_validation.cpp
    tests/test_rate_limiter.cpp
    tests/test_json_serialization.cpp
    tests/test_server_clock.cpp
    tests/test_state_machines.cpp
    tests/test_retry_and_clients.cpp
    tests/test_watchdog.cpp
    tests/test_vehicle_manager.cpp
  )
  target_link_libraries(comm_core_tests PRIVATE comm_core GTest::gtest_main)
  include(GoogleTest)
  gtest_discover_tests(comm_core_tests)
endif()
