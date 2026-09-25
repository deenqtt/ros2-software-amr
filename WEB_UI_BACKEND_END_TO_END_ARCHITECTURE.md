# Web UI + Backend End-to-End Architecture

Audit date: 2026-09-18  
Repository: `/home/deden/Documents/my-project/ros2-software-amr`  
Scope: `web-ui/`, `backend/`, and only root launch/configuration files needed to understand them.

## Evidence notation

- **VERIFIED FROM CODE** — directly supported by an implementation file and symbol/line reference.
- **VERIFIED AT RUNTIME** — observed during this audit.
- **INFERRED** — concluded from code relationships, not live behavior.
- **NOT VERIFIED** — the environment or available runtime did not permit observation.

This report documents the existing implementation. No application behavior was changed.

## 1. Executive summary

The application is a Vue 3 single-page Web UI served by Vite on port 3000. `App.vue` owns the complete shell: header, mode toggle, sidebar tabs, Leaflet map, panel area, dialogs, offline overlay, and toast host. There is no URL router implementation. `vue-router` is declared and installed but no `createRouter`, route table, or `RouterView` is used. The user-visible “pages” are local tabs selected by `activeTab` in `App.vue`.

The browser has two independent communication paths:

1. `web-ui/src/composables/useAPI.js` performs direct `fetch()` calls to hard-coded `http://localhost:3001/api` for application data and mode state.
2. `web-ui/src/composables/useROS.js` creates a direct `ROSLIB.Ros` WebSocket, defaulting to `ws://localhost:8765`, and uses rosbridge topic/service/action operations.

FastAPI does not import ROS libraries and is not the ROS transport boundary. It owns SQLite records and map files, exposes CRUD REST routes, serves `/maps/*`, and starts a background shell command for mode switching. That mode path is incomplete: the backend image does not contain the referenced script, and the current `scripts/docker_run.sh nav` branch is explicitly deferred.

Real-time robot telemetry is kept in Pinia and consumed by `MapView`, the header, `SpeedChart`, and active panels. Missions, destinations, docks, keepouts, mode settings, and map metadata are application data persisted by FastAPI/SQLite or the filesystem. Mission execution is ROS-driven, but mission definitions are saved through REST.

## 2. Repository baseline

**VERIFIED AT RUNTIME** from the requested commands:

| Item | Value |
|---|---|
| `pwd` | `/home/deden/Documents/my-project/ros2-software-amr` |
| Branch | `main` |
| HEAD | `3ddde28b668d646fed8f9e39188a9f1153e74a28` |
| Relation | `main...origin/main` |
| Scoped working tree | No pre-existing modifications under `web-ui/` or `backend/` |
| Whole working tree | Already dirty outside scope: Docker, ROS workspace, scripts, docs, reports, generated/runtime artifacts |

Existing uncommitted work was preserved. The only file created by this audit is this report.

## 3. Technology stack

### Web UI

| Area | Implementation evidence |
|---|---|
| Framework | Vue 3 Composition API / `<script setup>` (`src/main.js`, `src/App.vue`) |
| Language | JavaScript; no TypeScript source or `tsconfig.json` |
| Build/dev | Vite; `vite.config.js`; scripts `dev: vite`, `build: vite build` |
| Installed versions observed | Vue 3.5.30, Vite 5.4.21, `@vitejs/plugin-vue` 5.2.4 |
| Routing | No implementation; `vue-router` 4.6.4 is unused |
| State | Pinia 2.3.1; `src/stores/robot.js` |
| Styling | Tailwind CSS 3.4.19, PostCSS, custom variables in `src/assets/main.css` |
| UI primitives | Local shadcn-vue-style components under `src/components/ui/`; Radix/Reka dependencies |
| Icons | `lucide-vue-next`; Radix icons dependency also installed |
| Map | Leaflet 1.9.4 with `L.CRS.Simple` |
| Charts | ECharts 6.0.0 + `vue-echarts`; active `SpeedChart`, unused `BatteryChart` |
| ROS browser client | `roslib` 1.4.1 |
| HTTP | Native `fetch` through `useAPI.js` |
| Toasts | `vue-sonner` in active tree; separate custom `useToast` also exists |
| Tests | No test script/files found |
| Lint | ESLint + eslint-plugin-vue declared; configured command is broken in this checkout |

### Backend

| Area | Implementation evidence |
|---|---|
| Framework | FastAPI in `backend/main.py` |
| ASGI server | Uvicorn (`backend/Dockerfile`, README, `scripts/start_dev.sh`) |
| Python assumptions | Docker `python:3.11-slim`; host audit interpreter Python 3.12.3 |
| Declared packages | FastAPI 0.111.0, Uvicorn 0.29.0, multipart, PyYAML, Pillow, psutil |
| Audit venv versions | FastAPI 0.135.1, Uvicorn 0.41.0, Pydantic 2.12.5, PyYAML 6.0.3; `psutil` and `httpx` missing |
| Routers | maps, missions, keepout, docks, destinations, mode |
| Schemas | Pydantic models in `models.py` and `routers/mode.py` |
| Storage | SQLite via `sqlite3`; map files on filesystem |
| WebSocket | None in backend |
| ROS dependency | None in backend Python imports |
| Auth | None |
| CORS | All origins, methods, and headers |
| Tests | No backend test suite found |

## 4. Directory architecture

```text
web-ui/
├── index.html, package.json, vite.config.js
└── src/
    ├── main.js                  # mount Vue + Pinia
    ├── App.vue                  # shell, tabs, mode/startup flows
    ├── stores/robot.js          # central state
    ├── composables/             # REST, ROS, map mode, stats, toast
    ├── components/MapView.vue   # Leaflet, map, sensors, camera
    ├── components/MissionPanel.vue
    ├── components/DockingPanel.vue
    ├── components/MappingPanel.vue
    ├── components/SetupPanel.vue
    └── components/ui/           # local UI primitives/sidebar

backend/
├── main.py                      # app, CORS, mounts, startup, health/stats
├── database.py                  # SQLite setup and paths
├── models.py                    # Pydantic schemas
└── routers/                     # maps, missions, keepout, docks, destinations, mode
```

Present but not imported by active `App.vue`: `ControlPanel.vue`, `NavigationPanel.vue`, `StatusPanel.vue`, `MapManager.vue`, `KeepoutEditor.vue`, `MissionEditor.vue`, `BatteryChart.vue`, and `ToastManager.vue`. They are legacy/alternate paths, not runtime pages.

## 5. Frontend startup

**VERIFIED FROM CODE:**

```text
npm run dev
  → package.json: vite
  → vite.config.js (0.0.0.0:3000, /stream proxy)
  → index.html (#app + /src/main.js)
  → main.js: createApp(App), createPinia(), mount('#app')
  → App.vue
```

`index.html` loads Inter/Leaflet CSS externally and requests `/agv-icon.svg`; the repository has `public/amr-icon.svg`, so the favicon path is a likely asset mismatch.

Exact repository-defined commands:

- Web UI: `cd web-ui && npm run dev`.
- Web UI build: `cd web-ui && npm run build`.
- Setup helper: `bash scripts/setup_webui.sh` (runs `npm install`, then dev; `--build` runs the build).

## 6. Backend startup

**VERIFIED FROM CODE:**

```text
uvicorn main:app --host 0.0.0.0 --port 3001 [--reload]
  → backend/main.py
      FastAPI("AMR Backend", version="1.0.0")
      CORS middleware
      include six routers
      mount /maps → StaticFiles(MAPS_DIR)
      startup event → database.init_db()
```

Exact repository-defined commands:

- README native command: `cd backend && pip install -r requirements.txt && uvicorn main:app --host 0.0.0.0 --port 3001 --reload`.
- Docker service: `docker compose up --build amr-backend`.
- Combined helper: `bash scripts/start_dev.sh`; it requires `backend/.venv/bin/uvicorn`, sets `DB_PATH=$ROOT/data/amr.db`, `MAPS_DIR=$ROOT/maps`, `ROS_MAPS_PATH=$ROOT/maps`, then launches UI on 3000.

`main.py` uses `@app.on_event("startup")`, not an explicit lifespan. There is no backend ROS/WebSocket initialization.

The backend Dockerfile copies only `backend/` into `/app`. `routers/mode.py` computes a repository-root-relative `scripts/docker_run.sh`; in that image it resolves to `/scripts/docker_run.sh`, which is absent. The mode endpoint therefore cannot execute its intended script in the current image.

## 7. Initial browser-load sequence

```text
Browser http://localhost:3000/
  ↓ index.html
  ↓ src/main.js
  ↓ createApp(App) + Pinia + mount
  ↓ App setup creates store, useROS, useAPI, useMapMode, useSystemStats
  ↓ renders header + sidebar + MapView + Overview + offline overlay
  ↓ onMounted:
      localStorage('amr_ros_url') or ws://localhost:8765
      ros.connect(savedUrl)
      GET http://localhost:3001/api/maps
      GET http://localhost:3001/api/mode
      start /api/stats polling (immediate, then 5 s)
      add .dark class
```

Evidence: `App.vue:686-689`, `App.vue:1038-1058`, `useROS.js:150-158`, `MapView.vue:587-622`.

Initial state is `appMode='navigation'`, `activeTab='overview'`, `robotPose={0,0,0}`, `navStatus='idle'`, and no map. If mode is still the database default `navigation` with empty map, `syncModeFromBackend(true)` shows the startup dialog (`App.vue:965-990`). If ROS is offline, the offline overlay is shown. If `/map` is silent, MapView shows “Waiting for map data”.

There is no URL redirect or route resolution. The default page is the Overview tab in `App.vue`.

## 8. Complete frontend route/page map

```text
App.vue
├── navigation mode
│   ├── Overview (default, inline App template)
│   ├── Mission → MissionPanel.vue
│   ├── Docking → DockingPanel.vue
│   └── Setup → SetupPanel.vue
└── mapping mode
    ├── Overview (same inline template)
    └── Mapping → MappingPanel.vue
```

Items are defined at `App.vue:740-749`; `App.vue:423-446` selects panels; `AppSidebar.vue:19-35` emits a tab id. There are no child URL routes.

## 9. Page-by-page functionality

### Overview

Shows ROS URL/connect control, pose cards, navigation and docking badges, mission progress, expandable AMCL initial-pose form, velocity chart, system stats, and the global header indicators. Connect stores `amr_ros_url` and calls `ros.connect()` (`App.vue:870-878`). Initial pose converts degrees to radians and publishes `/initialpose` (`App.vue:880-888`). E-STOP calls `cancelNavigation()` and `store.stopMission()` (`App.vue:890-892`); it does not itself publish zero `/cmd_vel`.

### Mapping

`MappingPanel.vue` shows SLAM/map presence, linear/angular sliders and presets, joystick, D-pad, stop, and Save Map. Joystick/D-pad calls `publishCmdVel()` every 80 ms and publishes zero on release (`MappingPanel.vue:238-282`, `useROS.js:920-950`). Save Map calls `/map_saver/save_map` (`MappingPanel.vue:288-309`, `useROS.js:791-833`). “SLAM ACTIVE” means only `store.mapData != null`; it is not a lifecycle subscription.

### Mission

`MissionPanel.vue` manages destinations, up to five waypoints, task/continue-mode selection, reorder/delete/clear, Save/Load/Delete dialogs, loop settings, Start/Pause/Stop, and Manual Continue. Destination click flows through MapView emit → App exposed ref → `MissionPanel.onMapClick()` → `POST /api/destinations` → `/station_config` (`App.vue:894-906`, `MissionPanel.vue:324-389`). Start registers stations, publishes `/amr/mission_payload`, and starts `/mission_plan` goals (`MissionPanel.vue:420-454`, `useROS.js:673-735`).

### Docking

`DockingPanel.vue` shows docking state, station selection, Send to Dock, Undock, Cancel, auto-docking toggle/threshold/target, station list, place-on-map, add, rename, and remove. Mount/active-map change GETs `/api/docks` and registers stations with `/station_config` (`DockingPanel.vue:212-226`). Send/undock use `/dock_command`; `/dock_status` updates the store (`useROS.js:851-916`). Low-battery auto-docking is watched in `App.vue:929-960`.

### Setup

`SetupPanel.vue` shows CPU/memory/latency, maps refresh/list/activate, YAML+PGM/PNG upload, keepout draw/list/delete/clear. Activation calls `POST /api/maps/{id}/activate`, calls `/map_server/load_map`, loads keepouts, and publishes them to `/amr/keepout_zones` (`SetupPanel.vue:169-187`). Upload uses `FormData` fields `yaml_file` and `pgm_file` (`SetupPanel.vue:196-224`).

## 10. Component hierarchy

```text
main.js
└── App.vue
    ├── Toaster
    ├── header (mode, pose, status, battery, ROS, E-STOP)
    ├── AppSidebar
    ├── MapView
    │   ├── Leaflet map and overlays
    │   ├── toolbar and interaction modes
    │   ├── camera <img>
    │   └── robot/path/goal/waypoint/dock/sensor layers
    └── panel Card/ScrollArea
        ├── Overview inline + SpeedChart
        ├── MappingPanel
        ├── MissionPanel
        ├── DockingPanel
        └── SetupPanel
```

`App.vue` owns shell state and dialog/forms. `MapView` owns Leaflet objects and drag/drawing state. Panels own their local forms/loading state and share Pinia/composables. MapView emits `destinationClick` and `dockPlaced`; App forwards destinations to the MissionPanel exposed method.

## 11. State-management architecture

| State | Source/update | Consumers | Persistence |
|---|---|---|---|
| `appMode` | UI startup/mode switch | App, MapView, sidebar | Browser memory; backend mode mirror |
| `rosConnected`, `rosUrl` | ROS events/input | header, overlay, panels | URL in `localStorage('amr_ros_url')` |
| `mapData` | `/map` | MapView, `hasMap` | None |
| `robotPose` | TF, `/amcl_pose`, `/pose` | header, Overview, MapView | None |
| `robotVelocity` | `/odom` twist | SpeedChart, MappingPanel | None |
| `navStatus`, `navGoal`, `plannedPath` | ROS callbacks/UI | App, MapView, mission/dock panels | None |
| `waypoints`, mission flags/index | MissionPanel/useROS | MissionPanel, App, MapView | Saved copy via missions REST |
| `maps`, `activeMapId` | `/api/maps`, activation | Setup, Mission, Docking, MapView | Maps in SQLite; active ID memory |
| `destinations` | `/api/destinations` | MissionPanel, MapView | SQLite |
| `dockStations` | `/api/docks` | DockingPanel, MapView, auto-dock | SQLite |
| `keepoutZones` | `/api/keepout`, map drawing | Setup, MapView, ROS | SQLite only when map active; active list memory |
| battery fields | `/robot_status`, `/battery_state` | header, auto-dock | None |
| footprint/costmap/scan/particles | ROS topics | MapView | None |

`useROS.js` is a module-level singleton with ROS socket, TF buffer, mission execution variables, and timers. `useMapMode.js`, `useSystemStats.js`, and `useToast.js` also keep module-level singleton state. There is no Pinia persistence plugin, cookie, or session storage.

## 12. Frontend communication/service layer

### `useAPI.js`

`useAPI._fetch()` concatenates `BASE = 'http://localhost:3001/api'`, uses native `fetch`, throws on non-2xx, returns `null` for 204, parses JSON by content type, and otherwise returns text. There is no timeout, abort controller, retry, auth header, or environment lookup. `staticUrl()` hard-codes the same host and is unused by the active tree.

### `useROS.js`

`connect(url)` replaces the module-level ROSLIB socket, registers `connection`, `error`, and `close`, then runs `_subscribeAll()` after connection. There is no automatic reconnect. Close marks Pinia offline, resets nav status through `setConnected(false)`, clears AMCL timing, and clears the TF buffer. `/map` and `/robot_description` use custom rosbridge subscribe messages requesting transient-local QoS; other topics use `ROSLIB.Topic.subscribe()`.

### `useSystemStats.js`

App starts `/stats` polling immediately and every 5 seconds. CPU, memory, and latency update only when response fields are non-null; all failures are silently ignored. The backend always returns `latency_ms: None`, and no active caller invokes `setLatency()`.

## 13. ROSLIB/rosbridge architecture

```text
Vue components
  ├── useAPI.js ── HTTP http://localhost:3001/api ──> FastAPI
  │                                                    └── SQLite/files
  └── useROS.js ─ WebSocket ws://<host>:8765 ────────> rosbridge_server
                                                       └── ROS 2

Camera: ROS /camera/image_raw → web_video_server :8080 → browser <img>
```

FastAPI is not between the browser and ROS. `useROS.js` has a stale comment saying “Foxglove Bridge”; the configured contract and Compose launch path use `rosbridge_server`.

## 14. ROS interface inventory

### Subscriptions: ROS → browser

| Topic | Type used | Consumer/behavior |
|---|---|---|
| `/map` | `nav_msgs/OccupancyGrid` | Raw map; custom transient-local subscribe |
| `/tf` | `tf2_msgs/TFMessage` | TF buffer; compose map→odom→base |
| `/tf_static` | `tf2_msgs/TFMessage` | Static TF buffer |
| `/amcl_pose` | `geometry_msgs/PoseWithCovarianceStamped` | Pose fallback if TF unavailable |
| `/pose` | `geometry_msgs/PoseWithCovarianceStamped` | SLAM fallback if TF/AMCL unavailable |
| `/odom` | `nav_msgs/Odometry` | Linear X/angular Z velocity only |
| `/plan` | `nav_msgs/Path` | Planned path polyline |
| `/scan` | `sensor_msgs/LaserScan` | Laser points on map |
| `/particle_cloud` | `nav2_msgs/ParticleCloud` | Particle markers |
| `/robot_description` | `std_msgs/String` | URDF footprint parser; transient-local request |
| `/global_costmap/costmap` | `nav_msgs/OccupancyGrid` | Costmap overlay; throttle 500 ms |
| `/navigate_to_pose/_action/status` | `action_msgs/GoalStatusArray` | Terminal single-goal state |
| `/mission_plan/_action/status` | `action_msgs/GoalStatusArray` | Advance mission waypoint |
| `/mission_plan/_action/feedback` | `custom_interfaces/action/MissionPlan_FeedbackMessage` | Text → nav status |
| `/dock_status` | `std_msgs/String` | Docking/nav state machine |
| `/robot_status` | `custom_interfaces/msg/RobotStatus` | Nav/docking/battery fields |
| `/battery_state` | `sensor_msgs/BatteryState` | Battery fallback; throttle 1 s |

Implementation evidence: `useROS.js:200-624`.

### Publications: browser → ROS

| Topic | Type | Trigger |
|---|---|---|
| `/goal_pose` | `geometry_msgs/PoseStamped` | Single-goal form/map click via `navigateTo()` |
| `/cmd_vel` | `geometry_msgs/Twist` | Mapping joystick/D-pad every 80 ms |
| `/initialpose` | `geometry_msgs/PoseWithCovarianceStamped` | Initial-pose form/map drag |
| `/amr/mission_payload` | `std_msgs/String` JSON | Mission start |
| `/amr/keepout_zones` | `std_msgs/String` JSON | Draw/delete/clear/reconnect |

### Services: browser → ROS

| Service | Type | Trigger |
|---|---|---|
| `/robot_mode` | `custom_interfaces/srv/RobotMode` | Header mode switch |
| `/dock_command` | `custom_interfaces/srv/DockCommand` | Dock/undock/cancel |
| `/station_config` | `custom_interfaces/srv/StationConfig` | Destination/dock/mission station registration |
| `/mission_confirm` | `std_srvs/srv/Trigger` | Manual mission continuation |
| `/map_server/load_map` | `nav2_msgs/srv/LoadMap` | Map activation |
| `/map_saver/save_map` | `nav2_msgs/srv/SaveMap` | Mapping save |
| `/navigate_to_pose/_action/cancel_goal` | `action_msgs/srv/CancelGoal` | Cancel workaround |

### Action protocol

Mission goals are sent with rosbridge `op: 'send_action_goal'`, action `/mission_plan`, and type `custom_interfaces/action/MissionPlan`; completion is inferred from the status topic. `navigateTo()` does not send a `/navigate_to_pose` action goal; it publishes `/goal_pose` and watches status/cancel endpoints.

## 15. ROS contract comparison

Compared with `docs/ROS_INTERFACE_CONTRACT.md`:

| Interface/fact | Classification | Explanation |
|---|---|---|
| `/map`, OccupancyGrid, transient-local | MATCH | Custom QoS request and MapView consumer |
| `/tf`, `/tf_static`, `/amcl_pose`, `/pose`, `/odom` | MATCH | Names/types/fallback code match contract |
| `/plan`, `/scan`, particles, costmap | MATCH | Active subscriptions match documented types |
| `/robot_description` transient-local | MATCH | URDF parser plus QoS request |
| `/dock_status` values | MATCH | Handled values match contract list |
| `/battery_state` | MATCH/PARTIAL | Active fallback; primary battery is `/robot_status` |
| `/goal_pose` | MATCH | UI publication documented and implemented |
| `/navigate_to_pose` action | MISMATCH/PARTIAL | Contract describes action; source publishes `/goal_pose` |
| `/mission_plan` action | MATCH/PARTIAL | Action/status/feedback path exists; goal carries station/task, not coordinates |
| `/dock_command`, `/station_config`, `/mission_confirm` | MATCH | Service names/types/fields align |
| `/robot_mode` | CONTRACT-ONLY/PARTIAL | UI calls it; contract says no current provider |
| `/amr/mission_payload` | UI-ONLY/DISCONNECTED | UI publishes; contract audit found no subscriber |
| Foxglove wording | MISMATCH | Source comment vs actual rosbridge launch |
| Physical robot mapping | NOT VERIFIED | Contract intentionally leaves it TBD |

No ROS interface was changed.

## 16. Backend application architecture

```text
FastAPI app (backend/main.py)
├── CORS allow all
├── /api/maps, /api/missions, /api/keepout
├── /api/docks, /api/destinations, /api/mode
├── /maps/* static map files
├── /health
└── /api/stats

startup → database.init_db()
        → create dirs, WAL DB, tables, migrations, mode defaults
```

Routers call `database.get_db()` directly. There is no service/repository layer, injected settings object, auth layer, or backend ROS worker. `mode.py` is the only router with an external process side effect.

## 17. REST API inventory

Base URL: `http://localhost:3001/api` (`useAPI.js`).

| Method | Path | Handler | Input/output | UI use |
|---|---|---|---|---|
| GET | `/api/maps` | `maps.list_maps` | `list[MapOut]`; scans/syncs YAML | App, Setup |
| POST | `/api/maps/upload` | `maps.upload_map` | multipart YAML + PGM/PNG → `MapOut` | Setup |
| POST | `/api/maps/{id}/activate` | `maps.activate_map` | → `MapActivateOut.yaml_path` | Setup |
| DELETE | `/api/maps/{id}` | `maps.delete_map` | DB metadata only → `{ok:true}` | No active caller |
| GET | `/api/missions` | `missions.list_missions` | optional `map_id` → missions | Mission |
| POST | `/api/missions` | `missions.create_mission` | `MissionIn` → `MissionOut` | Mission |
| PUT | `/api/missions/{id}` | `missions.update_mission` | `MissionIn` → `MissionOut` | No active caller |
| DELETE | `/api/missions/{id}` | `missions.delete_mission` | → `{ok:true}` | Mission |
| GET | `/api/keepout` | `keepout.list_keepout` | optional `map_id` → polygons | Setup/MapView |
| POST | `/api/keepout` | `keepout.create_keepout` | `KeepoutIn` → `KeepoutOut` | MapView |
| DELETE | `/api/keepout/{id}` | `keepout.delete_keepout` | → `{ok:true}` | Setup |
| GET | `/api/docks` | `docks.list_docks` | optional `map_id` → docks | Docking |
| POST | `/api/docks` | `docks.create_dock` | `DockIn` → `DockOut` | App/Docking |
| PUT | `/api/docks/{id}` | `docks.update_dock` | `DockIn` → `DockOut` | Dock rename |
| DELETE | `/api/docks/{id}` | `docks.delete_dock` | → `{ok:true}` | Docking |
| GET | `/api/destinations` | `destinations.list_destinations` | optional `map_id` → destinations | Mission |
| POST | `/api/destinations` | `destinations.create_destination` | `DestinationIn` → destination | Mission |
| PUT | `/api/destinations/{id}` | `destinations.update_destination` | `DestinationIn` → destination | Mission |
| DELETE | `/api/destinations/{id}` | `destinations.delete_destination` | 204 | Mission |
| GET | `/api/mode` | `mode.get_mode` | `{mode,map_file}` | App |
| POST | `/api/mode/switch` | `mode.switch_mode` | `SwitchRequest` → `SwitchResponse` | Startup |
| GET | `/api/stats` | `main.system_stats` | CPU/memory/latency | App |
| GET | `/health` | `main.health` | `{"status":"ok"}` | No active caller |
| GET | `/maps/{filename}` | StaticFiles | raw file | no active caller; helper unused |

The app route inventory generated 28 Starlette routes including docs/static infrastructure. There is no REST endpoint for live ROS telemetry or robot commands.

## 18. Backend schemas and data models

### Maps

`MapOut` has id/name/YAML filename, optional resolution/dimensions/origin, and `created_at`. `maps.py` scans `MAPS_DIR`, parses YAML, reads PGM dimensions, inserts new YAML files, and removes rows whose YAML disappeared. Activation returns `ROS_MAPS_PATH/<yaml_file>`.

### Missions

`MissionIn` contains name, optional map id, waypoints, loop, and loop count. `WaypointItem` stores only name/x/y/theta/task/continue_mode. The frontend sends extra `dest_point` and `station_id`; current Pydantic behavior ignores them, so saved missions lose destination/station association.

### Keepouts

`KeepoutIn/Out` contains map id, name, and `{x,y}` polygon list. The polygon is JSON text in SQLite and has a map foreign key with cascade.

### Destinations

`DestinationIn/Out` contains optional map id, name, x, y, yaw, and station type (0 Pick, 1 Drop, 2 Pick & Drop). The UI also registers each destination over `/station_config`.

### Docks

The table stores target plus `approach_x`, `approach_y`, `approach_yaw`, but `DockIn` and `DockOut` expose only map id/name/target. App sends an `approach` object; Pydantic ignores it and the router inserts NULL approach columns. The two-step UI placement does not survive backend persistence.

### Settings

Key/value rows persist `ros_mode` and `ros_map_file`, defaulting to `navigation` and empty string.

## 19. Persistence/storage

`database.py` reads `DB_PATH` (default `/data/amr.db`), `MAPS_DIR` (default `/maps`), and `ROS_MAPS_PATH` (default `MAPS_DIR`). It enables SQLite WAL, creates tables/migrations/defaults, and `get_db()` enables foreign keys and commits/rolls back each operation.

- Maps: YAML/PGM/PNG on disk; metadata in SQLite. Upload saves files and registers metadata. Delete removes DB metadata only; files remain.
- Missions: JSON waypoint array in SQLite.
- Destinations/docks: SQLite rows; map deletion cascades them.
- Keepouts: JSON polygon in SQLite; map deletion cascades them.
- Mode: SQLite settings.
- Pose/map/sensors/battery/active execution: browser memory only.

## 20. Configuration and environment variables

No `.env` or `.env.example` was found in the scoped directories.

| Variable/setting | Default/current value | Used by | Purpose |
|---|---|---|---|
| Vite host | `0.0.0.0` | `vite.config.js` | Dev bind address |
| Vite port | `3000` | `vite.config.js` | Web UI |
| API base | `http://localhost:3001/api` | `useAPI.js` | REST origin; hard-coded |
| Static map base | `http://localhost:3001/maps` | `useAPI.staticUrl` | Helper; unused |
| ROS WebSocket default | `ws://localhost:8765` | `robot.js`, `App.vue` | User-editable/localStorage |
| Camera | `http://<ROS host>:8080/stream?topic=/camera/image_raw` | `MapView.vue` | Direct web video |
| `DB_PATH` | `/data/amr.db` | `database.py` | SQLite file |
| `MAPS_DIR` | `/maps` | backend | Map directory/static mount |
| `ROS_MAPS_PATH` | `MAPS_DIR` | map activation | Path returned to ROS |
| CORS | `*` | `main.py` | All origins/methods/headers |
| Compose `ROS_DOMAIN_ID` | `42` | `docker-compose.yml` | ROS network domain |
| Compose ROS/video/backend ports | `8765/8080/3001` | Compose | Exposed services |

## 21. Hard-coded URL/localhost audit

| Location | Assumption | Classification |
|---|---|---|
| `useAPI.js:17` | Browser calls `http://localhost:3001/api` | Hard-coded multi-PC blocker |
| `useAPI.js:65` | Static files use localhost:3001 | Hard-coded; helper unused |
| `robot.js:20`, `App.vue:1038` | ROS default is localhost:8765 | Runtime configurable via input/localStorage |
| `vite.config.js:18` | `/stream` proxy targets localhost:8080 | Source-configurable; active MapView bypasses it |
| `MapView.vue:467` | Camera host derives from ROS URL, port 8080 fixed | Partially configurable |
| `scripts/start_dev.sh` | UI/backend local ports 3000/3001 | Safe same-PC; no remote API config |
| CORS `*` | Any browser origin accepted | Broad/insecure default |

## 22. Multi-PC readiness

For `Computer A = browser/UI/backend` and `Computer B = ROS/rosbridge/video`, the ROS path is partially ready: the user can enter B’s WebSocket URL and MapView derives B’s camera hostname. The FastAPI path is not configurable because browser fetches always target A-local `localhost:3001`; that is safe only while backend remains on A. The Vite `/stream` proxy still points to A-localhost and is not used by active camera code.

Mode orchestration is a separate blocker: the backend image lacks the script/Docker access, and current `docker_run.sh nav` exits because Nav2 integration is deferred. No ROS namespace or QoS configuration is exposed in the UI. No physical teammate interface is inferred.

## 23. Camera flow

```text
ROS /camera/image_raw
  → web_video_server :8080
  → MapView computed URL http://<host>:8080/stream?topic=/camera/image_raw
  → browser <img>
```

It is not ROSLIB image subscription and does not pass through FastAPI. `showCamera` starts false. Image load/error handlers and Retry control manage loading/error UI; a five-second timer clears loading if MJPEG does not emit a normal load event.

## 24. Map flow

```text
/map nav_msgs/OccupancyGrid
  → rosbridge transient-local subscription
  → useROS store.setMapData()
  → MapView.renderOccupancyGrid()
  → canvas ImageData + vertical flip + data URL
  → Leaflet L.imageOverlay on L.CRS.Simple
```

`renderOccupancyGrid()` uses width/height/resolution/origin, maps unknown to gray, free to white, occupied values to dark grayscale, flips ROS row order, uses 100 pixels/metre, and fits the first overlay. Costmap is a parallel transparent/cyan/blue/magenta/red canvas overlay. `/plan` becomes a blue polyline, laser data becomes points relative to current pose, particles become purple markers, and `/robot_description` controls robot icon dimensions.

Map interactions: navigate publishes `/goal_pose`; initial pose publishes `/initialpose`; destination emits to MissionPanel; keepout click/Finish publishes JSON and optionally POSTs `/keepout`; dock placement uses two steps but backend drops approach data. The raw waypoint toolbar currently warns that destinations panel must be used instead of adding a waypoint.

## 25. Robot-control flow

### Single navigation

```text
MapView click/drag or navigation handler
  → onMapMouseUp()
  → ros.navigateTo(x, y, theta|null)
  → store.navGoal + navStatus='navigating'
  → publish /goal_pose geometry_msgs/PoseStamped, frame_id=map
  → /navigate_to_pose/_action/status subscription
  → terminal status clears local goal/path and returns idle
```

The active shell uses MapView for this path. `NavigationPanel.vue` and `ControlPanel.vue` contain alternate form implementations but are not imported by App.

### Teleoperation

```text
MappingPanel joystick/D-pad
  → calculate linear/angular limits
  → useROS.publishCmdVel()
  → /cmd_vel geometry_msgs/Twist every 80 ms
  → release/stop → /cmd_vel zero
```

### Emergency stop

Header E-STOP calls `cancelNavigation()` and `store.stopMission()`. MappingPanel’s square/joystick release publishes zero Twist. The header E-STOP itself does not call `stopRobot()`; the safety behavior is split across controls.

### Docking command

```text
DockingPanel Send / auto-dock watcher
  → ros.sendToDock(station)
  → store docking/nav status = docking
  → /dock_command custom_interfaces/srv/DockCommand
  → /dock_status and service-result parser
  → docked/idle/error Pinia state
```

## 26. Mission flow

```text
Map destination click
  → POST /api/destinations
  → /station_config save
  → store destination
  → select as waypoint
  → register waypoint stations
  → publish /amr/mission_payload JSON
  → send_action_goal /mission_plan for waypoint 0
  → /mission_plan/_action/status terminal result
  → wait 1 s, send next goal
  → watchdog after missionTimeoutSec advances
  → final goal → store.stopMission()
```

Manual mode sends `continue_mode=false`; Confirm calls `/mission_confirm`. Looping is a MissionPanel watcher: on natural completion it starts `followWaypoints()` again until configured count, with 0 meaning infinite. Save/Load/Delete is separate REST persistence and never runs a ROS mission.

Known mission gaps:

- `MissionIn.WaypointItem` omits frontend `dest_point` and `station_id`, so save/load loses those fields.
- The action goal sends station/task/continue data, not the coordinate fields held by the UI waypoint.
- `MissionEditor.vue` is an unused alternate implementation.
- A raw MapView waypoint click is not implemented beyond a warning.

## 27. Error/offline behavior

### Backend offline

App logs a warning for initial maps and shows startup dialog when initial mode fetch fails. Setup shows temporary inline errors and toasts. Mission/destination/dock actions toast failures. `useAPI` has no timeout or retry, so a stalled fetch can leave UI loading state pending.

### rosbridge offline

ROSLIB errors are logged; close marks Pinia offline, resets nav status, and clears TF. There is no reconnect. App shows a translucent offline overlay and connection prompt; most controls are disabled by `rosConnected`. Calls without `_ros` often return silently; `/robot_mode` explicitly rejects “ROS not connected”.

### Topic stops

Pose, battery, map, costmap, scan, and path values remain stale; no freshness watchdog exists. Mission goals have a timeout watchdog.

### Camera unavailable

`<img @error>` displays “Camera stream unavailable” and Retry. No backend/ROS error event is involved.

### API errors

`useAPI` throws formatted errors for non-2xx responses. Active panels use toasts, inline errors, console warnings, or silent catches depending on flow.

### Malformed ROS data

URDF parsing catches XML/geometry errors. Most subscriptions directly access expected fields with no validation. Dock service result parsing is defensive; malformed other messages may throw inside callbacks without global UI error state.

## 28. Mock/placeholder/dead-code inventory

| Finding | Classification | Evidence |
|---|---|---|
| `vue-router` dependency without router code | DEAD/UNUSED | package dependency; no router symbols |
| ControlPanel, NavigationPanel, StatusPanel, MapManager, KeepoutEditor, MissionEditor | DEAD/UNREFERENCED | Not imported by active App |
| BatteryChart, ToastManager | DEAD/UNREFERENCED | Not imported; ToastManager template is empty |
| `ros3d`, `three` dependencies | UNUSED | No active source imports |
| `useAPI.staticUrl()` | UNUSED | No active caller |
| custom `useToast` | MIXED/LEGACY | Active shell primarily uses vue-sonner |
| MapView waypoint mode | PARTIAL/PLACEHOLDER | Warns rather than adding raw waypoint |
| mode shell orchestration | PARTIAL/DISCONNECTED | Missing script in image; nav helper deferred |
| `/robot_mode` | CONTRACT-ONLY/PARTIAL | UI caller, no provider found in contract audit |
| `/amr/mission_payload` | UI-ONLY/DISCONNECTED | Published; no current subscriber found |
| dock approach point | PARTIAL | Captured UI data discarded by schema/router |
| mission station/destination identity | PARTIAL | Extra frontend fields ignored by backend schema |
| `/api/stats.latency_ms` | PLACEHOLDER | Backend returns null; UI displays `—` |
| search terms mock/dummy/fake/sample/demo | No active mock provider confirmed | Search found placeholders/comments, not mock data source |

## 29. Runtime verification

### Verified

- **Frontend isolated build: PASS.** `npx vite build --outDir /tmp/amr-webui-dist-audit --emptyOutDir=true` transformed 3325 modules and produced output. Warnings: Vite CJS API, stale Browserslist data, module type, and large JS chunk.
- **Backend source compilation: PASS.** A no-write `compile()` check parsed 10 backend Python files.
- **Backend app import: PASS.** With DB/map paths redirected to `/tmp`, FastAPI imported as `AMR Backend 1.0.0` and routes were enumerated.
- **Backend Uvicorn startup: PASS at process level.** Logs showed “Application startup complete” and Uvicorn listening on 127.0.0.1:3001.

### Failed/unavailable

- **Standard `npm run build`: FAIL due filesystem.** Vite could not clean existing root-owned `web-ui/dist/amr-icon.svg` (`EACCES`). The isolated build passed.
- **`npm run lint`: FAIL before linting.** It references missing `web-ui/.gitignore`; direct no-fix ESLint also found no configuration. The package script includes `--fix`, so it was not run as a modifying diagnostic.
- **Backend HTTP integration: NOT VERIFIED.** Sandbox localhost access was unreliable after Uvicorn startup; FastAPI TestClient was unavailable because `httpx` is missing.
- **Frontend dev runtime: NOT VERIFIED.** `npm run dev -- --host 127.0.0.1 --port 3000` failed with sandbox `listen EPERM`.
- **ROS/rosbridge runtime: NOT VERIFIED.** No live ROS/rosbridge/simulator session was available.

## 30. Build/test baseline

| Check | Result | Evidence |
|---|---|---|
| Isolated Vite build | PASS | 3325 modules; output in `/tmp` |
| Standard `npm run build` | FAIL | Existing `dist` ownership |
| `npm run lint` | FAIL | Missing ignore/config files |
| Backend Python parse/compile | PASS | 10 files |
| Backend import/startup | PASS | App import + Uvicorn logs |
| Backend HTTP tests | NOT AVAILABLE | `httpx` absent; sandbox network |
| Frontend tests | NOT AVAILABLE | No test script/files |
| ROS integration | NOT VERIFIED | No live ROS runtime |

## 31. End-to-end architecture diagram

```text
Browser / Vue App ── HTTP :3001 ──> FastAPI ──> SQLite + map files
       │
       └──────── WebSocket :8765 ──> rosbridge_server ──> ROS 2

Camera: ROS /camera/image_raw → web_video_server :8080 → browser <img>
```

The backend is not between the browser and ROS.

## 32. Initial-load sequence diagram

```text
Browser
  → GET :3000/
  → index.html → main.js → createApp/App/Pinia
  → render Overview + MapView + offline overlay
  → GET :3001/api/maps
  → GET :3001/api/mode
  → GET :3001/api/stats, then every 5 s
  → ROSLIB connect(localStorage URL/default)
      → connection → subscribeAll()
  → /map, if available → Pinia mapData → canvas overlay
```

## 33. ROS telemetry sequence

```text
ROS publisher
  → rosbridge WebSocket
  → useROS callback
  → Pinia action/ref
  → Vue reactivity
      ├── MapView layer
      ├── header/status/battery
      ├── SpeedChart
      └── active panel
```

Pose priority is TF composition, then `/amcl_pose`, then `/pose`. `/odom` updates velocity only.

## 34. Robot-command sequence

```text
User gesture
  → component/MapView handler
  → useROS method
  → ROSLIB publish/service/rosbridge action message
  → ROS consumer
  → status/feedback topic
  → Pinia/UI update
```

Single navigation is `/goal_pose`; mission is `/mission_plan`; docking is `/dock_command`; teleop is `/cmd_vel`; initial localization is `/initialpose`.

## 35. Backend REST sequence

```text
Vue component
  → useAPI get/post/put/del/upload
  → native fetch :3001/api
  → FastAPI route + Pydantic validation
  → router function
  → SQLite/filesystem
  → response model/JSON/204
  → useAPI parser
  → component/store + toast/error state
```

The REST path handles durable application data only, not live ROS telemetry, camera, action status, or robot command responses.

## 36. Feature matrix

| Feature | UI | Backend | ROS | Storage | Status |
|---|---:|---:|---:|---:|---|
| Startup/mode selection | Yes | Yes | `/robot_mode` later | settings | PARTIAL/DISCONNECTED |
| Map list/upload | Yes | Yes | No | files + SQLite | ACTIVE CODE; HTTP runtime not verified |
| Map activate/load | Yes | Yes | load_map | files | PARTIAL |
| Occupancy map | Yes | No | `/map` | None | ACTIVE CODE; ROS not verified |
| Pose/battery/sensors | Yes | No | TF/status/sensor topics | None | ACTIVE CODE; ROS not verified |
| Camera | Yes | No | web video | None | ACTIVE CODE; stream not verified |
| Single navigation | Yes | No | `/goal_pose` | None | PARTIAL; contract differs |
| Teleop | Yes | No | `/cmd_vel` | None | ACTIVE CODE; ROS not verified |
| Destinations | Yes | CRUD | `/station_config` | SQLite | PARTIAL |
| Mission save/load | Yes | CRUD | No | SQLite | PARTIAL; fields lost |
| Mission execution | Yes | No | action/status/feedback | memory | PARTIAL |
| Dock stations | Yes | CRUD | `/station_config` | SQLite | PARTIAL; approach lost |
| Dock/undock | Yes | No | command/status | memory | ACTIVE CODE; ROS not verified |
| Keepouts | Yes | CRUD | JSON topic | SQLite | ACTIVE CODE; ROS not verified |
| System stats | Yes | `/stats` | No | None | PARTIAL; latency null |

## 37. Architectural boundaries

### Web UI owns

Presentation, tabs/forms/dialogs, Leaflet and canvas rendering, camera `<img>`, local interaction modes, loading/error display, Pinia state, direct browser ROS transport, and sequential mission-goal orchestration.

### FastAPI owns

REST validation/CRUD for maps, missions, destinations, docks, keepouts, and settings; SQLite/file operations; static map files; and a currently incomplete mode-switch subprocess request.

### rosbridge owns

Browser WebSocket translation for ROS topics, services, and action protocol.

### ROS/simulator owns

Map/TF/odometry/sensor/battery/docking/path/action interfaces, navigation, SLAM, docking, motion, and simulator behavior. This audit documents only the interfaces this UI consumes or sends.

### Important state ownership

| State | Owner |
|---|---|
| Live pose/velocity/map/sensors/battery/feedback | ROS publishers, transported directly into Pinia |
| Active UI mode/tab/map interaction | Vue/App/Pinia |
| Saved map metadata and application records | FastAPI + SQLite/filesystem |
| Mission execution progression | Browser `useROS.js` + ROS action/status |

## 38. Current known gaps

1. No URL router despite dependency and deployment comments.
2. Standard frontend build blocked by root-owned existing `dist`; isolated build passes.
3. Lint is not runnable: missing `web-ui/.gitignore` and ESLint config; package script includes `--fix`.
4. Audit venv does not match declared backend dependencies and lacks `psutil`/`httpx`.
5. Mode switching cannot run from current backend image and the current helper’s nav branch exits deferred.
6. API origin is hard-coded to browser-localhost; remote FastAPI is not configurable.
7. Camera bypasses Vite proxy and hard-codes port/topic.
8. Single navigation uses `/goal_pose` rather than documented action flow.
9. `/robot_mode` has no confirmed provider.
10. `/amr/mission_payload` has no confirmed subscriber.
11. Dock approach coordinates are discarded by API schema/router.
12. Mission station/destination fields are discarded by backend schema.
13. Raw map waypoint mode is warning-only.
14. No reconnect or telemetry freshness indicators.
15. No auth; CORS is wildcard.
16. No active automated frontend/backend test suite.

## 39. Risks

- Mode UI can report a request while ROS restart did not occur.
- Header E-STOP cancels navigation/mission state but does not itself publish zero Twist; mapping stop does.
- Mission save/load can silently lose station/destination identity.
- Dock UI can display a placement whose approach point was never persisted.
- Hard-coded localhost values create deployment and multi-PC failures.
- Silent stale telemetry can be mistaken for current robot state.
- Topic/action/service contract mismatches can produce UI success states without robot execution.
- Dependency drift between requirements and audit venv can change behavior.
- Unauthenticated REST, wildcard CORS, file upload, and subprocess control are broad trust boundaries.

## 40. Recommended future work — do not implement in this session

1. Define explicit configuration for API, rosbridge, camera, and map/ROS paths for the intended two-computer topology.
2. Choose one single-goal contract (`/goal_pose` topic or `/navigate_to_pose` action) and align source/contract/status handling.
3. Define a deployable mode-orchestration boundary; remove the current broken script/Docker assumption.
4. Reconcile mission schema with `station_id`, `dest_point`, task semantics, yaw, and continue behavior; add round-trip tests.
5. Reconcile dock API with approach-point placement; add round-trip tests.
6. Add ROS reconnect/backoff and message freshness state.
7. Define and verify the E-STOP safety contract separately from ordinary cancellation.
8. Make build/lint/test configuration reproducible without auto-fix diagnostics.
9. Add backend endpoint tests with declared HTTP test dependencies and temporary DB/map paths.
10. Add browser/runtime smoke coverage for initial load, offline mode, REST failures, map/camera, and mode transitions.
11. Archive unused components/dependencies only after checking external references.
12. Restrict CORS, add auth, validate uploads, and constrain subprocess control before non-trusted deployment.
13. Compare teammate ROS interfaces only after receiving actual topic/type/service/action/TF/QoS evidence; use adapters/remappings rather than changing this contract silently.
