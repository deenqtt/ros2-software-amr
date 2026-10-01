# Robot kiosk — mockup

What the screen on the robot could show. Static HTML/CSS/JS, no build, no
ROS: every state is faked so the screens can be judged before any wiring.

## Open it

```bash
xdg-open kiosk-mockup/index.html      # or just double-click index.html
```

For the robot's look, press F11 (fullscreen). On a real robot it would run as:

```bash
chromium --kiosk --noerrdialogs --disable-translate file:///path/to/index.html
```

## Simulation panel (bottom right, ⚙ or key `D`)

| Key | State | What the guest sees |
|---|---|---|
| 1 | Idle | Face, eyes look around and follow a touch |
| 2 | Moving | "Menuju Meja 5", route progress; arrives by itself after 6 s |
| 3 | Blocked | Worried yellow eyes, "Permisi 🙏" |
| 4 | Arrived (confirm) | Big "SUDAH DIAMBIL" button, 45 s countdown, ding-dong |
| 5 | Thanks | Happy eyes, then on to the next stop |
| 6 | Charging | Big battery filling |
| 7 | Low battery | Yellow alert |
| 8 | Error | "Saya butuh bantuan" |
| 9 | E-STOP | Flashing red |

Moving runs the whole dummy route by itself: Dapur → **Meja 5** (confirm) →
**Meja 8** (confirm) → Dapur.

Staff menu: long-press the top-left corner for 1.2 s, PIN `1234`.

## Wiring it to the robot later

| Mockup | Real robot |
|---|---|
| `setMode(...)` from the panel | `/robot_mode_status` (agent JSON) over `ws://localhost:9090` |
| Route and current stop | Run plan the agent already has (steps + station names) |
| "SUDAH DIAMBIL" button | Call `/mission_confirm` (agent waits on it at a `confirm` step) |
| Countdown timeout | Agent-side timeout, so it holds even with the screen off |
| Battery | `/battery_state` |
| E-STOP / error | Agent state, `/robot_status` |

The agent does not wait at `confirm` steps yet in `mission_via=nav` mode —
that is the next piece of work once the screens are agreed.
