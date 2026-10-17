"""The secret generators.

They are standalone scripts with no imports from app.*, so they are exercised the
way a user runs them: as subprocesses, checking stdout.
"""

import re
import subprocess
import sys
from pathlib import Path

from cryptography.fernet import Fernet

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def run(script: str) -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / script)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_jwt_script_emits_a_256_bit_hex_key():
    match = re.search(r"^JWT_SECRET_KEY=([0-9a-f]+)$", run("generate_jwt_secret.py"), re.MULTILINE)
    assert match, "no JWT_SECRET_KEY= line in output"
    assert len(match.group(1)) == 64


def test_jwt_script_generates_a_fresh_key_every_run():
    assert run("generate_jwt_secret.py") != run("generate_jwt_secret.py")


def test_fernet_script_emits_a_key_that_fernet_accepts():
    match = re.search(r"^LLM_ENCRYPTION_KEY=(\S+)$", run("generate_fernet_key.py"), re.MULTILINE)
    assert match, "no LLM_ENCRYPTION_KEY= line in output"
    key = match.group(1).encode()
    assert Fernet(key).decrypt(Fernet(key).encrypt(b"mokinjay")) == b"mokinjay"


def test_fernet_script_warns_that_rotation_is_destructive():
    output = run("generate_fernet_key.py")
    assert "undecryptable" in output


def test_jwt_script_does_not_import_the_application():
    """It must run on a bare interpreter, so it cannot reach the app package."""
    source = (SCRIPTS / "generate_jwt_secret.py").read_text()
    assert "app.config" not in source
    assert "app.crypto" not in source
    assert "app.database" not in source
