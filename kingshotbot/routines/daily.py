"""Daily routine: login rewards, production, quests, mail, alliance help.

Mirrors the community "daily 15-minute routine": collect city production,
claim the daily login reward, sweep quests/mail, and help all alliance
timers (free speed-ups for everyone).
"""

from __future__ import annotations

import logging
from typing import List

from ..vision import Match
from .base import Routine, RoutineResult, register

log = logging.getLogger("kingshotbot.routines.daily")

# Element names the routine looks for, in order.
DIALOG_FLOWS = [
    ("daily_login", ("btn_daily_claim",), "claimed daily login reward"),
    ("quests", ("btn_quest", "btn_claim"), "claimed quest rewards"),
    ("mail", ("btn_mail", "btn_claim_all"), "claimed mail"),
    ("alliance help", ("btn_alliance", "btn_help_all"), "helped all alliance timers"),
]


@register
class DailyRoutine(Routine):
    name = "daily"
    description = "Collect production, daily login, quests, mail, alliance help"

    def run(self, agent) -> RoutineResult:
        actions: List[str] = []
        ok = True

        # 0. dismiss any startup dialog (daily login, news, events ...).
        for label, buttons, note in DIALOG_FLOWS:
            if not self._flow(agent, label, buttons, note, actions):
                ok = False

        # 1. collect city production bubbles (may be several).
        collected = 0
        while True:
            m: Match | None = agent.vision.wait_for(
                agent.device, ["bubble_production", "production_bubble"],
                timeout=1.0, sleep_fn=agent.sleep,
            )
            if m is None:
                break
            agent.tap(m)
            collected += 1
            if collected >= 10:  # safety bound
                break
        if collected:
            Routine.note(actions, f"collected {collected} production bubble(s)")
        else:
            Routine.note(actions, "no production bubbles found")

        return RoutineResult(routine=self.name, ok=ok, summary="; ".join(actions),
                             actions=actions)

    def _flow(self, agent, label: str, buttons, note: str,
              actions: List[str]) -> bool:
        """Open a dialog, press its claim button, come back."""
        opener, claim = buttons[0], buttons[-1]
        # If the dialog is already open on screen, claim directly.
        screen = agent.device.screenshot()
        if agent.vision.find(screen, claim):
            agent.find_and_tap([claim], timeout=4.0)
            Routine.note(actions, note)
            return True
        m = agent.vision.find(screen, opener)
        if m is None:
            log.debug("opener %r not visible for flow %s", opener, label)
            Routine.note(actions, f"{label}: opener not visible (skipped)")
            return True  # not an error - screen layout may differ
        agent.tap(m)
        if agent.find_and_tap([claim], timeout=2.5):
            Routine.note(actions, note)
            agent.close_dialog()
            return True
        # Claim button absent after opening the dialog usually means the
        # reward was already claimed today - not an error.
        Routine.note(actions, f"{label}: nothing to claim (already claimed?)")
        agent.close_dialog()
        return True
