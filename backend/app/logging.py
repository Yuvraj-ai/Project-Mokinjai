"""Shared logging setup using pretty_logger.

All modules should import `logger` from this module
to ensure a single logger instance with one file handler.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from pretty_logger.pretty_logger import get_logger

logger = get_logger()
