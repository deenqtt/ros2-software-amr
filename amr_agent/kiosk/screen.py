"""
What the kiosk shows, decided from what the robot reports.

Plain Python, no Qt: the decisions here (which screen wins when two things are
true at once, what the robot says) are the ones worth testing, and the QML only
draws the answer. Both the live ROS source and the --mock simulation feed the
same `Inputs`, so the screen behaves identically in both.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Screens, one per layout in the QML.
IDLE = "idle"
MOVING = "moving"
BLOCKED = "blocked"
ARRIVED = "arrived"
THANKS = "thanks"
CHARGING = "charging"
LOWBAT = "lowbat"
ERROR = "error"
ESTOP = "estop"
OFFLINE = "offline"

LOW_BATTERY = 15
# The face's mood for each screen. See Face.qml.
MOOD = {
    IDLE: "neutral",
    MOVING: "focused",
    BLOCKED: "worried",
    ARRIVED: "happy",
    THANKS: "happy",
    CHARGING: "sleepy",
    LOWBAT: "sleepy",
    ERROR: "worried",
    ESTOP: "worried",
    OFFLINE: "sleepy",
}

TEXT = {
    "id": {
        "idle": ("Halo!", "Saya siap mengantar"),
        "done": ("Semua pesanan terantar", "Saya siap mengantar lagi"),
        "moving": ("Menuju {place}", "Permisi, saya lewat ya"),
        "near": ("Hampir sampai di {place}", "Sebentar lagi pesanan Anda tiba"),
        "blocked": ("Permisi", "Saya berhenti sebentar, ada yang menghalangi jalan"),
        "thanks": ("Terima kasih!", "Selamat menikmati"),
        "tickle": ("Hehe, geli!", "Saya siap mengantar"),
        "annoyed": ("Aduh, pelan-pelan ya", "Saya bukan tombol, hehe"),
        "offline": ("Sebentar ya", "Saya sedang menyiapkan sistem"),
        "turn_left": "Saya belok kiri",
        "turn_right": "Saya belok kanan",
        "arrived_kicker": "Pesanan Anda sudah tiba",
        "arrived_hint": "Ambil pesanan dari nampan, lalu tekan tombol hijau",
        "confirm": "Sudah diambil",
        "countdown": "Tidak ditekan? Robot lanjut sendiri",
        "countdown_ending": "Robot akan segera lanjut",
        "charging": ("Sedang mengisi daya", "Sebentar ya, saya istirahat dulu"),
        "charged": ("Sedang mengisi daya", "Baterai penuh, siap bertugas"),
        "lowbat": ("Baterai lemah", "Saya kembali ke charger dulu ya"),
        "error": ("Saya butuh bantuan", "Saya tidak bisa melanjutkan rute. Mohon panggil staf."),
        "estop": ("Robot berhenti", "Tombol darurat ditekan. Mohon panggil staf."),
        "pin_title": "Masukkan PIN staf",
        "cancel": "Batal",
        "menu_title": "Menu staf",
        "menu_continue": "Lanjutkan sekarang",
        "menu_large": "Teks besar",
        "menu_info": "Info teknis",
        "menu_close": "Tutup",
        "linked": "Terhubung",
        "unlinked": "Tidak terhubung",
        "say_arrived": "Pesanan untuk {place} sudah tiba. Silakan diambil, lalu tekan tombol hijau.",
        "say_reminder": "Pesanannya masih di sini. Silakan diambil ya.",
        "say_thanks": "Terima kasih, selamat menikmati.",
        "say_blocked": "Permisi, saya mau lewat.",
        "pill": {
            IDLE: "Siap", MOVING: "Mengantar", BLOCKED: "Terhalang", ARRIVED: "Tiba",
            THANKS: "Selesai", CHARGING: "Mengisi", LOWBAT: "Baterai lemah",
            ERROR: "Butuh bantuan", ESTOP: "Darurat", OFFLINE: "Menyiapkan",
        },
    },
    "en": {
        "idle": ("Hello!", "Ready to deliver"),
        "done": ("All orders delivered", "Ready for the next one"),
        "moving": ("Heading to {place}", "Excuse me, coming through"),
        "near": ("Almost at {place}", "Your order is nearly here"),
        "blocked": ("Excuse me", "I have stopped for a moment, something is in my way"),
        "thanks": ("Thank you!", "Enjoy your meal"),
        "tickle": ("Hehe, that tickles!", "Ready to deliver"),
        "annoyed": ("Gently, please", "I am not a button, hehe"),
        "offline": ("One moment", "I am getting my systems ready"),
        "turn_left": "I am turning left",
        "turn_right": "I am turning right",
        "arrived_kicker": "Your order has arrived",
        "arrived_hint": "Take your order from the tray, then press the green button",
        "confirm": "Picked up",
        "countdown": "Not pressed? I will carry on by myself",
        "countdown_ending": "I will carry on shortly",
        "charging": ("Charging", "Taking a short rest"),
        "charged": ("Charging", "Fully charged, ready to go"),
        "lowbat": ("Battery low", "Heading back to the charger"),
        "error": ("I need help", "I cannot continue my route. Please call staff."),
        "estop": ("Robot stopped", "Emergency stop pressed. Please call staff."),
        "pin_title": "Enter staff PIN",
        "cancel": "Cancel",
        "menu_title": "Staff menu",
        "menu_continue": "Continue now",
        "menu_large": "Large text",
        "menu_info": "Technical info",
        "menu_close": "Close",
        "linked": "Connected",
        "unlinked": "Not connected",
        "say_arrived": "Your order for {place} has arrived. Please take it, then press the green button.",
        "say_reminder": "Your order is still here. Please take it.",
        "say_thanks": "Thank you, enjoy your meal.",
        "say_blocked": "Excuse me, coming through.",
        "pill": {
            IDLE: "Ready", MOVING: "Delivering", BLOCKED: "Blocked", ARRIVED: "Arrived",
            THANKS: "Done", CHARGING: "Charging", LOWBAT: "Low battery",
            ERROR: "Needs help", ESTOP: "Emergency", OFFLINE: "Starting",
        },
    },
}


@dataclass
class Inputs:
    """Everything the screen depends on. Filled from /amr/kiosk and friends."""

    #: The agent's phase (delivery.py), or "" when nothing heard yet.
    phase: str = ""
    #: The agent has been heard recently.
    linked: bool = False
    route: list[str] = field(default_factory=list)
    step: int | None = None
    confirm_remaining: int | None = None
    confirm_timeout: int | None = None
    detail: str = ""
    battery: float | None = None
    charging: bool = False
    estop: bool = False
    #: "left", "right" or "" — a turn about to happen.
    intent: str = ""
    #: "tickle", "annoyed" or "" — the face reacting to a touch.
    reaction: str = ""
    lang: str = "id"


@dataclass
class View:
    screen: str
    mood: str
    title: str
    subtitle: str
    pill: str
    place: str = ""
    near: bool = False
    show_route: bool = False
    intent_text: str = ""


def screen_for(inputs: Inputs) -> str:
    """
    Which screen wins. Safety first, then the person who needs to act, then
    the robot's own business.
    """
    phase = inputs.phase
    if inputs.estop:
        return ESTOP
    if phase == "failed":
        return ERROR
    if not inputs.linked or not phase or phase == "off":
        # The robot is still delivering if a run is going, even with the agent
        # unheard for a moment; but with nothing at all, say we're starting.
        return CHARGING if inputs.charging else OFFLINE
    if phase == "waiting":
        return ARRIVED
    if phase == "thanks":
        return THANKS
    if phase == "blocked":
        return BLOCKED
    if phase in ("moving", "near"):
        return MOVING
    if inputs.charging:
        return CHARGING
    if inputs.battery is not None and inputs.battery <= LOW_BATTERY:
        return LOWBAT
    return IDLE


def place_of(inputs: Inputs) -> str:
    if inputs.step is None or not (0 <= inputs.step < len(inputs.route)):
        return ""
    return inputs.route[inputs.step]


def view_for(inputs: Inputs) -> View:
    text = TEXT.get(inputs.lang, TEXT["id"])
    screen = screen_for(inputs)
    place = place_of(inputs)
    near = inputs.phase == "near"

    key = {
        IDLE: "done" if inputs.phase == "done" else "idle",
        MOVING: "near" if near else "moving",
        BLOCKED: "blocked",
        THANKS: "thanks",
        CHARGING: "charged" if (inputs.battery or 0) >= 100 else "charging",
        LOWBAT: "lowbat",
        ERROR: "error",
        ESTOP: "estop",
        OFFLINE: "offline",
        ARRIVED: "thanks",  # unused on the arrived screen; keeps the lookup total
    }[screen]
    mood = MOOD[screen]
    if screen == MOVING and near:
        mood = "eager"
    if screen == IDLE and inputs.reaction in ("tickle", "annoyed"):
        key = inputs.reaction
        mood = "happy" if inputs.reaction == "tickle" else "annoyed"

    title, subtitle = text[key]
    if screen == ERROR and inputs.detail:
        # The staff member who comes over wants the reason; the guest only
        # needs the first line.
        subtitle = f"{subtitle}\n{inputs.detail}"

    intent = ""
    if screen == MOVING and inputs.intent in ("left", "right"):
        intent = text[f"turn_{inputs.intent}"]

    return View(
        screen=screen,
        mood=mood,
        title=title.format(place=place),
        subtitle=subtitle.format(place=place),
        pill=text["pill"][screen],
        place=place,
        near=near,
        show_route=screen in (MOVING, BLOCKED, THANKS) and bool(inputs.route),
        intent_text=intent,
    )


def spoken(lang: str, key: str, place: str = "") -> str:
    return TEXT.get(lang, TEXT["id"])[key].format(place=place)


def countdown_text(lang: str, remaining: int | None) -> str:
    text = TEXT.get(lang, TEXT["id"])
    return text["countdown_ending"] if remaining is not None and remaining <= 30 else text["countdown"]


def clock_text(seconds: int | None) -> str:
    if seconds is None:
        return ""
    return f"{seconds // 60}:{seconds % 60:02d}"
