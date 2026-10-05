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
| 1 | Idle | Face, eyes look around and follow a finger; a tap giggles, a burst of taps gets a fed-up look |
| 2 | Moving | "Menuju Meja 5", route progress, a turn signalled on the way ("Saya belok kiri", eyes and LED strip), "Hampir sampai" just before arriving |
| 3 | Blocked | Worried amber eyes, "Permisi", spoken "Permisi, saya mau lewat" |
| 4 | Arrived (confirm) | Big "Sudah diambil" button, **2 minute** countdown, ding-dong + spoken prompt, spoken reminder with 30 s left |
| 5 | Thanks | Happy ^ ^ eyes, then on to the next stop |
| 6 | Charging | Sleeping eyes over a battery filling |
| 7 | Low battery | Amber alert |
| 8 | Error | "Saya butuh bantuan" |
| 9 | E-STOP | Flashing red |

Icons are drawn for this screen (inline SVG in `index.html`, 24 px grid,
1.5 stroke) — no emoji, which render differently on every OS. The thin bar
along the bottom stands in for the LED strip round the robot's base. Voice
uses the browser's speech synthesis as a stand-in for the robot's speaker.

Moving runs the whole dummy route by itself: Dapur → **Meja 5** (confirm) →
**Meja 8** (confirm) → Dapur.

Staff menu: long-press the top-left corner for 1.2 s, PIN `1234`. It also
has a large-text switch.

URL options for reviewing one screen: `?mode=arrived&lang=en&panel=0&sound=0&large=1`.

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
