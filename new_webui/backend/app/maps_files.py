"""
Map file handling.

A ROS map is a *pair*: a `.yaml` describing the grid, and an image holding the
occupancy values. The yaml refers to the image by relative filename, so the two
cannot be stored or moved independently — a yaml whose `image:` field points at
a name that is not there produces a map_server that starts and then fails, and
that failure reads to an operator as a broken robot.

Everything that knows about that coupling lives here.
"""

from __future__ import annotations

import contextlib
import hashlib
import math
import os
import re
import secrets
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

# Canonical names inside a map's directory. The originals are discarded: their
# only job was to point at each other, and after ingest that is this pair.
YAML_NAME = "map.yaml"

ALLOWED_IMAGE_SUFFIXES = {".pgm", ".png"}
# Real map yamls are a few hundred bytes. The cap bounds what yaml.safe_load is
# asked to chew on: a small file can still nest deeply enough to exhaust the
# parser's stack.
MAX_YAML_BYTES = 64 * 1024
# 32 MiB is a 5600 x 5600 cell PGM: a 280 m square at 5 cm, far beyond any
# warehouse this system maps, yet small enough that a few concurrent uploads
# cannot exhaust memory.
MAX_IMAGE_BYTES = 32 * 1024 * 1024


class MapFormatError(ValueError):
    """The uploaded pair is not a usable ROS map."""


@dataclass(frozen=True)
class MapMetadata:
    """The fields the UI needs without downloading the image."""

    resolution: float | None
    origin_x: float | None
    origin_y: float | None
    origin_yaw: float | None
    negate: int | None
    occupied_thresh: float | None
    free_thresh: float | None
    width: int | None
    height: int | None


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _as_float(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        result = float(value)
        # NaN and infinity survive yaml.safe_load and then poison every
        # downstream calculation silently.
        return result if math.isfinite(result) else None
    return None


# The three values nav2's map_saver writes, and the only three this system
# produces. See CANONICAL_VALUES below for why anything else is a defect.
OCCUPIED_VALUE = 0
UNKNOWN_VALUE = 205
FREE_VALUE = 254
CANONICAL_VALUES = frozenset({OCCUPIED_VALUE, UNKNOWN_VALUE, FREE_VALUE})

# How many offending values to name in an error. Enough to recognise the cause,
# short enough to read.
_MAX_REPORTED_VALUES = 8


@dataclass(frozen=True)
class PgmHeader:
    """A parsed PGM header and where the pixel data starts."""

    magic: bytes
    width: int
    height: int
    max_value: int
    pixel_offset: int


def _parse_pgm_header(data: bytes) -> PgmHeader | None:
    """
    Read a PGM header, or None when this is not a PGM.

    Written against the bytes rather than a path so an upload can be validated
    before anything is committed to disk. Handles both P5 (binary) and P2
    (ASCII), because GIMP's export dialog offers the choice and operators do
    pick ASCII.
    """
    if not data.startswith((b"P5", b"P2")):
        return None

    tokens: list[bytes] = []
    index = 2
    # Three tokens: width, height, max value. A comment may sit between any two.
    while len(tokens) < 3 and index < len(data):
        byte = data[index : index + 1]
        if byte == b"#":  # comment runs to end of line
            newline = data.find(b"\n", index)
            index = len(data) if newline == -1 else newline + 1
            continue
        if byte.isspace():
            index += 1
            continue
        end = index
        while end < len(data) and not data[end : end + 1].isspace():
            end += 1
        tokens.append(data[index:end])
        index = end

    try:
        width, height, max_value = (int(token) for token in tokens)
    except (IndexError, ValueError):
        return None
    if width <= 0 or height <= 0 or max_value <= 0:
        return None

    return PgmHeader(
        magic=data[:2],
        width=width,
        height=height,
        max_value=max_value,
        # Exactly one whitespace byte separates the header from binary pixel
        # data; for P2 the parser skips whitespace anyway.
        pixel_offset=index + 1,
    )


def read_pgm_size(data: bytes) -> tuple[int | None, int | None]:
    """Width and height from a PGM header, or (None, None)."""
    header = _parse_pgm_header(data)
    return (None, None) if header is None else (header.width, header.height)


def read_pgm_cells(data: bytes) -> bytes | None:
    """
    The occupancy bytes of a PGM, one per cell, or None when unreadable.

    P2 is expanded to the same one-byte-per-cell form, so callers never have to
    care which encoding arrived.
    """
    header = _parse_pgm_header(data)
    if header is None or header.max_value > 255:
        return None

    expected = header.width * header.height
    body = data[header.pixel_offset :]

    if header.magic == b"P5":
        return body[:expected] if len(body) >= expected else None

    try:
        values = [int(token) for token in body.split()]
    except ValueError:
        return None
    if len(values) < expected or any(value < 0 or value > 255 for value in values):
        return None
    return bytes(values[:expected])


def parse_map_yaml(raw: bytes) -> tuple[dict, MapMetadata]:
    """Parse a map yaml, returning the document and the fields we index."""
    if len(raw) > MAX_YAML_BYTES:
        raise MapFormatError(f"map yaml exceeds {MAX_YAML_BYTES // 1024} KiB")
    try:
        document = yaml.safe_load(raw)
    except yaml.YAMLError as error:
        raise MapFormatError(f"map yaml is not valid YAML: {error}") from error
    except RecursionError as error:
        # Deeply nested flow collections ("[[[[...") blow the parser's stack.
        raise MapFormatError("map yaml is nested too deeply") from error

    if not isinstance(document, dict):
        raise MapFormatError("map yaml must be a mapping")
    if "image" not in document:
        raise MapFormatError("map yaml has no 'image' field")

    origin = document.get("origin") or []
    if not isinstance(origin, list):
        origin = []

    def origin_at(index: int) -> float | None:
        return _as_float(origin[index]) if len(origin) > index else None

    negate = document.get("negate")
    negate_int = (
        int(negate)
        if isinstance(negate, (int, float)) and not isinstance(negate, bool)
        else None
    )
    metadata = MapMetadata(
        resolution=_as_float(document.get("resolution")),
        origin_x=origin_at(0),
        origin_y=origin_at(1),
        origin_yaw=origin_at(2),
        negate=negate_int,
        occupied_thresh=_as_float(document.get("occupied_thresh")),
        free_thresh=_as_float(document.get("free_thresh")),
        width=None,
        height=None,
    )
    return document, metadata


def rewrite_image_reference(document: dict, image_name: str) -> bytes:
    """
    Point the yaml at the image name we actually stored.

    This is the step whose absence breaks everything downstream: a map saved as
    `warehouse.pgm` and stored as `map.pgm` yields a yaml that map_server
    cannot resolve, on a robot, at the moment it is asked to navigate.
    """
    rewritten = dict(document)
    rewritten["image"] = image_name
    try:
        return yaml.safe_dump(rewritten, default_flow_style=False, sort_keys=False).encode()
    except RecursionError as error:
        raise MapFormatError("map yaml is nested too deeply") from error


def validate_pgm_cells(data: bytes) -> None:
    """
    Reject a PGM whose cells are not one of the three canonical values.

    A ROS occupancy map has three states, not a greyscale range: 0 occupied,
    205 unknown, 254 free. Everything between is *interpreted* through the
    yaml's thresholds, and the middle band lands on "unknown" — which a global
    costmap will not plan through.

    This matters because the usual way to tidy a map is to open it in GIMP,
    whose default brush is feathered. Every stroke then lays down a band of
    intermediate values along its edge. On screen that looks like a slightly
    soft line; on the robot it is a wall of unknown cells that Nav2 refuses to
    cross, and nothing in the file says anything is wrong.

    The margin is thinner than it looks. With this project's thresholds
    (occupied 0.65, free 0.196) the value 205 classifies as unknown by 0.000078
    — two percent of one greyscale step. Values chosen by eye do not survive
    that, so they are refused here rather than debugged on a robot.

    Only PGM is checked. PNG would need an image library the backend does not
    carry, so a PNG upload is trusted; see ALLOWED_IMAGE_SUFFIXES.
    """
    cells = read_pgm_cells(data)
    if cells is None:
        raise MapFormatError("image is not a readable PGM (expected P5 or P2)")

    offenders = sorted(set(cells) - CANONICAL_VALUES)
    if not offenders:
        return

    count = sum(1 for cell in cells if cell not in CANONICAL_VALUES)
    shown = ", ".join(str(value) for value in offenders[:_MAX_REPORTED_VALUES])
    if len(offenders) > _MAX_REPORTED_VALUES:
        shown += ", …"
    raise MapFormatError(
        f"{count} of {len(cells)} cells are not a valid occupancy value "
        f"(found {shown}; expected only {OCCUPIED_VALUE} occupied, "
        f"{UNKNOWN_VALUE} unknown, {FREE_VALUE} free). "
        "An image editor with antialiasing or a soft brush produces this; "
        "turn both off, or edit the map in the map editor."
    )


def validate_image(filename: str, data: bytes) -> str:
    """Check an uploaded image and return the suffix to store it under."""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_SUFFIXES:
        raise MapFormatError(
            f"image must be one of {sorted(ALLOWED_IMAGE_SUFFIXES)}, got '{suffix or filename}'"
        )
    if not data:
        raise MapFormatError("image is empty")
    if len(data) > MAX_IMAGE_BYTES:
        raise MapFormatError(f"image exceeds {MAX_IMAGE_BYTES // (1024 * 1024)} MB")
    return suffix


_SAFE_NAME = re.compile(r"^[\w][\w .\-]{0,63}$")


def validate_map_name(name: str) -> str:
    """
    Names are shown to operators and grouped into versions, so they are checked
    rather than sanitised: silently turning "Gudang A/B" into "Gudang A_B"
    produces a second map nobody meant to create.
    """
    cleaned = name.strip()
    if not cleaned:
        raise MapFormatError("map name is required")
    if not _SAFE_NAME.match(cleaned):
        raise MapFormatError(
            "map name may contain letters, digits, spaces, dots, hyphens and underscores"
        )
    return cleaned


def map_directory(maps_root: Path, map_id: str) -> Path:
    """
    One directory per map, named by id.

    The old layout put every map in one flat folder, so two robots each saving
    `map.pgm` would overwrite one another. An id-named directory makes that
    impossible without having to invent unique filenames.
    """
    return maps_root / map_id


class StagedFiles:
    """
    New contents for files in one directory, installed only on request.

    Replacing a map in place used to write straight over the live files and
    update the database row afterwards, so a failure in between left new bytes
    under an old content hash — or half a new pair next to an old yaml. This
    splits the replace into three steps a caller can order around its
    transaction:

    1. construction writes every file to a temp name in the *same* directory,
       so the later rename never crosses a filesystem;
    2. `install()` keeps a backup of each existing file (a hard link, so a
       concurrent download never sees the name missing) and renames the temp
       file into place with `os.replace`, which is atomic per file;
    3. `commit()` drops the backups, or `rollback()` puts them back and removes
       anything left over.

    Construction cleans up after itself if any write fails.
    """

    def __init__(self, directory: Path, files: dict[str, bytes]) -> None:
        self.directory = directory
        self._temps: dict[str, Path] = {}
        #: (final path, backup path or None when there was no previous file)
        self._installed: list[tuple[Path, Path | None]] = []
        try:
            directory.mkdir(parents=True, exist_ok=True)
            for name, data in files.items():
                handle, raw = tempfile.mkstemp(prefix=f".{name}.", suffix=".tmp", dir=directory)
                self._temps[name] = Path(raw)
                with os.fdopen(handle, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
        except BaseException:
            self._discard_temps()
            raise

    def _backup(self, final: Path) -> Path | None:
        if not final.exists():
            return None
        backup = final.with_name(f".{final.name}.{secrets.token_hex(6)}.bak")
        try:
            os.link(final, backup)
        except OSError:
            # A filesystem without hard links: a copy still restores correctly,
            # it just costs the bytes once more.
            shutil.copy2(final, backup)
        return backup

    def install(self) -> None:
        """Move every staged file into place. On failure, call `rollback()`."""
        for name, temp in list(self._temps.items()):
            final = self.directory / name
            backup = self._backup(final)
            try:
                os.replace(temp, final)
            except BaseException:
                if backup is not None:
                    backup.unlink(missing_ok=True)
                raise
            del self._temps[name]
            self._installed.append((final, backup))

    def rollback(self) -> None:
        """Restore what was there before `install()`, and remove the temps."""
        for final, backup in reversed(self._installed):
            with contextlib.suppress(OSError):
                if backup is None:
                    final.unlink(missing_ok=True)
                else:
                    os.replace(backup, final)
        self._installed.clear()
        self._discard_temps()

    def commit(self) -> None:
        """Keep the installed files and drop the backups."""
        for _final, backup in self._installed:
            if backup is not None:
                with contextlib.suppress(OSError):
                    backup.unlink(missing_ok=True)
        self._installed.clear()
        self._discard_temps()

    def _discard_temps(self) -> None:
        for temp in self._temps.values():
            with contextlib.suppress(OSError):
                temp.unlink(missing_ok=True)
        self._temps.clear()
