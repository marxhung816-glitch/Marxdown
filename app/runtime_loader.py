"""Load the preview engine without delaying the first visible window."""

from PySide6.QtCore import QThread, Signal


class RuntimeLoader(QThread):
    loaded = Signal(object, object)
    failed = Signal(str)

    def run(self) -> None:
        try:
            from .markdown_renderer import MarkdownRenderer
            from .tab_manager import DocumentTab
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.loaded.emit(DocumentTab, MarkdownRenderer)
