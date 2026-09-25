# AMR Web UI — Architecture Audit & Redesign Proposal

**Audit date:** 2026-09-25
**Scope:** `web-ui/`, `backend/`, plus the `ros2_ws/` interfaces and launch files needed to understand how they connect.
**Status:** Audit and proposal only. No application behaviour was changed.

**Evidence rule:** every finding below cites a file and line from this repository. Where something could not be verified from code, it is marked `NOT VERIFIED`.

Two prior audits cover related ground and are still accurate where cited: [`WEB_UI_BACKEND_END_TO_END_ARCHITECTURE.md`](WEB_UI_BACKEND_END_TO_END_ARCHITECTURE.md) (2026-09-18) and [`history/investigations/WEB_UI_STARTUP_PLAYWRIGHT_UX_AUDIT.md`](history/investigations/WEB_UI_STARTUP_PLAYWRIGHT_UX_AUDIT.md) (2026-09-18). This document does not repeat them; it extends them with the multi-robot, design-system, technology and roadmap analysis.

> **Note (2026-09-25):** the documentation reorganisation proposed in §13 has since been executed. File paths cited in §13.4 are the *pre-move* paths; the resulting structure is recorded in §13.3.

---

## Table of contents

1. [Current architecture](#1-current-architecture)
2. [Current frontend stack](#2-current-frontend-stack)
3. [Current backend integration](#3-current-backend-integration)
4. [Single-robot assumptions](#4-single-robot-assumptions)
5. [UX problems](#5-ux-problems)
6. [Design system problems](#6-design-system-problems)
7. [Performance assessment](#7-performance-assessment)
8. [Technology comparison](#8-technology-comparison)
9. [Recommended frontend architecture](#9-recommended-frontend-architecture)
10. [Proposed information architecture](#10-proposed-information-architecture)
11. [Proposed design system](#11-proposed-design-system)
12. [Multi-robot migration strategy](#12-multi-robot-migration-strategy)
13. [Documentation cleanup plan](#13-documentation-cleanup-plan)
14. [Implementation roadmap](#14-implementation-roadmap)
15. [Appendix — defect register](#15-appendix--defect-register)

---

## 1. Current architecture

### 1.1 Process topology

```
┌─ Browser ────────────────────────────────────────────────┐
│  Vue 3 SPA (Vite dev server :3000)                       │
│                                                          │
│   useAPI.js  ──── HTTP ────────┐                         │
│   useROS.js  ──── WebSocket ───┼──┐                      │
└───────────────────────────────┬┴──┴──────────────────────┘
                                │   │
              ┌─────────────────┘   └──────────────────┐
              ▼                                        ▼
┌─ amr-backend (:3001) ─────────┐     ┌─ amr-sim container ─────────────┐
│  FastAPI + raw sqlite3        │     │  rosbridge_websocket  :8765     │
│  /api/maps /missions /keepout │     │  web_video_server     :8080     │
│  /docks /destinations /mode   │     │  Nav2 / slam_toolbox            │
│  StaticFiles  /maps/*         │     │  mission_manager_node.py        │
│  /data/amr.db  (SQLite WAL)   │     │  docking_manager_node.py        │
│  ── NO ROS LIBRARIES ──       │     │  Gazebo Harmonic                │
└───────────────────────────────┘     └─────────────────────────────────┘
        shares ./maps volume ◄──────────────────► shares ./maps volume
```

The key structural fact: **the backend is not on the robot control path.** It never imports `rclpy`, opens no WebSocket, and holds no live robot state. It is a CRUD store for SQLite rows plus a static file server for map images. All real-time control and telemetry goes browser → rosbridge → ROS 2, bypassing the backend entirely.

Evidence: `backend/main.py:1-60` imports only `fastapi`, `psutil`, `database`, `routers`. No `rclpy`, no `roslibpy`, no `websockets`. `backend/requirements.txt:1-6` lists six packages, none ROS-related.

Also note the web UI is **not** in `docker-compose.yml:1-95`. Only `amr-sim`, `amr-backend` and an optional `teleop` profile are defined. The UI runs on the host via `npm run dev` (`README.md:33-36`, `scripts/setup_webui.sh`).

### 1.2 Data flows

**Telemetry (robot → UI).** Browser subscribes directly:

| Topic | Type | Handler | Store target |
|---|---|---|---|
| `/map` | `nav_msgs/OccupancyGrid` | `useROS.js:323-344` (manual `transient_local` QoS) | `mapData` |
| `/tf`, `/tf_static` | `tf2_msgs/TFMessage` | `useROS.js:349-380` (throttle 33 ms) | `robotPose` via TF chain |
| `/amcl_pose`, `/pose` | `PoseWithCovarianceStamped` | `useROS.js:383-409` | `robotPose` (fallback only) |
| `/odom` | `nav_msgs/Odometry` | `useROS.js:412-421` | `robotVelocity` |
| `/plan` | `nav_msgs/Path` | `useROS.js:424-437` | `plannedPath` |
| `/scan` | `sensor_msgs/LaserScan` | `useROS.js:439-446` (no throttle) | `laserScan` |
| `/particle_cloud` | `nav2_msgs/ParticleCloud` | `useROS.js:448-463` (no throttle) | `particleCloud` |
| `/global_costmap/costmap` | `nav_msgs/OccupancyGrid` | `useROS.js:536-545` (throttle 500 ms) | `costmapData` |
| `/robot_description` | `std_msgs/String` | `useROS.js:465-496` | `robotFootprint` (URDF parsed in browser) |
| `/robot_status` | `custom_interfaces/msg/RobotStatus` | `useROS.js:547-605` | nav status, dock status, battery |
| `/battery_state` | `sensor_msgs/BatteryState` | `useROS.js:607-624` | battery (fallback) |
| `/dock_status` | `std_msgs/String` | `useROS.js:278-321` | docking status |
| `/mission_plan/_action/status` | `action_msgs/GoalStatusArray` | `useROS.js:229-256` | mission advance trigger |
| `/mission_plan/_action/feedback` | `MissionPlan_FeedbackMessage` | `useROS.js:259-275` | nav status |
| `/navigate_to_pose/_action/status` | `action_msgs/GoalStatusArray` | `useROS.js:201-226` | single-goal completion |

**Commands (UI → robot).** Also direct:

| Operation | Mechanism | Location |
|---|---|---|
| Manual drive | publish `/cmd_vel` at 12.5 Hz | `useROS.js:1069-1078`, driven by `MappingPanel.vue` `setInterval(…, 80)` |
| Single goal | publish `/goal_pose` | `useROS.js:641-659` |
| Mission | `op: 'send_action_goal'` to `/mission_plan` | `useROS.js:715-725` |
| Mission confirm | service `/mission_confirm` (`std_srvs/Trigger`) | `useROS.js:816-839` |
| Dock / undock / cancel | service `/dock_command` | `useROS.js:879-911` |
| Station register/delete | service `/station_config` | `useROS.js:1174-1198` |
| Load map | service `/map_server/load_map` | `useROS.js:1001-1013` |
| Save map | service `/slam_toolbox/save_map` | `useROS.js:1022-1053` |
| Initial pose | publish `/initialpose` | `useROS.js:1086-1108` |
| Keepout zones | publish `/amr/keepout_zones` (JSON in `std_msgs/String`) | `useROS.js:1153-1164` |
| Mission payload | publish `/amr/mission_payload` (JSON in `std_msgs/String`) | `useROS.js:1117-1145` |
| Robot mode | service `/robot_mode` — **exported but never called** | `useROS.js:852-877`, `useROS.js:1243` |

**Persistence (UI → backend).** Plain REST through `useAPI.js:19-58`: maps, missions, keepout, docks, destinations, mode.

### 1.3 The dual-write pattern

Every spatial entity is written **twice, without a transaction**: once to SQLite via REST, once to the robot via `/station_config`. Example — `MissionPanel.vue` `onMapClick`:

```js
const saved = await api.post('/destinations', {…})   // SQLite
store.addDestination(saved)
ros.configStation({ station_id: saved.name, … })     // robot, fire-and-forget
```

The ROS call is not awaited and its failure is not surfaced. If rosbridge is down, the destination exists in the database and the operator sees a success toast, but the robot has never heard of the station. The same pattern appears in `DockingPanel.vue` (`fetchDocks`, `addDock`, `removeDock`, `saveRename`), `App.vue:958-989` (`confirmDockPlacement`), and `MissionPanel.vue` (`changeDestType`, `renameDestination`, `updateDestYaw`, `deleteDestination`, `startMission`).

**There is no reconciliation.** Nothing ever compares the SQLite station set against the robot's registry. Drift is permanent and invisible.

### 1.4 Identity mismatch

The robot identifies stations by **name** (`station_id: saved.name`); SQLite identifies them by **integer id**. Renaming a dock (`DockingPanel.vue` `saveRename`) calls `configStation` with the new name and `action: 1` (save), but never calls `action: 0` (delete) for the old name. The old station stays registered on the robot forever.

---

## 2. Current frontend stack

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Framework | Vue 3 (Composition API, `<script setup>`) | ^3.4.0 | |
| Build | Vite | ^5.1.0 | `vite.config.js:1-19`, alias `@` → `src` |
| Language | **JavaScript, not TypeScript** | — | `jsconfig.json`; `components.json` has `"typescript": false` |
| Routing | **none** | — | `vue-router@^4.3.0` installed, **0 imports** |
| State | Pinia | ^2.1.7 | one store: `stores/robot.js` (440 lines) |
| Styling | Tailwind CSS | ^3.4.1 | + `tailwindcss-animate` |
| Components | shadcn-vue (new-york, zinc) on **reka-ui** | reka-ui ^2.9.2 | **`radix-vue@^1.9.17` also installed, 0 imports** |
| Icons | `lucide-vue-next` + `@radix-icons/vue` | | both used |
| Map | Leaflet | ^1.9.4 | `L.CRS.Simple`, 100 px per metre |
| 3D | **`ros3d`, `three`** | | **0 imports each** |
| Charts | ECharts + `vue-echarts` | ^6.0.0 | 2 charts, 1 of them dead |
| ROS | `roslib` | ^1.4.0 | against `rosbridge_server`, not Foxglove |
| Toasts | **`vue-sonner` AND a hand-rolled `useToast`** | | two systems, see §6.3 |
| Utils | `@vueuse/core`, `clsx`, `tailwind-merge`, `cva` | | |

Total application source: **9,611 lines** across `.vue`/`.js`/`.css` in `src/`.

### 2.1 Size distribution

| File | Lines | Assessment |
|---|---:|---|
| `components/MapView.vue` | 1,594 | Leaflet + 7 interaction modes + camera overlay + all rendering |
| `composables/useROS.js` | 1,245 | Connection, 14 subscriptions, 11 commands, mission state machine |
| `App.vue` | 1,210 | Shell + Overview page + 3 dialogs + battery + mode sync + E-STOP CSS |
| `components/MissionPanel.vue` | 509 | Destinations CRUD + waypoints + mission control + save/load |
| `stores/robot.js` | 440 | Single flat store, 40+ refs |
| `components/MissionEditor.vue` | 419 | **dead — never imported** |
| `components/MappingPanel.vue` | 311 | Joystick + D-pad + speed presets + save map |
| `components/DockingPanel.vue` | 289 | Dock CRUD + dock/undock + auto-dock config |
| `components/MapManager.vue` | 259 | **dead — never imported** |
| `components/SetupPanel.vue` | 249 | Maps + upload + keepout (duplicates MapManager + KeepoutEditor) |

Three files hold 42 % of the codebase. `App.vue` and `MapView.vue` are both god components.

### 2.2 Dead code

Never imported anywhere:

| File | Lines |
|---|---:|
| `components/MissionEditor.vue` | 419 |
| `components/MapManager.vue` | 259 |
| `components/NavigationPanel.vue` | 148 |
| `components/StatusPanel.vue` | 139 |
| `components/ControlPanel.vue` | 129 |
| `components/KeepoutEditor.vue` | 98 |
| `components/charts/BatteryChart.vue` | 74 |
| `components/ToastManager.vue` | 2 (empty template + comment) |
| **Total** | **~1,268 (13 % of `src/`)** |

`ControlPanel.vue` calls `useAPI()` and `useToast()` **without importing either** — it would throw `ReferenceError` on mount. It cannot ever have been rendered in its current form. This is strong evidence the dead set is genuinely dead, not merely lazily wired.

Unused shadcn primitives (generated, 42 files, never imported): `ui/select` (11 files), `ui/sheet` (9), `ui/table` (10), `ui/tabs` (5), `ui/tooltip` (5), `ui/skeleton` (2). Meanwhile **12 native `<select>` elements** are hand-styled inline (e.g. `App.vue:542-551`, `App.vue:648-657`).

---

## 3. Current backend integration

### 3.1 API surface

797 lines total. Raw `sqlite3`, no ORM, no migrations framework (three `ALTER TABLE` statements in a try/except loop at `database.py:84-93`).

| Method | Path | Handler | Note |
|---|---|---|---|
| GET | `/health` | `main.py:45` | |
| GET | `/api/stats` | `main.py:50-60` | `latency_ms` always `null` |
| GET | `/api/maps` | `maps.py:118-122` | **scans filesystem and mutates DB as a side effect** |
| POST | `/api/maps/{id}/activate` | `maps.py:125-133` | returns a path string only; does not talk to ROS |
| POST | `/api/maps/upload` | `maps.py:136-175` | |
| DELETE | `/api/maps/{id}` | `maps.py:178-186` | |
| GET/POST/PUT/DELETE | `/api/missions` | `missions.py` | |
| GET/POST/DELETE | `/api/keepout` | `keepout.py` | **no PUT** |
| GET/POST/PUT/DELETE | `/api/docks` | `docks.py` | |
| GET/POST/PUT/DELETE | `/api/destinations` | `destinations.py` | |
| GET | `/api/mode` | `mode.py:41-43` | |
| POST | `/api/mode/switch` | `mode.py:46-68` | **does not switch anything** |
| — | `/maps/*` | `main.py:37` | StaticFiles |

### 3.2 `/api/mode/switch` does not switch the mode

```python
# backend/routers/mode.py:58-68
_save_mode(req.mode, map_file)
return SwitchResponse(
    mode=req.mode, map_file=map_file,
    message=(f"{label} disimpan. Jalankan command runtime di terminal host: "
             f"bash scripts/docker_run.sh {'slam' if req.mode == 'slam' else f'nav {map_file}'}"),
)
```

It writes two rows to the `settings` table and returns a sentence telling a human to run a shell command. No ROS service is called, no process is spawned.

The UI treats this as success: `App.vue:829-832` does `toast.success(response?.message || …)` and `App.vue:822` immediately does `store.setAppMode(mode)`. The operator sees a green toast, the sidebar switches to the other mode's tabs, and **the robot's actual stack is unchanged**. If the robot was running SLAM, it is still running SLAM while the UI presents Navigation panels.

A `/robot_mode` service exists as an interface (`custom_interfaces/srv/RobotMode.srv`) and a client exists in the frontend (`useROS.js:852-877`), but:
- no node in `ros2_ws/src/` advertises `/robot_mode` (verified by grep across all `.py`);
- `callRobotModeService` is exported at `useROS.js:1243` and **called from nowhere**.

So the mode-switch feature is stubbed end to end, and the UI reports success regardless. This is the single most misleading behaviour in the application.

### 3.3 Cascade deletion of operator data

```sql
-- backend/database.py:44-72
CREATE TABLE keepout_zones ( … map_id INTEGER NOT NULL REFERENCES maps(id) ON DELETE CASCADE … );
CREATE TABLE dock_stations ( … map_id INTEGER REFERENCES maps(id) ON DELETE CASCADE … );
CREATE TABLE destinations  ( … map_id INTEGER REFERENCES maps(id) ON DELETE CASCADE … );
```

`database.py:101` enables `PRAGMA foreign_keys = ON`. And `GET /api/maps` — an ordinary read — deletes map rows whose file has disappeared:

```python
# backend/routers/maps.py:76-80
for row in existing:
    if row["yaml_file"] not in yaml_files:
        db.execute("DELETE FROM maps WHERE id = ?", (row["id"],))
```

**Consequence:** an engineer who renames, moves or deletes a `.yaml` in the maps folder destroys every keepout zone, dock station and destination associated with it, the next time anyone loads the UI. There is no warning, no confirmation, and no backup. `missions` survives (`ON DELETE SET NULL`, `database.py:37`) but loses its map binding.

`DELETE /api/maps/{id}` (`maps.py:178-186`) has the same effect and is also ineffective: it removes the DB row but leaves the file on disk ("files stay on disk — managed by engineer"), so the next `GET /api/maps` re-registers the same file under a **new id** — with all of its children already cascaded away.

### 3.4 API contract loses fields

**Missions lose station binding.** `MissionPanel.vue` `doSave` sends:

```js
waypoints: store.waypoints.map(w => ({ name, x, y, theta, task, continue_mode,
                                       dest_point: w.destPoint ?? null,
                                       station_id: w.stationId ?? null }))
```

`models.py:28-34` defines `WaypointItem` with exactly `name, x, y, theta, task, continue_mode`. Pydantic v2 ignores unknown fields by default, so `dest_point` and `station_id` are silently dropped on write. On read, `doLoad` does `stationId: w.station_id ?? null` → always `null`. `startMission` then regenerates a station id from the display name (`w.name.replace(/\s+/g, '_')`), which is not the id the destination was registered under. **A saved and reloaded mission does not address the same stations as the original.**

**Docks lose their approach pose.** `DockIn` (`models.py:106-109`) has `map_id`, `name`, `target` — no `approach`. The DB has `approach_x`, `approach_y`, `approach_yaw` (`database.py:58-60`). `docks.py:38-41` hardcodes them to `NULL` on create, and `docks.py:55-58` hardcodes them to `NULL` on update. `App.vue:972` sends `approach: { x: approach_x, y: approach_y, yaw }` from the two-click map placement flow. **The operator's second click is discarded.** The columns exist and are permanently null.

**Destination yaw is silently reset.** `MissionPanel.vue` `changeDestType` sends `{ name, x, y, station_type }` with no `yaw`. `DestinationIn.yaw` defaults to `0.0` (`models.py:83`), and `destinations.py:41-44` writes `yaw = ?` unconditionally. **Changing a destination's type resets its orientation to zero.** The robot is then re-registered at yaw 0 via `configStation`.

### 3.5 Security posture

```python
# backend/main.py:20-25
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
```

No authentication, no authorisation, no rate limiting, on any endpoint. Combined with `rosbridge_websocket` on `:8765` (also unauthenticated — `bringup.launch.py:113-116`) and `network_mode: host` (`docker-compose.yml:44`), **anyone with network reach to the robot can drive it, delete its maps, and reconfigure its stations.** For a LAN-isolated lab this may be an accepted risk; it must be a conscious decision, and it must not survive into a multi-robot fleet deployment where the blast radius is every robot at once.

### 3.6 ROS-side service conflicts

Both manager nodes are launched together (`amr_bringup/launch/bringup.launch.py:147,165,187,189`), and both advertise the same names:

| Name | mission_manager | docking_manager |
|---|---|---|
| `/station_config` (service) | `mission_manager_node.py:114-119` | `docking_manager_node.py:107` |
| `/dock_command` (service) | `mission_manager_node.py:121-126` | `docking_manager_node.py:106` |
| `/dock_status` (publisher) | `mission_manager_node.py:80` | `docking_manager_node.py:110` |
| `/cmd_vel` (publisher) | `mission_manager_node.py:81` | `docking_manager_node.py:111` |

In ROS 2, two servers on one service name is not an error — the client binds to whichever it discovers, non-deterministically. **Which node answers a `/station_config` call is undefined**, and the two nodes keep separate station registries. This is the likely root cause of any "the robot doesn't know about the station I just created" class of bug.

`/cmd_vel` additionally has four uncoordinated publishers (both managers, the Nav2 controller, and the browser joystick at 12.5 Hz) with no `twist_mux` arbitration.

---

## 4. Single-robot assumptions

Classified as: **UI** (presentation only) · **FE** (frontend architecture) · **BE** (backend) · **API** (contract) · **ROS** (integration).

| # | Assumption | Evidence | Class | What multi-robot requires |
|---|---|---|---|---|
| 1 | One rosbridge URL, from one build-time env var | `.env:3` `VITE_ROS_URL`; `stores/robot.js:31-34` | FE | Per-robot connection config, resolved at runtime from a registry, not at build time |
| 2 | One module-level `ROSLIB.Ros` singleton | `useROS.js:21` `let _ros = null`; `useROS.js:146` `if (_ros) disconnect()` | FE | Connection pool keyed by robot id; `connect()` must not tear down other robots |
| 3 | One global `connected` flag | `useROS.js:22` `const _connected = ref(false)`; `stores/robot.js:30` | FE/UI | Per-robot connection state; a fleet view shows N independent states |
| 4 | One TF buffer, one pose | `useROS.js:42` `const _tfBuffer = {}`; `stores/robot.js:45` `robotPose` | FE | TF buffer and pose per robot |
| 5 | One mission execution state machine | `useROS.js:29-33` module-level `_missionWaypoints/_missionIndex/_missionRunning` | FE | Mission runner instance per robot; a second robot's mission currently overwrites the first's index |
| 6 | One Pinia store instance holds *all* robot state | `stores/robot.js:17-440` — pose, battery, nav status, docking, waypoints all flat | FE | Split: `useFleetStore` (registry) + `useRobotStore(robotId)` factory + workspace stores |
| 7 | Unqualified topic names | `/cmd_vel`, `/odom`, `/scan`, `/map`, `/tf`, `/goal_pose`, `/robot_status`, `/dock_status` throughout `useROS.js` | ROS | Namespacing (`/robot_a/cmd_vel`) or one bridge per robot. Namespacing changes the TF frame strategy too (`useROS.js:79-85` hardcodes `map`/`odom`/`base_footprint`) |
| 8 | No `robot_id` column anywhere | `database.py:22-77` — six tables, zero robot references | BE/API | `robots` table; `robot_id` FK on `missions`, and a decision on whether maps/docks/destinations are fleet-shared or per-robot |
| 9 | Mode is a single global setting | `settings` rows `ros_mode`, `ros_map_file` (`database.py:79-80`); `mode.py:23-38` | BE/API | Mode is per robot. Global mode is meaningless in a fleet |
| 10 | Station registry keyed by name, in one robot's memory | `useROS.js:1174-1198`; `mission_manager_node.py:73` `self._stations: dict` | ROS/API | Stations are fleet-level map data; each robot needs a sync protocol, not a per-robot in-memory dict |
| 11 | Backend base URL hardcoded to localhost | `useAPI.js:17` `const BASE = 'http://localhost:3001/api'`; `useAPI.js:65` | FE | Configurable base URL; a fleet backend is not on the operator's machine |
| 12 | Camera URL derived from the single ROS host | `MapView.vue:459-471` — takes `rosUrl` hostname, hardcodes port 8080 | UI/FE | Per-robot camera endpoint in the registry |
| 13 | `/api/stats` reports the **backend host's** CPU/RAM, labelled "System" | `main.py:50-60`; `App.vue:408-424` | UI | Distinguish operator-station metrics from per-robot diagnostics |
| 14 | One `appMode` drives the entire navigation tree | `stores/robot.js:23`; `App.vue:799-801` | UI/FE | Mode belongs to the selected robot, not the application |
| 15 | Auto-dock watcher is global | `App.vue:992-1014` watches `store.batteryPercent` | FE | Per-robot policy and per-robot watcher |
| 16 | `activeMapId` is a single global | `stores/robot.js:81` | FE/API | Robots may be on different maps simultaneously |

**Nothing in the SQLite schema, the REST contract, the ROS topic names, or the frontend state model is robot-aware.** The single-robot assumption is structural, not cosmetic. It is, however, mostly *additive* to fix — see §12.

One useful property: because the backend is a pure CRUD store with no live state, adding `robot_id` is a schema and contract change, not a redesign of a stateful service. The hard part is the frontend connection/state model and the ROS namespace decision.

---

## 5. UX problems

### 5.1 Information architecture

Current navigation is a two-level construct: a global **mode** toggle in the header (`App.vue:29-57`) that changes which **tabs** the sidebar shows (`App.vue:788-801`):

```
Navigation mode:  Overview · Mission · Docking · Setup
Mapping mode:     Overview · Mapping
```

Problems:

- **Mode is presented as an application-level switch, but it is a robot-level operating state.** The header control sits next to the brand mark, implying "what part of the app am I in", while it actually means "what stack is the robot running". In a fleet this framing breaks completely.
- **Switching mode hides Mission, Docking and Setup entirely.** Dock stations and destinations are map data that remain valid during mapping, but become unreachable.
- **`Setup` is a grab-bag**: map library, map upload, and keepout zones (`SetupPanel.vue`). Map management is spatial/fleet-level; keepout editing is a map-authoring task. They are grouped because they were built at the same time, not because they belong together.
- **`Overview` is a dumping ground**: connection control, pose readout, status badges, AMCL init pose, a velocity chart, and host system stats (`App.vue:250-425`). Three different altitudes of concern in one scroll.
- **No URL routing at all.** `activeTab` is a local `ref` (`App.vue:742`). There is no deep link to a screen, no browser back, no bookmark, and a refresh returns to `overview` with all in-memory state gone.

### 5.2 Robot context

**The UI never identifies which robot it is controlling.** There is no name, no serial, no model, no IP shown anywhere — the only identifying string is the raw `VITE_ROS_URL` in the Overview connection row (`App.vue:262`) and the startup dialog (`App.vue:597`).

Today this is survivable because there is exactly one robot. The moment there are two, an operator can have two browser tabs open against two robots, with **identical-looking UIs**, and drive the wrong one. There is no colour, no name, no badge to tell them apart.

What the UI currently does communicate:

| Signal | Where | Quality |
|---|---|---|
| Connection | header dot + ONLINE/OFFLINE (`App.vue:130-145`) | good |
| Availability | `AVAILABLE`/`BUSY` badge (`App.vue:82-91`) | good, derived from `isBusy` (`stores/robot.js:151-155`) |
| Nav status | badge with raw enum text (`App.vue:94-99`) | weak — `following_waypoints` shown as "following waypoints" |
| Docking status | badge in Overview only (`App.vue:340-348`) | not visible from other tabs |
| Battery | header meter + % + voltage (`App.vue:102-127`) | good |
| Pose | header strip, `lg:` breakpoint only (`App.vue:62-77`) | hidden on smaller screens |
| Operating mode | header toggle (reflects UI belief, not robot truth) | **actively misleading** (§3.2) |
| Localisation quality | — | **absent** — particle cloud is drawn but never scored |
| Faults | — | **absent** — no fault list; `sts === 5` collapses to `navStatus: "error"` with no detail |
| Emergency state | — | **absent** — no latched e-stop state, see §5.3 |
| Movement authority | — | **absent** — nothing says whether the operator or the autonomy stack currently owns `/cmd_vel` |

### 5.3 Operational safety

**The E-STOP does not stop the robot.**

```js
// App.vue:941-945
function emergencyStop() {
  ros.cancelNavigation();
  store.stopMission();
  toast.error("Emergency stop activated!");
}
```

`cancelNavigation` (`useROS.js:765-808`) cancels the `/mission_plan` goal, calls `/navigate_to_pose/_action/cancel_goal`, and clears local mission state. It **never publishes a zero `Twist`** and never calls any emergency-stop service. If the robot is under `docking_manager` velocity control (`docking_manager_node.py:111` publishes `/cmd_vel` directly, outside Nav2), or under joystick control, or if the cancel service call fails, the robot keeps moving. A `stopRobot()` function exists (`useROS.js:1080-1082`) and is not called from the E-STOP path.

Worse, when disconnected the button is styled as disabled — `estop-btn--offline` sets `cursor: not-allowed` (`App.vue:1153-1158`) — but has **no `:disabled` attribute**, so the click handler still runs and still shows "Emergency stop activated!". The operator receives positive confirmation of an action that did nothing, in the exact situation where they most need the truth. The same applies to the floating map E-STOP (`App.vue:215-228`, `.estop-float--offline` at `App.vue:1192-1197`).

**Confirmation coverage.** Only one destructive action has a confirmation dialog:

| Action | Confirm? | Location |
|---|---|---|
| Switch operating mode | ✅ yes | `App.vue:511-572` |
| Emergency stop | ❌ (correct — should be instant) | |
| Start mission | ❌ | `MissionPanel.vue` `startMission` |
| Send to dock | ❌ | `DockingPanel.vue` `dock()` |
| Undock | ❌ | `DockingPanel.vue` `undock()` |
| Activate map (reloads robot's map) | ❌ | `SetupPanel.vue` `activateMap` |
| Delete destination | ❌ | `MissionPanel.vue` `deleteDestination` |
| Delete dock station | ❌ | `DockingPanel.vue` `removeDock` |
| Delete keepout zone | ❌ | `SetupPanel.vue` `removeZone` |
| **Clear all keepout zones** | ❌ | `SetupPanel.vue` `clearAllZones` — deletes every safety zone on the map in one click |
| Delete saved mission | ❌ | `MissionPanel.vue` `doDeleteMission` |
| Delete map | ❌ | (cascades per §3.3) |

`clearAllZones` deleting every keepout region — the map's safety constraints — with a single unconfirmed click is the most serious of these.

**Disabled-state coverage is inconsistent.** Some controls check connection (`MappingPanel.vue` `onPointerDown`: `if (!store.rosConnected) return`; `App.vue:388` `:disabled="!store.rosConnected"` on Set Initial Pose). Others do not: `startMission`, `dock()`, `undock()`, `sendGoal` all proceed while disconnected — `useROS` functions begin with `if (!_ros) return` (e.g. `useROS.js:635`, `918`, `1002`) and return silently, so the UI shows the operation starting and nothing happens.

Nothing is gated on `isBusy`. The store computes it (`stores/robot.js:151-155`) and documents it as "tidak boleh menerima perintah navigasi baru dari web UI", but **no component uses it to disable anything** — it is only rendered as a badge. An operator can start a mission while a dock sequence is running.

**The offline overlay does not block.** `App.vue:460-464` renders a full-screen dimmer with `pointer-events-none`. Every control underneath stays clickable while disconnected.

### 5.4 State handling

| State | Handled? | Evidence |
|---|---|---|
| Loading (map list) | partial | `mapsLoading` in `App.vue`, `loading` in `SetupPanel.vue` — separate ad-hoc implementations |
| Waiting for map data | yes | `MapView.vue:380-407` overlay |
| Disconnected | partial | banner (`App.vue:466-480`) that does not block input |
| **Reconnecting** | **no** | `useROS.js:165-172` `on("close")` sets flags and clears the TF buffer. No retry, no backoff, no timer. Recovery requires a manual click on Connect |
| **Stale telemetry** | **no** | no message timestamps are ever compared to wall clock. If rosbridge stays up but Nav2 dies, the pose freezes and the UI reports ONLINE / AVAILABLE indefinitely |
| Empty data | partial | "Belum ada map tersimpan" (`App.vue:539-541`); no empty state for destinations, docks, waypoints or missions |
| Backend unavailable | partial | `SetupPanel.vue` `setMapError` with a 5 s auto-clear; `App.vue:1099-1101` logs to console only |
| ROS unavailable | partial | see disconnected |
| Permission denied | n/a | no auth exists |
| Operation in progress | partial | `dockPending`/`undockPending` in `DockingPanel.vue` use a `watch` that self-unsubscribes; `activating` in `SetupPanel.vue`; no shared pattern |
| **Partial failure (DB ok, ROS failed)** | **no** | the dual-write of §1.3 reports success on the REST half alone |

**Nothing survives a page refresh.** There is no `localStorage`, `sessionStorage` or IndexedDB use anywhere in `src/` (verified by grep; the only hit is a stale comment at `useROS.js:155` claiming keepout zones come from localStorage — they do not). Lost on reload: the current waypoint list, `activeMapId`, sidebar collapse, map minimise, selected dock, auto-dock settings, speed preset. `activeMapId` is particularly consequential — it is only ever set by `SetupPanel.activateMap`, so after a refresh it is `null` and `MissionPanel`/`DockingPanel` fetch **unscoped** destination and dock lists, mixing entities from every map.

---

## 6. Design system problems

### 6.1 Foundations exist but are bypassed

shadcn-vue is installed and configured correctly (`components.json`), with 17 primitives generated. Six of them (`select`, `sheet`, `table`, `tabs`, `tooltip`, `skeleton` — 42 files) are never imported, while **12 native `<select>` elements** are hand-styled with duplicated Tailwind strings:

```html
<!-- App.vue:542-551 and again at App.vue:648-657 -->
<select class="w-full text-xs h-8 rounded-md border border-input bg-background px-2
               focus:outline-none focus:ring-1 focus:ring-ring">
```

### 6.2 Repeated ad-hoc patterns

**Section label**, repeated 20 times across 5 files as a raw class string:

```html
<div class="text-[10px] font-semibold tracking-widest text-muted-foreground uppercase">
```

(`App.vue` ×7, `DockingPanel.vue` ×4, `MappingPanel.vue` ×4, `SetupPanel.vue` ×3, `MissionPanel.vue` ×2.) Any change to label styling requires 20 edits.

**Status → variant mapping**, duplicated:

```js
// App.vue:892-897                    // DockingPanel.vue — byte-identical
const dockVariant = computed(() => {
  const s = store.dockingStatus
  if (s === 'error')  return 'destructive'
  if (s === 'docked') return 'default'
  return 'outline'
})
```

`statusVariant` (`App.vue:885-890`) is a second, differently-shaped mapping for `navStatus`. Battery→colour logic is three more computeds (`App.vue:900-922`). There is no single status vocabulary.

**E-STOP** is 77 lines of scoped CSS in `App.vue:1121-1197`, in two variants (`.estop-btn`, `.estop-float`), each with `--active`/`--offline` states — the most safety-critical control in the product, implemented as page-local styles rather than a component.

### 6.3 Two toast systems, one of them invisible

- `composables/useToast.js` — 37 lines, hand-rolled, pushes to a module-level `toasts` ref.
- `vue-sonner` — rendered by `<Toaster>` at `App.vue:680`.

`ToastManager.vue`, the renderer for the hand-rolled system, is an **empty template**:

```html
<!-- Toast notifications are handled by vue-sonner <Toaster> in App.vue -->
<template></template>
```

But `useROS.js:18` still imports `useToast` and calls it in **nine places** — nav cancelled, nav failed, mission cancelled, mission aborted, docking error, dock command failure, service call failure, `/robot_mode` failure, `/robot_mode` timeout (`useROS.js:218-219, 246-248, 314, 866, 872, 899, 907`).

**Every error message originating from the ROS layer is pushed into an array that nothing renders.** These are exactly the messages an operator most needs: *"Navigasi gagal: Terhalang rintangan atau target tidak valid"*, *"Proses docking mengalami kegagalan (Error)"*, *"Misi waypoint gagal (Aborted)"*. They are invisible. Only component-level toasts (which import `toast` from `vue-sonner` directly) appear.

### 6.4 Theming is not a system

`main.css:16-47` defines `:root` with **dark** values for the app palette (`--background: 0 0% 3.9%`) but **light** values for the sidebar block (`--sidebar-background: 0 0% 98%`). `.dark` (`main.css:49-58`) then overrides only the sidebar tokens. `App.vue:1105` unconditionally forces `document.documentElement.classList.add("dark")` on mount.

Net effect: there is exactly one theme, achieved by a class applied in JavaScript over a `:root` whose sidebar half is written for a light theme that does not exist. Adding a light mode — genuinely useful for a robot operating in a bright warehouse — currently requires unpicking this.

A second palette lives alongside the semantic one: `tailwind.config.js` `colors.amr` = `{ ok, warning, danger, info, data }` as raw hex. So `destructive` and `amr-danger` both mean "bad", used interchangeably (`App.vue:83` uses `variant="destructive"`; `App.vue:904` uses `bg-amr-danger`).

### 6.5 Layout is hardcoded to one viewport

```html
<!-- App.vue:203-206 -->
:style="{ width: 'calc(100vw - 39rem)', height: 'calc(100vh - 6.5rem)' }"
```

The map panel's width is the viewport minus a magic constant that encodes the sidebar width plus the right panel width plus gaps. The minimised branch at `App.vue:236` uses a **different** constant (`calc(100vw - 28rem)`) for the same layout — they cannot both be right. Collapsing the sidebar (`sidebarCollapsed`, `App.vue:11`) changes the real available width but not the constant, so the map no longer fits its container.

Responsive handling is limited to `hidden sm:` / `hidden lg:` on header items (pose strip, badges, brand text). Below roughly 1200 px the fixed-width right panel and the `39rem` subtraction make the layout unusable. There is no tablet layout, which matters for an operator walking the floor next to the robot.

### 6.6 Component inventory — what should become a primitive

Justified by actual repetition found in the code:

| Proposed | Justification (occurrences) |
|---|---|
| `SectionLabel` | 20 duplicated class strings |
| `StatusBadge` | 3 duplicated status→variant mappings + inconsistent label casing |
| `ConnectionIndicator` | header dot + startup dialog + offline banner, 3 implementations |
| `ConfirmDialog` | 12 unconfirmed destructive actions (§5.3) |
| `EmergencyStop` | 77 lines of scoped CSS, 2 variants, safety-critical |
| `MetricTile` | pose cards (`App.vue:286-304`), stats rows (`App.vue:413-424`), velocity readouts |
| `EmptyState` / `LoadingState` / `ErrorState` | ~6 ad-hoc spinners and messages |
| `FormField` | label+input+step triples repeated in init-pose, dock name, mission name, speed settings |
| `Select` | adopt the existing unused `ui/select`; replaces 12 native elements |
| `RobotBadge` | **new** — does not exist; required before multi-robot (§5.2) |

Not recommended: a generic `DataTable` (no tabular data today), a `Sidebar` abstraction beyond the existing `AppSidebar.vue` (69 lines, adequate), or wrapping every shadcn primitive.

---

## 7. Performance assessment

The constraint stated for this project — the UI may run on a machine that is also carrying robot workloads — makes the following non-theoretical.

### 7.1 Bundle

```
web-ui/dist/assets/index-BsOgeKsJ.js   1.1 MB   (single chunk, no code splitting)
web-ui/dist/assets/index-C7zlhFlw.css   69 KB
```

No manual chunks are configured (`vite.config.js:1-19`), so Vue, Pinia, Leaflet, ECharts, roslib and all application code load as one file before first paint. Removing dead dependencies alone is a large win:

| Dependency | Imports in `src/` | Action |
|---|---:|---|
| `three` | 0 | remove |
| `ros3d` | 0 | remove (pulls `three`) |
| `radix-vue` | 0 | remove (superseded by `reka-ui`) |
| `vue-router` | 0 | **keep and start using** (§9) |
| `echarts` + `vue-echarts` | 8 | replace — see below |

`three` + `ros3d` + `radix-vue` are pure dead weight in `node_modules` and in the dev-server dependency graph.

ECharts is used for exactly two charts, one of which (`BatteryChart.vue`) is dead. `echarts@6` full import is on the order of 1 MB before gzip. For two real-time line charts, **uPlot** (~45 KB) is the appropriate tool and is measurably faster for streaming data.

### 7.2 Runtime — occupancy grid and costmap rendering

Both grids are rendered by writing every cell into an `ImageData` and then calling `canvas.toDataURL()`:

```js
// MapView.vue:804-838 (map) and 876-922 (costmap)
for (let i = 0; i < data.length; i++) { … imgData.data[idx] = r; … }
ctx.putImageData(imgData, 0, 0);
const url = canvas.toDataURL();        // full PNG encode + base64
occupancyLayer.setUrl(url).setBounds(bounds);
```

`toDataURL()` synchronously PNG-encodes the entire grid and base64-encodes the result on the main thread. For `/map` this happens once (latched topic), which is acceptable. For `/global_costmap/costmap` it happens **every 500 ms** (`useROS.js:541` `throttleRate: 500`), forever, for as long as the app is open. On a 2000×2000 costmap that is a multi-megabyte PNG encode twice per second, on the same machine as the robot stack.

The fix is a `canvas` element used directly as a Leaflet layer (or `L.ImageOverlay` fed from an `OffscreenCanvas` / `createImageBitmap`), eliminating the encode entirely.

### 7.3 Runtime — sensor overlays

- **Laser scan** (`MapView.vue` `renderLaserScan`) correctly pools `L.circleMarker` objects and only splices the excess. Good. But `/scan` is subscribed with **no throttle** (`useROS.js:439-446`), so the full scan is deserialised and re-projected at the sensor's native rate (typically 10–40 Hz). At ~360 points per scan that is up to ~14k `setLatLng` calls per second.
- **Particle cloud** (`MapView.vue` `renderParticleCloud`) does the opposite of pooling:
  ```js
  particleMarkers.forEach((m) => m.remove());
  particleMarkers = [];
  for (const { x, y } of poses) particleMarkers.push(L.circleMarker(…).addTo(leafletMap));
  ```
  Every message destroys and recreates every marker. AMCL defaults to 500–2000 particles, unthrottled (`useROS.js:448-463`). This is thousands of object allocations and Leaflet layer add/removes per second, producing continuous GC pressure.
- **Pose** arrives at ~30 Hz (`/tf` `throttle_rate: 33`, `useROS.js:353`) into a `watch(…, { deep: true })` (`MapView.vue:666-696`) that performs a string `replace()` on `el.style.transform` and rewrites it on every frame.

### 7.4 Reactivity

`stores/robot.js` stores raw ROS messages in plain `ref()`s: `mapData` (`:38`), `costmapData` (`:119`), `laserScan` (`:123`), `particleCloud` (`:126`). Vue deep-wraps these in reactive proxies. A `LaserScan` contains a `ranges` array of several hundred floats; an `OccupancyGrid` contains a `data` array of **millions** of entries. Every one gets proxied.

These should be `shallowRef` — the components only ever read them wholesale and re-render imperatively. `MapView.vue` already uses `shallowRef` for its own marker arrays (`:547-550`), so the pattern is understood; it just was not applied in the store.

### 7.5 Polling and timers

| Timer | Interval | Location |
|---|---|---|
| `/api/stats` poll | 5 s | `useSystemStats.js:32` — never stopped on disconnect, runs while backend is down (silently caught) |
| Joystick publish | 80 ms | `MappingPanel.vue` `_publishInterval` |
| D-pad publish | 80 ms | `MappingPanel.vue` `_dirInterval` |
| Mission watchdog | 120 s | `useROS.js:728-734` |

The mission watchdog is a correctness concern more than a performance one: on timeout it calls `_advanceMission()` and sends the **next** goal while the robot may still be executing the current one (`useROS.js:729-734`).

### 7.6 Measured baseline

`NOT VERIFIED` — no profiling was run as part of this audit. The bundle figure is from the checked-in `dist/` (built 2026-09-20). Establishing a real baseline (bundle analysis, a 10-minute heap trace, and a CPU profile during active navigation with costmap enabled) is Phase 0 work.

---

## 8. Technology comparison

### 8.1 Option A — keep Vue 3 + Vite

| | |
|---|---|
| **Migration cost** | zero |
| **Bundle** | Vue runtime ~34 KB gzip; already the smallest of the three |
| **Dev server** | Vite, ~200 MB RSS, sub-second HMR |
| **Production runtime** | static files; can be served by the existing FastAPI `StaticFiles` mount — **no extra process on the robot machine** |
| **Risk** | none |
| **Weaknesses** | no types today; team familiarity unknown |

### 8.2 Option B — React + Vite + TypeScript

| | |
|---|---|
| **Migration cost** | **full rewrite of 9,611 lines.** Leaflet integration (1,594 lines), the ROS layer (1,245 lines) and the store (440 lines) all rewritten |
| **Bundle** | React + ReactDOM ~45 KB gzip, slightly larger than Vue |
| **Dev server** | Vite, comparable |
| **Production runtime** | static files, same as A |
| **Operator benefit** | **none.** No user-visible capability is gained |
| **Real gain** | larger ecosystem; shadcn/ui upstream is React-first, so primitives land there first |

The honest framing: the hard, valuable parts of this codebase are the Leaflet rendering pipeline, the TF composition logic (`useROS.js:44-92`), the latched-topic QoS workaround (`useROS.js:323-344`), and the URDF footprint parser (`useROS.js:498-534`). None of that is framework code. A React rewrite discards ~9.6k lines of working, debugged integration to land in the same place.

### 8.3 Option C — Next.js

| | |
|---|---|
| **Migration cost** | full rewrite, plus an App Router / RSC architecture to learn |
| **Bundle** | largest of the three; framework runtime plus hydration payload |
| **Dev server** | heaviest; Next dev typically 400 MB–1 GB+ RSS |
| **Production runtime** | **requires a long-lived Node process** unless fully statically exported. On a machine also running ROS 2, Gazebo and Nav2, that is a permanent resident process for no benefit |
| **What Next.js provides** | SSR/SSG, SEO, file-system routing, image optimisation, API routes, middleware |

Measured against this application:

- **SSR/SEO** — the app is an authenticated-by-network-isolation internal operator console. It is never crawled. Every meaningful pixel depends on a live WebSocket, so server rendering produces an empty shell that must hydrate anyway. **No value.**
- **API routes** — FastAPI already owns the API. Adding a second backend runtime would split the contract across two languages. **Negative value.**
- **File-system routing** — `vue-router` is already a dependency and provides this. **No value.**
- **Image optimisation** — the only images are dynamically generated map canvases. **No value.**
- **Cost** — a Node process resident on a robot-adjacent machine, plus a rewrite.

**Next.js is the wrong tool for this application.** Not because it is popular or unpopular, but because every feature it adds over a Vite SPA targets a problem this product does not have, while its one concrete cost — a persistent server runtime — lands directly on the constraint this project has explicitly stated.

### 8.4 Summary

| Criterion | A: Vue+Vite | B: React+Vite | C: Next.js |
|---|---|---|---|
| Migration cost | none | ~9.6k lines | ~9.6k lines + new paradigm |
| Bundle (framework) | ~34 KB gz | ~45 KB gz | largest |
| Dev server RSS | ~200 MB | ~200 MB | 400 MB–1 GB+ |
| Production process on robot host | none (static) | none (static) | **Node process** |
| Operator-visible benefit | — | none | none |
| SEO value | n/a | n/a | wasted |
| **Verdict** | ✅ **keep** | ❌ | ❌ |

### 8.5 Supporting choices

| Concern | Recommendation | Reason |
|---|---|---|
| Types | **Add TypeScript incrementally** | The single largest bug class in this audit is silently dropped/renamed fields across the browser↔REST↔ROS boundary (`station_id`, `dest_point`, `approach`, `yaw` — §3.4). Typed ROS message and API interfaces catch all four at compile time. `vite` needs no config change; rename files as they are touched |
| Routing | **Adopt `vue-router`** (already installed) | Deep links, browser back, refresh-safe screen state, and the natural carrier for `/robots/:robotId/...` in §10 |
| State | **Keep Pinia**, split by domain | Already a dependency, already idiomatic. Needs `shallowRef` for message payloads (§7.4) and a per-robot store factory (§12) |
| Server state | **TanStack Query (Vue) — optional, Phase 5+** | Would remove ~10 hand-rolled `loading`/`error`/`refresh` triples. Not urgent; defer until the routing and context work lands |
| UI primitives | **Keep shadcn-vue / reka-ui**, delete `radix-vue` | Already installed and correctly configured; the gap is adoption, not capability |
| Icons | **Keep `lucide-vue-next`**, consider dropping `@radix-icons/vue` | Two icon sets for one product; consolidation is cheap |
| Charts | **Replace ECharts with uPlot** | ~1 MB → ~45 KB for two streaming line charts |
| Real-time | **Keep roslibjs against rosbridge** | Works, and the QoS/TF/action workarounds in `useROS.js` represent real debugging investment. Wrap it behind a typed client rather than replacing it |
| Map | **Keep Leaflet** | `CRS.Simple` at 100 px/m is a sound choice; the problems are in rendering technique (§7.2), not the library |

**Recommendation: stay on Vue 3 + Vite. Add TypeScript, vue-router, and the design-system discipline. Do not migrate frameworks.**

---

## 9. Recommended frontend architecture

```
web-ui/src/
├── main.ts
├── App.vue                       ← shell only: <RouterView>, global providers. Target < 100 lines
│
├── app/
│   ├── router.ts                 ← route table, guards
│   ├── providers.ts              ← pinia, toaster, error boundary
│   └── layouts/
│       ├── FleetLayout.vue       ← fleet-level chrome
│       └── RobotLayout.vue       ← RobotContextBar + workspace nav  ★ the safety-critical shell
│
├── domain/                       ← framework-free; pure logic, fully unit-testable
│   ├── ros/
│   │   ├── client.ts             ← typed rosbridge wrapper (replaces the useROS singleton)
│   │   ├── connection.ts         ← reconnect with backoff, heartbeat, staleness
│   │   ├── tf.ts                 ← TF buffer + composition   (from useROS.js:44-92)
│   │   ├── urdf.ts               ← footprint parser          (from useROS.js:498-534)
│   │   └── topics.ts             ← topic/service names + message types in ONE place
│   ├── mission/runner.ts         ← mission state machine     (from useROS.js:673-761)
│   └── types/                    ← RobotStatus, MissionPlan, StationConfig, API DTOs
│
├── features/                     ← one folder per workspace; owns its components + store
│   ├── fleet/ · overview/ · operate/ · mission/ · navigation/
│   ├── mapping/ · docking/ · diagnostics/ · system/
│
├── shared/
│   ├── ui/                       ← shadcn primitives (unused ones deleted)
│   ├── components/               ← SectionLabel, StatusBadge, ConfirmDialog,
│   │                               EmergencyStop, MetricTile, EmptyState, RobotBadge
│   ├── map/                      ← MapCanvas + layer modules, split from MapView.vue
│   │   ├── MapCanvas.vue · layers/{occupancy,costmap,laser,particles,robot,path}.ts
│   │   └── interactions/{navigate,waypoint,keepout,initialPose,destination,dock}.ts
│   └── api/                      ← typed client, base URL from env
│
└── stores/
    ├── fleet.ts                  ← robot registry, selected robot
    ├── robot.ts                  ← factory: useRobotStore(robotId)
    └── ui.ts                     ← persisted preferences
```

**Principles**

1. **`App.vue` becomes a shell.** Today it is 1,210 lines holding the header, the Overview page, three dialogs, battery logic and mode sync. Overview becomes a route; dialogs become feature components.
2. **ROS logic leaves the composable.** `useROS.js` mixes connection management, 14 subscriptions, 11 commands and a mission state machine in module-level `let` variables. Moving the pure parts (TF, URDF, mission sequencing) into `domain/` makes them unit-testable without a browser and removes the singleton that blocks multi-robot.
3. **One source of truth for topic names.** `domain/ros/topics.ts` is where namespacing gets introduced in §12 — a single edit rather than a grep through 1,245 lines.
4. **`MapView.vue` splits into layers and interactions.** Each layer owns its render strategy (and its performance fix from §7.2); each interaction mode owns its drag/click handling. 1,594 lines becomes ~12 files of 100–200.
5. **Features own their state.** `stores/robot.js` currently holds destinations, docks, keepout zones, waypoints, costmap toggles and battery thresholds in one object. These belong to their features.
6. **Route = screen = URL.** Deep linking, browser back, and refresh-safe navigation follow for free.

---

## 10. Proposed information architecture

Derived from the capabilities that actually exist in this repository, not from a generic template.

```
/                                   → redirect to /fleet (or to the single robot if only one)

/fleet                              FLEET CONTEXT
  ├── Robots            robot cards: name, state, battery, map, current task, connection
  ├── Maps              map library, upload, activate, per-map metadata      [from SetupPanel]
  └── Stations          destinations + dock stations, per map, map-centric   [from MissionPanel/DockingPanel]

/robots/:robotId                    ROBOT CONTEXT — RobotContextBar always visible
  ├── overview          identity, connection, pose, mode, battery, faults, current task
  ├── operate           manual drive: joystick, D-pad, speed presets, E-STOP   [from MappingPanel]
  ├── mission           waypoint list, execute, pause/stop, confirm, save/load [from MissionPanel]
  ├── navigation        goal pose, initial pose, localisation quality, plan    [from App Overview + NavigationPanel]
  ├── mapping           SLAM session, live map, save map                       [from MappingPanel]
  ├── docking           dock selection, dock/undock, auto-dock policy          [from DockingPanel]
  └── diagnostics       topic health, message rates, TF tree, faults, logs     ★ new

/system                             SYSTEM CONTEXT
  ├── robots            register/edit robots: name, bridge URL, camera URL, colour  ★ new
  ├── network           bridge endpoints, backend URL, connectivity tests
  ├── integrations      ROS interface contract, station sync status                 ★ new
  └── preferences       theme, units, telemetry rates, confirmation strictness
```

### What moved and why

| Current | Proposed | Reason |
|---|---|---|
| Header mode toggle (global) | `RobotContextBar` → mode control, per robot | Mode is robot state, not app state (§5.1). Must show *actual* robot mode, not UI belief (§3.2) |
| `Overview` tab (6 concerns) | split: `overview` / `navigation` / `system` | Connection + pose + init-pose + velocity chart + host stats are four altitudes in one scroll |
| `Setup` tab | `/fleet/maps` + `/fleet/stations` | Map library and keepout zones are fleet/map-level, not robot-level |
| Joystick inside `Mapping` | `/robots/:id/operate` | Manual drive is needed during navigation too; today it is unreachable outside mapping mode |
| Destinations inside `Mission` | `/fleet/stations` | Stations are reusable map data; missions *reference* them |
| Mode hides whole tabs | Mode disables *actions*, tabs stay visible | Operators need to see docks and stations during mapping |
| (nothing) | `/robots/:id/diagnostics` | The single biggest observability gap — see §5.4 stale telemetry |
| (nothing) | `/system/robots` | Prerequisite for multi-robot |

### The robot context bar

The most important new surface. Always visible within `/robots/:robotId`, never scrolls away:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ▌[AMR-01]  ● ONLINE   NAV MODE   AVAILABLE   🔋 87%   📍 LOCALISED   [E-STOP] │
└──────────────────────────────────────────────────────────────────────────────┘
  ▲       ▲       ▲          ▲          ▲         ▲         ▲            ▲
  │       │       │          │          │         │         │            └ always enabled when connected,
  │       │       │          │          │         │         │              truly disabled (and labelled so) when not
  │       │       │          │          │         │         └ from particle cloud spread — new
  │       │       │          │          │         └ existing
  │       │       │          │          └ from isBusy (stores/robot.js:151)
  │       │       │          └ from the ROBOT, not from appMode
  │       │       └ existing connection state + staleness
  │       └ robot name — does not exist today
  └ per-robot accent colour — the primary "am I driving the right robot" cue
```

Rules: the accent stripe and name are the strongest visual elements on the page. Switching robots requires an explicit action, never a side effect of navigation. Any command sent while `BUSY` or disconnected is blocked at the UI layer with a stated reason, not silently dropped by `if (!_ros) return`.

---

## 11. Proposed design system

### 11.1 Status system

One vocabulary, one mapping, used everywhere. This replaces the three duplicated `statusVariant`/`dockVariant` computeds (§6.2).

| Semantic | Meaning | Token | Use |
|---|---|---|---|
| `neutral` | idle, no activity | `--status-neutral` | AVAILABLE, IDLE |
| `active` | autonomous operation in progress | `--status-active` | NAVIGATING, EXECUTING, DOCKING |
| `attention` | operator input required | `--status-attention` | WAITING PAYLOAD, manual confirm |
| `warning` | degraded, still operating | `--status-warning` | low battery, stale telemetry, poor localisation |
| `fault` | stopped, intervention required | `--status-fault` | ERROR, aborted, disconnected |
| `success` | terminal success | `--status-success` | mission complete, docked, map saved |

Every status is rendered by one `StatusBadge` with a shape + icon in addition to colour (colour alone fails for colour-blind operators and in direct sunlight).

### 11.2 Colour

- Keep shadcn semantic tokens (`background`, `foreground`, `muted`, `border`, `destructive`) — they are correct and already wired.
- **Retire the parallel `amr.*` palette** (§6.4); map `amr-ok/warning/danger/info` onto the status tokens above.
- Fix the `:root` / `.dark` split so light and dark are both real (§6.4), then remove the forced `classList.add("dark")` at `App.vue:1105`.
- Per-robot accent colours: a fixed palette of 8, assigned at registration, used only for robot identity (stripe, badge, map marker outline) and never for status. This is the mechanism that prevents operating the wrong robot.
- Reserve saturated red exclusively for E-STOP and `fault`. Today `destructive` is also used for the Disconnect button (`App.vue:267`) and the "Cancel add mode" toggle (`MissionPanel.vue`), diluting the signal.

### 11.3 Typography

| Role | Family | Size | Use |
|---|---|---|---|
| Display | Inter 600 | 18–20 px | page titles |
| Body | Inter 400/500 | 13–14 px | labels, prose |
| Section label | Inter 600, `0.08em` tracking, uppercase | 10 px | the `SectionLabel` component |
| **Data** | JetBrains Mono, `tabular-nums` | 12–16 px | **all numeric telemetry** |

`font-data` and `tabular-nums` are already used correctly for pose (`App.vue:65`, `:297`) — this generalises that to every number. Non-tabular numerals on live telemetry cause visible digit jitter at 30 Hz.

Current sizing goes as low as `text-[9px]` (`App.vue:293`, `:300`). **Set a 10 px floor.** Operators read this on a factory floor, sometimes standing.

### 11.4 Spacing & density

4 px base scale, three density tiers:

- **Compact** (`gap-1`/`p-2`) — telemetry lists, data tables
- **Default** (`gap-2`/`p-3`) — panels, forms
- **Comfortable** (`gap-4`/`p-4`) — dialogs, empty states

Density serves information, not decoration. Per the stated direction: no gradients, no glassmorphism, no decorative shadows. Note `App.vue:245` currently uses `bg-background/92 backdrop-blur-md shadow-2xl` on the main panel — `backdrop-blur` in particular is a continuous GPU cost on a machine sharing work with the robot stack, for a purely decorative effect over an opaque background.

### 11.5 Layout patterns

Replace the hardcoded `calc(100vw - 39rem)` (§6.5) with CSS Grid:

```
┌────────────────────────────────────────────────────────────┐
│  AppBar                                          (56px)    │
├──────────────────────────────────────────────────────────  │
│  RobotContextBar                                 (44px)    │  ← only in robot context
├─────────┬──────────────────────────────┬───────────────────┤
│ Nav     │  Primary (map / workspace)   │  Inspector        │
│ 56/220  │  1fr                         │  320–380px        │
│         │                              │  collapsible      │
└─────────┴──────────────────────────────┴───────────────────┘
```

`grid-template-columns: auto 1fr auto` — the map gets whatever is left, correctly, at every viewport and with the sidebar in either state.

Breakpoints: **≥1440** three columns · **1024–1440** inspector becomes an overlay sheet (`ui/sheet` already exists, unused) · **768–1024** map full-width, workspace in a bottom sheet, context bar pinned · **<768** read-only status view; manual driving controls are hidden, not shrunk.

### 11.6 Motion

Permitted only where it carries information:

| Purpose | Treatment |
|---|---|
| Connection state change | 150 ms colour transition on the indicator |
| Operation in progress | indeterminate progress on the specific control |
| Robot movement | position interpolation on the map marker only |
| Route transition | 120 ms fade; no slide, no parallax |
| Fault onset | one 400 ms attention pulse, then static |

Everything else is static. Honour `prefers-reduced-motion`. Remove the continuous `animate-glow-ok` on the connection dot (`App.vue:139`) — a permanently pulsing element for a steady state is noise, and it repaints forever.

---

## 12. Multi-robot migration strategy

The goal is to reach fleet support **without rewriting the application**. The sequencing below keeps single-robot operation working at every step; each phase ships independently.

### Stage 1 — Make "one robot" explicit (no behaviour change)

The current code has an *implicit* single robot. Make it an *explicit* robot with an id, still hardcoded to one.

1. Backend: add a `robots` table (`id`, `name`, `bridge_url`, `camera_url`, `colour`, `serial`, `created_at`). Seed one row, `id = 1`, from the current `VITE_ROS_URL`.
2. Backend: add nullable `robot_id` to `missions` (mission↔robot is the only genuinely robot-scoped relation today; maps, docks, destinations and keepout zones are **map**-scoped and should stay fleet-shared).
3. Backend: move mode out of the global `settings` table (`database.py:79-80`) into a per-robot column.
4. Frontend: `stores/fleet.ts` with a registry; `selectedRobotId` defaults to the single seeded robot.
5. Frontend: `useRobotStore(robotId)` as a factory, initially only ever called with `1`.
6. Frontend: `domain/ros/topics.ts` centralises every topic name and takes an optional namespace that resolves to `''` today.

**Everything still behaves identically.** The ids exist and are unused.

### Stage 2 — Route on robot id

7. Adopt `vue-router`; routes become `/robots/:robotId/...`.
8. Ship `RobotContextBar` with name and accent colour, sourced from the registry.
9. `/system/robots` becomes the place robots are registered — replacing the build-time `VITE_ROS_URL`.

Still one robot, but every screen is now addressed by robot id and the operator sees which robot they hold.

### Stage 3 — Connection multiplexing

10. Replace the `useROS` singleton (`useROS.js:21-33`) with `RosConnectionPool` keyed by robot id: N connections, each with its own TF buffer, mission runner and subscription set.
11. Add reconnect with exponential backoff and a per-topic staleness detector — the gap identified in §5.4. This is worth doing for one robot regardless.
12. Cap concurrent live subscriptions: the **selected** robot subscribes to everything; background robots subscribe only to `/robot_status` and `/battery_state`. This is what keeps N robots affordable on shared hardware.

### Stage 4 — ROS namespacing

13. Decide the topology and record the decision in `docs/ROS_INTEGRATION.md`:
    - **(a) One rosbridge per robot, unnamespaced topics.** Simplest. Bridge URL per robot is already in the registry. Each robot keeps its own DDS domain. **Recommended** — it changes no ROS code.
    - **(b) One bridge, namespaced topics** (`/amr_01/cmd_vel`). Requires launch changes and a TF frame prefix strategy (`map` → `amr_01/map`), which touches `useROS.js:79-85` and Nav2 configuration.
14. Whichever is chosen, `domain/ros/topics.ts` is the only frontend file that changes.

### Stage 5 — Fleet surfaces

15. `/fleet/robots` overview with per-robot cards.
16. Cross-robot safety: fleet-wide E-STOP; explicit robot switching; per-robot confirmation copy that names the robot (*"Send **AMR-02** to Dock 1?"*).
17. Mission queueing and robot assignment.

### Prerequisites to fix first

These block or corrupt the migration and should land before Stage 3:

| Must fix | Why it blocks |
|---|---|
| `/api/mode/switch` reporting false success (§3.2) | Per-robot mode is meaningless if mode never applied in the first place |
| Duplicate `/station_config` + `/dock_command` servers (§3.6) | Non-deterministic service resolution becomes far harder to debug with N robots |
| Station identity by name (§1.4) | Name collisions across robots/maps are inevitable in a fleet |
| Missions dropping `station_id` (§3.4) | Mission portability across robots depends on stable station references |
| Map-delete cascade (§3.3) | One engineer's file rename destroying fleet-wide station data is unacceptable at any scale |

### Explicitly out of scope for now

Do **not** build yet: cross-robot traffic management, fleet-wide path deconfliction, multi-robot task allocation, or a central fleet scheduler. Those are a different product tier and none of the required foundations exist.

---

## 13. Documentation cleanup plan

### 13.1 State before cleanup

*This section records the situation as found on 2026-09-25, before the reorganisation was executed.*

- **23 Markdown files** in the project (excluding `node_modules`, `.venv`).
- **16 `PHASE_*.md` reports at the repository root**, 10 KB–26 KB each, ~270 KB total.
- `docs/` contains a mix of active reference, Indonesian working notes, `.txt` files, and `docs/README.md` — which is actually **the `custom_interfaces` package README**, not a docs index.
- `docs/evidence/` is **86 MB across 715 tracked files** (345 `.txt`, 167 `.log`, 156 `.json`), tracked in git.
- **No CI**, so nothing but `scripts/docker_run.sh:28` references a doc path.

### 13.2 Reference check (verified before proposing any move)

```
scripts/docker_run.sh:28  →  docs/runbooks/AMR_SIMULATION_COMMANDS.md
```

That is the **only** cross-reference from code, scripts or tooling to any documentation file. `README.md` contains no Markdown links. There is no `.github/`. Everything else can be moved safely, provided that one path is preserved or the script is updated in the same commit.

### 13.3 Structure — as executed (2026-09-25)

Files were relocated with `git mv` so history follows them. **No document content was rewritten**; consolidation and splitting are deferred (see "remaining work" below).

```
README.md                                        ← only .md left at root
docs/
├── README.md                                    ← NEW index + "where documentation belongs" table
├── ROS_INTERFACE_CONTRACT.md                    ← current reference
├── WEB_UI_BACKEND_END_TO_END_ARCHITECTURE.md    ← moved from root
├── WEB_UI_REDESIGN_AUDIT.md                     ← this file
├── JAZZY_DEPENDENCY_STATUS.md                   ← current reference
├── SHARED_MAP_STORAGE_NFS.md                    ← moved from root
├── runbooks/
│   └── AMR_SIMULATION_COMMANDS.md               ← UNCHANGED PATH (scripts/docker_run.sh:28)
├── decisions/
│   └── README.md                                ← NEW: ADR format + the 3 pending records
├── evidence/
│   ├── phase4k/  … phase5b/                     ← + the 4 phase4k-*.json from root
│   └── (unchanged otherwise)
└── history/
    ├── README.md                                ← NEW: what this is, why kept, per-file status
    ├── ROS2_JAZZY_MIGRATION_RESEARCH_AND_PLAN.md
    ├── phases/          16 files                ← PHASE_*.md from root
    ├── plans/           14 files                ← from docs/superpowers/plans/
    ├── designs/          1 file                 ← from docs/superpowers/designs/
    ├── investigations/   3 files
    └── notes/            8 files                ← pending review, not deleted

ros2_ws/src/custom_interfaces/README.md          ← was docs/README.md (misplaced package doc)
```

Also done: deleted `figma-linux_197.snap.partial` (96 MB, untracked, already gitignored). `docs/superpowers/` removed after its contents moved.

**Target filenames not yet created** — these require writing or splitting content, not moving files, and belong to later phases: `ARCHITECTURE.md`, `FRONTEND.md`, `BACKEND.md`, `API.md`, `ROS_INTEGRATION.md`, `UX_ARCHITECTURE.md`, `DESIGN_SYSTEM.md`, `DEVELOPMENT.md`, `TESTING.md`, `DEPLOYMENT.md`. The source material for each is identified in §13.4.

### 13.4 Classification

**Active reference — keep, update in place**

| File | Destination |
|---|---|
| `README.md` (root) | stays; fix stale "ROS2 Humble" claim — the stack is **Jazzy** (`docker-compose.yml:2`, `bringup.launch.py`) |
| `docs/ROS_INTERFACE_CONTRACT.md` | → `docs/ROS_INTEGRATION.md` (merge target; 16 KB, current) |
| `docs/runbooks/AMR_SIMULATION_COMMANDS.md` | **unchanged path** |
| `docs/JAZZY_DEPENDENCY_STATUS.md` | → `docs/DEPLOYMENT.md` (merge) |
| `SHARED_MAP_STORAGE_NFS.md` | → `docs/DEPLOYMENT.md` (merge) |

**Architecture — becomes the base of the new docs**

| File | Destination |
|---|---|
| `WEB_UI_BACKEND_END_TO_END_ARCHITECTURE.md` (45 KB) | split → `docs/ARCHITECTURE.md` + `docs/FRONTEND.md` + `docs/BACKEND.md` + `docs/API.md` |
| `WEB_UI_STARTUP_PLAYWRIGHT_UX_AUDIT.md` (30 KB) | → `docs/history/investigations/`; findings folded into `docs/UX_ARCHITECTURE.md` |
| **this file** | → `docs/history/investigations/`; conclusions distributed into `UX_ARCHITECTURE.md`, `DESIGN_SYSTEM.md`, `decisions/` |

**Historical evidence — preserve, relocate**

| Files | Destination | Rationale |
|---|---|---|
| 15 × `PHASE_*.md` (root) | `docs/history/phases/` | Real engineering value: Phase 4G–4P document the diff-drive slip investigation and the calibration that produced current physics parameters. **Do not delete.** They just should not be the first 15 things in the repository root |
| `ROS2_JAZZY_MIGRATION_RESEARCH_AND_PLAN.md` (69 KB) | `docs/history/` | Migration is complete; the research remains valuable |
| `VELOCITY_POSE_DRIFT_ROOT_CAUSE_INVESTIGATION.md` | `docs/history/investigations/` | |
| `docs/ODOMETRY_IMU_EKF_MAPPING_DIAGNOSTIC.md` | `docs/history/investigations/` | |
| `docs/superpowers/plans/*` (13 files) | `docs/history/plans/` | Plans for completed phases |
| `docs/superpowers/designs/*` | `docs/history/designs/` | |

**Working notes — review, then consolidate**

| File | Action |
|---|---|
| `docs/docking_changes.md` | Extract anything still true into `docs/ROS_INTEGRATION.md`, then archive |
| `docs/real_robot_docking_fix.md` | Same |
| `docs/robot_status_analysis.md` | Same — relevant to the §3.6 duplicate-service conflict |
| `docs/keepout_integration.txt` | Convert to Markdown, fold into `docs/ROS_INTEGRATION.md`, archive |
| `docs/keepout_koordinasi_tim_robot.txt` | Team coordination note — archive |
| `docs/PROGRESS_WEBUI.txt` | Superseded by this audit — archive |
| `docs/LAPORAN_PROGRESS.md` | Superseded — archive |

**Obsolete — delete after review**

| File | Reason |
|---|---|
| `docs/perubahan.md` | 126 bytes; verify then delete. **Moved to `history/notes/` pending that review** |
| `docs/README.md` | Misplaced — it is the `custom_interfaces` package README. ✅ **moved** to `ros2_ws/src/custom_interfaces/README.md`; a real docs index now occupies `docs/README.md` |
| `phase4k-*.json` (4 files, root) | Generated runtime captures. ✅ **moved** to `docs/evidence/phase4k/` |
| `figma-linux_197.snap.partial` | 96 MB, untracked, already gitignored (`.gitignore:31`). ✅ **deleted** |

**`docs/evidence/` — 86 MB, needs a policy decision**

Raw `.log`/`.json`/`.txt` captures from the Phase 4/5 investigations. Options, in order of preference:

1. **Keep the analysis, archive the raw data.** Each phase folder keeps a short `README.md` with the conclusions and the commands to regenerate; raw captures move to external storage or a release artefact. Repository drops to a few MB.
2. **Git LFS** for `docs/evidence/**`. Keeps everything in-repo, keeps clones fast.
3. **Keep as-is.** Every clone pays 86 MB forever.

This is a call for the repository owner. Given the previous commit `7514b55 chore: remove large generated files from repository`, the intent to shrink the repo already exists; this is the remaining 86 MB.

### 13.5 Execution rules

1. Use `git mv` throughout so history follows the files.
2. Update `scripts/docker_run.sh:28` **in the same commit** as any runbook move (or keep that path fixed).
3. One commit per group (`docs: archive phase reports`, `docs: consolidate ROS integration docs`) so any move is individually revertable.
4. `docs/history/README.md` explains what the archive is and why it was kept — otherwise the next person deletes it.
5. Nothing is deleted until it has been read. Several "notes" files contain the only written record of why a ROS interface is shaped the way it is.

---

## 14. Implementation roadmap

Sequenced so that **safety and correctness land before appearance**, and so every phase is independently shippable.

### Phase 0 — Baseline & safety net

*No user-visible change. Makes everything after it verifiable.*

- Capture a performance baseline: bundle analysis, 10-minute heap trace, CPU profile during navigation with the costmap enabled (§7.6).
- Record the current REST contract (OpenAPI is already generated by FastAPI — snapshot it) and the ROS interface contract as fixtures.
- Add Vitest; test the pure logic first — TF composition (`useROS.js:44-92`), URDF parsing (`useROS.js:498-534`), quaternion helpers (`useROS.js:1210-1221`), mission sequencing (`useROS.js:673-761`).
- Add pytest for the backend routers, including a **regression test for the map-delete cascade** (§3.3).
- Set up lint + typecheck in CI (there is no `.github/` today).

**Exit:** a test suite that fails if any §15 defect is reintroduced.

### Phase 1 — Safety-critical fixes

*Highest value per line changed. Independent of any redesign.*

- **E-STOP actually stops** — publish zero `Twist` and hold it, in addition to cancelling goals; disable properly when disconnected instead of faking it (§5.3).
- **Render ROS-layer toasts** — point `useROS.js` at `vue-sonner` and delete the orphaned `useToast`/`ToastManager` (§6.3). Nine error paths become visible.
- **Stop `/api/mode/switch` from reporting false success** — either implement the `/robot_mode` server or surface the "run this command" instruction as a manual step, clearly labelled (§3.2).
- **Guard the cascade** — require explicit confirmation before a map delete removes child data; stop `GET /api/maps` from deleting rows as a read side effect (§3.3).
- **`ConfirmDialog` on the 12 unconfirmed destructive actions**, starting with `clearAllZones` (§5.3).
- **Gate commands on `isBusy` and connection** — replace silent `if (!_ros) return` with a stated refusal (§5.3).
- **Reconnect with backoff + staleness detection** (§5.4).

**Exit:** no control reports success for an action that did not happen.

### Phase 2 — Contract repair

- Add `station_id` and `dest_point` to `WaypointItem` (§3.4); migrate existing missions.
- Add `approach` to `DockIn`/`DockOut`; populate the existing columns (§3.4).
- Make destination `PUT` partial, or require full objects — stop resetting `yaw` (§3.4).
- Resolve the duplicate `/station_config` and `/dock_command` servers: pick one owner (`mission_manager` is the better candidate — it already holds the station registry) and remove the other (§3.6).
- Move station identity to a stable id, with the display name as a separate mutable field (§1.4).
- Make the backend base URL configurable via env, matching `VITE_ROS_URL` (§4, item 11).

**Exit:** no data is silently lost across the browser↔REST↔ROS boundary.

### Phase 3 — Documentation cleanup ✅ done (2026-09-25)

File reorganisation per §13.3 is complete: root holds only `README.md`, everything else is filed under `docs/` with an index, `docs/history/` for completed work, and `docs/decisions/` ready for ADRs. `git mv` was used throughout, so history follows the files.

**Remaining, deferred:** writing the consolidated `ARCHITECTURE.md` / `FRONTEND.md` / `BACKEND.md` / `API.md` / `ROS_INTEGRATION.md` / `UX_ARCHITECTURE.md` / `DESIGN_SYSTEM.md` / `DEVELOPMENT.md` / `TESTING.md` / `DEPLOYMENT.md` (content work — source material mapped in §13.4), reviewing the 8 files in `docs/history/notes/`, and deciding the `docs/evidence/` 86 MB policy.

### Phase 4 — Design system foundation

- Delete dead code: 8 components (~1,268 lines) and 6 unused shadcn primitive sets (42 files) (§2.2).
- Remove dead dependencies: `three`, `ros3d`, `radix-vue` (§7.1).
- Build the shared components of §6.6: `SectionLabel`, `StatusBadge`, `ConfirmDialog`, `EmergencyStop`, `MetricTile`, `EmptyState`/`LoadingState`/`ErrorState`, `FormField`.
- Establish the token system: status vocabulary, real light/dark, retire the parallel `amr.*` palette (§11.1–11.2).
- Replace the 12 native `<select>` elements with the existing `ui/select`.

**Exit:** one status vocabulary, one label component, one confirmation pattern.

### Phase 5 — Application shell

- Introduce `vue-router`; every screen gets a URL.
- Reduce `App.vue` from 1,210 lines to a shell; Overview becomes a route.
- CSS Grid layout replacing the `calc(100vw - 39rem)` constants; real tablet breakpoint (§11.5).
- Persist UI preferences (sidebar, density, last route) — currently nothing survives a refresh (§5.4).

**Exit:** deep-linkable, refresh-safe, correct at every viewport ≥768 px.

### Phase 6 — Robot context model

- `stores/fleet.ts` + `useRobotStore(robotId)` factory (§12 Stage 1).
- `robots` table; `robot_id` on `missions`; per-robot mode (§12 Stage 1).
- `/robots/:robotId/...` routing; `RobotContextBar` with name and accent colour (§12 Stage 2).
- `/system/robots` registration screen, replacing build-time `VITE_ROS_URL`.

**Exit:** still one robot, but the architecture no longer assumes it.

### Phase 7 — Feature migration & UX

- Move panels into the §10 IA: `operate`, `mission`, `navigation`, `mapping`, `docking`, `diagnostics`, `/fleet/maps`, `/fleet/stations`.
- Split `MapView.vue` into layers + interaction modules (§9).
- Build `diagnostics`: topic health, message rates, TF tree, fault list — the §5.4 observability gap.
- Localisation quality indicator derived from the particle cloud (already subscribed, currently only drawn).

**Exit:** the IA of §10, fully populated.

### Phase 8 — Performance

- Replace `canvas.toDataURL()` with direct canvas layers for map and costmap (§7.2).
- Throttle `/scan` and `/particle_cloud`; pool particle markers (§7.3).
- `shallowRef` for all raw ROS message payloads in the store (§7.4).
- Replace ECharts with uPlot (§7.1).
- Route-level code splitting; drop `backdrop-blur` and the continuous glow animation (§11.4, §11.6).

**Exit:** measured improvement against the Phase 0 baseline, on the target hardware.

### Phase 9 — Fleet

Stages 3–5 of §12: connection pool, namespacing decision, fleet surfaces, cross-robot safety.

### Sequencing notes

- **Phases 1 and 2 are the highest value in this document** and require none of the redesign. If only one thing ships, ship Phase 1.
- Phase 3 is independent; run it in parallel.
- Phase 4 must precede 5 and 7 — migrating features into a shell built on inconsistent primitives just relocates the inconsistency.
- Phase 6 must precede 9, but Phases 7 and 8 can proceed in parallel with 6.
- Phase 8 is placed late, but the costmap `toDataURL()` fix (§7.2) is a contained change worth pulling forward if the machine is already under load.

---

## 15. Appendix — defect register

Concrete defects found during this audit, ordered by severity. Each is independently fixable.

| # | Severity | Defect | Evidence |
|---|---|---|---|
| 1 | **Critical** | E-STOP never publishes a stop command; reports success while disconnected | `App.vue:941-945`, `App.vue:1153-1158`, `useROS.js:765-808` |
| 2 | **Critical** | `/api/mode/switch` changes nothing but reports success; UI switches modes anyway | `mode.py:46-68`, `App.vue:821-832` |
| 3 | **Critical** | Renaming/removing a map `.yaml` on disk silently cascade-deletes all keepout zones, docks and destinations | `maps.py:76-80`, `database.py:46,53,65,101` |
| 4 | **Critical** | `clearAllZones` deletes every keepout zone with no confirmation | `SetupPanel.vue` `clearAllZones` |
| 5 | **High** | All ROS-layer error toasts are invisible (9 call sites route to an unrendered store) | `useROS.js:18,218,246,314,866,872,899,907`; `ToastManager.vue` |
| 6 | **High** | Two nodes advertise `/station_config` and `/dock_command`; resolution is non-deterministic | `mission_manager_node.py:114-126`, `docking_manager_node.py:106-107`, `bringup.launch.py:187-189` |
| 7 | **High** | Saved missions lose `station_id` and `dest_point`; reload addresses different stations | `models.py:28-34`, `MissionPanel.vue` `doSave`/`doLoad`/`startMission` |
| 8 | **High** | Dock `approach` pose is discarded; the operator's second placement click is thrown away | `models.py:106-109`, `docks.py:38-41,55-58`, `App.vue:972` |
| 9 | **High** | Changing a destination's type silently resets its `yaw` to 0 | `MissionPanel.vue` `changeDestType`, `models.py:83`, `destinations.py:41-44` |
| 10 | **High** | No reconnect after a dropped ROS connection; requires a manual click | `useROS.js:165-172` |
| 11 | **High** | No staleness detection — a frozen topic reads as ONLINE/AVAILABLE forever | no timestamp comparison anywhere in `useROS.js` |
| 12 | **High** | Mission watchdog advances to the next goal after 120 s while the robot may still be moving | `useROS.js:728-734` |
| 13 | **Medium** | Mission status handler reads the last entry of `status_list` without matching `goal_id` — another goal's completion can advance the mission | `useROS.js:236-254` |
| 14 | **Medium** | Dock rename registers the new station id without deleting the old one | `DockingPanel.vue` `saveRename` |
| 15 | **Medium** | Dual-write to SQLite + ROS with no transaction, no await on the ROS half, no reconciliation | §1.3, 10 call sites |
| 16 | **Medium** | `isBusy` is computed and documented as a command gate but gates nothing | `stores/robot.js:151-155` |
| 17 | **Medium** | Offline overlay is `pointer-events-none`; all controls stay clickable while disconnected | `App.vue:460-464` |
| 18 | **Medium** | No auth on any endpoint + `allow_origins=["*"]` + unauthenticated rosbridge on a host network | `main.py:20-25`, `bringup.launch.py:113-116`, `docker-compose.yml:44` |
| 19 | **Medium** | Backend URL hardcoded to `localhost:3001`; LAN deployment breaks while the ROS URL is configurable | `useAPI.js:17,65` |
| 20 | **Medium** | Costmap re-encoded as a base64 PNG on the main thread every 500 ms | `MapView.vue:876-922`, `useROS.js:541` |
| 21 | **Medium** | Particle cloud destroys and recreates every marker per message, unthrottled | `MapView.vue` `renderParticleCloud`, `useROS.js:448-463` |
| 22 | **Medium** | `activeMapId` is never restored after a refresh → destinations and docks are fetched unscoped across all maps | `stores/robot.js:81`; no persistence anywhere in `src/` |
| 23 | **Low** | `ControlPanel.vue` calls `useAPI()`/`useToast()` without importing them — would throw on mount | `ControlPanel.vue:8-9` |
| 24 | **Low** | `useROS()` returns `ros: _ros`, captured before `connect()` assigns it — always `null` | `useROS.js:21,1224` |
| 25 | **Low** | `callRobotModeService` is exported and never called; no node advertises `/robot_mode` | `useROS.js:852-877,1243` |
| 26 | **Low** | `/scan` subscribed with no throttle | `useROS.js:439-446` |
| 27 | **Low** | Raw ROS messages stored in deep-reactive `ref()`s | `stores/robot.js:38,119,123,126` |
| 28 | **Low** | `latency_ms` is always `null`; the "Latency" metric permanently reads "—" | `main.py:59`, `useSystemStats.js:36` |
| 29 | **Low** | Map panel width uses two different hardcoded constants for the same layout | `App.vue:204,236` |
| 30 | **Low** | `:root` mixes dark app tokens with light sidebar tokens; dark mode forced in JS | `main.css:16-58`, `App.vue:1105` |
| 31 | **Low** | ~1,268 lines of dead components; 42 unused shadcn primitive files; 3 dead dependencies | §2.2, §7.1 |
| 32 | **Low** | `README.md` states "ROS2 Humble"; the stack is Jazzy | `README.md:3` vs `docker-compose.yml:2` |
| 33 | **Low** | `useROS.js` header documents "Foxglove Bridge"; the launch file starts `rosbridge_server` | `useROS.js:2` vs `bringup.launch.py:113-116` |
| 34 | **Low** | Stale comment claims keepout zones are restored from localStorage; no localStorage exists | `useROS.js:155` |

---

*End of audit. No application code was modified in producing this document.*
