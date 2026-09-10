"""Gift-code routine: discover new codes online and announce them.

Kingshot gift codes are released by Century Games on socials and the
official redemption center (https://ks-giftcode.centurygame.com/). This
routine periodically scrapes public code aggregators, deduplicates
against the bot's state, and announces anything new through the
configured notification channels.

Codes are redeemed manually in-game or on the official site (Player ID +
Kingdom + code) - the bot announces them so nobody in your alliance
misses one.
"""

from __future__ import annotations

import logging
from typing import List

from ..codes import CodeManager
from .base import Routine, RoutineResult, register

log = logging.getLogger("kingshotbot.routines.gifts")


@register
class GiftsRoutine(Routine):
    name = "gifts"
    description = "Check online sources for new Kingshot gift codes and announce them"

    def run(self, agent) -> RoutineResult:
        actions: List[str] = []
        cfg = agent.config.gifts
        if not cfg.enabled:
            return RoutineResult(self.name, True, "gift checking disabled")

        manager = CodeManager(
            sources=cfg.sources,
            manual_codes_file=cfg.manual_codes_file,
            timeout=15.0,
        )
        findings = manager.fetch_all()
        Routine.note(actions, f"checked {len(manager.errors) + len(manager.per_source)} "
                              f"source(s), {len(findings)} active code(s) found")
        for url, error in manager.errors:
            Routine.note(actions, f"source error: {url}: {error[:80]}")

        new_codes: List[str] = []
        for code in findings:
            is_new = agent.state.add_code(code.code, code.source)
            if is_new:
                new_codes.append(code.code)

        if new_codes:
            message = (
                "**New Kingshot gift codes found:** "
                + ", ".join(f"`{c}`" for c in sorted(new_codes))
                + f"\nRedeem at {cfg.redeem_url} (Player ID + Kingdom + code)."
            )
            agent.notifier.send(message, title="Kingshot gift codes")
            Routine.note(actions, f"NEW codes announced: {', '.join(sorted(new_codes))}")
        else:
            Routine.note(actions, "no new codes (all already known)")

        agent.state.save()
        summary = "; ".join(actions)
        return RoutineResult(self.name, True, summary, actions)
