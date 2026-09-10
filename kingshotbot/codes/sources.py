"""Scrapers for public Kingshot gift-code pages.

Each source is an HTML page listing "active" and "expired" codes. The
generic parser:

1. splits the page at the first "expired" section marker,
2. pulls code-shaped tokens (``<strong>CODE</strong>`` style markup and
   table cells) from the active part,
3. validates them with heuristics (length, charset, blocklist).

Parsing is intentionally conservative: a missed code is harmless, a
false positive just fails to redeem. Everything is best-effort - sites
change layouts constantly.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests

log = logging.getLogger("kingshotbot.codes")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass(frozen=True)
class CodeFinding:
    code: str
    source: str
    url: str


SOURCES: Dict[str, str] = {
    "pockettactics": "https://www.pockettactics.com/kingshot/codes",
    "pocketgamer": "https://www.pocketgamer.com/kingshot/codes/",
    "topuplive": "https://www.topuplive.com/news/kingshot-gift-codes-november-2025.html",
    "lootbar": "https://www.lootbar.com/blog/en/newest-kingshot-gift-codes.html",
    "gamsgo": "https://www.gamsgo.com/blog/kingshot-gift-code",
}

# Tokens that look like codes but never are.
_BLOCKLIST = {
    # months / weekdays (code pages are full of dates)
    "january", "february", "march", "april", "june", "july", "august",
    "september", "october", "november", "december", "jan", "feb", "mar",
    "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday",
    # game / brand / site words
    "kingshot", "kingdom", "governor", "alliance", "arena", "century",
    "discord", "reddit", "facebook", "youtube", "twitter", "instagram",
    "telegram", "tiktok", "pockettactics", "pocketgamer", "topuplive",
    "lootbar", "gamsgo", "official", "store", "rewards", "redeem",
    "codes", "guide", "update", "news", "gems", "speedup", "speedups",
    "survival", "strategy", "download", "android", "iphone", "ipad",
}

_EXPIRED_MARKERS = re.compile(
    r"expired\s+(?:kingshot\s+)?(?:gift\s+)?codes|>\s*expired\s*codes?\s*<",
    re.IGNORECASE,
)
# code-shaped tokens wrapped in emphasis/list/table markup
_TOKEN_HTML = re.compile(
    r">\s*([A-Za-z0-9][A-Za-z0-9]{3,19})\s*<"
    r"(?:/\s*(?:strong|b|code|li|span|p|td|th|em|div)\s*>|br\s*/?>)",
    re.IGNORECASE,
)


def looks_like_code(token: str) -> bool:
    """Heuristic validation of a candidate gift code."""
    token = token.strip()
    if not 4 <= len(token) <= 20:
        return False
    if not re.fullmatch(r"[A-Za-z0-9]+", token):
        return False
    if not any(c.isalpha() for c in token):
        return False  # pure numbers are dates/ids
    if token.lower() in _BLOCKLIST:
        return False
    has_digit = any(c.isdigit() for c in token)
    all_caps = token == token.upper()
    # accept anything with a digit; pure-letter tokens must be ALL-CAPS
    return has_digit or all_caps


def parse_html(source: str, url: str, html: str) -> List[CodeFinding]:
    """Extract active codes from a code-listing page's HTML."""
    marker = _EXPIRED_MARKERS.search(html)
    active_part = html[: marker.start()] if marker else html
    # unescape entities that show up inside code markup
    active_part = active_part.replace("&amp;", "&")

    seen, findings = set(), []
    for match in _TOKEN_HTML.finditer(active_part):
        token = match.group(1)
        if not looks_like_code(token):
            continue
        key = token.upper()
        if key in seen:
            continue
        seen.add(key)
        findings.append(CodeFinding(code=token, source=source, url=url))
    log.debug("source %s: %d candidate codes", source, len(findings))
    return findings


def fetch_source(name: str, timeout: float = 15.0,
                 session: Optional[requests.Session] = None) -> List[CodeFinding]:
    """Download and parse one source. Raises on network errors."""
    url = SOURCES[name]
    requester = session or requests
    resp = requester.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return parse_html(name, url, resp.text)
