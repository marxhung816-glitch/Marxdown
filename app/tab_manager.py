"""WebEngine document tabs and link handling."""

import os
from pathlib import Path
import tempfile
from html import escape

from PySide6.QtCore import QObject, QRunnable, QSignalBlocker, QThreadPool, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QFontMetricsF
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QPlainTextEdit, QSplitter, QVBoxLayout, QWidget

from .file_manager import is_markdown, read_markdown, write_markdown
from .markdown_editor import MarkdownEditor
from .markdown_renderer import Heading, MarkdownRenderer


class RenderSignals(QObject):
    finished = Signal(object, object, object)


class RenderTask(QRunnable):
    def __init__(self, renderer: MarkdownRenderer, key: tuple[str, str, int]) -> None:
        super().__init__()
        self.renderer = renderer
        self.key = key
        self.signals = RenderSignals()

    def run(self) -> None:
        try:
            result = self.renderer.render(*self.key)
            self.signals.finished.emit(self.key, result, None)
        except Exception as error:
            self.signals.finished.emit(self.key, None, str(error))


class DocumentPage(QWebEnginePage):
    markdown_requested = Signal(str)
    anchor_requested = Signal(str)

    def __init__(self, document_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.document_path = document_path

    def acceptNavigationRequest(self, url: QUrl, navigation_type, is_main_frame: bool) -> bool:
        if is_main_frame and url.isLocalFile():
            target = Path(url.toLocalFile())
            if url.fragment() and target == self.document_path:
                self.anchor_requested.emit(url.fragment())
                return False
            if is_markdown(target):
                self.markdown_requested.emit(str(target))
                return False
        if navigation_type != QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            return super().acceptNavigationRequest(url, navigation_type, is_main_frame)
        if url.scheme() in {"https", "http", "mailto"}:
            QDesktopServices.openUrl(url)
            return False
        if url.isLocalFile():
            target = Path(url.toLocalFile())
            if url.fragment() and (target == self.document_path or target == self.document_path.parent):
                self.anchor_requested.emit(url.fragment())
                return False
            QDesktopServices.openUrl(url)
        return False


class DocumentTab(QWidget):
    markdown_requested = Signal(str)
    changed = Signal()
    preview_updated = Signal()
    render_failed = Signal(str)

    def __init__(self, path: Path, renderer: MarkdownRenderer, theme: str, font_size: int, parent=None) -> None:
        super().__init__(parent)
        self.path = path.resolve()
        self.content = ""
        self.saved_content = ""
        self.headings: list[Heading] = []
        self.stamp: tuple[int, int] | None = None
        self.dirty = False
        self.editing = False
        self.external_change_pending = False
        self.renderer = renderer
        self.theme = theme
        self.font_size = font_size
        self._rendering_key: tuple[str, str, int] | None = None
        self._preview_directory = tempfile.TemporaryDirectory(prefix="marxdown-preview-", ignore_cleanup_errors=True)
        self._preview_file = Path(self._preview_directory.name) / "preview.html"
        self.editor = MarkdownEditor(self)
        self.editor.setObjectName("markdownEditor")
        self.editor.setAcceptDrops(False)
        self.editor.viewport().setAcceptDrops(False)
        self.editor.setPlaceholderText("在这里编辑 Markdown…")
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        editor_font = QFont("Cascadia Code", 11)
        editor_font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.setFont(editor_font)
        self.editor.setTabStopDistance(QFontMetricsF(editor_font).horizontalAdvance(" ") * 4)
        self.editor.textChanged.connect(self._on_editor_changed)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(320)
        self.preview_timer.timeout.connect(self._render_preview)
        self.view = QWebEngineView(self)
        self.page = DocumentPage(self.path, self.view)
        self.view.setPage(self.page)
        self.view.setAcceptDrops(False)
        self.view.loadFinished.connect(self._disable_preview_drops)
        self._disable_preview_drops()
        self.view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self.page.markdown_requested.connect(self.markdown_requested)
        self.page.anchor_requested.connect(self.scroll_to_anchor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.editor)
        self.splitter.addWidget(self.view)
        self.splitter.setStretchFactor(1, 1)
        layout.addWidget(self.splitter)
        self.editor.hide()
        self.refresh(theme, font_size)

    def _disable_preview_drops(self, *_args) -> None:
        self.view.setAcceptDrops(False)
        if self.view.focusProxy() is not None:
            self.view.focusProxy().setAcceptDrops(False)

    def file_stamp(self) -> tuple[int, int] | None:
        try:
            info = self.path.stat()
            return info.st_mtime_ns, info.st_size
        except OSError:
            return None

    def refresh(self, theme: str, font_size: int, reread: bool = True) -> None:
        self.theme = theme
        self.font_size = font_size
        if reread:
            self.content = read_markdown(self.path)
            self.saved_content = self.content
            self.stamp = self.file_stamp()
            with QSignalBlocker(self.editor):
                self.editor.setPlainText(self.content)
            self.dirty = False
            self.external_change_pending = False
            self.changed.emit()
        self._render_preview()

    def _render_preview(self) -> None:
        if self._rendering_key is not None:
            return
        key = (self.content, self.theme, self.font_size)
        self._rendering_key = key
        task = RenderTask(self.renderer, key)
        task.signals.finished.connect(self._render_finished)
        QThreadPool.globalInstance().start(task)

    def _render_finished(self, key, result, error) -> None:
        self._rendering_key = None
        if key != (self.content, self.theme, self.font_size):
            if not self.preview_timer.isActive():
                self._render_preview()
            return
        if error is not None:
            self.render_failed.emit(error)
            return
        self.headings = result.headings
        base_url = QUrl.fromLocalFile(str(self.path.parent) + os.sep).toString()
        html = result.html.replace("<head>", f'<head><base href="{escape(base_url, quote=True)}">', 1)
        try:
            self._preview_file.write_text(html, encoding="utf-8")
        except OSError as write_error:
            self.render_failed.emit(str(write_error))
            return
        self.view.load(QUrl.fromLocalFile(str(self._preview_file)))
        self.preview_updated.emit()

    def _on_editor_changed(self) -> None:
        self.content = self.editor.toPlainText()
        self.dirty = self.content != self.saved_content
        self.changed.emit()
        self.preview_timer.start()

    def set_edit_mode(self, editing: bool) -> None:
        self.editing = editing
        self.editor.setVisible(editing)
        if editing:
            self.splitter.setSizes([620, 480])
            self.editor.setFocus()
        else:
            if self.preview_timer.isActive():
                self.preview_timer.stop()
                self._render_preview()
            self.view.setFocus()
        self.changed.emit()

    def save(self, force: bool = False) -> None:
        if not self.dirty:
            return
        if not force and self.file_stamp() != self.stamp:
            self.external_change_pending = True
            raise ExternalModificationError(self.path)
        write_markdown(self.path, self.content)
        self.stamp = self.file_stamp()
        self.saved_content = self.content
        self.dirty = False
        self.external_change_pending = False
        self.changed.emit()

    def scroll_to_anchor(self, anchor: str) -> None:
        import json

        self.view.page().runJavaScript(
            f"document.getElementById({json.dumps(anchor)})?.scrollIntoView({{behavior: 'smooth'}})"
        )


class ExternalModificationError(Exception):
    """A document changed on disk while it contained unsaved edits."""


from .tab_widget import TabManager
