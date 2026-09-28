"""The main application window, navigation and document lifecycle."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QDir, QEvent, Qt, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFileSystemModel, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton, QSplitter,
    QStackedWidget, QTabWidget, QToolButton, QTreeView, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from .branding import APP_NAME, icon_path
from .file_manager import is_markdown
from .runtime_loader import RuntimeLoader
from .settings import AppSettings, SettingsDialog
from .tab_widget import TabManager

if TYPE_CHECKING:
    from .markdown_renderer import MarkdownRenderer
    from .tab_manager import DocumentTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = AppSettings()
        self.renderer: MarkdownRenderer | None = None
        self._document_type: type[DocumentTab] | None = None
        self._pending_files: list[Path] = []
        self._runtime_error: str | None = None
        self._export_jobs: set[object] = set()
        self.current_folder: Path | None = None
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(icon_path())))
        self.resize(1160, 790)
        self.setMinimumSize(720, 480)
        self.setAcceptDrops(True)
        QApplication.instance().installEventFilter(self)
        self._build_ui()
        self._bind_shortcuts()
        self._apply_theme()
        self._update_recent_menu()
        self._update_chrome()
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(1200)
        self.poll_timer.timeout.connect(self.check_for_updates)
        self.poll_timer.start()
        self._runtime_loader: RuntimeLoader | None = None
        renderer_module = sys.modules.get(f"{__package__}.markdown_renderer")
        document_module = sys.modules.get(f"{__package__}.tab_manager")
        if renderer_module is not None and document_module is not None:
            self._runtime_ready(document_module.DocumentTab, renderer_module.MarkdownRenderer)
        else:
            loader = RuntimeLoader(self)
            loader.loaded.connect(self._runtime_ready)
            loader.failed.connect(self._runtime_failed)
            self._runtime_loader = loader
            self._runtime_start_timer = QTimer(self)
            self._runtime_start_timer.setSingleShot(True)
            self._runtime_start_timer.timeout.connect(loader.start)
            self._runtime_start_timer.start(150)

    def _runtime_ready(self, document_type: type[DocumentTab], renderer_type: type[MarkdownRenderer]) -> None:
        self._document_type = document_type
        self.renderer = renderer_type()
        if self._pending_files:
            QTimer.singleShot(0, self._open_next_pending_file)

    def _runtime_failed(self, message: str) -> None:
        self._runtime_error = message
        self._pending_files.clear()
        self.statusBar().showMessage(f"预览组件加载失败：{message}")

    def _open_next_pending_file(self) -> None:
        if not self._pending_files:
            return
        path = self._pending_files.pop(0)
        self.open_file(path)
        if self._pending_files:
            QTimer.singleShot(0, self._open_next_pending_file)

    def _build_ui(self) -> None:
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        tools = QHBoxLayout(toolbar)
        tools.setContentsMargins(12, 7, 12, 7)
        tools.setSpacing(4)
        self.sidebar_button = QToolButton()
        self.sidebar_button.setObjectName("iconButton")
        self.sidebar_button.setText("☰")
        self.sidebar_button.setToolTip("显示或隐藏侧边栏")
        self.sidebar_button.clicked.connect(self.toggle_sidebar)
        tools.addWidget(self.sidebar_button)
        self.file_label = QLabel(APP_NAME)
        self.file_label.setObjectName("fileLabel")
        tools.addWidget(self.file_label, 1)
        self.edit_button = QPushButton("编辑")
        self.edit_button.setToolTip("切换源码编辑与预览 (Ctrl+E)")
        self.edit_button.clicked.connect(self.toggle_edit_mode)
        tools.addWidget(self.edit_button)
        self.save_button = QPushButton("保存")
        self.save_button.setToolTip("保存当前文件 (Ctrl+S)")
        self.save_button.clicked.connect(self.save_current)
        tools.addWidget(self.save_button)
        self.open_button = QToolButton()
        self.open_button.setText("打开 ▾")
        self.open_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.open_menu = QMenu(self.open_button)
        self.open_menu.addAction("打开文件", self.choose_file)
        self.open_menu.addAction("打开文件夹", self.choose_folder)
        self.open_button.setMenu(self.open_menu)
        tools.addWidget(self.open_button)
        more_button = QToolButton()
        more_button.setObjectName("iconButton")
        more_button.setText("⋯")
        more_button.setToolTip("更多操作")
        more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_menu = QMenu(more_button)
        self.recent_menu = self.more_menu.addMenu("最近打开")
        self.export_menu = self.more_menu.addMenu("导出")
        self.export_menu.addAction("导出 PDF…", self.choose_export_pdf)
        self.export_menu.addAction("导出 Word…", self.choose_export_word)
        self.more_menu.addAction("刷新当前文件", self.refresh_current)
        self.theme_action = self.more_menu.addAction("切换主题", self.toggle_theme)
        self.more_menu.addAction("关闭当前标签页", self.close_current_tab)
        self.more_menu.addSeparator()
        self.more_menu.addAction("设置…", self.show_settings)
        more_button.setMenu(self.more_menu)
        tools.addWidget(more_button)
        root_layout.addWidget(toolbar)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        self.splitter = split
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)
        sidebar_layout.setSpacing(0)
        self.sidebar_tabs = QTabWidget()
        self.sidebar_tabs.setObjectName("sidebarTabs")
        self.sidebar_tabs.setDocumentMode(True)
        self.file_model = QFileSystemModel(self)
        self.file_model.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)
        self.file_model.setNameFilters(["*.md", "*.markdown"])
        self.file_model.setNameFilterDisables(False)
        self.file_tree = QTreeView()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setAnimated(True)
        self.file_tree.setRootIsDecorated(False)
        self.file_tree.setIndentation(16)
        for column in range(1, 4):
            self.file_tree.hideColumn(column)
        self.file_tree.clicked.connect(self._tree_clicked)
        self.sidebar_tabs.addTab(self.file_tree, "文件")
        self.outline = QTreeWidget()
        self.outline.setHeaderHidden(True)
        self.outline.setIndentation(15)
        self.outline.itemClicked.connect(self._outline_clicked)
        self.sidebar_tabs.addTab(self.outline, "目录")
        sidebar_layout.addWidget(self.sidebar_tabs)
        split.addWidget(self.sidebar)

        right = QFrame()
        right.setObjectName("contentPanel")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self.stack = QStackedWidget()
        welcome = QWidget()
        welcome_layout = QVBoxLayout(welcome)
        welcome_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QLabel("✦")
        icon.setObjectName("welcomeIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(icon)
        heading = QLabel("开始阅读")
        heading.setObjectName("welcomeHeading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(heading)
        helper = QLabel("打开文件，或将 Markdown 文件拖入窗口")
        helper.setObjectName("welcomeHelp")
        helper.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(helper)
        self.stack.addWidget(welcome)
        self.tabs = TabManager()
        self.tabs.currentChanged.connect(self._update_chrome)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.stack.addWidget(self.tabs)
        right_layout.addWidget(self.stack, 1)

        self.search_bar = QFrame()
        self.search_bar.setObjectName("searchBar")
        search_layout = QHBoxLayout(self.search_bar)
        search_layout.setContentsMargins(15, 8, 15, 8)
        search_layout.addWidget(QLabel("查找"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索当前文档…")
        self.search_input.textChanged.connect(self._find_text)
        self.search_input.returnPressed.connect(self.find_next)
        search_layout.addWidget(self.search_input, 1)
        previous = QPushButton("上一个")
        previous.clicked.connect(self.find_previous)
        search_layout.addWidget(previous)
        following = QPushButton("下一个")
        following.clicked.connect(self.find_next)
        search_layout.addWidget(following)
        dismiss = QPushButton("关闭")
        dismiss.clicked.connect(self.hide_search)
        search_layout.addWidget(dismiss)
        self.search_bar.hide()
        right_layout.addWidget(self.search_bar)
        split.addWidget(right)
        split.setSizes([255, 905])
        split.setStretchFactor(1, 1)
        if not self.settings.sidebar_visible:
            self.sidebar.hide()
        root_layout.addWidget(split, 1)
        self.statusBar().showMessage("就绪")

    def _bind_shortcuts(self) -> None:
        for sequence, handler in (
            ("Ctrl+O", self.choose_file),
            ("Ctrl+Shift+O", self.choose_folder),
            ("Ctrl+W", self.close_current_tab),
            ("Ctrl+R", self.refresh_current),
            ("Ctrl+F", self.show_search),
            ("Ctrl+E", self.toggle_edit_mode),
            ("Ctrl+S", self.save_current),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(handler)

    def choose_file(self) -> None:
        initial = str(self.current_folder or Path.home())
        selected, _ = QFileDialog.getOpenFileName(self, "打开 Markdown 文件", initial, "Markdown 文件 (*.md *.markdown)")
        if selected:
            self.open_file(Path(selected))

    def choose_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "打开文件夹", str(self.current_folder or Path.home()))
        if selected:
            self.open_folder(Path(selected))

    def choose_export_pdf(self) -> None:
        document = self.current_document()
        if document is None:
            return
        selected, _ = QFileDialog.getSaveFileName(
            self, "导出 PDF", str(document.path.with_suffix(".pdf")), "PDF 文件 (*.pdf)"
        )
        if selected:
            target = Path(selected)
            self.export_pdf_to(target if target.suffix.lower() == ".pdf" else target.with_suffix(".pdf"))

    def choose_export_word(self) -> None:
        document = self.current_document()
        if document is None:
            return
        selected, _ = QFileDialog.getSaveFileName(
            self, "导出 Word", str(document.path.with_suffix(".docx")), "Word 文档 (*.docx)"
        )
        if selected:
            target = Path(selected)
            self.export_word_to(target if target.suffix.lower() == ".docx" else target.with_suffix(".docx"))

    def export_pdf_to(self, output_path: Path):
        from .export_manager import PdfExportJob

        document = self.current_document()
        if document is None:
            return None
        job = PdfExportJob(document.content, document.path, output_path, self.renderer, self.settings.font_size, self)
        self._start_export(job, "正在导出 PDF…")
        return job

    def export_word_to(self, output_path: Path):
        from .export_manager import WordExportJob

        document = self.current_document()
        if document is None:
            return None
        job = WordExportJob(document.content, document.path, output_path, self)
        self._start_export(job, "正在导出 Word…")
        return job

    def _start_export(self, job, message: str) -> None:
        self._export_jobs.add(job)
        job.finished.connect(self._export_finished)
        self.statusBar().showMessage(message)
        job.start()

    def _export_finished(self, path: str, success: bool, message: str) -> None:
        self._export_jobs.discard(self.sender())
        if success:
            self.statusBar().showMessage(f"已导出：{path}", 6000)
        else:
            self.statusBar().showMessage(f"导出失败：{message}", 6000)
            QMessageBox.warning(self, "导出失败", message)

    def open_folder(self, folder: Path, show_sidebar: bool = True) -> bool:
        folder = Path(folder).resolve()
        if not folder.is_dir():
            QMessageBox.warning(self, "无法打开文件夹", f"文件夹不存在：\n{folder}")
            return False
        self.current_folder = folder
        self.file_tree.setRootIndex(self.file_model.setRootPath(str(folder)))
        if show_sidebar:
            self.sidebar_tabs.setCurrentWidget(self.file_tree)
            self.set_sidebar_visible(True)
        self.statusBar().showMessage(f"已打开文件夹：{folder.name}", 3000)
        return True

    def open_file(self, path: Path) -> bool:
        path = Path(path).resolve()
        if not is_markdown(path):
            QMessageBox.warning(self, "文件类型不支持", "请选择 .md 或 .markdown 文件。")
            return False
        existing = self.tabs.find_document(path)
        if existing:
            self.tabs.setCurrentWidget(existing)
            self.settings.add_recent(path)
            self._update_recent_menu()
            return True
        if self._runtime_error is not None:
            QMessageBox.warning(self, "无法打开文件", f"预览组件加载失败：{self._runtime_error}")
            return False
        if self._document_type is None:
            if path not in self._pending_files:
                self._pending_files.append(path)
            self.statusBar().showMessage(f"正在准备预览：{path.name}")
            return True
        try:
            document = self._document_type(path, self.renderer, self.settings.theme, self.settings.font_size)
        except (OSError, UnicodeError, ValueError) as error:
            QMessageBox.warning(self, "无法打开文件", f"无法读取 Markdown 文件：\n{path}\n\n{error}")
            return False
        document.markdown_requested.connect(lambda target: self.open_file(Path(target)))
        document.changed.connect(lambda current=document: self._document_changed(current))
        document.preview_updated.connect(lambda current=document: self._document_preview_updated(current))
        document.render_failed.connect(lambda error: self.statusBar().showMessage(f"预览失败：{error}", 6000))
        self.tabs.add_document(document)
        self.open_folder(path.parent, show_sidebar=False)
        self.settings.add_recent(path)
        self._update_recent_menu()
        self._update_chrome()
        self.statusBar().showMessage(f"已打开 {path.name}", 3000)
        return True

    def current_document(self) -> DocumentTab | None:
        return self.tabs.document_at(self.tabs.currentIndex())

    def close_current_tab(self) -> None:
        self.close_tab(self.tabs.currentIndex())

    def close_tab(self, index: int) -> None:
        document = self.tabs.document_at(index)
        if document is None:
            return
        if not self._confirm_close_document(document):
            return
        self.tabs.removeTab(index)
        document.deleteLater()
        self._update_chrome()

    def _confirm_close_document(self, document: DocumentTab) -> bool:
        if not document.dirty:
            return True
        self.tabs.setCurrentWidget(document)
        decision = QMessageBox.question(
            self, "未保存的更改", f"保存对 {document.path.name} 的修改吗？",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if decision == QMessageBox.StandardButton.Cancel:
            return False
        if decision == QMessageBox.StandardButton.Save:
            return self.save_current()
        return decision == QMessageBox.StandardButton.Discard

    def toggle_edit_mode(self) -> None:
        document = self.current_document()
        if document:
            document.set_edit_mode(not document.editing)
            self._document_changed(document)

    def save_current(self) -> bool:
        from .tab_manager import ExternalModificationError

        document = self.current_document()
        if not document:
            return False
        try:
            document.save()
        except ExternalModificationError:
            answer = QMessageBox.question(
                self, "文件已在外部修改",
                f"{document.path.name} 已被其他程序修改。要用当前编辑内容覆盖磁盘文件吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
            try:
                document.save(force=True)
            except OSError as error:
                QMessageBox.warning(self, "保存失败", str(error))
                return False
        except (OSError, UnicodeError, ValueError) as error:
            QMessageBox.warning(self, "保存失败", str(error))
            return False
        self.statusBar().showMessage(f"已保存 {document.path.name}", 3000)
        return True

    def refresh_current(self) -> None:
        document = self.current_document()
        if document:
            if document.dirty:
                answer = QMessageBox.question(
                    self, "放弃未保存的更改？",
                    "重新载入文件会丢失当前未保存的修改。是否继续？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
            self._refresh_document(document, True)

    def _refresh_document(self, document: DocumentTab, forced: bool = False) -> None:
        try:
            document.refresh(self.settings.theme, self.settings.font_size)
        except (OSError, UnicodeError) as error:
            self.statusBar().showMessage(f"刷新失败：{error}", 6000)
            if forced:
                QMessageBox.warning(self, "刷新失败", str(error))
            return
        if document is self.current_document():
            self._update_outline()
            self.statusBar().showMessage(f"已刷新 {document.path.name}", 3000)

    def check_for_updates(self) -> None:
        for index in range(self.tabs.count()):
            document = self.tabs.document_at(index)
            if not document:
                continue
            current_stamp = document.file_stamp()
            if current_stamp is None or current_stamp == document.stamp:
                continue
            if document.dirty:
                if not document.external_change_pending:
                    document.external_change_pending = True
                    if document is self.current_document():
                        self.statusBar().showMessage("磁盘文件已变化；保存时会询问是否覆盖。", 6000)
                continue
            self._refresh_document(document)

    def _tree_clicked(self, index) -> None:
        path = Path(self.file_model.filePath(index))
        if path.is_file() and is_markdown(path):
            self.open_file(path)

    def _update_chrome(self, *_args) -> None:
        document = self.current_document()
        self.stack.setCurrentWidget(self.tabs if document else self.stack.widget(0))
        self.setWindowTitle(f"{document.path.name} - {APP_NAME}" if document else APP_NAME)
        self.file_label.setText(("● " if document and document.dirty else "") + document.path.name if document else APP_NAME)
        self.file_label.setToolTip(str(document.path) if document else "")
        self.tabs.tabBar().setVisible(self.tabs.count() > 1)
        self.edit_button.setEnabled(document is not None)
        self.edit_button.setText("完成" if document and document.editing else "编辑")
        self.save_button.setVisible(bool(document and (document.editing or document.dirty)))
        self.save_button.setEnabled(bool(document and document.dirty))
        self.export_menu.setEnabled(document is not None)
        self._update_outline()

    def _document_changed(self, document: DocumentTab) -> None:
        index = self.tabs.indexOf(document)
        if index >= 0:
            self.tabs.setTabText(index, ("● " if document.dirty else "") + document.path.name)
        if document is self.current_document():
            self._update_chrome()

    def _document_preview_updated(self, document: DocumentTab) -> None:
        if document is self.current_document():
            self._update_outline()

    def toggle_sidebar(self) -> None:
        self.set_sidebar_visible(self.sidebar.isHidden())

    def set_sidebar_visible(self, visible: bool) -> None:
        self.sidebar.setVisible(visible)
        if visible:
            self.splitter.setSizes([255, max(500, self.splitter.width() - 255)])
        self.settings.sidebar_visible = visible

    def _update_outline(self) -> None:
        self.outline.clear()
        document = self.current_document()
        if not document:
            return
        parents: list[tuple[int, QTreeWidgetItem]] = []
        for heading in document.headings:
            while parents and parents[-1][0] >= heading.level:
                parents.pop()
            item = QTreeWidgetItem([heading.title])
            item.setData(0, Qt.ItemDataRole.UserRole, heading.anchor)
            if parents:
                parents[-1][1].addChild(item)
            else:
                self.outline.addTopLevelItem(item)
            parents.append((heading.level, item))
        self.outline.expandAll()

    def _outline_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        document = self.current_document()
        if document:
            document.scroll_to_anchor(item.data(0, Qt.ItemDataRole.UserRole))

    def _update_recent_menu(self) -> None:
        self.recent_menu.clear()
        recent = self.settings.recent_files
        if not recent:
            action = self.recent_menu.addAction("暂无最近文件")
            action.setEnabled(False)
        for path in recent:
            action = self.recent_menu.addAction(path.name)
            action.setToolTip(str(path))
            action.triggered.connect(lambda _checked=False, file=path: self.open_file(file))
        if recent:
            self.recent_menu.addSeparator()
            self.recent_menu.addAction("清除记录", self._clear_recent)

    def _clear_recent(self) -> None:
        self.settings.clear_recent()
        self._update_recent_menu()

    def toggle_theme(self) -> None:
        self.settings.theme = "dark" if self.settings.theme == "light" else "light"
        self._apply_theme()
        self._rerender_tabs()

    def show_settings(self) -> None:
        dialog = SettingsDialog(self.settings.font_size, self)
        if dialog.exec():
            self.settings.font_size = dialog.font_spin.value()
            self._rerender_tabs()

    def _rerender_tabs(self) -> None:
        for index in range(self.tabs.count()):
            document = self.tabs.document_at(index)
            if document:
                document.refresh(self.settings.theme, self.settings.font_size, reread=False)

    def _apply_theme(self) -> None:
        dark = self.settings.theme == "dark"
        self.theme_action.setText("切换到浅色模式" if dark else "切换到深色模式")
        palette = {
            "bg": "#1e2025" if dark else "#ffffff",
            "panel": "#25282e" if dark else "#f8f9fa",
            "text": "#dce1e8" if dark else "#30343b",
            "muted": "#989faa" if dark else "#7e858e",
            "border": "#353a42" if dark else "#e9ebee",
            "hover": "#343942" if dark else "#eef0f2",
            "accent": "#8ab4e8" if dark else "#527cae",
        }
        QApplication.instance().setStyleSheet("""
            QWidget { background: %(bg)s; color: %(text)s; font-family: 'Segoe UI', 'Microsoft YaHei UI'; font-size: 13px; }
            QFrame#toolbar { background: %(bg)s; border-bottom: 1px solid %(border)s; }
            QFrame#sidebar { background: %(panel)s; border-right: 1px solid %(border)s; }
            QFrame#contentPanel { background: %(bg)s; }
            QFrame#searchBar { background: %(panel)s; border-top: 1px solid %(border)s; }
            QLabel#fileLabel { font-size: 13px; font-weight: 600; padding-left: 12px; }
            QLabel#welcomeIcon { color: %(muted)s; font-size: 42px; }
            QLabel#welcomeHeading { font-size: 23px; font-weight: 500; }
            QLabel#welcomeHelp { color: %(muted)s; font-size: 13px; }
            QPushButton, QToolButton { border: 0; border-radius: 6px; padding: 6px 11px; background: transparent; }
            QPushButton:hover, QToolButton:hover { background: %(hover)s; }
            QPushButton:disabled, QToolButton:disabled { color: %(muted)s; }
            QToolButton#iconButton { min-width: 34px; min-height: 30px; padding: 0; font-size: 20px; }
            QToolButton::menu-indicator { image: none; }
            QTreeView, QTreeWidget { background: %(panel)s; border: 0; outline: none; padding: 4px; }
            QTreeView::item, QTreeWidget::item { padding: 6px 4px; border-radius: 4px; }
            QTreeView::item:hover, QTreeWidget::item:hover { background: %(hover)s; }
            QTreeView::item:selected, QTreeWidget::item:selected { background: %(hover)s; color: %(accent)s; }
            QTabWidget::pane { border: 0; }
            QTabWidget#sidebarTabs, QTabWidget#sidebarTabs QTabBar, QTabWidget#sidebarTabs::pane { background: %(panel)s; }
            QTabBar::tab { background: %(bg)s; color: %(muted)s; border-bottom: 1px solid %(border)s; padding: 9px 18px; }
            QTabBar::tab:selected { color: %(text)s; border-bottom: 2px solid %(accent)s; }
            QTabBar::tab:hover { background: %(hover)s; }
            QTabWidget#sidebarTabs QTabBar::tab { background: %(panel)s; padding: 9px 19px; border: 0; }
            QTabWidget#sidebarTabs QTabBar::tab:selected { color: %(accent)s; border-bottom: 2px solid %(accent)s; }
            QPlainTextEdit#markdownEditor { background: %(panel)s; color: %(text)s; border: 0; border-right: 1px solid %(border)s; padding: 24px; selection-background-color: %(accent)s; font-family: 'Cascadia Code', Consolas, monospace; font-size: 13px; }
            QLineEdit, QSpinBox { border: 1px solid %(border)s; border-radius: 5px; padding: 6px; background: %(bg)s; }
            QLineEdit:focus, QSpinBox:focus { border-color: %(accent)s; }
            QMenu { background: %(bg)s; border: 1px solid %(border)s; padding: 5px; }
            QMenu::item { padding: 7px 24px; border-radius: 4px; }
            QMenu::item:selected { background: %(hover)s; }
            QStatusBar { background: %(bg)s; color: %(muted)s; font-size: 11px; min-height: 22px; }
            QSplitter::handle { background: %(border)s; width: 1px; }
        """ % palette)

    def show_search(self) -> None:
        if self.current_document():
            self.search_bar.show()
            self.search_input.setFocus()
            self.search_input.selectAll()

    def hide_search(self) -> None:
        self.search_bar.hide()
        document = self.current_document()
        if document:
            if document.editing:
                document.editor.setFocus()
            else:
                document.view.findText("")
                document.view.setFocus()

    def _find_text(self, text: str) -> None:
        document = self.current_document()
        if document:
            if document.editing:
                cursor = document.editor.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                document.editor.setTextCursor(cursor)
                if text:
                    document.editor.find(text)
            else:
                document.view.findText(text)

    def find_next(self) -> None:
        document = self.current_document()
        if document:
            text = self.search_input.text()
            if document.editing:
                if text and not document.editor.find(text):
                    cursor = document.editor.textCursor()
                    cursor.movePosition(QTextCursor.MoveOperation.Start)
                    document.editor.setTextCursor(cursor)
                    document.editor.find(text)
            else:
                document.view.findText(text)

    def find_previous(self) -> None:
        from PySide6.QtWebEngineCore import QWebEnginePage

        document = self.current_document()
        if document:
            text = self.search_input.text()
            if document.editing:
                if text and not document.editor.find(text, QTextDocument.FindFlag.FindBackward):
                    cursor = document.editor.textCursor()
                    cursor.movePosition(QTextCursor.MoveOperation.End)
                    document.editor.setTextCursor(cursor)
                    document.editor.find(text, QTextDocument.FindFlag.FindBackward)
            else:
                document.view.findText(text, QWebEnginePage.FindFlag.FindBackward)

    def dragEnterEvent(self, event) -> None:
        if any(url.isLocalFile() and is_markdown(Path(url.toLocalFile())) for url in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def eventFilter(self, watched, event) -> bool:
        if event.type() not in {QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop}:
            return super().eventFilter(watched, event)
        owner = watched
        while owner is not None and owner is not self:
            owner = owner.parent()
        if owner is not self or not hasattr(event, "mimeData"):
            return super().eventFilter(watched, event)
        paths = self._dropped_markdown_paths(event)
        if not paths:
            return super().eventFilter(watched, event)
        if event.type() == QEvent.Type.Drop:
            QTimer.singleShot(0, lambda files=paths: self._open_dropped_files(files))
        event.acceptProposedAction()
        return True

    def dropEvent(self, event) -> None:
        paths = self._dropped_markdown_paths(event)
        if paths:
            event.acceptProposedAction()
            QTimer.singleShot(0, lambda files=paths: self._open_dropped_files(files))
        else:
            event.ignore()

    def _dropped_markdown_paths(self, event) -> tuple[Path, ...]:
        return tuple(
            Path(url.toLocalFile()) for url in event.mimeData().urls()
            if url.isLocalFile() and is_markdown(Path(url.toLocalFile()))
        )

    def _open_dropped_files(self, paths: tuple[Path, ...]) -> None:
        for path in paths:
            self.open_file(path)

    def closeEvent(self, event) -> None:
        for index in range(self.tabs.count()):
            document = self.tabs.document_at(index)
            if document and not self._confirm_close_document(document):
                event.ignore()
                return
        QApplication.instance().removeEventFilter(self)
        if hasattr(self, "_runtime_start_timer"):
            self._runtime_start_timer.stop()
        if self._runtime_loader is not None and self._runtime_loader.isRunning():
            self._runtime_loader.wait()
        super().closeEvent(event)
