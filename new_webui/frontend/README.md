# AMR Frontend

Fleet control and monitoring interface for the AMR stack. Vue 3 + Vite + TypeScript.

It replaced the old `web-ui/` application, which has been removed from this repository.
The user manual is [`docs/Panduan_AMR_Web_UI.pdf`](../../docs/Panduan_AMR_Web_UI.pdf).

---

## Quick start

```bash
cd new_webui/frontend
npm install
cp .env.example .env     # adjust the backend and bridge URLs
npm run dev              # http://localhost:3100
```

Port 3100, so this runs alongside the existing UI on 3000.

| Command | Does |
|---|---|
| `npm run dev` | Dev server with HMR |
| `npm run build` | Typecheck, then production build |
| `npm run typecheck` | `vue-tsc` only |
| `npm test` | Unit tests (Vitest) |
| `npm run lint` | ESLint with `--fix` |
| `npm run format` | Prettier |

## Configuration

All runtime configuration is environment-driven — see `.env.example`.

`VITE_API_BASE_URL` matters: the old UI hardcoded `http://localhost:3001/api` in two
places while making only the ROS URL configurable, so any deployment where the backend
was not on the operator's own machine silently failed.

Per-robot bridge URLs live in the robot registry (System › Robots), not in `.env`.
`VITE_DEFAULT_ROS_URL` only seeds the first robot on a fresh install.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Framework | Vue 3 + Vite | Audit section 8: no operator-visible benefit from React or Next.js, and Next.js would put a resident Node process on a robot-adjacent machine |
| Language | TypeScript | Four of the data-loss defects in the audit are type errors at the browser ↔ REST ↔ ROS boundary |
| Routing | vue-router | Deep links, browser back, refresh-safe screens. The old app kept the active screen in a local `ref` |
| State | Pinia | Per-robot store factory, not one global singleton |
| Styling | Tailwind 3 + CSS custom properties | Both light and dark themes are real |
| Primitives | reka-ui (shadcn-vue) | Already the old project's base; the gap was adoption, not capability |
| Map | Leaflet | `CRS.Simple`. Installed, not yet wired |
| Charts | uPlot | ~45 KB, replacing ECharts (~1 MB for two line charts). Installed, not yet wired |
| ROS | roslibjs over rosbridge | Installed, not yet wired |

## Layout

```
src/
├── app/            shell: router, config, layouts
├── domain/         framework-free logic and types — unit tested, no Vue imports
│   ├── ros/        topics, TF, URDF, quaternions, status vocabulary
│   └── types/      robot, mission, station, map
├── features/       one folder per workspace
├── shared/         ui primitives, shared components, api client, utils
└── stores/         fleet (registry), robot (per-robot telemetry), ui (preferences)
```

`domain/` imports nothing from Vue. That is what makes the TF chain, the URDF parser and
the status rules testable without a browser — in the old project they were buried in a
1,245-line composable behind module-level mutable state.

`domain/ros/topics.ts` holds every ROS name in one place. Moving the fleet to namespaced
topics is an edit to that file, not a grep through the codebase.

## What works today

- Routing, layouts and navigation across all three contexts (fleet, robot, system)
- Robot registry with add/remove, persisted, accent colours assigned per robot
- `RobotContextBar`: identity, connection, mode, activity, staleness, battery, E-STOP
- Design tokens, status vocabulary, shared components
- `domain/` logic with 28 passing tests

## What is deliberately not wired

**There is no ROS connection yet.** Telemetry is empty and the E-STOP refuses with a stated
reason rather than reporting a stop that did not happen. The ROS client, reconnect with
backoff, and staleness detection are roadmap phase 1.

Workspaces that are not built render a placeholder naming the audit section and roadmap
phase that covers them.

## Conventions

- **Never report success for an action that did not happen.** If a command cannot be sent,
  say why. The old UI's mode switch and E-STOP both violated this.
- **Every destructive action goes through `ConfirmDialog`,** and the message names the robot
  or object rather than saying "this item".
- **Check `canCommand` before sending anything.** The old store computed the equivalent and
  used it only to render a badge.
- **Raw ROS message payloads never go in a Pinia `ref`.** An OccupancyGrid's data array is
  millions of entries and Vue would deep-proxy every one. Use `shallowRef` in the layer
  that owns the rendering.
- **10px is the minimum font size** (`text-label`). Operators read this standing up.
- **Status colour always carries a shape or icon too.**
