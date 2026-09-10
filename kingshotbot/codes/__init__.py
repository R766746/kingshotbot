"""Gift-code discovery package."""

from .sources import CodeFinding, SOURCES, fetch_source, looks_like_code, parse_html
from .manager import CodeManager

__all__ = [
    "CodeFinding",
    "SOURCES",
    "fetch_source",
    "looks_like_code",
    "parse_html",
    "CodeManager",
]
