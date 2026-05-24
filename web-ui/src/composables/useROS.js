/**
 * useROS — roslibjs wrapper for Foxglove Bridge WebSocket connection.
 *
 * Provides:
 *  - connect / disconnect
 *  - subscribe to topics
 *  - publish to topics
 *  - call services
 *  - send action goals (navigate_to_pose, follow_waypoints, dock)
 *
 * Usage:
 *   const { ros, connected, connect, navigateTo, followWaypoints, ... } = useROS()
 */

import { ref, readonly } from "vue";
import ROSLIB from "roslib";
import { useRobotStore } from "@/stores/robot";
import { useToast } from "@/composables/useToast";

// ── Singleton ROSLIB instance shared across the app ───────────────────────────
let _ros = null;
const _connected = ref(false);

// ── Action goal handle references (for cancelling) ────────────────────────────
let _navGoalHandle = null;
let _dockGoalHandle = null;

// ── Mission state (sequential waypoint execution) ─────────────────────────────
let _missionWaypoints = [];
let _missionIndex = 0;
let _missionRunning = false;
let _missionGoalTimeout = null;
let _currentMissionGoalId = null;

// ── Pose source tracking ───────────────────────────────────────────────────────
// Priority: TF chain (map→base_footprint) > AMCL pose > SLAM /pose
let _lastAmclTime = 0;
const AMCL_TIMEOUT_MS = 3000;

// ── TF buffer — stores latest known transforms ────────────────────────────────
// key: "parent_frame/child_frame", value: { tx, ty, yaw }
const _tfBuffer = {};

function _tfKey(parent, child) {
  return `${parent}/${child}`;
}

function _storeTF(header_frame_id, child_frame_id, transform) {
  const yaw = _quaternionToYaw(transform.rotation);
  _tfBuffer[_tfKey(header_frame_id, child_frame_id)] = {
    tx: transform.translation.x,
    ty: transform.translation.y,
    yaw,
  };
}

// Compose two 2D planar transforms: result = T_parent * T_child
function _composeTF(parent, child) {
  const cosP = Math.cos(parent.yaw);
  const sinP = Math.sin(parent.yaw);
  return {
    tx: parent.tx + child.tx * cosP - child.ty * sinP,
    ty: parent.ty + child.tx * sinP + child.ty * cosP,
    yaw: parent.yaw + child.yaw,
  };
}

// Lazy helper — use the same quaternionToYaw logic before it's defined
function _quaternionToYaw(q) {
  if (!q) return 0;
  const siny = 2 * ((q.w ?? 1) * (q.z ?? 0) + (q.x ?? 0) * (q.y ?? 0));
  const cosy = 1 - 2 * ((q.y ?? 0) ** 2 + (q.z ?? 0) ** 2);
  return Math.atan2(siny, cosy);
}

// Try to resolve map → base_footprint (or base_link) from TF buffer
function _poseFromTF(store) {
  const mapOdom =
    _tfBuffer[_tfKey("map", "odom")] ||
    _tfBuffer[_tfKey("map", "odom_combined")];
  const odomBase =
    _tfBuffer[_tfKey("odom", "base_footprint")] ||
    _tfBuffer[_tfKey("odom", "base_link")] ||
    _tfBuffer[_tfKey("odom_combined", "base_footprint")] ||
    _tfBuffer[_tfKey("odom_combined", "base_link")];

  if (!mapOdom || !odomBase) return false;

  const { tx, ty, yaw } = _composeTF(mapOdom, odomBase);
  store.updatePose(tx, ty, yaw);
  return true;
}

function _findDockById(store, dockId) {
  return store.dockStations.find((dock) => dock.id === dockId) ?? null;
}

function _resolveDockServiceResult(rawResult) {
  const text = String(rawResult ?? "").trim();
  const lower = text.toLowerCase();
  let parsed = null;

  if (text.startsWith("{") || text.startsWith("[")) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = null;
    }
  }

  const explicitSuccess =
    typeof parsed?.success === "boolean" ? parsed.success
    : typeof parsed?.succeeded === "boolean" ? parsed.succeeded
    : typeof parsed?.result === "boolean" ? parsed.result
    : lower === "true" ? true
    : lower === "false" ? false
    : /(?:^|[\s"'_{])success(?:ful)?(?:[\s"'_:=-]+)(true|false)/i.test(text)
      ? /(?:^|[\s"'_{])success(?:ful)?(?:[\s"'_:=-]+)true/i.test(text)
    : /(?:^|[\s"'_{])failed?(?:[\s"'_:=-]+)(true|false)/i.test(text)
      ? !/(?:^|[\s"'_{])failed?(?:[\s"'_:=-]+)true/i.test(text)
    : null;

  const accepted =
    explicitSuccess !== false &&
    !/\b(error|warn|not found|rejected|invalid|cannot|failed)\b/i.test(lower);

  const completed =
    explicitSuccess !== null ||
    /\b(docked|undocked|completed|complete|done|finished)\b/i.test(lower);

  const success =
    explicitSuccess !== null
      ? explicitSuccess
      : !/\b(failed|error)\b/i.test(lower);

  return { text, accepted, completed, success };
}

export function useROS() {
  const store = useRobotStore();
  const toast = useToast();

  // ── Connection ──────────────────────────────────────────────────────────────

  function connect(url) {
    if (_ros) disconnect();

    _ros = new ROSLIB.Ros({ url });

    _ros.on("connection", () => {
      console.log("%c[ROS] Connected to WebSocket: " + url, "color:#22c55e;font-weight:bold;font-size:12px");
      _connected.value = true;
      store.setConnected(true);
      _subscribeAll();
      // Re-publish keepout zones dari localStorage agar costmap filter ter-restore
      if (store.keepoutZones.length > 0) {
        setTimeout(() => updateKeepoutZones(store.keepoutZones), 2000);
      }
    });

    _ros.on("error", (err) => {
      console.error("%c[ROS] WebSocket Error!", "color:#ef4444;font-weight:bold", err);
    });

    _ros.on("close", () => {
      console.warn("%c[ROS] Connection Closed", "color:#f59e0b;font-weight:bold");
      _connected.value = false;
      store.setConnected(false);
      _lastAmclTime = 0;
      // Clear TF buffer so stale transforms from old session are not reused
      Object.keys(_tfBuffer).forEach((k) => delete _tfBuffer[k]);
    });
  }

  function disconnect() {
    if (_ros) {
      _ros.close();
      _ros = null;
    }
  }

  // ── Subscriptions ───────────────────────────────────────────────────────────

  function _subscribeAll() {
    _subscribeMap();
    _subscribePose();
    _subscribePath();
    _subscribeNavGoalStatus();
    _subscribeMissionStatus();
    _subscribeMissionFeedback();
    _subscribeDockStatus();
    _subscribeLaserScan();
    _subscribeParticleCloud();
    _subscribeRobotDescription();
    _subscribeCostmap();
    _subscribeBattery();
    _subscribeRobotStatus();
  }

  // /navigate_to_pose/_action/status — deteksi selesai untuk navigateTo() single goal
  function _subscribeNavGoalStatus() {
    const topic = new ROSLIB.Topic({
      ros: _ros,
      name: '/navigate_to_pose/_action/status',
      messageType: 'action_msgs/msg/GoalStatusArray',
    });
    topic.subscribe((msg) => {
      // Hanya reset jika tidak sedang mission (mission punya status-nya sendiri)
      if (_missionRunning) return;
      const list = msg.status_list ?? [];
      if (list.length === 0) return;

      const lastStatus = list[list.length - 1];
      const status = lastStatus.status;

      // status 4=SUCCEEDED, 5=CANCELED, 6=ABORTED
      if (status >= 4 && store.navStatus === 'navigating') {
        if (status === 5) toast.warning("Navigasi dibatalkan.");
        if (status === 6) toast.error("Navigasi gagal: Terhalang rintangan atau target tidak valid.");

        store.setNavStatus('idle');
        store.setNavGoal(null);
        store.setPlannedPath([]);
      }
    });
  }

  // /mission_plan/_action/status — deteksi goal selesai untuk advance waypoint
  function _subscribeMissionStatus() {
    const topic = new ROSLIB.Topic({
      ros: _ros,
      name: '/mission_plan/_action/status',
      messageType: 'action_msgs/msg/GoalStatusArray',
    });
    topic.subscribe((msg) => {
      if (!_missionRunning) return;
      const list = msg.status_list ?? [];
      if (list.length === 0) return;

      const lastStatus = list[list.length - 1];
      const status = lastStatus.status;

      // status 4=SUCCEEDED, 5=CANCELED, 6=ABORTED
      if (status >= 4) {
        console.info('[useROS] Mission goal finished', status);
        if (status === 5) toast.warning("Misi waypoint dibatalkan.");
        if (status === 6) {
          toast.error("Misi waypoint gagal (Aborted).");
          _missionRunning = false;
          store.stopMission();
          return;
        }
        _advanceMission();
      }
    });
  }

  // /mission_plan/_action/feedback — update navStatus di store
  function _subscribeMissionFeedback() {
    const topic = new ROSLIB.Topic({
      ros: _ros,
      name: '/mission_plan/_action/feedback',
      messageType: 'custom_interfaces/action/MissionPlan_FeedbackMessage',
    });
    topic.subscribe((msg) => {
      const sts = msg.feedback?.mission_sts ?? '';
      if (!sts) return;
      console.info('[useROS] /mission_plan/_action/feedback', sts);
      if (sts.startsWith('WAITING PAYLOAD'))  store.setNavStatus('waiting_confirm');
      else if (sts === 'COMPLETED')           store.setNavStatus('idle');
      else if (sts === 'DOCKING')             store.setNavStatus('docking');
      else if (sts.startsWith('EXECUTING'))   store.setNavStatus('executing');
      else                                    store.setNavStatus('navigating');
    });
  }

  // /dock_status — sinkronisasi status docking agar Busy/Available ikut berubah
  function _subscribeDockStatus() {
    const topic = new ROSLIB.Topic({
      ros: _ros,
      name: '/dock_status',
      messageType: 'std_msgs/String',
    });
    topic.subscribe((msg) => {
      const raw = String(msg.data ?? '').trim();
      if (!raw) return;

      const status = raw.toLowerCase();
      console.info('[useROS] /dock_status', raw);

      switch (status) {
        case 'idle':
          store.setDockingStatus('idle');
          if (store.navStatus === 'docking') {
            store.setNavStatus('idle');
          }
          break;
        case 'navigating_to_approach':
        case 'navigating_to_dock':
          store.setDockingStatus('docking');
          store.setNavStatus('docking');
          break;
        case 'docked':
          store.setDockingStatus('docked');
          store.setNavStatus('idle');
          break;
        case 'undocking':
          store.setDockingStatus('undocking');
          store.setNavStatus('docking');
          break;
        case 'error':
          store.setDockingStatus('error');
          store.setNavStatus('error');
          toast.error("Proses docking mengalami kegagalan (Error).");
          break;
        default:
          // Unknown state: keep the raw value only in console.
          break;
      }
    });
  }

  function _subscribeMap() {
    // nav2_map_server publishes /map with transient_local (latched) QoS.
    // JANGAN pakai ROSLIB.Topic.subscribe() karena itu kirim subscribe tanpa QoS
    // duluan → rosbridge buat volatile subscriber → latched message tidak diterima.
    // Solusi: register handler langsung via _ros.on('/map'), lalu kirim SATU
    // subscribe message dengan transient_local QoS.
    _ros.on("/map", (msg) => store.setMapData(msg));

    _ros.callOnConnection({
      op: "subscribe",
      topic: "/map",
      type: "nav_msgs/OccupancyGrid",
      throttle_rate: 0,
      queue_length: 1,
      qos: {
        durability: "transient_local",
        reliability: "reliable",
        history: "keep_last",
        depth: 1,
      },
    });
  }

  function _subscribePose() {
    // ── Primary: TF chain map→odom→base_footprint (50 Hz from SLAM/Nav2) ──────
    // This is exactly what Foxglove uses. Works in both SLAM and navigation mode.
    const tfTopic = new ROSLIB.Topic({
      ros: _ros,
      name: "/tf",
      messageType: "tf2_msgs/TFMessage",
      throttle_rate: 33, // ~30 Hz — cukup untuk visual smooth
    });
    tfTopic.subscribe((msg) => {
      let updated = false;
      for (const t of msg.transforms) {
        _storeTF(t.header.frame_id, t.child_frame_id, t.transform);
        if (
          t.header.frame_id === "map" ||
          t.child_frame_id === "base_footprint" ||
          t.child_frame_id === "base_link"
        ) {
          updated = true;
        }
      }
      if (updated) _poseFromTF(store);
    });

    // Static TF (one-time, e.g. sensor frames)
    const tfStaticTopic = new ROSLIB.Topic({
      ros: _ros,
      name: "/tf_static",
      messageType: "tf2_msgs/TFMessage",
    });
    tfStaticTopic.subscribe((msg) => {
      for (const t of msg.transforms) {
        _storeTF(t.header.frame_id, t.child_frame_id, t.transform);
      }
    });

    // ── Fallback: /amcl_pose (navigation mode, if TF unavailable) ─────────────
    const amclTopic = new ROSLIB.Topic({
      ros: _ros,
      name: "/amcl_pose",
      messageType: "geometry_msgs/PoseWithCovarianceStamped",
    });
    amclTopic.subscribe((msg) => {
      _lastAmclTime = Date.now();
      // Only use as fallback if TF chain not yet available
      if (_tfBuffer[_tfKey("map", "odom")]) return;
      const { x, y } = msg.pose.pose.position;
      const theta = quaternionToYaw(msg.pose.pose.orientation);
      store.updatePose(x, y, theta);
    });

    // ── Fallback: /pose (SLAM Toolbox, if TF unavailable) ─────────────────────
    const slamPoseTopic = new ROSLIB.Topic({
      ros: _ros,
      name: "/pose",
      messageType: "geometry_msgs/PoseWithCovarianceStamped",
    });
    slamPoseTopic.subscribe((msg) => {
      if (_tfBuffer[_tfKey("map", "odom")]) return; // TF lebih akurat
      if (Date.now() - _lastAmclTime < AMCL_TIMEOUT_MS) return;
      const { x, y } = msg.pose.pose.position;
      const theta = quaternionToYaw(msg.pose.pose.orientation);
      store.updatePose(x, y, theta);
    });

    // ── /odom — velocity data only ────────────────────────────────────────────
    const odomTopic = new ROSLIB.Topic({
      ros: _ros,
      name: "/odom",
      messageType: "nav_msgs/Odometry",
    });
    odomTopic.subscribe((msg) => {
      const linear = msg.twist?.twist?.linear?.x || 0;
      const angular = msg.twist?.twist?.angular?.z || 0;
      store.setRobotVelocity(linear, angular);
    });
  }

  function _subscribePath() {
    const topic = new ROSLIB.Topic({
      ros: _ros,
      name: "/plan",
      messageType: "nav_msgs/Path",
    });
    topic.subscribe((msg) => {
      const points = msg.poses.map((p) => ({
        x: p.pose.position.x,
        y: p.pose.position.y,
      }));
      store.setPlannedPath(points);
    });
  }

  function _subscribeLaserScan() {
    const topic = new ROSLIB.Topic({
      ros: _ros,
      name: "/scan",
      messageType: "sensor_msgs/LaserScan",
    });
    topic.subscribe((msg) => store.setLaserScan(msg));
  }

  function _subscribeParticleCloud() {
    const topic = new ROSLIB.Topic({
      ros: _ros,
      name: "/particle_cloud",
      messageType: "nav2_msgs/ParticleCloud",
    });
    topic.subscribe((msg) => {
      // nav2_msgs/ParticleCloud has .particles array of {pose, weight}
      const poses = (msg.particles ?? []).map((p) => ({
        x: p.pose.position.x,
        y: p.pose.position.y,
        theta: quaternionToYaw(p.pose.orientation),
      }));
      store.setParticleCloud(poses);
    });
  }

  function _subscribeRobotDescription() {
    const topic = new ROSLIB.Topic({
      ros: _ros,
      name: "/robot_description",
      messageType: "std_msgs/String",
      throttleRate: 0,
      queueSize: 1,
    });
    topic.subscribe((msg) => {
      const fp = _parseUrdfFootprint(msg.data);
      if (fp) {
        store.setRobotFootprint(fp);
      }
    });
    // Request with transient_local QoS — robot_description is a latched topic
    if (topic.subscribeId) {
      _ros.callOnConnection({
        op: "subscribe",
        id: topic.subscribeId,
        topic: "/robot_description",
        type: "std_msgs/String",
        throttle_rate: 0,
        queue_length: 1,
        qos: {
          durability: "transient_local",
          reliability: "reliable",
          history: "keep_last",
          depth: 1,
        },
      });
    }
  }

  function _parseUrdfFootprint(urdfString) {
    try {
      const doc = new DOMParser().parseFromString(urdfString, "text/xml");
      // Check for parse error
      if (doc.querySelector("parsererror")) return null;
      // Try common base link names in priority order
      for (const name of ["base_footprint", "base_link", "chassis", "body"]) {
        const link = doc.querySelector(`link[name="${name}"]`);
        if (!link) continue;
        // Prefer collision geometry for accurate footprint; fall back to visual
        const box =
          link.querySelector("collision geometry box") ||
          link.querySelector("visual geometry box");
        if (box) {
          const parts = box
            .getAttribute("size")
            .trim()
            .split(/\s+/)
            .map(Number);
          // URDF box size="length(x) width(y) height(z)"
          if (parts.length >= 2 && parts[0] > 0 && parts[1] > 0) {
            return { length: parts[0], width: parts[1] };
          }
        }
        const cyl =
          link.querySelector("collision geometry cylinder") ||
          link.querySelector("visual geometry cylinder");
        if (cyl) {
          const r = Number(cyl.getAttribute("radius"));
          if (r > 0) return { length: r * 2, width: r * 2 };
        }
      }
      return null;
    } catch {
      return null;
    }
  }

  function _subscribeCostmap() {
    const topic = new ROSLIB.Topic({
      ros: _ros,
      name: "/global_costmap/costmap",
      messageType: "nav_msgs/OccupancyGrid",
      throttleRate: 500,
      queueSize: 1,
    });
    topic.subscribe((msg) => store.setCostmapData(msg));
  }

  function _subscribeRobotStatus() {
    const topic = new ROSLIB.Topic({
      ros: _ros,
      name: "/robot_status",
      messageType: "custom_interfaces/msg/RobotStatus",
      queueSize: 1,
    });
    topic.subscribe((msg) => {
      const sts = msg.robot_current_sts;

      console.log("%c[DATA] /robot_status raw message:", "color:#38bdf8;font-weight:bold", {
        robot_docked: msg.robot_docked,
        robot_undocked: msg.robot_undocked,
        charging_state: msg.charging_state,
        battery_voltage: msg.battery_voltage,
        battery_percentage: msg.battery_percentage,
        robot_current_sts: msg.robot_current_sts,
      });

      // ── 1. Update Navigation Status ───────────────────────────────────────
      // Real robot: 0=Available, 1=Busy
      // Simulasi:   0=IDLE, 1=NAVIGATING, 2=DOCKING, 3=UNDOCKING, 4=CHARGING, 5=ERROR
      if (sts === 1) {
        store.setNavStatus("navigating");
      } else if (sts === 2 || sts === 3) {
        store.setNavStatus("docking");
      } else if (sts === 5) {
        store.setNavStatus("error");
      } else {
        store.setNavStatus("idle");
      }

      // ── 2. Update Docking Status ──────────────────────────────────────────
      if (msg.robot_docked) {
        store.setDockingStatus("docked");
      } else if (sts === 2) {
        store.setDockingStatus("docking");
      } else if (sts === 3) {
        store.setDockingStatus("undocking");
      } else if (sts === 5) {
        store.setDockingStatus("error");
      } else if (msg.robot_undocked) {
        if (store.dockingStatus === "docked") {
          store.setDockingStatus("idle");
        }
      }

      // Jika robot sedang bergerak (Busy) tapi flag docked/undocked tidak jelas,
      // biarkan state docking diatur oleh trigger service call.

      // ── 3. Update Battery & Charging ──────────────────────────────────────
      const battPct = msg.battery_percentage != null ? Math.round(msg.battery_percentage) : (store.batteryPercent ?? 0);
      const battVolt = msg.battery_voltage ?? null;
      
      // Charging jika flag charging_state true ATAU fisik robot sedang docked
      const isCharging = msg.charging_state || msg.robot_docked;
      store.setBattery(battPct, isCharging, battVolt);
    });
  }

  function _subscribeBattery() {
    // /battery_state mungkin tidak aktif di robot — charging state
    // sudah di-handle via /robot_status (charging_state field).
    // Subscribe tetap dipertahankan sebagai fallback jika topic ada.
    const topic = new ROSLIB.Topic({
      ros: _ros,
      name: "/battery_state",
      messageType: "sensor_msgs/BatteryState",
      throttleRate: 1000,
      queueSize: 1,
    });
    topic.subscribe((msg) => {
      const percent = Math.round(msg.percentage * 100);
      const isDocked = store.dockingStatus === "docked";
      const charging = msg.power_supply_status === 1 || isDocked;
      store.setBattery(percent, charging);
    });
  }

  // ── Navigate to single pose ─────────────────────────────────────────────────

  /**
   * Navigate to a single map-frame pose.
   * @param {number} x - metres
   * @param {number} y - metres
   * @param {number} theta - radians (yaw)
   */
  function navigateTo(x, y, theta = null) {
    if (!_ros) return;

    store.setNavGoal({ x, y, theta });
    store.setNavStatus("navigating");

    // Use /goal_pose topic — Nav2 bt_navigator listens to this
    const goalTopic = new ROSLIB.Topic({
      ros: _ros,
      name: "/goal_pose",
      messageType: "geometry_msgs/PoseStamped",
    });

    // theta=null → kirim quaternion identity, Nav2 akan tentukan orientasi sendiri
    const orientation = theta !== null ? yawToQuaternion(theta) : { x: 0, y: 0, z: 0, w: 1 };

    goalTopic.publish({
      header: {
        frame_id: "map",
        stamp: rosTime(),
      },
      pose: {
        position: { x, y, z: 0 },
        orientation,
      },
    });
  }

  // ── Follow waypoints (mission) ──────────────────────────────────────────────

  /**
   * Send a list of waypoints to nav2_waypoint_follower.
   * @param {Array<{x, y, theta}>} waypoints
   */
  /**
   * Sequential waypoint execution via /goal_pose.
   * rosbridge does not support ROS2 action clients for nav2_msgs,
   * so we send one goal at a time and advance on goal completion.
   */
  function followWaypoints(waypoints) {
    if (!_ros || waypoints.length === 0) return;

    console.info('[useROS] followWaypoints called', {
      waypointCount: waypoints.length,
      stations: waypoints.map((w) => w.stationId ?? ''),
    });
    _missionWaypoints = [...waypoints];
    _missionIndex = 0;
    _missionRunning = true;
    store.startMission();
    _sendMissionGoal();
  }

  function _sendMissionGoal() {
    if (_missionGoalTimeout) {
      clearTimeout(_missionGoalTimeout);
      _missionGoalTimeout = null;
    }

    if (!_missionRunning || _missionIndex >= _missionWaypoints.length) {
      _missionRunning = false;
      store.stopMission();
      return;
    }

    const wp = _missionWaypoints[_missionIndex];
    const { task = 'Pick', continueMode = 'Auto' } = wp;
    store.setCurrentWaypointIndex(_missionIndex);
    store.setNavStatus('navigating');

    console.info('[useROS] Sending mission goal to /mission_plan', {
      index: _missionIndex,
      stationId: wp.stationId ?? '',
      task,
      continueMode,
    });
    // Send action goal to /mission_plan
    // Completion dideteksi via _subscribeMissionStatus() yang listen ke
    // /mission_plan/_action/status topic — bukan via _ros.on(goalId) karena
    // roslibjs SocketAdapter tidak emit event untuk action_result/action_feedback.
    _currentMissionGoalId = `mg_${Date.now()}_${_missionIndex}`;
    _ros.callOnConnection({
      op: 'send_action_goal',
      action: '/mission_plan',
      action_type: 'custom_interfaces/action/MissionPlan',
      args: {
        station_id: wp.stationId ?? '',
        dest_tasks: { NoAction: 0, Pick: 1, Drop: 2, DropPick: 3 }[task] ?? 0,
        continue_mode: continueMode !== 'Manual',
      },
      id: _currentMissionGoalId,
    });

    // Watchdog — fallback jika action server tidak merespons
    const timeoutMs = (store.missionTimeoutSec ?? 120) * 1000;
    _missionGoalTimeout = setTimeout(() => {
      if (_missionRunning) {
        console.warn(`[useROS] Mission goal ${_missionIndex + 1} timed out, advancing`);
        _advanceMission();
      }
    }, timeoutMs);
  }

  let _advancing = false; // guard: cegah double-advance dari status topic burst

  function _advanceMission() {
    if (!_missionRunning || _advancing) return;
    _advancing = true;

    if (_missionGoalTimeout) {
      clearTimeout(_missionGoalTimeout);
      _missionGoalTimeout = null;
    }
    _currentMissionGoalId = null;
    _missionIndex++;

    if (_missionIndex >= _missionWaypoints.length) {
      _missionRunning = false;
      _advancing = false;
      store.stopMission();
    } else {
      // Delay: beri waktu status topic reset sebelum goal baru dikirim
      setTimeout(() => {
        _advancing = false;
        _sendMissionGoal();
      }, 1000);
    }
  }

  // ── Cancel navigation ───────────────────────────────────────────────────────

  function cancelNavigation() {
    _missionRunning = false;
    _advancing = false;
    _missionWaypoints = [];
    _missionIndex = 0;
    if (_missionGoalTimeout) {
      clearTimeout(_missionGoalTimeout);
      _missionGoalTimeout = null;
    }
    if (_navGoalHandle) {
      _navGoalHandle.cancel();
      _navGoalHandle = null;
    }

    if (_ros) {
      // Cancel active /mission_plan action goal
      if (_currentMissionGoalId) {
        _ros.callOnConnection({
          op: 'cancel_action_goal',
          action: '/mission_plan',
          id: _currentMissionGoalId,
        });
        _currentMissionGoalId = null;
      }
      // Also cancel any pending Nav2 goal (single navigateTo calls)
      const cancelSvc = new ROSLIB.Service({
        ros: _ros,
        name: "/navigate_to_pose/_action/cancel_goal",
        serviceType: "action_msgs/srv/CancelGoal",
      });
      cancelSvc.callService(
        new ROSLIB.ServiceRequest({
          goal_info: {
            goal_id: { uuid: new Array(16).fill(0) },
            stamp: { sec: 0, nanosec: 0 },
          },
        }),
        () => console.log("[useROS] Navigation cancelled"),
        (err) => console.warn("[useROS] Cancel failed:", err),
      );
    }
    store.stopMission();
    store.setNavStatus("idle");
  }

  // ── Mission confirm (Manual mode) ───────────────────────────────────────────

  /**
   * Konfirmasi ke robot untuk lanjut ke waypoint berikutnya (continue_mode=Manual).
   * Calls /mission_confirm service.
   */
  function confirmMission({ onSuccess, onError } = {}) {
    if (!_ros) return;
    const svc = new ROSLIB.Service({
      ros: _ros,
      name: '/mission_confirm',
      serviceType: 'std_srvs/srv/Trigger',
    });
    svc.callService(
      new ROSLIB.ServiceRequest({}),
      (res) => {
        console.log('[useROS] mission_confirm:', res.message);
        if (res.success) {
          store.setNavStatus('navigating');
          onSuccess?.();
        } else {
          onError?.(res.message);
        }
      },
      (err) => {
        console.warn('[useROS] mission_confirm error:', err);
        onError?.(err);
      },
    );
  }

  // ── Docking ─────────────────────────────────────────────────────────────────

  /**
   * Panggil service /dock_command.
   * Request : { action: string, station_id: string }
   * Response: { result: string }
   */
  /**
   * Call /robot_mode service — switch robot antara "map" dan "nav".
   * Returns Promise<string> (result dari robot).
   */
  function callRobotModeService(mode) {
    return new Promise((resolve, reject) => {
      if (!_ros) return reject(new Error("ROS not connected"));
      const svc = new ROSLIB.Service({
        ros: _ros,
        name: "/robot_mode",
        serviceType: "custom_interfaces/srv/RobotMode",
      });
      console.log("%c[ROS] CALL /robot_mode", "color:#a78bfa;font-weight:bold", { robot_mode: mode });
      svc.callService(
        new ROSLIB.ServiceRequest({ robot_mode: mode }),
        (res) => {
          console.log("[useROS] robot_mode result:", res.result);
          if (res.result.toLowerCase().includes("fail") || res.result.toLowerCase().includes("error")) {
            toast.error(`Gagal ganti mode: ${res.result}`);
          }
          resolve(res.result);
        },
        (err) => {
          console.warn("[useROS] robot_mode error:", err);
          toast.error("Service /robot_mode tidak merespon.");
          reject(err);
        },
      );
    });
  }

  function _callDockService({ action, station_id = "" }, { onSuccess, onError } = {}) {
    if (!_ros) return;
    const svc = new ROSLIB.Service({
      ros: _ros,
      name: "/dock_command",
      serviceType: "custom_interfaces/srv/DockCommand",
    });
    console.log("%c[ROS] CALL /dock_command", "color:#22c55e;font-weight:bold", { action, station_id });
    svc.callService(
      new ROSLIB.ServiceRequest({ action, station_id }),
      (res) => {
        console.log("[useROS] dock_command result:", res.result);
        console.log("%c[Docking] service raw result", "color:#38bdf8;font-weight:bold", {
          action,
          station_id,
          result: res.result,
        });

        const outcome = _resolveDockServiceResult(res.result);
        if (!outcome.accepted || (outcome.completed && !outcome.success)) {
          toast.error(`Docking ${action} gagal: ${res.result}`);
        }

        onSuccess?.(res.result);
      },
      (err) => {
        console.warn("[useROS] dock_command error:", err);
        console.warn("[Docking] service call failed:", { action, station_id, err });
        toast.error(`Gagal memanggil service docking: ${err}`);
        onError?.(err);
      },
    );
  }

  /**
   * Kirim robot ke dock station.
   * Station harus sudah di-register via configStation sebelumnya.
   * @param {object} station - { name, ... }
   */
  function sendToDock(station) {
    if (!_ros) return;
    if (station?.id) store.setActiveDockId(station.id);
    store.setDockingStatus("docking");
    store.setNavStatus("docking");
    _callDockService(
      { action: "dock", station_id: station.name },
      {
        onSuccess: (result) => {
          const outcome = _resolveDockServiceResult(result);
          console.log("%c[Docking] dock service parsed", "color:#f59e0b;font-weight:bold", {
            station: station.name,
            result,
            outcome,
          });
          if (!outcome.accepted || (outcome.completed && !outcome.success)) {
            store.setDockingStatus("error");
            store.setNavStatus("idle");
            return;
          }
          if (outcome.completed && outcome.success) {
            store.setDockingStatus("docked");
            store.setNavStatus("idle");
          }
        },
        onError: () => {
          store.setDockingStatus("error");
          store.setNavStatus("idle");
        },
      },
    );
  }

  function undock(station = null) {
    if (!_ros) return;
    const activeDock =
      station ??
      _findDockById(store, store.activeDockId) ??
      _findDockById(store, store.autoDockTargetId);
    const stationName = activeDock?.name ?? "";

    store.setDockingStatus("undocking");
    _callDockService(
      { action: "undock", station_id: stationName },
      {
        onSuccess: (result) => {
          const outcome = _resolveDockServiceResult(result);
          console.log("%c[Docking] undock service parsed", "color:#f59e0b;font-weight:bold", {
            station: stationName,
            result,
            outcome,
          });
          if (!outcome.accepted || (outcome.completed && !outcome.success)) {
            store.setDockingStatus("error");
            store.setNavStatus("idle");
            return;
          }
          if (outcome.completed && outcome.success) {
            store.setDockingStatus("idle");
            store.setNavStatus("idle");
          }
        },
        onError: () => {
          store.setDockingStatus("error");
          store.setNavStatus("idle");
        },
      },
    );
  }

  function cancelDocking() {
    if (!_ros) return;
    _callDockService({ action: "cancel", station_id: "" });
    store.setDockingStatus("idle");
    store.setNavStatus("idle");
  }

  // ── Map loader ──────────────────────────────────────────────────────────────

  /**
   * Load a new map via nav2_map_server service.
   * @param {string} yamlPath - absolute path on the robot filesystem
   */
  function loadMap(yamlPath) {
    if (!_ros) return;
    const service = new ROSLIB.Service({
      ros: _ros,
      name: "/map_server/load_map",
      serviceType: "nav2_msgs/srv/LoadMap",
    });
    service.callService(
      new ROSLIB.ServiceRequest({ map_url: yamlPath }),
      (result) => console.log("[useROS] loadMap result:", result),
      (err) => console.warn("[useROS] loadMap failed:", err),
    );
  }

  // ── Map saver ───────────────────────────────────────────────────────────────

  /**
   * Save the current map via nav2_map_server service.
   * @param {string} filename - base name (no extension) for the saved map
   * @param {{ onSuccess?: () => void, onError?: (err: string) => void }} callbacks
   */
  function saveMap(filename = "amr_map", { onSuccess, onError } = {}) {
    if (!_ros) return;

    const service = new ROSLIB.Service({
      ros: _ros,
      name: "/map_saver/save_map",
      serviceType: "nav2_msgs/srv/SaveMap",
    });

    const request = new ROSLIB.ServiceRequest({
      map_topic: "/map",
      map_url: `/maps/${filename}`,
      image_format: "pgm",
      free_thresh: 0.25,
      occupied_thresh: 0.65,
    });

    service.callService(
      request,
      (result) => {
        if (result.result) {
          onSuccess?.();
        } else {
          console.error("[useROS] Map save failed");
          onError?.("Map save failed");
        }
      },
      (err) => {
        console.error("[useROS] Map save error:", err);
        onError?.(String(err));
      },
    );
  }

  // ── Teleop (cmd_vel) ─────────────────────────────────────────────────────────

  let _cmdVelPub = null;
  function _getCmdVelPub() {
    if (!_cmdVelPub && _ros) {
      _cmdVelPub = new ROSLIB.Topic({
        ros: _ros,
        name: "/cmd_vel",
        messageType: "geometry_msgs/Twist",
      });
    }
    return _cmdVelPub;
  }

  function publishCmdVel(linear, angular) {
    const pub = _getCmdVelPub();
    if (!pub) return;
    pub.publish(
      new ROSLIB.Message({
        linear: { x: linear, y: 0, z: 0 },
        angular: { x: 0, y: 0, z: angular },
      }),
    );
  }

  function stopRobot() {
    publishCmdVel(0, 0);
  }

  // ── Publish initial pose (AMCL) ─────────────────────────────────────────────

  function setInitialPose(x, y, theta) {
    if (!_ros) return;

    const topic = new ROSLIB.Topic({
      ros: _ros,
      name: "/initialpose",
      messageType: "geometry_msgs/PoseWithCovarianceStamped",
    });

    // Use stamp {sec:0} so AMCL accepts the pose regardless of sim time offset
    topic.publish({
      header: { frame_id: "map", stamp: { sec: 0, nanosec: 0 } },
      pose: {
        pose: {
          position: { x, y, z: 0 },
          orientation: yawToQuaternion(theta),
        },
        covariance: Array(36)
          .fill(0)
          .map((_, i) => (i === 0 || i === 7 || i === 35 ? 0.25 : 0)),
      },
    });
  }

  // ── Mission payload publisher ────────────────────────────────────────────────

  /**
   * Publish mission payload ke /amr/mission_payload sesuai format:
   * { destNum, destPoint: [1,2,...], taskPoint: [1,2,...], cntMode: [1,2,...] }
   * taskPoint: 1=Pick, 2=Drop | cntMode: 1=Auto, 2=Manual
   */
  function publishMissionPayload(waypoints) {
    if (!_ros) return;

    console.info('[useROS] Publishing mission payload to /amr/mission_payload', {
      waypointCount: waypoints.length,
      payload: {
        destNum: waypoints.length,
        destPoint: waypoints.map((w) => w.destPoint ?? 0),
        stationId: waypoints.map((w) => w.stationId ?? ''),
        taskPoint: waypoints.map((w) => ({ NoAction: 0, Pick: 1, Drop: 2, DropPick: 3 }[w.task] ?? 0)),
        cntMode: waypoints.map((w) => (w.continueMode === "Auto" ? 1 : 2)),
      },
    });
    const topic = new ROSLIB.Topic({
      ros: _ros,
      name: "/amr/mission_payload",
      messageType: "std_msgs/String",
    });

    const payload = {
      destNum: waypoints.length,
      destPoint: waypoints.map((w) => w.destPoint ?? 0),
      stationId: waypoints.map((w) => w.stationId ?? ''),
      taskPoint: waypoints.map((w) => ({ NoAction: 0, Pick: 1, Drop: 2, DropPick: 3 }[w.task] ?? 0)),
      cntMode: waypoints.map((w) => (w.continueMode === "Auto" ? 1 : 2)),
    };

    topic.publish({ data: JSON.stringify(payload) });
  }

  // ── Keepout zone publisher ───────────────────────────────────────────────────

  /**
   * Publish the full list of keepout zones to the ROS keepout_mask_server.
   * @param {Array<{id, name, polygon: Array<{x, y}>}>} zones
   */
  function updateKeepoutZones(zones) {
    if (!_ros) return;

    const topic = new ROSLIB.Topic({
      ros: _ros,
      name: "/amr/keepout_zones",
      messageType: "std_msgs/String",
    });

    const payload = zones.map((z) => ({ polygon: z.polygon }));
    topic.publish({ data: JSON.stringify(payload) });
  }

  // ── Station Config ───────────────────────────────────────────────────────────

  /**
   * Register atau hapus station di robot via /station_config service.
   * station_type: 0=Pick, 1=Drop, 2=Pick & Drop, 3=Charging
   * action:       0=delete, 1=save
   * @param {object} opts - { station_id, station_type, action, x, y, yaw }
   */
  function configStation({
    station_id, station_type = 2, action = 1,
    x = 0, y = 0, yaw = 0,
  }) {
    return new Promise((resolve, reject) => {
      if (!_ros) { resolve(null); return; }
      const svc = new ROSLIB.Service({
        ros: _ros,
        name: "/station_config",
        serviceType: "custom_interfaces/srv/StationConfig",
      });
      svc.callService(
        new ROSLIB.ServiceRequest({
          station_id,
          type: station_type,
          action,
          x_pose: x,
          y_pose: y,
          yaw_pose: yaw,
        }),
        (res) => { console.log(`[useROS] station_config (${action === 1 ? "save" : "delete"}) "${station_id}":`, res.result); resolve(res.result); },
        (err) => { console.warn("[useROS] station_config error:", err); reject(err); },
      );
    });
  }

  // ── Helpers ──────────────────────────────────────────────────────────────────

  function rosTime() {
    const now = Date.now();
    return {
      sec: Math.floor(now / 1000),
      nanosec: (now % 1000) * 1e6,
    };
  }

  function yawToQuaternion(yaw) {
    const cy = Math.cos(yaw * 0.5);
    const sy = Math.sin(yaw * 0.5);
    return { x: 0, y: 0, z: sy, w: cy };
  }

  function quaternionToYaw(q) {
    return Math.atan2(
      2 * (q.w * q.z + q.x * q.y),
      1 - 2 * (q.y * q.y + q.z * q.z),
    );
  }

  return {
    ros: _ros,
    connected: readonly(_connected),
    connect,
    disconnect,
    navigateTo,
    followWaypoints,
    cancelNavigation,
    confirmMission,
    sendToDock,
    undock,
    cancelDocking,
    publishCmdVel,
    stopRobot,
    loadMap,
    saveMap,
    setInitialPose,
    updateKeepoutZones,
    publishMissionPayload,
    configStation,
    callRobotModeService,
  };
}
