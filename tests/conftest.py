"""Shared fixtures: an agent wired to the mock simulator."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kingshotbot.agent import Agent  # noqa: E402
from kingshotbot.config import BotConfig  # noqa: E402
from kingshotbot.device import Sleeper  # noqa: E402
from kingshotbot.mock_device import SCREENS, MockDevice, render_template  # noqa: E402
from kingshotbot.notify import Notifier  # noqa: E402
from kingshotbot.state import BotState  # noqa: E402
from kingshotbot.vision import Vision  # noqa: E402


class RecordingNotifier(Notifier):
    """Notifier that records messages instead of sending them."""

    def __init__(self):
        super().__init__(webhook_url=None, console=False)
        self.sent = []

    def send(self, message, **kwargs):
        self.sent.append(message)


@pytest.fixture()
def templates_dir(tmp_path):
    """A templates folder containing an image for every mock element."""
    tdir = tmp_path / "templates"
    tdir.mkdir()
    for screen, elements in SCREENS.items():
        for elem in elements:
            img = render_template(screen, elem.id)
            out = tdir / f"{elem.id}.png"
            out.write_bytes(_png_bytes(img))
    return tdir


def _png_bytes(img):
    import cv2

    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


@pytest.fixture()
def make_agent(tmp_path, templates_dir):
    """Factory building an Agent around a fresh MockDevice."""

    def _make(marches: int = 5, dry_run: bool = False, device=None,
              notifier=None) -> tuple[Agent, MockDevice]:
        cfg = BotConfig()
        cfg.device.mode = "mock"
        cfg.device.tap_delay = 0.0
        cfg.dry_run = dry_run
        cfg.state_file = str(tmp_path / "state.json")
        dev = device or MockDevice(marches_available=marches)
        vision = Vision(templates_dir=templates_dir, threshold=0.85)
        state = BotState(cfg.state_file)
        agent = Agent(
            device=dev, vision=vision, state=state, config=cfg,
            notifier=notifier or RecordingNotifier(),
            sleeper=Sleeper(fn=lambda _s: None),
        )
        return agent, dev

    return _make
