"""Application logging: level-coloured console output plus a daily-rotating file.

Every module imports `logger` from here, so there is a single logger with one
console handler and one file handler.

This module used to import a vendored `pretty_logger` package, which arrived as an
unregistered git submodule gitlink — no `.gitmodules` entry, so a fresh clone got
an empty directory and could not import the application or collect a single test.
That package is GPL-3, so copying its source in would relicense this project;
this is an independent implementation of the same behaviour using only the
standard library.
"""

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler

LOG_DIR = "logs"
LOG_FILE = "applog.log"
BACKUP_DAYS = 30
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_RESET = "\033[0m"
_DIM = "\033[90m"
_YELLOW = "\033[93m"

# One colour per level; INFO's green is also the fallback for custom levels.
_LEVEL_COLOURS = {
    logging.DEBUG: "\033[96m",     # cyan
    logging.INFO: "\033[92m",      # green
    logging.WARNING: _YELLOW,
    logging.ERROR: "\033[91m",     # red
    logging.CRITICAL: "\033[95m",  # magenta
}


class ConsoleFormatter(logging.Formatter):
    """Colour the level and message, and prefix the emitting file and line."""

    def format(self, record: logging.LogRecord) -> str:
        colour = _LEVEL_COLOURS.get(record.levelno, _LEVEL_COLOURS[logging.INFO])
        line = (
            f"{_YELLOW}{self.formatTime(record, DATE_FORMAT)}{_RESET} "
            f"{_DIM}[{record.filename}:{record.lineno}]{_RESET} "
            f"{colour}{record.levelname:<8}{_RESET} - "
            f"{colour}{record.getMessage()}{_RESET}"
        )
        if record.exc_info:
            line += f"\n{_LEVEL_COLOURS[logging.ERROR]}{self.formatException(record.exc_info)}{_RESET}"
        return line


def get_logger(
    name: str = "mokinjay",
    log_dir: str = LOG_DIR,
    backup_days: int = BACKUP_DAYS,
) -> logging.Logger:
    """Return the application logger, attaching handlers on first call.

    Console output is coloured; the file is plain text and rotates at midnight,
    keeping `backup_days` of history. Calling this again returns the same logger
    without duplicating handlers.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:
        return logger

    os.makedirs(log_dir, exist_ok=True)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(ConsoleFormatter())
    logger.addHandler(console)

    rotating = TimedRotatingFileHandler(
        os.path.join(log_dir, LOG_FILE),
        when="midnight",
        interval=1,
        backupCount=backup_days,
        encoding="utf-8",
    )
    rotating.setLevel(logging.DEBUG)
    rotating.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(filename)s:%(lineno)d] %(levelname)-8s - %(message)s",
            datefmt=DATE_FORMAT,
        )
    )
    logger.addHandler(rotating)

    return logger


logger = get_logger()
