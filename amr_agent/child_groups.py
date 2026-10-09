"""
The process groups the agent started, written down so the next agent can stop them.

The agent runs each stack (`ros2 launch`, zone_mask_server) in a session of its
own, so the whole tree can be signalled at once. The other side of that is that
nothing stops the tree when the agent dies without cleaning up — a closed
terminal, a `kill`, a crash. The stack lives on with nobody to stop it, and the
next agent starts a second one next to it: two Nav2s with the same node names,
where the new one fails to come up ("Failed to change state for node:
planner_server") and the old one quietly drives the robot on the goals the new
one rejected.

So every group the agent starts is recorded here, and an agent that starts up
stops whatever the previous one left behind before it starts anything of its own.

A recorded group is only signalled when it is provably the one recorded: same
boot, and its leader, if still alive, started at the recorded time. A process ID
is reused once its process is gone, and the agent must never signal some other
program that happens to have been given the same number.

No ROS imports, on purpose: this is plain process handling, tested without a robot.
"""

from __future__ import annotations

import json
import os
import signal
import time
from pathlib import Path

RECORD_NAME = "children.json"

# SIGINT first: ros2 launch treats it as a shutdown request and lets its children
# exit cleanly, which matters for anything holding a map file. Then SIGTERM, then
# SIGKILL: an orphaned stack would hold the topics the next mode needs.
STOP_STEPS = ((signal.SIGINT, 8.0), (signal.SIGTERM, 4.0))
KILL_WAIT_S = 5.0
POLL_S = 0.2


def boot_id() -> str | None:
    """This boot's id; a group recorded in another boot is long gone."""
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return None


def start_ticks(pid: int) -> int | None:
    """When the process started, in clock ticks since boot, or None if it is gone."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    # The command name is in parentheses and may itself hold spaces or ")", so
    # count fields from the last ")". starttime is field 22; the text after ")"
    # begins at field 3.
    fields = stat[stat.rfind(")") + 2 :].split()
    try:
        return int(fields[19])
    except (IndexError, ValueError):
        return None


def group_alive(pgid: int) -> bool:
    """True while any process is left in the group."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Someone else's group: alive, but not one the agent may touch.
        return True
    return True


def stop_group(pgid: int, steps=STOP_STEPS, kill_wait: float = KILL_WAIT_S) -> str:
    """
    Stop every process in a group, politely first.

    Returns how it ended: "gone" (nothing was left to stop), "stopped" (it exited
    on SIGINT or SIGTERM), "killed" (it needed SIGKILL) or "stuck" (still there
    after SIGKILL — unkillable, or not ours to signal).

    Waits on the group, not on its leader: `ros2 launch` exiting first must not
    leave its children running.
    """
    if not group_alive(pgid):
        return "gone"
    for sig, grace in steps:
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return "stopped"
        except PermissionError:
            return "stuck"
        if _wait_gone(pgid, grace):
            return "stopped"
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return "stopped"
    except PermissionError:
        return "stuck"
    return "killed" if _wait_gone(pgid, kill_wait) else "stuck"


def _wait_gone(pgid: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        _reap(pgid)
        if not group_alive(pgid):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(POLL_S)


def _reap(pid: int) -> None:
    """
    Collect the group's leader if it is our own child and has exited.

    A child of this process that exited stays a zombie until waited on, and a
    zombie still counts as a member of its group: without this, a group the
    agent itself started would look alive until SIGKILL and past it. Only that
    one process is waited on: waiting on any child would take the exit status
    from under a subprocess.run elsewhere in the agent, which then reads as 0.
    """
    try:
        os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass


class ChildGroups:
    """The groups this agent has running, in a file next to its other state."""

    def __init__(self, directory: Path) -> None:
        self._path = Path(directory) / RECORD_NAME

    def _read(self) -> dict:
        try:
            value = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            # Unreadable is treated as empty: a group it named would then be left
            # running, which is what happened before this file existed, and no
            # worse.
            return {}
        return value if isinstance(value, dict) else {}

    def _write(self, entries: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        staging = self._path.with_name(self._path.name + ".tmp")
        with open(staging, "w", encoding="utf-8") as handle:
            json.dump(entries, handle, indent=1, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        staging.replace(self._path)

    def record(self, name: str, pid: int) -> None:
        """Note a group just started; `pid` leads it (start_new_session=True)."""
        entries = self._read()
        entries[name] = {"pgid": int(pid), "start": start_ticks(pid), "boot": boot_id()}
        self._write(entries)

    def forget(self, name: str) -> None:
        """The group was stopped: there is nothing to clean up after it."""
        entries = self._read()
        if entries.pop(name, None) is not None:
            self._write(entries)

    def leftovers(self) -> dict[str, int]:
        """
        Recorded groups still running that are provably the ones recorded.

        By name, to the group id to stop.
        """
        current_boot = boot_id()
        found = {}
        for name, entry in self._read().items():
            if not isinstance(entry, dict):
                continue
            try:
                pgid = int(entry["pgid"])
            except (KeyError, TypeError, ValueError):
                continue
            if pgid <= 1 or entry.get("boot") != current_boot or current_boot is None:
                continue
            if not group_alive(pgid):
                continue
            leader_start = start_ticks(pgid)
            # The leader may have exited and left its children in the group;
            # that is still our group, because Linux does not hand out a number
            # that is still some group's id. A living leader, though, must be
            # the very process recorded and not one that reused its number.
            if leader_start is not None and leader_start != entry.get("start"):
                continue
            found[name] = pgid
        return found

    def stop_leftovers(self, stop=stop_group) -> dict[str, str]:
        """
        Stop what a previous agent left running; by name, how each one ended.

        The record is cleared afterwards whatever happened: a group that could
        not be stopped is reported once, not on every start from now on.
        """
        outcomes = {name: stop(pgid) for name, pgid in self.leftovers().items()}
        self._write({})
        return outcomes
