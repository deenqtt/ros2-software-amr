/**
 * Pinia store — central state for the AMR web UI.
 *
 * Sections:
 *  - ROS connection state
 *  - Map data (OccupancyGrid)
 *  - Robot pose
 *  - Navigation state
 *  - Mission (waypoints + loop)
 *  - Docking state
 */

import { defineStore } from "pinia";
import { ref, computed } from "vue";

export const useRobotStore = defineStore("robot", () => {
  // ── App mode ──────────────────────────────────────────────────────────────
  /**
   * appMode: 'navigation' | 'mapping'
   * Mengontrol panel dan toolbar yang ditampilkan di seluruh UI.
   */
  const appMode = ref("navigation");

  function setAppMode(mode) {
    appMode.value = mode;
  }

  // ── ROS connection ────────────────────────────────────────────────────────
  const rosConnected = ref(false);
  const rosUrl = ref("ws://localhost:8765");

  // ── Map ───────────────────────────────────────────────────────────────────
  /** Raw OccupancyGrid message from /map topic */
  const mapData = ref(null);

  // ── Robot pose ────────────────────────────────────────────────────────────
  /**
   * { x, y, theta } in map frame (metres, radians)
   * Updated from /amcl_pose (navigation mode) or /odom (slam mode)
   */
  const robotPose = ref({ x: 0, y: 0, theta: 0 });

  /**
   * { linear, angular } velocities
   * Updated from /odom
   */
  const robotVelocity = ref({ linear: 0, angular: 0 });

  // ── Nav status ────────────────────────────────────────────────────────────
  /**
   * idle | navigating | following_waypoints | docking | mapping | error
   */
  const navStatus = ref("idle");

  /** Planned path — array of { x, y } in map coords */
  const plannedPath = ref([]);

  /** Current navigation goal { x, y, theta } */
  const navGoal = ref(null);

  // ── Mission ───────────────────────────────────────────────────────────────
  /**
   * waypoints: [{ id, name, x, y, theta }]
   * Ordered list of navigation targets.
   */
  const waypoints = ref([]);
  const missionRunning = ref(false);
  const missionLoop = ref(false);
  const missionLoopCount = ref(0); // 0 = infinite
  const missionTimeoutSec = ref(120); // seconds per waypoint before forced advance
  const currentWaypointIndex = ref(0);

  // ── Multi-map ──────────────────────────────────────────────────────────────
  /** List of maps fetched from backend */
  const maps = ref([]);
  /** Currently active map id (null = none selected) */
  const activeMapId = ref(null);

  // ── Battery ───────────────────────────────────────────────────────────────
  /** Persentase baterai 0–100, null = belum ada data */
  const batteryPercent = ref(null);
  /** Voltage baterai dalam Volt, null = belum ada data */
  const batteryVoltage = ref(null);
  /** true = sedang charging (docked) */
  const batteryCharging = ref(false);

  // ── Auto-docking config ───────────────────────────────────────────────────
  const autoDockEnabled = ref(false);
  const lowBatteryThreshold = ref(20);
  const autoDockTargetId = ref(null);

  // ── Docking ───────────────────────────────────────────────────────────────
  const dockingActive = ref(false);
  const dockingStatus = ref("idle"); // idle | docking | docked | undocking | error
  const activeDockId = ref(null);  // ID dock yang sedang/terakhir dituju

  // ── Destination points ────────────────────────────────────────────────────
  /**
   * destinations: [{ id, map_id, name, x, y }]
   * Point number = index + 1
   */
  const destinations = ref([])

  // ── Dock stations ─────────────────────────────────────────────────────────
  /** [{ id, map_id, name, x, y, theta, approach_x, approach_y }] */
  const dockStations = ref([]);

  // ── Robot description (URDF footprint) ───────────────────────────────────
  /** { length, width } in metres, parsed from /robot_description URDF */
  const robotFootprint = ref(null);
  const showRobot = ref(true);

  // ── Costmap ───────────────────────────────────────────────────────────────
  /** nav_msgs/OccupancyGrid from /global_costmap/costmap */
  const costmapData = ref(null);
  const showCostmap = ref(true);

  // ── Sensor data ───────────────────────────────────────────────────────────
  /** Raw sensor_msgs/LaserScan from /scan */
  const laserScan = ref(null);
  /** Array of {x, y, theta} in map frame from AMCL particle cloud */
  const particleCloud = ref([]);

  // ── Keepout zones ─────────────────────────────────────────────────────────
  /**
   * keepoutZones: [{ id, name, polygon: [{lat, lng}, ...] }]
   * Stored as Leaflet lat/lng pairs; converted to map coords when publishing.
   */
  const keepoutZones = ref([]);

  // ── Computed ──────────────────────────────────────────────────────────────
  const isIdle = computed(() => navStatus.value === "idle");
  const isNavigating = computed(
    () =>
      navStatus.value === "navigating" ||
      navStatus.value === "following_waypoints" ||
      dockingActive.value,
  );
  const hasMap = computed(() => mapData.value !== null);

  /**
   * isBusy — true ketika robot sedang aktif melakukan sesuatu dan
   * tidak boleh menerima perintah navigasi baru dari web UI.
   * Covers: navigating, following_waypoints, executing, waiting_confirm,
   *         docking in-progress, undocking in-progress.
   */
  const isBusy = computed(() =>
    navStatus.value !== "idle" ||
    dockingStatus.value === "docking" ||
    dockingStatus.value === "undocking",
  );

  /** Label singkat untuk status Available / Busy */
  const availabilityLabel = computed(() => (isBusy.value ? "BUSY" : "AVAILABLE"));

  // ── Actions ───────────────────────────────────────────────────────────────

  function setConnected(connected) {
    rosConnected.value = connected;
    if (!connected) navStatus.value = "idle";
  }

  function setMapData(data) {
    mapData.value = data;
  }

  function updatePose(x, y, theta) {
    robotPose.value = { x, y, theta };
  }

  function setRobotVelocity(linear, angular) {
    robotVelocity.value = { linear, angular };
  }

  function setNavStatus(status) {
    navStatus.value = status;
  }

  function setPlannedPath(points) {
    plannedPath.value = points;
  }

  function setNavGoal(goal) {
    navGoal.value = goal;
  }

  // ── Waypoint management ───────────────────────────────────────────────────

  function addWaypoint(
    x,
    y,
    theta = 0,
    name = null,
    task = "Pick",
    continueMode = "Auto",
    destPoint = null,
    stationId = null,
  ) {
    if (waypoints.value.length >= 5) return false;
    const id = Date.now();
    waypoints.value.push({
      id,
      name: name ?? `WP ${waypoints.value.length + 1}`,
      x,
      y,
      theta,
      task,
      continueMode,
      destPoint,
      stationId,
    });
    return true;
  }

  function removeWaypoint(id) {
    waypoints.value = waypoints.value.filter((w) => w.id !== id);
  }

  function updateWaypoint(id, patch) {
    const wp = waypoints.value.find((w) => w.id === id);
    if (wp) Object.assign(wp, patch);
  }

  function reorderWaypoints(newOrder) {
    waypoints.value = newOrder;
  }

  function clearWaypoints() {
    waypoints.value = [];
  }

  // ── Map management ────────────────────────────────────────────────────────

  function setMaps(list) {
    maps.value = list;
  }

  function setActiveMap(id) {
    activeMapId.value = id;
  }

  // ── Keepout zones ─────────────────────────────────────────────────────────

  function addKeepoutZone(polygon, name = null) {
    keepoutZones.value.push({
      id: Date.now(),
      name: name ?? `Zone ${keepoutZones.value.length + 1}`,
      polygon,
    });
  }

  function removeKeepoutZone(id) {
    keepoutZones.value = keepoutZones.value.filter((z) => z.id !== id);
  }

  // ── Destination point management ──────────────────────────────────────────

  function setDestinations(list) {
    destinations.value = list;
  }

  function addDestination(dest) {
    destinations.value.push(dest);
  }

  function removeDestination(id) {
    destinations.value = destinations.value.filter((d) => d.id !== id);
  }

  function setDockStations(list) { dockStations.value = list; }
  function addDockStation(d) { dockStations.value.push(d); }
  function removeDockStation(id) { dockStations.value = dockStations.value.filter((d) => d.id !== id); }

  // ── Docking ───────────────────────────────────────────────────────────────

  function setLaserScan(msg) {
    laserScan.value = msg;
  }

  function setParticleCloud(poses) {
    particleCloud.value = poses;
  }

  function setRobotFootprint(fp) {
    robotFootprint.value = fp;
  }

  function setCostmapData(data) {
    costmapData.value = data;
  }

  function toggleCostmap() {
    showCostmap.value = !showCostmap.value;
  }

  function toggleRobotVisibility() {
    showRobot.value = !showRobot.value;
  }

  function setBattery(percent, charging, voltage = null) {
    batteryPercent.value = percent;
    batteryCharging.value = charging;
    if (voltage !== null) batteryVoltage.value = voltage;
  }

  function setAutoDockEnabled(val) { autoDockEnabled.value = val; }
  function setLowBatteryThreshold(val) { lowBatteryThreshold.value = val; }
  function setAutoDockTargetId(val) { autoDockTargetId.value = val; }

  function setDockingStatus(status) {
    dockingStatus.value = status;
    dockingActive.value = status === "docking" || status === "undocking";
    if (status === "idle") activeDockId.value = null;
  }

  function setActiveDockId(id) { activeDockId.value = id; }

  // ── Mission execution state ───────────────────────────────────────────────

  function startMission() {
    missionRunning.value = true;
    currentWaypointIndex.value = 0;
    navStatus.value = "following_waypoints";
  }

  function stopMission() {
    missionRunning.value = false;
    navStatus.value = "idle";
    navGoal.value = null;
    plannedPath.value = [];
  }

  function pauseMission() {
    missionRunning.value = false;
    navStatus.value = "idle";
  }

  function resumeMission() {
    missionRunning.value = true;
    navStatus.value = "following_waypoints";
  }

  function setCurrentWaypointIndex(idx) {
    currentWaypointIndex.value = idx;
  }

  return {
    // State
    appMode,
    setAppMode,
    batteryPercent,
    batteryVoltage,
    batteryCharging,
    autoDockEnabled,
    lowBatteryThreshold,
    autoDockTargetId,
    rosConnected,
    rosUrl,
    mapData,
    robotPose,
    robotVelocity,
    navStatus,
    plannedPath,
    navGoal,
    waypoints,
    missionRunning,
    missionLoop,
    missionLoopCount,
    missionTimeoutSec,
    currentWaypointIndex,
    maps,
    activeMapId,
    dockingActive,
    dockingStatus,
    keepoutZones,
    robotFootprint,
    showRobot,
    laserScan,
    particleCloud,

    // Computed
    isIdle,
    isNavigating,
    hasMap,
    isBusy,
    availabilityLabel,

    // Actions
    setBattery,
    setAutoDockEnabled,
    setLowBatteryThreshold,
    setAutoDockTargetId,
    setConnected,
    setMapData,
    updatePose,
    setRobotVelocity,
    setNavStatus,
    setPlannedPath,
    setNavGoal,
    addWaypoint,
    removeWaypoint,
    updateWaypoint,
    reorderWaypoints,
    clearWaypoints,
    setMaps,
    setActiveMap,
    addKeepoutZone,
    removeKeepoutZone,
    destinations,
    setDestinations,
    addDestination,
    removeDestination,
    dockStations,
    setDockStations,
    addDockStation,
    removeDockStation,
    setRobotFootprint,
    costmapData,
    showCostmap,
    setCostmapData,
    toggleCostmap,
    toggleRobotVisibility,
    setLaserScan,
    setParticleCloud,
    activeDockId,
    setActiveDockId,
    setDockingStatus,
    startMission,
    stopMission,
    pauseMission,
    resumeMission,
    setCurrentWaypointIndex,
  };
});
