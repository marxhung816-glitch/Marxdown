"""Lightweight tab container kept independent of Qt WebEngine startup."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QTabWidget

if TYPE_CHECKING:
    from .tab_manager import DocumentTab


class TabManager(QTabWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)

    def document_at(self, index: int) -> DocumentTab | None:
        return self.widget(index)

    def find_document(self, path: Path) -> DocumentTab | None:
        resolved = path.resolve()
        for index in range(self.count()):
            document = self.document_at(index)
            if document and document.path == resolved:
                return document
        return None

    def add_document(self, document: DocumentTab) -> None:
        index = self.addTab(document, document.path.name)
        self.setTabToolTip(index, str(document.path))
        self.setCurrentIndex(index)
