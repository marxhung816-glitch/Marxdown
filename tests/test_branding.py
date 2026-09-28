"""Visible naming and icon assets for the released application."""

from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def test_window_uses_marxdown_name_and_loadable_icon():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert window.windowTitle() == "Marxdown"
        icon = window.windowIcon()
        assert not icon.isNull()
        assert not icon.pixmap(32, 32).isNull()
    finally:
        window.close()
        app.processEvents()


def test_icon_has_source_and_windows_formats():
    icons = Path(__file__).resolve().parents[1] / "resources" / "icons"
    assert (icons / "marxdown.svg").is_file()
    assert (icons / "marxdown.png").is_file()
    assert (icons / "marxdown.ico").is_file()
