"""Logging helpers: console + rotating file logs."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-24s | %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(verbose: bool = False, log_dir: str | Path = "logs") -> logging.Logger:
    """Configure root logging for the app.

    Args:
        verbose: enable DEBUG level on the console.
        log_dir: directory for rotating log files.

    Returns:
        The ``kingshotbot`` logger.
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(logging.Formatter(_FORMAT, _DATEFMT))
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "kingshotbot.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_FORMAT, _DATEFMT))
    root.addHandler(file_handler)

    # Third-party noise reduction.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)

    return logging.getLogger("kingshotbot")
