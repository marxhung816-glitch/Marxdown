"""Chinese IME positioning in the Markdown source editor."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.markdown_renderer import MarkdownRenderer
from app.tab_manager import DocumentTab


def test_ime_candidate_anchor_stays_below_the_line_being_edited(tmp_path):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "中文.md"
    source.write_text("第一行\n正在修改的文字\n第三行", encoding="utf-8")
    document = DocumentTab(source, MarkdownRenderer(), "light", 16)
    document.resize(1100, 500)
    document.show()
    document.set_edit_mode(True)
    editor = document.editor
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.Start)
    cursor.movePosition(cursor.MoveOperation.Down)
    editor.setTextCursor(cursor)
    app.processEvents()
    try:
        caret = editor.cursorRect()
        candidate_anchor = editor.inputMethodQuery(Qt.InputMethodQuery.ImCursorRectangle)
        assert candidate_anchor.top() >= caret.bottom() + editor.fontMetrics().height()
        assert editor.toPlainText() == "第一行\n正在修改的文字\n第三行"
    finally:
        document.close()


def test_source_editor_gets_more_room_than_preview_while_editing(tmp_path):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "编辑.md"
    source.write_text("# 标题\n\n这是一段较长的中文。", encoding="utf-8")
    document = DocumentTab(source, MarkdownRenderer(), "light", 16)
    document.resize(1100, 500)
    document.show()
    document.set_edit_mode(True)
    app.processEvents()
    try:
        assert document.editor.width() > document.view.width()
    finally:
        document.close()
