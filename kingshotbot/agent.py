"""The agent: ties device, vision, brain, state and notifications together.

Routines never touch the device directly - they ask the agent for
primitives (``find_and_tap``, ``wait_for``, ``back``...) which gives us
one place to implement dry-run safety, action logging, recovery and
(optional) LLM consultation for unknown screens.
"""

from __future__ import annotations

import logging
import time
from typing import Iterable, Optional, Sequence

from .brain import Brain, Observation, RuleBrain
from .config import BotConfig
from .device import KEY_BACK, Device, Sleeper
from .notify import Notifier
from .state import BotState
from .vision import Match, Vision

log = logging.getLogger("kingshotbot.agent")


class Agent:
    """One agent instance drives one device."""

    def __init__(
        self,
        device: Device,
        vision: Vision,
        state: BotState,
        config: BotConfig,
        notifier: Optional[Notifier] = None,
        brain: Optional[Brain] = None,
        sleeper: Optional[Sleeper] = None,
    ) -> None:
        self.device = device
        self.vision = vision
        self.state = state
        self.config = config
        self.notifier = notifier or Notifier()
        self.brain = brain or RuleBrain()
        self.sleep = sleeper or Sleeper()
        self.actions = 0

    # ------------------------------------------------------------------ #
    # observation
    # ------------------------------------------------------------------ #
    def observe(self, names: Optional[Iterable[str]] = None) -> Observation:
        """Take a screenshot and look for the given template names."""
        screen = self.device.screenshot()
        if names is None:
            names = self.vision.template_names
        matches = [m for n in names if (m := self.vision.find(screen, n))]
        obs = Observation(screen=screen, matches=matches)
        if matches:
            obs.screen_label = matches[0].name
        return obs

    def what_is_visible(self) -> list[str]:
        return [m.name for m in self.observe().matches]

    # ------------------------------------------------------------------ #
    # actions (all respect dry_run)
    # ------------------------------------------------------------------ #
    def _sleep_after_action(self) -> None:
        self.sleep(self.config.device.tap_delay)

    def tap(self, match: Match) -> bool:
        """Tap the center of a matched element (or a point)."""
        if self.config.dry_run:
            log.info("[dry-run] would tap %s at (%d,%d)", match.name, match.x, match.y)
            self.actions += 1
            return True
        log.debug("tap %s (%d,%d) conf=%.2f", match.name, match.x, match.y,
                  match.confidence)
        self.device.tap(match.x, match.y)
        self.actions += 1
        self._sleep_after_action()
        return True

    def tap_point(self, x: int, y: int) -> None:
        if self.config.dry_run:
            log.info("[dry-run] would tap point (%d,%d)", x, y)
            self.actions += 1
            return
        self.device.tap(x, y)
        self.actions += 1
        self._sleep_after_action()

    def back(self) -> None:
        if self.config.dry_run:
            log.info("[dry-run] would press BACK")
            return
        self.device.key(KEY_BACK)
        self.actions += 1
        self._sleep_after_action()

    # ------------------------------------------------------------------ #
    # higher-level flows
    # ------------------------------------------------------------------ #
    def find_and_tap(
        self,
        names: Sequence[str],
        timeout: float = 8.0,
        poll: float = 0.5,
        settle: float = 0.0,
    ) -> Optional[Match]:
        """Wait for any of ``names`` to appear, tap it, return the match."""
        if isinstance(names, str):  # convenience
            names = [names]
        match = self.vision.wait_for(
            self.device, names, timeout=timeout, poll=poll, sleep_fn=self.sleep
        )
        if match is None:
            return None
        self.tap(match)
        if settle:
            self.sleep(settle)
        return match

    def close_dialog(self, timeout: float = 3.0) -> bool:
        """Dismiss whatever dialog is open (X button or BACK)."""
        screen = self.device.screenshot()
        for name in ("btn_close", "close", "x_button"):
            m = self.vision.find(screen, name)
            if m:
                self.tap(m)
                return True
        self.back()
        return True

    def recover(self, attempts: int = 3) -> bool:
        """Try to get back to a main screen (city or world map) when lost."""
        main_markers = ("btn_world_map", "btn_city", "btn_build_menu")
        for _ in range(attempts):
            visible = self.what_is_visible()
            if any(v in main_markers or v.startswith("tile_") for v in visible):
                log.info("recovery: back on a main screen (%s)", visible[:3])
                return True
            log.info("recovery: unknown/dialog screen (%s), pressing BACK",
                     visible[:3])
            self.back()
        return False

    # ------------------------------------------------------------------ #
    # LLM assistance (optional)
    # ------------------------------------------------------------------ #
    def ask_brain(self, goal: str) -> Optional[Match]:
        """Let the configured brain pick a visible element to tap."""
        if not self.config.llm.enabled:
            return None
        obs = self.observe()
        decision = self.brain.decide(obs, context={"goal": goal})
        if decision.action == "tap" and decision.match is not None:
            log.info("brain(%s) chose %s", self.brain.name, decision.match.name)
            return decision.match  # type: ignore[return-value]
        if decision.action == "abort":
            log.warning("brain aborted: %s", decision.reason)
        return None

    # ------------------------------------------------------------------ #
    # routine execution
    # ------------------------------------------------------------------ #
    def run_routine(self, name: str):
        """Execute a routine by name; records the run in state."""
        from .routines import ROUTINES, RoutineResult

        routine_cls = ROUTINES.get(name)
        if routine_cls is None:
            raise KeyError(
                f"unknown routine {name!r}; available: {sorted(ROUTINES)}"
            )
        started = time.time()
        self.state.start_run(name)
        routine = routine_cls()
        log.info("routine '%s' starting (device=%s, dry_run=%s)",
                 name, self.device.name, self.config.dry_run)
        try:
            result: RoutineResult = routine.run(self)
        except Exception as exc:  # noqa: BLE001 - routines must not kill the loop
            log.exception("routine '%s' crashed", name)
            result = RoutineResult(routine=name, ok=False, summary=f"error: {exc}")
        result.duration = round(time.time() - started, 2)
        self.state.finish_run(name, result.ok, result.summary)
        self.state.save()
        log.info("routine '%s' finished ok=%s in %.1fs: %s",
                 name, result.ok, result.duration, result.summary)
        return result
