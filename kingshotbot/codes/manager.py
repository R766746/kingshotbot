"""CodeManager: merge codes from all sources + a manual file, dedupe."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from .sources import CodeFinding, SOURCES, fetch_source, looks_like_code

log = logging.getLogger("kingshotbot.codes.manager")


class CodeManager:
    """Fetches codes from every configured source and a manual file."""

    def __init__(
        self,
        sources: Optional[List[str]] = None,
        manual_codes_file: str | Path | None = None,
        timeout: float = 15.0,
    ) -> None:
        # explicit empty list = "no online sources" (manual codes only)
        self.source_names = list(SOURCES) if sources is None else list(sources)
        unknown = [s for s in self.source_names if s not in SOURCES]
        if unknown:
            log.warning("unknown code sources ignored: %s (known: %s)",
                        unknown, sorted(SOURCES))
            self.source_names = [s for s in self.source_names if s in SOURCES]
        self.manual_codes_file = Path(manual_codes_file) if manual_codes_file else None
        self.timeout = timeout
        self.errors: List[tuple[str, str]] = []
        self.per_source: Dict[str, List[CodeFinding]] = {}

    # ------------------------------------------------------------------ #
    def fetch_all(self) -> List[CodeFinding]:
        """Return the deduplicated union of active codes."""
        self.errors.clear()
        self.per_source.clear()
        merged: Dict[str, CodeFinding] = {}

        for name in self.source_names:
            try:
                findings = fetch_source(name, timeout=self.timeout)
            except Exception as exc:  # noqa: BLE001 - sources fail often
                log.warning("source %s failed: %s", name, exc)
                self.errors.append((SOURCES[name], str(exc)[:200]))
                continue
            self.per_source[name] = findings
            for finding in findings:
                merged.setdefault(finding.code.upper(), finding)

        for finding in self._manual_codes():
            merged.setdefault(finding.code.upper(), finding)

        result = sorted(merged.values(), key=lambda f: f.code.upper())
        log.info("code discovery: %d active codes from %d source(s), %d error(s)",
                 len(result), len(self.per_source), len(self.errors))
        return result

    # ------------------------------------------------------------------ #
    def _manual_codes(self) -> List[CodeFinding]:
        """Parse templates/manual_codes.txt (one code per line)."""
        findings: List[CodeFinding] = []
        if not self.manual_codes_file or not self.manual_codes_file.exists():
            return findings
        for line in self.manual_codes_file.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.split()
            code = parts[0]
            status = parts[1].lower() if len(parts) > 1 else "active"
            if status != "active":
                continue
            if looks_like_code(code):
                findings.append(CodeFinding(code=code, source="manual",
                                            url=str(self.manual_codes_file)))
            else:
                log.warning("manual_codes: %r does not look like a code", code)
        return findings
