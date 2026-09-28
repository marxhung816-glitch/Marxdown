import base64
import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QMimeData, QPoint, QPointF, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMessageBox

from app.main_window import MainWindow
import app.markdown_renderer
import app.tab_manager


def test_open_chinese_document_tabs_and_detect_external_edits(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    first = tmp_path / "学习笔记.md"
    second = tmp_path / "第二章.markdown"
    first.write_text("# 第一章\n\n初始内容", encoding="utf-8")
    second.write_text("# 第二章", encoding="utf-8")
    window = MainWindow()
    try:
        assert window.open_file(first)
        assert window.open_file(second)
        assert window.tabs.count() == 2
        assert window.windowTitle() == "第二章.markdown - Marxdown"
        assert window.open_file(first)
        assert window.tabs.count() == 2
        assert window.current_document().content.startswith("# 第一章")
        assert window.current_folder == tmp_path
        assert first in window.settings.recent_files
        first.write_text("# 第一章\n\n外部修改后的内容", encoding="utf-8")
        window.check_for_updates()
        assert "外部修改" in window.current_document().content
        window.close_current_tab()
        assert window.tabs.count() == 1
    finally:
        window.close()
        app.processEvents()


def test_local_markdown_link_requests_an_in_app_tab(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "起点.md"
    target = tmp_path / "第二章.md"
    source.write_text("[第二章](第二章.md)", encoding="utf-8")
    target.write_text("# 第二章", encoding="utf-8")
    window = MainWindow()
    try:
        assert window.open_file(source)
        page = window.current_document().page
        accepted = page.acceptNavigationRequest(
            QUrl.fromLocalFile(str(target)),
            QWebEnginePage.NavigationType.NavigationTypeLinkClicked,
            True,
        )
        assert accepted is False
        assert window.tabs.count() == 2
        assert window.current_document().path == target
    finally:
        window.close()
        app.processEvents()


def test_webengine_file_navigation_opens_markdown_as_a_tab(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "当前.md"
    target = tmp_path / "拖入.md"
    source.write_text("# 当前", encoding="utf-8")
    target.write_text("# 拖入", encoding="utf-8")
    window = MainWindow()
    try:
        assert window.open_file(source)
        page = window.current_document().page
        accepted = page.acceptNavigationRequest(
            QUrl.fromLocalFile(str(target)),
            QWebEnginePage.NavigationType.NavigationTypeOther,
            True,
        )
        assert accepted is False
        assert window.tabs.count() == 2
        assert window.current_document().path == target
    finally:
        window.close()
        app.processEvents()


def test_drop_markdown_on_tab_area_opens_it(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "拖入.md"
    source.write_text("# 拖入成功", encoding="utf-8")
    window = MainWindow()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(source))])
    try:
        enter = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(window.tabs, enter)
        assert enter.isAccepted()
        drop = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(window.tabs, drop)
        app.processEvents()
        assert window.current_document().path == source
    finally:
        window.close()
        app.processEvents()


def test_drop_markdown_on_webengine_preview_opens_it(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "当前.md"
    target = tmp_path / "拖入.markdown"
    source.write_text("# 当前", encoding="utf-8")
    target.write_text("# 拖入", encoding="utf-8")
    window = MainWindow()
    window.show()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(target))])
    try:
        assert window.open_file(source)
        ready = QEventLoop()
        window.current_document().view.loadFinished.connect(ready.quit)
        QTimer.singleShot(6000, ready.quit)
        ready.exec()
        preview = window.current_document().view.focusProxy()
        assert preview is not None
        assert not window.current_document().view.acceptDrops()
        assert not preview.acceptDrops()
        enter = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(preview, enter)
        assert enter.isAccepted()
        drop = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(preview, drop)
        assert drop.isAccepted()
        app.processEvents()
        assert window.current_document().path == target
    finally:
        window.close()
        app.processEvents()


def test_drop_files_on_empty_window_opens_each_markdown(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    first = tmp_path / "第一篇.md"
    second = tmp_path / "第二篇.markdown"
    ignored = tmp_path / "忽略.txt"
    for path in (first, second, ignored):
        path.write_text(f"# {path.stem}", encoding="utf-8")
    window = MainWindow()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)) for path in (first, ignored, second)])
    try:
        welcome = window.stack.currentWidget()
        enter = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(welcome, enter)
        assert enter.isAccepted()
        drop = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(welcome, drop)
        assert drop.isAccepted()
        app.processEvents()
        assert [window.tabs.document_at(index).path for index in range(window.tabs.count())] == [first, second]
    finally:
        window.close()
        app.processEvents()


def test_drop_file_on_editor_opens_new_tab_without_changing_source(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "当前.md"
    target = tmp_path / "新文件.md"
    source.write_text("# 当前", encoding="utf-8")
    target.write_text("# 新文件", encoding="utf-8")
    window = MainWindow()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(target))])
    try:
        assert window.open_file(source)
        window.toggle_edit_mode()
        editor = window.current_document().editor
        assert not editor.acceptDrops()
        assert not editor.viewport().acceptDrops()
        enter = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(editor.viewport(), enter)
        assert enter.isAccepted()
        drop = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(editor.viewport(), drop)
        assert drop.isAccepted()
        app.processEvents()
        assert window.current_document().path == target
        assert source.read_text(encoding="utf-8") == "# 当前"
    finally:
        window.close()
        app.processEvents()


def test_native_drop_handler_returns_before_opening_file(tmp_path: Path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    target = tmp_path / "拖入.md"
    target.write_text("# 拖入", encoding="utf-8")
    window = MainWindow()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(target))])
    opened = []
    monkeypatch.setattr(window, "open_file", lambda path: opened.append(Path(path)) or True)
    try:
        enter = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(window.stack.currentWidget(), enter)
        assert enter.isAccepted()
        drop = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(window.stack.currentWidget(), drop)
        assert drop.isAccepted()
        assert opened == []
        app.processEvents()
        assert opened == [target]
    finally:
        window.close()
        app.processEvents()


def test_focus_layout_collapses_sidebar_and_single_tab(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    store = QSettings("Marxdown", "Marxdown")
    old_sidebar = store.value("sidebar_visible")
    store.setValue("sidebar_visible", False)
    first = tmp_path / "第一章.md"
    second = tmp_path / "第二章.md"
    first.write_text("# 第一章", encoding="utf-8")
    second.write_text("# 第二章", encoding="utf-8")
    window = MainWindow()
    try:
        assert window.sidebar.isHidden()
        window.toggle_sidebar()
        assert not window.sidebar.isHidden()
        window.toggle_sidebar()
        assert window.sidebar.isHidden()
        assert window.open_file(first)
        assert window.tabs.tabBar().isHidden()
        assert window.open_file(second)
        assert not window.tabs.tabBar().isHidden()
        window.close_current_tab()
        assert window.tabs.tabBar().isHidden()
        assert window.open_folder(tmp_path)
        assert not window.sidebar.isHidden()
        assert window.sidebar_tabs.currentWidget() is window.file_tree
    finally:
        window.close()
        app.processEvents()
        if old_sidebar is None:
            store.remove("sidebar_visible")
        else:
            store.setValue("sidebar_visible", old_sidebar)


def test_edit_live_preview_and_save_utf8(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "可编辑.md"
    source.write_text("# 原标题", encoding="utf-8")
    window = MainWindow()
    try:
        assert window.open_file(source)
        window.toggle_edit_mode()
        document = window.current_document()
        assert document.editing
        document.editor.setPlainText("# 新标题\n\n中文修改。")
        assert document.dirty
        assert window.tabs.tabText(0).startswith("● ")
        loop = QEventLoop()
        QTimer.singleShot(500, loop.quit)
        loop.exec()
        assert document.headings[0].title == "新标题"
        assert window.save_current()
        assert source.read_text(encoding="utf-8") == "# 新标题\n\n中文修改。"
        assert not document.dirty
        assert not window.tabs.tabText(0).startswith("● ")
    finally:
        window.close()
        app.processEvents()


def test_dirty_editor_survives_external_change(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "并发.md"
    source.write_text("# 初始", encoding="utf-8")
    window = MainWindow()
    try:
        assert window.open_file(source)
        window.toggle_edit_mode()
        document = window.current_document()
        document.editor.setPlainText("# 我的修改")
        source.write_text("# 外部修改后的内容", encoding="utf-8")
        window.check_for_updates()
        assert document.content == "# 我的修改"
        assert document.external_change_pending
        document.save(force=True)
    finally:
        window.close()
        app.processEvents()


def test_open_menu_combines_file_and_folder_actions():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        labels = [action.text() for action in window.open_menu.actions()]
        assert "打开文件" in labels
        assert "打开文件夹" in labels
    finally:
        window.close()
        app.processEvents()


def test_export_menu_writes_unsaved_editor_text_to_word(tmp_path: Path):
    from docx import Document

    app = QApplication.instance() or QApplication([])
    source = tmp_path / "原稿.md"
    source.write_text("# 磁盘旧内容", encoding="utf-8")
    target = tmp_path / "导出.docx"
    window = MainWindow()
    try:
        assert window.open_file(source)
        window.toggle_edit_mode()
        window.current_document().editor.setPlainText("# 未保存的新内容")
        assert [action.text() for action in window.export_menu.actions()] == ["导出 PDF…", "导出 Word…"]
        job = window.export_word_to(target)
        result = []
        loop = QEventLoop()
        job.finished.connect(lambda _path, success, message: (result.append((success, message)), loop.quit()))
        QTimer.singleShot(5000, loop.quit)
        loop.exec()
        assert result and result[0][0], result
        assert Document(target).paragraphs[0].text == "未保存的新内容"
        assert source.read_text(encoding="utf-8") == "# 磁盘旧内容"
    finally:
        if window.current_document():
            window.current_document().editor.setPlainText("# 磁盘旧内容")
        window.close()
        app.processEvents()


def test_unsaved_document_can_cancel_window_close(tmp_path: Path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "未保存.md"
    source.write_text("原内容", encoding="utf-8")
    window = MainWindow()
    assert window.open_file(source)
    window.toggle_edit_mode()
    document = window.current_document()
    document.editor.setPlainText("未保存的内容")
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Cancel)
    assert window.close() is False
    assert source.read_text(encoding="utf-8") == "原内容"
    document.save()
    assert window.close() is True
    app.processEvents()


def test_save_does_not_overwrite_external_change_without_confirmation(tmp_path: Path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "冲突.md"
    source.write_text("原内容", encoding="utf-8")
    window = MainWindow()
    try:
        assert window.open_file(source)
        window.toggle_edit_mode()
        document = window.current_document()
        document.editor.setPlainText("我的修改")
        source.write_text("其他程序的修改", encoding="utf-8")
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.No)
        assert not window.save_current()
        assert source.read_text(encoding="utf-8") == "其他程序的修改"
        document.save(force=True)
    finally:
        window.close()
        app.processEvents()


def test_webengine_displays_chinese_and_relative_image(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    (image_dir / "图.png").write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lQAAAABJRU5ErkJggg=="
    ))
    source = tmp_path / "中文.md"
    source.write_text("# 中文标题\n\n![图片](images/图.png)", encoding="utf-8")
    window = MainWindow()
    window.show()
    try:
        assert window.open_file(source)
        document = window.current_document()
        loaded = []
        loop = QEventLoop()
        document.view.loadFinished.connect(lambda okay: (loaded.append(okay), loop.quit()))
        QTimer.singleShot(6000, loop.quit)
        loop.exec()
        assert loaded == [True]
        result = []
        js_loop = QEventLoop()
        document.view.page().runJavaScript(
            "JSON.stringify({title: document.querySelector('h1')?.textContent, image: document.querySelector('img')?.naturalWidth})",
            lambda value: (result.append(value), js_loop.quit()),
        )
        QTimer.singleShot(6000, js_loop.quit)
        js_loop.exec()
        assert result == ['{"title":"中文标题","image":1}']
    finally:
        window.close()
        app.processEvents()


def test_open_does_not_block_during_expensive_render(tmp_path: Path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "较长的笔记.md"
    source.write_text("# 较长的笔记\n\n内容", encoding="utf-8")
    window = MainWindow()
    original_render = window.renderer.render

    def slow_render(*args, **kwargs):
        time.sleep(0.7)
        return original_render(*args, **kwargs)

    monkeypatch.setattr(window.renderer, "render", slow_render)
    try:
        started = time.perf_counter()
        assert window.open_file(source)
        elapsed = time.perf_counter() - started
        assert elapsed < 0.4
        document = window.current_document()
        loop = QEventLoop()
        document.preview_updated.connect(loop.quit)
        QTimer.singleShot(3000, loop.quit)
        loop.exec()
        assert [heading.title for heading in document.headings] == ["较长的笔记"]
    finally:
        window.close()
        app.processEvents()


def test_large_highlighted_document_loads_in_webengine(tmp_path: Path):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "大型代码笔记.md"
    source.write_text(
        "# 大型代码笔记\n\n```cpp\n"
        + "int main() { std::cout << 123; return 0; }\n" * 5000
        + "```\n",
        encoding="utf-8",
    )
    window = MainWindow()
    window.show()
    try:
        assert window.open_file(source)
        document = window.current_document()
        loaded = []
        loop = QEventLoop()
        document.view.loadFinished.connect(lambda okay: (loaded.append(okay), loop.quit()))
        QTimer.singleShot(12000, loop.quit)
        loop.exec()
        assert loaded == [True]
        nodes = []
        js_loop = QEventLoop()
        document.view.page().runJavaScript(
            "document.querySelectorAll('*').length",
            lambda value: (nodes.append(value), js_loop.quit()),
        )
        QTimer.singleShot(3000, js_loop.quit)
        js_loop.exec()
        assert nodes and nodes[0] < 100
    finally:
        window.close()
        app.processEvents()


def test_latest_edit_replaces_render_started_before_it(tmp_path: Path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    source = tmp_path / "实时预览.md"
    source.write_text("# 旧标题", encoding="utf-8")
    window = MainWindow()
    original_render = window.renderer.render

    def slow_render(*args, **kwargs):
        time.sleep(0.35)
        return original_render(*args, **kwargs)

    monkeypatch.setattr(window.renderer, "render", slow_render)
    window.show()
    try:
        assert window.open_file(source)
        document = window.current_document()
        window.toggle_edit_mode()
        document.editor.setPlainText("# 新标题")
        loop = QEventLoop()
        document.view.loadFinished.connect(lambda okay: loop.quit() if okay and document.headings[0].title == "新标题" else None)
        QTimer.singleShot(5000, loop.quit)
        loop.exec()
        assert [heading.title for heading in document.headings] == ["新标题"]
        rendered = []
        js_loop = QEventLoop()
        document.view.page().runJavaScript(
            "document.querySelector('h1')?.textContent",
            lambda value: (rendered.append(value), js_loop.quit()),
        )
        QTimer.singleShot(3000, js_loop.quit)
        js_loop.exec()
        assert rendered == ["新标题"]
        document.save()
    finally:
        window.close()
        app.processEvents()
