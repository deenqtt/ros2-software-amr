"""
What the robot agent remembers across restarts and network outages.

The backend is the registry: it says which map a robot is on, what it should be
doing, where the stations are, and which mission to run. In production it is a
different machine from the robot — a server on one side, a Jetson on wifi on the
other — and the link between them drops. Three things went wrong when it did:

1. **A robot that booted while the server was down never started.** The agent
   could not read its desired mode, so it did nothing, although the map was
   sitting in its own cache. The last good registry reading is kept here, and
   the agent starts from it when the server cannot be reached.

2. **Run progress written while offline was lost.** Worse, a lost "done" left
   the run live on the server, and the agent picked it up again on reconnect and
   drove the route a second time. Reports now go into an outbox on disk, sent in
   order when the server is back, and every run this robot finished is recorded
   so it is never executed twice.

3. **Station poses lived only in memory.** An agent restarted while offline did
   not know where anything was. The last station set for each map is kept here.

No ROS imports, on purpose: this is plain file handling, and it is tested
without a robot.

Every write goes to a temporary file that is then moved into place. A power cut
mid-write leaves the previous version, never half of a new one: a half-written
outbox would lose exactly the reports it exists to keep.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

# Enough to cover any realistic outage. A robot reporting every step of a long
# route for a day offline is a few thousand entries at most.
OUTBOX_LIMIT = 5000
# How many finished runs to remember. A run is only ever offered back by the
# server while it is still live there, which is minutes to hours, not weeks.
FINISHED_LIMIT = 200

TERMINAL_STATES = ("done", "failed", "canceled")


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(path.name + ".tmp")
    with open(staging, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=1, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    staging.replace(path)


def _read_json(path: Path, default):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default
    except (OSError, ValueError):
        # A corrupt file is treated as missing rather than crashing the agent:
        # the server still holds the truth, and the next good read rewrites it.
        return default


class AgentState:
    """Files under one directory, one per concern."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        # The run thread reports while the sync timer flushes; both touch the
        # outbox, and a lost update there is a lost report. Re-entrant so a
        # `send` passed to flush() may itself read the state without deadlock.
        self._lock = threading.RLock()

    # ── Registry snapshot ────────────────────────────────────────────────────

    @property
    def _registry_path(self) -> Path:
        return self.directory / "registry.json"

    def save_registry(self, *, active_map_id, desired_mode, map_record=None) -> None:
        """
        Record the last registry reading that succeeded.

        `map_record` is the map's registry row (id, file names, content hash).
        It is kept with the assignment so a cached map can be checked against
        the hash it was recorded with before a robot navigates on it.
        """
        current = self.load_registry() or {}
        if map_record is None and current.get("map_record", {}).get("id") == active_map_id:
            # The assignment was re-read without the map: keep the map we had.
            map_record = current.get("map_record")
        _write_json(
            self._registry_path,
            {
                "active_map_id": active_map_id,
                "desired_mode": desired_mode,
                "map_record": map_record,
                "saved_at": time.time(),
            },
        )

    def load_registry(self) -> dict | None:
        value = _read_json(self._registry_path, None)
        return value if isinstance(value, dict) else None

    # ── Stations ─────────────────────────────────────────────────────────────

    def _stations_path(self, map_id: str) -> Path:
        return self.directory / f"stations_{map_id}.json"

    def save_stations(self, map_id: str, stations: list) -> None:
        _write_json(self._stations_path(map_id), list(stations))

    def load_stations(self, map_id: str) -> list:
        value = _read_json(self._stations_path(map_id), [])
        return value if isinstance(value, list) else []

    # ── Run report outbox ────────────────────────────────────────────────────

    @property
    def _outbox_path(self) -> Path:
        return self.directory / "outbox.json"

    def _read_outbox(self) -> list:
        value = _read_json(self._outbox_path, [])
        return value if isinstance(value, list) else []

    def enqueue(self, run_id: str, patch: dict) -> None:
        """Keep a report for later, after everything already waiting."""
        with self._lock:
            items = self._read_outbox()
            items.append({"run_id": run_id, "patch": dict(patch), "queued_at": time.time()})
            # Oldest progress goes first if the limit is ever hit; terminal
            # reports are never dropped, because they are the ones that stop a
            # run being executed again.
            while len(items) > OUTBOX_LIMIT:
                for index, item in enumerate(items):
                    if item["patch"].get("state") not in TERMINAL_STATES:
                        del items[index]
                        break
                else:
                    break
            _write_json(self._outbox_path, items)

    def pending(self) -> list:
        with self._lock:
            return self._read_outbox()

    def pending_count(self) -> int:
        """
        How many reports are waiting, without waiting for a flush in progress.

        For status displays. Lock-free is safe because the file is only ever
        replaced whole: a reader sees the old list or the new one.
        """
        return len(self._read_outbox())

    def has_pending(self) -> bool:
        return bool(self.pending())

    def has_pending_for(self, run_id: str) -> bool:
        return any(item.get("run_id") == run_id for item in self.pending())

    def flush(self, send) -> tuple[int, bool]:
        """
        Send waiting reports in order until one cannot be sent.

        `send(run_id, patch)` returns "sent", "drop" (the server refused it for
        good — the run ended or no longer exists) or "retry" (the server is
        unreachable; stop and keep the rest). Returns how many were removed and
        whether the outbox is now empty.

        In order, and stopping at the first retry: progress applied out of
        order would put a run back on a step it has already passed.
        """
        with self._lock:
            items = self._read_outbox()
            removed = 0
            while items:
                item = items[0]
                outcome = send(item["run_id"], item["patch"])
                if outcome == "retry":
                    break
                items.pop(0)
                removed += 1
            if removed:
                _write_json(self._outbox_path, items)
            return removed, not items

    # ── Finished runs ────────────────────────────────────────────────────────

    @property
    def _finished_path(self) -> Path:
        return self.directory / "finished_runs.json"

    def mark_finished(self, run_id: str, patch: dict) -> None:
        """
        Remember that this robot ended a run, and how.

        Written before the report is sent, so a crash between the two still
        leaves the robot knowing it must not drive the route again.
        """
        with self._lock:
            finished = _read_json(self._finished_path, {})
            if not isinstance(finished, dict):
                finished = {}
            finished[run_id] = {"patch": dict(patch), "at": time.time()}
            if len(finished) > FINISHED_LIMIT:
                oldest = sorted(finished, key=lambda key: finished[key].get("at", 0))
                for key in oldest[: len(finished) - FINISHED_LIMIT]:
                    del finished[key]
            _write_json(self._finished_path, finished)

    def finished(self, run_id: str) -> dict | None:
        """The final report this robot made for a run, or None if it never ended one."""
        finished = _read_json(self._finished_path, {})
        if not isinstance(finished, dict):
            return None
        entry = finished.get(run_id)
        return dict(entry["patch"]) if isinstance(entry, dict) and "patch" in entry else None
