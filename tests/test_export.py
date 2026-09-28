"""Verify exported files contain the current Markdown content."""

from pathlib import Path

from docx import Document
from pypdf import PdfReader
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication


def test_word_export_keeps_chinese_structure_and_relative_image(tmp_path: Path):
    from app.export_manager import export_docx

    source = tmp_path / "中文笔记.md"
    image = tmp_path / "图片.png"
    picture = QImage(4, 4, QImage.Format.Format_RGB32)
    picture.fill(QColor("#369adf"))
    assert picture.save(str(image))
    text = (
        "# 第一章 中文标题\n\n"
        "普通**加粗**文字，参考[网站](https://example.com)。\n\n"
        "- 第一项\n- 第二项\n\n"
        "| 姓名 | 成绩 |\n| --- | --- |\n| 小明 | 95 |\n\n"
        "![示例图片](图片.png)\n\n"
        "```python\nprint('中文')\n```\n"
    )
    source.write_text("磁盘旧内容", encoding="utf-8")
    target = tmp_path / "导出结果.docx"

    export_docx(text, source, target)

    word = Document(target)
    paragraphs = word.paragraphs
    assert paragraphs[0].style.name == "Heading 1"
    assert paragraphs[0].text == "第一章 中文标题"
    assert any(run.bold and run.text == "加粗" for p in paragraphs for run in p.runs)
    assert any("第一项" in p.text for p in paragraphs)
    assert word.tables[0].cell(1, 0).text == "小明"
    assert word.tables[0].cell(1, 1).text == "95"
    assert len(word.inline_shapes) == 1
    assert any("print('中文')" in p.text for p in paragraphs)
    assert "磁盘旧内容" not in "\n".join(p.text for p in paragraphs)


def test_pdf_export_uses_current_chinese_text_and_local_image(tmp_path: Path):
    from app.export_manager import PdfExportJob
    from app.markdown_renderer import MarkdownRenderer

    app = QApplication.instance() or QApplication([])
    source = tmp_path / "笔记.md"
    source.write_text("旧内容", encoding="utf-8")
    image = tmp_path / "图片.png"
    picture = QImage(24, 24, QImage.Format.Format_RGB32)
    picture.fill(QColor("#369adf"))
    assert picture.save(str(image))
    target = tmp_path / "导出.pdf"
    job = PdfExportJob("# 新标题\n\n中文新内容。\n\n![图片](图片.png)", source, target, MarkdownRenderer(), 16)
    result = []
    loop = QEventLoop()
    job.finished.connect(lambda path, success, message: (result.append((path, success, message)), loop.quit()))
    QTimer.singleShot(15000, loop.quit)
    job.start()
    loop.exec()

    assert result and result[0][1], result
    assert target.read_bytes().startswith(b"%PDF")
    pdf = PdfReader(target)
    combined = "\n".join(page.extract_text() for page in pdf.pages)
    assert "新标题" in combined
    assert "中文新内容" in combined
    assert "旧内容" not in combined
