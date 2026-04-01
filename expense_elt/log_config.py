"""
Centralized logging configuration for the expense ELT pipeline.

Sets up a root logger that writes to logs/app.log (rotating) and stderr.
All modules should use `logging.getLogger(__name__)` to get their logger.

Call `setup_logging()` once at startup (in main.py and server.py).
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_DIR = Path(__file__).parent / "logs"
_APP_LOG = _LOG_DIR / "app.log"

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with file + stderr handlers. Safe to call multiple times."""
    global _configured
    if _configured:
        return
    _configured = True

    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler — 5 MB, keep 3 backups
    file_handler = RotatingFileHandler(
        str(_APP_LOG), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    # Stderr handler — WARNING+ only (avoid duplicating uvicorn access logs)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(stderr_handler)

    # Quiet noisy third-party loggers
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
