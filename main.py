"""Launch the Marxdown desktop application."""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.branding import APP_NAME, icon_path
from app.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setWindowIcon(QIcon(str(icon_path())))
    app.setStyle("Fusion")
    window = MainWindow()
    if len(sys.argv) > 1:
        candidate = Path(sys.argv[1])
        if candidate.is_dir():
            window.open_folder(candidate)
        elif candidate.is_file():
            window.open_file(candidate)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
