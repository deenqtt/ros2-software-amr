# Robot kiosk

The screen on the robot: the face, where it is going, "Pesanan Anda sudah
tiba" with one big button, charging, and faults. Python + Qt Quick (PySide6),
running on the robot next to `robot_agent_node.py` and reading ROS locally, so
it keeps working when wifi or the server is down. The design is
`kiosk-mockup/`; this is the real thing.

## Run it

At a desk, no ROS needed — a delivery plays by itself:

```bash
pip install PySide6
python3 amr_agent/kiosk/kiosk_app.py --mock --window
python3 amr_agent/kiosk/kiosk_app.py --mock --window --size 800x1280   # portrait
```

| Key | State |
|---|---|
| 1 | Idle |
| 2 | Start a delivery (Dapur → Meja 5 → Meja 8 → Dapur) |
| 3 | Blocked |
| 4 | Arrived, waiting for "Sudah diambil" (2:00 countdown) |
| 5 | Thanks |
| 6 | Charging |
| 7 | Low battery |
| 8 | Error |
| 9 | Emergency stop (again to clear) |
| + / − | Battery up / down |
| L | Indonesian / English |

Tap the face while idle; tap it six times quickly. Staff menu: hold the
top-left corner for 1.2 s, PIN `1234` (set `AMR_KIOSK_PIN`).

On the robot, with the agent:

```bash
AMR_KIOSK_NAME=AMR-02 AMR_KIOSK_PIN=4821 \
  ./amr_agent/run_agent_gprp.sh --kiosk <robot_id> <backend_url>
```

or on its own: `python3 amr_agent/kiosk/kiosk_app.py --robot-name AMR-02`.

## Options

| Option | |
|---|---|
| `--mock` | Simulated delivery instead of ROS |
| `--window`, `--size WxH` | A window instead of full screen |
| `--lang id\|en` | Language (default `id`) |
| `--robot-name` | Name on the status bar (`AMR_KIOSK_NAME`) |
| `--pin` | Staff PIN (`AMR_KIOSK_PIN`) |
| `--estop-topic` | `std_msgs/Bool`, true while the emergency stop is pressed |
| `--no-sound` | No chimes or voice |

## What it reads and calls

| Name | Type | |
|---|---|---|
| `/amr/kiosk` | `std_msgs/String` (JSON, latched, 1 Hz) | From the agent: phase, mission, route, step, seconds left to confirm |
| `/battery_state` | `sensor_msgs/BatteryState` | Percentage and charging |
| `--estop-topic` | `std_msgs/Bool` | Optional |
| `/mission_confirm` | `std_srvs/Trigger` | The "Sudah diambil" button and the staff menu's "Lanjutkan sekarang" |

With `mission_via=nav` the agent waits at a `confirm` step itself, for up to
`confirm_timeout` seconds (120 by default, `AMR_CONFIRM_TIMEOUT`), and serves
`/mission_confirm`. With `mission_via=mission_plan` the mission manager does
both, and the kiosk shows the stop as "moving" until it is confirmed.

If the agent is not heard for 3.5 s the screen says it is starting up rather
than showing a face that claims to be ready.

## Sound

Chimes are generated on first use and played with `paplay` or `aplay`. Spoken
prompts use [Piper](https://github.com/rhasspy/piper) when
`AMR_KIOSK_PIPER_MODEL` points at a voice (offline, clear, runs on a Jetson),
otherwise `espeak-ng` if installed, otherwise none — the chime and the screen
still say everything.

## Files

| File | |
|---|---|
| `kiosk_app.py` | Entry point, the `Kiosk` object QML binds to, icon provider |
| `screen.py` | Which screen wins and what the robot says. No Qt; tested in `../tests/` |
| `sources.py` | `RosSource` (rclpy) and `MockSource` |
| `sound.py` | Chimes and voice |
| `icons.py` | The icon set, as SVG path data |
| `qml/` | The screens |
| `fonts/` | Plus Jakarta Sans (SIL Open Font License, `fonts/OFL.txt`) |

Tests (no ROS, no display):

```bash
python3 -m pytest amr_agent/tests
```
