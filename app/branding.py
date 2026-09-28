"""Shared app name and bundled icon location."""

from pathlib import Path
import sys


APP_NAME = "Marxdown"


def icon_path() -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return root / "resources" / "icons" / "marxdown.ico"
