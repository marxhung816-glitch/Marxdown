"""Persist theme, reading size and recently opened documents."""

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QSpinBox, QVBoxLayout


class AppSettings:
    def __init__(self) -> None:
        self._store = QSettings("Marxdown", "Marxdown")
        previous = QSettings("MarkdownViewer", "Markdown Viewer")
        for key in ("theme", "font_size", "sidebar_visible", "recent_files"):
            if not self._store.contains(key) and previous.contains(key):
                self._store.setValue(key, previous.value(key))

    @property
    def theme(self) -> str:
        value = self._store.value("theme", "light")
        return "dark" if value == "dark" else "light"

    @theme.setter
    def theme(self, value: str) -> None:
        self._store.setValue("theme", value)

    @property
    def font_size(self) -> int:
        return max(12, min(24, int(self._store.value("font_size", 16))))

    @font_size.setter
    def font_size(self, value: int) -> None:
        self._store.setValue("font_size", value)

    @property
    def sidebar_visible(self) -> bool:
        return self._store.value("sidebar_visible", False, type=bool)

    @sidebar_visible.setter
    def sidebar_visible(self, value: bool) -> None:
        self._store.setValue("sidebar_visible", value)

    @property
    def recent_files(self) -> list[Path]:
        value = self._store.value("recent_files", [])
        entries = [value] if isinstance(value, str) else list(value or [])
        return [Path(entry) for entry in entries if Path(entry).is_file()]

    def add_recent(self, path: Path) -> None:
        item = str(path.resolve())
        others = [str(other) for other in self.recent_files if str(other) != item]
        self._store.setValue("recent_files", [item, *others][:12])

    def clear_recent(self) -> None:
        self._store.remove("recent_files")


class SettingsDialog(QDialog):
    def __init__(self, font_size: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(310)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("阅读设置"))
        form = QFormLayout()
        self.font_spin = QSpinBox()
        self.font_spin.setRange(12, 24)
        self.font_spin.setSuffix(" px")
        self.font_spin.setValue(font_size)
        form.addRow("正文字号", self.font_spin)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
