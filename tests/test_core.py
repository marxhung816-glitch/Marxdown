from pathlib import Path

import pytest

from app.file_manager import read_markdown, resolve_markdown_link, write_markdown
from app.markdown_renderer import MarkdownRenderer


def test_utf8_chinese_markdown_and_local_links(tmp_path: Path):
    source = tmp_path / "学习笔记.md"
    source.write_text("# 中文标题\n\n你好，世界。", encoding="utf-8")
    sibling = tmp_path / "第二章.markdown"
    sibling.write_text("# 第二章", encoding="utf-8")

    assert "你好，世界" in read_markdown(source)
    assert resolve_markdown_link(source, "%E7%AC%AC%E4%BA%8C%E7%AB%A0.markdown") == sibling
    assert resolve_markdown_link(source, "https://example.com") is None


def test_renderer_supports_requested_syntax_and_unique_toc_ids():
    content = """# 第一章
## 重复
## 重复

**粗体** *斜体* ~~删除~~ `行内代码`

> 引用

1. 有序
2. 条目

- 无序

| 列 | 值 |
| --- | --- |
| 中文 | 内容 |

[第二章](chapter2.md) ![图片](images/图.png)

```python
print("你好")
```
"""
    result = MarkdownRenderer().render(content, "light", 16)
    html = result.html
    assert [item.anchor for item in result.headings] == ["heading-1", "heading-2", "heading-3"]
    for fragment in (
        "<strong>粗体</strong>", "<em>斜体</em>", "<s>删除</s>",
        "<blockquote>", "<ol>", "<ul>", "<table>",
        'href="chapter2.md"', 'src="images/%E5%9B%BE.png"',
        "highlight", "你好", "<code>行内代码</code>",
    ):
        assert fragment in html


def test_renderer_escapes_untrusted_html_and_switches_theme():
    renderer = MarkdownRenderer()
    light = renderer.render("<script>alert(1)</script>\n\n```python\npass\n```", "light", 16).html
    dark = renderer.render("# 标题", "dark", 18).html
    assert "<script>alert" not in light
    assert "&lt;script&gt;" in light
    assert "github-dark" in dark
    assert "font-size: 18px" in dark


def test_missing_and_non_markdown_files_are_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        read_markdown(tmp_path / "bad.txt")
    with pytest.raises(FileNotFoundError):
        read_markdown(tmp_path / "missing.md")


def test_write_markdown_saves_chinese_utf8(tmp_path: Path):
    target = tmp_path / "学习笔记.md"
    target.write_text("旧内容", encoding="utf-8")
    write_markdown(target, "# 新内容\n\n中文可以保存。")
    assert target.read_bytes() == "# 新内容\n\n中文可以保存。".encode("utf-8")


def test_large_code_block_avoids_excessive_highlight_nodes():
    source = "# 大型代码笔记\n\n```cpp\n" + "int value = 123;\n" * 5000 + "```\n"
    html = MarkdownRenderer().render(source, "dark", 16).html
    assert "int value = 123;" in html
    assert html.count("<span") < 100
    assert len(html) < len(source) * 2


def test_normal_code_block_keeps_syntax_highlighting():
    html = MarkdownRenderer().render("```cpp\nint value = 123;\n```", "light", 16).html
    assert '<span class="' in html


def test_many_code_blocks_have_bounded_highlight_nodes():
    source = "\n".join(
        "```cpp\n" + "int value = 123;\n" * 60 + "```"
        for _ in range(100)
    )
    html = MarkdownRenderer().render(source, "light", 16).html
    assert html.count("<span") < 12000
    assert html.count("int value = 123;") > 30
