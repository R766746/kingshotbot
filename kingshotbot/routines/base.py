"""Routine base class and registry."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Type

log = logging.getLogger("kingshotbot.routines")


@dataclass
class RoutineResult:
    """Outcome of one routine run."""

    routine: str
    ok: bool
    summary: str = ""
    actions: List[str] = field(default_factory=list)
    duration: float = 0.0


class Routine:
    """A named, self-contained unit of game automation."""

    name: str = "base"
    description: str = ""

    def run(self, agent) -> RoutineResult:  # pragma: no cover - interface
        raise NotImplementedError

    @staticmethod
    def note(result_actions: List[str], text: str) -> None:
        log.info("  - %s", text)
        result_actions.append(text)


ROUTINES: Dict[str, Type[Routine]] = {}


def register(cls: Type[Routine]) -> Type[Routine]:
    ROUTINES[cls.name] = cls
    return cls


def available_routines() -> List[str]:
    return sorted(ROUTINES)
