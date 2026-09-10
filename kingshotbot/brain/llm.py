"""Optional LLM brain for unfamiliar screens.

Points at any OpenAI-compatible chat-completions endpoint. It is only
consulted when the rule brain cannot classify a screen, and its answer
is constrained to a small action vocabulary - it can never invent free
-form actions. Disabled unless explicitly configured.
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

import requests

from .base import Brain, Decision, Observation

log = logging.getLogger("kingshotbot.brain.llm")

_SYSTEM_PROMPT = (
    "You are the vision brain of a game automation agent for the mobile game "
    "Kingshot. You receive a list of UI elements detected on the current "
    "screen. Reply with ONLY a JSON object: "
    '{"action": "tap"|"back"|"wait"|"abort", "element": "<element name or null>", '
    '"reason": "<short>"} '
    "Choose 'abort' if the screen shows a purchase prompt, captcha, or account "
    "issue. Otherwise pick the element that best advances the current goal."
)


class LLMBrain(Brain):
    """Consults an OpenAI-compatible API to pick the next tap."""

    name = "llm"

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1",
                 model: str = "gpt-4o-mini", temperature: float = 0.1,
                 max_tokens: int = 400, timeout: float = 20.0) -> None:
        if not api_key:
            raise ValueError("LLM brain requires an API key")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    def _chat(self, user_text: str) -> Optional[str]:
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_text},
                    ],
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, ValueError) as exc:
            log.warning("LLM call failed: %s", exc)
            return None

    def decide(self, observation: Observation, context: Optional[dict] = None) -> Decision:
        context = context or {}
        goal = context.get("goal", "unknown")
        elements: List[str] = [m.name for m in observation.matches]
        user_text = json.dumps(
            {"goal": goal, "elements": elements, "screen_hint": observation.screen_label}
        )
        raw = self._chat(user_text)
        if not raw:
            return Decision(action="wait", reason="LLM unavailable")
        try:
            # tolerate markdown fences
            text = raw.strip().removeprefix("```json").removeprefix("```")
            text = text.removesuffix("```").strip()
            data = json.loads(text)
        except json.JSONDecodeError:
            log.warning("LLM returned unparsable output: %r", raw[:200])
            return Decision(action="wait", reason="LLM output unparsable")
        action = data.get("action", "wait")
        if action not in {"tap", "back", "wait", "abort"}:
            action = "wait"
        decision = Decision(action=action, reason=f"llm: {data.get('reason', '')}")
        if action == "tap":
            wanted = data.get("element")
            for m in observation.matches:
                if m.name == wanted:
                    decision.match = m
                    return decision
            decision.action = "wait"
            decision.reason += " (element not visible)"
        return decision
