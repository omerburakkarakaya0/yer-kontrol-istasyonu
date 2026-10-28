#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <mutex>
#include <optional>
#include <sstream>
#include <set>
#include <string>
#include <thread>
#include <vector>

#ifdef _WIN32
#define NOMINMAX
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#endif

namespace {

struct Args {
    std::string type = "UDP";
    std::string target = "udp:0.0.0.0:14550";
    int baud = 57600;
};

struct Telemetry {
    bool connected = false;
    std::optional<std::string> mode;
    std::optional<bool> armed;
    std::optional<double> latitude;
    std::optional<double> longitude;
    std::optional<double> relative_altitude;
    std::optional<double> absolute_altitude;
    std::optional<double> ground_speed;
    std::optional<double> air_speed;
    std::optional<double> vertical_speed;
    std::optional<double> pitch;
    std::optional<double> roll;
    std::optional<double> yaw;
    std::optional<double> heading;
    std::optional<double> battery_voltage;
    std::optional<double> battery_current;
    std::optional<double> battery_remaining;
    std::optional<int> gps_fix_type;
    std::optional<int> satellites_visible;
    std::optional<double> signal_quality;
};

uint16_t le16(const uint8_t* p) {
    return static_cast<uint16_t>(p[0] | (p[1] << 8));
}

int16_t sle16(const uint8_t* p) {
    return static_cast<int16_t>(le16(p));
}

uint32_t le32(const uint8_t* p) {
    return static_cast<uint32_t>(p[0] | (p[1] << 8) | (p[2] << 16) | (p[3] << 24));
}

int32_t sle32(const uint8_t* p) {
    return static_cast<int32_t>(le32(p));
}

float lef32(const uint8_t* p) {
    float value;
    uint32_t raw = le32(p);
    std::memcpy(&value, &raw, sizeof(value));
    return value;
}

void push_u8(std::vector<uint8_t>& out, uint8_t value) {
    out.push_back(value);
}

void push_u16(std::vector<uint8_t>& out, uint16_t value) {
    out.push_back(static_cast<uint8_t>(value & 0xff));
    out.push_back(static_cast<uint8_t>((value >> 8) & 0xff));
}

void push_i32(std::vector<uint8_t>& out, int32_t value) {
    uint32_t raw = static_cast<uint32_t>(value);
    out.push_back(static_cast<uint8_t>(raw & 0xff));
    out.push_back(static_cast<uint8_t>((raw >> 8) & 0xff));
    out.push_back(static_cast<uint8_t>((raw >> 16) & 0xff));
    out.push_back(static_cast<uint8_t>((raw >> 24) & 0xff));
}

void push_f32(std::vector<uint8_t>& out, float value) {
    uint32_t raw = 0;
    std::memcpy(&raw, &value, sizeof(raw));
    out.push_back(static_cast<uint8_t>(raw & 0xff));
    out.push_back(static_cast<uint8_t>((raw >> 8) & 0xff));
    out.push_back(static_cast<uint8_t>((raw >> 16) & 0xff));
    out.push_back(static_cast<uint8_t>((raw >> 24) & 0xff));
}

double now_seconds() {
    using clock = std::chrono::system_clock;
    return std::chrono::duration<double>(clock::now().time_since_epoch()).count();
}

std::string plane_mode_from_custom(uint32_t custom_mode) {
    switch (custom_mode) {
        case 0: return "MANUAL";
        case 1: return "CIRCLE";
        case 2: return "STABILIZE";
        case 3: return "TRAINING";
        case 4: return "ACRO";
        case 5: return "FBWA";
        case 6: return "FBWB";
        case 7: return "CRUISE";
        case 8: return "AUTOTUNE";
        case 10: return "AUTO";
        case 11: return "RTL";
        case 12: return "LOITER";
        case 13: return "TAKEOFF";
        case 14: return "AVOID_ADSB";
        case 15: return "GUIDED";
        case 16: return "INITIALISING";
        case 17: return "QSTABILIZE";
        case 18: return "QHOVER";
        case 19: return "QLOITER";
        case 20: return "QLAND";
        case 21: return "QRTL";
        case 22: return "QAUTOTUNE";
        case 23: return "QACRO";
        case 24: return "THERMAL";
        case 25: return "LOITER_ALT_QLAND";
        case 26: return "AUTOLAND";
        default: return std::to_string(custom_mode);
    }
}

std::string copter_mode_from_custom(uint32_t custom_mode) {
    switch (custom_mode) {
        case 0: return "STABILIZE";
        case 1: return "ACRO";
        case 2: return "ALT_HOLD";
        case 3: return "AUTO";
        case 4: return "GUIDED";
        case 5: return "LOITER";
        case 6: return "RTL";
        case 9: return "LAND";
        case 11: return "DRIFT";
        case 13: return "SPORT";
        case 14: return "FLIP";
        case 15: return "AUTOTUNE";
        case 16: return "POSHOLD";
        case 17: return "BRAKE";
        case 18: return "THROW";
        case 19: return "AVOID_ADSB";
        case 20: return "GUIDED_NOGPS";
        case 21: return "SMART_RTL";
        case 22: return "FLOWHOLD";
        case 23: return "FOLLOW";
        case 24: return "ZIGZAG";
        case 25: return "SYSTEMID";
        case 26: return "AUTOROTATE";
        case 27: return "AUTO_RTL";
        case 28: return "TURTLE";
        default: return std::to_string(custom_mode);
    }
}

std::string mode_from_custom(uint32_t custom_mode, uint8_t vehicle_type) {
    if (vehicle_type == 2 || vehicle_type == 13 || vehicle_type == 14 || vehicle_type == 15) {
        return copter_mode_from_custom(custom_mode);
    }
    return plane_mode_from_custom(custom_mode);
}

std::string json_escape(const std::string& input) {
    std::ostringstream out;
    for (char c : input) {
        if (c == '"' || c == '\\') out << '\\' << c;
        else if (c == '\n') out << "\\n";
        else if (c == '\r') out << "\\r";
        else out << c;
    }
    return out.str();
}

double radio_link_quality_percent(int rssi, int remrssi, int txbuf, int noise, int remnoise) {
    std::vector<double> candidates;

    if (txbuf > 0) {
        candidates.push_back(std::clamp(static_cast<double>(txbuf), 0.0, 100.0));
    }

    auto rssi_to_percent = [](int value) {
        if (value <= 100) return std::clamp(static_cast<double>(value), 0.0, 100.0);
        return std::clamp(value / 254.0 * 100.0, 0.0, 100.0);
    };

    bool valid_rssi = rssi > 1;
    bool valid_remrssi = remrssi > 1;

    if (valid_rssi && valid_remrssi) {
        candidates.push_back(std::min(rssi_to_percent(rssi), rssi_to_percent(remrssi)));
    } else if (valid_rssi) {
        candidates.push_back(rssi_to_percent(rssi));
    } else if (valid_remrssi) {
        candidates.push_back(rssi_to_percent(remrssi));
    }

    std::vector<int> margins;
    if (valid_rssi && noise > 0 && rssi > noise) margins.push_back(rssi - noise);
    if (valid_remrssi && remnoise > 0 && remrssi > remnoise) margins.push_back(remrssi - remnoise);
    if (!margins.empty()) {
        int margin = *std::min_element(margins.begin(), margins.end());
        candidates.push_back(std::clamp((margin - 6) / 34.0 * 100.0, 0.0, 100.0));
    }

    if (candidates.empty()) return 0.0;
    return *std::max_element(candidates.begin(), candidates.end());
}

template <typename T>
void add_field(std::ostringstream& out, bool& first, const char* name, const std::optional<T>& value) {
    if (!value.has_value()) return;
    if (!first) out << ',';
    first = false;
    out << '"' << name << "\":" << *value;
}

void add_string_field(std::ostringstream& out, bool& first, const char* name, const std::optional<std::string>& value) {
    if (!value.has_value()) return;
    if (!first) out << ',';
    first = false;
    out << '"' << name << "\":\"" << json_escape(*value) << '"';
}

void publish(const Telemetry& t) {
    std::ostringstream out;
    bool first = true;
    out << std::fixed << std::setprecision(7);
    out << "{";
    out << "\"timestamp\":" << now_seconds();
    first = false;
    out << ",\"connected\":" << (t.connected ? "true" : "false");
    add_string_field(out, first, "mode", t.mode);
    add_field(out, first, "armed", t.armed);
    add_field(out, first, "latitude", t.latitude);
    add_field(out, first, "longitude", t.longitude);
    add_field(out, first, "relative_altitude", t.relative_altitude);
    add_field(out, first, "absolute_altitude", t.absolute_altitude);
    add_field(out, first, "ground_speed", t.ground_speed);
    add_field(out, first, "air_speed", t.air_speed);
    add_field(out, first, "vertical_speed", t.vertical_speed);
    add_field(out, first, "pitch", t.pitch);
    add_field(out, first, "roll", t.roll);
    add_field(out, first, "yaw", t.yaw);
    add_field(out, first, "heading", t.heading);
    add_field(out, first, "battery_voltage", t.battery_voltage);
    add_field(out, first, "battery_current", t.battery_current);
    add_field(out, first, "battery_remaining", t.battery_remaining);
    add_field(out, first, "gps_fix_type", t.gps_fix_type);
    add_field(out, first, "satellites_visible", t.satellites_visible);
    add_field(out, first, "signal_quality", t.signal_quality);
    out << "}\n";
    std::cout << out.str() << std::flush;
}

void publish_event(const std::string& name, const std::string& level, const std::string& message) {
    std::cout << "{\"type\":\"event\",\"event\":\"" << json_escape(name)
              << "\",\"level\":\"" << json_escape(level)
              << "\",\"message\":\"" << json_escape(message) << "\"}\n" << std::flush;
}

struct MavFrame {
    uint32_t msgid = 0;
    uint8_t sysid = 0;
    uint8_t compid = 0;
    std::vector<uint8_t> payload;
};

struct MissionWireItem {
    uint16_t seq = 0;
    uint8_t frame = 3;
    uint16_t command = 16;
    float param1 = 0.0f;
    float param2 = 0.0f;
    float param3 = 0.0f;
    float param4 = std::numeric_limits<float>::quiet_NaN();
    int32_t x = 0;
    int32_t y = 0;
    float z = 0.0f;
};

struct BridgeState {
    std::mutex mutex;
    std::condition_variable command_condition;
    HANDLE serial_handle = INVALID_HANDLE_VALUE;
    uint8_t target_system = 1;
    uint8_t target_component = 1;
    bool target_seen = false;
    uint8_t vehicle_type = 1;
    bool guided_target_pending = false;
    int mode_command_result = -1;
    std::string current_mode;
    std::vector<MissionWireItem> upload_items;
    bool upload_active = false;
    bool clear_active = false;
    std::set<int> uploaded_sequences;
    bool mission_count_sent = false;
    bool download_active = false;
    int download_expected = -1;
    std::vector<MissionWireItem> downloaded_items;
};

void publish_mission_downloaded(const std::vector<MissionWireItem>& items) {
    std::ostringstream out;
    out << std::fixed << std::setprecision(7);
    out << "{\"type\":\"event\",\"event\":\"mission_downloaded\",\"level\":\"SUCCESS\",\"items\":[";
    for (size_t i = 0; i < items.size(); ++i) {
        if (i) out << ',';
        const auto& item = items[i];
        out << "{\"seq\":" << item.seq
            << ",\"frame\":" << static_cast<int>(item.frame)
            << ",\"command\":" << item.command
            << ",\"param1\":" << item.param1
            << ",\"param2\":" << item.param2
            << ",\"param3\":" << item.param3
            << ",\"param4\":" << item.param4
            << ",\"x\":" << item.x
            << ",\"y\":" << item.y
            << ",\"z\":" << item.z << "}";
    }
    out << "]}\n";
    std::cout << out.str() << std::flush;
}

class MavParser {
public:
    std::optional<MavFrame> feed(uint8_t byte) {
        switch (state_) {
            case 0:
                if (byte == 0xFE || byte == 0xFD) {
                    magic_ = byte;
                    buffer_.clear();
                    buffer_.push_back(byte);
                    state_ = 1;
                }
                break;
            case 1:
                len_ = byte;
                buffer_.push_back(byte);
                header_needed_ = (magic_ == 0xFD) ? 8 : 4;
                state_ = 2;
                break;
            case 2:
                buffer_.push_back(byte);
                if (--header_needed_ == 0) state_ = 3;
                break;
            case 3:
                buffer_.push_back(byte);
                if (++payload_read_ >= len_) state_ = 4;
                break;
            case 4:
                buffer_.push_back(byte);
                if (++crc_read_ >= 2) {
                    MavFrame frame = build_frame();
                    reset();
                    return frame;
                }
                break;
        }
        return std::nullopt;
    }

private:
    MavFrame build_frame() const {
        MavFrame frame;
        if (magic_ == 0xFE) {
            frame.sysid = buffer_[3];
            frame.compid = buffer_[4];
            frame.msgid = buffer_[5];
            frame.payload.assign(buffer_.begin() + 6, buffer_.begin() + 6 + len_);
        } else {
            frame.sysid = buffer_[5];
            frame.compid = buffer_[6];
            frame.msgid = static_cast<uint32_t>(buffer_[7]) |
                          (static_cast<uint32_t>(buffer_[8]) << 8) |
                          (static_cast<uint32_t>(buffer_[9]) << 16);
            frame.payload.assign(buffer_.begin() + 10, buffer_.begin() + 10 + len_);
        }
        return frame;
    }

    void reset() {
        state_ = 0;
        len_ = 0;
        header_needed_ = 0;
        payload_read_ = 0;
        crc_read_ = 0;
        magic_ = 0;
        buffer_.clear();
    }

    int state_ = 0;
    uint8_t magic_ = 0;
    uint8_t len_ = 0;
    int header_needed_ = 0;
    int payload_read_ = 0;
    int crc_read_ = 0;
    std::vector<uint8_t> buffer_;
};

uint16_t crc_accumulate(uint8_t data, uint16_t crc) {
    data ^= static_cast<uint8_t>(crc & 0xff);
    data ^= data << 4;
    return static_cast<uint16_t>(
        (crc >> 8) ^ (static_cast<uint16_t>(data) << 8) ^
        (static_cast<uint16_t>(data) << 3) ^ (static_cast<uint16_t>(data) >> 4)
    );
}

uint16_t mav_crc(const std::vector<uint8_t>& bytes, uint8_t extra) {
    uint16_t crc = 0xffff;
    for (uint8_t b : bytes) crc = crc_accumulate(b, crc);
    return crc_accumulate(extra, crc);
}

std::vector<uint8_t> mavlink_v1_packet(
    uint8_t msgid,
    const std::vector<uint8_t>& payload,
    uint8_t crc_extra
) {
    static uint8_t seq = 0;
    constexpr uint8_t gcs_sysid = 255;
    constexpr uint8_t gcs_compid = 190;

    std::vector<uint8_t> packet;
    packet.reserve(payload.size() + 8);
    packet.push_back(0xFE);
    packet.push_back(static_cast<uint8_t>(payload.size()));
    packet.push_back(seq++);
    packet.push_back(gcs_sysid);
    packet.push_back(gcs_compid);
    packet.push_back(msgid);
    packet.insert(packet.end(), payload.begin(), payload.end());

    std::vector<uint8_t> crc_bytes(packet.begin() + 1, packet.end());
    uint16_t crc = mav_crc(crc_bytes, crc_extra);
    packet.push_back(static_cast<uint8_t>(crc & 0xff));
    packet.push_back(static_cast<uint8_t>((crc >> 8) & 0xff));
    return packet;
}

std::vector<uint8_t> heartbeat_packet() {
    // HEARTBEAT payload, MAVLink v1, crc extra 50.
    std::vector<uint8_t> payload(9, 0);
    payload[4] = 6;   // MAV_TYPE_GCS
    payload[5] = 8;   // MAV_AUTOPILOT_INVALID
    payload[6] = 0;   // base_mode
    payload[7] = 4;   // MAV_STATE_ACTIVE
    payload[8] = 3;   // mavlink_version
    return mavlink_v1_packet(0, payload, 50);
}

std::vector<uint8_t> request_data_stream_packet(
    uint8_t target_system,
    uint8_t target_component,
    uint8_t stream_id,
    uint16_t rate_hz
) {
    // REQUEST_DATA_STREAM wire order: uint16 rate, target sys, target comp, stream id, start.
    std::vector<uint8_t> payload;
    payload.push_back(static_cast<uint8_t>(rate_hz & 0xff));
    payload.push_back(static_cast<uint8_t>((rate_hz >> 8) & 0xff));
    payload.push_back(target_system);
    payload.push_back(target_component);
    payload.push_back(stream_id);
    payload.push_back(1);
    return mavlink_v1_packet(66, payload, 148);
}

bool is_copter_vehicle(uint8_t vehicle_type) {
    return vehicle_type == 2 || vehicle_type == 13 || vehicle_type == 14 || vehicle_type == 15;
}

uint32_t mode_id_from_name(const std::string& raw_mode, uint8_t vehicle_type) {
    std::string mode = raw_mode;
    std::transform(mode.begin(), mode.end(), mode.begin(), ::toupper);
    if (is_copter_vehicle(vehicle_type)) {
        if (mode == "AUTO" || mode == "OTONOM IN") return 3;
        if (mode == "GUIDED" || mode == "KAMIKAZE" || mode == "TAKIP" ||
            mode == "HAVA SAVUNMADAN KACIS") return 4;
        if (mode == "RTL" || mode == "GOREV IPTAL") return 6;
        return 0;
    }
    if (mode == "MANUAL") return 0;
    if (mode == "FBWA") return 5;
    if (mode == "AUTO" || mode == "OTONOM IN") return 10;
    if (mode == "RTL" || mode == "GOREV IPTAL") return 11;
    if (mode == "GUIDED" || mode == "KAMIKAZE" || mode == "TAKIP" ||
        mode == "HAVA SAVUNMADAN KACIS") return 15;
    return 0;
}

bool try_mode_id_from_name(const std::string& raw_mode, uint8_t vehicle_type, uint32_t& mode_id) {
    std::string mode = raw_mode;
    std::transform(mode.begin(), mode.end(), mode.begin(), ::toupper);
    if (is_copter_vehicle(vehicle_type)) {
        if (mode == "AUTO") mode_id = 3;
        else if (mode == "GUIDED") mode_id = 4;
        else if (mode == "RTL") mode_id = 6;
        else return false;
        return true;
    }
    if (mode == "MANUAL") mode_id = 0;
    else if (mode == "FBWA") mode_id = 5;
    else if (mode == "AUTO") mode_id = 10;
    else if (mode == "RTL") mode_id = 11;
    else if (mode == "GUIDED") mode_id = 15;
    else return false;
    return true;
}

std::vector<uint8_t> set_mode_packet(uint8_t target_system, const std::string& mode_name, uint8_t vehicle_type) {
    std::vector<uint8_t> payload;
    push_i32(payload, static_cast<int32_t>(mode_id_from_name(mode_name, vehicle_type)));
    push_u8(payload, target_system);
    push_u8(payload, 1); // MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
    return mavlink_v1_packet(11, payload, 89);
}

std::vector<uint8_t> command_long_set_mode_packet(
    uint8_t target_system,
    uint8_t target_component,
    const std::string& mode_name,
    uint8_t vehicle_type
) {
    std::vector<uint8_t> payload;
    push_f32(payload, 1.0f); // MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
    push_f32(payload, static_cast<float>(mode_id_from_name(mode_name, vehicle_type)));
    push_f32(payload, 0.0f);
    push_f32(payload, 0.0f);
    push_f32(payload, 0.0f);
    push_f32(payload, 0.0f);
    push_f32(payload, 0.0f);
    push_u16(payload, 176); // MAV_CMD_DO_SET_MODE
    push_u8(payload, target_system);
    push_u8(payload, target_component);
    push_u8(payload, 0);
    return mavlink_v1_packet(76, payload, 152);
}

std::vector<uint8_t> mission_clear_all_packet(uint8_t target_system, uint8_t target_component) {
    std::vector<uint8_t> payload;
    push_u8(payload, target_system);
    push_u8(payload, target_component);
    return mavlink_v1_packet(45, payload, 232);
}

std::vector<uint8_t> mission_count_packet(uint8_t target_system, uint8_t target_component, uint16_t count) {
    std::vector<uint8_t> payload;
    push_u16(payload, count);
    push_u8(payload, target_system);
    push_u8(payload, target_component);
    return mavlink_v1_packet(44, payload, 221);
}

std::vector<uint8_t> mission_item_int_packet(
    uint8_t target_system,
    uint8_t target_component,
    uint16_t seq,
    const MissionWireItem& item,
    uint8_t current = 0,
    uint8_t autocontinue = 1
) {
    std::vector<uint8_t> payload;
    push_f32(payload, item.param1);
    push_f32(payload, item.param2);
    push_f32(payload, item.param3);
    push_f32(payload, item.param4);
    push_i32(payload, item.x);
    push_i32(payload, item.y);
    push_f32(payload, item.z);
    push_u16(payload, seq);
    push_u16(payload, item.command);
    push_u8(payload, target_system);
    push_u8(payload, target_component);
    push_u8(payload, item.frame);
    push_u8(payload, current);
    push_u8(payload, autocontinue);
    return mavlink_v1_packet(73, payload, 38);
}

std::vector<uint8_t> set_position_target_global_int_packet(
    uint8_t target_system,
    uint8_t target_component,
    uint8_t frame,
    int32_t latitude_int,
    int32_t longitude_int,
    float altitude
) {
    std::vector<uint8_t> payload;
    push_i32(payload, 0); // time_boot_ms
    push_i32(payload, latitude_int);
    push_i32(payload, longitude_int);
    push_f32(payload, altitude);
    for (int i = 0; i < 8; ++i) push_f32(payload, 0.0f);
    push_u16(payload, 3576); // position only; ignore velocity, acceleration and yaw
    push_u8(payload, target_system);
    push_u8(payload, target_component);
    push_u8(payload, frame);
    return mavlink_v1_packet(86, payload, 5);
}

std::vector<uint8_t> command_int_reposition_packet(
    uint8_t target_system,
    uint8_t target_component,
    uint8_t frame,
    int32_t latitude_int,
    int32_t longitude_int,
    float altitude
) {
    std::vector<uint8_t> payload;
    push_f32(payload, -1.0f); // default groundspeed
    push_f32(payload, 0.0f);  // reposition flags; already switching to GUIDED
    push_f32(payload, 0.0f);  // loiter radius
    push_f32(payload, std::numeric_limits<float>::quiet_NaN());
    push_i32(payload, latitude_int);
    push_i32(payload, longitude_int);
    push_f32(payload, altitude);
    push_u16(payload, 192); // MAV_CMD_DO_REPOSITION
    push_u8(payload, target_system);
    push_u8(payload, target_component);
    push_u8(payload, frame);
    push_u8(payload, 0);
    push_u8(payload, 0);
    return mavlink_v1_packet(75, payload, 158);
}

std::vector<uint8_t> mission_set_current_packet(uint8_t target_system, uint8_t target_component, uint16_t seq) {
    std::vector<uint8_t> payload;
    push_u16(payload, seq);
    push_u8(payload, target_system);
    push_u8(payload, target_component);
    return mavlink_v1_packet(41, payload, 28);
}

std::vector<uint8_t> mission_request_list_packet(uint8_t target_system, uint8_t target_component) {
    std::vector<uint8_t> payload;
    push_u8(payload, target_system);
    push_u8(payload, target_component);
    return mavlink_v1_packet(43, payload, 132);
}

std::vector<uint8_t> mission_request_int_packet(uint8_t target_system, uint8_t target_component, uint16_t seq) {
    std::vector<uint8_t> payload;
    push_u16(payload, seq);
    push_u8(payload, target_system);
    push_u8(payload, target_component);
    return mavlink_v1_packet(51, payload, 196);
}

bool serial_write(HANDLE handle, const std::vector<uint8_t>& bytes) {
    if (bytes.empty()) return true;
    DWORD written = 0;
    if (!WriteFile(handle, bytes.data(), static_cast<DWORD>(bytes.size()), &written, nullptr)) {
        DWORD err = GetLastError();
        publish_event("serial_write_failed", "ERROR", "Serial write failed, Win32 error=" + std::to_string(err));
        return false;
    }
    if (written != bytes.size()) {
        publish_event("serial_write_partial", "WARNING", "Serial write partial: " + std::to_string(written) + "/" + std::to_string(bytes.size()));
        return false;
    }
    return true;
}

std::vector<std::string> split(const std::string& text, char delimiter) {
    std::vector<std::string> parts;
    std::stringstream ss(text);
    std::string part;
    while (std::getline(ss, part, delimiter)) parts.push_back(part);
    return parts;
}

bool parse_mission_item(const std::string& text, MissionWireItem& item) {
    auto parts = split(text, ',');
    if (parts.size() < 9) return false;
    try {
        item.frame = static_cast<uint8_t>(std::stoi(parts[0]));
        item.command = static_cast<uint16_t>(std::stoi(parts[1]));
        item.param1 = std::stof(parts[2]);
        item.param2 = std::stof(parts[3]);
        item.param3 = std::stof(parts[4]);
        item.param4 = std::stof(parts[5]);
        item.x = static_cast<int32_t>(std::stol(parts[6]));
        item.y = static_cast<int32_t>(std::stol(parts[7]));
        item.z = std::stof(parts[8]);
        return true;
    } catch (...) {
        return false;
    }
}

std::optional<MissionWireItem> mission_item_from_frame(const MavFrame& frame) {
    const auto& p = frame.payload;
    if (frame.msgid == 73 && p.size() >= 37) {
        MissionWireItem item;
        item.param1 = lef32(p.data());
        item.param2 = lef32(p.data() + 4);
        item.param3 = lef32(p.data() + 8);
        item.param4 = lef32(p.data() + 12);
        item.x = sle32(p.data() + 16);
        item.y = sle32(p.data() + 20);
        item.z = lef32(p.data() + 24);
        item.seq = le16(p.data() + 28);
        item.command = le16(p.data() + 30);
        item.frame = p[34];
        return item;
    }
    if (frame.msgid == 39 && p.size() >= 37) {
        MissionWireItem item;
        item.param1 = lef32(p.data());
        item.param2 = lef32(p.data() + 4);
        item.param3 = lef32(p.data() + 8);
        item.param4 = lef32(p.data() + 12);
        item.x = static_cast<int32_t>(lef32(p.data() + 16) * 1e7);
        item.y = static_cast<int32_t>(lef32(p.data() + 20) * 1e7);
        item.z = lef32(p.data() + 24);
        item.seq = le16(p.data() + 28);
        item.command = le16(p.data() + 30);
        item.frame = p[34];
        return item;
    }
    return std::nullopt;
}

void handle_command_line(BridgeState& state, const std::string& line) {
    std::unique_lock<std::mutex> lock(state.mutex);
    if (state.serial_handle == INVALID_HANDLE_VALUE || !state.target_seen) {
        publish_event("command_error", "ERROR", "No MAVLink target is ready yet");
        return;
    }

    if (line.rfind("MODE ", 0) == 0) {
        std::string mode = line.substr(5);
        std::transform(mode.begin(), mode.end(), mode.begin(), ::toupper);
        uint32_t requested_mode_id = 0;
        if (!try_mode_id_from_name(mode, state.vehicle_type, requested_mode_id)) {
            publish_event(
                "mode_failed",
                "ERROR",
                "Unsupported flight mode for connected vehicle: " + mode
            );
            return;
        }
        if (state.current_mode == mode) {
            publish_event("mode_complete", "SUCCESS", "Flight mode already active: " + mode);
            return;
        }

        serial_write(state.serial_handle, heartbeat_packet());
        state.mode_command_result = -1;
        // Mission Planner compatibility order: modern command first, then the
        // legacy SET_MODE message twice. HEARTBEAT remains authoritative.
        serial_write(state.serial_handle, command_long_set_mode_packet(state.target_system, state.target_component, mode, state.vehicle_type));
        serial_write(state.serial_handle, set_mode_packet(state.target_system, mode, state.vehicle_type));
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
        serial_write(state.serial_handle, set_mode_packet(state.target_system, mode, state.vehicle_type));

        bool mode_confirmed = state.command_condition.wait_for(
            lock,
            std::chrono::seconds(5),
            [&state, &mode]() {
                bool final_rejection = state.mode_command_result > 0 && state.mode_command_result != 5;
                return state.current_mode == mode || final_rejection;
            }
        );
        if (state.current_mode == mode) {
            publish_event(
                "mode_complete",
                "SUCCESS",
                "Flight mode confirmed by Pixhawk HEARTBEAT: " + mode
            );
        } else if (state.mode_command_result > 0 && state.mode_command_result != 5) {
            publish_event(
                "mode_failed",
                "ERROR",
                "Pixhawk rejected mode " + mode + ", COMMAND_ACK=" + std::to_string(state.mode_command_result)
            );
        } else if (!mode_confirmed) {
            publish_event(
                "mode_failed",
                "ERROR",
                "Pixhawk did not confirm mode " + mode + " with HEARTBEAT"
            );
        } else {
            publish_event("mode_failed", "ERROR", "Flight mode change failed: " + mode);
        }
        return;
    }

    if (line.rfind("GUIDED_TARGET|", 0) == 0) {
        auto values = split(line.substr(std::strlen("GUIDED_TARGET|")), ',');
        if (values.size() != 3) {
            publish_event("guided_target_failed", "ERROR", "Invalid Guided target payload");
            return;
        }
        double latitude = 0.0;
        double longitude = 0.0;
        float altitude = 0.0f;
        try {
            latitude = std::stod(values[0]);
            longitude = std::stod(values[1]);
            altitude = std::stof(values[2]);
        } catch (...) {
            publish_event("guided_target_failed", "ERROR", "Guided target contains invalid numbers");
            return;
        }
        if (!std::isfinite(latitude) || !std::isfinite(longitude) || !std::isfinite(altitude) ||
            latitude < -90.0 || latitude > 90.0 || longitude < -180.0 || longitude > 180.0 || altitude <= 0.0f) {
            publish_event("guided_target_failed", "ERROR", "Guided target is outside valid bounds");
            return;
        }

        serial_write(state.serial_handle, heartbeat_packet());
        state.mode_command_result = -1;
        serial_write(state.serial_handle, set_mode_packet(state.target_system, "GUIDED", state.vehicle_type));
        serial_write(state.serial_handle, command_long_set_mode_packet(
            state.target_system, state.target_component, "GUIDED", state.vehicle_type
        ));
        bool mode_confirmed = state.command_condition.wait_for(
            lock,
            std::chrono::seconds(2),
            [&state]() {
                return state.mode_command_result >= 0 || state.current_mode == "GUIDED";
            }
        );
        if (!mode_confirmed) {
            publish_event("guided_target_failed", "ERROR", "Pixhawk did not confirm GUIDED mode");
            return;
        }
        if (state.mode_command_result > 0 && state.current_mode != "GUIDED") {
            publish_event(
                "guided_target_failed",
                "ERROR",
                "Pixhawk rejected GUIDED mode, COMMAND_ACK=" + std::to_string(state.mode_command_result)
            );
            return;
        }

        int32_t latitude_int = static_cast<int32_t>(std::llround(latitude * 1e7));
        int32_t longitude_int = static_cast<int32_t>(std::llround(longitude * 1e7));
        if (is_copter_vehicle(state.vehicle_type)) {
            serial_write(state.serial_handle, set_position_target_global_int_packet(
                state.target_system, state.target_component, 6, latitude_int, longitude_int, altitude
            ));
            publish_event(
                "guided_target_complete",
                "SUCCESS",
                "Guided target sent with SET_POSITION_TARGET_GLOBAL_INT"
            );
        } else {
            MissionWireItem target;
            target.frame = 3;
            target.command = 16;
            target.param4 = std::numeric_limits<float>::quiet_NaN();
            target.x = latitude_int;
            target.y = longitude_int;
            target.z = altitude;
            serial_write(
                state.serial_handle,
                mission_item_int_packet(state.target_system, state.target_component, 0, target, 2, 0)
            );
            std::this_thread::sleep_for(std::chrono::milliseconds(90));
            serial_write(state.serial_handle, command_int_reposition_packet(
                state.target_system, state.target_component, 3, latitude_int, longitude_int, altitude
            ));
            std::this_thread::sleep_for(std::chrono::milliseconds(90));
            serial_write(state.serial_handle, set_position_target_global_int_packet(
                state.target_system, state.target_component, 3, latitude_int, longitude_int, altitude
            ));
            publish_event(
                "guided_target_complete",
                "SUCCESS",
                "ArduPlane Guided target dispatched with Mission Planner waypoint and stateless fallbacks"
            );
        }
        return;
    }

    if (line == "MISSION_DOWNLOAD") {
        state.download_active = true;
        state.download_expected = -1;
        state.downloaded_items.clear();
        serial_write(state.serial_handle, heartbeat_packet());
        serial_write(state.serial_handle, mission_request_list_packet(state.target_system, state.target_component));
        publish_event("mission_download_started", "INFO", "Mission download requested");
        return;
    }

    if (line == "MISSION_CLEAR") {
        state.upload_active = false;
        state.clear_active = true;
        state.upload_items.clear();
        state.uploaded_sequences.clear();
        state.mission_count_sent = false;
        serial_write(state.serial_handle, heartbeat_packet());
        serial_write(state.serial_handle, mission_clear_all_packet(state.target_system, state.target_component));
        publish_event("mission_clear_started", "INFO", "Mission clear requested");
        return;
    }

    if (line.rfind("MISSION_UPLOAD|", 0) == 0) {
        std::string body = line.substr(std::strlen("MISSION_UPLOAD|"));
        auto raw_items = split(body, ';');
        std::vector<MissionWireItem> items;
        for (const auto& raw : raw_items) {
            if (raw.empty()) continue;
            MissionWireItem item;
            if (!parse_mission_item(raw, item)) {
                publish_event("mission_upload_failed", "ERROR", "Invalid mission item payload");
                return;
            }
            items.push_back(item);
        }
        if (items.empty()) {
            state.upload_active = false;
            state.clear_active = true;
            state.upload_items.clear();
            state.uploaded_sequences.clear();
            state.mission_count_sent = false;
            serial_write(state.serial_handle, heartbeat_packet());
            serial_write(state.serial_handle, mission_clear_all_packet(state.target_system, state.target_component));
            publish_event("mission_clear_started", "INFO", "Mission clear requested");
            return;
        }
        state.clear_active = false;
        state.upload_items = items;
        state.upload_active = true;
        state.uploaded_sequences.clear();
        state.mission_count_sent = false;
        serial_write(state.serial_handle, heartbeat_packet());
        serial_write(state.serial_handle, mission_clear_all_packet(state.target_system, state.target_component));
        std::this_thread::sleep_for(std::chrono::milliseconds(120));
        serial_write(
            state.serial_handle,
            mission_count_packet(state.target_system, state.target_component, static_cast<uint16_t>(state.upload_items.size()))
        );
        state.mission_count_sent = true;
        publish_event("mission_upload_started", "INFO", "Mission upload started");
        return;
    }

    publish_event("command_error", "WARNING", "Unknown bridge command");
}

void stdin_command_loop(BridgeState& state) {
    std::string line;
    while (std::getline(std::cin, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (!line.empty()) handle_command_line(state, line);
    }
}

void process_mission_frame(BridgeState& state, const MavFrame& frame) {
    std::lock_guard<std::mutex> lock(state.mutex);
    if (state.serial_handle == INVALID_HANDLE_VALUE) return;

    if (frame.msgid == 77 && frame.payload.size() >= 3) {
        uint16_t command = le16(frame.payload.data());
        if (command == 176) {
            state.mode_command_result = static_cast<int>(frame.payload[2]);
            state.command_condition.notify_all();
        }
    }

    if (state.guided_target_pending && frame.msgid == 47 && frame.payload.size() >= 3) {
        uint8_t ack_type = frame.payload[2];
        state.guided_target_pending = false;
        if (ack_type == 0) {
            publish_event("guided_target_complete", "SUCCESS", "ArduPlane accepted Guided target");
        } else {
            publish_event(
                "guided_target_failed",
                "ERROR",
                "ArduPlane rejected Guided target, MISSION_ACK=" + std::to_string(ack_type)
            );
        }
        return;
    }

    if (state.clear_active && frame.msgid == 47 && frame.payload.size() >= 3) {
        uint8_t ack_type = frame.payload[2];
        state.clear_active = false;
        if (ack_type == 0) {
            publish_event("mission_clear_complete", "SUCCESS", "Mission cleared by Pixhawk");
        } else {
            publish_event("mission_clear_failed", "ERROR", "Mission clear rejected, ACK=" + std::to_string(ack_type));
        }
        return;
    }

    if (state.upload_active && (frame.msgid == 40 || frame.msgid == 51) && frame.payload.size() >= 2) {
        uint16_t seq = 0;
        if (frame.msgid == 51 && frame.payload.size() >= 4) {
            // MISSION_REQUEST_INT wire order starts with target_system,target_component,seq.
            seq = le16(frame.payload.data() + 2);
        } else {
            // MISSION_REQUEST wire order starts with seq.
            seq = le16(frame.payload.data());
        }
        if (seq < state.upload_items.size()) {
            serial_write(
                state.serial_handle,
                mission_item_int_packet(state.target_system, state.target_component, seq, state.upload_items[seq])
            );
            state.uploaded_sequences.insert(static_cast<int>(seq));
            publish_event(
                "mission_item_sent",
                "INFO",
                std::string("Mission item sent: seq=") + std::to_string(seq) +
                    " type=INT request=" + (frame.msgid == 51 ? "MISSION_REQUEST_INT" : "MISSION_REQUEST")
            );
        }
        return;
    }

    if (state.upload_active && frame.msgid == 47 && frame.payload.size() >= 3) {
        uint8_t ack_type = frame.payload[2];
        if (state.uploaded_sequences.size() < state.upload_items.size()) {
            publish_event(
                "mission_ack_ignored",
                "INFO",
                "Ignoring early mission ACK=" + std::to_string(ack_type)
            );
            return;
        }
        if (ack_type == 0) {
            uint16_t current = state.upload_items.size() > 1 ? 1 : 0;
            serial_write(state.serial_handle, mission_set_current_packet(state.target_system, state.target_component, current));
            publish_event("mission_upload_complete", "SUCCESS", "Mission upload accepted by Pixhawk");
        } else {
            publish_event("mission_upload_failed", "ERROR", "Mission upload rejected, ACK=" + std::to_string(ack_type));
        }
        state.upload_active = false;
        state.mission_count_sent = false;
        return;
    }

    if (state.download_active && frame.msgid == 44 && frame.payload.size() >= 2) {
        state.download_expected = static_cast<int>(le16(frame.payload.data()));
        state.downloaded_items.clear();
        if (state.download_expected <= 0) {
            state.download_active = false;
            publish_mission_downloaded(state.downloaded_items);
            return;
        }
        serial_write(state.serial_handle, mission_request_int_packet(state.target_system, state.target_component, 0));
        return;
    }

    if (state.download_active && (frame.msgid == 73 || frame.msgid == 39)) {
        auto item = mission_item_from_frame(frame);
        if (!item) return;
        state.downloaded_items.push_back(*item);
        int next = static_cast<int>(state.downloaded_items.size());
        if (state.download_expected > 0 && next < state.download_expected) {
            serial_write(state.serial_handle, mission_request_int_packet(state.target_system, state.target_component, static_cast<uint16_t>(next)));
        } else {
            state.download_active = false;
            publish_mission_downloaded(state.downloaded_items);
        }
    }
}

void request_serial_streams(HANDLE handle, uint8_t target_system, uint8_t target_component) {
    serial_write(handle, heartbeat_packet());
    serial_write(handle, request_data_stream_packet(target_system, target_component, 1, 4));   // RAW_SENSORS
    serial_write(handle, request_data_stream_packet(target_system, target_component, 2, 4));   // EXTENDED_STATUS
    serial_write(handle, request_data_stream_packet(target_system, target_component, 6, 10));  // POSITION
    serial_write(handle, request_data_stream_packet(target_system, target_component, 10, 20)); // EXTRA1 attitude
    serial_write(handle, request_data_stream_packet(target_system, target_component, 11, 10)); // EXTRA2 VFR
    serial_write(handle, request_data_stream_packet(target_system, target_component, 12, 4));  // EXTRA3
    std::cerr << "requested MAVLink streams from system=" << static_cast<int>(target_system)
              << " component=" << static_cast<int>(target_component) << "\n";
}

bool apply_frame(const MavFrame& frame, Telemetry& t) {
    const auto& p = frame.payload;
    constexpr double rad_to_deg = 57.29577951308232;
    bool changed = false;
    if (frame.msgid == 0 && p.size() >= 9) {
        uint32_t custom = le32(p.data());
        uint8_t vehicle_type = p[4];
        uint8_t autopilot = p[5];
        uint8_t base_mode = p[6];
        if (vehicle_type == 6 || autopilot == 8) {
            return false;
        }
        t.mode = mode_from_custom(custom, vehicle_type);
        t.armed = (base_mode & 0x80) != 0;
        changed = true;
    } else if (frame.msgid == 1 && p.size() >= 31) {
        uint16_t voltage = le16(p.data() + 14);
        int16_t current = sle16(p.data() + 16);
        int8_t remaining = static_cast<int8_t>(p[30]);
        if (voltage != UINT16_MAX) t.battery_voltage = voltage / 1000.0;
        if (current != INT16_MAX) t.battery_current = current / 100.0;
        if (remaining >= 0) t.battery_remaining = remaining;
        changed = true;
    } else if (frame.msgid == 24 && p.size() >= 30) {
        t.latitude = sle32(p.data() + 8) / 1e7;
        t.longitude = sle32(p.data() + 12) / 1e7;
        t.absolute_altitude = sle32(p.data() + 16) / 1000.0;
        t.gps_fix_type = static_cast<int>(p[28]);
        t.satellites_visible = static_cast<int>(p[29]);
        changed = true;
    } else if (frame.msgid == 30 && p.size() >= 28) {
        t.roll = lef32(p.data() + 4) * rad_to_deg;
        t.pitch = lef32(p.data() + 8) * rad_to_deg;
        double yaw = lef32(p.data() + 12) * rad_to_deg;
        if (yaw < 0) yaw += 360.0;
        t.yaw = yaw;
        changed = true;
    } else if (frame.msgid == 33 && p.size() >= 28) {
        t.latitude = sle32(p.data() + 4) / 1e7;
        t.longitude = sle32(p.data() + 8) / 1e7;
        t.absolute_altitude = sle32(p.data() + 12) / 1000.0;
        t.relative_altitude = sle32(p.data() + 16) / 1000.0;
        double vx = sle16(p.data() + 20) / 100.0;
        double vy = sle16(p.data() + 22) / 100.0;
        t.ground_speed = std::sqrt(vx * vx + vy * vy);
        t.vertical_speed = sle16(p.data() + 24) / 100.0;
        uint16_t hdg = le16(p.data() + 26);
        if (hdg != UINT16_MAX) t.heading = hdg / 100.0;
        changed = true;
    } else if (frame.msgid == 74 && p.size() >= 20) {
        t.air_speed = lef32(p.data());
        t.ground_speed = lef32(p.data() + 4);
        int16_t heading = sle16(p.data() + 8);
        if (heading >= 0) t.heading = heading;
        t.absolute_altitude = lef32(p.data() + 12);
        t.vertical_speed = lef32(p.data() + 16);
        changed = true;
    } else if ((frame.msgid == 109 || frame.msgid == 166) && p.size() >= 9) {
        int rssi = p[0];
        int remrssi = p[1];
        int txbuf = p[2];
        int noise = p[3];
        int remnoise = p[4];
        uint16_t rxerrors = le16(p.data() + 5);
        uint16_t fixed = le16(p.data() + 7);
        t.signal_quality = radio_link_quality_percent(rssi, remrssi, txbuf, noise, remnoise);
        static auto last_radio_log = std::chrono::steady_clock::time_point{};
        auto now = std::chrono::steady_clock::now();
        if (now - last_radio_log > std::chrono::seconds(2)) {
            last_radio_log = now;
            std::ostringstream message;
            message << (frame.msgid == 109 ? "RADIO_STATUS" : "RADIO")
                    << " rssi=" << rssi
                    << " remrssi=" << remrssi
                    << " txbuf=" << txbuf
                    << " noise=" << noise
                    << " remnoise=" << remnoise
                    << " rxerrors=" << rxerrors
                    << " fixed=" << fixed
                    << " signal=" << std::fixed << std::setprecision(1) << *t.signal_quality << "%";
            publish_event("radio_status", "INFO", message.str());
        }
        changed = true;
    } else if (frame.msgid == 77 && p.size() >= 3) {
        uint16_t command = le16(p.data());
        uint8_t result = p[2];
        publish_event(
            "command_ack",
            result == 0 ? "SUCCESS" : "WARNING",
            "COMMAND_ACK command=" + std::to_string(command) + " result=" + std::to_string(result)
        );
    } else if (frame.msgid == 253 && p.size() >= 51) {
        std::string text;
        for (size_t i = 1; i < std::min<size_t>(p.size(), 51); ++i) {
            if (p[i] == 0) break;
            text.push_back(static_cast<char>(p[i]));
        }
        if (!text.empty()) publish_event("statustext", "INFO", "Autopilot: " + text);
    }
    t.connected = true;
    return changed;
}

Args parse_args(int argc, char** argv) {
    Args args;
    for (int i = 1; i < argc; ++i) {
        std::string key = argv[i];
        if (key == "--type" && i + 1 < argc) args.type = argv[++i];
        else if (key == "--target" && i + 1 < argc) args.target = argv[++i];
        else if (key == "--baud" && i + 1 < argc) args.baud = std::stoi(argv[++i]);
    }
    std::transform(args.type.begin(), args.type.end(), args.type.begin(), ::toupper);
    return args;
}

#ifdef _WIN32
void run_serial(const Args& args) {
    std::string port = args.target;
    if (port.rfind("\\\\.\\", 0) != 0) port = "\\\\.\\" + port;
    HANDLE handle = CreateFileA(port.c_str(), GENERIC_READ | GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, 0, nullptr);
    if (handle == INVALID_HANDLE_VALUE) {
        std::cerr << "serial open failed: " << args.target << "\n";
        return;
    }

    DCB dcb = {};
    dcb.DCBlength = sizeof(dcb);
    GetCommState(handle, &dcb);
    dcb.BaudRate = args.baud;
    dcb.ByteSize = 8;
    dcb.Parity = NOPARITY;
    dcb.StopBits = ONESTOPBIT;
    SetCommState(handle, &dcb);

    COMMTIMEOUTS timeouts = {};
    timeouts.ReadIntervalTimeout = 1;
    timeouts.ReadTotalTimeoutConstant = 10;
    timeouts.ReadTotalTimeoutMultiplier = 1;
    SetCommTimeouts(handle, &timeouts);

    MavParser parser;
    Telemetry telemetry;
    BridgeState bridge_state;
    bridge_state.serial_handle = handle;
    std::thread command_thread(stdin_command_loop, std::ref(bridge_state));
    command_thread.detach();

    auto last_publish = std::chrono::steady_clock::now();
    auto last_stream_request = std::chrono::steady_clock::now() - std::chrono::seconds(10);
    auto last_mission_kick = std::chrono::steady_clock::now();
    uint8_t target_system = 1;
    uint8_t target_component = 1;
    bool target_seen = false;
    uint8_t buf[512];
    while (true) {
        DWORD read = 0;
        if (!ReadFile(handle, buf, sizeof(buf), &read, nullptr)) break;
        bool changed = false;
        for (DWORD i = 0; i < read; ++i) {
            auto frame = parser.feed(buf[i]);
            if (frame) {
                if (frame->sysid != 0 && frame->sysid != 255) {
                    target_system = frame->sysid;
                    target_component = frame->compid ? frame->compid : 1;
                    target_seen = true;
                    std::lock_guard<std::mutex> lock(bridge_state.mutex);
                    bridge_state.target_system = target_system;
                    bridge_state.target_component = target_component;
                    bridge_state.target_seen = true;
                    if (frame->msgid == 0 && frame->payload.size() >= 9) {
                        uint8_t vehicle_type = frame->payload[4];
                        uint8_t autopilot = frame->payload[5];
                        if (vehicle_type != 6 && autopilot != 8) {
                            bridge_state.vehicle_type = vehicle_type;
                            bridge_state.current_mode = mode_from_custom(le32(frame->payload.data()), vehicle_type);
                            bridge_state.command_condition.notify_all();
                        }
                    }
                }
                process_mission_frame(bridge_state, *frame);
                changed = apply_frame(*frame, telemetry) || changed;
            }
        }
        auto now = std::chrono::steady_clock::now();
        bool mission_busy = false;
        {
            std::lock_guard<std::mutex> lock(bridge_state.mutex);
            mission_busy = bridge_state.upload_active || bridge_state.download_active || bridge_state.clear_active;
        }
        if (target_seen && !mission_busy && now - last_stream_request >= std::chrono::seconds(3)) {
            request_serial_streams(handle, target_system, target_component);
            last_stream_request = now;
        }
        if (target_seen && now - last_mission_kick >= std::chrono::seconds(2)) {
            std::lock_guard<std::mutex> lock(bridge_state.mutex);
            if (bridge_state.download_active) {
                serial_write(handle, mission_request_list_packet(bridge_state.target_system, bridge_state.target_component));
                publish_event("mission_download_retry", "INFO", "Mission download request repeated");
            } else if (bridge_state.clear_active) {
                serial_write(handle, mission_clear_all_packet(bridge_state.target_system, bridge_state.target_component));
                publish_event("mission_clear_retry", "INFO", "Mission clear request repeated");
            }
            last_mission_kick = now;
        }
        if (changed && now - last_publish >= std::chrono::milliseconds(40)) {
            publish(telemetry);
            last_publish = now;
        }
    }
    {
        std::lock_guard<std::mutex> lock(bridge_state.mutex);
        bridge_state.serial_handle = INVALID_HANDLE_VALUE;
    }
    CloseHandle(handle);
}

void run_udp(const Args& args) {
    WSADATA wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);
    SOCKET sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    sockaddr_in addr = {};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    int port = 14550;
    auto pos = args.target.find_last_of(':');
    if (pos != std::string::npos) port = std::stoi(args.target.substr(pos + 1));
    addr.sin_port = htons(static_cast<u_short>(port));
    bind(sock, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));

    MavParser parser;
    Telemetry telemetry;
    auto last_publish = std::chrono::steady_clock::now();
    uint8_t buf[2048];
    while (true) {
        int read = recv(sock, reinterpret_cast<char*>(buf), sizeof(buf), 0);
        if (read <= 0) continue;
        bool changed = false;
        for (int i = 0; i < read; ++i) {
            auto frame = parser.feed(buf[i]);
            if (frame) changed = apply_frame(*frame, telemetry) || changed;
        }
        auto now = std::chrono::steady_clock::now();
        if (changed && now - last_publish >= std::chrono::milliseconds(40)) {
            publish(telemetry);
            last_publish = now;
        }
    }
    closesocket(sock);
    WSACleanup();
}
#endif

} // namespace

int main(int argc, char** argv) {
    Args args = parse_args(argc, argv);
#ifdef _WIN32
    if (args.type == "SERIAL") run_serial(args);
    else run_udp(args);
#else
    std::cerr << "telemetry_bridge currently supports Windows serial/udp builds\n";
#endif
    return 0;
}
