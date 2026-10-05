"""
Chimes and spoken prompts.

Nothing here may block the screen or crash it: a robot with no speaker, no
audio device or no voice installed still shows everything. Sound is played by
the system's own player (paplay, else aplay) in the background.

Voice, best first:
  1. Piper (offline neural TTS) when AMR_KIOSK_PIPER_MODEL points at a voice,
     e.g. id_ID-news_tts-medium.onnx. Clear, and fast enough on a Jetson.
  2. espeak-ng, robotic but always available from apt.
  3. Nothing: the chime and the screen carry the message.
"""

from __future__ import annotations

import math
import os
import shlex
import shutil
import struct
import subprocess
import threading
import wave
from pathlib import Path

RATE = 22050

# (frequency Hz, start s, length s). The arrival "ding-dong" is the sound people
# already know means something arrived.
TUNES = {
    "arrive": [(880, 0.0, 0.6), (1320, 0.18, 0.7)],
    "thanks": [(1046, 0.0, 0.25), (1318, 0.1, 0.25), (1568, 0.2, 0.45)],
    "blocked": [(660, 0.0, 0.18), (660, 0.22, 0.18)],
    "tickle": [(1500, 0.0, 0.08), (1900, 0.07, 0.12)],
    "annoyed": [(520, 0.0, 0.18), (390, 0.16, 0.3)],
    "tap": [(1200, 0.0, 0.05)],
}

VOICE_LANG = {"id": "id", "en": "en-gb"}


def _render(notes, path: Path) -> None:
    length = max(start + dur for _, start, dur in notes) + 0.05
    samples = [0.0] * int(RATE * length)
    for freq, start, dur in notes:
        first = int(RATE * start)
        for i in range(int(RATE * dur)):
            t = i / RATE
            # Fast attack, exponential decay: a bell, not a beep.
            envelope = min(1.0, t / 0.01) * math.exp(-4.5 * t / dur)
            samples[first + i] += 0.28 * envelope * math.sin(2 * math.pi * freq * t)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(
            b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples)
        )


class Sound:
    def __init__(self, enabled: bool = True, cache: Path | None = None) -> None:
        self.enabled = enabled
        self._cache = cache or Path.home() / ".cache" / "amr_kiosk"
        # AMR_KIOSK_PLAYER picks one; aplay works from a service with no
        # desktop session, where paplay has no sound server to talk to.
        chosen = os.environ.get("AMR_KIOSK_PLAYER", "")
        self._player = (shutil.which(chosen) if chosen else None) or (
            shutil.which("paplay") or shutil.which("aplay")
        )
        self._piper = shutil.which("piper")
        self._piper_model = os.environ.get("AMR_KIOSK_PIPER_MODEL", "")
        self._espeak = shutil.which("espeak-ng") or shutil.which("espeak")
        self._speech: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def _tune_path(self, name: str) -> Path:
        path = self._cache / f"{name}.wav"
        if not path.exists():
            self._cache.mkdir(parents=True, exist_ok=True)
            _render(TUNES[name], path)
        return path

    def chime(self, name: str) -> None:
        if not self.enabled or not self._player or name not in TUNES:
            return
        try:
            subprocess.Popen(
                [self._player, str(self._tune_path(name))],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass

    def say(self, text: str, lang: str = "id", delay_s: float = 0.7) -> None:
        """Speak after the chime has had its moment. A newer line cuts an older one."""
        if not self.enabled or not text:
            return
        threading.Timer(delay_s, self._speak, args=(text, lang)).start()

    def _speak(self, text: str, lang: str) -> None:
        with self._lock:
            if self._speech is not None and self._speech.poll() is None:
                self._speech.terminate()
            try:
                if self._piper and self._piper_model and self._player:
                    command = (
                        f"{shlex.quote(self._piper)} --model {shlex.quote(self._piper_model)} "
                        f"--output_file - | {shlex.quote(self._player)}"
                    )
                    self._speech = subprocess.Popen(
                        command,
                        shell=True,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    self._speech.stdin.write(text.encode())
                    self._speech.stdin.close()
                elif self._espeak:
                    self._speech = subprocess.Popen(
                        [self._espeak, "-v", VOICE_LANG.get(lang, "id"), "-s", "150", text],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            except OSError:
                self._speech = None

    def stop(self) -> None:
        with self._lock:
            if self._speech is not None and self._speech.poll() is None:
                self._speech.terminate()
