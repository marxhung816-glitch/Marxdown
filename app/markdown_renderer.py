"""Markdown-it rendering with a generated outline and Pygments styles."""

from dataclasses import dataclass
from html import escape
from pathlib import Path
import sys

from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.util import ClassNotFound


@dataclass(frozen=True)
class Heading:
    level: int
    title: str
    anchor: str


@dataclass(frozen=True)
class RenderResult:
    html: str
    headings: list[Heading]


def _resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


class MarkdownRenderer:
    def render(self, text: str, theme: str = "light", font_size: int = 16) -> RenderResult:
        theme = "dark" if theme == "dark" else "light"
        formatter = HtmlFormatter(style="monokai" if theme == "dark" else "friendly", cssclass="highlight")
        code_formatter = HtmlFormatter(style=formatter.style, nowrap=True)
        highlight_budget = 20_000

        def highlight_code(code: str, language: str, _attrs: str) -> str:
            nonlocal highlight_budget
            if len(code) > 12_000 or len(code) > highlight_budget:
                return f'<pre class="highlight"><code>{escape(code)}</code></pre>'
            highlight_budget -= len(code)
            try:
                lexer = get_lexer_by_name(language) if language else TextLexer()
            except ClassNotFound:
                lexer = TextLexer()
            colored = highlight(code, lexer, code_formatter)
            return f'<pre class="highlight"><code>{colored}</code></pre>'

        parser = MarkdownIt("default", {"html": False, "linkify": False, "highlight": highlight_code})
        parser.enable(["table", "strikethrough"])
        tokens = parser.parse(text)
        headings: list[Heading] = []
        for index, token in enumerate(tokens):
            if token.type != "heading_open":
                continue
            inline = tokens[index + 1]
            title = "".join(child.content for child in (inline.children or []) if child.type in {"text", "code_inline", "image"}).strip()
            title = title or inline.content.strip() or "（无标题）"
            anchor = f"heading-{len(headings) + 1}"
            token.attrSet("id", anchor)
            headings.append(Heading(int(token.tag[1]), title, anchor))

        body = parser.renderer.render(tokens, parser.options, {})
        css_file = _resource_root() / "resources" / "css" / f"github-{theme}.css"
        stylesheet = css_file.read_text(encoding="utf-8")
        pygments_css = formatter.get_style_defs(".highlight")
        document = (
            '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<style>{stylesheet}\n{pygments_css}\n.markdown-body {{ font-size: {int(font_size)}px; }}</style>"
            f'</head><body class="github-{theme}"><main class="markdown-body">{body}</main></body></html>'
        )
        return RenderResult(document, headings)
