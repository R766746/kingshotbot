"""Persistent bot state (JSON file): what ran when, which codes are known."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("kingshotbot.state")


def _now() -> float:
    return time.time()


class BotState:
    """Tiny JSON-backed store; safe to lose, cheap to rebuild."""

    def __init__(self, path: str | Path = "state.json") -> None:
        self.path = Path(path)
        self.data: Dict[str, Any] = {
            "routine_runs": {},       # name -> [{started, finished, ok, summary}]
            "known_codes": {},        # code -> {first_seen, sources}
            "reminders_sent": {},     # key -> timestamp
            "marches": [],            # last known march status
            "last_cycle": None,       # timestamp of last full cycle
        }
        self._load()

    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, dict):
                    self.data.update(loaded)
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("state file unreadable (%s) - starting fresh", exc)

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, indent=2, default=str)
        except OSError as exc:
            log.error("could not save state: %s", exc)

    # ------------------------------------------------------------------ #
    def record_run(self, routine: str, ok: bool, summary: str = "") -> Dict[str, Any]:
        entry = {
            "started": None,  # filled by caller via start_run
            "finished": _now(),
            "ok": ok,
            "summary": summary,
        }
        self.data["routine_runs"].setdefault(routine, []).append(entry)
        # keep the log bounded
        self.data["routine_runs"][routine] = self.data["routine_runs"][routine][-50:]
        return entry

    def start_run(self, routine: str) -> float:
        runs = self.data["routine_runs"].setdefault(routine, [])
        started = _now()
        runs.append({"started": started, "finished": None, "ok": None, "summary": ""})
        self.data["routine_runs"][routine] = runs[-50:]
        return started

    def finish_run(self, routine: str, ok: bool, summary: str = "") -> None:
        runs = self.data["routine_runs"].get(routine, [])
        for run in reversed(runs):
            if run.get("finished") is None and run.get("ok") is None:
                run.update(finished=_now(), ok=ok, summary=summary)
                break
        else:
            runs.append({"started": None, "finished": _now(),
                         "ok": ok, "summary": summary})

    def last_run(self, routine: str) -> Optional[Dict[str, Any]]:
        runs = self.data["routine_runs"].get(routine) or []
        return runs[-1] if runs else None

    # -- gift codes ------------------------------------------------------
    def add_code(self, code: str, source: str) -> bool:
        """Record a code; returns True if it was new."""
        code = code.strip().upper()
        if code in self.data["known_codes"]:
            entry = self.data["known_codes"][code]
            if source not in entry["sources"]:
                entry["sources"].append(source)
            return False
        self.data["known_codes"][code] = {
            "first_seen": _now(),
            "sources": [source],
        }
        return True

    def known_codes(self) -> Dict[str, Any]:
        return dict(self.data["known_codes"])

    # -- reminders --------------------------------------------------------
    def reminder_due(self, key: str, min_gap_seconds: float) -> bool:
        last = self.data["reminders_sent"].get(key, 0)
        return (_now() - last) >= min_gap_seconds

    def mark_reminder(self, key: str) -> None:
        self.data["reminders_sent"][key] = _now()

    def mark_cycle(self) -> None:
        self.data["last_cycle"] = _now()
