"""Events routine: reset countdown, arena reminder, bear hunt tracker.

Facts from community event calendars (see docs/RESEARCH.md):
* daily reset is 00:00 UTC; do your 10 arena attacks in the final
  minutes before reset so nobody can counter your rank
* Bear Hunt (Bear Trap) is an alliance event every ~2 days for 30
  minutes; trap times are set by R4/R5 and vary per alliance
* weekly spine: Alliance Championship, Armament Competition and Officer
  Project on 2-day anchors; 4-week rotation for Strongest Governor,
  Kingdom of Power (KvK), Alliance Brawl, Champagne Fair

The routine reports status and fires one-shot reminders (no duplicates,
thanks to state tracking).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from .base import Routine, RoutineResult, register

log = logging.getLogger("kingshotbot.routines.events")


def _parse_hhmm(value: Optional[str]) -> Optional[tuple[int, int]]:
    if not value:
        return None
    try:
        hh, mm = value.strip().split(":")
        return int(hh), int(mm)
    except (ValueError, AttributeError):
        log.warning("bear_hunt_utc %r is not HH:MM - ignoring", value)
        return None


@register
class EventsRoutine(Routine):
    name = "events"
    description = "Report event countdowns and fire reset/bear-hunt reminders"

    def run(self, agent) -> RoutineResult:
        actions: List[str] = []
        cfg = agent.config.events
        now = datetime.now(timezone.utc)

        # --- daily reset countdown + arena reminder -----------------------
        reset = now.replace(hour=cfg.daily_reset_utc_hour, minute=0, second=0,
                            microsecond=0)
        if reset <= now:
            reset += timedelta(days=1)
        minutes_left = (reset - now).total_seconds() / 60
        Routine.note(actions, f"daily reset in {minutes_left:.0f} min "
                              f"({reset:%H:%M UTC})")
        self._arena_reminder(agent, actions, cfg, minutes_left)

        # --- bear hunt tracker --------------------------------------------
        hhmm = _parse_hhmm(cfg.bear_hunt_utc)
        if hhmm:
            trap = now.replace(hour=hhmm[0], minute=hhmm[1], second=0,
                               microsecond=0)
            if trap <= now:
                trap += timedelta(days=cfg.bear_hunt_interval_days)
            bear_minutes = (trap - now).total_seconds() / 60
            Routine.note(
                actions,
                f"next bear hunt window in {bear_minutes / 60:.1f} h "
                f"({trap:%a %H:%M UTC}, every {cfg.bear_hunt_interval_days} days)",
            )
            self._bear_reminder(agent, actions, cfg, bear_minutes, trap)

        return RoutineResult(self.name, True, "; ".join(actions), actions)

    # ------------------------------------------------------------------ #
    def _arena_reminder(self, agent, actions: List[str], cfg, minutes_left: float
                        ) -> None:
        for lead in sorted(cfg.reminder_minutes_before, reverse=True):
            if minutes_left <= lead:
                key = f"arena_{datetime.now(timezone.utc):%Y%m%d}_{lead}m"
                if agent.state.reminder_due(key, min_gap_seconds=20 * 3600):
                    agent.state.mark_reminder(key)
                    agent.notifier.send(
                        f"⏰ Daily reset in ~{minutes_left:.0f} min — finish your "
                        f"{cfg.arena_attacks_per_day} arena attacks, claim daily "
                        f"quests and intel stamina!",
                        title="Kingshot: daily reset soon",
                    )
                    Routine.note(actions, f"arena reminder fired ({lead}m lead)")
                break

    def _bear_reminder(self, agent, actions: List[str], cfg,
                       bear_minutes: float, trap) -> None:
        if bear_minutes <= min(cfg.reminder_minutes_before, default=15):
            key = f"bear_{trap:%Y%m%d%H%M}"
            if agent.state.reminder_due(key, min_gap_seconds=12 * 3600):
                agent.state.mark_reminder(key)
                agent.notifier.send(
                    f"🐻 Bear Hunt starts in ~{bear_minutes:.0f} min! Recall "
                    f"gatherers, set your archer formation (≈1/10/89), donate "
                    f"hunting arrows and join the rallies.",
                    title="Kingshot: Bear Hunt soon",
                )
                Routine.note(actions, "bear hunt reminder fired")
