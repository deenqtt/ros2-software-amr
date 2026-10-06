"""
The kiosk's icons: drawn for this screen on a 24 px grid, 1.5 stroke, round
ends. The same set as docs/design/kiosk-mockup/, kept as path data so one icon can be any
colour (see IconProvider in kiosk_app.py). No emoji: they render differently
on every OS and cannot take a colour.
"""

ICONS = {
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "stop": '<path d="M8.2 2.5h7.6l5.7 5.7v7.6l-5.7 5.7H8.2l-5.7-5.7V8.2z"/><path d="M8.5 12h7"/>',
    "help": (
        '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3.8"/>'
        '<path d="M5.6 5.6l3.7 3.7M14.7 14.7l3.7 3.7M18.4 5.6l-3.7 3.7M9.3 14.7l-3.7 3.7"/>'
    ),
    "cloche": (
        '<path d="M2.5 18.5h19"/><path d="M4.5 18.5a7.5 7.5 0 0 1 15 0"/>'
        '<path d="M12 9.5V7.5"/><path d="M10.2 7.5h3.6"/><path d="M8 14.5a4.2 4.2 0 0 1 2.4-2.6"/>'
    ),
    "pin": (
        '<path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z"/>'
        '<circle cx="12" cy="10" r="2.3"/>'
    ),
    "turn-left": '<path d="M17 20v-6.5A4.5 4.5 0 0 0 12.5 9H5"/><path d="M9 5L5 9l4 4"/>',
    "turn-right": '<path d="M7 20v-6.5A4.5 4.5 0 0 1 11.5 9H19"/><path d="M15 5l4 4-4 4"/>',
    "pause": '<path d="M9 6v12M15 6v12"/>',
    "bolt": '<path d="M13.2 2.5L4.8 13.6h6.4l-1 7.9 8.4-11.1h-6.4z"/>',
    "battery-low": (
        '<rect x="2.5" y="7" width="16.5" height="10" rx="2.2"/>'
        '<path d="M21.5 10.5v3"/><path d="M6 10.5v3"/>'
    ),
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5"/><path d="M12 7.8h.01"/>',
    "backspace": (
        '<path d="M9 5h10.5A1.5 1.5 0 0 1 21 6.5v11a1.5 1.5 0 0 1-1.5 1.5H9l-6-7z"/>'
        '<path d="M12.5 9.5l5 5M17.5 9.5l-5 5"/>'
    ),
    "lock": '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
    "sliders": (
        '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/>'
        '<circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>'
    ),
    "text-size": '<path d="M3 19L8 6l5 13M4.9 14.5h6.2"/><path d="M14.5 19l3.2-7.5 3.3 7.5M15.6 16.5h4.2"/>',
    "wifi": (
        '<path d="M2.5 9a14 14 0 0 1 19 0"/><path d="M5.5 12.5a9.5 9.5 0 0 1 13 0"/>'
        '<path d="M8.7 16a5 5 0 0 1 6.6 0"/><path d="M12 19.5h.01"/>'
    ),
    "wifi-off": (
        '<path d="M3 3l18 18"/><path d="M8.7 16a5 5 0 0 1 6.6 0"/><path d="M12 19.5h.01"/>'
        '<path d="M5.5 12.5a9.5 9.5 0 0 1 4-2.3"/><path d="M2.5 9a14 14 0 0 1 4.3-2.9"/>'
    ),
    "play": '<path d="M7.5 5.5v13l11-6.5z"/>',
    "play-forward": '<path d="M5 6v12l8.5-6z"/><path d="M14 6v12l7-6z"/>',
}

# Icons drawn filled as well as stroked.
FILLED = {"bolt", "play"}


def svg(name: str, color: str, stroke_width: float = 1.5, fill: str | None = None) -> bytes:
    body = ICONS[name]
    fill_value = fill if fill is not None else (color if name in FILLED else "none")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="{fill_value}" stroke="{color}" stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    ).encode()
