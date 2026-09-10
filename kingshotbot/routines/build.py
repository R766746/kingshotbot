"""Build routine: keep construction and research queues busy.

Upgrade priority follows community guidance: Town Center first, then
whatever prerequisite blocks it, then resource/military buildings. The
routine is template-driven, so it simply starts whatever upgrade is
available when the slot is idle.
"""

from __future__ import annotations

import logging
from typing import List

from .base import Routine, RoutineResult, register

log = logging.getLogger("kingshotbot.routines.build")


@register
class BuildRoutine(Routine):
    name = "build"
    description = "Start construction/research upgrades when queues are idle"

    def run(self, agent) -> RoutineResult:
        actions: List[str] = []
        if not agent.find_and_tap(["btn_build_menu", "btn_build"], timeout=6.0):
            agent.recover()
            if not agent.find_and_tap(["btn_build_menu", "btn_build"], timeout=4.0):
                return RoutineResult(self.name, False, "could not open build menu")

        # construction slot
        if agent.find_and_tap(["btn_construction", "btn_build_slot"], timeout=5.0):
            if agent.find_and_tap(["btn_upgrade", "btn_build_now"], timeout=5.0):
                Routine.note(actions, "construction upgrade started")
            else:
                Routine.note(actions, "construction queue busy or button hidden")
            agent.close_dialog()
        else:
            Routine.note(actions, "construction entry not found")

        # research slot
        if agent.find_and_tap(["btn_research", "btn_academy"], timeout=5.0):
            if agent.find_and_tap(["btn_research_start", "btn_study"], timeout=5.0):
                Routine.note(actions, "research started")
            else:
                Routine.note(actions, "research queue busy or button hidden")
            agent.close_dialog()
        else:
            Routine.note(actions, "research entry not found")

        agent.back()  # leave build menu
        summary = "; ".join(actions) or "nothing to do"
        return RoutineResult(self.name, True, summary, actions)
