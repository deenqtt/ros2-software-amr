#!/usr/bin/env python3
"""
The screen on the robot.

Runs next to robot_agent_node.py on the robot itself and reads ROS topics
locally, so it keeps working when wifi or the server is down. Qt Quick draws it
on the GPU, which is what keeps it light on a Jetson.

    python3 kiosk_app.py                 # on the robot, full screen, reads ROS
    python3 kiosk_app.py --mock --window # at a desk: a delivery plays by itself

In --mock mode the keys 1–9 jump between states (see sources.MockSource).
Staff menu: press and hold the top-left corner, then the PIN.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from dataclasses import fields
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from PySide6.QtCore import (  # noqa: E402
    Property,
    QObject,
    QSize,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QFontDatabase, QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtQuick import QQuickImageProvider  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

import screen as screens  # noqa: E402
from icons import ICONS, svg  # noqa: E402
from sound import Sound  # noqa: E402

INPUT_FIELDS = {field.name for field in fields(screens.Inputs)}
# A touch on the face giggles; this many within POKE_WINDOW_S gets a fed-up look.
POKE_LIMIT = 6
POKE_WINDOW_S = 4.0
REMIND_AT_S = 30


class IconProvider(QQuickImageProvider):
    """image://icon/<name>/<rrggbb>/<stroke> — one drawn icon, any colour."""

    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Image)

    def requestImage(self, request_id, size, requested_size):  # noqa: N802 — Qt's name
        parts = request_id.split("/")
        name = parts[0] if parts and parts[0] in ICONS else "info"
        color = QColor("#" + parts[1]) if len(parts) > 1 else QColor("white")
        stroke = float(parts[2]) if len(parts) > 2 else 1.5
        side = max(requested_size.width(), requested_size.height(), 48)
        image = QImage(side, side, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(svg(name, color.name(), stroke))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
        if size is not None:
            size.setWidth(side)
            size.setHeight(side)
        return image


class Kiosk(QObject):
    """Everything QML binds to. One `changed` signal: the screen is small."""

    changed = Signal()
    # --mock only: open the staff menu without the long press, for review.
    staffRequested = Signal()
    # Sources may push from a ROS thread; this hops to the Qt thread.
    _pushed = Signal(dict)

    def __init__(self, *, lang: str, robot_name: str, pin: str, sound: Sound) -> None:
        super().__init__()
        self._inputs = screens.Inputs(lang=lang)
        self._view = screens.view_for(self._inputs)
        self._robot_name = robot_name
        self._pin = pin
        self._sound = sound
        self._source = None
        self._mission = ""
        self._robot_mode = ""
        self._large = False
        self._pokes: list[float] = []
        self._reaction_until = 0.0
        self._reminded = False
        self._pushed.connect(self._apply, Qt.ConnectionType.QueuedConnection)
        self._reaction_timer = QTimer(self)
        self._reaction_timer.setSingleShot(True)
        self._reaction_timer.timeout.connect(self._end_reaction)

    def attach(self, source) -> None:
        self._source = source

    def push(self, update: dict) -> None:
        """Thread-safe: called by sources from any thread."""
        self._pushed.emit(dict(update))

    # ── State ────────────────────────────────────────────────────────────────

    @Slot(dict)
    def _apply(self, update: dict) -> None:
        self._mission = update.pop("mission", self._mission)
        self._robot_mode = update.pop("robot_mode", self._robot_mode)
        for key, value in update.items():
            if key in INPUT_FIELDS:
                setattr(self._inputs, key, value)
        self._refresh()

    def _refresh(self) -> None:
        before = self._view.screen
        self._view = screens.view_for(self._inputs)
        after = self._view.screen
        if after != before:
            self._on_screen_change(after)
        remaining = self._inputs.confirm_remaining
        if after == screens.ARRIVED and remaining is not None:
            if remaining <= REMIND_AT_S and not self._reminded:
                self._reminded = True
                self._sound.chime("arrive")
                self._sound.say(screens.spoken(self._inputs.lang, "say_reminder"), self._inputs.lang)
        self.changed.emit()

    def _on_screen_change(self, screen: str) -> None:
        lang = self._inputs.lang
        if screen == screens.ARRIVED:
            self._reminded = False
            self._sound.chime("arrive")
            self._sound.say(screens.spoken(lang, "say_arrived", self._view.place), lang)
        elif screen == screens.THANKS:
            self._sound.chime("thanks")
            self._sound.say(screens.spoken(lang, "say_thanks"), lang)
        elif screen == screens.BLOCKED:
            self._sound.chime("blocked")
            self._sound.say(screens.spoken(lang, "say_blocked"), lang)
        else:
            self._sound.stop()
        # A reaction belongs to the idle face only.
        self._inputs.reaction = ""

    # ── Properties ───────────────────────────────────────────────────────────

    def _text(self, key: str) -> str:
        return screens.TEXT.get(self._inputs.lang, screens.TEXT["id"])[key]

    screen = Property(str, lambda self: self._view.screen, notify=changed)
    mood = Property(str, lambda self: self._view.mood, notify=changed)
    title = Property(str, lambda self: self._view.title, notify=changed)
    subtitle = Property(str, lambda self: self._view.subtitle, notify=changed)
    pill = Property(str, lambda self: self._view.pill, notify=changed)
    place = Property(str, lambda self: self._view.place, notify=changed)
    showRoute = Property(bool, lambda self: self._view.show_route, notify=changed)
    intentText = Property(str, lambda self: self._view.intent_text, notify=changed)
    intentSide = Property(str, lambda self: self._inputs.intent, notify=changed)
    route = Property("QVariantList", lambda self: list(self._inputs.route), notify=changed)
    step = Property(int, lambda self: -1 if self._inputs.step is None else self._inputs.step, notify=changed)
    linked = Property(bool, lambda self: self._inputs.linked, notify=changed)
    battery = Property(
        int,
        lambda self: -1 if self._inputs.battery is None else round(self._inputs.battery),
        notify=changed,
    )
    charging = Property(bool, lambda self: self._inputs.charging, notify=changed)
    robotName = Property(str, lambda self: self._robot_name, notify=changed)
    lang = Property(str, lambda self: self._inputs.lang, notify=changed)
    largeText = Property(bool, lambda self: self._large, notify=changed)
    mock = Property(bool, lambda self: type(self._source).__name__ == "MockSource", notify=changed)
    confirmRemaining = Property(
        int,
        lambda self: -1 if self._inputs.confirm_remaining is None else int(self._inputs.confirm_remaining),
        notify=changed,
    )
    confirmTimeout = Property(
        int,
        lambda self: int(self._inputs.confirm_timeout or 0),
        notify=changed,
    )
    countdownClock = Property(
        str, lambda self: screens.clock_text(self._inputs.confirm_remaining), notify=changed
    )
    countdownText = Property(
        str,
        lambda self: screens.countdown_text(self._inputs.lang, self._inputs.confirm_remaining),
        notify=changed,
    )
    t = Property(
        "QVariantMap",
        lambda self: {
            key: value
            for key, value in screens.TEXT.get(self._inputs.lang, screens.TEXT["id"]).items()
            if isinstance(value, str)
        },
        notify=changed,
    )
    techInfo = Property(
        str,
        lambda self: "\n".join(
            [
                f"Robot     : {self._robot_name}",
                f"Agent     : {'terhubung' if self._inputs.linked else 'tidak terdengar'}",
                f"Mode      : {self._robot_mode or '-'}",
                f"Fase      : {self._inputs.phase or '-'}",
                f"Misi      : {self._mission or '-'}",
                f"Rute      : {' → '.join(self._inputs.route) or '-'}",
                f"Baterai   : {'-' if self._inputs.battery is None else round(self._inputs.battery)}%",
                f"Sumber    : {'mock' if self.mock else 'ROS lokal'}",
            ]
        ),
        notify=changed,
    )

    # ── Actions ──────────────────────────────────────────────────────────────

    @Slot()
    def confirm(self) -> None:
        """The big green button, or the staff menu's "continue now"."""
        if self._source is not None:
            self._source.confirm()

    @Slot()
    def poke(self) -> None:
        """A touch on the face."""
        # Fed up lasts its full moment; more pokes do not cheer it up.
        if self._view.screen != screens.IDLE or self._inputs.reaction == "annoyed":
            return
        now = time.monotonic()
        self._pokes = [at for at in self._pokes if now - at < POKE_WINDOW_S] + [now]
        reaction = "annoyed" if len(self._pokes) >= POKE_LIMIT else "tickle"
        if reaction == "annoyed":
            self._pokes = []
        self._inputs.reaction = reaction
        self._sound.chime(reaction)
        self._reaction_timer.start(2600 if reaction == "annoyed" else 1100)
        self._refresh()

    def _end_reaction(self) -> None:
        self._inputs.reaction = ""
        self._refresh()

    @Slot(str, result=bool)
    def checkPin(self, pin: str) -> bool:  # noqa: N802 — QML name
        return pin == self._pin

    @Slot()
    def toggleLarge(self) -> None:  # noqa: N802
        self._large = not self._large
        self.changed.emit()

    @Slot()
    def toggleLang(self) -> None:  # noqa: N802
        self._inputs.lang = "en" if self._inputs.lang == "id" else "id"
        self._refresh()

    @Slot(str)
    def key(self, key: str) -> None:
        if key in ("s", "S") and self.mock:
            self.staffRequested.emit()
        elif self._source is not None:
            self._source.key(key)


def load_fonts() -> str:
    family = ""
    for font in sorted((HERE / "fonts").glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(font))
        if font_id >= 0 and not family:
            families = QFontDatabase.applicationFontFamilies(font_id)
            family = families[0] if families else ""
    return family or "Sans Serif"


def main() -> int:
    parser = argparse.ArgumentParser(description="AMR robot kiosk")
    parser.add_argument("--mock", action="store_true", help="play a delivery, no ROS needed")
    parser.add_argument("--window", action="store_true", help="a window instead of full screen")
    parser.add_argument("--size", default="1280x800", help="window size, e.g. 800x1280")
    parser.add_argument("--lang", choices=("id", "en"), default="id")
    parser.add_argument("--robot-name", default=os.environ.get("AMR_KIOSK_NAME", "AMR"))
    parser.add_argument("--pin", default=os.environ.get("AMR_KIOSK_PIN", "1234"))
    parser.add_argument("--estop-topic", default="", help="std_msgs/Bool, true while stopped")
    parser.add_argument("--no-sound", action="store_true")
    parser.add_argument("--screenshot", default="", help=argparse.SUPPRESS)
    parser.add_argument("--mock-keys", default="", help=argparse.SUPPRESS)
    args, qt_args = parser.parse_known_args()

    app = QGuiApplication([sys.argv[0], *qt_args])
    app.setApplicationName("AMR Kiosk")
    family = load_fonts()

    sound = Sound(enabled=not args.no_sound)
    kiosk = Kiosk(lang=args.lang, robot_name=args.robot_name, pin=args.pin, sound=sound)
    if args.mock:
        from sources import MockSource

        source = MockSource(kiosk.push)
        # For docs and review: jump to a state at start, e.g. --mock-keys 4.
        for index, key in enumerate(args.mock_keys):
            QTimer.singleShot(300 + 10 * index, lambda key=key: kiosk.key(key))
    else:
        from sources import RosSource

        source = RosSource(kiosk.push, estop_topic=args.estop_topic)
    kiosk.attach(source)

    width, _, height = args.size.partition("x")
    engine = QQmlApplicationEngine()
    engine.addImageProvider("icon", IconProvider())
    engine.addImportPath(str(HERE / "qml"))
    context = engine.rootContext()
    context.setContextProperty("kiosk", kiosk)
    context.setContextProperty("fontFamily", family)
    context.setContextProperty("windowed", args.window)
    context.setContextProperty("startSize", QSize(int(width), int(height)))
    engine.load(str(HERE / "qml" / "Main.qml"))
    if not engine.rootObjects():
        return 1

    if args.screenshot:
        # For docs: let the state settle, grab the window, quit.
        window = engine.rootObjects()[0]

        def grab() -> None:
            window.grabWindow().save(args.screenshot)
            app.quit()

        QTimer.singleShot(int(os.environ.get("AMR_KIOSK_SHOT_DELAY_MS", "1500")), grab)

    # Ctrl+C in a terminal should close it, not be swallowed by the event loop.
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    tick = QTimer()
    tick.start(250)
    tick.timeout.connect(lambda: None)

    code = app.exec()
    if hasattr(source, "close"):
        source.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
