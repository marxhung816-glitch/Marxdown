"""File validation, UTF-8 reading and local Markdown link resolution."""

from pathlib import Path
import os
import tempfile
from urllib.parse import unquote, urlsplit


MARKDOWN_SUFFIXES = {".md", ".markdown"}


def is_markdown(path: Path) -> bool:
    return path.suffix.lower() in MARKDOWN_SUFFIXES


def read_markdown(path: Path) -> str:
    path = Path(path)
    if not is_markdown(path):
        raise ValueError(f"不是 Markdown 文件：{path.name}")
    return path.read_text(encoding="utf-8-sig")


def write_markdown(path: Path, content: str) -> None:
    """Atomically replace a Markdown file with UTF-8 text."""
    path = Path(path)
    if not is_markdown(path):
        raise ValueError(f"不是 Markdown 文件：{path.name}")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def resolve_markdown_link(source: Path, href: str) -> Path | None:
    """Return a local Markdown target, or None for other kinds of links."""
    parts = urlsplit(href)
    if parts.scheme or parts.netloc or not parts.path:
        return None
    target = (Path(source).parent / unquote(parts.path)).resolve()
    return target if is_markdown(target) else None
