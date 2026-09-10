"""Brain interface: turns observations into actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Observation:
    """What the agent currently sees."""

    screen: object = None  # np.ndarray (BGR)
    matches: List = field(default_factory=list)  # [vision.Match]
    screen_label: Optional[str] = None  # best-guess screen name


@dataclass
class Decision:
    """What the brain wants to do next."""

    action: str  # "tap" | "swipe" | "back" | "wait" | "report" | "abort"
    match: Optional[object] = None
    x: int = 0
    y: int = 0
    reason: str = ""
    payload: Optional[dict] = None


class Brain:
    """Base class for decision engines."""

    name = "base"

    def decide(self, observation: Observation, context: Optional[dict] = None) -> Decision:
        raise NotImplementedError
