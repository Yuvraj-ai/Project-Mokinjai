"""Repository hygiene guards.

These catch defects that do not affect the machine they were created on, but
break the project for anyone else — the class of bug that no functional test
notices because everything works locally.
"""

import importlib.util
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_no_unregistered_submodule_gitlinks():
    """A gitlink with no `.gitmodules` entry ships an empty directory to clones.

    `backend/pretty_logger` was exactly that: mode 160000 pointing at a commit,
    with no `.gitmodules` anywhere in the repo. A fresh clone therefore got an
    empty directory, and since `app/logging.py` imported it, the application could
    not be imported and not one test could be collected. Its behaviour now lives
    in `app/logging.py` as an independent implementation.
    """
    listing = subprocess.run(
        ["git", "ls-files", "-s"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    gitlinks = [line for line in listing.splitlines() if line.startswith("160000")]
    assert gitlinks == [], (
        "gitlinks found — fresh clones receive empty directories for these, so "
        f"anything importing them is broken on checkout: {gitlinks}"
    )


def test_pretty_logger_is_no_longer_vendored():
    """The GPL-3 package must not be importable or present in the tree."""
    assert importlib.util.find_spec("pretty_logger") is None, (
        "pretty_logger is still importable; the logging code was meant to be "
        "inlined into app/logging.py so the tree no longer carries it"
    )


def test_application_logger_is_configured():
    """The inlined logging implementation actually works."""
    from app.logging import logger

    assert logger.handlers, "logger has no handlers attached"
    assert logger.level == 10, "logger level should be DEBUG (10)"
