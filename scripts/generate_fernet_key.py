#!/usr/bin/env python3
"""Generate an LLM_ENCRYPTION_KEY for .env.

Standalone on purpose: imports nothing from app.*, needs no database and no
environment.

WARNING — rotation is DESTRUCTIVE and unrecoverable. Every LLM API key already
stored in llm_profiles.encrypted_api_key becomes undecryptable, and each one has
to be re-entered by hand. Rotate only when you accept that.
"""

import sys

WARNING = (
    "# Paste into .env.\n"
    "# WARNING: rotating this key renders every stored LLM API key\n"
    "# undecryptable. There is no recovery; each key must be re-entered by hand.\n"
)

PROBE = b"mokinjay"


def main() -> int:
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        print(
            "cryptography is not installed for this interpreter.\n"
            "Run it with the project venv instead:\n"
            "  backend/venv/bin/python scripts/generate_fernet_key.py",
            file=sys.stderr,
        )
        return 1

    key = Fernet.generate_key()

    # Prove the key works before handing it over, so a bad paste is impossible.
    assert Fernet(key).decrypt(Fernet(key).encrypt(PROBE)) == PROBE

    print(WARNING, end="")
    print(f"LLM_ENCRYPTION_KEY={key.decode()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
