"""
Run the server:

    python -m app

Create a super admin, or reset one's password, on the server itself:

    python -m app create-admin <username>

Host, port and reload come from the environment, so the command is the same in
development and in a container — only the .env differs.
"""

from __future__ import annotations

import argparse
import getpass
import sys

import uvicorn

from app.config import Settings, get_settings


def create_admin(settings: Settings, username: str, *, reset: bool) -> int:
    """
    Make a super admin account from a shell on the server.

    The only way to get the first account, by design: whoever can run this
    already controls the machine, so it cannot be used to gain anything — unlike
    a default password or a sign-up page reachable from the plant network.
    """
    from app.db import connect, migrate, transaction
    from app.repositories import users as users_repo
    from app.schemas.user import USERNAME_PATTERN
    from app.security import hash_password, password_problem

    if not USERNAME_PATTERN.match(username):
        print("Username: 3 to 32 letters, digits, dots, dashes or underscores.", file=sys.stderr)
        return 2

    password = getpass.getpass(f"Password for {username}: ")
    problem = password_problem(password, username)
    if problem:
        print(f"{problem}.", file=sys.stderr)
        return 2
    if getpass.getpass("Again: ") != password:
        print("The passwords do not match.", file=sys.stderr)
        return 2

    connection = connect(settings.db_path)
    try:
        migrate(connection)
        existing = users_repo.get_credentials(connection, username)
        with transaction(connection):
            if existing is None:
                users_repo.create_user(
                    connection,
                    {
                        "username": username,
                        "role": "super_admin",
                        "password_hash": hash_password(password),
                    },
                )
                print(f"Created super admin '{username}'.")
            elif reset:
                users_repo.update_user(
                    connection,
                    existing["id"],
                    {
                        "role": "super_admin",
                        "disabled": 0,
                        "password_hash": hash_password(password),
                        "must_change_password": 0,
                    },
                )
                users_repo.delete_sessions_for(connection, existing["id"])
                print(
                    f"Reset '{username}': super admin, enabled, new password, "
                    "signed out everywhere."
                )
            else:
                print(
                    f"'{username}' already exists. "
                    "Add --reset to make it a super admin with this password.",
                    file=sys.stderr,
                )
                return 1
    finally:
        connection.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    args_list = sys.argv[1:] if argv is None else argv

    if args_list[:1] == ["create-admin"]:
        admin_parser = argparse.ArgumentParser(
            prog="python -m app create-admin", description="Create or reset a super admin account."
        )
        admin_parser.add_argument("username")
        admin_parser.add_argument(
            "--reset",
            action="store_true",
            help="If the account exists: make it an enabled super admin with the new password.",
        )
        admin_args = admin_parser.parse_args(args_list[1:])
        return create_admin(settings, admin_args.username, reset=admin_args.reset)

    parser = argparse.ArgumentParser(prog="python -m app", description="Run the AMR backend.")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Restart on source changes. Development only.",
    )
    args = parser.parse_args(args_list)

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
