<template>
  <div class="relative w-full h-full">
    <!-- Leaflet map container -->
    <div ref="mapEl" class="w-full h-full rounded-lg" />

    <!-- Map toolbar overlay -->
    <div
      class="absolute top-3 right-3 z-[1000] flex flex-col gap-1.5 p-1.5 bg-background/80 backdrop-blur-md border border-border/50 shadow-xl rounded-2xl"
    >
      <!-- Mode pill -->
      <div
        class="flex items-center justify-center px-2 py-0.5 rounded-md text-[9px] font-bold uppercase tracking-widest transition-[background-color,color] duration-150"
        :class="
          store.appMode === 'mapping'
            ? 'bg-amber-500/20 text-amber-400'
            : 'bg-primary/20 text-primary'
        "
      >
        {{ store.appMode === "mapping" ? "MAPPING" : "NAV" }}
      </div>

      <!-- Pan/View — always first, stagger 0ms -->
      <button
        class="toolbar-btn group"
        style="animation-delay: 0ms"
        :class="{
          'bg-secondary text-foreground shadow-inner': mapMode === 'view',
          'text-muted-foreground': mapMode !== 'view',
        }"
        @click="setMode('view')"
      >
        <Hand :size="18" :stroke-width="2.5" />
        <span class="toolbar-tooltip">Pan / View</span>
      </button>

      <!-- ── Navigation mode only ── -->
      <template v-if="store.appMode === 'navigation'">
        <button
          class="toolbar-btn group"
          style="animation-delay: 40ms"
          :class="
            store.isBusy
              ? 'text-muted-foreground/40 cursor-not-allowed'
              : mapMode === 'navigate'
                ? 'bg-primary text-primary-foreground shadow-md shadow-primary/20'
                : 'text-muted-foreground'
          "
          @click="store.isBusy ? null : setMode('navigate')"
          :disabled="store.isBusy"
        >
          <Navigation :size="18" :stroke-width="2.5" />
          <span class="toolbar-tooltip">{{ store.isBusy ? "Robot BUSY" : "Navigate" }}</span>
        </button>

        <button
          class="toolbar-btn group"
          style="animation-delay: 80ms"
          :class="{
            'bg-violet-600 text-white shadow-md shadow-violet-600/20': mapMode === 'waypoint',
            'text-muted-foreground': mapMode !== 'waypoint',
          }"
          @click="setMode('waypoint')"
        >
          <MapPin :size="18" :stroke-width="2.5" />
          <span class="toolbar-tooltip">Add Waypoint</span>
        </button>

        <button
          class="toolbar-btn group"
          style="animation-delay: 120ms"
          :class="{
            'bg-emerald-600 text-white shadow-md shadow-emerald-600/20': mapMode === 'destination',
            'text-muted-foreground': mapMode !== 'destination',
          }"
          @click="setMode('destination')"
        >
          <Flag :size="18" :stroke-width="2.5" />
          <span class="toolbar-tooltip">Add Destination</span>
        </button>

        <button
          class="toolbar-btn group"
          style="animation-delay: 160ms"
          :class="{
            'bg-amber-600 text-white shadow-md shadow-amber-600/20': mapMode === 'dock_placement',
            'text-muted-foreground': mapMode !== 'dock_placement',
          }"
          @click="setMode('dock_placement')"
        >
          <Anchor :size="18" :stroke-width="2.5" />
          <span class="toolbar-tooltip">Place Dock</span>
        </button>
      </template>

      <!-- ── Mapping mode only ── -->
      <template v-if="store.appMode === 'mapping'">
        <button
          class="toolbar-btn group"
          style="animation-delay: 40ms"
          :class="{
            'bg-amber-500 text-white shadow-md shadow-amber-500/20': mapMode === 'keepout',
            'text-muted-foreground': mapMode !== 'keepout',
          }"
          @click="setMode('keepout')"
        >
          <ShieldAlert :size="18" :stroke-width="2.5" />
          <span class="toolbar-tooltip">Keepout Zone</span>
        </button>
      </template>

      <!-- ── Selalu tampil di kedua mode ── -->
      <button
        class="toolbar-btn group"
        :class="{
          'bg-emerald-500 text-white shadow-md shadow-emerald-500/20': mapMode === 'initial_pose',
          'text-muted-foreground': mapMode !== 'initial_pose',
        }"
        @click="setMode('initial_pose')"
      >
        <Crosshair :size="18" :stroke-width="2.5" />
        <span class="toolbar-tooltip">Init Pose (AMCL)</span>
      </button>

      <div class="h-px bg-border/50 mx-2 my-0.5"></div>

      <button
        class="toolbar-btn group"
        :class="{
          'bg-cyan-600 text-white shadow-md shadow-cyan-600/20': store.showCostmap,
          'text-muted-foreground': !store.showCostmap,
        }"
        @click="store.toggleCostmap()"
      >
        <Layers :size="18" :stroke-width="2.5" />
        <span class="toolbar-tooltip">Toggle Costmap</span>
      </button>

      <button
        class="toolbar-btn group"
        :class="{
          'bg-blue-600 text-white shadow-md shadow-blue-600/20': store.showRobot,
          'text-muted-foreground': !store.showRobot,
        }"
        @click="store.toggleRobotVisibility()"
      >
        <Bot :size="18" :stroke-width="2.5" />
        <span class="toolbar-tooltip">Toggle Robot</span>
      </button>

      <button
        class="toolbar-btn group"
        :class="{
          'bg-blue-600 text-white shadow-md shadow-blue-600/20': showCamera,
          'text-muted-foreground': !showCamera,
        }"
        @click="showCamera = !showCamera"
      >
        <Camera :size="18" :stroke-width="2.5" />
        <span class="toolbar-tooltip">Toggle Camera</span>
      </button>
    </div>

    <!-- ── Floating Camera Feed ─────────────────────────────────────────── -->
    <transition name="fade">
      <div
        v-if="showCamera"
        class="absolute bottom-6 right-16 z-[1000] w-80 aspect-video bg-black rounded-xl border border-border/50 shadow-2xl overflow-hidden group flex items-center justify-center cursor-move select-none"
        :style="{ transform: `translate(${cameraOffset.x}px, ${cameraOffset.y}px)` }"
        @mousedown="startCameraDrag"
      >
        <img
          v-if="!cameraError"
          :src="cameraStreamSrc"
          class="w-full h-full object-cover transition-opacity duration-300 pointer-events-none"
          :class="{ 'opacity-30': cameraLoading }"
          @load="clearTimeout(_cameraLoadTimer); cameraLoading = false; cameraError = false;"
          @error="clearTimeout(_cameraLoadTimer); cameraLoading = false; cameraError = true;"
        />

        <!-- Drag handle indicator (visual only) -->
        <div
          class="absolute top-2 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"
        >
          <div class="w-8 h-1 rounded-full bg-white/20"></div>
        </div>

        <!-- Overlay controls -->
        <div
          class="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-2"
        >
          <div class="flex items-center justify-between gap-2">
            <span
              class="text-[10px] font-semibold text-white/80 uppercase tracking-widest bg-black/40 px-2 py-0.5 rounded backdrop-blur-sm"
              >Robot Camera</span
            >
            <button
              @click="retryCamera"
              class="p-1 hover:bg-white/20 rounded transition-colors text-white"
              title="Retry Stream"
            >
              <RotateCcw :size="12" />
            </button>
          </div>
        </div>

        <!-- States -->
        <div
          v-if="cameraError"
          class="absolute inset-0 flex flex-col items-center justify-center gap-2 p-4 text-center"
        >
          <div
            class="w-8 h-8 rounded-full bg-destructive/10 flex items-center justify-center text-destructive mb-1"
          >
            <Camera :size="16" />
          </div>
          <span class="text-xs text-muted-foreground font-medium"
            >Camera stream unavailable</span
          >
          <button
            @click="retryCamera"
            class="px-3 py-1 text-[10px] font-bold uppercase tracking-wider bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 transition-colors"
          >
            Retry
          </button>
        </div>

        <div
          v-else-if="cameraLoading"
          class="absolute inset-0 flex flex-col items-center justify-center gap-2"
        >
          <span
            class="w-4 h-4 rounded-full border-2 border-primary/30 border-t-primary animate-spin"
          />
          <span
            class="text-[10px] text-muted-foreground font-mono uppercase tracking-widest animate-pulse"
            >Connecting</span
          >
        </div>
      </div>
    </transition>

    <!-- Mode indicator -->
    <transition name="mode-bar">
    <div
      v-if="mapMode !== 'view'"
      class="absolute bottom-6 left-1/2 -translate-x-1/2 z-[1000] flex items-center h-10 px-5 rounded-full bg-background/80 backdrop-blur-md border border-border/50 shadow-lg text-sm text-foreground font-medium"
    >
      <div v-if="mapMode === 'navigate'" class="flex items-center gap-2">
        <Navigation :size="16" class="text-primary" />
        <span
          >Click &amp; drag to navigate with heading, or click to navigate</span
        >
      </div>
      <div v-if="mapMode === 'destination'" class="flex items-center gap-2">
        <Flag :size="16" class="text-emerald-500" />
        <span
          >Click &amp; drag to add destination with yaw, or click for
          yaw=0</span
        >
      </div>
      <div v-if="mapMode === 'waypoint'" class="flex items-center gap-2">
        <MapPin :size="16" class="text-violet-500" />
        <span>Click map to add waypoint</span>
      </div>
      <div v-if="mapMode === 'keepout'" class="flex items-center gap-3">
        <div class="flex items-center gap-2 mr-2">
          <ShieldAlert :size="16" class="text-amber-500" />
          <span>Click to draw keepout polygon</span>
        </div>
        <button
          class="px-3 py-1 text-xs font-semibold rounded-md bg-amber-500/20 text-amber-500 hover:bg-amber-500/30 transition-colors"
          @click="finishKeepout"
        >
          Finish
        </button>
        <button
          class="px-3 py-1 text-xs font-semibold rounded-md bg-destructive/10 text-destructive hover:bg-destructive/20 transition-colors"
          @click="cancelKeepout"
        >
          Cancel
        </button>
      </div>
      <div v-if="mapMode === 'initial_pose'" class="flex items-center gap-2">
        <Crosshair :size="16" class="text-emerald-500" />
        <span>Click &amp; drag to set robot pose and orientation</span>
      </div>
      <div
        v-if="mapMode === 'dock_placement' && dockStep === 0"
        class="flex items-center gap-2"
      >
        <Anchor :size="16" class="text-amber-500" />
        <span>Click &amp; drag to set dock position and direction</span>
      </div>
      <div
        v-if="mapMode === 'dock_placement' && dockStep === 1"
        class="flex items-center gap-3"
      >
        <div class="flex items-center gap-2 mr-2">
          <Anchor :size="16" class="text-amber-500" />
          <span>Click to place approach point (same direction)</span>
        </div>
        <button
          class="px-3 py-1 text-xs font-semibold rounded-md bg-secondary text-secondary-foreground hover:bg-secondary/80 transition-colors"
          @click="skipApproach"
        >
          Skip
        </button>
        <button
          class="px-3 py-1 text-xs font-semibold rounded-md bg-destructive/10 text-destructive hover:bg-destructive/20 transition-colors"
          @click="cancelDockPlacement"
        >
          Cancel
        </button>
      </div>
    </div>
    </transition>

    <!-- No map placeholder -->
    <transition name="fade">
      <div
        v-if="!store.hasMap"
        class="absolute inset-0 flex items-center justify-center rounded-lg z-[500] pointer-events-none"
        style="
          background: radial-gradient(
            ellipse at center,
            rgba(9, 9, 11, 0.85) 0%,
            rgba(9, 9, 11, 0.97) 100%
          );
          backdrop-filter: blur(2px);
        "
      >
        <div class="flex flex-col items-center gap-5">
          <!-- Animated ring + icon -->
          <div class="relative flex items-center justify-center w-20 h-20">
            <!-- Outer pulse ring -->
            <div
              class="absolute inset-0 rounded-full border-2 border-blue-500/30 animate-ping"
              style="animation-duration: 2s"
            ></div>
            <!-- Mid ring -->
            <div
              class="absolute inset-2 rounded-full border border-blue-400/20"
            ></div>
            <!-- Spinning arc -->
            <svg
              class="absolute inset-0 w-full h-full animate-spin"
              style="animation-duration: 3s"
              viewBox="0 0 80 80"
            >
              <circle
                cx="40"
                cy="40"
                r="36"
                fill="none"
                stroke="#3b82f6"
                stroke-width="2"
                stroke-dasharray="60 165"
                stroke-linecap="round"
              />
            </svg>
            <!-- Center icon -->
            <div
              class="w-10 h-10 rounded-full bg-blue-500/10 border border-blue-500/30 flex items-center justify-center"
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#60a5fa"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21" />
                <line x1="9" y1="3" x2="9" y2="18" />
                <line x1="15" y1="6" x2="15" y2="21" />
              </svg>
            </div>
          </div>

          <!-- Text -->
          <div class="flex flex-col items-center gap-1.5">
            <p class="text-sm font-semibold text-slate-200 tracking-wide">
              Waiting for map data
            </p>
            <p class="text-xs text-slate-500 font-mono">
              Subscribing to <span class="text-blue-400/80">/map</span> topic
            </p>
          </div>

          <!-- Dots loader -->
          <div class="flex items-center gap-1.5">
            <div
              class="w-1.5 h-1.5 rounded-full bg-blue-400/60 animate-bounce"
              style="animation-delay: 0ms; animation-duration: 1.2s"
            ></div>
            <div
              class="w-1.5 h-1.5 rounded-full bg-blue-400/60 animate-bounce"
              style="animation-delay: 200ms; animation-duration: 1.2s"
            ></div>
            <div
              class="w-1.5 h-1.5 rounded-full bg-blue-400/60 animate-bounce"
              style="animation-delay: 400ms; animation-duration: 1.2s"
            ></div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import {
  ref,
  watch,
  onMounted,
  onUnmounted,
  shallowRef,
  defineEmits,
} from "vue";
import L from "leaflet";
import { useRobotStore } from "@/stores/robot";
import { useROS } from "@/composables/useROS";
import { useAPI } from "@/composables/useAPI";
import { useMapMode } from "@/composables/useMapMode";
import {
  Navigation,
  MapPin,
  ShieldAlert,
  Crosshair,
  Flag,
  Anchor,
  Layers,
  Hand,
  Camera,
  RotateCcw,
  Maximize2,
  Bot,
} from "lucide-vue-next";
import { toast } from "vue-sonner";
import { computed } from "vue";

const emit = defineEmits(["destinationClick", "dockPlaced"]);

const store = useRobotStore();
const ros = useROS();
const api = useAPI();
const { mapMode, setMode: _setModeShared } = useMapMode();

const mapEl = ref(null);

// ── Camera state ─────────────────────────────────────────────────────────────
const showCamera = ref(false);
const cameraError = ref(false);
const cameraLoading = ref(false);
const cameraRetryKey = ref(0);

const baseCameraUrl = computed(() => {
  try {
    // rosUrl can be "ws://host:8765" or "host:8765" or just "host"
    const raw = store.rosUrl || "";
    const withProto = raw.startsWith("ws://") || raw.startsWith("wss://")
      ? raw
      : `ws://${raw}`;
    const host = new URL(withProto).hostname || "localhost";
    return `http://${host}:8080/stream?topic=/camera/image_raw`;
  } catch {
    return "http://localhost:8080/stream?topic=/camera/image_raw";
  }
});

const cameraStreamSrc = computed(() => {
  const sep = baseCameraUrl.value.includes("?") ? "&" : "?";
  return cameraRetryKey.value === 0
    ? baseCameraUrl.value
    : `${baseCameraUrl.value}${sep}_r=${cameraRetryKey.value}`;
});

function retryCamera() {
  cameraError.value = false;
  cameraLoading.value = true;
  cameraRetryKey.value = Date.now();
}

// ── Camera Dragging ──────────────────────────────────────────────────────────
const cameraOffset = ref({ x: 0, y: 0 });
let isDraggingCamera = false;
let startMousePos = { x: 0, y: 0 };
let startOffset = { x: 0, y: 0 };

function startCameraDrag(e) {
  // Hanya drag jika yang di-klik bukan tombol atau elemen interaktif lain
  if (e.target.closest("button")) return;

  isDraggingCamera = true;
  startMousePos = { x: e.clientX, y: e.clientY };
  startOffset = { ...cameraOffset.value };

  window.addEventListener("mousemove", handleCameraDrag);
  window.addEventListener("mouseup", stopCameraDrag);

  // Prevent text selection
  e.preventDefault();
}

function handleCameraDrag(e) {
  if (!isDraggingCamera) return;

  const dx = e.clientX - startMousePos.x;
  const dy = e.clientY - startMousePos.y;

  cameraOffset.value = {
    x: startOffset.x + dx,
    y: startOffset.y + dy,
  };
}

function stopCameraDrag() {
  isDraggingCamera = false;
  window.removeEventListener("mousemove", handleCameraDrag);
  window.removeEventListener("mouseup", stopCameraDrag);
}

let _cameraLoadTimer = null;
watch(showCamera, (visible) => {
  if (visible) {
    cameraError.value = false;
    cameraLoading.value = true;
    // If @load/@error never fires (common with MJPEG streams), clear loading after 5s
    clearTimeout(_cameraLoadTimer);
    _cameraLoadTimer = setTimeout(() => {
      cameraLoading.value = false;
    }, 5000);
  } else {
    clearTimeout(_cameraLoadTimer);
  }
});

// Leaflet objects
let leafletMap = null;
let occupancyLayer = null; // ImageOverlay for OccupancyGrid
let costmapLayer = null; // ImageOverlay for Nav2 global costmap
let robotMarker = null; // 3D robot marker
let pathPolyline = null;
let goalMarker = null;
const waypointMarkers = shallowRef([]);
const keepoutLayers = shallowRef([]);
const destinationMarkers = shallowRef([]);
const dockMarkers = shallowRef([]);

// Navigate drag state (click+drag to set goal pose + yaw)
let navDragStart = null;
let navDragArrow = null;
let navDragging = false;

// Dock placement state
const dockStep = ref(0); // 0: target drag, 1: approach click
let dockPos = null; // { x, y, yaw }

// Dock target drag state (for yaw)
let dockDragStart = null;
let dockDragArrow = null;
let dockDragging = false;

// Keepout drawing state
let keepoutPoints = [];
let keepoutPolyline = null;

// Sensor layers
let laserCanvas = null; // L.Canvas renderer
let laserMarkers = [];
let particleMarkers = [];

// Initial pose drag state
let initPoseStart = null;
let initPoseDragArrow = null;
let initPoseDragging = false;

// Destination drag state (click+drag to set yaw)
let destDragStart = null;
let destDragArrow = null;
let destDragging = false;

// ── Map initialisation ────────────────────────────────────────────────────────

onMounted(() => {
  laserCanvas = L.canvas();

  leafletMap = L.map(mapEl.value, {
    center: [0, 0],
    zoom: 2,
    crs: L.CRS.Simple, // use a flat (pixel) coordinate system
    zoomControl: true,
    attributionControl: false,
  });

  leafletMap.on("click", onMapClick);
  leafletMap.on("mousedown", onMapMouseDown);
  leafletMap.on("mousemove", onMapMouseMove);
  leafletMap.on("mouseup", onMapMouseUp);

  // Robot marker — mulai invisible, tampil saat map pertama kali dirender
  robotMarker = L.marker([0, 0], { icon: robotIcon(), opacity: 0 }).addTo(
    leafletMap,
  );

  // Path polyline
  pathPolyline = L.polyline([], {
    color: "#3b82f6",
    weight: 2,
    opacity: 0.7,
  }).addTo(leafletMap);

  // Goal marker
  goalMarker = L.marker([0, 0], { icon: goalIcon(), opacity: 0 }).addTo(
    leafletMap,
  );

  // Render initial data if exists
  if (store.dockStations.length > 0) renderDockMarkers(store.dockStations);
});

onUnmounted(() => {
  if (leafletMap) leafletMap.remove();
  window.removeEventListener("mousemove", handleCameraDrag);
  window.removeEventListener("mouseup", stopCameraDrag);
});

// ── Watch store changes ───────────────────────────────────────────────────────

watch(
  () => store.mapData,
  (data) => {
    if (data) renderOccupancyGrid(data);
  },
);

watch(
  () => store.costmapData,
  (data) => {
    if (data && store.showCostmap) renderCostmap(data);
  },
);

watch(
  () => store.showCostmap,
  (visible) => {
    if (!costmapLayer) return;
    if (visible) {
      if (store.costmapData) renderCostmap(store.costmapData);
    } else {
      costmapLayer.remove();
      costmapLayer = null;
    }
  },
);

watch(
  () => store.showRobot,
  (visible) => {
    if (robotMarker) robotMarker.setOpacity(visible ? 1 : 0);
  },
);

watch(
  () => store.robotPose,
  ({ x, y, theta }) => {
    if (!leafletMap) return;
    const ll = mapToLeaflet(x, y);
    robotMarker.setLatLng(ll);

    // Pastikan opacity sesuai visibilitas saat posisi di-update
    if (robotMarker.options.opacity !== (store.showRobot ? 1 : 0)) {
      robotMarker.setOpacity(store.showRobot ? 1 : 0);
    }

    const el = robotMarker.getElement();
    if (el) {
      // ROS theta=0 → robot menghadap +X (kanan di peta)
      // SVG icon forward = atas → perlu offset +90° (π/2)
      // CSS rotate positif = searah jarum jam di layar
      const cssRot = Math.PI / 2 - theta;
      // Set transform-origin ke iconAnchor (body center) bukan element center,
      // supaya rotasi tidak menggeser visual position dari koordinat peta.
      const [anchorX, anchorY] = robotMarker.options.icon.options.iconAnchor;
      el.style.transformOrigin = `${anchorX}px ${anchorY}px`;
      el.style.transform = el.style.transform.replace(
        /\s*rotate\([^)]*\)/g,
        "",
      );
      el.style.transform += ` rotate(${cssRot}rad)`;
    }
  },
  { deep: true },
);

// Update ukuran icon saat footprint URDF datang dari /robot_description
watch(
  () => store.robotFootprint,
  (fp) => {
    if (!leafletMap || !robotMarker) return;
    robotMarker.setIcon(robotIcon(fp));
    // Re-apply transform-origin setelah icon diganti (anchor bisa berubah)
    const el = robotMarker.getElement();
    if (el) {
      const [anchorX, anchorY] = robotMarker.options.icon.options.iconAnchor;
      el.style.transformOrigin = `${anchorX}px ${anchorY}px`;
    }
  },
);

watch(
  () => store.plannedPath,
  (points) => {
    if (!leafletMap) return;
    const lls = points.map(({ x, y }) => mapToLeaflet(x, y));
    pathPolyline.setLatLngs(lls);
  },
);

watch(
  () => store.navGoal,
  (goal) => {
    if (!goal || !leafletMap) return;
    const ll = mapToLeaflet(goal.x, goal.y);
    goalMarker.setLatLng(ll).setOpacity(1);
  },
);

watch(
  () => store.waypoints,
  (wps) => {
    renderWaypointMarkers(wps);
    renderDestinationMarkers(store.destinations);
  },
  { deep: true },
);

watch(
  () => store.keepoutZones,
  (zones) => {
    renderKeepoutZones(zones);
  },
  { deep: true },
);

watch(
  () => store.destinations,
  (dests) => {
    renderDestinationMarkers(dests);
  },
  { deep: true },
);

// Tampilkan dock marker hanya saat sedang menuju / docked / undocking
watch(
  [
    () => store.dockStations,
    () => store.dockingStatus,
    () => store.activeDockId,
  ],
  () => {
    renderDockMarkers(store.dockStations);
  },
  { deep: true, immediate: true },
);

// Re-render destination markers saat mission mulai/berhenti (toggle nomor)
watch(
  () => store.missionRunning,
  () => {
    renderDestinationMarkers(store.destinations);
  },
);

watch(
  () => store.laserScan,
  (scan) => {
    if (scan && leafletMap) renderLaserScan(scan);
  },
);

watch(
  () => store.particleCloud,
  (poses) => {
    if (poses && leafletMap) renderParticleCloud(poses);
  },
);

// ── OccupancyGrid rendering ───────────────────────────────────────────────────

function renderOccupancyGrid(msg) {
  const { width, height, resolution, origin } = msg.info;
  const data = msg.data;

  // Draw grid onto canvas
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  const imgData = ctx.createImageData(width, height);

  for (let i = 0; i < data.length; i++) {
    const v = data[i];
    let r, g, b, a;
    if (v === -1) {
      // Unknown → grey
      r = 128;
      g = 128;
      b = 128;
      a = 200;
    } else if (v === 0) {
      // Free → white
      r = 240;
      g = 240;
      b = 240;
      a = 255;
    } else {
      // Occupied → dark
      const shade = Math.round(255 * (1 - v / 100));
      r = shade;
      g = shade;
      b = shade;
      a = 255;
    }
    // OccupancyGrid row 0 = bottom, canvas row 0 = top → flip
    const row = height - 1 - Math.floor(i / width);
    const col = i % width;
    const idx = (row * width + col) * 4;
    imgData.data[idx] = r;
    imgData.data[idx + 1] = g;
    imgData.data[idx + 2] = b;
    imgData.data[idx + 3] = a;
  }
  ctx.putImageData(imgData, 0, 0);

  const url = canvas.toDataURL();

  // Leaflet bounds in CRS.Simple units (pixels = metres * scale)
  const scale = 100; // pixels per metre
  const swX = origin.position.x * scale;
  const swY = origin.position.y * scale;
  const neX = swX + width * resolution * scale;
  const neY = swY + height * resolution * scale;

  const bounds = [
    [swY, swX],
    [neY, neX],
  ];

  if (occupancyLayer) {
    occupancyLayer.setUrl(url).setBounds(bounds);
  } else {
    occupancyLayer = L.imageOverlay(url, bounds, { opacity: 0.9 }).addTo(
      leafletMap,
    );
    leafletMap.fitBounds(bounds);
    // Reveal robot marker now that map is loaded
    if (robotMarker) robotMarker.setOpacity(1);
  }
}

// ── Costmap rendering (RViz-style colormap) ───────────────────────────────────

function renderCostmap(msg) {
  const { width, height, resolution, origin } = msg.info;
  const data = msg.data;

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  const imgData = ctx.createImageData(width, height);

  for (let i = 0; i < data.length; i++) {
    const v = data[i];
    let r, g, b, a;

    if (v <= 0 || v === -1) {
      // Free space atau unknown → transparan, tampilkan base map di bawah
      r = 0;
      g = 0;
      b = 0;
      a = 0;
    } else if (v >= 100) {
      // Lethal obstacle → merah
      r = 255;
      g = 0;
      b = 0;
      a = 210;
    } else {
      // Inflation zone (1–99): cyan → biru → magenta, mirip RViz costmap scheme
      const t = v / 99;
      if (t < 0.5) {
        // cyan (#00e5ff) → biru (#0000ff)
        const s = t * 2;
        r = 0;
        g = Math.round(229 * (1 - s));
        b = 255;
      } else {
        // biru (#0000ff) → magenta/pink (#ff00ff)
        const s = (t - 0.5) * 2;
        r = Math.round(255 * s);
        g = 0;
        b = 255;
      }
      a = 180;
    }

    // Flip Y: ROS origin = bottom-left, canvas origin = top-left
    const row = height - 1 - Math.floor(i / width);
    const col = i % width;
    const idx = (row * width + col) * 4;
    imgData.data[idx] = r;
    imgData.data[idx + 1] = g;
    imgData.data[idx + 2] = b;
    imgData.data[idx + 3] = a;
  }

  ctx.putImageData(imgData, 0, 0);
  const url = canvas.toDataURL();

  const scale = 100;
  const swX = origin.position.x * scale;
  const swY = origin.position.y * scale;
  const neX = swX + width * resolution * scale;
  const neY = swY + height * resolution * scale;
  const bounds = [
    [swY, swX],
    [neY, neX],
  ];

  if (costmapLayer) {
    costmapLayer.setUrl(url).setBounds(bounds);
  } else {
    costmapLayer = L.imageOverlay(url, bounds, {
      opacity: 0.75,
      interactive: false,
    }).addTo(leafletMap);
  }
}

// ── Map coordinate helpers ────────────────────────────────────────────────────

const SCALE = 100; // pixels per metre (matches renderOccupancyGrid)

function mapToLeaflet(x, y) {
  // In CRS.Simple, LatLng = [y, x]
  return [y * SCALE, x * SCALE];
}

function leafletToMap(ll) {
  return { x: ll.lng / SCALE, y: ll.lat / SCALE };
}

// ── Click handler ─────────────────────────────────────────────────────────────

function onMapClick(e) {
  // Ignore clicks outside the rendered map area
  if (occupancyLayer) {
    const bounds = occupancyLayer.getBounds();
    if (!bounds.contains(e.latlng)) return;
  }

  const { x, y } = leafletToMap(e.latlng);

  if (mapMode.value === "waypoint") {
    toast.warning(
      "Tambah waypoint dari destinations panel — klik peta tidak mendukung station ID.",
    );
  } else if (mapMode.value === "dock_placement") {
    // Step 0 handled by mousedown/mouseup drag (for yaw)
    if (dockStep.value === 1) {
      emit("dockPlaced", {
        x: dockPos.x,
        y: dockPos.y,
        yaw: dockPos.yaw,
        approach_x: x,
        approach_y: y,
      });
      cancelDockPlacement();
      setMode("navigate");
    }
  } else if (mapMode.value === "keepout") {
    keepoutPoints.push([e.latlng.lat, e.latlng.lng]);
    if (keepoutPolyline) {
      keepoutPolyline.setLatLngs(keepoutPoints);
    } else {
      keepoutPolyline = L.polyline(keepoutPoints, {
        color: "#f59e0b",
        dashArray: "4",
        weight: 2,
      }).addTo(leafletMap);
    }
  }
  // initial_pose handled by mousedown/mouseup (drag to set orientation)
}

// ── Initial pose drag (click+drag to set position + orientation) ──────────────

function onMapMouseDown(e) {
  if (mapMode.value === "navigate") {
    if (store.isBusy) {
      toast.warning(
        "Robot sedang BUSY — tunggu sampai selesai sebelum mengirim goal baru.",
      );
      setMode("view");
      return;
    }
    navDragging = true;
    navDragStart = { map: leafletToMap(e.latlng), latlng: e.latlng };
    navDragArrow = L.polyline([e.latlng, e.latlng], {
      color: "#3b82f6",
      weight: 3,
      opacity: 0.9,
    }).addTo(leafletMap);
    leafletMap.dragging.disable();
  } else if (mapMode.value === "initial_pose") {
    initPoseDragging = true;
    initPoseStart = { map: leafletToMap(e.latlng), latlng: e.latlng };
    initPoseDragArrow = L.polyline([e.latlng, e.latlng], {
      color: "#22c55e",
      weight: 3,
      opacity: 0.9,
    }).addTo(leafletMap);
    leafletMap.dragging.disable();
  } else if (mapMode.value === "destination") {
    destDragging = true;
    destDragStart = { map: leafletToMap(e.latlng), latlng: e.latlng };
    destDragArrow = L.polyline([e.latlng, e.latlng], {
      color: "#10b981",
      weight: 3,
      opacity: 0.9,
    }).addTo(leafletMap);
    leafletMap.dragging.disable();
  } else if (mapMode.value === "dock_placement" && dockStep.value === 0) {
    dockDragging = true;
    dockDragStart = { map: leafletToMap(e.latlng), latlng: e.latlng };
    dockDragArrow = L.polyline([e.latlng, e.latlng], {
      color: "#f59e0b",
      weight: 3,
      opacity: 0.9,
    }).addTo(leafletMap);
    leafletMap.dragging.disable();
  }
}

function onMapMouseMove(e) {
  if (navDragging && navDragArrow)
    navDragArrow.setLatLngs([navDragStart.latlng, e.latlng]);
  if (initPoseDragging && initPoseDragArrow)
    initPoseDragArrow.setLatLngs([initPoseStart.latlng, e.latlng]);
  if (destDragging && destDragArrow)
    destDragArrow.setLatLngs([destDragStart.latlng, e.latlng]);
  if (dockDragging && dockDragArrow)
    dockDragArrow.setLatLngs([dockDragStart.latlng, e.latlng]);
}

function onMapMouseUp(e) {
  if (navDragging) {
    navDragging = false;
    leafletMap.dragging.enable();

    const end = leafletToMap(e.latlng);
    const dx = end.x - navDragStart.map.x;
    const dy = end.y - navDragStart.map.y;
    // Kalau tidak di-drag (pure click), biarkan Nav2 tentukan orientasi sendiri (theta=null)
    const dragged = Math.sqrt(dx * dx + dy * dy) > 0.05;
    const theta = dragged ? Math.atan2(dy, dx) : null;

    if (navDragArrow) {
      navDragArrow.remove();
      navDragArrow = null;
    }
    ros.navigateTo(navDragStart.map.x, navDragStart.map.y, theta);
    navDragStart = null;
    setMode("view"); // kembali ke pan mode setelah goal dikirim
  }

  if (initPoseDragging) {
    initPoseDragging = false;
    leafletMap.dragging.enable();

    const end = leafletToMap(e.latlng);
    const dx = end.x - initPoseStart.map.x;
    const dy = end.y - initPoseStart.map.y;
    const theta = Math.atan2(dy, dx);

    if (initPoseDragArrow) {
      initPoseDragArrow.remove();
      initPoseDragArrow = null;
    }
    ros.setInitialPose(initPoseStart.map.x, initPoseStart.map.y, theta);
    initPoseStart = null;
    setMode("navigate");
  }

  if (destDragging) {
    destDragging = false;
    leafletMap.dragging.enable();

    const end = leafletToMap(e.latlng);
    const dx = end.x - destDragStart.map.x;
    const dy = end.y - destDragStart.map.y;
    const dragged = Math.sqrt(dx * dx + dy * dy) > 0.05;
    const yaw = dragged ? Math.atan2(dy, dx) : 0;

    if (destDragArrow) {
      destDragArrow.remove();
      destDragArrow = null;
    }
    emit("destinationClick", destDragStart.map.x, destDragStart.map.y, yaw);
    destDragStart = null;
    // tetap di destination mode supaya bisa tambah lebih banyak titik
  }

  if (dockDragging) {
    dockDragging = false;
    leafletMap.dragging.enable();

    const end = leafletToMap(e.latlng);
    const dx = end.x - dockDragStart.map.x;
    const dy = end.y - dockDragStart.map.y;
    const yaw = Math.atan2(dy, dx);

    if (dockDragArrow) {
      dockDragArrow.remove();
      dockDragArrow = null;
    }
    dockPos = { x: dockDragStart.map.x, y: dockDragStart.map.y, yaw };
    dockDragStart = null;
    dockStep.value = 1;
  }
}

// ── Keepout zone drawing ──────────────────────────────────────────────────────

async function finishKeepout() {
  if (keepoutPoints.length < 3) return;

  const polygon = keepoutPoints.map((ll) =>
    leafletToMap({ lat: ll[0], lng: ll[1] }),
  );
  store.addKeepoutZone(polygon);
  ros.updateKeepoutZones(store.keepoutZones);

  // Persist to backend if a map is active
  if (store.activeMapId) {
    const zone = store.keepoutZones[store.keepoutZones.length - 1];
    try {
      const saved = await api.post("/keepout", {
        map_id: store.activeMapId,
        name: zone.name,
        polygon,
      });
      // Replace the temp id with the backend-assigned id
      zone.id = saved.id;
    } catch (err) {
      console.warn("[MapView] keepout persist failed:", err);
    }
  }

  cancelKeepout();
  setMode("navigate");
}

function cancelKeepout() {
  if (keepoutPolyline) {
    keepoutPolyline.remove();
    keepoutPolyline = null;
  }
  keepoutPoints = [];
}

// ── Dock placement ────────────────────────────────────────────────────────────

function skipApproach() {
  if (dockPos) {
    emit("dockPlaced", {
      x: dockPos.x,
      y: dockPos.y,
      yaw: dockPos.yaw,
      approach_x: dockPos.x,
      approach_y: dockPos.y,
    });
  }
  cancelDockPlacement();
  setMode("navigate");
}

function cancelDockPlacement() {
  if (dockDragArrow) {
    dockDragArrow.remove();
    dockDragArrow = null;
  }
  dockDragging = false;
  dockDragStart = null;
  if (leafletMap) leafletMap.dragging.enable();
  dockPos = null;
  dockStep.value = 0;
}

// ── Waypoint markers ──────────────────────────────────────────────────────────

function renderWaypointMarkers(wps) {
  waypointMarkers.value.forEach((m) => m.remove());
  waypointMarkers.value = wps.map((wp, i) => {
    const ll = mapToLeaflet(wp.x, wp.y);
    return L.marker(ll, { icon: waypointIcon(i + 1) })
      .bindTooltip(wp.name, { permanent: false })
      .addTo(leafletMap);
  });
}

// ── Keepout zone layers ───────────────────────────────────────────────────────

function renderKeepoutZones(zones) {
  keepoutLayers.value.forEach((l) => l.remove());
  keepoutLayers.value = zones.map((zone) => {
    const lls = zone.polygon.map(({ x, y }) => mapToLeaflet(x, y));
    return L.polygon(lls, {
      color: "#f59e0b",
      fillColor: "#f59e0b",
      fillOpacity: 0.2,
      weight: 2,
    })
      .bindTooltip(zone.name)
      .addTo(leafletMap);
  });
}

// ── Laser scan rendering ──────────────────────────────────────────────────────

function renderLaserScan(scan) {
  const { x: rx, y: ry, theta: rt } = store.robotPose;
  const { angle_min, angle_increment, range_min, range_max, ranges } = scan;

  const opts = {
    radius: 2,
    color: "#ef4444",
    fillColor: "#ef4444",
    fillOpacity: 1,
    weight: 0,
    renderer: laserCanvas,
  };
  let poolIdx = 0;

  for (let i = 0; i < ranges.length; i++) {
    const r = ranges[i];
    if (!isFinite(r) || r < range_min || r > range_max) continue;
    const angle = angle_min + i * angle_increment + rt;
    const ll = mapToLeaflet(rx + r * Math.cos(angle), ry + r * Math.sin(angle));
    if (poolIdx < laserMarkers.length) {
      laserMarkers[poolIdx].setLatLng(ll);
    } else {
      laserMarkers.push(L.circleMarker(ll, opts).addTo(leafletMap));
    }
    poolIdx++;
  }

  // Remove excess markers from previous frame
  laserMarkers.splice(poolIdx).forEach((m) => m.remove());
}

// ── Particle cloud rendering ──────────────────────────────────────────────────

function renderParticleCloud(poses) {
  particleMarkers.forEach((m) => m.remove());
  particleMarkers = [];

  for (const { x, y } of poses) {
    particleMarkers.push(
      L.circleMarker(mapToLeaflet(x, y), {
        radius: 2,
        color: "#a855f7",
        fillColor: "#a855f7",
        fillOpacity: 0.6,
        weight: 0,
        renderer: laserCanvas,
      }).addTo(leafletMap),
    );
  }
}

// ── Mode management ───────────────────────────────────────────────────────────

function setMode(mode) {
  if (mapMode.value === "keepout" && mode !== "keepout") cancelKeepout();
  // Cleanup nav drag jika keluar dari navigate mode
  if (mapMode.value === "navigate" && mode !== "navigate" && navDragging) {
    navDragging = false;
    if (navDragArrow) {
      navDragArrow.remove();
      navDragArrow = null;
    }
    if (leafletMap) leafletMap.dragging.enable();
  }
  // Re-enable map panning saat masuk view mode
  if (mode === "view" && leafletMap) leafletMap.dragging.enable();
  _setModeShared(mode);
}

// ── Leaflet icon factories ────────────────────────────────────────────────────

/**
 * Buat 3D isometric robot icon.
 * @param {object|null} fp - { length, width } dalam meter dari /robot_description.
 *                           Kalau null, pakai ukuran default.
 *
 * Ukuran visual menggunakan ICON_SCALE px/m (bukan map SCALE),
 * supaya icon tetap terbaca di semua zoom level.
 * Minimum ukuran body: 20px agar tetap visible.
 */
function robotIcon(fp = null) {
  const ICON_SCALE = 110; // px per metre

  // Body dimensions (flat top-down view)
  const bw = fp ? Math.max(Math.round(fp.width * ICON_SCALE), 18) : 24; // lebar (sumbu Y robot)
  const bl = fp ? Math.max(Math.round(fp.length * ICON_SCALE), 18) : 30; // panjang (sumbu X robot)

  const hw = Math.round(bw / 2);
  const hl = Math.round(bl / 2);

  // Roda: flat, menempel di sisi kiri & kanan body
  const ww = 4; // lebar roda
  const wh = Math.round(bl * 0.32); // tinggi roda
  const wGap = 1;

  // Arrow depan (segitiga kecil keluar dari body)
  const arrowH = 7;

  // SVG canvas — arrow di atas body, jadi oy harus offset ke bawah sebesar arrowH
  const pad = ww + wGap + 2;
  const svgW = bw + pad * 2;
  const svgH = bl + arrowH + 4;
  const ox = Math.round(svgW / 2);
  const oy = arrowH + hl + 2; // center body: beri ruang arrowH di atas

  const html = `<svg width="${svgW}" height="${svgH}"
    viewBox="0 0 ${svgW} ${svgH}"
    xmlns="http://www.w3.org/2000/svg"
    style="overflow:visible">

    <!-- Body utama (top-down) -->
    <rect
      x="${ox - hw}" y="${oy - hl}"
      width="${bw}" height="${bl}"
      fill="#3b82f6" stroke="#93c5fd" stroke-width="1.5" rx="3"/>

    <!-- Stripe depan (indikator arah maju) -->
    <rect
      x="${ox - hw + 2}" y="${oy - hl + 2}"
      width="${bw - 4}" height="${Math.max(Math.round(bl * 0.2), 4)}"
      fill="#93c5fd" opacity="0.5" rx="1.5"/>

    <!-- Roda kiri-depan -->
    <rect x="${ox - hw - wGap - ww}" y="${oy - hl + 2}" width="${ww}" height="${wh}" fill="#1e293b" rx="1.5" stroke="#475569" stroke-width="0.5"/>
    <!-- Roda kiri-belakang -->
    <rect x="${ox - hw - wGap - ww}" y="${oy + hl - wh - 2}" width="${ww}" height="${wh}" fill="#1e293b" rx="1.5" stroke="#475569" stroke-width="0.5"/>
    <!-- Roda kanan-depan -->
    <rect x="${ox + hw + wGap}" y="${oy - hl + 2}" width="${ww}" height="${wh}" fill="#1e293b" rx="1.5" stroke="#475569" stroke-width="0.5"/>
    <!-- Roda kanan-belakang -->
    <rect x="${ox + hw + wGap}" y="${oy + hl - wh - 2}" width="${ww}" height="${wh}" fill="#1e293b" rx="1.5" stroke="#475569" stroke-width="0.5"/>

    <!-- Panah arah maju (keluar dari atas body) -->
    <polygon
      points="${ox},${oy - hl - arrowH} ${ox - 5},${oy - hl} ${ox + 5},${oy - hl}"
      fill="#ffffff" opacity="0.95"/>
  </svg>`;

  return L.divIcon({
    html,
    iconSize: [svgW, svgH],
    iconAnchor: [ox, oy], // tepat di center body — tidak ada 3D offset
    className: "",
  });
}

function goalIcon() {
  return L.divIcon({
    html: `<svg width="20" height="20" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
      <circle cx="10" cy="10" r="8" fill="none" stroke="#22c55e" stroke-width="2" stroke-dasharray="4"/>
      <circle cx="10" cy="10" r="3" fill="#22c55e"/>
    </svg>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
    className: "",
  });
}

function waypointIcon(n) {
  return L.divIcon({
    html: `<div style="background:#f59e0b;color:white;border-radius:50%;width:22px;height:22px;
                display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:bold;
                border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.5)">${n}</div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
    className: "",
  });
}

// Saat mission running: kotak hijau bernomor
// Saat idle: titik kecil (pin) tanpa nomor
function destinationIcon(n, showNumber) {
  if (showNumber) {
    return L.divIcon({
      html: `<div style="background:#10b981;color:white;border-radius:4px;width:22px;height:22px;
                  display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:bold;
                  border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.5)">${n}</div>`,
      iconSize: [22, 22],
      iconAnchor: [11, 11],
      className: "",
    });
  }
  return L.divIcon({
    html: `<div style="background:#10b981;border-radius:50%;width:10px;height:10px;
                border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.5)"></div>`,
    iconSize: [10, 10],
    iconAnchor: [5, 5],
    className: "",
  });
}

// ── Destination markers ───────────────────────────────────────────────────────

function renderDestinationMarkers(dests) {
  destinationMarkers.value.forEach((m) => m.remove());
  destinationMarkers.value = [];

  // Sembunyikan semua marker saat mission tidak berjalan
  if (!store.missionRunning) return;

  // Hanya tampilkan destination yang dipakai sebagai waypoint
  const usedPoints = new Set(
    store.waypoints.map((w) => w.destPoint).filter((p) => p != null),
  );

  dests.forEach((dest, i) => {
    const pointNum = i + 1;
    if (!usedPoints.has(pointNum)) return;
    const ll = mapToLeaflet(dest.x, dest.y);
    destinationMarkers.value.push(
      L.marker(ll, { icon: destinationIcon(pointNum, true) })
        .bindTooltip(`Point ${pointNum}: ${dest.name}`, { permanent: false })
        .addTo(leafletMap),
    );
  });
}

// ── Dock markers ──────────────────────────────────────────────────────────────

function renderDockMarkers(docks) {
  if (!leafletMap) return;
  dockMarkers.value.forEach((m) => m.remove());

  // Tampilkan hanya saat robot sedang menuju / docked / undocking
  const dockingActive = ["docking", "docked", "undocking"].includes(
    store.dockingStatus,
  );
  const filteredDocks =
    dockingActive && store.activeDockId
      ? docks.filter((d) => d.id === store.activeDockId)
      : [];

  dockMarkers.value = filteredDocks.map((dock) => {
    const ll = mapToLeaflet(dock.target.x, dock.target.y);
    const m = L.marker(ll, { icon: dockIcon() })
      .bindTooltip(`Dock: ${dock.name}`, { permanent: false })
      .addTo(leafletMap);

    // Add approach point line if exists
    if (dock.approach?.x != null && dock.approach?.y != null) {
      const appLL = mapToLeaflet(dock.approach.x, dock.approach.y);
      const line = L.polyline([ll, appLL], {
        color: "#f59e0b",
        weight: 1,
        dashArray: "2, 4",
        opacity: 0.6,
      }).addTo(leafletMap);

      const dot = L.circleMarker(appLL, {
        radius: 3,
        color: "#f59e0b",
        fillOpacity: 1,
        weight: 0,
      }).addTo(leafletMap);

      // Wrap them so we can remove them later
      const originalRemove = m.remove;
      m.remove = function () {
        line.remove();
        dot.remove();
        return originalRemove.apply(this, arguments);
      };
    }

    return m;
  });
}

function dockIcon() {
  return L.divIcon({
    html: `<div style="background:#d97706;color:white;border-radius:4px;width:18px;height:18px;
                display:flex;align-items:center;justify-content:center;font-size:10px;
                border:2px solid white;box-shadow:0 1px 3px rgba(0,0,0,0.5)">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
              <path d="M12 2v20M2 12h20" />
            </svg>
          </div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
    className: "",
  });
}
</script>

<style scoped>
/* ── Toolbar button base ────────────────────────────────────────────── */
.toolbar-btn {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 0.75rem;
  transition: background-color 150ms cubic-bezier(0.23, 1, 0.32, 1),
              color 150ms cubic-bezier(0.23, 1, 0.32, 1),
              box-shadow 150ms cubic-bezier(0.23, 1, 0.32, 1),
              transform 100ms cubic-bezier(0.23, 1, 0.32, 1);
}

.toolbar-btn:active {
  transform: scale(0.93);
}

@media (hover: hover) and (pointer: fine) {
  .toolbar-btn:not(:disabled):hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: hsl(var(--foreground));
  }
}

/* ── Toolbar tooltip: scale-in from right ───────────────────────────── */
.toolbar-tooltip {
  position: absolute;
  right: calc(100% + 0.5rem);
  padding: 0.25rem 0.5rem;
  font-size: 0.625rem;
  font-weight: 500;
  background: hsl(var(--popover));
  color: hsl(var(--popover-foreground));
  border-radius: 0.375rem;
  white-space: nowrap;
  pointer-events: none;
  border: 1px solid hsl(var(--border) / 0.5);
  box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.3);
  transform-origin: right center;
  /* Default: hidden */
  opacity: 0;
  transform: scale(0.92);
  transition: opacity 125ms cubic-bezier(0.23, 1, 0.32, 1),
              transform 125ms cubic-bezier(0.23, 1, 0.32, 1);
}

@media (hover: hover) and (pointer: fine) {
  .toolbar-btn:hover .toolbar-tooltip {
    opacity: 1;
    transform: scale(1);
  }
}

/* ── Mode indicator bar enter/exit ──────────────────────────────────── */
.mode-bar-enter-active {
  transition: opacity 200ms cubic-bezier(0.23, 1, 0.32, 1),
              transform 200ms cubic-bezier(0.23, 1, 0.32, 1);
}

.mode-bar-leave-active {
  transition: opacity 120ms ease-in,
              transform 120ms ease-in;
}

.mode-bar-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}

.mode-bar-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(6px);
}
</style>
