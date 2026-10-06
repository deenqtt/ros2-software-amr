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
 │  /backend/api/robots/<id>/ros  (WS relay)│
 └──────────────────────────────────────────┘
        │ ws://<jetson>:9090   ▲ HTTP poll every 10 s + bearer token
        ▼ (relay, server → robot)│ (robot → server)
 ┌──────────────── Jetson (each robot) ─────┐
 │ robot_agent  (amr_agent/, systemd)       │  ~/map_cache/   cached maps
 │ Nav2 / SLAM  (started by the agent)      │  ~/amr_agent/state/  offline memory
 │ rosbridge :9090                          │
 └──────────────────────────────────────────┘
```

Browsers talk to the server only. Live data (map, laser, pose) and commands
(goals, teleop) go over a WebSocket to `/backend/api/robots/<id>/ros`, on the
same origin and with the session cookie. The backend checks the sign-in and the
`Origin`, connects to the robot's registered `bridge_url` (`ws://<jetson>:9090`)
and forwards only allow-listed telemetry and role-checked commands:

- **viewer**: telemetry, and stop-class commands only (zero teleop, cancel
  goal, `/robot_mode` stop);
- **operator** and above: also goals, initial pose, teleop, start mapping, save
  map.

Missions, maps and registry still work the other way round: robots **poll** the
server over HTTP and send their reports, each with its own **agent token**, so a
robot behind NAT or on a roaming wifi client still works for those. The live
view needs the server to reach the robot's 9090.

rosbridge has no authentication of its own, so nothing but the server may
reach it (see Ports). There is no `/robot/<n>` nginx proxy any more: it handed
rosbridge to anyone who could load the page.

## Ports

| From | To | Port | What |
|---|---|---|---|
| Browser | Server | 80/443 | UI, `/backend/` API and the `/backend/api/robots/<id>/ros` WebSocket (nginx) |
| Robot (agent) | Server | 80/443 (`/backend`) or 3002 | registry, maps, stations, runs (HTTP, bearer token) |
| Server | Robot | 9090 | rosbridge, for the relay only |

Browsers never need to reach a robot, and must not be able to: **firewall each
robot's port 9090 so that only the server can connect.** This is a manual step
on every robot, for example:

```bash
sudo ufw allow from <server-ip> to any port 9090 proto tcp
sudo ufw deny 9090/tcp
```

Nothing else needs to reach the robot. If the server cannot reach a robot's
9090 the live view for that robot stays empty; missions still run.

## Server with Docker (recommended)

Two images, built by `.github/workflows/webui.yml` for **amd64 and arm64**, so
the same steps work on a PC server and on a **Raspberry Pi 4/5 with a 64-bit
OS** (32-bit Raspberry Pi OS is not supported):

| Image | |
|---|---|
| `ghcr.io/deenqtt/amr-backend` | FastAPI backend, SQLite, migrations on start-up |
| `ghcr.io/deenqtt/amr-web` | nginx serving the built UI, proxying `/backend/` to the backend |

Tags: `latest` and `1.2.0` from a git tag `v1.2.0`; `main` and `sha-<short>`
from every push to main. Run a release tag in production.

```bash
sudo mkdir -p /opt/amr && sudo chown "$USER" /opt/amr && cd /opt/amr
curl -fsSLO https://raw.githubusercontent.com/deenqtt/ros2-software-amr/main/new_webui/deploy/docker-compose.yml
curl -fsSL -o .env https://raw.githubusercontent.com/deenqtt/ros2-software-amr/main/new_webui/deploy/.env.example
nano .env          # AMR_VERSION, AMR_CORS_ORIGINS, first admin, HTTP or HTTPS
                   # keep AMR_AGENT_AUTH=required (production refuses "optional")
mkdir -p data maps nginx && sudo chown 10001:10001 data maps
docker compose up -d
```

- **HTTP or HTTPS** is a choice in `.env` (see "HTTPS" below). With
  `AMR_ENV=production` the backend refuses to start over plain HTTP
  (`AMR_COOKIE_SECURE=false`) unless `AMR_ALLOW_INSECURE_HTTP=true` says so
  explicitly; the example `.env` starts that way, for a closed test network.
  Then the session cookie and every password cross the network unencrypted,
  and the backend says so in its log at every start.
- **Client addresses.** The two containers share a network with a fixed
  subnet (`AMR_NET_SUBNET`, default `172.30.57.0/24`); the web container has a
  fixed address (`AMR_WEB_ADDR`, default `172.30.57.10`), and the backend
  takes the client's address from `X-Forwarded-For` only from that address
  (`FORWARDED_ALLOW_IPS`). That address is what the audit trail records and
  the sign-in throttle counts. If the subnet overlaps a network already on the
  machine, `docker compose up` fails with "Pool overlaps": set both variables
  to a free range.

- **First super admin** comes from `AMR_BOOTSTRAP_USER` / `AMR_BOOTSTRAP_PASSWORD`
  in that `.env` (set a strong one-time password; empty creates no account), only while the database has no accounts; it must choose its
  own password at the first sign-in. Delete both lines afterwards. Never put
  them in the images or in GitHub: the images are public.
- **Update:** set `AMR_VERSION`, then `docker compose pull && docker compose up -d`.
- **Back up** `/opt/amr/data` and `/opt/amr/maps`; everything else is in the image.
- **Robots** point at `http://<server>/backend`, or `https://` with HTTPS on
  (`run_agent_gprp.sh <robot_id> http://<server>/backend`) and carry their own
  agent token (see "Agent tokens").
- **No rosbridge proxy.** The old `robots.conf` `/robot/<n>` blocks were removed
  for security; `nginx/` is now only for other per-site extras. If an existing
  `/opt/amr/nginx/robots.conf` still has such a block, delete it and run
  `docker compose restart web`.
- **Raspberry Pi:** keep `/opt/amr` on an SSD or USB drive rather than the SD
  card; SQLite writes on every report and sign-in, and SD cards wear out.

## Server without Docker

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

3. **nginx**: start from `new_webui/deploy/nginx-tls.conf.example` (HTTPS;
   `nginx.conf.example` is the plain-HTTP variant, which needs
   `AMR_ALLOW_INSECURE_HTTP=true` in production). Copy
   `new_webui/frontend/nginx/security-headers.conf` to
   `/etc/nginx/snippets/amr-security-headers.conf`; both examples include it.
   Their `/backend/` block must upgrade WebSockets (it does) because it carries
   the robots' ROS relay, and must **set** `X-Forwarded-For $remote_addr`
   rather than append to it. The backend believes that header only from
   127.0.0.1 (uvicorn's `FORWARDED_ALLOW_IPS` default), so keep nginx on the
   same machine or set that variable in the service to nginx's address. Do not add `/robot/<name>` blocks to rosbridge: remove
   any left from an older config. The robot's `bridge_url` in the registry is
   its direct address, `ws://<jetson>:9090`, which only the backend uses.

## HTTPS

Over plain HTTP the session cookie and every password cross the network
readable by anyone on it, so production refuses it unless
`AMR_ALLOW_INSECURE_HTTP=true` is set. With HTTPS:

- port 80 only redirects (308) to HTTPS;
- `Strict-Transport-Security: max-age=31536000` is sent, over HTTPS only;
- the session cookie is `Secure` (`AMR_COOKIE_SECURE=true`);
- every response carries the security headers in
  `new_webui/frontend/nginx/security-headers.conf` (CSP, `X-Frame-Options`,
  `nosniff`, `Referrer-Policy`, `Permissions-Policy`), on HTTP as well.

**Certificate.** Any certificate the operators' browsers and the robots trust,
for the name (or IP address) the UI is opened with:

- a certificate from the plant's internal CA (preferred on a closed network);
- Let's Encrypt, if the server has a public DNS name;
- for a test, a self-signed one (browsers warn; robots must be told to trust it):

  ```bash
  mkdir -p certs
  openssl req -x509 -newkey rsa:3072 -nodes -days 825 \
      -subj "/CN=amr.example.local" \
      -addext "subjectAltName=DNS:amr.example.local,IP:192.168.10.5" \
      -keyout certs/privkey.pem -out certs/fullchain.pem
  ```

`fullchain.pem` is the certificate followed by any intermediates. When the
certificate is renewed, replace the files and run `docker compose restart web`
(or `systemctl reload nginx`).

**Docker:** in `/opt/amr/.env` switch from choice A to choice B (see
`.env.example`):

```bash
COMPOSE_FILE=docker-compose.yml:docker-compose.tls.yml
AMR_HTTPS_PORT=443
AMR_CORS_ORIGINS=https://amr.example.local,https://192.168.10.5
# and delete AMR_COOKIE_SECURE=false / AMR_ALLOW_INSECURE_HTTP=true
```

Also download `docker-compose.tls.yml` next to `docker-compose.yml`. Put the
files in `/opt/amr/certs/`; the web container's nginx runs as uid 101, so:
`sudo chown root:101 certs/privkey.pem && sudo chmod 640 certs/privkey.pem`.
Then `docker compose up -d`. The TLS file sets `AMR_COOKIE_SECURE=true` and
publishes `AMR_HTTPS_PORT` (443). Terminate TLS in the web container, not in
another proxy in front of it: such a proxy would hide every client's address
behind its own.

**Without Docker:** `new_webui/deploy/nginx-tls.conf.example`, with the files
in `/etc/ssl/amr/`, and `AMR_COOKIE_SECURE=true` plus `https://` origins in the
backend's `.env`.

**Robots** then use `https://<server>/backend`. They do not follow the
redirect for their reports (a redirected POST fails), so change `--backend`
(`AMR_BACKEND_URL` in `/etc/amr/robot.env`) and make each robot trust the
certificate: copy the CA (or the self-signed certificate) to
`/usr/local/share/ca-certificates/amr.crt` and run
`sudo update-ca-certificates`, then `sudo systemctl restart amr-agent`.

## Agent tokens

Each robot agent authenticates to the backend with its own bearer token, bound
to that robot (`AMR_AGENT_AUTH=required`, the default). With `required`, an
agent without a valid token is refused.

1. Register the robot in the UI (Robot → Add robot; `bridge_url`
   `ws://<jetson>:9090`).
2. As an admin: Robot → Details → **Agent token** → generate. The token is
   shown **once**; only its hash is stored. (API: `POST /api/robots/{id}/agent-token`.)
3. Put it on the robot: `--agent-token <token>` on `push_to_robot.sh` /
   `install_robot.sh` (prompted for if omitted), or `AMR_AGENT_TOKEN=` in
   `/etc/amr/robot.env` followed by `sudo systemctl restart amr-agent`.
4. **Rotate** by generating again (the old token stops working at once) and
   updating the robot. **Revoke** with the same dialog, or
   `DELETE /api/robots/{id}/agent-token`: that robot is refused until given a
   new one.

`/etc/amr/robot.env` also holds `AMR_MAX_LINEAR` / `AMR_MAX_ANGULAR` (default
0.5 m/s, 1.5 rad/s): the agent clamps teleop to them and stops on NaN/Inf.
`/robot_mode nav|<path>` only accepts a `.yaml` inside the map cache or the
default map directory.

`AMR_AGENT_AUTH=optional` (anything without credentials acts as an unbound
agent) is for local development only; the backend refuses to start with it when
`AMR_ENV=production`.

## Upgrading an existing site

Order matters; an agent without a token stops working as soon as the new
backend is running.

1. Back up `data/amr.db` and `data/maps/`.
2. Edit the server's `.env`: `AMR_AGENT_AUTH=required` (remove `optional`).
3. Remove any `/robot/<n>` rosbridge proxy (`nginx/robots.conf` or your nginx
   site) and set each robot's `bridge_url` to `ws://<jetson>:9090`.
4. Update the server (`AMR_VERSION`, `docker compose pull && docker compose up -d`;
   the new migration runs on start-up).
5. For each robot: generate its agent token in the UI and install it (steps
   above). Do this while the robots are idle if you can: until the token is in
   place the server refuses that robot.
6. Firewall 9090 on each robot so only the server can reach it, then check the
   live view from a browser.

### Upgrading to the release that refuses plain HTTP

An existing `.env` with `AMR_ENV=production` and `AMR_COOKIE_SECURE=false`
stops the backend from starting ("AMR_COOKIE_SECURE=false in production").
Before updating, either add `AMR_ALLOW_INSECURE_HTTP=true` (stays on HTTP, as
before) or set up HTTPS as above. With Docker, also expect `docker compose up
-d` to recreate both containers on the new `net` network (fixed subnet); the
old `amr_default` network is left unused and can be removed with
`docker network rm amr_default`. With nginx on the host, change
`X-Forwarded-For $proxy_add_x_forwarded_for` to `X-Forwarded-For $remote_addr`
in the `/backend/` block and add the security-headers include.

## Robot (Jetson)

One command from your computer copies `amr_agent/` to the robot and installs
the **agent** and the **kiosk** there as two services. Only those two: the
robot's own stack — ROS 2, Nav2, its workspace with `custom_interfaces`,
rosbridge on 9090, how the OS boots — is the robot team's, and must be in
place first. The installer checks for it and stops with a list if anything is
missing; it never installs or changes it.

```bash
# first time
./amr_agent/deploy/push_to_robot.sh robot@192.168.2.133 \
    --robot-id <id from the web UI> --backend http://<server>/backend --name AMR-02

# every update after that
./amr_agent/deploy/push_to_robot.sh robot@192.168.2.133
```

Or on the robot itself, from a copied `amr_agent` folder:
`./deploy/install_robot.sh --robot-id … --backend …` (`--check` reports only).

What `install_robot.sh` does — each step checks first and installs only what
is missing, so running it again is safe:

1. **Robot stack (checked only)** — ROS 2 in `/opt/ros`, the robot workspace
   (`--ros-ws`, default `~/ros2_gprp_amr_ws`), and the packages the agent uses:
   `rclpy`, `nav2_msgs`, `nav2_map_server`, `custom_interfaces`, … Missing
   ones are listed for the robot team and nothing is installed.
2. **System packages for the agent and kiosk** — `cage` (full-screen kiosk
   compositor), `espeak-ng`, `alsa-utils`, `python3-venv` and the libraries Qt
   needs.
3. **Python packages** — `amr_agent/requirements.txt` (PySide6) into
   `amr_agent/.venv`, made with `--system-site-packages` so it still sees
   `rclpy` from ROS.
4. **Settings** — `/etc/amr/robot.env` from `deploy/robot.env.example`, with a
   random kiosk staff PIN (printed once). An existing file is never touched;
   edit it there afterwards.
5. **Services** — enabled and (re)started:

   | Service | What |
   |---|---|
   | `amr-agent` | `run_agent_gprp.sh`: missions, maps, starting Nav2/SLAM |
   | `amr-kiosk` | the kiosk in `cage` on tty7, full screen, restarted if it ever exits (`--no-kiosk` for a robot without a screen) |

   If the Ubuntu desktop also runs, the kiosk is on Ctrl+Alt+F7. Booting
   straight to the kiosk (no desktop) is a robot setting for the robot team:
   `sudo systemctl set-default multi-user.target`.

The robot's own files survive updates: `state/` (unsent run reports, cached
registry), `station_data.yaml` and `.venv` are never copied over.

```bash
journalctl -u amr-agent -f                      # or amr-kiosk
sudo nano /etc/amr/robot.env && sudo systemctl restart amr-agent amr-kiosk
```

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

- **rosbridge itself still has no authentication.** Browsers no longer reach
  it, but anything that can open a robot's port 9090 can drive it: the firewall
  rule (only the server) is what protects it, and it is a manual step on every
  robot.
- The kiosk's waiting at `confirm` steps (`mission_via=nav`) has been tested
  without a robot only; see `amr_agent/kiosk/README.md`.

## Checklist

- [ ] Backend `.env`: `AMR_ENV=production`, explicit `AMR_CORS_ORIGINS`,
      `AMR_AGENT_AUTH=required`
- [ ] HTTPS on (`AMR_COOKIE_SECURE=true`, certificate trusted by browsers and
      robots), or plain HTTP chosen knowingly with `AMR_ALLOW_INSECURE_HTTP=true`
- [ ] Response headers present: `curl -sI https://<server>/` shows
      `Content-Security-Policy` and `Strict-Transport-Security`
- [ ] Frontend built with `.env.production`
- [ ] nginx serves `/` and proxies `/backend/` with WebSocket upgrade and
      `X-Forwarded-For $remote_addr`; no `/robot/<n>` blocks left
- [ ] Each robot: robot stack ready (robot team), rosbridge on 9090, firewalled
      so only the server can reach it
- [ ] Each robot: `push_to_robot.sh` run; `amr-agent` and `amr-kiosk` active;
      kiosk staff PIN noted
- [ ] Each robot registered in the UI with the right `bridge_url`
      (`ws://<jetson>:9090`), map assigned
- [ ] Each robot has its agent token (`AMR_AGENT_TOKEN`); the robot shows online
- [ ] Pull the server's network once with a robot mid-mission: it should finish
      the mission, and the run should show done when the network is back
- [ ] Back-ups of `data/amr.db` and `data/maps/`
