"""Export the current Markdown text to Word and PDF files."""

from html import escape
import os
from pathlib import Path
import tempfile
from urllib.parse import unquote, urlsplit

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.shared import Inches, Pt
from markdown_it import MarkdownIt
from PySide6.QtCore import QObject, QRunnable, QThreadPool, QUrl, Signal
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings

from .tab_manager import RenderTask


def _set_chinese_font(style, name: str) -> None:
    style.font.name = name
    fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
    fonts.set(qn("w:eastAsia"), name)


def _add_hyperlink(paragraph, label: str, url: str) -> None:
    relationship = paragraph.part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship)
    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "2768A5")
    properties.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    properties.append(underline)
    run.append(properties)
    text = OxmlElement("w:t")
    text.text = label
    run.append(text)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def _add_image(paragraph, source: str, alt: str, markdown_path: Path) -> None:
    parts = urlsplit(source)
    if parts.scheme in {"http", "https"}:
        paragraph.add_run(alt or source)
        return
    image_path = Path(unquote(parts.path))
    if not image_path.is_absolute():
        image_path = markdown_path.parent / image_path
    try:
        shape = paragraph.add_run().add_picture(str(image_path))
    except (OSError, ValueError):
        paragraph.add_run(alt or source)
        return
    limit = Inches(6.2)
    if shape.width > limit:
        shape.height = int(shape.height * limit / shape.width)
        shape.width = limit


def _add_inline(paragraph, children, markdown_path: Path, bold_default: bool = False) -> None:
    bold = bold_default
    italic = False
    strike = False
    link = ""
    for token in children or []:
        kind = token.type
        if kind == "strong_open":
            bold = True
        elif kind == "strong_close":
            bold = bold_default
        elif kind == "em_open":
            italic = True
        elif kind == "em_close":
            italic = False
        elif kind == "s_open":
            strike = True
        elif kind == "s_close":
            strike = False
        elif kind == "link_open":
            link = token.attrGet("href") or ""
        elif kind == "link_close":
            link = ""
        elif kind == "image":
            _add_image(paragraph, token.attrGet("src") or "", token.content, markdown_path)
        elif kind in {"softbreak", "hardbreak"}:
            paragraph.add_run().add_break()
        elif kind in {"text", "code_inline", "html_inline"} and token.content:
            if link:
                _add_hyperlink(paragraph, token.content, link)
            else:
                run = paragraph.add_run(token.content)
                run.bold = bold
                run.italic = italic
                run.font.strike = strike
                if kind == "code_inline":
                    run.font.name = "Consolas"


def export_docx(text: str, markdown_path: Path, output_path: Path) -> None:
    """Write editable Word content using the text currently in the editor."""
    markdown_path = Path(markdown_path)
    output_path = Path(output_path)
    document = Document()
    normal = document.styles["Normal"]
    _set_chinese_font(normal, "Microsoft YaHei")
    normal.font.size = Pt(10.5)
    for level in range(1, 7):
        _set_chinese_font(document.styles[f"Heading {level}"], "Microsoft YaHei")
    code_style = document.styles.add_style("Markdown Code", WD_STYLE_TYPE.PARAGRAPH)
    code_style.font.name = "Consolas"
    code_style.font.size = Pt(9)

    parser = MarkdownIt("default", {"html": False})
    parser.enable(["table", "strikethrough"])
    tokens = parser.parse(text)
    paragraph = None
    table = None
    row = None
    column = 0
    header = False
    lists: list[str] = []
    quote_depth = 0
    for index, token in enumerate(tokens):
        kind = token.type
        if kind == "heading_open":
            paragraph = document.add_heading(level=min(int(token.tag[1]), 9))
        elif kind == "paragraph_open":
            if table is not None and row is not None:
                continue
            if lists:
                style = "List Number" if lists[-1] == "ordered" else "List Bullet"
            elif quote_depth:
                style = "Quote"
            else:
                style = "Normal"
            paragraph = document.add_paragraph(style=style)
            if lists and len(lists) > 1:
                paragraph.paragraph_format.left_indent = Inches(0.25 * (len(lists) - 1))
        elif kind == "inline" and paragraph is not None:
            _add_inline(paragraph, token.children, markdown_path, header)
        elif kind in {"fence", "code_block"}:
            paragraph = document.add_paragraph(style=code_style)
            paragraph.add_run(token.content.rstrip("\n"))
        elif kind == "bullet_list_open":
            lists.append("bullet")
        elif kind == "ordered_list_open":
            lists.append("ordered")
        elif kind in {"bullet_list_close", "ordered_list_close"}:
            lists.pop()
        elif kind == "blockquote_open":
            quote_depth += 1
        elif kind == "blockquote_close":
            quote_depth -= 1
        elif kind == "table_open":
            columns = 0
            for following in tokens[index + 1:]:
                if following.type == "tr_close":
                    break
                if following.type in {"th_open", "td_open"}:
                    columns += 1
            table = document.add_table(rows=0, cols=max(columns, 1))
            table.style = "Table Grid"
        elif kind == "tr_open" and table is not None:
            row = table.add_row()
            column = 0
        elif kind in {"th_open", "td_open"} and row is not None:
            paragraph = row.cells[column].paragraphs[0]
            header = kind == "th_open"
            column += 1
        elif kind in {"th_close", "td_close"}:
            header = False
        elif kind == "tr_close":
            row = None
        elif kind == "table_close":
            table = None
        elif kind == "hr":
            document.add_paragraph("―――")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)


class WordExportSignals(QObject):
    finished = Signal(str, bool, str)


class WordExportTask(QRunnable):
    def __init__(self, text: str, markdown_path: Path, output_path: Path) -> None:
        super().__init__()
        self.text = text
        self.markdown_path = markdown_path
        self.output_path = output_path
        self.signals = WordExportSignals()

    def run(self) -> None:
        try:
            export_docx(self.text, self.markdown_path, self.output_path)
        except Exception as error:
            self.signals.finished.emit(str(self.output_path), False, str(error))
            return
        self.signals.finished.emit(str(self.output_path), True, "")


class WordExportJob(QObject):
    finished = Signal(str, bool, str)

    def __init__(self, text: str, markdown_path: Path, output_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.task = WordExportTask(text, markdown_path, output_path)
        self.task.signals.finished.connect(self._finished)

    def start(self) -> None:
        QThreadPool.globalInstance().start(self.task)

    def _finished(self, path: str, success: bool, message: str) -> None:
        self.finished.emit(path, success, message)
        self.deleteLater()


class PdfExportJob(QObject):
    """Render a snapshot of the editor text and print it without blocking the UI."""

    finished = Signal(str, bool, str)

    def __init__(self, text: str, markdown_path: Path, output_path: Path, renderer, font_size: int, parent=None) -> None:
        super().__init__(parent)
        self.text = text
        self.markdown_path = Path(markdown_path)
        self.output_path = Path(output_path)
        self.renderer = renderer
        self.font_size = font_size
        self._task = None
        self._page = None
        self._temporary = None

    def start(self) -> None:
        self._task = RenderTask(self.renderer, (self.text, "light", self.font_size))
        self._task.signals.finished.connect(self._render_finished)
        QThreadPool.globalInstance().start(self._task)

    def _render_finished(self, _key, result, error) -> None:
        if error is not None:
            self._finish(False, f"Markdown 渲染失败：{error}")
            return
        try:
            self._temporary = tempfile.TemporaryDirectory(prefix="marxdown-pdf-", ignore_cleanup_errors=True)
            html_path = Path(self._temporary.name) / "document.html"
            base = QUrl.fromLocalFile(str(self.markdown_path.parent.resolve()) + os.sep).toString()
            print_css = (
                "<style>@page { size: A4; margin: 17mm; } "
                "@media print { .markdown-body { max-width: none; padding: 0; margin: 0; } "
                "blockquote, tr, img { break-inside: avoid; } }</style>"
            )
            html = result.html.replace(
                "<head>", f'<head><base href="{escape(base, quote=True)}">{print_css}', 1
            )
            html_path.write_text(html, encoding="utf-8")
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self._page = QWebEnginePage(self)
            self._page.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            self._page.loadFinished.connect(self._page_loaded)
            self._page.pdfPrintingFinished.connect(self._pdf_finished)
            self._page.load(QUrl.fromLocalFile(str(html_path)))
        except (OSError, ValueError) as failure:
            self._finish(False, str(failure))

    def _page_loaded(self, success: bool) -> None:
        if not success:
            self._finish(False, "导出页面加载失败")
            return
        self._page.printToPdf(str(self.output_path))

    def _pdf_finished(self, _path: str, success: bool) -> None:
        self._finish(success, "" if success else "PDF 打印失败")

    def _finish(self, success: bool, message: str) -> None:
        if self._page is not None:
            self._page.deleteLater()
            self._page = None
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None
        self.finished.emit(str(self.output_path), success, message)
        self.deleteLater()
