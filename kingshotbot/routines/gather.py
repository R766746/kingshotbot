"""Gathering routine: keep idle march queues farming resource tiles.

Community-verified facts baked into the defaults:
* best tiles are level 6-8 (levels 9-10 do not exist in Kingshot)
* keep one march free for auto-rally-join if you rely on it
* stone and iron are usually the bottleneck for building upgrades
* gathering heroes: Olive (bread), Forrest (wood), Edwin (stone), Seth (iron)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

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
    description = "Send idle marches with resource-specific hero formations"

    def run(self, agent) -> RoutineResult:
        actions: List[str] = []
        cfg = agent.config.gather
        if not cfg.enabled:
            return RoutineResult(self.name, True, "gathering disabled in config")

        priority: List[str] = [str(r).lower() for r in cfg.resource_priority]
        unknown = [r for r in priority if r not in TILE_TEMPLATES]
        if unknown:
            return RoutineResult(
                self.name,
                False,
                f"unknown resources in gather.resource_priority: {unknown}",
            )
        if not priority:
            return RoutineResult(
                self.name, False, "gather.resource_priority cannot be empty"
            )

        formations = {
            str(resource).lower(): str(hero).strip().lower().replace(" ", "_")
            for resource, hero in (cfg.formations or {}).items()
            if str(hero).strip()
        }

        # 1. Get to the world map.
        if not agent.find_and_tap(["btn_world_map", "world_map"], timeout=6.0):
            agent.recover()
            if not agent.find_and_tap(
                ["btn_world_map", "world_map"], timeout=4.0
            ):
                return RoutineResult(
                    self.name, False, "could not open the world map"
                )

        # 2. Detect returned/idle marches before doing any tile work. Slot
        # templates are preferred; OCR of the busy/total counter is fallback.
        status = self._march_status(agent)
        idle: Optional[int] = None
        if status is None:
            target = max(0, int(cfg.march_count))
            Routine.note(actions, f"march counter unavailable; target={target}")
        else:
            idle = status.idle
            agent.state.set_march_status(status.busy, status.total, status.source)
            reserve = 1 if cfg.keep_one_march_free else 0
            target = min(max(0, int(cfg.march_count)), max(0, idle - reserve))
            Routine.note(
                actions,
                f"marches: {status.busy}/{status.total} busy, {idle} idle "
                f"({status.source}); target={target}",
            )

        if target == 0:
            agent.find_and_tap(["btn_city", "btn_city_view"], timeout=4.0)
            summary = "no idle marches available after reservation"
            Routine.note(actions, summary)
            return RoutineResult(self.name, True, summary, actions)

        # 3. Fill only the number of queues detected as available.
        sent: Dict[str, int] = {resource: 0 for resource in priority}
        attempts = 0
        max_attempts = target + len(priority) + 2
        while sum(sent.values()) < target and attempts < max_attempts:
            attempts += 1
            resource = self._next_resource(priority, sent, target)
            tile_names = self._tile_names(agent, resource)
            if not tile_names:
                Routine.note(actions, f"no tile template for {resource} - skipping")
                continue
            if agent.find_and_tap(tile_names, timeout=4.0) is None:
                Routine.note(actions, f"no {resource} tile visible")
                continue

            if not agent.find_and_tap(
                ["btn_search_gather", "btn_gather", "btn_search"], timeout=5.0
            ):
                Routine.note(actions, f"{resource}: gather button not found")
                agent.close_dialog()
                continue

            hero = formations.get(resource)
            selected_formation = False
            if hero:
                preset = hero if hero.startswith("preset_") else f"preset_{hero}"
                if agent.vision.has(preset):
                    selected_formation = bool(
                        agent.find_and_tap([preset], timeout=2.0)
                    )
                    if selected_formation:
                        Routine.note(actions, f"{resource}: selected {hero} formation")
                else:
                    Routine.note(
                        actions,
                        f"{resource}: formation template {preset}.png missing",
                    )

            previous_idle = idle
            if not agent.find_and_tap(
                ["btn_march_send", "btn_send", "btn_march"], timeout=5.0
            ):
                Routine.note(actions, f"{resource}: march confirm button not found")
                agent.close_dialog()
                continue

            # Confirm the queue count changed when detection is available. This
            # prevents a full queue from being reported as a successful send.
            consumed = True
            if previous_idle is not None:
                new_status = self._wait_for_march_change(agent, previous_idle)
                if new_status is not None:
                    idle = new_status.idle
                    agent.state.set_march_status(
                        new_status.busy, new_status.total, new_status.source
                    )
                    if idle >= previous_idle:
                        consumed = False
                        Routine.note(actions, "march count did not change; stopping")

            if not consumed:
                break
            sent[resource] += 1
            formation_note = f" with {hero}" if selected_formation else ""
            Routine.note(
                actions,
                f"sent march #{sum(sent.values())} -> {resource}{formation_note}",
            )

        # 4. Return to the city.
        agent.find_and_tap(["btn_city", "btn_city_view"], timeout=4.0)

        total = sum(sent.values())
        summary = (
            f"sent {total}/{target} available marches: "
            + ", ".join(f"{resource}={count}" for resource, count in sent.items())
        )
        Routine.note(actions, summary)
        return RoutineResult(self.name, total > 0, summary, actions)

    @staticmethod
    def _march_status(agent):
        screen = agent.device.screenshot()
        configured_region = agent.config.vision.march_counter_region
        region = None
        if configured_region is not None:
            try:
                if len(configured_region) == 4:
                    region = tuple(int(value) for value in configured_region)
                else:
                    log.warning("vision.march_counter_region must have four values")
            except (TypeError, ValueError):
                log.warning("vision.march_counter_region contains invalid values")
        return agent.vision.march_status(screen, ocr_region=region)

    def _wait_for_march_change(self, agent, previous_idle: int):
        """Allow a few UI refreshes for the march counter to decrease."""
        latest = None
        for attempt in range(4):
            latest = self._march_status(agent)
            if latest is None or latest.idle < previous_idle:
                return latest
            if attempt < 3:
                agent.sleep(0.5)
        return latest

    def _next_resource(
        self, priority: List[str], sent: Dict[str, int], cap: int
    ) -> str:
        """Round-robin over the priority list."""
        for resource in priority:
            if sent[resource] < max(1, cap // len(priority)):
                return resource
        return priority[0]

    def _tile_names(self, agent, resource: str) -> List[str]:
        names = list(TILE_TEMPLATES[resource])
        return [name for name in names if agent.vision.has(name)]
