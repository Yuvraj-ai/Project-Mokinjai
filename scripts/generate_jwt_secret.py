#!/usr/bin/env python3
"""Generate a JWT_SECRET_KEY for .env.

Standalone on purpose: imports nothing from app.*, needs no database and no
environment, and runs on a bare interpreter.

Rotating JWT_SECRET_KEY is cheap. Outstanding access tokens stop validating and
users sign in again; nothing is lost. That is NOT true of LLM_ENCRYPTION_KEY —
see scripts/generate_fernet_key.py before rotating that one.
"""

import secrets

# 256 bits, matching HS256's security level. Hex has no quoting hazards in .env.
BYTES = 32


def main() -> None:
    value = secrets.token_hex(BYTES)
    print("# Paste into .env. Rotating this invalidates all outstanding tokens.")
    print(f"JWT_SECRET_KEY={value}")


if __name__ == "__main__":
    main()
