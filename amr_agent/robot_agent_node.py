#!/usr/bin/env python3
"""
Robot agent — mode supervisor.

The gap this fills: mode is currently a *launch argument*. bringup.launch.py
evaluates `use_slam` once, through IfCondition, and there is no runtime path to
change it. Switching between mapping and navigation therefore means killing the
whole stack and starting it again by hand — which is why the backend's
/api/mode/switch does nothing but persist a setting and return a sentence
telling a human to run a shell command.

This node makes /robot_mode real. It owns the two sub-launches as child
processes and brings them up and down on request.

Deliberately not lifecycle transitions: both slam_toolbox and AMCL publish the
map->odom transform, so having both resident and merely deactivated is a TF
conflict waiting to happen. Separate processes cannot fight over a transform
that only one of them is alive to publish.

Interfaces
----------
Desired mode
------------
The registry holds what a robot is *supposed* to be doing (robots.desired_mode)
and this agent reconciles towards it on every sync. Before that existed the mode
lived only in this process and /robot_mode was a command, so an agent that
restarted came back idle with nothing anywhere reporting it — and a robot needed
somebody to press a button before it would work at all.

`nav` is the resting state and the default. Nav2 running is not the robot
moving: an idle planner plans nothing, and the robot only moves when a mission
gives it a goal.

service  /robot_mode          custom_interfaces/srv/RobotMode
           request.robot_mode : "map" | "nav" | "nav|<map yaml path>" | "stop"
           response.result    : "ACCEPTED ..." | "REJECTED ..."
service  /map_save            custom_interfaces/srv/RobotMode
           request.robot_mode : the map name to publish under
           response.result    : "SAVED <map id> v<n>"        published to the registry
                                "SAVED_LOCAL <path>"          written here only, no backend
                                "REJECTED ..."                not saved
service  /mission_poll        std_srvs/Trigger
           Check the registry for work now, instead of waiting for the next
           sync. A nudge, not a command: the run itself is dispatched through
           the backend, so this being missed costs latency and nothing else.

calls    /mission_plan        custom_interfaces/action/MissionPlan
           One goal per mission step. The *robot* executes a mission: the
           previous UI held the step index in tab memory and sent goals from
           there, so closing the tab stranded a robot mid-route. Lap and step
           are reported back to the registry, so an agent restarted mid-route
           reads its own progress and carries on.

topic    /amr/zones           std_msgs/String  (JSON, latched)
           The map's zones as polygons, for zone_mask_server to rasterise into
           the costmap filter masks Nav2 reads. Polygons rather than a mask
           image: a mask belongs to one resolution and cannot be edited back
           into corners. Republished only when the set changes.

calls    /station_config      custom_interfaces/srv/StationConfig
           Registers the loaded map's stations with mission_manager, which
           keeps them in memory only and loses them on every restart. Pushed
           when a map is loaded, and again whenever the registry's station set
           changes — a dragged dock moves no map, so a load-only push would
           leave the robot driving to where the station used to be.

service  /mission_confirm     std_srvs/Trigger   (mission_via=nav only)
           Somebody took the order at a `confirm` stop; drive on. With
           mission_via=mission_plan the mission manager serves this name
           itself, so the kiosk calls the same service either way.

topic    /amr/kiosk           std_msgs/String  (JSON, latched, 1 Hz)
           What the screen on the robot shows: phase (idle, moving, near,
           blocked, waiting, thanks, done, failed, off), mission name, route as
           station names, current step, seconds left to confirm. See delivery.py.

topic    /robot_mode_status   std_msgs/String  (JSON, 1 Hz)
           {"mode", "state", "map", "map_id", "detail", "managed", "backend",
            "teleop"}
topic    /teleop/cmd_vel      geometry_msgs/Twist   (in)
topic    /cmd_vel             geometry_msgs/Twist   (out, relayed)

Teleop relay
------------
A browser driving a robot over wifi cannot be trusted to keep talking. Nothing
in this stack arbitrates /cmd_vel and nothing times it out, so a command sent
just before the link drops is the last thing the robot ever hears — and it
keeps executing it. On a 100 kg machine in a warehouse that is not a rough
edge, it is a defect.

So the browser publishes to /teleop/cmd_vel, never to /cmd_vel. This node
republishes at a steady rate and stops the robot when the stream goes quiet.
The relay runs only while mapping: in navigation mode Nav2 owns /cmd_vel, and
a second publisher would fight it.

/map_save reuses the RobotMode service type because its `string in, string out`
shape is exactly what is needed, and adding a purpose-built .srv means
regenerating custom_interfaces and rebuilding a 5.6 GB image. The field is
misnamed and that is deliberate: documented here rather than churning the
interface package for a first iteration.

Map handling follows the decision that the backend is the registry and the
robot keeps a cache. A map is still *born* here — slam_toolbox writes it to
this robot's own disk, so a survey survives the server being unreachable — and
is published afterwards. Loading goes the other way: the backend says which map
this robot should be on, and the agent downloads it only when its local copy
does not match the recorded content hash.

The request returns as soon as the switch is accepted, not when it finishes: a
mode change takes ten to twenty seconds, and a service call blocking that long
over rosbridge gives the operator no idea whether anything is happening. The
status topic carries the progress instead.

It is published at 1 Hz on purpose. /robot_status next door publishes only on
change and has no timer, so any subscriber that connects while the robot is
idle learns nothing and waits forever. This one repeats itself.
"""

import hashlib
import json
import math
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import Twist
from std_msgs.msg import String
from std_srvs.srv import Trigger

from nav2_msgs.action import NavigateToPose
from nav2_msgs.srv import LoadMap, ReloadDockDatabase, SaveMap

from agent_state import TERMINAL_STATES, AgentState
from delivery import (
    CONFIRMED,
    PHASE_BLOCKED,
    PHASE_DONE,
    PHASE_FAILED,
    PHASE_IDLE,
    PHASE_MOVING,
    PHASE_NEAR,
    PHASE_OFF,
    PHASE_THANKS,
    PHASE_WAITING,
    TIMED_OUT,
    ConfirmGate,
    ProgressWatch,
    kiosk_status,
)
from backend_client import BackendClient, BackendError
from custom_interfaces.action import MissionPlan
from custom_interfaces.srv import RobotMode, StationConfig

# Mode names on the wire. "map" and "nav" are what the existing frontend
# already sends to /robot_mode.
MODE_MAP = "map"
MODE_NAV = "nav"
MODE_STOP = "stop"
MODE_UNKNOWN = "unknown"

# The registry does not speak this agent's vocabulary: it says "idle" where
# /robot_mode says "stop". Translated in one place and in both directions,
# because an untranslated value is not an error anywhere — _reconcile_mode
# simply ignores it, and the robot never parks.
REGISTRY_TO_MODE = {"nav": MODE_NAV, "map": MODE_MAP, "idle": MODE_STOP}
MODE_TO_REGISTRY = {MODE_NAV: "nav", MODE_MAP: "map", MODE_STOP: "idle"}

STATE_IDLE = "idle"
STATE_STARTING = "starting"
STATE_RUNNING = "running"
STATE_STOPPING = "stopping"
STATE_FAILED = "failed"

DEFAULT_MAP = "/maps/amr_map.yaml"

# How long a child gets to shut down politely before it is killed.
SIGINT_GRACE_S = 8.0
SIGTERM_GRACE_S = 4.0

# Nodes that prove a stack is actually up, rather than merely spawned.
SLAM_MARKER_NODES = ("slam_toolbox", "map_saver")
NAV_MARKER_NODES = ("planner_server", "controller_server", "bt_navigator")
READY_TIMEOUT_S = 45.0

# The action a navigation stack must be able to accept before it is any use.
#
# A Nav2 node existing is not a Nav2 node that works: the lifecycle manager
# configures and activates them afterwards, and the action server appears only
# at the end of that. Reporting `running` in between produced exactly one bug —
# a mission dispatched into the gap, and the first goal came straight back as
# "Nav2 not available".
NAV_READY_ACTION = "navigate_to_pose"
NAV_ACTIVATE_TIMEOUT_S = 60.0

# Map saving and loading.
MAP_SAVER_SERVICE = "/map_saver/save_map"
STATION_CONFIG_SERVICE = "/station_config"

# Nav2's docking server keeps its destinations in a YAML file and reloads it on
# request. A stack built around that has no /station_config to push to, so the
# same registry is written as a dock database instead. See _write_dock_database.
# Verified against a running Jazzy docking_server: the served name is
# `reload_database`. `reload_dock_database` also shows up in `ros2 service
# list` — a client registers there too — so the list is not evidence that
# anything answers it. `ros2 node info /docking_server` is.
DOCK_RELOAD_SERVICE = "/docking_server/reload_database"

# StationConfig.srv: 0=Pick, 1=Drop, 2=Pick&Drop, 3=Charging. The registry
# stores these as words; this is the only place the numbers are known.
STATION_TYPE_WIRE = {"pick": 0, "drop": 1, "pick_drop": 2, "charging": 3}
STATION_ACTION_SAVE = 1
STATION_ACTION_DELETE = 0

MISSION_ACTION = "/mission_plan"
MISSION_POLL_SERVICE = "/mission_poll"

ZONES_TOPIC = "/amr/zones"
KIOSK_TOPIC = "/amr/kiosk"
MISSION_CONFIRM_SERVICE = "/mission_confirm"
# After "Sudah diambil", the robot waits this long before driving off: the
# person is still standing at the tray, and a robot pulling away under their
# hands is the moment they stop trusting it.
THANKS_HOLD_S = 3.0
# How long "all delivered" stays on the screen before it goes back to idle.
DONE_HOLD_S = 10.0
# And "I need help" after a failed run. Long, because somebody has to walk over;
# not forever, because the operator may have sorted it out from the web UI.
FAILED_HOLD_S = 300.0

NO_MAP_DETAIL = "No map assigned — nothing to navigate on"
# How long to wait before trying a failed stack again. Long enough that the
# error stays readable in the log, short enough that a transient fault heals.
MODE_RETRY_COOLDOWN_S = 60.0


def _latched_qos() -> QoSProfile:
    """
    Keep the last message for anyone who subscribes later.

    zone_mask_server may start after this node, and a zone list published into
    an empty graph is a map with no zones on it — with nothing anywhere saying
    the zones were ever sent.
    """
    return QoSProfile(
        depth=1,
        history=HistoryPolicy.KEEP_LAST,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        reliability=ReliabilityPolicy.RELIABLE,
    )

# MissionPlan.action dest_tasks. `none` is a waypoint merely passed through;
# mission_manager treats anything that is not 1 as a drop, so its log says
# "Drop" for a pass-through. Harmless — it navigates and completes either way —
# but worth knowing before trusting that line.
MISSION_TASK_WIRE = {"none": 0, "pick": 1, "drop": 2}

# How long a single step may take before the agent gives up on it. Generous:
# a robot crossing a warehouse with a detour is not stuck, and the old UI's
# two-minute timer used to fire mid-drive and send the *next* goal while the
# robot was still working on the last one.
MISSION_STEP_TIMEOUT_S = 900.0
MISSION_GOAL_ACCEPT_TIMEOUT_S = 20.0
# How often a step in progress asks the backend whether its run still exists.
# "Cancel mission" used to be read only at the end of a lap, so the robot drove
# the rest of the route after the operator had abandoned it.
RUN_CANCEL_CHECK_S = 2.0
# Returned as a step's detail when the run was ended from outside. Not a
# failure: nothing is reported, because the run already has its final state.
RUN_CANCELED = "run canceled"
MAP_LOADER_SERVICE = "/map_server/load_map"
SERVICE_WAIT_S = 10.0
SERVICE_CALL_TIMEOUT_S = 120.0
# nav2 defaults; kept explicit so a saved map records the thresholds it was
# written with rather than inheriting whatever a future default becomes.
FREE_THRESH = 0.196
OCCUPIED_THRESH = 0.65

# Teleop relay.
TELEOP_IN_TOPIC = "/teleop/cmd_vel"
CMD_VEL_TOPIC = "/cmd_vel"
# Republish rate. Faster than the browser sends, so network jitter does not
# show up as stutter in the wheels.
TELEOP_TICK_HZ = 20.0
# Silence past this and the robot is stopped. Roughly three browser frames at
# the rate the UI publishes: long enough to ride out a hiccup, short enough
# that a dropped link does not travel far.
TELEOP_TIMEOUT_S = 0.3
# A single stop message can be lost. Repeat it for a few ticks.
TELEOP_STOP_REPEATS = 5


# Where each stack's console output is kept, one file per mode, the previous
# run's beside it as .1. Capped so a robot left running for a week does not
# fill its disk with "Optimizer reset".
LAUNCH_LOG_DIR = Path(os.path.expanduser("~/.ros/amr_agent"))
LAUNCH_LOG_MAX_BYTES = 20 * 1024 * 1024


def launch_log_path(mode: str) -> Path:
    return LAUNCH_LOG_DIR / f"{mode}.log"


def _rotate(path: Path) -> None:
    try:
        if path.exists():
            path.replace(path.with_suffix(path.suffix + ".1"))
    except OSError:
        pass


def _tee_child_output(stream, path: Path) -> None:
    """Copy a launch's stdout to the console and to its log file, line by line."""
    log = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate(path)
        log = open(path, "ab")  # noqa: SIM115 — closed below, lives as long as the stream
    except OSError:
        log = None
    try:
        for line in iter(stream.readline, b""):
            try:
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
            except (OSError, ValueError):
                pass
            if log is not None:
                try:
                    log.write(line)
                    log.flush()
                    if log.tell() > LAUNCH_LOG_MAX_BYTES:
                        log.close()
                        _rotate(path)
                        log = open(path, "ab")  # noqa: SIM115
                except OSError:
                    log = None
    finally:
        stream.close()
        if log is not None:
            log.close()


class RobotAgent(Node):
    def __init__(self) -> None:
        super().__init__("robot_agent")

        self.declare_parameter("managed_mode", False)
        self.declare_parameter("use_sim_time_arg", True)
        self.declare_parameter("default_map", DEFAULT_MAP)
        self.declare_parameter("backend_url", "")
        self.declare_parameter("robot_id", "")
        self.declare_parameter("map_cache_dir", "/maps/cache")
        # What this agent remembers across restarts and outages: the last
        # registry reading, station sets, unsent run reports, finished runs.
        # Empty means ~/.amr_agent. See agent_state.py.
        self.declare_parameter("state_dir", "")
        self.declare_parameter("map_sync_period", 10.0)
        # Which launch files this agent drives. Parameters rather than constants
        # because the agent is not only run against this repository's stack: a
        # robot built elsewhere has its own package and file names, and hard
        # coding ours meant the agent launched nothing there and reported the
        # failure as a broken robot. Defaults are this repository's, so every
        # existing command keeps behaving exactly as it did.
        self.declare_parameter("slam_launch_package", "amr_simulation")
        self.declare_parameter("slam_launch_file", "slam.launch.py")
        self.declare_parameter("nav_launch_package", "amr_navigation")
        self.declare_parameter("nav_launch_file", "navigation.launch.py")
        # Appended to both launch commands, shell-quoted. Someone else's launch
        # file usually needs a few of its own arguments turned off — an
        # orchestrator that would fight this agent over /robot_mode, an rviz
        # nobody is looking at, a rosbridge already running on that port.
        self.declare_parameter("extra_launch_args", "")
        # Appended only to the SLAM launch command. This keeps mapping-specific
        # arguments out of navigation while preserving the shared arguments
        # above for both launch modes.
        self.declare_parameter("slam_extra_launch_args", "")
        # How a survey is written to disk: "service" calls a running map_saver
        # node, "cli" shells out to map_saver_cli. See _write_map_via_cli.
        self.declare_parameter("map_save_via", "service")
        self.declare_parameter("map_save_timeout", 20.0)
        # Where this robot's destinations live.
        #
        # Empty means the robot has a /station_config service to push to, which
        # is this repository's own mission manager. A path means it does not,
        # and the registry is written as a Nav2 dock database instead — the file
        # is this agent's to own, so the robot's own station file is never
        # touched and never has to be given back.
        self.declare_parameter("station_file", "")
        self.declare_parameter("dock_reload_service", DOCK_RELOAD_SERVICE)
        # opennav_docking addresses plugins by name; only the ones listed in the
        # docking server's own dock_plugins exist.
        self.declare_parameter("dock_plugin", "simple_charging_dock")
        # How a mission step is carried out.
        #
        # "mission_plan" hands the station id to a mission manager that knows
        # where it is — this repository's own stack. "nav" resolves the pose
        # from the registry here and drives there with Nav2's own
        # navigate_to_pose, which is what a robot without that manager has.
        self.declare_parameter("mission_via", "mission_plan")
        # How long a `confirm` stop waits for somebody to take the order before
        # the robot carries on by itself (mission_via=nav). 0 waits forever.
        # Two minutes: long enough to walk over from the far side of a room,
        # short enough that a forgotten tray does not hold the whole route.
        self.declare_parameter("confirm_timeout", 120.0)
        # zone_mask_server, run alongside navigation by this agent. For stacks
        # whose own launch does not include it — this repository's navigation
        # launch does, so it stays empty there. A path to the script.
        self.declare_parameter("zone_mask_script", "")

        self._managed = bool(self.get_parameter("managed_mode").value)
        self._use_sim_time_arg = bool(self.get_parameter("use_sim_time_arg").value)
        self._current_map = str(self.get_parameter("default_map").value)

        backend_url = str(self.get_parameter("backend_url").value).strip()
        self._robot_id = str(self.get_parameter("robot_id").value).strip()
        self._cache_dir = Path(str(self.get_parameter("map_cache_dir").value))
        state_dir = str(self.get_parameter("state_dir").value).strip()
        self._store = AgentState(Path(state_dir) if state_dir else Path.home() / ".amr_agent")
        # The registry's desired mode as last read, kept with the map snapshot.
        self._registry_desired = "nav"
        # Said once per outage rather than every sync.
        self._offline_announced = False
        self._sync_period = float(self.get_parameter("map_sync_period").value)
        self._slam_launch_pkg = str(self.get_parameter("slam_launch_package").value)
        self._slam_launch_file = str(self.get_parameter("slam_launch_file").value)
        self._nav_launch_pkg = str(self.get_parameter("nav_launch_package").value)
        self._nav_launch_file = str(self.get_parameter("nav_launch_file").value)
        self._extra_launch_args = shlex.split(
            str(self.get_parameter("extra_launch_args").value)
        )
        self._slam_extra_launch_args = shlex.split(
            str(self.get_parameter("slam_extra_launch_args").value)
        )
        self._map_save_timeout = float(self.get_parameter("map_save_timeout").value)
        station_file = str(self.get_parameter("station_file").value).strip()
        self._station_file = Path(station_file) if station_file else None
        self._dock_reload_service = str(self.get_parameter("dock_reload_service").value)
        self._dock_plugin = str(self.get_parameter("dock_plugin").value)
        zone_mask_script = str(self.get_parameter("zone_mask_script").value).strip()
        self._zone_mask_script = Path(zone_mask_script) if zone_mask_script else None
        # Runs while navigation does; started and stopped with it.
        self._zone_mask: subprocess.Popen | None = None
        self._mission_via = str(self.get_parameter("mission_via").value).strip().lower()
        if self._mission_via not in ("mission_plan", "nav"):
            raise ValueError(
                f"mission_via must be 'mission_plan' or 'nav', not {self._mission_via!r}"
            )
        # Station poses by id, kept from the last registry read. A mission step
        # names a station; driving there needs to know where that is.
        self._station_poses: dict[str, tuple[float, float, float]] = {}
        # And their names, for the kiosk: a guest reads "Meja 5", not a uuid.
        self._station_names: dict[str, str] = {}
        self._confirm_timeout = float(self.get_parameter("confirm_timeout").value)
        # The kiosk's view of the current run. Written by the run thread and by
        # Nav2 feedback on executor threads, read by the publish timer.
        self._kiosk_lock = threading.Lock()
        self._kiosk = {"phase": PHASE_IDLE}
        self._kiosk_since = time.monotonic()
        self._confirm_gate = ConfirmGate()
        self._progress = ProgressWatch()
        self._map_save_via = str(self.get_parameter("map_save_via").value).strip().lower()
        # Refused at startup, not at the first save. A typo here would otherwise
        # surface as a failed survey an hour into a shift, after the driving is
        # already done and the map is still only in slam_toolbox's memory.
        if self._map_save_via not in ("service", "cli"):
            raise ValueError(
                f"map_save_via must be 'service' or 'cli', not {self._map_save_via!r}"
            )
        # No backend configured is a supported deployment, not a misconfiguration:
        # the robot still maps and navigates, it simply publishes nowhere.
        self._backend = (
            BackendClient(backend_url, self._robot_id)
            if backend_url and self._robot_id
            else None
        )
        self._backend_state = "not configured" if self._backend is None else "unknown"
        self._loaded_map_id: str | None = None
        # The hash of what map_server actually holds, so a map replaced in place
        # under the same id is still detected.
        self._loaded_hash: str | None = None
        # Fingerprint of the station set last pushed to mission_manager, and the
        # ids that went with it — deletions have to be sent, not just omitted.
        self._station_hash: str | None = None
        self._station_ids: set[str] = set()
        # The thread executing a mission run, or None when idle.
        self._run_thread: threading.Thread | None = None
        # Fingerprint of the zone set last published, so an unchanged set does
        # not make every filter rebuild its mask once a second.
        self._zone_hash: str | None = None
        # (map id, fingerprint) of the zone set last written to disk.
        self._zone_saved: tuple[str, str] | None = None
        # Earliest time a failed mode switch may be retried.
        self._mode_retry_after = 0.0
        # Where the current launch's stderr is going, so a failure can say why.
        self._child_errors = None
        self._map_busy = threading.Lock()

        # Teleop relay state. Guarded because the subscription callback and the
        # watchdog tick run on different threads under MultiThreadedExecutor.
        self._teleop_lock = threading.Lock()
        self._teleop_cmd: Twist | None = None
        self._teleop_at: float = 0.0
        self._teleop_stops_sent = 0
        self._teleop_active = False

        self._cb = ReentrantCallbackGroup()
        self._lock = threading.Lock()
        self._child: subprocess.Popen | None = None
        self._mode = MODE_UNKNOWN
        self._state = STATE_IDLE
        self._detail = ""
        self._worker: threading.Thread | None = None

        self._status_pub = self.create_publisher(String, "/robot_mode_status", 10)
        # transient_local: zone_mask_server may come up after this, and a zone
        # list nobody heard is a map with no zones on it and no error anywhere.
        self._zones_pub = self.create_publisher(
            String, ZONES_TOPIC, qos_profile=_latched_qos()
        )
        self._cmd_vel_pub = self.create_publisher(Twist, CMD_VEL_TOPIC, 10)
        self.create_subscription(
            Twist, TELEOP_IN_TOPIC, self._on_teleop, 10, callback_group=self._cb
        )
        self.create_timer(
            1.0 / TELEOP_TICK_HZ, self._teleop_tick, callback_group=self._cb
        )
        self.create_service(
            RobotMode, "/robot_mode", self._on_robot_mode, callback_group=self._cb
        )
        self.create_service(
            RobotMode, "/map_save", self._on_map_save, callback_group=self._cb
        )
        # A nudge, not a command. The sync loop would find the run anyway, ten
        # seconds later — which is a long time to stand in front of a robot
        # wondering whether the button worked.
        self.create_service(
            Trigger, MISSION_POLL_SERVICE, self._on_mission_poll, callback_group=self._cb
        )
        self.create_timer(1.0, self._publish_status, callback_group=self._cb)

        # Latched, so a kiosk started after the agent sees the current state at
        # once instead of a blank face for up to a second.
        self._kiosk_pub = self.create_publisher(
            String, KIOSK_TOPIC, qos_profile=_latched_qos()
        )
        self.create_timer(1.0, self._publish_kiosk, callback_group=self._cb)
        if self._mission_via == "nav":
            # mission_plan stacks have a mission manager serving this name.
            # Two servers on one service name is undefined which one answers.
            self.create_service(
                Trigger,
                MISSION_CONFIRM_SERVICE,
                self._on_mission_confirm,
                callback_group=self._cb,
            )

        if self._backend is not None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self.create_timer(
                self._sync_period, self._sync_assigned_map, callback_group=self._cb
            )
            self.get_logger().info(
                f"[robot_agent] backend {backend_url} as robot {self._robot_id}"
            )
        else:
            self.get_logger().info(
                "[robot_agent] no backend configured — maps stay on this robot"
            )

        if self._managed:
            self._set_state(MODE_UNKNOWN, STATE_IDLE, "No mode started yet")
            self.get_logger().info(
                "[robot_agent] managed mode — /robot_mode owns slam and navigation"
            )
        else:
            # The stack was launched the old way, with use_slam fixed at boot.
            # Say so rather than pretending to be in charge: a switch here
            # would leave two copies of a stack fighting over the same topics.
            detected = self._detect_running_mode()
            self._set_state(
                detected,
                STATE_RUNNING if detected != MODE_UNKNOWN else STATE_IDLE,
                "Launched outside the agent; switching is disabled",
            )
            self.get_logger().warning(
                "[robot_agent] unmanaged — started with managed_mode:=false, "
                f"detected mode '{detected}'. Mode switching is refused."
            )

    # ── Status ────────────────────────────────────────────────────────────────

    def _set_state(self, mode: str, state: str, detail: str = "") -> None:
        self._mode, self._state, self._detail = mode, state, detail
        self._publish_status()

    def _publish_status(self) -> None:
        msg = String()
        msg.data = json.dumps(
            {
                "mode": self._mode,
                "state": self._state,
                "map": self._current_map if self._mode == MODE_NAV else "",
                "map_id": self._loaded_map_id or "",
                "detail": self._detail,
                "managed": self._managed,
                "backend": self._backend_state,
                "teleop": self._teleop_active,
                # Run reports written while the server was unreachable, still
                # waiting to be sent. Non-zero means the UI's run is behind.
                "pending_reports": self._store.pending_count(),
            }
        )
        self._status_pub.publish(msg)

    def _detect_running_mode(self) -> str:
        """Infer the mode from the node graph, for the unmanaged case."""
        try:
            names = {name for name, _ in self.get_node_names_and_namespaces()}
        except Exception:
            return MODE_UNKNOWN
        if any(marker in names for marker in SLAM_MARKER_NODES):
            return MODE_MAP
        if any(marker in names for marker in NAV_MARKER_NODES):
            return MODE_NAV
        return MODE_UNKNOWN

    def _nodes_present(self, markers: tuple[str, ...]) -> bool:
        try:
            names = {name for name, _ in self.get_node_names_and_namespaces()}
        except Exception:
            return False
        return any(marker in names for marker in markers)

    # ── Service ───────────────────────────────────────────────────────────────

    def _on_robot_mode(self, request, response):
        raw = (request.robot_mode or "").strip()

        if not self._managed:
            response.result = (
                "REJECTED: agent is not managing modes. Relaunch with "
                "managed_mode:=true, or restart the stack with use_slam."
            )
            return response

        # "nav|/maps/foo.yaml" carries the map inline because RobotMode.srv has
        # only one string field. A dedicated field belongs here, but changing
        # custom_interfaces means regenerating and rebuilding the image, so the
        # encoding is documented instead of the interface being churned.
        mode, _, inline_map = raw.partition("|")
        mode = mode.strip().lower()
        inline_map = inline_map.strip()

        if mode not in (MODE_MAP, MODE_NAV, MODE_STOP):
            response.result = f"REJECTED: unknown mode '{raw}'"
            return response

        with self._lock:
            if self._state in (STATE_STARTING, STATE_STOPPING):
                response.result = f"REJECTED: busy ({self._state})"
                return response
            if self._worker and self._worker.is_alive():
                response.result = "REJECTED: a switch is already running"
                return response

            if mode == MODE_NAV:
                target_map = inline_map or self._current_map
                if not os.path.isfile(target_map):
                    # Refuse early. Nav2 started without a readable map comes up
                    # and then fails in a way that looks like a robot fault.
                    response.result = f"REJECTED: map not found on robot: {target_map}"
                    return response
                self._current_map = target_map

            self._worker = threading.Thread(
                target=self._switch, args=(mode,), daemon=True
            )
            self._worker.start()

        # Intent is recorded after the switch is under way, not before: a
        # rejected request must not leave the registry claiming something the
        # robot was never asked to do. A failure here is logged and no more —
        # the switch is already happening, and refusing the caller now would
        # report a failure for work that succeeded.
        self._record_intent(mode)

        target = self._current_map if mode == MODE_NAV else ""
        response.result = f"ACCEPTED: switching to {mode}{f' ({target})' if target else ''}"
        return response

    def _record_intent(self, mode: str) -> None:
        """Tell the registry what was asked for, so the sync loop agrees."""
        if self._backend is None:
            return
        try:
            self._backend.set_desired_mode(MODE_TO_REGISTRY[mode])
        except Exception as exc:  # noqa: BLE001 — losing the note must not fail the switch
            self.get_logger().warning(
                f"[robot_agent] could not record desired mode '{mode}': {exc}. "
                "The sync loop may switch back."
            )

    # ── Teleop relay ──────────────────────────────────────────────────────────

    def _teleop_allowed(self) -> bool:
        """
        Only while mapping.

        In navigation mode Nav2 owns /cmd_vel through its velocity smoother; a
        second publisher would fight it, and the robot would jerk between two
        opinions about where it is going.
        """
        return self._mode == MODE_MAP and self._state == STATE_RUNNING

    def _on_teleop(self, msg: Twist) -> None:
        if not self._teleop_allowed():
            # Refuse quietly rather than queueing: acting on it later, after a
            # mode change, would move the robot on a stale instruction.
            return
        with self._teleop_lock:
            self._teleop_cmd = msg
            self._teleop_at = time.monotonic()
            self._teleop_stops_sent = 0

    @staticmethod
    def _zero_twist() -> Twist:
        return Twist()

    def _teleop_tick(self) -> None:
        """
        Republish the last command, or stop the robot if the stream went quiet.

        Republishing at a steady rate rather than forwarding each message means
        network jitter does not reach the wheels; the watchdog below is what
        makes that safe.
        """
        with self._teleop_lock:
            command = self._teleop_cmd
            last_at = self._teleop_at
            stops_sent = self._teleop_stops_sent

        if command is None:
            return

        allowed = self._teleop_allowed()
        fresh = (time.monotonic() - last_at) <= TELEOP_TIMEOUT_S

        if allowed and fresh:
            self._cmd_vel_pub.publish(command)
            if not self._teleop_active:
                self._teleop_active = True
            return

        # Either the operator stopped talking to us, or the robot left mapping
        # mode underneath them. Both mean: stop.
        if stops_sent < TELEOP_STOP_REPEATS:
            self._cmd_vel_pub.publish(self._zero_twist())
            with self._teleop_lock:
                self._teleop_stops_sent = stops_sent + 1
            if stops_sent == 0:
                reason = "link went quiet" if allowed else f"left {MODE_MAP} mode"
                self.get_logger().warning(f"[robot_agent] teleop stopped: {reason}")
            return

        # Stop delivered. Forget the command so a later mode change cannot
        # resurrect it.
        if self._teleop_active:
            self._teleop_active = False
        with self._teleop_lock:
            self._teleop_cmd = None

    # ── Service helpers ───────────────────────────────────────────────────────

    def _call_service(self, client, request, timeout: float = SERVICE_CALL_TIMEOUT_S):
        """
        Call a service and wait for the result.

        Safe to block here because every caller runs on a worker thread, never
        on a ROS callback — the executor keeps spinning, so the future actually
        resolves. Doing this from inside a callback would deadlock.
        """
        if not client.wait_for_service(timeout_sec=SERVICE_WAIT_S):
            raise RuntimeError(f"service {client.srv_name} is not available")

        future = client.call_async(request)
        deadline = time.time() + timeout
        while not future.done():
            if time.time() > deadline:
                future.cancel()
                raise RuntimeError(f"service {client.srv_name} timed out after {timeout:.0f}s")
            time.sleep(0.05)
        return future.result()

    # ── Saving a map ──────────────────────────────────────────────────────────

    def _on_map_save(self, request, response):
        name = (request.robot_mode or "").strip()
        if not name:
            response.result = "REJECTED: a map name is required"
            return response
        if self._mode != MODE_MAP or self._state != STATE_RUNNING:
            # map_saver only exists while SLAM is up, and a save attempted in
            # navigation mode would silently capture the map already loaded
            # rather than anything newly surveyed.
            response.result = f"REJECTED: not mapping (mode={self._mode}, state={self._state})"
            return response
        if not self._map_busy.acquire(blocking=False):
            response.result = "REJECTED: a map operation is already running"
            return response

        try:
            result = self._save_and_publish(name)
        except Exception as exc:  # noqa: BLE001 — a failed save must not kill the agent
            self.get_logger().error(f"[robot_agent] map save failed: {exc}")
            response.result = f"REJECTED: {exc}"
        else:
            response.result = result
        finally:
            self._map_busy.release()
        return response

    def _write_map_via_service(self, stem: Path) -> None:
        """Save through a running map_saver node (this repository's stack)."""
        saver = self.create_client(SaveMap, MAP_SAVER_SERVICE, callback_group=self._cb)
        try:
            request = SaveMap.Request()
            request.map_topic = "map"
            request.map_url = str(stem)
            request.image_format = "pgm"
            request.map_mode = "trinary"
            request.free_thresh = FREE_THRESH
            request.occupied_thresh = OCCUPIED_THRESH
            reply = self._call_service(saver, request)
        finally:
            self.destroy_client(saver)

        if reply is None or not reply.result:
            raise RuntimeError("map_saver refused to write the map")

    def _write_map_via_cli(self, stem: Path) -> None:
        """
        Save through map_saver_cli, for stacks with no map_saver node running.

        Starting one is not an alternative: map_saver is a lifecycle node and
        stays in `unconfigured` until something transitions it, so an agent that
        merely spawned it would wait forever. The CLI configures and activates
        its own node and exits.

        slam_toolbox's /slam_toolbox/save_map is not a substitute either. It
        takes a name and nothing else, so the image format, the thresholds and
        the destination are whatever that node was configured with — and the
        registry needs a trinary PGM at a path this agent chose.
        """
        cmd = [
            "ros2", "run", "nav2_map_server", "map_saver_cli",
            "-t", "map",
            "-f", str(stem),
            "--occ", str(OCCUPIED_THRESH),
            "--free", str(FREE_THRESH),
            "--fmt", "pgm",
            "--mode", "trinary",
            # Must outlast one /map publication. slam_toolbox publishes on
            # map_update_interval — commonly 5 s — while the CLI's own default
            # is 2 s, so a perfectly healthy stack fails with "Failed to spin
            # map subscription" and nothing explains why.
            "--ros-args", "-p", f"save_map_timeout:={self._map_save_timeout}",
        ]
        self.get_logger().info(f"[robot_agent] exec: {shlex.join(cmd)}")
        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=self._map_save_timeout + 30.0,
            check=False,
        )
        if completed.returncode != 0:
            # Both streams merged on purpose: the ros2 CLI writes launch and
            # node failures to stdout, so capturing stderr alone reports an
            # empty reason for a command that explained itself perfectly well.
            tail = (completed.stdout or "").strip().splitlines()[-4:]
            raise RuntimeError(
                "map_saver_cli failed: " + (" | ".join(tail) or "no output")
            )

    def _save_and_publish(self, name: str) -> str:
        staging = self._cache_dir / ".staging"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True, exist_ok=True)
        stem = staging / "map"

        if self._map_save_via == "cli":
            self._write_map_via_cli(stem)
        else:
            self._write_map_via_service(stem)

        yaml_path = stem.with_suffix(".yaml")
        image_path = stem.with_suffix(".pgm")
        if not yaml_path.is_file() or not image_path.is_file():
            raise RuntimeError(f"map_saver reported success but wrote nothing to {staging}")

        self.get_logger().info(
            f"[robot_agent] saved map '{name}' locally ({image_path.stat().st_size} bytes)"
        )

        if self._backend is None:
            # A distinct prefix, because the caller must not read this as a
            # publish. The map exists, but only here, and the operator's map
            # list will never show it — so this reports as a partial success
            # rather than hiding behind the same word as a real one.
            return f"SAVED_LOCAL {yaml_path} (no backend configured)"

        try:
            record = self._backend.upload_map(
                name=name,
                yaml_bytes=yaml_path.read_bytes(),
                image_bytes=image_path.read_bytes(),
                image_filename="map.pgm",
            )
        except BackendError as error:
            self._backend_state = "unreachable" if error.is_offline else "error"
            # The map is on this robot's disk either way. Saying where is what
            # makes the upload retryable instead of the work being lost.
            raise RuntimeError(f"saved at {yaml_path} but upload failed: {error}") from error

        self._backend_state = "ok"
        # Keep the bytes under the published id, so the robot already has the
        # map it just created and will not download its own work back.
        self._adopt_into_cache(record, yaml_path.read_bytes(), image_path.read_bytes())
        shutil.rmtree(staging, ignore_errors=True)

        # The robot that surveyed a map becomes the robot that runs it. An
        # operator who picked this robot, drove it around the site and saved the
        # result has already expressed that intent; making them assign it again
        # in a second screen is a step that only ever gets forgotten.
        #
        # Deliberately not fatal. The map is published and cached — losing the
        # assignment costs one click, while failing the save here would throw
        # away a finished survey over a bookkeeping call.
        try:
            self._backend.assign_map(record["id"])
        except BackendError as error:
            self.get_logger().warning(
                f"[robot_agent] published map {record['id']} but could not assign it: {error}"
            )
        else:
            # _loaded_map_id deliberately untouched: it means "map_server has
            # this", and map_server is not even running during a survey. Setting
            # it here would make the sync loop skip the load when navigation
            # starts, and the robot would navigate on the wrong map.
            self.get_logger().info(f"[robot_agent] now assigned to its own map {record['id']}")

        return f"SAVED {record['id']} v{record['version']}"

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _cached_yaml(self, record: dict) -> Path | None:
        """Return the cached yaml for this map, or None when it must be fetched."""
        directory = self._cache_dir / record["id"]
        yaml_path = directory / record["yaml_file"]
        image_path = directory / record["image_file"]
        if not yaml_path.is_file() or not image_path.is_file():
            return None

        # Verify, do not assume. A truncated download that is never checked is
        # loaded as a map, and a robot navigating half a warehouse is worse
        # than a robot that refuses to start.
        digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
        if digest != record["content_hash"]:
            self.get_logger().warning(
                f"[robot_agent] cached map {record['id']} failed its hash check; refetching"
            )
            shutil.rmtree(directory, ignore_errors=True)
            return None
        return yaml_path

    def _adopt_into_cache(self, record: dict, yaml_bytes: bytes, image_bytes: bytes) -> Path:
        directory = self._cache_dir / record["id"]
        directory.mkdir(parents=True, exist_ok=True)
        (directory / record["image_file"]).write_bytes(image_bytes)
        yaml_path = directory / record["yaml_file"]
        yaml_path.write_bytes(yaml_bytes)
        return yaml_path

    def _ensure_cached(self, record: dict) -> Path:
        cached = self._cached_yaml(record)
        if cached is not None:
            return cached
        if self._backend is None:
            raise RuntimeError(f"map {record['id']} is not cached and no backend is configured")

        self.get_logger().info(f"[robot_agent] fetching map {record['id']} ({record['name']})")
        image = self._backend.download_map_file(record["id"], "image")
        digest = hashlib.sha256(image.data).hexdigest()
        if digest != record["content_hash"]:
            raise RuntimeError(
                f"downloaded image hash {digest[:12]} does not match "
                f"the registry's {record['content_hash'][:12]}"
            )
        yaml_file = self._backend.download_map_file(record["id"], "yaml")
        return self._adopt_into_cache(record, yaml_file.data, image.data)

    # ── Applying the assigned map ─────────────────────────────────────────────

    def _sync_assigned_map(self) -> None:
        """
        Reconcile this robot against the map the backend says it should be on.

        Polled rather than pushed. A robot roams on wifi and may sit behind
        NAT, so an outbound poll works in deployments where an inbound call
        from the server simply cannot arrive.
        """
        if self._backend is None or not self._map_busy.acquire(blocking=False):
            return
        robot = None
        outage = False
        try:
            robot = self._backend.get_robot()
            self._backend_state = "ok"
        except BackendError as error:
            self._backend_state = "unreachable" if error.is_offline else "error"
            # Unreachable or failing is an outage. A 4xx is the server answering:
            # a 404 means this robot is not registered, and the snapshot must
            # not keep a deleted robot driving.
            outage = error.is_offline or error.status >= 500
        finally:
            self._map_busy.release()

        if robot is None:
            if outage:
                self._run_from_snapshot()
            return

        if self._offline_announced:
            self.get_logger().info("[robot_agent] server reachable again; back on the registry")
            self._offline_announced = False
        # Reports from the outage go before anything else: the server's view of
        # a run has to be current before it is asked what to run next.
        self._flush_outbox()

        assigned = robot.get("active_map_id")
        raw_desired = str(robot.get("desired_mode") or "nav")
        self._registry_desired = raw_desired
        try:
            self._store.save_registry(active_map_id=assigned, desired_mode=raw_desired)
        except OSError as exc:
            self.get_logger().warning(f"[robot_agent] could not save registry snapshot: {exc}")
        desired = REGISTRY_TO_MODE.get(raw_desired, MODE_UNKNOWN)
        if desired == MODE_UNKNOWN:
            self.get_logger().warning(
                f"[robot_agent] registry asked for an unknown mode '{raw_desired}'"
            )
            return

        # The map comes first, and this order is not arbitrary. Navigation is
        # started with a map path on the command line, so starting it before the
        # assigned map has been fetched launches it on whatever the launch file
        # defaulted to — a stale map, silently, with the robot localising
        # against a building it is not in.
        #
        # _prefetch is what caches the file and points _current_map at it, so it
        # has to have run at least once before a switch to nav is allowed.
        if assigned and (
            assigned != self._loaded_map_id
            or self._mode != MODE_NAV
            or self._state != STATE_RUNNING
        ):
            self._prefetch(assigned)

        self._reconcile_mode(desired, assigned)

        if not assigned:
            # Clearing the assignment does not unload the running map — that
            # would strand a robot mid-shift. It does drop our belief about
            # what is loaded, so re-assigning the same map later actually
            # re-applies it instead of being skipped as already-current.
            if self._loaded_map_id is not None:
                self.get_logger().info("[robot_agent] map assignment cleared")
                self._loaded_map_id = None
                self._loaded_hash = None
                self._station_hash = None
                self._station_ids = set()
                self._zone_hash = None
            return

        # Zones are fetched and kept on disk in every mode, not only once Nav2
        # has the map: saving them needs nothing from the stack, and a robot
        # sitting idle when its zones are edited must still have the new set if
        # it next starts with the server down. They are only *published* for
        # the map map_server actually holds, so a new map's keepouts are never
        # laid over the old one while a switch is in progress.
        self._sync_zones(assigned, publish=assigned == self._loaded_map_id)

        # Same id is not the same map. A map's contents can be replaced in place
        # from the UI, which keeps the id and changes the content hash — so an
        # id-only check would leave this robot running the old bytes forever
        # while a robot that happened to restart picked up the new ones. Two
        # robots, one id, different worlds, and nothing on screen saying so.
        if assigned == self._loaded_map_id:
            try:
                record = self._backend.get_map(assigned)
            except BackendError as error:
                self._backend_state = "unreachable" if error.is_offline else "error"
                return
            if record.get("content_hash") == self._loaded_hash:
                # The map is current. Its stations may still have moved, and a
                # run may be waiting to be picked up.
                self._sync_stations()
                self._poll_run()
                return
            self.get_logger().warning(
                f"[robot_agent] map {assigned} changed underneath us "
                f"({str(self._loaded_hash)[:12]} -> {str(record.get('content_hash'))[:12]}); reloading"
            )
        if self._mode != MODE_NAV or self._state != STATE_RUNNING:
            # Already prefetched above: /map_server only exists in navigation
            # mode, so there is nothing to load into yet.
            return

        if not self._map_busy.acquire(blocking=False):
            return
        try:
            self._apply_map(assigned)
        except Exception as exc:  # noqa: BLE001 — a failed apply must not kill the agent
            self.get_logger().error(f"[robot_agent] could not apply map {assigned}: {exc}")
        finally:
            self._map_busy.release()

    def _prefetch(self, map_id: str) -> None:
        if not self._map_busy.acquire(blocking=False):
            return
        try:
            record = self._backend.get_map(map_id)
            yaml_path = self._ensure_cached(record)
            # Point at the assigned map even before anything is running. Nav
            # starts on whatever this holds, and leaving it on the launch
            # fallback means coming up on the wrong map and swapping a moment
            # later — visible as a robot that localises somewhere it is not.
            self._current_map = str(yaml_path)
            self._snapshot_map(record)
        except (BackendError, RuntimeError, OSError) as error:
            self.get_logger().warning(f"[robot_agent] prefetch of {map_id} failed: {error}")
        finally:
            self._map_busy.release()

    # ── Running without the server ────────────────────────────────────────────

    def _snapshot_map(self, record: dict) -> None:
        """Keep the map's registry row with the assignment, for booting offline."""
        try:
            self._store.save_registry(
                active_map_id=record["id"],
                desired_mode=self._registry_desired,
                map_record={
                    key: record.get(key)
                    for key in ("id", "name", "version", "yaml_file", "image_file", "content_hash")
                },
            )
        except OSError as exc:
            self.get_logger().warning(f"[robot_agent] could not save registry snapshot: {exc}")

    def _verified_cache(self, record: dict) -> Path | None:
        """
        The cached map, if its bytes still match the recorded hash.

        Unlike _cached_yaml this never deletes a mismatch. Offline, the cache is
        the only copy there is: throwing it away cannot be undone until the
        server is back, and refusing to start on it is enough.
        """
        directory = self._cache_dir / str(record.get("id"))
        yaml_path = directory / str(record.get("yaml_file"))
        image_path = directory / str(record.get("image_file"))
        if not yaml_path.is_file() or not image_path.is_file():
            return None
        if hashlib.sha256(image_path.read_bytes()).hexdigest() != record.get("content_hash"):
            return None
        return yaml_path

    def _run_from_snapshot(self) -> None:
        """
        Keep to the last registry reading while the server cannot be reached.

        A robot that powered up while the server was down used to sit idle with
        its map already in its own cache, because the only thing it was waiting
        for was a server telling it what it already knew. It now starts from the
        last reading it saved. Reconciling against the same reading when it is
        already running changes nothing, so this is safe to call every sync.
        """
        snapshot = self._store.load_registry()
        if not snapshot:
            return
        assigned = snapshot.get("active_map_id")
        desired = REGISTRY_TO_MODE.get(str(snapshot.get("desired_mode") or "nav"), MODE_UNKNOWN)
        if desired == MODE_UNKNOWN:
            return

        record = snapshot.get("map_record") or {}
        if assigned and record.get("id") == assigned:
            cached = self._verified_cache(record)
            if cached is None:
                self.get_logger().warning(
                    f"[robot_agent] server unreachable and the cached map {assigned} "
                    "is missing or fails its hash check; not starting"
                )
                return
            self._current_map = str(cached)

        if assigned and not self._station_poses:
            self._remember_station_poses(self._store.load_stations(assigned))
        if assigned and self._zone_hash is None:
            saved_zones = self._store.load_zones(assigned)
            if saved_zones is not None:
                self._publish_zones(assigned, saved_zones, " (saved copy; server unreachable)")

        if not self._offline_announced:
            saved = time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(float(snapshot.get("saved_at") or 0))
            )
            self.get_logger().warning(
                f"[robot_agent] server unreachable; following the registry as saved at {saved} "
                f"({snapshot.get('desired_mode')} on map {assigned})"
            )
            self._offline_announced = True
        self._reconcile_mode(desired, assigned)

    def _apply_map(self, map_id: str) -> None:
        record = self._backend.get_map(map_id)
        yaml_path = self._ensure_cached(record)

        loader = self.create_client(LoadMap, MAP_LOADER_SERVICE, callback_group=self._cb)
        try:
            request = LoadMap.Request()
            # A path on this robot's own disk. Never a shared mount: a hung NFS
            # mount blocks map_server in uninterruptible sleep at exactly the
            # moment it is asked to navigate.
            request.map_url = str(yaml_path)
            reply = self._call_service(loader, request)
        finally:
            self.destroy_client(loader)

        if reply is None or reply.result != LoadMap.Response.RESULT_SUCCESS:
            code = "no reply" if reply is None else reply.result
            raise RuntimeError(f"map_server refused the map (result {code})")

        self._loaded_map_id = map_id
        self._loaded_hash = record.get("content_hash")
        self._current_map = str(yaml_path)
        self._snapshot_map(record)
        self.get_logger().info(
            f"[robot_agent] loaded map {record['name']} v{record['version']} ({map_id})"
        )
        # Stations are expressed in this map's frame, so they follow the map in
        # and are pushed only once it is the one actually loaded.
        self._push_stations(map_id)
        self._publish_status()

    # ── Desired mode ──────────────────────────────────────────────────────────

    def _reconcile_mode(self, desired: str, assigned_map) -> None:
        """
        Move towards what the registry says this robot should be doing.

        The mode used to live only in this process, and /robot_mode was a
        command rather than a state — so an agent that restarted came back idle
        and nothing anywhere noticed. Now the registry holds the intent and this
        keeps reality pointed at it, the same way the assigned map works.

        Nav2 running is not the robot moving: an idle planner plans nothing, and
        the robot only moves when a mission gives it a goal. Starting it without
        being asked is therefore safe, and is what lets a robot be useful the
        moment it is powered on.
        """
        if desired not in (MODE_NAV, MODE_MAP, MODE_STOP):
            self.get_logger().warning(f"[robot_agent] unknown desired mode '{desired}'")
            return

        # Never interrupt a transition. Switching while a stack is coming up
        # leaves half of it running and the next start colliding with it.
        if self._state in (STATE_STARTING, STATE_STOPPING):
            return
        if self._worker is not None and self._worker.is_alive():
            return

        if desired == MODE_NAV and not assigned_map:
            # Nav with no map is a planner with no world. Said once rather than
            # once every sync, and said rather than silently doing nothing.
            if self._mode != MODE_UNKNOWN or self._detail != NO_MAP_DETAIL:
                self._set_state(MODE_UNKNOWN, STATE_IDLE, NO_MAP_DETAIL)
            return

        if desired == self._mode and self._state == STATE_RUNNING:
            return

        # Stopped is a destination, not just an absence.
        #
        # _switch(MODE_STOP) leaves the agent in `unknown/idle` rather than a
        # mode named "stop", so the check above can never match it: `stop` is
        # not `unknown`, and `idle` is not `running`. Without this the sync loop
        # tears down an already stopped stack every ten seconds for the rest of
        # the shift, logging "switching" each time and never arriving.
        #
        # Only reachable since the registry gained a vocabulary for it — `idle`
        # maps to MODE_STOP — which is what turned a latent gap into a loop.
        if desired == MODE_STOP and self._child is None:
            return

        # A failed start is not retried immediately. Without this a stack that
        # cannot come up is restarted every ten seconds for the rest of the
        # shift, and the log that would explain why scrolls past.
        now = time.time()
        if self._state == STATE_FAILED and now < self._mode_retry_after:
            return

        if desired == MODE_NAV:
            # Not merely "a readable file": the launch fallback is readable and
            # is the wrong building. Nav has to start on the *assigned* map, so
            # this checks the path points into that map's cache directory.
            #
            # Nav2 started on the wrong map does not fail — it localises against
            # a floor plan the robot is not standing in, which is far worse than
            # not starting.
            wanted = self._cache_dir / str(assigned_map)
            current = Path(self._current_map)
            if not current.is_file() or wanted not in current.parents:
                self._set_state(
                    MODE_UNKNOWN,
                    STATE_IDLE,
                    f"Waiting for the assigned map to be cached ({assigned_map})",
                )
                return

        self._mode_retry_after = now + MODE_RETRY_COOLDOWN_S
        self.get_logger().info(
            f"[robot_agent] registry wants {desired}, currently "
            f"{self._mode}/{self._state} — switching"
        )
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._worker = threading.Thread(
                target=self._switch, args=(desired,), daemon=True
            )
            self._worker.start()

    # ── Zones ─────────────────────────────────────────────────────────────────

    def _sync_zones(self, map_id: str, publish: bool = True) -> None:
        """
        Fetch the map's zones, keep them on disk, and publish them when asked.

        Kept on this robot's disk in every mode, like the stations: a robot
        that boots while the server is down must still know where it may not
        go. Written only when the set changes, so an unchanged list is not
        rewritten to the Jetson's flash every sync.

        Published as polygons rather than as a mask image, for zone_mask_server
        to rasterise. The mask is tied to one map resolution and cannot be
        edited back into corners; the polygon is what the operator drew, and
        the robot is where it becomes pixels. Republished only when the set
        changes — a mask rebuild walks every cell of the map.
        """
        if self._backend is None:
            return
        try:
            zones = self._backend.list_zones(map_id)
        except BackendError as error:
            self._backend_state = "unreachable" if error.is_offline else "error"
            return

        digest = hashlib.sha256(json.dumps(zones, sort_keys=True).encode()).hexdigest()
        if self._zone_saved != (map_id, digest):
            try:
                self._store.save_zones(map_id, zones)
                self._zone_saved = (map_id, digest)
                self.get_logger().info(
                    f"[robot_agent] saved {len(zones)} zone(s) for map {map_id} to this robot"
                )
            except OSError as exc:
                self.get_logger().warning(f"[robot_agent] could not save zones: {exc}")

        if publish:
            self._publish_zones(map_id, zones)

    def _publish_zones(self, map_id: str, zones: list, source: str = "") -> bool:
        """Publish a zone set unless it is the one already out. True when sent."""
        payload = json.dumps(zones, sort_keys=True)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        if digest == self._zone_hash:
            return False

        self._zones_pub.publish(String(data=payload))
        self._zone_hash = digest
        active = sum(1 for zone in zones if zone.get("enabled", True))
        self.get_logger().info(
            f"[robot_agent] published {active} active zone(s) of {len(zones)} "
            f"for map {map_id}{source}"
        )
        return True

    # ── Mission runs ──────────────────────────────────────────────────────────

    def _poll_run(self) -> None:
        """
        Pick up a run the backend says this robot should be executing.

        The robot is what executes a mission, not the browser. The previous UI
        held the step index in tab memory and sent one goal per step from there,
        so closing the tab stranded a robot mid-route with nobody left to send
        the next goal — and a refresh lost the lap count while it kept driving.

        Polling also recovers: an agent restarted mid-route reads its own
        progress back from the server and carries on from the step it was on.
        """
        if self._backend is None or self._run_thread is not None:
            return
        # Only in navigation. A mission in mapping mode has no map_server to
        # plan against, and Nav2 is not even running.
        if self._mode != MODE_NAV or self._state != STATE_RUNNING:
            return

        # The server only knows where a run is once the reports from an outage
        # have arrived. Asking it what to run before then gets a stale answer —
        # including a run this robot has already finished.
        self._flush_outbox()
        if self._store.has_pending():
            return

        try:
            plan = self._backend.get_active_run()
        except BackendError as error:
            self._backend_state = "unreachable" if error.is_offline else "error"
            return
        if not plan or not plan.get("steps"):
            return

        run_id = str(plan["id"])
        final = self._store.finished(run_id)
        if final is not None:
            # This robot ended this run and the server never heard. Driving it
            # again would deliver everything twice; telling the server again is
            # what was missing.
            self.get_logger().warning(
                f"[robot_agent] run {run_id} already ended here ({final.get('state')}); "
                "re-sending the final report instead of driving it again"
            )
            if self._send_report(run_id, final) == "retry":
                self._store.enqueue(run_id, final)
            return

        self._run_thread = threading.Thread(
            target=self._execute_run, args=(plan,), daemon=True
        )
        self._run_thread.start()

    def _on_mission_poll(self, request, response):
        """Look for work now. Idempotent: a second call while busy does nothing."""
        del request
        if self._run_thread is not None:
            response.success = True
            response.message = "already running"
            return response
        if not self._run_allowed():
            response.success = False
            response.message = f"robot is {self._mode}/{self._state}, not navigating"
            return response

        self._poll_run()
        started = self._run_thread is not None
        response.success = started
        response.message = "run started" if started else "nothing to run"
        return response

    def _send_report(self, run_id: str, patch: dict) -> str:
        """
        One attempt at one report.

        "sent"; "ended" when the run is over or gone on the server (409, 404);
        "rejected" when the server refused the report itself (another 4xx), so
        resending it can never succeed; "retry" when the server could not be
        reached or failed, and the report must be kept.
        """
        try:
            self._backend.report_run(run_id, patch)
        except BackendError as error:
            if error.status in (404, 409):
                self.get_logger().info(f"[robot_agent] run {run_id} already ended on the server")
                return "ended"
            if not error.is_offline and error.status < 500:
                self.get_logger().warning(
                    f"[robot_agent] server refused report {patch} for run {run_id}: {error}"
                )
                return "rejected"
            self._backend_state = "unreachable" if error.is_offline else "error"
            return "retry"
        return "sent"

    def _flush_outbox(self) -> None:
        """Send reports kept during an outage, oldest first, until one cannot go."""
        if self._backend is None or not self._store.has_pending():
            return
        removed, empty = self._store.flush(
            lambda run_id, patch: (
                "retry" if self._send_report(run_id, patch) == "retry" else "sent"
            )
        )
        if removed:
            self.get_logger().info(
                f"[robot_agent] sent {removed} run report(s) kept while offline"
                + ("" if empty else "; the rest are still waiting")
            )

    def _report_run(self, run_id: str, patch: dict) -> bool:
        """
        Write progress back. Never lost: a report the server cannot take now is
        kept on disk and sent, in order, when it can.

        False only when the server says the run has already ended: the caller
        must stop driving it. Unreachable is not that — ending a run because the
        network blinked would strand a robot holding a payload.
        """
        if self._backend is None:
            return True

        if patch.get("state") in TERMINAL_STATES:
            # Before sending, so a crash between the two still leaves this robot
            # knowing it must not drive the route again (see _poll_run).
            self._store.mark_finished(run_id, patch)

        # Anything already waiting goes first, or this report would overtake it
        # and the server would see the run move backwards when the rest arrive.
        self._flush_outbox()
        if self._store.has_pending():
            self._store.enqueue(run_id, patch)
            return True

        outcome = self._send_report(run_id, patch)
        if outcome == "retry":
            self.get_logger().warning(
                f"[robot_agent] server unreachable; keeping report {patch} for run {run_id}"
            )
            self._store.enqueue(run_id, patch)
            return True
        return outcome != "ended"

    def _execute_run(self, plan: dict) -> None:
        """
        Work through the route, lap after lap, until it ends or is stopped.

        Runs on its own thread: every step blocks on an action result, and doing
        that from a ROS callback would stop the executor that has to deliver it.
        """
        run_id = str(plan["id"])
        steps = list(plan["steps"])
        mode = str(plan.get("mode", "once"))
        laps_target = plan.get("laps_target")
        lap = int(plan.get("lap", 1))
        step_index = int(plan.get("step_index", 0))
        stopping = str(plan.get("state")) == "stopping"

        self.get_logger().info(
            f"[robot_agent] running '{plan.get('mission_name')}' "
            f"({len(steps)} steps, mode {mode}) from lap {lap} step {step_index}"
        )
        client = (
            ActionClient(self, NavigateToPose, NAV_READY_ACTION, callback_group=self._cb)
            if self._mission_via == "nav"
            else ActionClient(self, MissionPlan, MISSION_ACTION, callback_group=self._cb)
        )
        route = [
            self._station_names.get(str(step.get("station_id")), "") or f"Stop {index + 1}"
            for index, step in enumerate(steps)
        ]
        self._kiosk_set(
            phase=PHASE_MOVING,
            mission=str(plan.get("mission_name") or ""),
            route=route,
            step=step_index,
            lap=lap,
            laps=int(laps_target) if mode == "laps" and laps_target else None,
            detail="",
        )
        try:
            while True:
                while step_index < len(steps):
                    if not self._run_allowed():
                        self._report_run(
                            run_id, {"state": "canceled", "detail": "robot left navigation mode"}
                        )
                        self._kiosk_set(phase=PHASE_IDLE)
                        return

                    # Checked before every step, not only at the end of a lap.
                    if self._run_canceled(run_id) or not self._report_run(
                        run_id, {"lap": lap, "step_index": step_index}
                    ):
                        self.get_logger().info(f"[robot_agent] run {run_id} canceled; stopping")
                        # Remembered, so a server that still lists it as live
                        # (a cancel that raced a lost report) cannot restart it.
                        self._store.mark_finished(run_id, {"state": "canceled"})
                        self._kiosk_set(phase=PHASE_IDLE)
                        return
                    step = steps[step_index]
                    self._progress.reset()
                    self._kiosk_set(phase=PHASE_MOVING, step=step_index, lap=lap)
                    ok, detail = (
                        self._run_step_nav(client, step, run_id)
                        if self._mission_via == "nav"
                        else self._run_step(client, step, run_id)
                    )
                    # The UI's "Cancel mission" also cancels the Nav2 goal, so
                    # a step can fail from the cancel before the next check
                    # sees the run gone. That is a cancel, not a failure.
                    if not ok and detail != RUN_CANCELED and self._run_canceled(run_id):
                        detail = RUN_CANCELED
                    if detail == RUN_CANCELED:
                        # Ended from outside while driving. The goal is already
                        # canceled and the run already has its final state.
                        self.get_logger().info(
                            f"[robot_agent] run {run_id} canceled during step {step_index + 1}"
                        )
                        self._store.mark_finished(run_id, {"state": "canceled"})
                        self._kiosk_set(phase=PHASE_IDLE)
                        return
                    if not ok:
                        # Stop the whole run rather than retrying. An automatic
                        # retry is how a robot spends a night driving into a
                        # blocked doorway with nobody watching.
                        self._report_run(
                            run_id,
                            {
                                "state": "failed",
                                "detail": f"lap {lap}, step {step_index + 1}: {detail}",
                            },
                        )
                        self.get_logger().error(f"[robot_agent] run {run_id} failed: {detail}")
                        self._kiosk_set(phase=PHASE_FAILED, detail=detail)
                        return
                    # Reported the moment it arrives. step_index only moves on
                    # when the next step starts, and never for a lap's last
                    # step, so it cannot tell anyone the robot got there.
                    self._report_run(run_id, {"reached_lap": lap, "reached_index": step_index})
                    self.get_logger().info(
                        f"[robot_agent] run {run_id} reached step {step_index + 1} (lap {lap})"
                    )
                    # mission_plan stacks wait for the confirm inside their
                    # mission manager; with plain Nav2 the waiting is here.
                    if self._mission_via == "nav" and str(step.get("confirm")) == "confirm":
                        if not self._await_confirm(run_id, step_index, lap):
                            return
                    step_index += 1

                # Lap complete. Re-read the run: somebody may have asked it to
                # stop while it was driving, and "stop after this lap" is only
                # meaningful if it is checked here.
                stopping = stopping or self._run_wants_stop(run_id)
                if stopping or not self._more_laps(mode, lap, laps_target):
                    self._report_run(run_id, {"state": "done"})
                    self._kiosk_set(phase=PHASE_DONE)
                    self.get_logger().info(f"[robot_agent] run {run_id} completed at lap {lap}")
                    return

                lap += 1
                step_index = 0
        except Exception as exc:  # noqa: BLE001 — a failed run must not kill the agent
            self.get_logger().error(f"[robot_agent] run {run_id} aborted: {exc}")
            self._report_run(run_id, {"state": "failed", "detail": str(exc)})
            self._kiosk_set(phase=PHASE_FAILED, detail=str(exc))
        finally:
            client.destroy()
            self._run_thread = None

    def _await_confirm(self, run_id: str, step_index: int, lap: int) -> bool:
        """
        Hold at a `confirm` stop until the order is taken or the time runs out.

        Returns False when the run must end here (canceled, or the robot left
        navigation); the caller then returns without reporting anything more.
        Timing out is not a failure: the robot carries on, as a waiter would
        after calling twice, and the run says so.
        """
        self._confirm_gate.open(self._confirm_timeout)
        self._kiosk_set(phase=PHASE_WAITING, step=step_index, lap=lap)
        self.get_logger().info(
            f"[robot_agent] run {run_id} waiting for a confirm at step {step_index + 1}"
        )
        check = {"next": time.time() + RUN_CANCEL_CHECK_S, "canceled": False}

        def should_stop() -> bool:
            if not self._run_allowed():
                return True
            # The backend is asked every few seconds, not every poll.
            if time.time() >= check["next"]:
                check["next"] = time.time() + RUN_CANCEL_CHECK_S
                check["canceled"] = self._run_canceled(run_id)
            return check["canceled"]

        outcome = self._confirm_gate.wait(should_stop)
        if outcome == CONFIRMED:
            self._report_run(run_id, {"detail": f"step {step_index + 1}: order taken"})
            self._kiosk_set(phase=PHASE_THANKS)
            time.sleep(THANKS_HOLD_S)
            return True
        if outcome == TIMED_OUT:
            self._report_run(
                run_id,
                {"detail": f"step {step_index + 1}: nobody confirmed, carried on"},
            )
            self.get_logger().info(
                f"[robot_agent] run {run_id}: no confirm at step {step_index + 1}; carrying on"
            )
            return True

        if check["canceled"]:
            self.get_logger().info(f"[robot_agent] run {run_id} canceled while waiting")
            self._store.mark_finished(run_id, {"state": "canceled"})
        else:
            self._report_run(
                run_id, {"state": "canceled", "detail": "robot left navigation mode"}
            )
        self._kiosk_set(phase=PHASE_IDLE)
        return False

    def _on_mission_confirm(self, request, response):
        """The order was taken: the kiosk's button, or the web UI's."""
        del request
        if self._confirm_gate.confirm():
            response.success = True
            response.message = "confirmed"
        else:
            response.success = False
            response.message = "nothing is waiting for a confirmation"
        return response

    def _on_nav_feedback(self, message) -> None:
        feedback = message.feedback
        phase = self._progress.update(
            float(feedback.distance_remaining), int(feedback.number_of_recoveries)
        )
        with self._kiosk_lock:
            driving = self._kiosk.get("phase") in (PHASE_MOVING, PHASE_NEAR, PHASE_BLOCKED)
        if driving:
            self._kiosk_set(phase=phase)

    # ── Kiosk ─────────────────────────────────────────────────────────────────

    def _kiosk_set(self, **fields) -> None:
        with self._kiosk_lock:
            changed = any(self._kiosk.get(key) != value for key, value in fields.items())
            if fields.get("phase") not in (None, self._kiosk.get("phase")):
                self._kiosk_since = time.monotonic()
            self._kiosk.update(fields)
        if changed:
            self._publish_kiosk()

    def _publish_kiosk(self) -> None:
        with self._kiosk_lock:
            view = dict(self._kiosk)
            since = self._kiosk_since
        phase = view.get("phase", PHASE_IDLE)
        navigating = self._mode == MODE_NAV and self._state == STATE_RUNNING
        if not navigating and self._run_thread is None:
            phase = PHASE_OFF
        elif phase == PHASE_DONE and time.monotonic() - since > DONE_HOLD_S:
            phase = PHASE_IDLE
        elif phase == PHASE_FAILED and time.monotonic() - since > FAILED_HOLD_S:
            phase = PHASE_IDLE
        idle = phase in (PHASE_IDLE, PHASE_OFF)
        msg = String()
        msg.data = json.dumps(
            kiosk_status(
                phase=phase,
                robot_mode=f"{self._mode}/{self._state}",
                mission="" if idle else str(view.get("mission") or ""),
                route=[] if idle else list(view.get("route") or []),
                step=None if idle else view.get("step"),
                lap=None if idle else view.get("lap"),
                laps=None if idle else view.get("laps"),
                confirm_remaining=self._confirm_gate.remaining(),
                confirm_timeout=self._confirm_gate.timeout,
                detail=str(view.get("detail") or "") if phase == PHASE_FAILED else "",
            )
        )
        self._kiosk_pub.publish(msg)

    def _run_allowed(self) -> bool:
        return self._mode == MODE_NAV and self._state == STATE_RUNNING

    @staticmethod
    def _more_laps(mode: str, lap: int, laps_target) -> bool:
        if mode == "forever":
            return True
        if mode == "laps":
            return lap < int(laps_target or 1)
        return False

    def _run_wants_stop(self, run_id: str) -> bool:
        """True when the run is no longer one this robot should continue."""
        if self._backend is None:
            return False
        try:
            current = self._backend.get_active_run()
        except BackendError:
            # Unreachable is not a stop. Ending the run because the network
            # blinked would strand a robot holding a payload.
            return False
        if current is None or str(current.get("id")) != run_id:
            return True
        return str(current.get("state")) == "stopping"

    def _run_canceled(self, run_id: str) -> bool:
        """
        True when the run has been ended from outside — canceled, or finished.

        Unlike `_run_wants_stop`, `stopping` is not a cancel: that one means
        "finish this lap", and is honoured where the lap ends.
        """
        if self._backend is None:
            return False
        try:
            current = self._backend.get_active_run()
        except BackendError:
            # Unreachable is not a cancel, for the same reason as above.
            return False
        return current is None or str(current.get("id")) != run_id

    def _wait_for_step(self, handle, run_id: str, timeout_msg: str):
        """
        Wait for a step's goal, giving it up when it should not continue.

        Returns (outcome, None) when the goal finished by itself, or
        (None, (ok, detail)) for the step to return after its goal has been
        canceled — by a mode change, the step timeout, or the run being ended.
        """
        result_future = handle.get_result_async()
        deadline = time.time() + MISSION_STEP_TIMEOUT_S
        next_check = time.time() + RUN_CANCEL_CHECK_S
        while not result_future.done():
            if not self._run_allowed():
                handle.cancel_goal_async()
                return None, (False, "robot left navigation mode")
            if time.time() > deadline:
                handle.cancel_goal_async()
                return None, (False, timeout_msg)
            if time.time() >= next_check:
                next_check = time.time() + RUN_CANCEL_CHECK_S
                if self._run_canceled(run_id):
                    handle.cancel_goal_async()
                    return None, (False, RUN_CANCELED)
            time.sleep(0.1)
        return result_future.result(), None

    def _run_step_nav(self, client, step: dict, run_id: str) -> tuple[bool, str]:
        """
        Drive to one station with Nav2's own navigate_to_pose.

        For robots with no mission manager to hand a station id to. The pose
        comes from the registry, which is where it was taught, rather than from
        anything the robot remembers: a station dragged while the robot was
        parked is then already correct, with nothing to re-push first.

        Only the driving. `task` is not acted on here — reaching the place is
        the whole of a `none` step, and pick and drop need a docking or payload
        behaviour this does not have. A step that asks for one is refused rather
        than quietly treated as a drive-past, which would look like success.
        """
        station_id = str(step["station_id"])
        pose = self._station_poses.get(station_id)
        if pose is None:
            return False, f"station {station_id} is not in this map's registry"

        task = str(step.get("task") or "none")
        if task != "none":
            return False, f"task '{task}' needs a mission manager; this robot has none"

        if not client.wait_for_server(timeout_sec=SERVICE_WAIT_S):
            return False, f"{NAV_READY_ACTION} is not available"

        x, y, yaw = pose
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = "map"
        # Stamped zero on purpose: under sim time a stamp taken from this
        # process is in a different clock to the robot's, and Nav2 then rejects
        # a goal that is perfectly valid.
        goal.pose.header.stamp.sec = 0
        goal.pose.header.stamp.nanosec = 0
        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y
        goal.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(yaw / 2.0)

        send_future = client.send_goal_async(goal, feedback_callback=self._on_nav_feedback)
        deadline = time.time() + MISSION_GOAL_ACCEPT_TIMEOUT_S
        while not send_future.done():
            if time.time() > deadline:
                return False, f"{NAV_READY_ACTION} did not answer"
            time.sleep(0.05)

        handle = send_future.result()
        if handle is None or not handle.accepted:
            return False, f"{NAV_READY_ACTION} rejected the goal"

        outcome, early = self._wait_for_step(
            handle, run_id, f"step timed out after {MISSION_STEP_TIMEOUT_S:.0f}s"
        )
        if early is not None:
            return early

        status = getattr(outcome, "status", None)
        if status != GoalStatus.STATUS_SUCCEEDED:
            # Nav2 aborts for reasons about the map or the surroundings far more
            # often than about the robot, so the code is carried rather than
            # translated into a guess.
            return False, f"navigation did not succeed (status {status})"
        return True, ""

    def _run_step(self, client, step: dict, run_id: str) -> tuple[bool, str]:
        """Send one MissionPlan goal and wait for it. One step, one goal."""
        if not client.wait_for_server(timeout_sec=SERVICE_WAIT_S):
            return False, "mission_plan action server is not available"

        goal = MissionPlan.Goal()
        # The station id, not its name — the same key the agent registered it
        # under. Addressing by display name is what orphaned stations on rename.
        goal.station_id = str(step["station_id"])
        goal.dest_tasks = MISSION_TASK_WIRE.get(str(step.get("task")), 0)
        # `confirm` waits for /mission_confirm, which means somebody has to be
        # standing there to press it.
        goal.continue_mode = str(step.get("confirm", "auto")) != "confirm"

        send_future = client.send_goal_async(goal)
        deadline = time.time() + MISSION_GOAL_ACCEPT_TIMEOUT_S
        while not send_future.done():
            if time.time() > deadline:
                return False, "mission_plan did not answer"
            time.sleep(0.05)

        handle = send_future.result()
        if handle is None or not handle.accepted:
            return False, "mission_plan rejected the goal"

        result, early = self._wait_for_step(handle, run_id, "step timed out")
        if early is not None:
            return early

        outcome = str(result.result.result)
        if not outcome.startswith("SUCCESS"):
            return False, outcome
        return True, outcome

    # ── Stations ──────────────────────────────────────────────────────────────

    def _station_digest(self, stations: list) -> str:
        """A stable fingerprint of the station set, to detect edits."""
        payload = sorted(
            (
                str(row.get("id")),
                str(row.get("type")),
                f"{float(row.get('x', 0)):.4f}",
                f"{float(row.get('y', 0)):.4f}",
                f"{float(row.get('yaw', 0)):.4f}",
            )
            for row in stations
        )
        return hashlib.sha256(repr(payload).encode()).hexdigest()

    def _sync_stations(self) -> None:
        """
        Re-push when the registry's stations have changed.

        Stations move independently of the map: an operator drags a dock while
        the robot is parked, and nothing about the map changes. Pushing only on
        map load would leave the robot addressing the old pose until its next
        restart — and the name would still resolve, so nothing would look wrong.
        """
        map_id = self._loaded_map_id
        if self._backend is None or map_id is None:
            return
        try:
            stations = self._backend.list_stations(map_id)
        except BackendError as error:
            self._backend_state = "unreachable" if error.is_offline else "error"
            return

        # Cached whether or not anything changed: a restarted agent has an empty
        # cache and an unchanged digest, and a mission would then fail to
        # resolve stations that are perfectly well known to the registry.
        self._remember_station_poses(stations, map_id)

        digest = self._station_digest(stations)
        if digest == self._station_hash:
            return
        self.get_logger().info("[robot_agent] station set changed; re-registering")
        if self._apply_stations(map_id, stations):
            self._station_hash = digest

    def _remember_station_poses(self, stations: list, map_id: str | None = None) -> None:
        """
        Keep the poses in memory, and on disk when they came from the server.

        On disk so an agent restarted while the server is down still knows
        where its stations are (see _run_from_snapshot).
        """
        if map_id is not None:
            try:
                self._store.save_stations(map_id, stations)
            except OSError as exc:
                self.get_logger().warning(f"[robot_agent] could not save stations: {exc}")
        self._station_poses = {
            str(station["id"]): (
                float(station["x"]),
                float(station["y"]),
                float(station["yaw"]),
            )
            for station in stations
        }
        self._station_names = {
            str(station["id"]): str(station.get("name") or "") for station in stations
        }

    def _push_stations(self, map_id: str) -> None:
        """
        Register this map's stations with the mission manager.

        The robot keeps stations in a plain dictionary that empties on every
        restart (`self._stations = {}` in mission_manager_node.py), so a site's
        whole layout is one power cut away from being retyped. The registry is
        the source of truth; this is the push that makes the robot agree with
        it, and it runs whenever the loaded map changes.

        Not fatal on failure. A missing station makes one mission step fail with
        "Unknown station_id", which is visible; refusing to load the map would
        take the robot off the floor for a bookkeeping problem.
        """
        if self._backend is None:
            return
        try:
            stations = self._backend.list_stations(map_id)
        except BackendError as error:
            self._backend_state = "unreachable" if error.is_offline else "error"
            self.get_logger().warning(f"[robot_agent] could not read stations: {error}")
            return

        self._remember_station_poses(stations, map_id)

        if self._apply_stations(map_id, stations):
            self._station_hash = self._station_digest(stations)

    def _apply_stations(self, map_id: str, stations: list) -> bool:
        """Make the robot agree with the registry. True when it did."""
        if self._station_file is not None:
            return self._write_dock_database(map_id, stations)
        return self._push_via_service(map_id, stations)

    def _write_dock_database(self, map_id: str, stations: list) -> bool:
        """
        Write the registry as a Nav2 dock database and ask for it to be reloaded.

        For stacks that reach their destinations through opennav_docking rather
        than a mission manager: there is no /station_config there, and the
        docking server reads its destinations from a file.

        The file written is this agent's own, named by the station_file
        parameter and handed to the reload service by path. The robot's existing
        dock database is neither read nor overwritten — it belongs to whoever
        put it there, and a fleet tool that edits other people's configuration
        in place is one nobody can safely run twice.

        Poses are written in the map frame, in metres and radians, which is what
        the registry already holds and what the docking server expects. No unit
        conversion happens anywhere, deliberately.
        """
        lines = [
            "# Generated by robot_agent from the map registry. Do not edit:",
            f"# rewritten whenever the stations of map {map_id} change.",
            "docks:",
        ]
        for station in stations:
            # The id, not the display name: renaming a station must not strand
            # the missions that address it.
            lines.append(f"  {station['id']}:")
            lines.append(f"    type: {self._dock_plugin}")
            lines.append("    frame: map")
            lines.append(
                "    pose: [%.6f, %.6f, %.6f]"
                % (float(station["x"]), float(station["y"]), float(station["yaw"]))
            )
        body = "\n".join(lines) + "\n"

        try:
            self._station_file.parent.mkdir(parents=True, exist_ok=True)
            # Written whole and moved into place. The docking server may read
            # this file at any moment, and half a database is worse than a stale
            # one: it loads, and the destinations that did not make it are
            # simply gone.
            staging = self._station_file.with_suffix(".tmp")
            staging.write_text(body)
            staging.replace(self._station_file)
        except OSError as exc:
            self.get_logger().warning(f"[robot_agent] could not write {self._station_file}: {exc}")
            return False

        # Everything from here is best-effort. The stations are already on disk,
        # and the docking server reads this file when it starts, so a reload that
        # cannot happen now still takes effect at the next launch. Letting it
        # throw would take the robot off the floor over a bookkeeping call — and
        # it did: _call_service raises when a service is missing, the exception
        # escaped the sync timer, and the whole agent died with Nav2 mid-start.
        client = self.create_client(
            ReloadDockDatabase, self._dock_reload_service, callback_group=self._cb
        )
        try:
            request = ReloadDockDatabase.Request()
            request.filepath = str(self._station_file)
            reply = self._call_service(client, request)
            if reply is None or not reply.success:
                self.get_logger().warning(
                    f"[robot_agent] wrote {len(stations)} station(s) to "
                    f"{self._station_file}, but {self._dock_reload_service} "
                    "refused the reload"
                )
                return False
        except Exception as exc:  # noqa: BLE001 — a missing service must not kill the agent
            self.get_logger().warning(
                f"[robot_agent] wrote {len(stations)} station(s) to "
                f"{self._station_file}, but could not reload the dock database: {exc}"
            )
            return False
        finally:
            self.destroy_client(client)

        self._station_ids = {str(s["id"]) for s in stations}
        self.get_logger().info(
            f"[robot_agent] wrote {len(stations)} station(s) for map {map_id} "
            f"to {self._station_file} and reloaded the dock database"
        )
        return True

    def _push_via_service(self, map_id: str, stations: list) -> bool:
        """Register each station with the mission manager. True when all landed."""
        client = self.create_client(
            StationConfig, STATION_CONFIG_SERVICE, callback_group=self._cb
        )
        try:
            wanted: set[str] = set()
            pushed = 0
            for station in stations:
                wanted.add(str(station["id"]))
                request = StationConfig.Request()
                # The id, not the name. The old UI keyed stations by display
                # name, so renaming one registered a second station and
                # orphaned the first; a mission then addressed neither.
                request.station_id = str(station["id"])
                request.type = STATION_TYPE_WIRE.get(str(station.get("type")), 0)
                request.x_pose = float(station["x"])
                request.y_pose = float(station["y"])
                request.yaw_pose = float(station["yaw"])
                request.action = STATION_ACTION_SAVE
                reply = self._call_service(client, request)
                if reply is None:
                    raise RuntimeError("no reply from /station_config")
                pushed += 1
            # Withdraw what the registry no longer has. Omitting a station
            # leaves it in the robot's memory for the rest of its uptime, and a
            # mission written against a stale id would still resolve — to a pose
            # nobody can see any more.
            removed = 0
            for stale in self._station_ids - wanted:
                request = StationConfig.Request()
                request.station_id = stale
                request.action = STATION_ACTION_DELETE
                self._call_service(client, request)
                removed += 1

            self._station_ids = wanted
            self.get_logger().info(
                f"[robot_agent] registered {pushed} station(s) for map {map_id}"
                + (f", withdrew {removed}" if removed else "")
            )
            return True
        except Exception as exc:  # noqa: BLE001 — a failed push must not kill the agent
            # The digest is left alone, so the next sync tries again rather than
            # believing the robot is up to date.
            self.get_logger().warning(f"[robot_agent] station push failed: {exc}")
            return False
        finally:
            self.destroy_client(client)

    # ── Switching ─────────────────────────────────────────────────────────────

    def _switch(self, mode: str) -> None:
        try:
            # Whatever happens next, the robot must not keep executing the
            # operator's last teleop command through the transition.
            self._halt_teleop()
            self._set_state(self._mode, STATE_STOPPING, "Stopping current stack")
            self._stop_child()

            if mode == MODE_STOP:
                self._set_state(MODE_UNKNOWN, STATE_IDLE, "Stopped on request")
                return

            self._set_state(mode, STATE_STARTING, f"Starting {mode} stack")
            self._start_child(mode)

            markers = SLAM_MARKER_NODES if mode == MODE_MAP else NAV_MARKER_NODES
            if self._await_ready(markers) and self._await_usable(mode):
                self._set_state(mode, STATE_RUNNING, "")
                self.get_logger().info(f"[robot_agent] {mode} mode running")
            else:
                detail = f"Timed out after {READY_TIMEOUT_S:.0f}s waiting for {mode} nodes"
                self._stop_child()
                self._set_state(mode, STATE_FAILED, detail)
                self.get_logger().error(f"[robot_agent] {detail}")
        except Exception as exc:  # noqa: BLE001 — a failed switch must not kill the agent
            self._set_state(self._mode, STATE_FAILED, str(exc))
            self.get_logger().error(f"[robot_agent] switch failed: {exc}")

    def _halt_teleop(self) -> None:
        """Send a stop and drop the held command."""
        with self._teleop_lock:
            had_command = self._teleop_cmd is not None
            self._teleop_cmd = None
            self._teleop_stops_sent = TELEOP_STOP_REPEATS
        if had_command:
            for _ in range(TELEOP_STOP_REPEATS):
                self._cmd_vel_pub.publish(self._zero_twist())
        self._teleop_active = False

    def _launch_command(self, mode: str) -> list[str]:
        use_sim_time = "true" if self._use_sim_time_arg else "false"
        if mode == MODE_MAP:
            cmd = [
                "ros2", "launch", self._slam_launch_pkg, self._slam_launch_file,
                f"use_sim_time:={use_sim_time}",
            ]
        else:
            cmd = [
                "ros2", "launch", self._nav_launch_pkg, self._nav_launch_file,
                f"use_sim_time:={use_sim_time}",
                f"map:={self._current_map}",
            ]
        if mode == MODE_MAP:
            return cmd + self._slam_extra_launch_args + self._extra_launch_args
        return cmd + self._extra_launch_args

    def _start_child(self, mode: str) -> None:
        cmd = self._launch_command(mode)
        self.get_logger().info(f"[robot_agent] exec: {shlex.join(cmd)}")

        # stderr to a file, stdout left on the console. A launch that dies on
        # startup says why on stderr, and "exited with code 1" on its own sends
        # whoever is reading it to go and reproduce the failure by hand — which
        # is exactly what happened when a renamed script was not reinstalled.
        self._child_errors = tempfile.NamedTemporaryFile(  # noqa: SIM115 — closed in _stop_child
            mode="w+", prefix="amr-launch-", suffix=".log", delete=False
        )
        # start_new_session puts the launch and everything it spawns in their
        # own process group, so the whole tree can be signalled at once. Without
        # it, killing `ros2 launch` leaves its children running and the next
        # start collides with the previous stack.
        self._child = subprocess.Popen(
            cmd,
            start_new_session=True,
            stdout=subprocess.PIPE,
            stderr=self._child_errors,
        )
        # Nav2 logs to stdout, so a goal that fails says why on a terminal and
        # nowhere else: diagnosing a robot meant asking whoever was next to it
        # to copy lines across. Every line still goes to the console, and also
        # to a file that outlives the launch.
        threading.Thread(
            target=_tee_child_output,
            args=(self._child.stdout, launch_log_path(mode)),
            name=f"launch-log-{mode}",
            daemon=True,
        ).start()
        if mode == MODE_NAV:
            self._start_zone_mask()

    def _start_zone_mask(self) -> None:
        """
        Run zone_mask_server next to navigation, when this stack needs it.

        It turns the zone polygons on /amr/zones into the masks Nav2's costmap
        filters read. A stack whose launch does not start one has zones in the
        registry that change nothing on the floor — a keepout drawn round a
        switchboard that the robot drives straight through.
        """
        script = self._zone_mask_script
        if script is None:
            return
        if not script.is_file():
            self.get_logger().warning(
                f"[robot_agent] zone_mask_script {script} not found; zones will not be applied"
            )
            return
        use_sim_time = "true" if self._use_sim_time_arg else "false"
        cmd = [sys.executable, str(script), "--ros-args", "-p", f"use_sim_time:={use_sim_time}"]
        self.get_logger().info(f"[robot_agent] exec: {shlex.join(cmd)}")
        self._zone_mask = subprocess.Popen(cmd, start_new_session=True)

    def _child_error_tail(self, lines: int = 4) -> str:
        """The last few lines the launch complained about, for the status."""
        handle = self._child_errors
        if handle is None:
            return ""
        try:
            handle.flush()
            with open(handle.name, encoding="utf-8", errors="replace") as source:
                tail = [line.strip() for line in source.readlines() if line.strip()]
        except OSError:
            return ""
        return " / ".join(tail[-lines:])

    def _await_ready(self, markers: tuple[str, ...]) -> bool:
        deadline = time.time() + READY_TIMEOUT_S
        while time.time() < deadline:
            if self._child is not None and self._child.poll() is not None:
                detail = self._child_error_tail()
                raise RuntimeError(
                    f"launch exited early with code {self._child.returncode}"
                    + (f": {detail}" if detail else "")
                )
            if self._nodes_present(markers):
                return True
            time.sleep(0.5)
        return False

    def _await_usable(self, mode: str) -> bool:
        """
        Wait until the stack can actually be given work.

        Only navigation has anything to wait for. Its nodes come up, and then
        the lifecycle manager configures and activates them; the action server
        is the last thing to appear. Between those two moments the stack looks
        present and refuses every goal.
        """
        if mode != MODE_NAV:
            return True

        client = ActionClient(self, NavigateToPose, NAV_READY_ACTION, callback_group=self._cb)
        try:
            deadline = time.time() + NAV_ACTIVATE_TIMEOUT_S
            while time.time() < deadline:
                if self._child is not None and self._child.poll() is not None:
                    raise RuntimeError(
                        f"launch exited while activating (code {self._child.returncode})"
                    )
                if client.wait_for_server(timeout_sec=1.0):
                    self.get_logger().info("[robot_agent] navigation is accepting goals")
                    return True
            self.get_logger().error(
                f"[robot_agent] {NAV_READY_ACTION} never became available"
            )
            return False
        finally:
            client.destroy()

    def _release_child_errors(self) -> None:
        """Close and remove the stderr capture. Failing to is a leak per switch."""
        handle = self._child_errors
        self._child_errors = None
        if handle is None:
            return
        try:
            handle.close()
            os.unlink(handle.name)
        except OSError:
            pass

    def _stop_child(self) -> None:
        companion = self._zone_mask
        self._zone_mask = None
        if companion is not None:
            self._stop_group(companion)

        child = self._child
        self._child = None
        self._release_child_errors()
        if child is not None:
            self._stop_group(child)

    def _stop_group(self, child: subprocess.Popen) -> None:
        """Stop a process started in its own session, and everything it spawned."""
        if child.poll() is not None:
            return

        pgid = os.getpgid(child.pid)

        # SIGINT first: ros2 launch treats it as a shutdown request and lets its
        # children exit cleanly, which matters for anything holding a map file.
        for sig, grace in ((signal.SIGINT, SIGINT_GRACE_S), (signal.SIGTERM, SIGTERM_GRACE_S)):
            try:
                os.killpg(pgid, sig)
            except ProcessLookupError:
                return
            deadline = time.time() + grace
            while time.time() < deadline:
                if child.poll() is not None:
                    return
                time.sleep(0.2)

        # Nothing polite worked. An orphaned stack would hold the topics the
        # next mode needs, so this is not optional.
        try:
            os.killpg(pgid, signal.SIGKILL)
            child.wait(timeout=5)
            self.get_logger().warning("[robot_agent] child needed SIGKILL")
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass

    def destroy_node(self) -> bool:
        self._stop_child()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RobotAgent()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
