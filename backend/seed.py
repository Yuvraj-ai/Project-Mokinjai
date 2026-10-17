#!/usr/bin/env python3
"""Provision the rows required to use a Mokinjay database.

    python seed.py --generate-password

Idempotent: safe to run against a database that is already usable, and expected
to be re-run without effect. Seeds data only -- run `alembic upgrade head`
first, because this script never builds schema.
"""

import argparse
import asyncio
import getpass
import os
import secrets
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.engine import make_url  # noqa: E402

# Hosts that are plainly the machine we are already on. Anything else is treated
# as remote and needs --yes, the same philosophy as ALLOW_REMOTE_MIGRATIONS:
# writing an administrator into the wrong database is worth one flag to prevent.
LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1"}


def describe_target(database_url: str) -> tuple[str, str]:
    """Return (host, database) for display. Never returns user or password."""
    parsed = make_url(database_url)
    return (parsed.host or "", parsed.database or "")


def requires_confirmation(host: str) -> bool:
    return host not in LOCAL_HOSTS


def resolve_password(args, environ) -> tuple[str, bool]:
    """Return (password, was_generated).

    There is deliberately no default. A default password for a superuser is a
    back door, so every path here ends in a user-supplied secret or a fresh
    random one -- never a constant.
    """
    if args.password:
        return args.password, False

    from_env = environ.get("MOKINJAY_SEED_PASSWORD")
    if from_env:
        return from_env, False

    if args.generate_password:
        return secrets.token_urlsafe(24), True

    return _prompt_for_password(), False


def _prompt_for_password() -> str:
    first = getpass.getpass("Password for the seeded account: ")
    second = getpass.getpass("Confirm: ")
    if first != second:
        print("Passwords did not match.", file=sys.stderr)
        raise SystemExit(2)
    if not first:
        print("Password must not be empty.", file=sys.stderr)
        raise SystemExit(2)
    return first


def format_summary(result, host: str, database: str) -> str:
    """Render what happened.

    The password is not a parameter, so it cannot reach this text -- a
    structural guarantee rather than a checked one.
    """
    def mark(created: bool) -> str:
        return "created" if created else "already existed"

    return "\n".join(
        [
            f"Target: {host or '(local)'} / {database}",
            f"User:       {result.user_id} ({mark(result.user_created)})",
            f"Workspace:  {result.workspace_id} ({mark(result.workspace_created)})",
            f"Membership: role=owner ({mark(result.membership_created)})",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed a superuser, a workspace, and the owner membership joining them."
    )
    parser.add_argument("--email", default="admin@mokinjay.local")
    parser.add_argument("--name", default="Administrator")
    parser.add_argument("--workspace-name", default="Default")
    parser.add_argument("--password", default=None, help="Prefer MOKINJAY_SEED_PASSWORD to this: it leaks into shell history.")
    parser.add_argument("--generate-password", action="store_true", help="Generate one and print it once.")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation for a non-local host.")
    return parser


async def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    from app.config import get_settings
    from app.database import async_session
    from app.services.seed import seed_admin_and_workspace

    database_url = get_settings().DATABASE_URL
    host, database = describe_target(database_url)

    if requires_confirmation(host) and not args.yes:
        print(f"Refusing to seed the non-local database {host} / {database}.")
        print("Re-run with --yes if that is really the target.")
        return 2

    password, generated = resolve_password(args, os.environ)

    async with async_session() as db:
        result = await seed_admin_and_workspace(
            db,
            email=args.email,
            password=password,
            name=args.name,
            workspace_name=args.workspace_name,
        )

    print(format_summary(result, host=host, database=database))
    if generated:
        # Printed exactly once: it is not recoverable afterwards, because only
        # the hash is stored.
        print(f"\nGenerated password (shown once): {password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
