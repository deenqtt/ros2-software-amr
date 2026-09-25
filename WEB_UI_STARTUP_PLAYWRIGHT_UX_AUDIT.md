# Web UI Startup Browser UX Audit

Audit date: 2026-09-18
Repository: `/home/deden/Documents/my-project/ros2-software-amr`
Scope: `web-ui/`, `backend/`, and runtime/configuration files needed to launch them.
Application behavior was not modified.

## Evidence labels

- **VERIFIED IN BROWSER** — observed in a clean Chrome browser session through the Chrome DevTools Protocol.
- **VERIFIED FROM CODE** — directly supported by source/configuration.
- **INFERRED** — reasoned from the observed implementation, not directly exercised.
- **NOT VERIFIED** — unavailable or intentionally not exercised.

Playwright was not installed in the repository, Python environment, or global Node modules. No dependency was installed. The browser audit used a clean, temporary Google Chrome profile controlled through CDP; this is the least invasive available browser-automation fallback and provides DOM, storage, screenshot, console, network, viewport, click, reload, and keyboard evidence.

## 1. Executive summary

**VERIFIED IN BROWSER:** On a fresh launch with backend mode state `navigation` and no saved map, the application immediately renders the complete Overview shell, automatically attempts ROS at `ws://localhost:8765`, calls the FastAPI endpoints for maps/mode/stats, shows the ROS offline state, and opens a centered `Pilih Mode Operasi` dialog. The dialog offers `Mapping` and `Navigation`.

The current startup order is therefore:

```text
browser opens
  → application shell renders
  → ROS connection is attempted automatically
  → backend maps/mode/stats are requested
  → mode dialog appears when the backend is fresh/default
  → user chooses Mapping or Navigation
  → ROS URL is discovered in Overview, outside the startup dialog
```

The main UX friction is ordering and visibility: the user is asked to choose an operating mode before being shown the ROS target and before the UI verifies that ROS is reachable. The ROS URL field is technically already mounted behind the dialog, but it is not part of the first decision surface. A fresh user can choose Mapping while ROS is offline; Navigation is correctly prevented from starting when no map exists, but the same precondition is not applied to ROS connectivity.

**Recommendation:** evolve toward a unified startup dialog containing ROS target, separate Backend/ROS/Camera status, mode selection, and map selection when Navigation is chosen. Keep an explicit `Continue Offline` path for development and diagnostics. Do not require ROS connectivity merely to enter the shell; require it before executing ROS-dependent Mapping/Navigation commands.

## 2. Test environment

| Item | Evidence |
|---|---|
| Host | Linux workspace environment |
| Browser | Google Chrome 150.0.7871.114, headless |
| Automation | Chrome DevTools Protocol fallback; Playwright unavailable |
| Browser profile | Temporary clean profiles under `/tmp`, no project browser state |
| Viewports | 1440×900, 1366×768, 1920×1080 |
| Frontend | Vite dev server on `http://localhost:3000` |
| Backend | Uvicorn/FastAPI on `http://localhost:3001` |
| Backend audit data | Temporary SQLite/map paths under `/tmp`; repository DB was readonly |
| rosbridge | Not running; offline behavior intentionally tested |
| ROS/simulator | Not running; no movement or robot commands issued |
| Camera server | Not running and not exercised |

## 3. Git baseline

**VERIFIED IN TERMINAL** before the audit:

```text
pwd: /home/deden/Documents/my-project/ros2-software-amr
branch: main
HEAD: 3ddde28b668d646fed8f9e39188a9f1153e74a28
```

The worktree was already dirty outside the requested application scope. Existing modifications in Docker, ROS workspace, scripts, docs, and prior reports were preserved. There were no pre-existing changes under `web-ui/` or `backend/` at the start of the audit.

## 4. Services started

### Frontend

**VERIFIED FROM CODE/RUNTIME:** The repository helper is `bash scripts/start_dev.sh`; its frontend portion runs `cd web-ui && npm run dev`, which starts Vite on port 3000. The audit also started the same Vite command directly with `--host 0.0.0.0`.

The first sandbox attempt failed to bind ports with `EPERM`. With the required runtime permission, Vite started successfully and served `/` with HTTP 200.

### Backend

**VERIFIED FROM CODE/RUNTIME:** The repository helper normally runs `.venv/bin/uvicorn main:app --host 0.0.0.0 --port 3001 --reload`. That exact helper could not initialize the repository database because `data/amr.db` was readonly in the audit environment. A second, audit-only instance used the supported environment variables `DB_PATH`, `MAPS_DIR`, and `ROS_MAPS_PATH` pointing to `/tmp`.

Runtime checks for the isolated backend:

```text
GET /health       → 200 {"status":"ok"}
GET /api/mode     → 200 {"mode":"navigation","map_file":""}
GET /api/maps     → 200 []
```

### ROS

No rosbridge was started. This was intentional and allowed the offline startup flow to be observed without connecting to or commanding a robot.

### Build/static verification

**VERIFIED IN TERMINAL:** `npx vite build --outDir /tmp/amr-webui-startup-audit-dist --emptyOutDir=true` passed, transforming 3325 modules. It emitted existing warnings about Vite's CJS API, stale Browserslist data, package module type, and a large JavaScript chunk.

The normal `python3 -m py_compile` check could not write into the existing root-owned `backend/__pycache__` directory. A no-write `compile()` check passed for all 10 backend Python files. No source or generated application output under the repository was modified by these checks.

## 5. Browser configuration

Each browser run used a new temporary Chrome profile. Browser storage was inspected before application interaction.

**VERIFIED IN BROWSER:** Initial state:

```json
{
  "localStorage": {},
  "sessionStorage": {},
  "cookies": ""
}
```

The frontend itself supplies the default ROS URL when storage is empty. **VERIFIED FROM CODE** at `web-ui/src/App.vue:1037-1041`: `localStorage['amr_ros_url'] || 'ws://localhost:8765'`.

## 6. Initial localStorage state

**VERIFIED IN BROWSER:** A true fresh profile contained no `amr_ros_url`. After changing the URL in the Overview ROS control to `ws://localhost:8766` and pressing `Connect`, the browser contained:

```json
{
  "amr_ros_url": "ws://localhost:8766"
}
```

No session storage or cookie state was used.

## 7. First-load screenshot/evidence

The primary first-load screenshot is:

[01-first-load-1440x900.png](</home/deden/Documents/my-project/ros2-software-amr/docs/evidence/webui-startup-audit/01-first-load-1440x900.png>)

Additional evidence:

- [02-mapping-selected.png](</home/deden/Documents/my-project/ros2-software-amr/docs/evidence/webui-startup-audit/02-mapping-selected.png>)
- [03-navigation-no-map.png](</home/deden/Documents/my-project/ros2-software-amr/docs/evidence/webui-startup-audit/03-navigation-no-map.png>)
- [04-ros-custom-url-offline.png](</home/deden/Documents/my-project/ros2-software-amr/docs/evidence/webui-startup-audit/04-ros-custom-url-offline.png>)
- [05-backend-offline.png](</home/deden/Documents/my-project/ros2-software-amr/docs/evidence/webui-startup-audit/05-backend-offline.png>)
- [06-laptop-1366x768.png](</home/deden/Documents/my-project/ros2-software-amr/docs/evidence/webui-startup-audit/06-laptop-1366x768.png>)
- [07-desktop-1920x1080.png](</home/deden/Documents/my-project/ros2-software-amr/docs/evidence/webui-startup-audit/07-desktop-1920x1080.png>)

Raw compact interaction evidence:

- [targeted-flow.json](</home/deden/Documents/my-project/ros2-software-amr/docs/evidence/webui-startup-audit/targeted-flow.json>)
- [ros-control.json](</home/deden/Documents/my-project/ros2-software-amr/docs/evidence/webui-startup-audit/ros-control.json>)
- [backend-offline.json](</home/deden/Documents/my-project/ros2-software-amr/docs/evidence/webui-startup-audit/backend-offline.json>)

## 8. First-load actual sequence

**VERIFIED IN BROWSER and VERIFIED FROM CODE:**

```text
Browser GET http://localhost:3000/
  ↓
index.html loads /src/main.js
  ↓
main.js mounts App.vue with Pinia and global CSS
  ↓
App.vue renders the shell with activeTab = overview and appMode = navigation
  ↓
onMounted reads localStorage or defaults to ws://localhost:8765
  ↓
useROS.connect(savedUrl) creates a ROSLIB WebSocket
  ↓
App requests /api/maps, /api/mode, and /api/stats
  ↓
rosbridge refuses connection; header becomes OFFLINE
  ↓
MapView remains in “Waiting for map data / Subscribing to /map topic”
  ↓
backend returns navigation + empty map_file
  ↓
startup dialog opens: “Pilih Mode Operasi”
```

Implementation evidence: `web-ui/src/main.js:1-8`, `web-ui/src/App.vue:963-1052`, `web-ui/src/composables/useROS.js:145-173`, and `web-ui/src/composables/useSystemStats.js:13-27`.

## 9. Startup dialog behavior

**VERIFIED IN BROWSER:** The first-load dialog contains:

- title `Pilih Mode Operasi`;
- card `Mapping` — `Buat peta baru dengan SLAM`;
- card `Navigation` — `Navigasi dengan peta tersimpan`;
- `Mulai` button;
- `Close` control.

The dialog is visually modal and dims the Overview shell. The ROS URL input and `Connect` button are visible in the DOM and behind the dimmed surface, but they are not part of the startup decision. A user sees the mode choice first.

**VERIFIED FROM CODE:** `App.vue:547-628` defines this dialog. `App.vue:963-990` opens it when the backend returns no meaningful mode/map state or when the backend request fails during startup. `App.vue:1017-1034` sends the selected mode to `POST /api/mode/switch`.

The `Mulai` action was intentionally not submitted during this audit. It starts `scripts/docker_run.sh` through a backend background thread; that path first runs Docker orchestration `down`, so submitting it would have changed external simulator/container state. The pre-submit UX and all safe startup controls were tested.

## 10. Mapping startup journey

Evidence: [02-mapping-selected.png](</home/deden/Documents/my-project/ros2-software-amr/docs/evidence/webui-startup-audit/02-mapping-selected.png>).

**VERIFIED IN BROWSER:** Clicking the actual startup Mapping card selects it with the amber selected style. The `Mulai` button becomes enabled even though:

- ROS is visibly offline;
- the map is still waiting for `/map`;
- no ROS connection has been verified.

No ROS request or mode-switch request was sent because only the card was selected. **VERIFIED FROM CODE:** Mapping selection only sets `startupMode = 'mapping'` and clears the startup map file (`App.vue:560-571`). The submit path would POST `{mode:'slam'}` to `/api/mode/switch` (`App.vue:1017-1029`).

UX consequence: the user can reach an apparently ready `Mulai` action without knowing that the actual mapping runtime still needs rosbridge/ROS.

## 11. Navigation startup journey

Evidence: [03-navigation-no-map.png](</home/deden/Documents/my-project/ros2-software-amr/docs/evidence/webui-startup-audit/03-navigation-no-map.png>).

**VERIFIED IN BROWSER:** Selecting Navigation reveals `Pilih Map`. Because the backend returned `[]`, the dialog shows:

```text
Belum ada map tersimpan. Pilih Mapping untuk membuat peta dulu.
```

The `Mulai` button remains disabled. This is a clear and useful precondition check.

**VERIFIED FROM CODE:** `onStartupNavSelect()` refreshes `/api/maps` (`App.vue:1002-1014`); the template renders the empty-map warning at `App.vue:588-610`; `Mulai` is disabled when Navigation has no `startupMapFile` (`App.vue:613-618`).

Navigation therefore has a visible map prerequisite, but no equivalent visible ROS prerequisite at this stage.

## 12. ROS connection journey

Evidence: [04-ros-custom-url-offline.png](</home/deden/Documents/my-project/ros2-software-amr/docs/evidence/webui-startup-audit/04-ros-custom-url-offline.png>).

**VERIFIED IN BROWSER:** After closing the startup dialog, the user can find the Overview panel's `ROS CONNECTION` input. The audit changed it to the harmless unavailable URL `ws://localhost:8766` and clicked `Connect`.

Observed result:

- the input accepted the value;
- the browser attempted `ws://localhost:8766/`;
- the header remained `OFFLINE`;
- Overview showed `No robot connection` and `Enter WebSocket URL in Overview panel to connect`;
- no reconnect or alternate target dialog appeared.

**VERIFIED FROM CODE:** `App.vue:870-878` writes the store URL, persists `amr_ros_url`, and calls `ros.connect()`. `useROS.js:145-173` creates the ROSLIB socket, logs errors, marks the store disconnected on close, and has no automatic retry loop.

The connection control is discoverable only after the user knows to close/leave the startup mode surface and inspect Overview.

## 13. ROS URL persistence

**VERIFIED IN BROWSER:** After the custom URL was entered and Connect was pressed:

```text
localStorage['amr_ros_url'] = 'ws://localhost:8766'
```

**VERIFIED FROM CODE:** Persistence is explicit in `App.vue:874-876`; there is no Pinia persistence plugin. This is browser-local persistence, not backend persistence.

## 14. Reload behavior

**VERIFIED IN BROWSER:** A reload in the same clean browser context:

- restored the input value `ws://localhost:8766`;
- automatically attempted `ws://localhost:8766/` again;
- kept the ROS state offline when the port was unavailable;
- showed the startup dialog again because backend mode remained default Navigation with no map.

This distinguishes two independent persistence rules:

```text
ROS target → localStorage and automatic reconnect
mode/map startup readiness → backend settings/map state
```

There was no saved map or successful mode start in this audit, so the “previously configured Navigation with a map” path was **NOT VERIFIED IN BROWSER**. Its direct-apply behavior is **VERIFIED FROM CODE** at `App.vue:984-1000`.

## 15. ROS-offline behavior

**VERIFIED IN BROWSER:** With rosbridge unavailable:

- header status displayed `OFFLINE`;
- pose remained `0.00, 0.00, 0.0°`;
- navigation and docking badges stayed `IDLE`;
- map showed `Waiting for map data` and `Subscribing to /map topic`;
- Overview showed `No robot connection`;
- camera was not exercised because no ROS/video service was running;
- the map toolbar and stop control remained visible;
- no retry countdown or reconnect button appeared beyond the normal `Connect` control.

The UI distinguishes ROS offline in the header, but it does not explain whether the FastAPI backend is healthy in the same surface.

## 16. Backend-offline behavior

Evidence: [05-backend-offline.png](</home/deden/Documents/my-project/ros2-software-amr/docs/evidence/webui-startup-audit/05-backend-offline.png>).

**VERIFIED IN BROWSER:** With Vite running and FastAPI unavailable:

- the frontend shell still rendered;
- `/api/maps`, `/api/mode`, and `/api/stats` failed with `ERR_CONNECTION_REFUSED`;
- ROS still attempted `ws://localhost:8765/` and failed independently;
- the startup dialog still appeared;
- the map remained in its waiting state;
- system stats remained `—`;
- no explicit `Backend offline` label was shown.

This is a meaningful ambiguity: a user sees a generic ROS `OFFLINE` experience even though the backend is also down. The startup dialog can still offer Mapping/Navigation, but backend-dependent continuation cannot succeed reliably.

## 17. Console findings

**VERIFIED IN BROWSER:** Expected offline errors:

```text
WebSocket connection to 'ws://localhost:8765/' failed: net::ERR_CONNECTION_REFUSED
[ROS] WebSocket Error!
[ROS] Connection Closed
```

When FastAPI was offline, browser console output also included:

```text
[App] Could not fetch maps: Failed to fetch
Failed to load resource: net::ERR_CONNECTION_REFUSED
```

Observed non-offline warnings:

- Vue warning: extraneous `closeable` attribute passed through `DialogContent`/Teleport;
- warning: DialogContent missing `Description` or `aria-describedby`;
- Vite development warning about the CJS API;
- Vite warning that `postcss.config.js` is reparsed as an ES module because package module type is unspecified.

The ROS errors are expected under the test condition. The Vue accessibility/dialog warnings are implementation findings, not caused by the offline environment.

## 18. Network findings

**VERIFIED IN BROWSER:** Normal first load requested:

```text
GET http://localhost:3001/api/maps
GET http://localhost:3001/api/mode
GET http://localhost:3001/api/maps       # startup refresh
GET http://localhost:3001/api/stats
GET http://localhost:3000/agv-icon.svg
WebSocket ws://localhost:8765/
```

`/api/stats` was requested immediately and then again through the five-second polling loop when the session lasted long enough. The browser also opened Vite's development WebSocket; that is tooling HMR, not the ROS transport.

After the custom URL was entered, the ROS attempt changed to:

```text
WebSocket ws://localhost:8766/
```

No frontend `POST /api/mode/switch` was recorded because the potentially destructive orchestration action was deliberately not submitted.

## 19. Multi-PC scenario

Target topology:

```text
Computer A: browser/Web UI :3000 + FastAPI :3001
Computer B: rosbridge :8765 + ROS 2 + simulator + web_video_server :8080
```

**VERIFIED FROM CODE / INFERRED:** The user can enter a remote ROS URL such as `ws://192.168.1.50:8765` in the Overview control, and that URL is persisted in localStorage. The FastAPI target remains hard-coded to `http://localhost:3001` in `useAPI.js:16-18`, so backend and browser must remain co-located or use forwarding/proxying.

The current multi-PC steps are:

1. Open the Web UI.
2. Encounter the mode dialog.
3. Close or otherwise leave the mode surface.
4. Navigate/recognize Overview.
5. Replace the ROS WebSocket URL.
6. Press Connect.
7. Inspect the header and map for offline/telemetry feedback.

The target location is not obvious at first launch, and there is no explicit connection test result other than the global status. The camera implementation is separately tied to the ROS URL hostname in `MapView.vue` by source inspection, so it should follow the selected ROS host, but this was **NOT VERIFIED IN BROWSER** without a video server.

## 20. Desktop/laptop layout observations

Evidence:

- [06-laptop-1366x768.png](</home/deden/Documents/my-project/ros2-software-amr/docs/evidence/webui-startup-audit/06-laptop-1366x768.png>)
- [07-desktop-1920x1080.png](</home/deden/Documents/my-project/ros2-software-amr/docs/evidence/webui-startup-audit/07-desktop-1920x1080.png>)

**VERIFIED IN BROWSER:** At 1366×768, the startup dialog remained centered and readable, and the two mode cards fit side-by-side. At 1440×900 and 1920×1080 it remained centered with substantial dimmed shell visible behind it. No clipping or horizontal overflow was observed in this focused startup check.

The screenshot evidence is from headless Chrome, so physical display color/contrast calibration was not assessed. The primary robot-control layout remains desktop-oriented, matching the intended usage.

## 21. Current-flow strengths

**VERIFIED IN BROWSER:**

- The fresh-install mode dialog is visually prominent and uses plain labels: Mapping versus Navigation.
- Mapping and Navigation are visually distinct selectable cards.
- Navigation without maps is blocked with a direct Indonesian explanation.
- The Overview clearly shows `OFFLINE`, `No robot connection`, and the default URL.
- A remote ROS URL can be entered without changing application source or backend configuration.
- The ROS URL persists across reload and is automatically retried.
- The shell still renders when ROS or backend is unavailable, which is useful for diagnostics.

## 22. Current-flow friction/confusion

**VERIFIED IN BROWSER:**

- ROS target selection is not in the first startup dialog.
- ROS connection is attempted before the user has seen or confirmed the target.
- The URL input is behind the modal and only becomes a practical control after leaving the startup dialog.
- Mapping can be selected and its `Mulai` action enabled while ROS is offline.
- Navigation has a visible map prerequisite but no visible ROS prerequisite.
- Backend offline and ROS offline are not separately represented in the startup experience.
- `Close` allows the user to leave the startup dialog without selecting a mode, so mode selection is not actually mandatory.
- A mode choice is conceptually coupled to backend/docker orchestration, but the user surface does not explain that runtime transition.
- The same screen exposes top-level header Mapping/Navigation toggles; a generic user can confuse those with the startup cards.
- Console warnings indicate dialog accessibility metadata is incomplete.

## 23. Current flow diagram

```text
Fresh browser
  ↓
App.vue shell renders Overview + MapView
  ↓
localStorage URL or ws://localhost:8765
  ↓
ROSLIB WebSocket attempt ----------------------┐
  ↓                                            │
OFFLINE / no robot connection                  │
                                               │
FastAPI GET /api/maps, /api/mode, /api/stats  │
  ↓                                            │
navigation + empty map                         │
  ↓                                            │
Pilih Mode Operasi dialog                      │
  ├── Mapping → Mulai enabled even if ROS off  │
  └── Navigation → map required; no map blocks │
  ↓                                            │
user closes dialog / enters shell              │
  ↓                                            │
Overview ROS URL field                          │
  ↓                                            │
edit URL → Connect → localStorage + ROS retry ┘
```

## 24. Alternative flow A — current model

```text
Mode
  → shell / Overview
  → discover ROS connection
  → edit target
  → Connect
```

**Advantages:** minimal change to the current implementation; allows the UI shell to appear while robot infrastructure is unavailable; preserves the existing offline debugging capability.

**Disadvantages observed:** mode decision precedes connection context; Mapping can look actionable while ROS is offline; the remote target is hidden from the initial surface; backend and ROS health are conflated.

## 25. Alternative flow B — connection first

```text
ROS URL
  → connect/test
  → choose mode
  → shell
```

**Advantages:** establishes the most important external dependency before asking the user to choose a robot operating mode; better for a physical robot or teammate simulator.

**Disadvantages:** can make a disconnected UI inaccessible exactly when a developer needs to configure or inspect it; may imply that every shell feature requires live ROS; it still needs a map choice for Navigation and a backend status.

## 26. Alternative flow C — unified startup dialog

```text
┌─────────────────────────────────────┐
│ ROS Connection                      │
│ [ ws://192.168.1.50:8765 ]          │
│ Backend  ●   ROS Bridge  ●  Camera ●│
│ [Connect/Test]                       │
│                                     │
│ Operating Mode                       │
│ [ Mapping ] [ Navigation ]           │
│ Navigation map: [select map]         │
│                                     │
│ [Continue]       [Continue Offline]  │
└─────────────────────────────────────┘
```

**Advantages:** puts target, health, mode, and Navigation map prerequisites in one mental model; directly supports local simulator, teammate simulator, and physical robot; preserves an explicit offline choice instead of making offline behavior accidental.

**Disadvantages:** more information on first launch; needs careful rules for what `Continue` means when ROS is unreachable; separate Backend/ROS/Camera statuses can overwhelm users if shown with too much technical detail.

## 27. Comparison and tradeoffs

| Criterion | A: current | B: connection first | C: unified dialog |
|---|---|---|---|
| Remote ROS target discoverability | Weak | Strong | Strong |
| Offline diagnostics | Strong shell access | Risk of blocking | Strong with explicit offline action |
| Map prerequisite visibility | Strong for Navigation | Strong | Strong |
| Backend health visibility | Weak | Needs addition | Natural fit |
| Physical robot safety/context | Weak | Strong | Strong |
| Implementation disruption | None | Medium | Medium |
| First-launch cognitive load | Mode first, connection hidden | Connection first | All key decisions together |

## 28. Recommended startup flow

Recommend **Option C: unified startup dialog**, with these rules:

1. Pre-fill the saved ROS URL, defaulting to `ws://localhost:8765` only when none exists.
2. Show Backend, ROS Bridge, and Camera as compact independent statuses.
3. Allow `Connect/Test` without leaving the dialog.
4. Let the user choose Mapping or Navigation in the same dialog.
5. When Navigation is selected, require a saved map before enabling normal Continue.
6. Do not require ROS connectivity merely to enter the shell; offer `Continue Offline` explicitly.
7. If Mapping is selected while ROS is offline, allow offline entry/configuration but do not imply that SLAM has started. The mapping action should explain that ROS is required.
8. Keep ROS target editable after entering the shell.
9. Confirm target changes if live telemetry is active because changing the target resets live state and can point the UI at a different robot.
10. Continue deriving the camera host from the selected ROS host only if the camera endpoint is known to be colocated; show camera status separately.

This recommendation is based on the observed hidden-target problem, the successful existing offline shell, and the clear Navigation map validation. It is not an implementation in this session.

## 29. Answers to the 12 product questions

1. **Should ROS URL configuration appear before entering the application?**  Yes, at least in the unified startup surface. It is the primary multi-PC dependency and currently appears too late.
2. **Should ROS URL and Mapping/Navigation be in the same dialog?**  Yes. Option C best matches the observed need without removing offline access.
3. **Should Continue require ROS connected?**  No for entering the shell; yes for starting ROS-dependent Mapping/Navigation execution. Use explicit state text rather than silently enabling an action.
4. **Should there be Continue Offline?**  Yes. The current shell renders usefully offline, so preserve that capability intentionally.
5. **Navigation selected but no map?**  Keep the current behavior: show the map prerequisite and disable normal Continue until a map is selected.
6. **Mapping selected but ROS disconnected?**  Allow offline configuration/diagnostics, but clearly mark Mapping as not started and block/guard the actual SLAM start until ROS is connected.
7. **Should saved ROS URL auto-reconnect?**  Yes, preferably with a visible reconnect attempt/result. The current automatic retry-on-reload behavior is useful.
8. **Should the target remain editable in-app?**  Yes, because multi-PC and target-switching are real workflows.
9. **Should changing target require confirmation?**  Yes when currently connected or telemetry is active; it can reset state and change which robot the operator sees.
10. **Should camera host derive from selected ROS host?**  Yes if the deployment contract keeps web_video_server on the ROS computer; keep it configurable or show a clear camera endpoint when that assumption does not hold.
11. **Separate Backend/ROS/Camera status?**  Yes, but compactly. The backend-offline evidence shows why one generic `OFFLINE` indicator is insufficient.
12. **Simplest flow for local simulator, teammate simulator, physical robot?**  Unified dialog: saved/pre-filled ROS target → test/connect → mode → map if Navigation → Continue or Continue Offline; retain in-app target editing with confirmation.

## 30. Suggested implementation scope — DO NOT IMPLEMENT

Future implementation work should be planned separately and may include:

- move or mirror the ROS connection control into the startup dialog;
- expose independent Backend/ROS/Camera health state;
- make startup action semantics explicit (`Continue`, `Start Mapping`, `Continue Offline`);
- preserve the current URL persistence and auto-reconnect behavior;
- keep the Navigation map prerequisite;
- define safe behavior for Mapping with no ROS;
- add target-change confirmation when connected;
- make camera-host derivation/configuration explicit for LAN deployments;
- add focused browser tests for fresh load, no map, backend offline, ROS offline, saved URL, and remote ROS URL.

No item in this section was implemented.

## 31. Files created/changed

Created by this audit:

- [WEB_UI_STARTUP_PLAYWRIGHT_UX_AUDIT.md](</home/deden/Documents/my-project/ros2-software-amr/WEB_UI_STARTUP_PLAYWRIGHT_UX_AUDIT.md>)
- `docs/evidence/webui-startup-audit/01-first-load-1440x900.png`
- `docs/evidence/webui-startup-audit/02-mapping-selected.png`
- `docs/evidence/webui-startup-audit/03-navigation-no-map.png`
- `docs/evidence/webui-startup-audit/04-ros-custom-url-offline.png`
- `docs/evidence/webui-startup-audit/05-backend-offline.png`
- `docs/evidence/webui-startup-audit/06-laptop-1366x768.png`
- `docs/evidence/webui-startup-audit/07-desktop-1920x1080.png`
- three compact JSON evidence files in the same directory.

Application source files under `web-ui/` and `backend/` were not modified. No dependency, package metadata, API contract, ROS interface, CSS, or runtime behavior was changed. No commit, push, reset, clean, stash, or branch switch was performed.

## 32. Final recommendation

The current application does ask a first-time user to choose Mapping or Navigation, but that choice is presented before the user is given a clear ROS connection context. The flow works acceptably for a local, already-configured developer who knows to use Overview, but it is not coherent enough for a multi-PC robot operator.

Adopt a unified startup flow that shows ROS target and independent service status together with mode selection, keeps Navigation map validation, and provides an explicit Continue Offline path. Do not make ROS connectivity a hard gate for viewing the shell; make it a clear gate for starting robot-dependent operations.
