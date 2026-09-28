"""Markdown source editor with room for Chinese input method candidates."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtWidgets import QPlainTextEdit


class MarkdownEditor(QPlainTextEdit):
    def inputMethodQuery(self, query):
        result = super().inputMethodQuery(query)
        if query != Qt.InputMethodQuery.ImCursorRectangle:
            return result
        rectangle = QRectF(result)
        line_height = self.fontMetrics().height()
        if rectangle.top() + 3 * line_height + 72 < self.height():
            rectangle.translate(0, 3 * line_height)
        else:
            rectangle.translate(0, -5 * line_height)
        return rectangle
