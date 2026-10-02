"""
Minimal HTTP client for the AMR backend, written against the standard library.

`requests` is not installed in the robot image and cannot be added without
rebuilding it, so this uses urllib directly — including a hand-rolled multipart
encoder, which is the only genuinely fiddly part.

Every call has a timeout. A robot agent that blocks forever on a server that
stopped answering is worse than one that fails: the failure is visible and
retried, the block is silent and permanent.
"""

from __future__ import annotations

import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass

DEFAULT_TIMEOUT_S = 15.0
UPLOAD_TIMEOUT_S = 120.0


class BackendError(Exception):
    """A request reached the server and was refused, or never arrived."""

    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status

    @property
    def is_offline(self) -> bool:
        """status 0 means the request never reached the server."""
        return self.status == 0

    @property
    def is_not_found(self) -> bool:
        return self.status == 404


@dataclass(frozen=True)
class DownloadedFile:
    data: bytes
    content_hash: str | None


def _encode_multipart(
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes]],
) -> tuple[bytes, str]:
    """Encode form fields and files as multipart/form-data."""
    boundary = f"----amr{uuid.uuid4().hex}"
    parts: list[bytes] = []

    for name, value in fields.items():
        if value is None:
            continue
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )

    for name, (filename, data) in files.items():
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n".encode()
        )
        parts.append(data)
        parts.append(b"\r\n")

    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class BackendClient:
    """
    Talks to the backend on behalf of one robot.

    Deliberately synchronous: it is called from the agent's worker threads, not
    from a ROS callback, so blocking is contained.
    """

    def __init__(self, base_url: str, robot_id: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.robot_id = robot_id

    # ── plumbing ──────────────────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        content_type: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> tuple[bytes, dict[str, str]]:
        url = f"{self.base_url}{path}"
        request = urllib.request.Request(url, data=body, method=method)  # noqa: S310 — http(s) only, url built from config
        if content_type:
            request.add_header("Content-Type", content_type)

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                return response.read(), {k.lower(): v for k, v in response.headers.items()}
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:500]
            raise BackendError(f"{method} {path} -> {error.code}: {detail}", error.code) from error
        except urllib.error.URLError as error:
            raise BackendError(f"{method} {path} -> unreachable: {error.reason}", 0) from error
        except TimeoutError as error:
            raise BackendError(f"{method} {path} -> timed out after {timeout:.0f}s", 0) from error

    def _get_json(self, path: str) -> object:
        raw, _ = self._request("GET", path)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as error:
            raise BackendError(f"GET {path} -> response was not JSON") from error

    # ── endpoints ─────────────────────────────────────────────────────────────

    def health(self) -> bool:
        try:
            self._get_json("/ready")
            return True
        except BackendError:
            return False

    def get_robot(self, robot_id: str | None = None) -> dict:
        target = robot_id or self.robot_id
        result = self._get_json(f"/api/robots/{urllib.parse.quote(target)}")
        if not isinstance(result, dict):
            raise BackendError("robot response was not an object")
        return result

    def get_map(self, map_id: str) -> dict:
        result = self._get_json(f"/api/maps/{urllib.parse.quote(map_id)}")
        if not isinstance(result, dict):
            raise BackendError("map response was not an object")
        return result

    def list_zones(self, map_id: str) -> list[dict]:
        """
        Zones registered against one map.

        Polygons, not the rasterised mask: the mask belongs to one resolution
        and cannot be edited back into corners, so the robot builds it from the
        points when it pushes them to the filters.
        """
        result = self._get_json(f"/api/zones?map_id={urllib.parse.quote(map_id)}")
        if not isinstance(result, list):
            raise BackendError("zone response was not a list")
        return [row for row in result if isinstance(row, dict)]

    def get_active_run(self, robot_id: str | None = None) -> dict | None:
        """
        The run this robot should be executing, or None when it is idle.

        Also how an agent that has just restarted discovers it was in the middle
        of something: the lap and step live on the server, not in this process.
        """
        target = robot_id or self.robot_id
        result = self._get_json(f"/api/robots/{urllib.parse.quote(target)}/run")
        if result is None:
            return None
        if not isinstance(result, dict):
            raise BackendError("run response was not an object")
        return result

    def report_run(self, run_id: str, patch: dict) -> dict:
        """Write back progress, or a terminal state."""
        body = json.dumps(patch).encode()
        raw, _ = self._request(
            "PATCH",
            f"/api/runs/{urllib.parse.quote(run_id)}",
            body=body,
            content_type="application/json",
        )
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise BackendError("run update response was not an object")
        return result

    def list_stations(self, map_id: str) -> list[dict]:
        """
        Stations registered against one map.

        Scoped to a map because a station's coordinates only mean anything in
        that map's frame; pushing another map's poses would register real
        station names at places that do not exist here.
        """
        result = self._get_json(f"/api/stations?map_id={urllib.parse.quote(map_id)}")
        if not isinstance(result, list):
            raise BackendError("station response was not a list")
        return [row for row in result if isinstance(row, dict)]

    def assign_map(self, map_id: str | None, robot_id: str | None = None) -> dict:
        """
        Point a robot at a map. None clears the assignment.

        The robot that just surveyed a map already holds its bytes, so claiming
        it costs one request and no download.
        """
        target = robot_id or self.robot_id
        body = json.dumps({"map_id": map_id}).encode()
        raw, _ = self._request(
            "PUT",
            f"/api/robots/{urllib.parse.quote(target)}/map",
            body=body,
            content_type="application/json",
        )
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise BackendError("assignment response was not an object")
        return result

    def set_desired_mode(self, mode: str, robot_id: str | None = None) -> dict:
        """
        Record what this robot is supposed to be doing.

        The registry is where intent lives, so a mode asked for over
        /robot_mode has to land here too. Without this the sync loop reads the
        old intent back and undoes the switch a few seconds later, which looks
        like the robot changing its mind on its own.

        `mode` is the registry's vocabulary, not the service's — see
        MODE_TO_REGISTRY in robot_agent_node.py.
        """
        target = robot_id or self.robot_id
        body = json.dumps({"desired_mode": mode}).encode()
        raw, _ = self._request(
            "PUT",
            f"/api/robots/{urllib.parse.quote(target)}/mode",
            body=body,
            content_type="application/json",
        )
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise BackendError("mode response was not an object")
        return result

    def download_map_file(self, map_id: str, which: str) -> DownloadedFile:
        """Fetch one half of a map pair. `which` is 'yaml' or 'image'."""
        data, headers = self._request(
            "GET",
            f"/api/maps/{urllib.parse.quote(map_id)}/files/{which}",
            timeout=UPLOAD_TIMEOUT_S,
        )
        return DownloadedFile(data=data, content_hash=headers.get("x-content-hash"))

    def upload_map(
        self,
        name: str,
        yaml_bytes: bytes,
        image_bytes: bytes,
        image_filename: str,
        note: str | None = None,
    ) -> dict:
        """
        Publish a map pair to the registry.

        Safe to retry: the backend returns the existing version when the image
        hash already exists under that name, so a redelivery after a dropped
        connection does not leave a trail of identical versions.
        """
        fields = {"name": name}
        if self.robot_id:
            fields["robot_id"] = self.robot_id
        if note:
            fields["note"] = note

        body, content_type = _encode_multipart(
            fields,
            {
                "yaml_file": ("map.yaml", yaml_bytes),
                "image_file": (image_filename, image_bytes),
            },
        )
        raw, _ = self._request(
            "POST", "/api/maps", body=body, content_type=content_type, timeout=UPLOAD_TIMEOUT_S
        )
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as error:
            raise BackendError("upload response was not JSON") from error
        if not isinstance(result, dict):
            raise BackendError("upload response was not an object")
        return result
