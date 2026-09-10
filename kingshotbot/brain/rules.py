"""Rule-based brain: safe, deterministic UI navigation.

The rule brain encodes Kingshot UI conventions learned from research:
dialogs have a close (X) button top-right, Android BACK closes dialogs,
and every routine flow is a find-template -> tap -> verify chain. It also
implements the recovery policy used when an expected element is missing.
"""

from __future__ import annotations

import logging
from typing import Optional

from .base import Brain, Decision, Observation

log = logging.getLogger("kingshotbot.brain.rules")

# Templates that mean "a dialog is open".
CLOSE_BUTTONS = ("btn_close", "close", "x_button")


class RuleBrain(Brain):
    """Deterministic fallback/primary brain - no network, no cost."""

    name = "rules"

    def __init__(self, recovery_presses_back: bool = True) -> None:
        self.recovery_presses_back = recovery_presses_back

    def decide(self, observation: Observation, context: Optional[dict] = None) -> Decision:
        context = context or {}
        wanted = context.get("wanted") or []  # template names the routine wants
        for match in observation.matches:
            if match.name in wanted:
                return Decision(action="tap", match=match,
                                reason=f"wanted element {match.name}")
        # nothing wanted matched -> let the routine drive recovery
        return Decision(action="wait", reason="no wanted element visible")
