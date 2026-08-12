"""Logging centralizado para Deluxevor Music."""
import logging
import sys
from pathlib import Path

LOG_DIR = Path.home() / ".local" / "share" / "vorem-music" / "logs"
LOG_FILE = LOG_DIR / "vorem.log"

_configured = False


def _configure():
    global _configured
    if _configured:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)

    root = logging.getLogger("vorem")
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger hijo bajo el namespace 'vorem'."""
    _configure()
    return logging.getLogger(f"vorem.{name}")
