<template>
    <div class="opponent-page">
        <aside class="opponent-sidebar">
            <div class="brand-row">
                <i class="fas fa-crosshairs"></i>
                <h2>Rakip SIHA Analizi</h2>
            </div>

            <div class="button-row">
                <button @click="browseFile">JSON Yukle</button>
                <button @click="loadSample">Ornek Ac</button>
                <input
                    ref="fileInput"
                    accept=".json,application/json"
                    class="hidden-input"
                    type="file"
                    @change="onFileSelected">
            </div>

            <p class="summary">{{ summary }}</p>

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
            <div id="opponentCesiumContainer"></div>
            <div class="legend">
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
    Cartesian3,
    Cartesian2,
    ClockRange,
    Color,
    ColorBlendMode,
    ColorGeometryInstanceAttribute,
    BoundingSphere,
    GeometryInstance,
    HeadingPitchRange,
    HeadingPitchRoll,
    JulianDate,
    LabelStyle,
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
    UrlTemplateImageryProvider,
    Viewer
} from 'cesium'

import 'cesium/Build/Cesium/Widgets/widgets.css'

const LOCAL_MBTILES_URL = '/local-tiles/{z}/{x}/{y}.png?v=offline3'
const LOCAL_MBTILES_CREDIT = 'Offline MBTiles'
const LOCAL_MBTILES_MIN_LEVEL = 13
const LOCAL_MBTILES_MAX_LEVEL = 19
const COLORS = ['#35c7ff', '#ff4f81', '#9cff57', '#ffd447', '#b980ff', '#ff6b35', '#48f2b4']

function toNumber (value, fallback = 0) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : fallback
}

function degToRad (value) {
    return toNumber(value) * Math.PI / 180
}

export default {
    name: 'OpponentCesiumViewer',
    data () {
        return {
            viewer: null,
            opponents: [],
            selectedOpponentId: null,
            currentSamples: {},
            summary: 'Rakip SIHA JSON dosyasi yukleyin veya ornek veriyi acin.',
            entities: [],
            primitives: [],
            cameraMode: 'free'
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
            return this.currentSamples[this.selectedOpponent.id] || this.selectedOpponent.points[0] || {}
        }
    },
    mounted () {
        this.createViewer()
        window.addEventListener('resize', this.resizeViewer)
        this.$nextTick(() => {
            setTimeout(this.resizeViewer, 150)
        })
        this.loadSample()
    },
    beforeDestroy () {
        window.removeEventListener('resize', this.resizeViewer)
        if (this.viewer) {
            this.viewer.clock.onTick.removeEventListener(this.updateCurrentSamples)
            this.viewer.destroy()
            this.viewer = null
        }
    },
    methods: {
        createViewer () {
            const imageryProvider = new UrlTemplateImageryProvider({
                url: LOCAL_MBTILES_URL,
                rectangle: this.getLocalImageryRectangle(),
                minimumLevel: LOCAL_MBTILES_MIN_LEVEL,
                maximumLevel: LOCAL_MBTILES_MAX_LEVEL,
                credit: LOCAL_MBTILES_CREDIT
            })

            this.viewer = new Viewer('opponentCesiumContainer', {
                homeButton: false,
                timeline: true,
                animation: true,
                requestRenderMode: true,
                maximumRenderTimeChange: 0.25,
                shouldAnimate: false,
                scene3DOnly: false,
                selectionIndicator: false,
                shadows: false,
                orderIndependentTranslucency: false,
                baseLayerPicker: false,
                imageryProvider,
                geocoder: false,
                useBrowserRecommendedResolution: true
            })

            this.viewer.scene.globe.depthTestAgainstTerrain = true
            this.viewer.scene.fog.enabled = false
            this.viewer.scene.sun.show = false
            this.viewer.scene.globe.baseColor = Color.fromCssColorString('#364e3a')
            this.viewer.scene.moon.show = false
            this.viewer.scene.skyAtmosphere.show = false
            this.viewer.scene.skyBox.show = false
            this.viewer.scene.screenSpaceCameraController.enableCollisionDetection = false
            this.viewer.clock.onTick.addEventListener(this.updateCurrentSamples)
            this.addCameraButtons()
            this.resizeViewer()
        },
        resizeViewer () {
            if (!this.viewer || this.viewer.isDestroyed()) {
                return
            }
            this.viewer.resize()
            this.viewer.scene.requestRender()
        },
        refreshImageryLayers () {
            if (!this.viewer || this.viewer.isDestroyed()) {
                return
            }
            const hasTelemetry = this.getAllTelemetryPoints().length > 0
            const layers = this.viewer.scene.imageryLayers
            layers.removeAll()
            const imageryProvider = new UrlTemplateImageryProvider({
                url: LOCAL_MBTILES_URL,
                rectangle: this.getLocalImageryRectangle(),
                minimumLevel: LOCAL_MBTILES_MIN_LEVEL,
                maximumLevel: LOCAL_MBTILES_MAX_LEVEL,
                credit: LOCAL_MBTILES_CREDIT
            })
            layers.addImageryProvider(imageryProvider)
            if (hasTelemetry) {
                this.addLocalBackdropImagery()
                this.addLocalMosaicImagery()
            }
            this.resizeViewer()
        },
        getLocalImageryRectangle () {
            const bounds = this.getLocalImageryBounds()
            return Rectangle.fromDegrees(bounds.west, bounds.south, bounds.east, bounds.north)
        },
        getAllTelemetryPoints () {
            return this.opponents
                .flatMap(opponent => opponent.points || [])
                .filter(point => Number.isFinite(point.longitude) && Number.isFinite(point.latitude))
        },
        getLocalImageryBounds () {
            const points = this.getAllTelemetryPoints()
            if (points.length === 0) {
                return { west: 25.0, south: 35.0, east: 45.0, north: 43.5 }
            }

            const lons = points.map(point => point.longitude)
            const lats = points.map(point => point.latitude)
            const minLon = Math.min(...lons)
            const maxLon = Math.max(...lons)
            const minLat = Math.min(...lats)
            const maxLat = Math.max(...lats)
            const padding = 0.02
            return {
                west: minLon - padding,
                south: minLat - padding,
                east: maxLon + padding,
                north: maxLat + padding
            }
        },
        getBackdropImageryBounds () {
            const bounds = this.getLocalImageryBounds()
            const lonSpan = bounds.east - bounds.west
            const latSpan = bounds.north - bounds.south
            const targetLonSpan = Math.min(1.2, Math.max(lonSpan * 12, 0.28))
            const targetLatSpan = Math.min(1.2, Math.max(latSpan * 12, 0.28))
            const centerLon = (bounds.west + bounds.east) / 2
            const centerLat = (bounds.south + bounds.north) / 2

            return {
                west: Math.max(-180, centerLon - targetLonSpan / 2),
                south: Math.max(-85, centerLat - targetLatSpan / 2),
                east: Math.min(180, centerLon + targetLonSpan / 2),
                north: Math.min(85, centerLat + targetLatSpan / 2)
            }
        },
        addLocalBackdropImagery () {
            const bounds = this.getBackdropImageryBounds()
            const query = new URLSearchParams({
                west: bounds.west.toString(),
                south: bounds.south.toString(),
                east: bounds.east.toString(),
                north: bounds.north.toString(),
                z: '14',
                v: 'offline-backdrop-opponents-1'
            }).toString()
            const provider = new SingleTileImageryProvider({
                url: `/local-backdrop.png?${query}`,
                tileWidth: 2048,
                tileHeight: 2048,
                rectangle: Rectangle.fromDegrees(bounds.west, bounds.south, bounds.east, bounds.north),
                credit: 'Offline MBTiles Backdrop'
            })
            this.localBackdropLayer = this.viewer.scene.imageryLayers.addImageryProvider(provider, 0)
        },
        addLocalMosaicImagery () {
            const bounds = this.getLocalImageryBounds()
            const query = new URLSearchParams({
                west: bounds.west.toString(),
                south: bounds.south.toString(),
                east: bounds.east.toString(),
                north: bounds.north.toString(),
                z: '17',
                v: 'offline-mosaic-opponents-1'
            }).toString()
            const provider = new SingleTileImageryProvider({
                url: `/local-mosaic.png?${query}`,
                tileWidth: 4096,
                tileHeight: 4096,
                rectangle: Rectangle.fromDegrees(bounds.west, bounds.south, bounds.east, bounds.north),
                credit: 'Offline MBTiles Mosaic'
            })
            this.localMosaicLayer = this.viewer.scene.imageryLayers.addImageryProvider(provider)
        },
        browseFile () {
            this.$refs.fileInput.click()
        },
        onFileSelected (event) {
            const file = event.target.files && event.target.files[0]
            if (!file) {
                return
            }
            const reader = new FileReader()
            reader.onload = () => {
                try {
                    this.loadPayload(JSON.parse(reader.result), file.name)
                } catch (error) {
                    this.summary = `Dosya okunamadi: ${error.message || error}`
                }
            }
            reader.readAsText(file, 'utf-8')
        },
        async loadSample () {
            try {
                const response = await fetch('/opponent-telemetry/sample?v=1')
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`)
                }
                this.loadPayload(await response.json(), 'sample_opponent_telemetry.json')
            } catch (error) {
                this.summary = `Ornek veri yuklenemedi: ${error.message || error}`
            }
        },
        loadPayload (payload, sourceName = '') {
            const opponents = this.normalizeOpponents(payload)
            this.clearScene()
            this.opponents = opponents
            this.selectedOpponentId = opponents[0] ? opponents[0].id : null
            this.currentSamples = {}
            this.refreshImageryLayers()

            if (opponents.length === 0) {
                this.summary = 'Gecerli rakip telemetri noktasi bulunamadi.'
                return
            }

            this.configureClock(opponents)
            this.drawOpponents(opponents)
            this.zoomToOpponents()
            const pointCount = opponents.reduce((total, opponent) => total + opponent.points.length, 0)
            const suffix = sourceName ? ` (${sourceName})` : ''
            this.summary = `${opponents.length} rakip SIHA, ${pointCount} telemetri noktasi yuklendi${suffix}.`
        },
        normalizeOpponents (payload) {
            const raw = Array.isArray(payload)
                ? payload
                : (
                    payload.opponents ||
                    payload.rakipler ||
                    payload.aircraft ||
                    payload.vehicles ||
                    payload.data ||
                    []
                )

            return raw
                .map((item, index) => {
                    const telemetry = item.telemetry || item.samples || item.positions || item.track || []
                    const points = telemetry
                        .map(sample => this.normalizeSample(sample))
                        .filter(sample => Number.isFinite(sample.latitude) && Number.isFinite(sample.longitude))
                        .sort((a, b) => a.timestamp - b.timestamp)

                    return {
                        id: String(item.id || item.vehicle_id || `rakip-${index + 1}`),
                        callsign: String(item.callsign || item.name || `Rakip SIHA ${index + 1}`),
                        team: item.team || item.team_name || '',
                        color: item.color || COLORS[index % COLORS.length],
                        points
                    }
                })
                .filter(opponent => opponent.points.length > 0)
        },
        normalizeSample (sample) {
            return {
                timestamp: toNumber(sample.timestamp ?? sample.time ?? sample.t, 0),
                latitude: toNumber(sample.latitude ?? sample.lat ?? sample.enlem, NaN),
                longitude: toNumber(sample.longitude ?? sample.lon ?? sample.lng ?? sample.boylam, NaN),
                altitude: toNumber(sample.altitude ?? sample.relative_altitude ?? sample.irtifa, 0),
                speed: toNumber(sample.speed ?? sample.ground_speed ?? sample.hiz, 0),
                heading: toNumber(sample.heading ?? sample.yaw, 0),
                pitch: toNumber(sample.pitch, 0),
                roll: toNumber(sample.roll, 0),
                battery: toNumber(sample.battery ?? sample.battery_remaining, 0)
            }
        },
        configureClock (opponents) {
            const timestamps = opponents.flatMap(opponent => opponent.points.map(point => point.timestamp))
            const minTime = Math.min(...timestamps)
            const maxTime = Math.max(...timestamps)
            this.start = JulianDate.now()
            this.stop = JulianDate.addSeconds(this.start, Math.max(1, maxTime - minTime), new JulianDate())
            this.timeOffset = minTime

            this.viewer.clock.startTime = this.start.clone()
            this.viewer.clock.stopTime = this.stop.clone()
            this.viewer.clock.currentTime = this.start.clone()
            this.viewer.clock.clockRange = ClockRange.LOOP_STOP
            this.viewer.clock.multiplier = 1
            this.viewer.timeline.zoomTo(this.start, this.stop)
        },
        drawOpponents (opponents) {
            for (const opponent of opponents) {
                this.drawOpponent(opponent)
            }
            this.updateCurrentSamples()
            this.viewer.scene.requestRender()
        },
        drawOpponent (opponent) {
            const color = Color.fromCssColorString(opponent.color)
            const sampledPosition = new SampledPositionProperty()
            const sampledOrientation = new SampledProperty(Quaternion)
            const positions = []
            const fixedFrameTransform = Transforms.localFrameToFixedFrameGenerator('north', 'west')

            for (const sample of opponent.points) {
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

            if (positions.length > 1) {
                const primitive = new Primitive({
                    geometryInstances: new GeometryInstance({
                        geometry: new PolylineGeometry({
                            positions,
                            width: 4.0
                        }),
                        attributes: {
                            color: ColorGeometryInstanceAttribute.fromColor(color)
                        }
                    }),
                    appearance: new PolylineColorAppearance()
                })
                this.viewer.scene.primitives.add(primitive)
                this.primitives.push(primitive)
            }

            const entity = this.viewer.entities.add({
                id: `opponent-${opponent.id}`,
                availability: new TimeIntervalCollection([new TimeInterval({
                    start: this.start,
                    stop: this.stop
                })]),
                position: sampledPosition,
                orientation: sampledOrientation,
                model: {
                    uri: require('../assets/plane.glb').default,
                    minimumPixelSize: 18,
                    scale: 0.1,
                    color,
                    colorBlendMode: ColorBlendMode.MIX,
                    colorBlendAmount: 0.45
                },
                label: {
                    text: opponent.callsign,
                    font: '13px sans-serif',
                    style: LabelStyle.FILL_AND_OUTLINE,
                    fillColor: color,
                    outlineColor: Color.BLACK,
                    outlineWidth: 3,
                    pixelOffset: new Cartesian2(0, -28)
                },
                viewFrom: new Cartesian3(5, 0, 3)
            })
            this.entities.push(entity)
        },
        clearScene () {
            if (!this.viewer) {
                return
            }
            for (const entity of this.entities) {
                this.viewer.entities.remove(entity)
            }
            for (const primitive of this.primitives) {
                this.viewer.scene.primitives.remove(primitive)
            }
            this.entities = []
            this.primitives = []
        },
        zoomToOpponents () {
            if (this.entities.length === 0) {
                return
            }
            this.resizeViewer()
            setTimeout(() => {
                this.resizeViewer()
                this.fitOpponentBounds()
            }, 200)
        },
        selectOpponent (id) {
            this.selectedOpponentId = id
            if (this.cameraMode === 'follow') {
                this.trackSelectedOpponent()
            }
        },
        addCameraButtons () {
            this.$nextTick(() => {
                const toolbar = document.getElementsByClassName('cesium-viewer-toolbar')[0]
                if (!toolbar || document.getElementById('opponent-fit-button')) {
                    return
                }
                toolbar.append(this.createToolbarButton(
                    'opponent-fit-button',
                    'Rotayi ekrana sigdir',
                    '<path d="M11 17V9h8M29 17V9h-8M11 23v8h8M29 23v8h-8" fill="none" ' +
                    'stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>',
                    () => {
                        this.cameraMode = 'free'
                        this.viewer.trackedEntity = undefined
                        this.fitOpponentBounds()
                    }
                ))
                toolbar.append(this.createToolbarButton(
                    'opponent-follow-button',
                    'Secili rakip SIHA takip',
                    '<path d="M10 22l3-8h14l3 8v7H10z" fill="currentColor"/>' +
                    '<path d="M14 14l-2 6h16l-2-6z" fill="#303336"/>' +
                    '<circle cx="15" cy="29" r="3" fill="#303336"/>' +
                    '<circle cx="25" cy="29" r="3" fill="#303336"/>',
                    () => {
                        this.cameraMode = 'follow'
                        this.trackSelectedOpponent()
                    }
                ))
                toolbar.append(this.createToolbarButton(
                    'opponent-free-button',
                    'Serbest kamera',
                    '<path d="M12 26h16M20 12v16M14 18l6-6 6 6" fill="none" ' +
                    'stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>',
                    () => {
                        this.cameraMode = 'free'
                        this.viewer.trackedEntity = undefined
                        this.viewer.scene.requestRender()
                    }
                ))
            })
        },
        createToolbarButton (id, title, svgPath, onClick) {
            const wrapper = document.createElement('span')
            wrapper.className = 'cesium-navigationHelpButton-wrapper'
            wrapper.innerHTML = '' +
                '<button type="button" ' +
                `id="${id}" ` +
                'class="cesium-button cesium-toolbar-button" ' +
                `title="${title}">` +
                '<svg viewBox="0 0 40 40" aria-hidden="true">' +
                svgPath +
                '</svg>' +
                '</button>'
            wrapper.querySelector('button').addEventListener('click', onClick)
            return wrapper
        },
        fitOpponentBounds () {
            if (!this.viewer || this.entities.length === 0) {
                return
            }
            const positions = this.getAllTelemetryPoints()
                .filter(point => Number.isFinite(point.longitude) &&
                    Number.isFinite(point.latitude) &&
                    Number.isFinite(point.altitude))
                .map(point => Cartesian3.fromDegrees(point.longitude, point.latitude, point.altitude))

            if (positions.length === 0) {
                this.viewer.flyTo(this.entities)
                return
            }
            const sphere = BoundingSphere.fromPoints(positions)
            sphere.radius = Math.max(sphere.radius * 1.7, 80)
            this.viewer.camera.flyToBoundingSphere(sphere, {
                duration: 1.2,
                offset: new HeadingPitchRange(0, -0.55, sphere.radius * 2.7)
            })
        },
        trackSelectedOpponent () {
            const entity = this.entities.find(item => item.id === `opponent-${this.selectedOpponentId}`)
            if (entity) {
                this.viewer.trackedEntity = entity
                this.viewer.flyTo(entity, { offset: new HeadingPitchRange(0, -0.45, 120) })
            }
        },
        updateCurrentSamples () {
            if (!this.viewer || !this.start) {
                return
            }
            const seconds = JulianDate.secondsDifference(this.viewer.clock.currentTime, this.start) + this.timeOffset
            const samples = {}
            for (const opponent of this.opponents) {
                samples[opponent.id] = this.sampleAtTime(opponent.points, seconds)
            }
            this.currentSamples = samples
        },
        sampleAtTime (points, seconds) {
            if (!points || points.length === 0) {
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
        formatNumber (value, digits = 1) {
            const number = Number(value)
            return Number.isFinite(number) ? number.toFixed(digits) : '-'
        },
        formatSeconds (value) {
            const number = Number(value)
            return Number.isFinite(number) ? number.toFixed(1) : '-'
        }
    }
}
</script>

<style scoped>
.opponent-page {
    display: flex;
    width: 100%;
    height: 100%;
    min-height: 0;
    overflow: hidden;
    background: #070a0f;
    color: #f7fbff;
}

.opponent-sidebar {
    width: 385px;
    flex: 0 0 385px;
    background: linear-gradient(180deg, #202b42 0%, #121a29 100%);
    border-right: 1px solid #2d3a50;
    padding: 14px 12px;
    overflow: auto;
}

.brand-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
}

.brand-row h2 {
    font-size: 21px;
    margin: 0;
}

.button-row {
    display: flex;
    gap: 8px;
    margin-bottom: 10px;
}

button {
    background: #23324a;
    color: #ffffff;
    border: 1px solid #3b587f;
    border-radius: 5px;
    padding: 7px 11px;
    cursor: pointer;
}

button:hover {
    background: #31517b;
}

.hidden-input {
    display: none;
}

.summary {
    color: #aeb8c7;
    font-size: 13px;
    line-height: 1.35;
    margin: 8px 0 12px;
}

.opponent-list {
    display: flex;
    flex-direction: column;
    gap: 7px;
    margin-bottom: 12px;
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

.name {
    font-weight: 700;
}

.meta {
    color: #c8d2df;
    font-size: 12px;
}

.details {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

.details th,
.details td {
    border-bottom: 1px solid #2a3548;
    padding: 6px 4px;
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

#opponentCesiumContainer {
    position: absolute;
    inset: 0;
    display: flex;
    width: 100%;
    height: 100%;
}

.legend {
    position: absolute;
    left: 14px;
    bottom: 34px;
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    padding: 8px 10px;
    background: rgba(10, 15, 24, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 6px;
    pointer-events: none;
}
</style>

<style>
html,
body,
#app {
    width: 100%;
    height: 100%;
}

#opponentCesiumContainer .cesium-widget,
#opponentCesiumContainer .cesium-widget canvas {
    width: 100% !important;
    height: 100% !important;
}
</style>
