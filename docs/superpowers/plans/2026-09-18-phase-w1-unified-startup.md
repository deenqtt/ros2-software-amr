# Phase W1 Unified Startup Connection Implementation Plan

> **For agentic workers:** Execute this plan inline with verification checkpoints. No commit is permitted for this task.

**Goal:** Replace the first-run mode-only dialog with a unified startup surface that exposes the shared ROS target, Backend/ROS/Camera status, mode prerequisites, and explicit offline entry.

**Architecture:** Keep `App.vue` as the startup/shell owner, keep `useROS.js` as the only ROSLIB WebSocket client, and use the existing Pinia robot state plus one `rosUrl` binding shared by startup and Overview. Use the existing `/health` endpoint for backend status and do not change `/api/mode/switch` or any ROS interface.

**Tech Stack:** Vue 3 Composition API, Pinia, native fetch, ROSLIB, existing local UI primitives, Chrome CDP for browser E2E, Vite build.

## Global Constraints

- Work only in `/home/deden/Documents/my-project/ros2-software-amr`.
- Application behavior changes are limited to startup connection/mode UX.
- Preserve `amr_ros_url`, ROS topic/service/action names, schemas, mode orchestration, Mission, Docking, simulator, and storage schemas.
- `Continue Offline` must not call `/api/mode/switch`, Docker, or ROS commands.
- Do not install dependencies or run destructive Docker orchestration.
- Validate with isolated Vite build, no-write backend validation, and clean Chrome CDP E2E.

## Files and responsibilities

- Modify `web-ui/src/App.vue`: unified dialog, startup state, health polling/request, eligibility, offline entry, target-change confirmation.
- Modify `web-ui/src/composables/useROS.js` only if the existing disconnect/reconnect state needs a minimal shared status/reset hook; do not add a second client.
- Modify `web-ui/src/stores/robot.js` only if a minimal shared connection status field is required; prefer existing `rosConnected`/`rosUrl`.
- Create `docs/evidence/webui-phase-w1/`: concise screenshots and JSON browser evidence.
- Create `PHASE_W1_UNIFIED_STARTUP_CONNECTION_REPORT.md`: implementation and validation report.
- Do not modify backend source unless a safe existing endpoint is unusable; `/health` already exists.

## Task 1: Establish a failing browser contract

- [ ] Create a temporary CDP probe outside the repository that loads the current application with a clean profile and asserts the W1 contract: startup dialog exposes a ROS URL, status labels, `Continue Offline`, and no hidden URL-only Overview requirement.
- [ ] Run the probe against the current implementation and record the expected failure before production code changes.
- [ ] Keep the probe outside the repository unless it is needed as a reusable evidence script.

## Task 2: Implement shared startup connection state

- [ ] Reuse `localStorage['amr_ros_url'] || 'ws://localhost:8765'` as the single initial target.
- [ ] Keep the existing `rosUrl` binding synchronized with `store.rosUrl` and the Overview input.
- [ ] Add only small derived state for startup connection status and backend health; use ROS store events rather than a new WebSocket.
- [ ] Add lightweight URL validation using `new URL()` and permit only `ws:` or `wss:`.
- [ ] Request `GET /health` safely on startup and expose checking/online/offline without crashing when unavailable.
- [ ] Preserve automatic connection attempt and existing ROSLIB callbacks.

## Task 3: Replace the startup surface

- [ ] Evolve the existing startup dialog markup, not the entire UI system.
- [ ] Show ROS URL/input, Connect/Reconnect, ROS status, Backend status, Camera `—`/Not checked, Mapping, Navigation, and conditional map selection.
- [ ] Keep the existing Navigation empty-map wording and refresh behavior.
- [ ] Add Mapping offline explanation when ROS is disconnected.
- [ ] Remove silent generic startup bypass; provide explicit `Continue Offline` instead.
- [ ] Add a DialogDescription and remove the unsupported `closeable` attribute from this dialog only, if that resolves the observed warnings safely.

## Task 4: Apply continuation safety rules

- [ ] Enable normal Continue only for Mapping + ROS connected or Navigation + ROS connected + selected map.
- [ ] Make Continue call the existing `confirmStartup()` and therefore preserve existing `/api/mode/switch` semantics; do not invoke it during offline entry.
- [ ] Make Continue Offline set a shell-only state, close the dialog, preserve honest disconnected status, and avoid mode orchestration or ROS commands.
- [ ] Prevent the shell from falsely claiming that offline Mapping/Navigation runtime has started.

## Task 5: Protect in-app target changes

- [ ] Keep Overview ROS input and startup input bound to the same target.
- [ ] When connected and the entered target differs, show a confirmation explaining telemetry/state will reconnect/reset.
- [ ] On confirmation, reuse `ros.disconnect()`/`ros.connect()` and existing close reset behavior; do not change ROS contracts or store architecture.
- [ ] Do not confirm when disconnected or when the target is unchanged.

## Task 6: Validate and document

- [ ] Re-run the failing CDP contract probe after implementation and require it to pass.
- [ ] Run fresh-profile scenarios: first load ROS offline, custom URL, reload persistence, Mapping offline, Navigation no map, Continue Offline, backend offline, and target-change confirmation where runtime permits.
- [ ] Capture required screenshots and compact JSON under `docs/evidence/webui-phase-w1/`.
- [ ] Run `npx vite build --outDir /tmp/amr-webui-phase-w1-dist --emptyOutDir=true`.
- [ ] Run no-write compile/import validation for backend files.
- [ ] Check that no `/api/mode/switch` request occurs from Continue Offline and no movement/mission/docking ROS command is issued.
- [ ] Write `PHASE_W1_UNIFIED_STARTUP_CONNECTION_REPORT.md` with evidence labels and a PASS/BLOCKED gate matrix.
- [ ] Run final git/status/diff checks and leave the repository uncommitted.
