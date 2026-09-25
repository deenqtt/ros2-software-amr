#!/usr/bin/env python3
"""Gazebo Harmonic contact JSON parsing and persistent topic reader."""

from __future__ import annotations

import json
import subprocess
import threading
import time


def parse_contact_json_line(line: str) -> dict:
    message = json.loads(line)
    stamp = message.get("header", {}).get("stamp", {})
    contacts = message.get("contact", []) or []
    pairs = []
    normal_force_z = []
    depths = []
    for contact in contacts:
        pairs.append(
            (
                contact.get("collision1", {}).get("name", ""),
                contact.get("collision2", {}).get("name", ""),
            )
        )
        depths.extend(float(value) for value in contact.get("depth", []) or [])
        for wrench in contact.get("wrench", []) or []:
            force = wrench.get("body1Wrench", {}).get("force", {})
            if "z" in force:
                normal_force_z.append(abs(float(force["z"])))
    return {
        "stamp_s": float(stamp.get("sec", 0.0)) + float(stamp.get("nsec", 0.0)) * 1e-9,
        "active": bool(contacts),
        "contact_count": len(contacts),
        "pairs": pairs,
        "normal_force_z_max_n": max(normal_force_z, default=0.0),
        "depth_max_m": max(depths, default=0.0),
    }


class ContactReader:
    def __init__(self, topic: str):
        self.topic = topic
        self.latest = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._process = subprocess.Popen(
            ["stdbuf", "-oL", "gz", "topic", "-e", "--json-output", "-t", topic],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self):
        assert self._process.stdout is not None
        for line in self._process.stdout:
            if self._stop.is_set():
                break
            try:
                parsed = parse_contact_json_line(line)
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
            with self._lock:
                self.latest = parsed

    def snapshot(self):
        with self._lock:
            return dict(self.latest) if self.latest is not None else None

    def wait_ready(self, timeout_s: float = 10.0):
        deadline = time.monotonic() + timeout_s
        while self.snapshot() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        return self.snapshot() is not None

    def close(self):
        self._stop.set()
        self._process.terminate()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()
