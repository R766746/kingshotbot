"""Notifications: console log + optional Discord webhook."""

from __future__ import annotations

import logging
from typing import Optional

import requests

log = logging.getLogger("kingshotbot.notify")


class Notifier:
    """Sends messages to the console and (optionally) a Discord webhook."""

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        console: bool = True,
        timeout: float = 10.0,
        title_prefix: str = "",
    ) -> None:
        self.webhook_url = webhook_url
        self.console = console
        self.timeout = timeout
        self.title_prefix = title_prefix.strip()

    def send(self, message: str, *, embed: bool = True, title: str = "KingshotBot") -> None:
        """Log locally and post to Discord if configured.

        Never raises on network problems - notifications are best-effort.
        """
        if self.console:
            log.info("notify: %s", message)
        if not self.webhook_url:
            return
        if self.title_prefix:
            title = f"{self.title_prefix} · {title}"
        payload: dict = {"content": message} if not embed else {
            "embeds": [
                {
                    "title": title,
                    "description": message[:4000],
                    "color": 0xF5A623,
                }
            ]
        }
        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=self.timeout)
            if resp.status_code >= 300:
                log.warning("discord webhook returned %s", resp.status_code)
        except requests.RequestException as exc:
            log.warning("discord webhook failed: %s", exc)
