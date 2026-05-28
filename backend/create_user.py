#!/usr/bin/env python3
"""Create a new user in the database from the command line.

Usage:
    python create_user.py --name "John Doe" --email john@example.com --password s3cret
    python create_user.py --admin --name "Admin" --email admin@local --password adminpass

The --admin flag marks the user as a superuser with full access.
"""

import argparse
import sys
from pathlib import Path

# Ensure we can import app modules
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))


def create_user(name: str, email: str, password: str, admin: bool = False):
    """Create a user in the database."""
    from sqlalchemy import inspect

    from app.database import engine, async_session, Base
    from app.models.user import User
    from app.utils.security import hash_password

    inspector = inspect(engine.sync_engine)
    if "users" not in inspector.get_table_names():
        import asyncio

        async def create_tables():
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        asyncio.get_event_loop().run_until_complete(create_tables())

    import asyncio

    async def _do_create():
        async with async_session() as db:
            from sqlalchemy import select

            result = await db.execute(select(User).where(User.email == email))
            existing = result.scalar_one_or_none()
            if existing:
                print(f"Error: User with email '{email}' already exists (id={existing.id})")
                sys.exit(1)

            user = User(
                name=name,
                email=email,
                hashed_password=hash_password(password),
                is_superuser=admin,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            return user

    user = asyncio.run(_do_create())
    role = "superuser" if admin else "user"
    print(f"Created {role}: {user.name} <{user.email}> (id={user.id})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a user in the Mokinjay backend")
    parser.add_argument("--name", required=True, help="User's display name")
    parser.add_argument("--email", required=True, help="User's email address")
    parser.add_argument("--password", required=True, help="User's password")
    parser.add_argument("--admin", action="store_true", help="Mark as superuser (full admin access)")

    args = parser.parse_args()
    create_user(args.name, args.email, args.password, args.admin)
