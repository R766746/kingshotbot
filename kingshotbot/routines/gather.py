"""Gathering routine: keep march queues farming resource tiles.

Community-verified facts baked into the defaults:
* best tiles are level 6-8 (levels 9-10 do not exist in Kingshot)
* keep one march free for auto-rally-join if you rely on it
* stone and iron are usually the bottleneck for building upgrades
* gathering heroes: Olive (bread), Forrest (wood), Edwin (stone), Seth (iron)
"""

from __future__ import annotations

import logging
from typing import Dict, List

from .base import Routine, RoutineResult, register

log = logging.getLogger("kingshotbot.routines.gather")

TILE_TEMPLATES = {
    "bread": ("tile_bread", "tile_food"),
    "wood": ("tile_wood", "tile_lumber"),
    "stone": ("tile_stone",),
    "iron": ("tile_iron",),
}


@register
class GatherRoutine(Routine):
    name = "gather"
    description = "Send idle marches to gather resource tiles on the world map"

    def run(self, agent) -> RoutineResult:
        actions: List[str] = []
        cfg = agent.config.gather
        if not cfg.enabled:
            return RoutineResult(self.name, True, "gathering disabled in config")

        priority: List[str] = [r.lower() for r in cfg.resource_priority]
        unknown = [r for r in priority if r not in TILE_TEMPLATES]
        if unknown:
            return RoutineResult(
                self.name, False,
                f"unknown resources in gather.resource_priority: {unknown}"
            )

        # 1. get to the world map
        if not agent.find_and_tap(["btn_world_map", "world_map"], timeout=6.0):
            agent.recover()
            if not agent.find_and_tap(["btn_world_map", "world_map"], timeout=4.0):
                return RoutineResult(self.name, False,
                                     "could not open the world map")

        # 2. fill march queues
        sent: Dict[str, int] = {r: 0 for r in priority}
        attempts = 0
        max_attempts = cfg.march_count + 2
        while sum(sent.values()) < cfg.march_count and attempts < max_attempts:
            attempts += 1
            resource = self._next_resource(priority, sent, cfg.march_count)
            tile_names = self._tile_names(agent, resource)
            if not tile_names:
                Routine.note(actions, f"no tile template for {resource} - skipping")
                continue
            tile = agent.find_and_tap(tile_names, timeout=4.0)
            if tile is None:
                Routine.note(actions, f"no {resource} tile visible")
                continue
            # 3. open the gather dialog and confirm the march
            if not agent.find_and_tap(["btn_search_gather", "btn_gather", "btn_search"],
                                      timeout=5.0):
                Routine.note(actions, f"{resource}: gather button not found")
                agent.close_dialog()
                continue
            if agent.find_and_tap(["btn_march_send", "btn_send", "btn_march"],
                                  timeout=5.0):
                sent[resource] += 1
                Routine.note(actions, f"sent march #{sum(sent.values())} -> {resource}")
            else:
                Routine.note(actions, f"{resource}: march confirm button not found")
                agent.close_dialog()

        # 4. back to the city
        agent.find_and_tap(["btn_city", "btn_city_view"], timeout=4.0)

        total = sum(sent.values())
        summary = (f"sent {total}/{cfg.march_count} marches: "
                   + ", ".join(f"{r}={n}" for r, n in sent.items()))
        Routine.note(actions, summary)
        return RoutineResult(self.name, total > 0, summary, actions)

    def _next_resource(self, priority: List[str], sent: Dict[str, int],
                       cap: int) -> str:
        """Round-robin over the priority list."""
        for resource in priority:
            if sent[resource] < max(1, cap // len(priority)):
                return resource
        return priority[0]

    def _tile_names(self, agent, resource: str) -> List[str]:
        names = list(TILE_TEMPLATES[resource])
        return [n for n in names if agent.vision.has(n)]
