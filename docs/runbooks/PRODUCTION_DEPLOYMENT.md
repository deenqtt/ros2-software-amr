# Production deployment: server + robots

The web UI and its backend run on a **server**; each robot runs its stack and
the **robot agent** on its own **Jetson**. They are different machines on a
network that will drop. This runbook covers the layout, the ports between
them, how to install each side, and what keeps working when the link is down.

## Layout

```
   Operator browser
        │  http(s)://amr.example.local          (one origin)
        ▼
 ┌──────────────── Server ─────────────────┐
 │ nginx                                    │
 │  /            → frontend dist/ (static)  │
 │  /backend/    → FastAPI 127.0.0.1:3002   │──── SQLite amr.db + map files
 │  /robot/<n>   → ws://<jetson>:9090 (opt.)│
 └──────────────────────────────────────────┘
        ▲ HTTP poll every 10 s (robot → server)
        │
 ┌──────────────── Jetson (each robot) ─────┐
 │ robot_agent  (amr_agent/, systemd)       │  ~/map_cache/   cached maps
 │ Nav2 / SLAM  (started by the agent)      │  ~/amr_agent/state/  offline memory
 │ rosbridge :9090                          │
 └──────────────────────────────────────────┘
```

The server never calls a robot. Robots poll the server, so a robot behind NAT
or on a roaming wifi client still works. The browser does talk to each robot's
rosbridge (live map, laser, goals, teleop) — directly, or through nginx.

## Ports

| From | To | Port | What |
|---|---|---|---|
| Browser | Server | 80/443 | UI and `/backend/` API (nginx) |
| Robot (agent) | Server | 80/443 (`/backend`) or 3002 | registry, maps, stations, runs |
| Browser | Robot | 9090 | rosbridge, **unless** proxied through nginx `/robot/<n>` |

Nothing needs to reach the robot except rosbridge, and with the nginx proxy not
even that from the operators' network — only from the server.

## Server

1. **Backend** (`new_webui/backend`):

   ```bash
   python3 -m venv .venv && ./.venv/bin/pip install -e .
   cp .env.example .env    # then set the production block at the bottom:
                           #   AMR_ENV=production
                           #   AMR_HOST=127.0.0.1
                           #   AMR_CORS_ORIGINS=http://amr.example.local
   ./.venv/bin/python -m app        # no --reload in production
   ```

   Migrations run on start-up. Back up `data/amr.db` and `data/maps/` — they
   are the registry every robot follows.

   As a service, `/etc/systemd/system/amr-backend.service`:

   ```ini
   [Unit]
   Description=AMR web backend
   After=network-online.target

   [Service]
   WorkingDirectory=/opt/amr/backend
   ExecStart=/opt/amr/backend/.venv/bin/python -m app
   Restart=always
   User=amr

   [Install]
   WantedBy=multi-user.target
   ```

2. **Frontend** (`new_webui/frontend`):

   ```bash
   cp .env.production.example .env.production   # relative /backend URLs
   npm ci && npm run build                      # → dist/
   rsync -a dist/ /opt/amr/web/dist/
   ```

3. **nginx**: start from `new_webui/deploy/nginx.conf.example`. One
   `/robot/<name>` block per robot if browsers should not reach Jetsons
   directly; the robot's `bridge_url` in the registry is then
   `ws(s)://amr.example.local/robot/<name>`.

## Robot (Jetson)

1. **Agent files.** From a checkout:

   ```bash
   ssh user@jetson 'mkdir -p ~/amr_agent'
   scp amr_agent/*.py amr_agent/*.sh user@jetson:~/amr_agent/
   ```

   `amr_agent/` in this repository is the source. Copy the named files only:
   the robot's runtime state in `~/amr_agent/state/` must never be overwritten.

2. **rosbridge** on 9090 (the agent's launches are run with
   `launch_websocket:=false`, so it is started separately):

   ```bash
   ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=9090
   ```

3. **Agent as a service**, `/etc/systemd/system/amr-agent.service`:

   ```ini
   [Unit]
   Description=AMR robot agent
   After=network-online.target

   [Service]
   User=robot
   Environment=ROS_DOMAIN_ID=10
   ExecStart=/home/robot/amr_agent/run_agent_gprp.sh <robot-id> http://amr.example.local/backend
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

   `<robot-id>` is the id the web UI shows for the robot after it is added.
   `run_agent_gprp.sh` is set up for the Isaac Sim stack (`*_sim_launch.py`,
   `use_sim_time:=true`); a physical robot needs its own launch packages and
   `use_sim_time_arg:=false`.

## When the server cannot be reached

The registry lives on the server; each robot keeps what it needs to carry on.

| Situation | What happens |
|---|---|
| Robot boots while the server is down | Starts from its last saved registry reading (`state/registry.json`): same mode, same map, from `~/map_cache` — **only if the cached map still matches its recorded hash**. Station poses come from `state/stations_<map>.json`. |
| Link drops during a mission | The mission continues. Progress, arrivals and the final result are written to `state/outbox.json` and sent, in order, when the server is back. `pending_reports` in `/robot_mode_status` says how many are waiting. |
| Link comes back | Waiting reports go first; only then does the robot ask for new work. |
| A finished run still looks live on the server (its "done" never arrived) | The robot remembers every run it ended (`state/finished_runs.json`) and re-sends the result instead of driving the route again. |
| Operator cancels while the robot is offline | The robot cannot hear it until the link is back. Use the robot's own stop (or E-STOP) for anything urgent. |
| Server answers 404 for the robot | Treated as "not registered", not as an outage: the robot does **not** run from its snapshot. |

What does *not* work offline: starting new missions, editing maps, stations or
missions, and anything in the browser that goes through the server.

## Not done yet

- **No authentication** on the backend or on rosbridge. Keep both on a trusted
  network or VPN; put nginx in front with TLS and, at minimum, HTTP basic auth
  until real accounts exist.
- `confirm` steps are not waited on in `mission_via=nav` mode (see
  `kiosk-mockup/README.md`).

## Checklist

- [ ] Backend `.env`: `AMR_ENV=production`, explicit `AMR_CORS_ORIGINS`
- [ ] Frontend built with `.env.production`
- [ ] nginx serves `/` and proxies `/backend/` (and `/robot/<n>` if used)
- [ ] Each robot: agent deployed, rosbridge on 9090, `amr-agent` service enabled
- [ ] Each robot registered in the UI with the right `bridge_url`, map assigned
- [ ] Pull the server's network once with a robot mid-mission: it should finish
      the mission, and the run should show done when the network is back
- [ ] Back-ups of `data/amr.db` and `data/maps/`
