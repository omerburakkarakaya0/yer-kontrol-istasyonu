<template>
    <div class="analysis-page">
        <aside class="analysis-sidebar">
            <div class="brand-row">
                <i class="fas fa-crosshairs"></i>
                <h2>Rakip SIHA Analizi</h2>
            </div>

            <div class="source-status" :class="{ inactive: !analysisActive }">
                <span class="status-dot"></span>
                {{ analysisActive
                    ? 'Gercek Pixhawk ve hakem telemetri analizi'
                    : 'Pixhawk Cube Orange baglantisi bekleniyor' }}
            </div>
            <p class="summary">{{ summary }}</p>

            <section class="control-section">
                <label for="camera-mode">Kamera</label>
                <select id="camera-mode" v-model="cameraMode" @change="applyCameraMode">
                    <option value="perspective">Perspektif</option>
                    <option value="top">Ustten</option>
                    <option value="side">Yandan</option>
                    <option value="follow">Secili SIHA Takip</option>
                    <option value="free">Serbest</option>
                </select>
            </section>

            <section class="mission-card">
                <div class="section-title">Bizim Mission Rotamiz</div>
                <div class="metric-row">
                    <span>Waypoint</span>
                    <strong>{{ missionPoints.length }}</strong>
                </div>
                <div class="metric-row">
                    <span>Irtifa araligi</span>
                    <strong>{{ missionAltitudeRange }}</strong>
                </div>
                <div class="metric-row">
                    <span>Kendi telemetri</span>
                    <strong>
                        {{ ownship && ownship.points.length
                            ? ownship.points.length + ' nokta'
                            : 'Plan uzerinde' }}
                    </strong>
                </div>
            </section>

            <section class="risk-section">
                <div class="section-title">3B Rota Yaklasma Analizi</div>
                <p v-if="missionPoints.length < 2" class="muted">
                    Analiz icin Mission sekmesinde en az iki waypoint olusturun.
                </p>
                <p v-else-if="conflicts.length === 0" class="muted">
                    Rakip telemetrisi bekleniyor.
                </p>
                <button
                    v-for="conflict in conflicts"
                    :key="conflict.id"
                    class="risk-row"
                    :class="conflict.level"
                    @click="selectOpponent(conflict.id)">
                    <span>{{ conflict.callsign }}</span>
                    <strong>{{ formatDistance(conflict.distance) }}</strong>
                    <small>{{ conflict.label }}</small>
                </button>
            </section>

            <div class="section-title">Hakem Rakip Telemetrileri</div>
            <div class="opponent-list">
                <button
                    v-for="opponent in opponents"
                    :key="opponent.id"
                    :class="{ active: selectedOpponentId === opponent.id }"
                    :style="{ borderLeftColor: opponent.color }"
                    @click="selectOpponent(opponent.id)">
                    <span class="name">{{ opponent.callsign }}</span>
                    <span class="meta">{{ opponent.points.length }} nokta</span>
                </button>
            </div>

            <table v-if="selectedOpponent" class="details">
                <tbody>
                    <tr><th>ID</th><td>{{ selectedOpponent.id }}</td></tr>
                    <tr><th>Takim</th><td>{{ selectedOpponent.team || '-' }}</td></tr>
                    <tr><th>Zaman</th><td>{{ formatSeconds(currentSample.timestamp) }} sn</td></tr>
                    <tr><th>Enlem</th><td>{{ formatNumber(currentSample.latitude, 6) }}</td></tr>
                    <tr><th>Boylam</th><td>{{ formatNumber(currentSample.longitude, 6) }}</td></tr>
                    <tr><th>Irtifa</th><td>{{ formatNumber(currentSample.altitude, 1) }} m</td></tr>
                    <tr><th>Hiz</th><td>{{ formatNumber(currentSample.speed, 1) }} m/s</td></tr>
                    <tr><th>Heading</th><td>{{ formatNumber(currentSample.heading, 1) }} deg</td></tr>
                    <tr><th>Pitch</th><td>{{ formatNumber(currentSample.pitch, 1) }} deg</td></tr>
                    <tr><th>Roll</th><td>{{ formatNumber(currentSample.roll, 1) }} deg</td></tr>
                </tbody>
            </table>
        </aside>

        <main class="viewer-shell">
            <div id="liveOpponentCesiumContainer"></div>
            <div class="viewer-badges">
                <template v-if="analysisActive">
                    <span class="mission-badge">Mission: {{ missionPoints.length }} WP</span>
                    <span>Hakem: {{ opponents.length }} rakip</span>
                </template>
                <span v-else class="waiting-badge">Pixhawk bekleniyor</span>
            </div>
            <div v-if="analysisActive" class="legend">
                <span class="mission-legend">Bizim planlanan rota</span>
                <span v-if="ownship" class="ownship-legend">Bizim SIHA telemetrisi</span>
                <span
                    v-for="opponent in opponents"
                    :key="opponent.id"
                    :style="{ color: opponent.color }">
                    {{ opponent.callsign }}
                </span>
            </div>
        </main>
    </div>
</template>

<script>
import {
    BoundingSphere,
    Cartesian2,
    Cartesian3,
    ClockRange,
    Color,
    ColorBlendMode,
    ColorGeometryInstanceAttribute,
    GeometryInstance,
    HeadingPitchRange,
    HeadingPitchRoll,
    JulianDate,
    LabelStyle,
    PointGraphics,
    PolylineColorAppearance,
    PolylineGeometry,
    Primitive,
    Quaternion,
    Rectangle,
    SampledPositionProperty,
    SampledProperty,
    SingleTileImageryProvider,
    TimeInterval,
    TimeIntervalCollection,
    Transforms,
    Viewer
} from 'cesium'

import 'cesium/Build/Cesium/Widgets/widgets.css'

const COLORS = ['#35c7ff', '#ff4f81', '#9cff57', '#b980ff', '#ff6b35', '#48f2b4']
const MISSION_COLOR = '#ffd447'
const OWNSHIP_COLOR = '#ff9d2e'
const SOIL_COLOR = '#756348'
const FLIGHT_AREA_BOUNDS = {
    west: 38.4000,
    south: 38.3083,
    east: 38.4520,
    north: 38.3360
}
const ANALYSIS_PLANE_BOUNDS = {
    west: 38.3636,
    south: 38.28891,
    east: 38.4884,
    north: 38.35539
}

function toNumber (value, fallback = 0) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : fallback
}

function degToRad (value) {
    return toNumber(value) * Math.PI / 180
}

function haversineDistance (first, second) {
    const radius = 6371000
    const lat1 = degToRad(first.latitude)
    const lat2 = degToRad(second.latitude)
    const deltaLat = lat2 - lat1
    const deltaLon = degToRad(second.longitude - first.longitude)
    const a = Math.sin(deltaLat / 2) ** 2 +
        Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLon / 2) ** 2
    return radius * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)))
}

export default {
    name: 'LiveOpponentCesiumViewer',
    data () {
        return {
            viewer: null,
            analysisActive: false,
            opponents: [],
            missionPoints: [],
            ownship: null,
            conflicts: [],
            selectedOpponentId: null,
            currentSamples: {},
            summary: 'Hakem sunucusundan rakip telemetri bekleniyor.',
            entities: [],
            primitives: [],
            retiredPrimitives: [],
            primitiveGeneration: 0,
            cameraMode: 'perspective',
            pollTimer: null,
            lastPayloadSignature: '',
            imageryBoundsSignature: '',
            fetching: false,
            hasFramedScene: false,
            playbackSeconds: null,
            start: null,
            stop: null,
            timeOffset: 0,
            clockMaxSeconds: null
        }
    },
    computed: {
        selectedOpponent () {
            return this.opponents.find(opponent => opponent.id === this.selectedOpponentId) || null
        },
        currentSample () {
            if (!this.selectedOpponent) {
                return {}
            }
            return this.currentSamples[this.selectedOpponent.id] ||
                this.selectedOpponent.points[this.selectedOpponent.points.length - 1] || {}
        },
        missionAltitudeRange () {
            if (this.missionPoints.length === 0) {
                return '-'
            }
            const altitudes = this.missionPoints.map(point => point.altitude)
            return `${Math.min(...altitudes).toFixed(0)} - ${Math.max(...altitudes).toFixed(0)} m`
        }
    },
    mounted () {
        this.createViewer()
        window.addEventListener('resize', this.resizeViewer)
        this.fetchAnalysisData()
        this.pollTimer = window.setInterval(this.fetchAnalysisData, 1000)
        this.$nextTick(() => window.setTimeout(this.resizeViewer, 100))
    },
    beforeDestroy () {
        window.removeEventListener('resize', this.resizeViewer)
        if (this.pollTimer) {
            window.clearInterval(this.pollTimer)
        }
        if (this.viewer) {
            this.viewer.clock.onTick.removeEventListener(this.updateCurrentSamples)
            this.viewer.destroy()
            this.viewer = null
        }
    },
    methods: {
        createViewer () {
            this.viewer = new Viewer('liveOpponentCesiumContainer', {
                animation: true,
                timeline: true,
                homeButton: false,
                geocoder: false,
                baseLayerPicker: false,
                navigationHelpButton: false,
                selectionIndicator: false,
                scene3DOnly: false,
                shouldAnimate: false,
                requestRenderMode: true,
                maximumRenderTimeChange: 0.2,
                shadows: false,
                orderIndependentTranslucency: false,
                imageryProvider: false,
                useBrowserRecommendedResolution: true
            })
            this.viewer.scene.globe.depthTestAgainstTerrain = true
            this.viewer.scene.globe.baseColor = Color.fromCssColorString(SOIL_COLOR)
            this.viewer.scene.backgroundColor = Color.fromCssColorString(SOIL_COLOR)
            this.viewer.scene.fog.enabled = false
            this.viewer.scene.sun.show = false
            this.viewer.scene.moon.show = false
            this.viewer.scene.skyAtmosphere.show = false
            this.viewer.scene.skyBox.show = false
            this.viewer.scene.screenSpaceCameraController.enableCollisionDetection = false
            this.viewer.clock.onTick.addEventListener(this.updateCurrentSamples)
            this.refreshImageryLayers()
            this.setPlaybackControlsVisible(false)
            this.resizeViewer()
        },
        resizeViewer () {
            if (!this.viewer || this.viewer.isDestroyed()) {
                return
            }
            this.viewer.resize()
            this.viewer.scene.requestRender()
        },
        setPlaybackControlsVisible (visible) {
            if (!this.viewer) {
                return
            }
            if (this.viewer.animation && this.viewer.animation.container) {
                this.viewer.animation.container.style.display = visible ? '' : 'none'
            }
            if (this.viewer.timeline && this.viewer.timeline.container) {
                this.viewer.timeline.container.style.display = visible ? '' : 'none'
            }
            this.viewer.resize()
        },
        async fetchAnalysisData () {
            if (this.fetching) {
                return
            }
            this.fetching = true
            try {
                const response = await fetch(`/analysis-data?t=${Date.now()}`, { cache: 'no-store' })
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`)
                }
                const payload = await response.json()
                const signature = this.payloadSignature(payload)
                if (signature !== this.lastPayloadSignature) {
                    this.lastPayloadSignature = signature
                    this.loadAnalysisPayload(payload)
                }
            } catch (error) {
                this.summary = `Hakem telemetri akisi okunamadi: ${error.message || error}`
            } finally {
                this.fetching = false
            }
        },
        payloadSignature (payload) {
            const route = Array.isArray(payload.mission) ? payload.mission : []
            const opponents = Array.isArray(payload.opponents) ? payload.opponents : []
            const ownship = payload.ownship || null
            const opponentParts = opponents.map(item => {
                const points = item.telemetry || item.samples || item.positions || []
                const last = points[points.length - 1] || {}
                return [item.id, points.length, last.timestamp, last.latitude, last.longitude, last.altitude]
            })
            const ownPoints = ownship ? (ownship.telemetry || ownship.samples || []) : []
            const ownLast = ownPoints[ownPoints.length - 1] || {}
            return JSON.stringify({
                active: Boolean(payload.analysis_active),
                route: route.map(item => [item.sequence, item.latitude, item.longitude, item.altitude, item.speed]),
                opponents: opponentParts,
                own: [ownPoints.length, ownLast.timestamp, ownLast.latitude, ownLast.longitude, ownLast.altitude]
            })
        },
        loadAnalysisPayload (payload) {
            const wasActive = this.analysisActive
            this.analysisActive = Boolean(payload.analysis_active)
            const previousSelection = this.selectedOpponentId
            const opponents = this.normalizeOpponents(payload.opponents || [])
            const missionPoints = this.normalizeMission(payload.mission || [])
            const ownship = this.normalizeAircraft(payload.ownship, OWNSHIP_COLOR)
            const firstLoad = !this.hasFramedScene

            this.setPlaybackControlsVisible(this.analysisActive)
            if (!this.analysisActive) {
                this.clearScene()
                this.opponents = []
                this.missionPoints = []
                this.ownship = null
                this.conflicts = []
                this.selectedOpponentId = null
                this.currentSamples = {}
                this.clockMaxSeconds = null
                this.summary = 'Demo verisi analiz disi. Gercek Pixhawk Cube Orange baglantisi bekleniyor.'
                window.setTimeout(() => this.setCameraMode('perspective'), 100)
                this.viewer.scene.requestRender()
                return
            }
            const primitiveGeneration = this.beginSceneUpdate()
            this.opponents = opponents
            this.missionPoints = missionPoints
            this.ownship = ownship
            this.selectedOpponentId = opponents.some(item => item.id === previousSelection)
                ? previousSelection
                : (opponents[0] ? opponents[0].id : null)
            this.currentSamples = {}

            const aircraft = [...opponents]
            if (ownship && ownship.points.length) {
                aircraft.push(ownship)
            } else if (missionPoints.length) {
                aircraft.push({
                    id: 'bizim-plan',
                    callsign: 'Bizim SIHA',
                    team: 'Bizim Takim',
                    color: MISSION_COLOR,
                    ownship: true,
                    points: missionPoints
                })
            }

            this.refreshImageryLayers()
            if (aircraft.length) {
                this.configureClock(aircraft)
                aircraft.forEach(item => this.drawAircraft(item))
            }
            this.drawMission()
            this.finishSceneUpdate(primitiveGeneration)
            this.conflicts = this.calculateConflicts()
            this.updateCurrentSamples()
            this.updateSummary()

            if ((firstLoad || !wasActive) && this.getCameraScenePoints().length) {
                this.hasFramedScene = true
                window.setTimeout(() => this.setCameraMode('perspective'), 200)
            } else if (this.cameraMode === 'follow') {
                this.trackSelectedAircraft()
            }
            this.viewer.scene.requestRender()
        },
        normalizeOpponents (raw) {
            return (Array.isArray(raw) ? raw : [])
                .map((item, index) => {
                    const normalized = this.normalizeAircraft(item, COLORS[index % COLORS.length])
                    if (normalized) {
                        const fallbackName = `Rakip ${item.team || item.id || index + 1}`
                        normalized.callsign = String(item.callsign || item.name || fallbackName)
                    }
                    return normalized
                })
                .filter(item => item && item.points.length)
        },
        normalizeAircraft (item, fallbackColor) {
            if (!item || typeof item !== 'object') {
                return null
            }
            const telemetry = item.telemetry || item.samples || item.positions || item.track || []
            const points = (Array.isArray(telemetry) ? telemetry : [])
                .map((sample, index) => this.normalizeSample(sample, index))
                .filter(sample => Number.isFinite(sample.latitude) && Number.isFinite(sample.longitude))
                .sort((a, b) => a.timestamp - b.timestamp)
            return {
                id: String(item.id || item.vehicle_id || item.team || 'aircraft'),
                callsign: String(item.callsign || item.name || item.id || 'SIHA'),
                team: item.team || item.team_name || '',
                color: item.color || fallbackColor,
                ownship: Boolean(item.ownship || String(item.id || '').startsWith('bizim')),
                points
            }
        },
        normalizeSample (sample, index = 0) {
            return {
                timestamp: toNumber(sample.timestamp ?? sample.time ?? sample.t ?? index, index),
                latitude: toNumber(sample.latitude ?? sample.lat ?? sample.enlem ?? sample.iha_enlem, NaN),
                longitude: toNumber(
                    sample.longitude ?? sample.lon ?? sample.lng ?? sample.boylam ?? sample.iha_boylam,
                    NaN
                ),
                altitude: toNumber(
                    sample.altitude ?? sample.relative_altitude ?? sample.irtifa ?? sample.iha_irtifa,
                    0
                ),
                speed: toNumber(sample.speed ?? sample.ground_speed ?? sample.hiz ?? sample.iha_hiz, 0),
                heading: toNumber(sample.heading ?? sample.yaw ?? sample.iha_yonelme, 0),
                pitch: toNumber(sample.pitch ?? sample.iha_dikilme, 0),
                roll: toNumber(sample.roll ?? sample.iha_yatis, 0),
                battery: toNumber(sample.battery ?? sample.battery_remaining ?? sample.iha_batarya, 0)
            }
        },
        normalizeMission (raw) {
            const points = (Array.isArray(raw) ? raw : [])
                .map(item => ({
                    sequence: toNumber(item.sequence, 0),
                    latitude: toNumber(item.latitude ?? item.lat, NaN),
                    longitude: toNumber(item.longitude ?? item.lon, NaN),
                    altitude: toNumber(item.altitude, 0),
                    speed: Math.max(0.5, toNumber(item.speed, 10)),
                    type: item.type || 'Waypoint'
                }))
                .filter(point => Number.isFinite(point.latitude) && Number.isFinite(point.longitude))
                .sort((a, b) => a.sequence - b.sequence)

            let timestamp = 0
            for (let index = 0; index < points.length; index++) {
                if (index > 0) {
                    const distance = haversineDistance(points[index - 1], points[index])
                    timestamp += distance / points[index].speed
                }
                points[index].timestamp = timestamp
                if (index + 1 < points.length) {
                    points[index].heading = this.bearingDegrees(points[index], points[index + 1])
                } else {
                    points[index].heading = index > 0 ? points[index - 1].heading : 0
                }
                points[index].pitch = 0
                points[index].roll = 0
            }
            return points
        },
        bearingDegrees (first, second) {
            const lat1 = degToRad(first.latitude)
            const lat2 = degToRad(second.latitude)
            const deltaLon = degToRad(second.longitude - first.longitude)
            const y = Math.sin(deltaLon) * Math.cos(lat2)
            const x = Math.cos(lat1) * Math.sin(lat2) -
                Math.sin(lat1) * Math.cos(lat2) * Math.cos(deltaLon)
            return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360
        },
        configureClock (aircraft) {
            const timestamps = aircraft.flatMap(item => item.points.map(point => point.timestamp))
            const minTime = timestamps.length ? Math.min(...timestamps) : 0
            const maxTime = timestamps.length ? Math.max(...timestamps) : 1
            const previousSeconds = this.playbackSeconds
            const previousMaxSeconds = this.clockMaxSeconds
            const wasAnimating = this.viewer.clock.shouldAnimate
            this.start = JulianDate.now()
            this.stop = JulianDate.addSeconds(this.start, Math.max(1, maxTime - minTime), new JulianDate())
            this.timeOffset = minTime
            this.viewer.clock.startTime = this.start.clone()
            this.viewer.clock.stopTime = this.stop.clone()
            this.viewer.clock.clockRange = ClockRange.CLAMPED
            this.viewer.clock.multiplier = 1
            const wasAtLiveEdge = !Number.isFinite(previousSeconds) ||
                !Number.isFinite(previousMaxSeconds) ||
                previousSeconds >= previousMaxSeconds - 1.5
            const targetSeconds = wasAtLiveEdge
                ? maxTime
                : Math.max(minTime, Math.min(maxTime, previousSeconds))
            this.clockMaxSeconds = maxTime
            this.viewer.clock.currentTime = JulianDate.addSeconds(
                this.start,
                targetSeconds - minTime,
                new JulianDate()
            )
            this.viewer.clock.shouldAnimate = wasAnimating
            this.viewer.timeline.zoomTo(this.start, this.stop)
        },
        drawAircraft (aircraft) {
            if (!aircraft.points.length) {
                return
            }
            const color = Color.fromCssColorString(aircraft.color)
            const sampledPosition = new SampledPositionProperty()
            const sampledOrientation = new SampledProperty(Quaternion)
            const positions = []
            const fixedFrameTransform = Transforms.localFrameToFixedFrameGenerator('north', 'west')

            for (const sample of aircraft.points) {
                const position = Cartesian3.fromDegrees(sample.longitude, sample.latitude, sample.altitude)
                const time = JulianDate.addSeconds(this.start, sample.timestamp - this.timeOffset, new JulianDate())
                positions.push(position)
                sampledPosition.addSample(time, position)
                sampledOrientation.addSample(
                    time,
                    Transforms.headingPitchRollQuaternion(
                        position,
                        new HeadingPitchRoll(
                            degToRad(sample.heading),
                            degToRad(sample.pitch),
                            degToRad(sample.roll)
                        ),
                        undefined,
                        fixedFrameTransform
                    )
                )
            }
            if (aircraft.points.length === 1) {
                const position = positions[0]
                sampledPosition.addSample(this.stop, position)
                sampledOrientation.addSample(
                    this.stop,
                    Transforms.headingPitchRollQuaternion(
                        position,
                        new HeadingPitchRoll(),
                        undefined,
                        fixedFrameTransform
                    )
                )
            }

            if (positions.length > 1) {
                this.addPolyline(positions, color, aircraft.ownship ? 5 : 4)
            }

            const entity = this.viewer.entities.add({
                id: `analysis-aircraft-${aircraft.id}`,
                availability: new TimeIntervalCollection([new TimeInterval({ start: this.start, stop: this.stop })]),
                position: sampledPosition,
                orientation: sampledOrientation,
                model: {
                    uri: require('../assets/plane.glb').default,
                    minimumPixelSize: aircraft.ownship ? 24 : 20,
                    scale: 0.12,
                    color,
                    colorBlendMode: ColorBlendMode.MIX,
                    colorBlendAmount: 0.45
                },
                label: {
                    text: aircraft.callsign,
                    font: 'bold 13px sans-serif',
                    style: LabelStyle.FILL_AND_OUTLINE,
                    fillColor: color,
                    outlineColor: Color.BLACK,
                    outlineWidth: 3,
                    pixelOffset: new Cartesian2(0, -30)
                },
                viewFrom: new Cartesian3(8, 0, 4)
            })
            this.entities.push(entity)
        },
        drawMission () {
            if (!this.missionPoints.length) {
                return
            }
            const color = Color.fromCssColorString(MISSION_COLOR)
            const positions = this.missionPoints.map(point =>
                Cartesian3.fromDegrees(point.longitude, point.latitude, point.altitude)
            )
            if (positions.length > 1) {
                this.addPolyline(positions, color, 6)
            }
            this.missionPoints.forEach((point, index) => {
                const entity = this.viewer.entities.add({
                    id: `mission-waypoint-${point.sequence}-${index}`,
                    position: positions[index],
                    point: new PointGraphics({
                        color,
                        outlineColor: Color.BLACK,
                        outlineWidth: 2,
                        pixelSize: 10
                    }),
                    label: {
                        text: `WP ${point.sequence}\n${point.altitude.toFixed(0)} m`,
                        font: 'bold 12px sans-serif',
                        style: LabelStyle.FILL_AND_OUTLINE,
                        fillColor: color,
                        outlineColor: Color.BLACK,
                        outlineWidth: 3,
                        pixelOffset: new Cartesian2(0, -25)
                    }
                })
                this.entities.push(entity)
            })
        },
        addPolyline (positions, color, width) {
            const primitive = new Primitive({
                geometryInstances: new GeometryInstance({
                    geometry: new PolylineGeometry({ positions, width }),
                    attributes: { color: ColorGeometryInstanceAttribute.fromColor(color) }
                }),
                appearance: new PolylineColorAppearance()
            })
            this.viewer.scene.primitives.add(primitive)
            this.primitives.push(primitive)
        },
        beginSceneUpdate () {
            if (!this.viewer) {
                return 0
            }
            this.viewer.trackedEntity = undefined
            this.entities.forEach(entity => this.viewer.entities.remove(entity))
            this.entities = []
            if (this.primitives.length) {
                this.retiredPrimitives.push(...this.primitives)
            }
            this.primitives = []
            this.primitiveGeneration += 1
            return this.primitiveGeneration
        },
        finishSceneUpdate (generation) {
            if (!this.viewer || generation !== this.primitiveGeneration) {
                return
            }
            const currentPrimitives = [...this.primitives]
            const readyPromises = currentPrimitives
                .map(primitive => primitive && primitive.readyPromise)
                .filter(Boolean)
                .map(promise => Promise.resolve(promise).catch(() => null))
            const removeRetired = () => {
                if (!this.viewer || generation !== this.primitiveGeneration) {
                    return
                }
                this.retiredPrimitives.forEach(primitive => {
                    if (this.viewer.scene.primitives.contains(primitive)) {
                        this.viewer.scene.primitives.remove(primitive)
                    }
                })
                this.retiredPrimitives = []
                this.viewer.scene.requestRender()
            }
            if (readyPromises.length) {
                Promise.all(readyPromises).then(removeRetired)
            } else {
                removeRetired()
            }
        },
        clearScene () {
            if (!this.viewer) {
                return
            }
            this.primitiveGeneration += 1
            this.viewer.trackedEntity = undefined
            this.entities.forEach(entity => this.viewer.entities.remove(entity))
            const allPrimitives = [...this.primitives, ...this.retiredPrimitives]
            allPrimitives.forEach(primitive => {
                if (this.viewer.scene.primitives.contains(primitive)) {
                    this.viewer.scene.primitives.remove(primitive)
                }
            })
            this.entities = []
            this.primitives = []
            this.retiredPrimitives = []
        },
        getAllScenePoints () {
            const points = [...this.missionPoints]
            this.opponents.forEach(opponent => points.push(...opponent.points))
            if (this.ownship) {
                points.push(...this.ownship.points)
            }
            return points.filter(point => Number.isFinite(point.latitude) && Number.isFinite(point.longitude))
        },
        getCameraScenePoints () {
            const points = this.getAllScenePoints()
            if (points.length) {
                return points
            }
            return [
                { latitude: FLIGHT_AREA_BOUNDS.south, longitude: FLIGHT_AREA_BOUNDS.west, altitude: 0 },
                { latitude: FLIGHT_AREA_BOUNDS.north, longitude: FLIGHT_AREA_BOUNDS.east, altitude: 0 }
            ]
        },
        refreshImageryLayers () {
            if (!this.viewer || this.imageryBoundsSignature === 'competition-area') {
                return
            }
            this.imageryBoundsSignature = 'competition-area'
            const layers = this.viewer.scene.imageryLayers
            layers.removeAll()
            layers.addImageryProvider(new SingleTileImageryProvider({
                url: '/analysis-plane.jpg?v=2',
                tileWidth: 2048,
                tileHeight: 2048,
                rectangle: Rectangle.fromDegrees(
                    ANALYSIS_PLANE_BOUNDS.west,
                    ANALYSIS_PLANE_BOUNDS.south,
                    ANALYSIS_PLANE_BOUNDS.east,
                    ANALYSIS_PLANE_BOUNDS.north
                ),
                credit: 'Offline Competition Map'
            }))
        },
        applyCameraMode () {
            this.setCameraMode(this.cameraMode)
        },
        setCameraMode (mode) {
            this.cameraMode = mode
            if (!this.viewer) {
                return
            }
            if (mode === 'follow') {
                this.trackSelectedAircraft()
                return
            }
            this.viewer.trackedEntity = undefined
            if (mode === 'free') {
                this.viewer.scene.requestRender()
                return
            }
            const points = this.getCameraScenePoints().map(point =>
                Cartesian3.fromDegrees(point.longitude, point.latitude, point.altitude)
            )
            if (!points.length) {
                return
            }
            const sphere = BoundingSphere.fromPoints(points)
            sphere.radius = Math.max(sphere.radius * 1.25, 80)
            let offset = new HeadingPitchRange(0, -0.82, sphere.radius * 2.35)
            if (mode === 'top') {
                offset = new HeadingPitchRange(0, -Math.PI / 2, sphere.radius * 2.3)
            } else if (mode === 'side') {
                offset = new HeadingPitchRange(Math.PI / 2, -0.12, sphere.radius * 3.0)
            }
            this.viewer.camera.flyToBoundingSphere(sphere, { duration: 0.9, offset })
        },
        selectOpponent (id) {
            this.selectedOpponentId = id
            if (this.cameraMode === 'follow') {
                this.trackSelectedAircraft()
            }
        },
        trackSelectedAircraft () {
            const id = this.selectedOpponentId
                ? `analysis-aircraft-${this.selectedOpponentId}`
                : (this.ownship ? `analysis-aircraft-${this.ownship.id}` : 'analysis-aircraft-bizim-plan')
            const entity = this.entities.find(item => item.id === id)
            if (entity) {
                this.viewer.trackedEntity = entity
                entity.viewFrom = new Cartesian3(12, 0, 6)
                this.viewer.scene.requestRender()
            }
        },
        updateCurrentSamples () {
            if (!this.viewer || !this.start) {
                return
            }
            const seconds = JulianDate.secondsDifference(this.viewer.clock.currentTime, this.start) + this.timeOffset
            this.playbackSeconds = seconds
            const samples = {}
            this.opponents.forEach(opponent => {
                samples[opponent.id] = this.sampleAtTime(opponent.points, seconds)
            })
            this.currentSamples = samples
        },
        sampleAtTime (points, seconds) {
            if (!points || !points.length) {
                return {}
            }
            let closest = points[0]
            let bestDelta = Math.abs(points[0].timestamp - seconds)
            for (const point of points) {
                const delta = Math.abs(point.timestamp - seconds)
                if (delta < bestDelta) {
                    closest = point
                    bestDelta = delta
                }
            }
            return closest
        },
        calculateConflicts () {
            if (this.missionPoints.length < 2) {
                return []
            }
            const origin = this.missionPoints[0]
            const mission = this.downsample(this.missionPoints).map(point => this.toLocal(point, origin))
            return this.opponents.map(opponent => {
                const route = this.downsample(opponent.points).map(point => this.toLocal(point, origin))
                const closest = this.minimumRouteDistance(mission, route)
                let level = 'safe'
                let label = 'Guvenli'
                if (closest.distance <= 15) {
                    level = 'critical'
                    label = 'Carpisma riski'
                } else if (closest.distance <= 40) {
                    level = 'warning'
                    label = 'Yakin gecis'
                }
                return {
                    id: opponent.id,
                    callsign: opponent.callsign,
                    distance: closest.distance,
                    horizontal: closest.horizontal,
                    vertical: closest.vertical,
                    level,
                    label
                }
            }).sort((a, b) => a.distance - b.distance)
        },
        downsample (points, maximum = 900) {
            if (points.length <= maximum) {
                return points
            }
            const step = Math.ceil(points.length / maximum)
            const result = points.filter((_point, index) => index % step === 0)
            if (result[result.length - 1] !== points[points.length - 1]) {
                result.push(points[points.length - 1])
            }
            return result
        },
        toLocal (point, origin) {
            const latScale = 110540
            const lonScale = 111320 * Math.cos(degToRad(origin.latitude))
            return {
                x: (point.longitude - origin.longitude) * lonScale,
                y: (point.latitude - origin.latitude) * latScale,
                z: point.altitude
            }
        },
        minimumRouteDistance (first, second) {
            if (!second.length) {
                return { distance: Infinity, horizontal: Infinity, vertical: Infinity }
            }
            let best = { distance: Infinity, horizontal: Infinity, vertical: Infinity }
            const firstSegments = first.length > 1 ? first.length - 1 : 1
            const secondSegments = second.length > 1 ? second.length - 1 : 1
            for (let i = 0; i < firstSegments; i++) {
                const a = first[i]
                const b = first[Math.min(i + 1, first.length - 1)]
                for (let j = 0; j < secondSegments; j++) {
                    const c = second[j]
                    const d = second[Math.min(j + 1, second.length - 1)]
                    const candidate = this.segmentDistance(a, b, c, d)
                    if (candidate.distance < best.distance) {
                        best = candidate
                    }
                }
            }
            return best
        },
        segmentDistance (p1, q1, p2, q2) {
            const sub = (a, b) => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z })
            const add = (a, b) => ({ x: a.x + b.x, y: a.y + b.y, z: a.z + b.z })
            const mul = (a, scalar) => ({ x: a.x * scalar, y: a.y * scalar, z: a.z * scalar })
            const dot = (a, b) => a.x * b.x + a.y * b.y + a.z * b.z
            const u = sub(q1, p1)
            const v = sub(q2, p2)
            const w = sub(p1, p2)
            const a = dot(u, u)
            const b = dot(u, v)
            const c = dot(v, v)
            const d = dot(u, w)
            const e = dot(v, w)
            const epsilon = 1e-9
            let sN = 0
            let sD = a * c - b * b
            let tN = 0
            let tD = sD

            if (sD < epsilon) {
                sN = 0
                sD = 1
                tN = e
                tD = c || 1
            } else {
                sN = b * e - c * d
                tN = a * e - b * d
                if (sN < 0) {
                    sN = 0
                    tN = e
                    tD = c || 1
                } else if (sN > sD) {
                    sN = sD
                    tN = e + b
                    tD = c || 1
                }
            }
            if (tN < 0) {
                tN = 0
                if (-d < 0) {
                    sN = 0
                } else if (-d > a) {
                    sN = sD
                } else {
                    sN = -d
                    sD = a || 1
                }
            } else if (tN > tD) {
                tN = tD
                if (-d + b < 0) {
                    sN = 0
                } else if (-d + b > a) {
                    sN = sD
                } else {
                    sN = -d + b
                    sD = a || 1
                }
            }
            const sc = Math.abs(sN) < epsilon ? 0 : sN / sD
            const tc = Math.abs(tN) < epsilon ? 0 : tN / tD
            const firstPoint = add(p1, mul(u, sc))
            const secondPoint = add(p2, mul(v, tc))
            const delta = sub(firstPoint, secondPoint)
            const horizontal = Math.hypot(delta.x, delta.y)
            const vertical = Math.abs(delta.z)
            return { distance: Math.hypot(horizontal, vertical), horizontal, vertical }
        },
        updateSummary () {
            const rivalPoints = this.opponents.reduce((total, item) => total + item.points.length, 0)
            if (!this.opponents.length) {
                this.summary = this.missionPoints.length
                    ? `Mission rotasi hazir (${this.missionPoints.length} waypoint). ` +
                        'Hakem rakip telemetrisi bekleniyor.'
                    : 'Hakem sunucusundan rakip telemetri ve Mission rotasi bekleniyor.'
                return
            }
            this.summary = `${this.opponents.length} rakip SIHA, ${rivalPoints} hakem telemetri noktasi ve ` +
                `${this.missionPoints.length} Mission waypoint analiz ediliyor.`
        },
        formatNumber (value, digits = 1) {
            const number = Number(value)
            return Number.isFinite(number) ? number.toFixed(digits) : '-'
        },
        formatSeconds (value) {
            const number = Number(value)
            return Number.isFinite(number) ? number.toFixed(1) : '-'
        },
        formatDistance (value) {
            const number = Number(value)
            return Number.isFinite(number) ? `${number.toFixed(number < 100 ? 1 : 0)} m` : '-'
        }
    }
}
</script>

<style scoped>
.analysis-page {
    display: flex;
    width: 100%;
    height: 100%;
    min-height: 0;
    overflow: hidden;
    background: #070a0f;
    color: #f7fbff;
}

.analysis-sidebar {
    width: 360px;
    flex: 0 0 360px;
    background: #151e2d;
    border-right: 1px solid #2d3a50;
    padding: 13px 12px;
    overflow-x: hidden;
    overflow-y: auto;
}

.brand-row {
    display: flex;
    align-items: center;
    gap: 9px;
    padding-bottom: 8px;
    border-bottom: 1px solid #2a3548;
}

.brand-row h2 {
    margin: 0;
    font-size: 19px;
    letter-spacing: 0;
}

.source-status {
    display: flex;
    align-items: center;
    gap: 7px;
    margin-top: 10px;
    color: #a9bdd3;
    font-size: 12px;
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #48f2b4;
    box-shadow: 0 0 7px rgba(72, 242, 180, 0.8);
}

.source-status.inactive .status-dot {
    background: #ffd166;
    box-shadow: 0 0 7px rgba(255, 209, 102, 0.65);
}

.summary {
    color: #c3cfdd;
    font-size: 12px;
    line-height: 1.4;
    margin: 8px 0 10px;
}

.section-title {
    color: #8fa6bf;
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
    margin: 10px 0 6px;
}

.control-section,
.mission-card,
.risk-section {
    border-bottom: 1px solid #2a3548;
    padding-bottom: 10px;
}

.control-section {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
}

.control-section label {
    color: #a9bdd3;
    font-weight: 700;
}

select,
button {
    background: #202d41;
    color: #f7fbff;
    border: 1px solid #3a506d;
    border-radius: 4px;
    padding: 7px 9px;
}

select {
    width: 180px;
}

.metric-row {
    display: flex;
    justify-content: space-between;
    padding: 3px 0;
    color: #b9c7d8;
    font-size: 12px;
}

.metric-row strong {
    color: #ffd447;
}

.muted {
    color: #8598ae;
    font-size: 12px;
    margin: 6px 0;
}

.risk-row {
    width: 100%;
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 2px 8px;
    text-align: left;
    margin-bottom: 5px;
    border-left-width: 4px;
}

.risk-row small {
    grid-column: 1 / 3;
    color: #aebed0;
}

.risk-row.safe { border-left-color: #48f2b4; }
.risk-row.warning { border-left-color: #ffd447; }
.risk-row.critical { border-left-color: #ff4f5e; background: #40202a; }

.opponent-list {
    display: flex;
    flex-direction: column;
    gap: 5px;
    margin-bottom: 10px;
}

.opponent-list button {
    display: flex;
    justify-content: space-between;
    align-items: center;
    text-align: left;
    border-left-width: 5px;
}

.opponent-list button.active {
    background: #315f91;
    border-color: #64e9ff;
}

.name { font-weight: 700; }
.meta { color: #c8d2df; font-size: 11px; }

.details {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
}

.details th,
.details td {
    border-bottom: 1px solid #2a3548;
    padding: 5px 3px;
}

.details th {
    color: #9fb1c7;
    text-align: left;
    width: 42%;
}

.viewer-shell {
    position: relative;
    flex: 1;
    min-width: 0;
    min-height: 0;
    height: 100%;
    overflow: hidden;
}

#liveOpponentCesiumContainer {
    position: absolute;
    inset: 0;
    display: flex;
    width: 100%;
    height: 100%;
}

.viewer-badges {
    position: absolute;
    top: 10px;
    left: 10px;
    display: flex;
    gap: 7px;
    pointer-events: none;
}

.viewer-badges span,
.legend {
    background: rgba(8, 14, 23, 0.78);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 4px;
    padding: 6px 9px;
}

.mission-badge,
.mission-legend { color: #ffd447; }
.waiting-badge { color: #ffd166; }
.ownship-legend { color: #ff9d2e; }

.legend {
    position: absolute;
    left: 10px;
    bottom: 34px;
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    pointer-events: none;
    font-size: 12px;
}
</style>

<style>
html,
body,
#app {
    width: 100%;
    height: 100%;
}

#liveOpponentCesiumContainer .cesium-widget,
#liveOpponentCesiumContainer .cesium-widget canvas {
    width: 100% !important;
    height: 100% !important;
}
</style>
