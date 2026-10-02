# AMR Control

Web control for a fleet of ROS 2 AMRs: a web UI and its backend on a server,
an agent on each robot, and a kiosk screen for the robot's display.

```
new_webui/      Web UI (Vue 3 + Vite) and backend (FastAPI + SQLite)
amr_agent/      Robot agent: runs on each robot, follows the backend's registry
kiosk-mockup/   Static mockup of the robot's on-board screen
docs/           User manual (PDF), deployment runbook, ROS interface contract
DESIGN.md       Design system the web UI follows
```

## Run the web UI locally

```bash
# backend → http://localhost:3002
cd new_webui/backend
python3 -m venv .venv && ./.venv/bin/pip install -e ".[dev]"
cp .env.example .env
./.venv/bin/python -m app --reload

# frontend → http://localhost:3100
cd new_webui/frontend
npm install
cp .env.example .env
npm run dev
```

## Run the agent on a robot

Copy `amr_agent/` to the robot (`~/amr_agent`), start rosbridge on port 9090,
then:

```bash
~/amr_agent/run_agent_gprp.sh <robot-id> http://<server>:3002
```

`<robot-id>` is the id the web UI shows once the robot is added under **Robot**.

## Kiosk

Open `kiosk-mockup/index.html` in a browser. Press `D` for the simulation panel.

## Documentation

- [docs/Panduan_AMR_Web_UI.pdf](docs/Panduan_AMR_Web_UI.pdf) — user manual
- [docs/runbooks/PRODUCTION_DEPLOYMENT.md](docs/runbooks/PRODUCTION_DEPLOYMENT.md) — server + robot deployment
