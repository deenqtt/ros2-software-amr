"""Request-scoped dependencies."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request


def get_connection(request: Request) -> Iterator[sqlite3.Connection]:
    """
    One connection per request.

    SQLite connections are not safe to share across threads, and FastAPI runs
    sync endpoints in a thread pool — so a single app-wide connection would be
    a race waiting to happen.
    """
    settings = request.app.state.settings
    from app.db import connect

    connection = connect(settings.db_path)
    try:
        yield connection
    finally:
        connection.close()


# Use this in signatures instead of `= Depends(get_connection)`: a default
# argument that calls a function is evaluated once at import time in ordinary
# Python, and writing it as an annotation keeps the dependency where a reader
# expects to find it.
Connection = Annotated[sqlite3.Connection, Depends(get_connection)]
