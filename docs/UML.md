# BLACK BOX Yer Kontrol Istasyonu - UML

Bu dokuman projenin ana mimarisini UML/Mermaid diyagramlariyla ozetler. Diyagramlar uygulamadaki gercek modullere gore hazirlanmistir:

- PyQt5 yer istasyonu arayuzu
- MAVLink/Pixhawk telemetri ve mission katmani
- Hakem sunucusu icin ayri C++ `communication_core` servisi
- Kamera, harita, gorev, fence ve parametre akislarinin baglantilari

## 1. Genel Komponent Diyagrami

```mermaid
flowchart LR
    User["Operator / Pilot"] --> UI["PyQt5 UI\nMainWindow"]

    UI --> Flight["FlightTab\nHUD + Map + Camera + Modes"]
    UI --> Mission["MissionTab\nMission + Fence"]
    UI --> Logs["LogsTab"]
    UI --> Params["ParametersTab"]

    UI --> TelemetryWorker["TelemetryWorker\nQThread"]
    UI --> VideoWorker["VideoWorker\nQThread"]
    UI --> RefVideo["RefereeVideoStream\nMJPEG + optional upload"]
    UI --> CoreStatus["CommunicationCoreStatusWorker\n1 Hz /status polling"]

    TelemetryWorker --> TelemetryManager["TelemetryManager"]
    TelemetryManager --> SimBackend["SimulationTelemetryBackend"]
    TelemetryManager --> PyMavlink["MavlinkTelemetryBackend\nmission/fence/params"]
    TelemetryManager --> CppBridge["CppTelemetryBackend\ntelemetry bridge process"]
    CppBridge --> CppBridgeExe["backend_cpp/telemetry_bridge.exe"]
    PyMavlink --> Pixhawk["Pixhawk / MAVLink"]
    CppBridgeExe --> Pixhawk

    Mission --> MissionManager["MissionManager"]
    Flight --> SharedMap["SharedMapState"]
    Mission --> SharedMap
    SharedMap --> MapWidget["MapWidget\nMBTiles + overlays"]

    UI --> CommCoreExe["communication_core_service.exe"]
    CommCoreExe --> LocalRest["Local REST\n127.0.0.1:8090"]
    CoreStatus --> LocalRest
    UI --> LocalRest
    LocalRest --> CommState["StateStore"]
    CommCoreExe --> Hakem["Hakem Sunucusu\nHTTP API"]
    RefVideo --> Hakem

    VideoWorker --> Flight
```

## 2. Python Yer Istasyonu Sinif Diyagrami

```mermaid
classDiagram
    class MainWindow {
        +mission_manager: MissionManager
        +telemetry_worker: TelemetryWorker
        +video_worker: VideoWorker
        +communication_core_worker: CommunicationCoreStatusWorker
        +shared_map_state: SharedMapState
        +init_ui()
        +init_workers()
        +setup_connections()
        +start_workers()
        -_on_telemetry_received(telemetry)
        -_on_referee_connect_requested(cfg)
        -_on_mission_upload_requested(items, zones)
        -_on_parameters_refresh_requested()
    }

    class FlightTab {
        +connect_requested
        +disconnect_requested
        +mode_change_requested
        +referee_connect_requested
        +referee_qr_fetch_requested
        +referee_hss_fetch_requested
        +update_telemetry(telemetry)
        +update_video_frame(image)
        +set_connection_status(connected)
    }

    class MissionTab {
        +mission_upload_requested
        +mission_download_requested
        +fit_mission_on_map()
    }

    class LogsTab {
        +update_telemetry_status(connected)
        +update_video_status(connected)
    }

    class ParametersTab {
        +refresh_requested
        +set_loading(loading)
        +set_parameters(parameters)
    }

    class TelemetryWorker {
        +telemetry_received
        +connection_status_changed
        +mission_downloaded
        +fence_downloaded
        +parameters_downloaded
        +connect_backend(cfg)
        +upload_mission(items, zones)
        +download_mission()
        +download_parameters()
    }

    class VideoWorker {
        +frame_ready
        +video_finished
        +run()
        +stop()
    }

    class CommunicationCoreStatusWorker {
        +status_received
        +run()
        +stop()
    }

    class RefereeVideoStream {
        +start()
        +stop()
        +update_frame(image)
        +start_upload(base_url, path, team_number)
        +register_stream_url(base_url, stream_url, team_number)
    }

    class TelemetryManager {
        +connect(config)
        +disconnect()
        +read(timeout)
        +set_mode(mode_name)
        +upload_mission(items, zones)
        +download_mission()
        +upload_fence(zones)
        +download_fence()
        +download_parameters()
    }

    class TelemetryBackend {
        <<abstract>>
        +start()
        +stop()
        +read(timeout)
        +set_mode(mode_name)
        +upload_mission(items)
        +download_mission()
        +upload_fence(zones)
        +download_fence()
        +download_parameters()
    }

    class CppTelemetryBackend
    class MavlinkTelemetryBackend
    class SimulationTelemetryBackend

    class MissionManager {
        +items
        +add_waypoint(lat, lon)
        +remove_item(index)
        +replace_items(items)
        +clear()
    }

    class SharedMapState {
        +aircraft_lat
        +aircraft_lon
        +aircraft_heading
        +defense_zones
        +overlay_markers
        +set_aircraft(lat, lon, heading)
        +set_overlay_markers(markers)
        +add_defense_zone(zone)
        +save_defense_zones()
    }

    class MapWidget {
        +coordinate_clicked
        +coordinate_double_clicked
        +set_overlay_markers(markers)
        +add_defense_zone(zone)
    }

    MainWindow *-- FlightTab
    MainWindow *-- MissionTab
    MainWindow *-- LogsTab
    MainWindow *-- ParametersTab
    MainWindow *-- TelemetryWorker
    MainWindow *-- VideoWorker
    MainWindow *-- CommunicationCoreStatusWorker
    MainWindow *-- RefereeVideoStream
    MainWindow *-- MissionManager
    MainWindow *-- SharedMapState

    FlightTab --> SharedMapState
    MissionTab --> MissionManager
    MissionTab --> SharedMapState
    MapWidget --> SharedMapState
    TelemetryWorker *-- TelemetryManager
    TelemetryManager --> TelemetryBackend
    TelemetryBackend <|-- CppTelemetryBackend
    TelemetryBackend <|-- MavlinkTelemetryBackend
    TelemetryBackend <|-- SimulationTelemetryBackend
```

## 3. Veri Modeli UML

```mermaid
classDiagram
    class TelemetryData {
        +timestamp: float
        +connected: bool
        +mode: str
        +armed: bool
        +latitude: float
        +longitude: float
        +relative_altitude: float
        +ground_speed: float
        +pitch: float
        +roll: float
        +yaw: float
        +heading: float
        +battery_remaining: float
        +signal_quality: float
        +altitude
        +speed
        +battery
        +to_dict()
    }

    class MissionItem {
        +item_type: MissionItemType
        +sequence: int
        +latitude: float
        +longitude: float
        +altitude: float
        +speed: float
        +parameters: dict
        +to_dict()
        +from_dict(data)
    }

    class MissionItemType {
        <<enumeration>>
        TAKEOFF
        WAYPOINT
        DO_JUMP
        RTL
        DO_LAND_START
        LAND
    }

    class DefenseZone {
        +center_lat: float
        +center_lon: float
        +radius_m: float
        +name: str
        +is_active: bool
        +color: tuple
    }

    MissionItem --> MissionItemType
    SharedMapState "1" o-- "*" DefenseZone
    MissionManager "1" o-- "*" MissionItem
```

## 4. C++ Communication Core Sinif Diyagrami

```mermaid
classDiagram
    class AppContext {
        +config(): AppConfig
        +state(): StateStore
        +events(): EventBus
    }

    class AppConfig {
        +server: ServerConfig
        +vehicle_manager: VehicleManagerConfig
        +team_number: int
        +telemetry_upload_hz: double
        +mavlink_connection_url: string
        +rest_port: int
    }

    class StateStore {
        +updateVehicleState(state)
        +vehicleState()
        +setServerTime(time)
        +serverTime()
        +setQrCoordinate(coordinate)
        +setHssCoordinates(coordinates)
        +setOpponentPositions(positions)
        +connectionStatus()
    }

    class EventBus {
        +publish(event)
        +subscribe(type, handler)
    }

    class CompetitionApiClient {
        +login(username, password)
        +getServerTime()
        +sendTelemetry(packet)
        +sendLockInfo(packet)
        +sendKamikazeInfo(packet)
        +getQrCoordinate()
        +getHssCoordinates()
    }

    class ICompetitionApi {
        <<interface>>
        +login(username, password)
        +getServerTime()
        +sendTelemetry(packet)
        +getQrCoordinate()
        +getHssCoordinates()
    }

    class AuthManager {
        +login()
        +ensureAuthenticated()
    }

    class ServerClockSync {
        +sync()
        +serverNow()
        +offset()
    }

    class TelemetryUploader {
        +tick()
        +upload(vehicle_state)
    }

    class QrCoordinateClient {
        +fetchOnce()
    }

    class HssCoordinateClient {
        +fetchOnce()
    }

    class LocalWebSocketServer {
        +setVehicleIntegrations(qr, hss, command_sender)
        +start()
        +stop()
    }

    class VehicleManagerCommandSender {
        +sendJson(json)
        +sendQr(coordinate)
        +sendHss(coordinates)
        +sendTimeSync(server_time)
    }

    AppContext *-- AppConfig
    AppContext *-- StateStore
    AppContext *-- EventBus

    ICompetitionApi <|.. CompetitionApiClient
    AuthManager --> ICompetitionApi
    ServerClockSync --> ICompetitionApi
    ServerClockSync --> StateStore
    TelemetryUploader --> ICompetitionApi
    TelemetryUploader --> StateStore
    QrCoordinateClient --> ICompetitionApi
    QrCoordinateClient --> StateStore
    HssCoordinateClient --> ICompetitionApi
    HssCoordinateClient --> StateStore
    LocalWebSocketServer --> AppContext
    LocalWebSocketServer --> QrCoordinateClient
    LocalWebSocketServer --> HssCoordinateClient
    LocalWebSocketServer --> VehicleManagerCommandSender
```

## 5. Telemetri Akis Sequence Diyagrami

```mermaid
sequenceDiagram
    participant Pixhawk
    participant Backend as TelemetryBackend
    participant Worker as TelemetryWorker
    participant Main as MainWindow
    participant Flight as FlightTab
    participant Map as SharedMapState
    participant Hakem as communication_core

    Pixhawk->>Backend: MAVLink messages
    Backend->>Worker: TelemetryData
    Worker->>Main: telemetry_received
    Main->>Flight: update_telemetry()
    Flight->>Map: set_aircraft(lat, lon, heading)
    Main->>Hakem: POST /vehicle/state (1 Hz)
    Hakem->>Hakem: sendTelemetry() to referee server (1 Hz)
```

## 6. Mission/Fence Gonderme Sequence Diyagrami

```mermaid
sequenceDiagram
    participant User
    participant MissionTab
    participant MainWindow
    participant TelemetryWorker
    participant TelemetryManager
    participant MavlinkBackend
    participant Pixhawk

    User->>MissionTab: Waypoint/Fence ekle
    User->>MissionTab: Send Mission to Pixhawk
    MissionTab->>MainWindow: mission_upload_requested(items, zones)
    MainWindow->>TelemetryWorker: upload_mission(items, zones)
    TelemetryWorker->>TelemetryManager: upload_mission(items, zones)

    alt Current backend is C++ bridge
        TelemetryManager->>TelemetryManager: stop C++ bridge
        TelemetryManager->>MavlinkBackend: temporary pymavlink backend
    end

    MavlinkBackend->>Pixhawk: MISSION_COUNT
    Pixhawk->>MavlinkBackend: MISSION_REQUEST_INT / MISSION_REQUEST
    MavlinkBackend->>Pixhawk: MISSION_ITEM_INT
    Pixhawk->>MavlinkBackend: MISSION_ACK
    MavlinkBackend->>Pixhawk: Fence upload/download verify
    TelemetryManager->>TelemetryWorker: verified mission/fence
    TelemetryWorker->>MainWindow: mission_downloaded + fence_downloaded
    MainWindow->>MissionTab: refresh tables/map
```

## 7. Hakem Sunucusu Akis Sequence Diyagrami

```mermaid
sequenceDiagram
    participant User
    participant FlightTab
    participant MainWindow
    participant Core as communication_core_service
    participant LocalRest as Local REST 8090
    participant Referee as Hakem Sunucusu
    participant Map as SharedMapState

    User->>FlightTab: Hakem bilgilerini gir + Baglan
    FlightTab->>MainWindow: referee_connect_requested(cfg)
    MainWindow->>MainWindow: config.yaml yaz
    MainWindow->>Core: process baslat
    Core->>Referee: login()
    MainWindow->>LocalRest: GET /healthz
    MainWindow->>FlightTab: Connected + server time

    loop 1 Hz
        MainWindow->>LocalRest: GET /status
        LocalRest->>MainWindow: server_time, opponents, qr, hss
        MainWindow->>Map: rakip markerlarini guncelle
    end

    User->>FlightTab: QR Koordinatlarini Cek
    FlightTab->>MainWindow: referee_qr_fetch_requested
    MainWindow->>LocalRest: POST /vehicle/send_qr
    Core->>Referee: getQrCoordinate()
    Core->>LocalRest: StateStore qr_coordinate
    MainWindow->>Map: QR marker goster

    User->>FlightTab: Hava Savunma Koordinatlarini Cek
    FlightTab->>MainWindow: referee_hss_fetch_requested
    MainWindow->>LocalRest: POST /vehicle/send_hss
    Core->>Referee: getHssCoordinates()
    Core->>LocalRest: StateStore hss_coordinates
    MainWindow->>Map: HSS fence alanlarini goster
```

## 8. Thread ve Process Mimarisi

```mermaid
flowchart TB
    subgraph UIProcess["Python UI Process"]
        UIThread["Main UI Thread\nPyQt widgets + signal handlers"]
        TWorker["TelemetryWorker QThread"]
        VWorker["VideoWorker QThread"]
        SWorker["CommunicationCoreStatusWorker QThread"]
        MJPEG["RefereeVideoStream\nbackground HTTP/upload threads"]
    end

    subgraph TelemetryProcesses["Telemetry Processes"]
        CPPBridge["backend_cpp telemetry_bridge.exe"]
        PyMav["pymavlink temporary backend\nmission/fence/params"]
    end

    subgraph HakemProcess["Communication Core Process"]
        CommMain["communication_core_service.exe"]
        LocalApi["Local REST 8090"]
        RefereeLoop["1 Hz telemetry upload + status"]
    end

    UIThread <-->|signals| TWorker
    UIThread <-->|signals| VWorker
    UIThread <-->|signals| SWorker
    TWorker --> CPPBridge
    TWorker --> PyMav
    UIThread --> CommMain
    SWorker --> LocalApi
    MJPEG --> CommMain
```

## 9. Kisa Sorumluluk Ozeti

| Katman | Ana siniflar | Sorumluluk |
|---|---|---|
| UI | `MainWindow`, `FlightTab`, `MissionTab`, `LogsTab`, `ParametersTab` | Kullanici etkilesimi ve ekran guncellemeleri |
| Harita | `SharedMapState`, `MapWidget`, `MissionManager` | Harita gorunumu, waypoint, fence, QR/rakip overlay |
| Telemetri | `TelemetryWorker`, `TelemetryManager`, `TelemetryBackend` | Pixhawk baglantisi, veri okuma, mode/mission/fence/param komutlari |
| Video | `VideoWorker`, `VideoWidget`, `RefereeVideoStream` | Kamera goruntusu ve hakem tarafina video aktarimi |
| Hakem servis | `communication_core_service`, `CompetitionApiClient`, `StateStore` | Hakem login, telemetri gonderme, server time, QR/HSS/rakip verisi |
| Veri modelleri | `TelemetryData`, `MissionItem`, `DefenseZone` | Uygulama icinde tasinan temel veri yapilari |

