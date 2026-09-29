"""
Run the server:

    python -m app

Host, port and reload come from the environment, so the command is the same in
development and in a container — only the .env differs.
"""

from __future__ import annotations

import argparse
import sys

import uvicorn

from app.config import get_settings


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()

    parser = argparse.ArgumentParser(prog="python -m app", description="Run the AMR backend.")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Restart on source changes. Development only.",
    )
    args = parser.parse_args(argv)

    try:
        settings.validate_for_runtime()
    except ValueError as error:
        # Fail on the configuration, before binding a port and looking healthy.
        print(f"Refusing to start: {error}", file=sys.stderr)
        return 1

    print(f"AMR backend  →  http://{args.host}:{args.port}  ({settings.env})")
    print(f"API docs     →  http://{args.host}:{args.port}/docs")

    # An import string rather than the app object: uvicorn's reloader has to be
    # able to re-import the module in a fresh process.
    uvicorn.run("app.asgi:app", host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
