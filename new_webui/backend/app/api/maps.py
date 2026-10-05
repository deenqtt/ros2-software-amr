"""
Map registry endpoints.

The backend owns maps; robots keep a local cache and pull when told to. A map
is still born on the robot — slam_toolbox writes it to the robot's own disk, so
a survey survives the server being unreachable — and is published here
afterwards.

Nothing in here mutates on a read. The previous backend's `GET /api/maps`
scanned the filesystem and deleted rows whose file had gone, which through
ON DELETE CASCADE destroyed every keepout zone, dock and destination attached
to that map. An engineer renaming a `.yaml` lost an operator's work.
"""

from __future__ import annotations

import io
import shutil
import sqlite3
import zipfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import Connection
from app.auth import Admin, AdminOrAgent, Reader
from app.db import transaction
from app.maps_files import (
    YAML_NAME,
    MapFormatError,
    map_directory,
    parse_map_yaml,
    read_pgm_size,
    rewrite_image_reference,
    sha256_of,
    validate_image,
    validate_map_name,
    validate_pgm_cells,
)
from app.repositories import maps as repo
from app.repositories import robots as robots_repo
from app.repositories import stations as stations_repo
from app.schemas.map import MapOut, MapRenameIn

router = APIRouter(prefix="/api/maps", tags=["maps"], dependencies=[Reader])


def _to_out(row: sqlite3.Row) -> MapOut:
    return MapOut.model_validate(dict(row))


def _maps_root(request: Request) -> Path:
    return Path(request.app.state.settings.maps_dir)


@router.get("", response_model=list[MapOut])
def list_maps(connection: Connection) -> list[MapOut]:
    return [_to_out(row) for row in repo.list_maps(connection)]


@router.get("/{map_id}", response_model=MapOut)
def get_map(map_id: str, connection: Connection) -> MapOut:
    row = repo.get_map(connection, map_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Map not found")
    return _to_out(row)


@router.post(
    "",
    response_model=MapOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminOrAgent],
)
async def create_map(
    request: Request,
    connection: Connection,
    name: Annotated[str, Form()],
    yaml_file: Annotated[UploadFile, File()],
    image_file: Annotated[UploadFile, File()],
    robot_id: Annotated[str | None, Form()] = None,
    note: Annotated[str | None, Form()] = None,
) -> MapOut:
    """
    Publish a map pair.

    Used both by an operator uploading by hand and by a robot agent after a
    survey. Saving an unchanged image under the same name returns the existing
    version rather than manufacturing one that differs in nothing but its
    number.
    """
    try:
        clean_name = validate_map_name(name)
        yaml_bytes = await yaml_file.read()
        image_bytes = await image_file.read()
        suffix = validate_image(image_file.filename or "", image_bytes)
        # PGM only: PNG would need an image library the backend does not carry.
        if suffix == ".pgm":
            validate_pgm_cells(image_bytes)
        document, metadata = parse_map_yaml(yaml_bytes)
    except MapFormatError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error

    if robot_id is not None and robots_repo.get_robot(connection, robot_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Robot not found: {robot_id}")

    content_hash = sha256_of(image_bytes)
    existing = repo.find_by_hash(connection, clean_name, content_hash)
    if existing is not None:
        # Idempotent: an agent retrying an upload after a dropped connection
        # must not leave a trail of identical versions behind it.
        return _to_out(existing)

    image_name = f"map{suffix}"
    width, height = read_pgm_size(image_bytes) if suffix == ".pgm" else (None, None)

    payload = {
        "name": clean_name,
        "content_hash": content_hash,
        "yaml_file": YAML_NAME,
        "image_file": image_name,
        "image_bytes": len(image_bytes),
        "resolution": metadata.resolution,
        "width": metadata.width or width,
        "height": metadata.height or height,
        "origin_x": metadata.origin_x,
        "origin_y": metadata.origin_y,
        "origin_yaw": metadata.origin_yaw,
        "negate": metadata.negate,
        "occupied_thresh": metadata.occupied_thresh,
        "free_thresh": metadata.free_thresh,
        "created_by_robot_id": robot_id,
        "note": note,
    }

    with transaction(connection):
        row = repo.create_map(connection, payload)

    # Files are written after the row commits, so a crash leaves an orphaned
    # row rather than orphaned bytes: a row with no files is visible and
    # fixable, files with no row are invisible and accumulate forever.
    directory = map_directory(_maps_root(request), row["id"])
    try:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / image_name).write_bytes(image_bytes)
        (directory / YAML_NAME).write_bytes(rewrite_image_reference(document, image_name))
    except OSError as error:
        with transaction(connection):
            repo.delete_map(connection, row["id"])
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(
            status.HTTP_507_INSUFFICIENT_STORAGE, f"Could not store map files: {error}"
        ) from error

    return _to_out(row)


@router.get("/{map_id}/files/{which}")
def download_map_file(map_id: str, which: str, request: Request, connection: Connection):
    """
    Serve one half of the pair.

    This is how a robot fetches a map it does not have. Downloading over HTTP
    rather than reading a shared mount is deliberate: an AMR roams on wifi, and
    a hung NFS mount blocks map_server in uninterruptible sleep at exactly the
    moment it is asked to navigate.
    """
    if which not in ("yaml", "image"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expected 'yaml' or 'image'")

    row = repo.get_map(connection, map_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Map not found")

    filename = row["yaml_file"] if which == "yaml" else row["image_file"]
    path = map_directory(_maps_root(request), map_id) / filename
    if not path.is_file():
        raise HTTPException(
            status.HTTP_410_GONE,
            f"Map {map_id} is registered but its {which} file is missing on disk",
        )

    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=f"{row['name']}_v{row['version']}_{filename}",
        headers={
            "X-Content-Hash": row["content_hash"],
            # A map version can be replaced in place. The URL deliberately
            # remains stable so assignments survive, so clients must not keep
            # the old bytes after a successful replace.
            "Cache-Control": "no-store, must-revalidate",
            "Pragma": "no-cache",
        },
    )


@router.patch("/{map_id}", response_model=MapOut, dependencies=[Admin])
def rename_map(map_id: str, body: MapRenameIn, connection: Connection) -> MapOut:
    """
    Rename a map.

    The name is the lineage key — "Warehouse A" v1, v2, v3 are one map with
    three versions — so this renames every version, not just the row addressed.
    Renaming one version would split the lineage and leave the new name starting
    at whatever version number that row happened to hold.

    Nothing on disk moves. Directories are named by id and robots reference a
    map by id, so a rename cannot detach a robot from the map it is running.
    """
    row = repo.get_map(connection, map_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Map not found")

    try:
        clean_name = validate_map_name(body.name)
    except MapFormatError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error

    if clean_name == row["name"]:
        return _to_out(row)

    try:
        with transaction(connection):
            repo.rename_lineage(connection, row["name"], clean_name)
    except repo.MapNameTakenError as error:
        # 409, not 422: the name is well-formed, it is merely taken. Merging two
        # lineages is not a rename — the version numbers would collide — so this
        # refuses rather than guessing at a renumbering.
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error

    renamed = repo.get_map(connection, map_id)
    if renamed is None:  # pragma: no cover — existence was just checked
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Map not found")
    return _to_out(renamed)


@router.put("/{map_id}/image", response_model=MapOut, dependencies=[Admin])
async def replace_map_image(
    map_id: str,
    request: Request,
    connection: Connection,
    yaml_file: Annotated[UploadFile, File()],
    image_file: Annotated[UploadFile, File()],
    note: Annotated[str | None, Form()] = None,
) -> MapOut:
    """
    Replace this version's contents, keeping its id, name and version number.

    Publishing a new version is the safer default and what the UI offers first.
    This exists because an operator correcting an obvious mistake does not always
    want a second row, and that is a legitimate call to make.

    What it costs: the previous contents are gone. There is nothing to reassign a
    robot back to if the correction turns out to be wrong.

    Response headers name the robots currently assigned, so a caller can report
    what it just changed underneath them.
    """
    row = repo.get_map(connection, map_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Map not found")

    try:
        yaml_bytes = await yaml_file.read()
        image_bytes = await image_file.read()
        suffix = validate_image(image_file.filename or "", image_bytes)
        if suffix == ".pgm":
            validate_pgm_cells(image_bytes)
        document, metadata = parse_map_yaml(yaml_bytes)
    except MapFormatError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from error

    width, height = read_pgm_size(image_bytes) if suffix == ".pgm" else (None, None)
    image_name = f"map{suffix}"
    payload = {
        "content_hash": sha256_of(image_bytes),
        "image_file": image_name,
        "image_bytes": len(image_bytes),
        "resolution": metadata.resolution,
        "width": metadata.width or width,
        "height": metadata.height or height,
        "origin_x": metadata.origin_x,
        "origin_y": metadata.origin_y,
        "origin_yaw": metadata.origin_yaw,
        "negate": metadata.negate,
        "occupied_thresh": metadata.occupied_thresh,
        "free_thresh": metadata.free_thresh,
        # The note describes the contents, and the contents just changed.
        "note": note,
    }

    directory = map_directory(_maps_root(request), map_id)
    previous_image = str(row["image_file"])
    try:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / image_name).write_bytes(image_bytes)
        (directory / YAML_NAME).write_bytes(rewrite_image_reference(document, image_name))
        # A format change leaves the old file behind, still referenced by nothing.
        if previous_image != image_name:
            (directory / previous_image).unlink(missing_ok=True)
    except OSError as error:
        raise HTTPException(
            status.HTTP_507_INSUFFICIENT_STORAGE, f"Could not store map files: {error}"
        ) from error

    with transaction(connection):
        updated = repo.replace_image(connection, map_id, payload)

    return _to_out(updated)


@router.get("/{map_id}/archive")
def download_map_archive(map_id: str, request: Request, connection: Connection) -> Response:
    """
    Serve both halves of the pair as one zip.

    A map is a yaml and an image, and the yaml refers to the image by filename.
    Handing out either half alone produces a file that looks like a map and
    cannot be loaded, so the operator-facing download is the pair — stored under
    the names the yaml already uses, so it works unzipped into any directory.

    The robot fetches halves individually via /files/{which}: it caches them
    under known names and has no use for an archive it would only unpack again.
    """
    row = repo.get_map(connection, map_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Map not found")

    directory = map_directory(_maps_root(request), map_id)
    members = [row["yaml_file"], row["image_file"]]
    missing = [name for name in members if not (directory / name).is_file()]
    if missing:
        raise HTTPException(
            status.HTTP_410_GONE,
            f"Map {map_id} is registered but missing on disk: {', '.join(missing)}",
        )

    # Built in memory: a map is tens of kilobytes, and a temp file would have to
    # be cleaned up on every error path here.
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in members:
            archive.write(directory / name, arcname=name)

    stem = f"{row['name']}_v{row['version']}".replace(" ", "_")
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{stem}.zip"',
            "X-Content-Hash": row["content_hash"],
        },
    )


@router.delete("/{map_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Admin])
def delete_map(map_id: str, request: Request, connection: Connection) -> Response:
    if repo.get_map(connection, map_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Map not found")

    try:
        with transaction(connection):
            repo.delete_map(connection, map_id)
    except repo.MapInUseError as error:
        # 409, not 403: the request is well-formed and would be legal once the
        # robots are moved off it.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "message": str(error),
                "robots": error.robot_names,
                "missions": error.mission_names,
            },
        ) from error

    shutil.rmtree(map_directory(_maps_root(request), map_id), ignore_errors=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{map_id}/stations/count")
def count_map_stations(map_id: str, connection: Connection) -> dict[str, int]:
    """
    How many stations go with this map if it is deleted.

    Deleting a map cascades to its stations, and a site's whole layout
    disappearing without warning is not something to discover afterwards. The
    delete confirmation reads this so it can say what else is at stake.
    """
    if repo.get_map(connection, map_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Map not found")
    return {"stations": stations_repo.count_for_map(connection, map_id)}
