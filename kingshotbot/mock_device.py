"""A tiny in-process Kingshot simulator for dry-runs, demos and tests.

The :class:`MockDevice` renders simplified Kingshot screens with PIL and
behaves like a device: screenshots in, taps out. It implements a small
state machine that mirrors the UI flows the bot's routines drive on the
real game (city view, daily login, quests, mail, alliance help, world
map gathering, build/research menus).

Templates for the vision layer can be generated from the same drawing
code with :func:`render_template`, so the whole agent pipeline - vision,
brain, routines - can be exercised without an emulator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SCREEN_W, SCREEN_H = 1280, 720

# --------------------------------------------------------------------- #
# screen definitions
# --------------------------------------------------------------------- #


@dataclass(frozen=True)
class Element:
    """A tappable UI element on a mock screen."""

    id: str
    rect: Tuple[int, int, int, int]  # x, y, w, h
    action: str = "nav"  # nav | once | send_march | select
    target: Optional[str] = None  # screen to open (nav)
    effect: Optional[str] = None  # flag to set (once)
    resource: Optional[str] = None  # resource type (send_march)
    hero: Optional[str] = None  # formation hero (select)
    plain: bool = False  # draw a compact indicator without text


def _e(elem_id, x, y, w, h, **kw):
    return Element(id=elem_id, rect=(x, y, w, h), **kw)


# "once" elements disappear once their effect flag is set.
SCREENS: Dict[str, List[Element]] = {
    "daily_login": [
        _e("btn_daily_claim", 540, 480, 200, 80, action="once",
           effect="daily_claimed", target="city"),
    ],
    "city": [
        _e("btn_world_map", 1080, 640, 170, 60, target="world_map"),
        _e("btn_build_menu", 1080, 550, 170, 60, target="build_menu"),
        _e("btn_quest", 40, 200, 150, 60, target="quests"),
        _e("btn_mail", 40, 280, 150, 60, target="mail"),
        _e("btn_alliance", 40, 360, 150, 60, target="alliance"),
        _e("bubble_production", 600, 300, 130, 60, action="once",
           effect="production_collected"),
    ],
    "world_map": [
        _e("tile_stone", 300, 190, 150, 90, target="tile_detail", resource="stone"),
        _e("tile_iron", 510, 340, 150, 90, target="tile_detail", resource="iron"),
        _e("tile_bread", 190, 440, 150, 90, target="tile_detail", resource="bread"),
        _e("tile_wood", 720, 240, 150, 90, target="tile_detail", resource="wood"),
        _e("btn_city", 1080, 640, 170, 60, target="city"),
    ],
    "tile_detail": [
        _e("btn_search_gather", 880, 600, 210, 80, target="march_confirm"),
        _e("btn_close", 1150, 30, 90, 70, target="world_map"),
    ],
    "march_confirm": [
        _e("preset_olive", 100, 250, 220, 70, action="select", hero="olive"),
        _e("preset_forrest", 370, 250, 220, 70, action="select", hero="forrest"),
        _e("preset_edwin", 640, 250, 220, 70, action="select", hero="edwin"),
        _e("preset_seth", 910, 250, 220, 70, action="select", hero="seth"),
        _e("btn_march_send", 880, 600, 210, 80, action="send_march",
           target="world_map"),
        _e("btn_close", 1150, 30, 90, 70, target="world_map"),
    ],
    "quests": [
        _e("btn_claim", 560, 400, 220, 80, action="once", effect="quests_claimed"),
        _e("btn_close", 1150, 30, 90, 70, target="city"),
    ],
    "mail": [
        _e("btn_claim_all", 560, 400, 220, 80, action="once", effect="mail_claimed"),
        _e("btn_close", 1150, 30, 90, 70, target="city"),
    ],
    "alliance": [
        _e("btn_help_all", 560, 400, 220, 80, action="once", effect="help_given"),
        _e("btn_close", 1150, 30, 90, 70, target="city"),
    ],
    "build_menu": [
        _e("btn_construction", 280, 300, 250, 90, target="construction"),
        _e("btn_research", 600, 300, 250, 90, target="research"),
        _e("btn_close", 1150, 30, 90, 70, target="city"),
    ],
    "construction": [
        _e("btn_upgrade", 560, 420, 220, 80, action="once",
           effect="construction_started"),
        _e("btn_close", 1150, 30, 90, 70, target="build_menu"),
    ],
    "research": [
        _e("btn_research_start", 560, 420, 230, 80, action="once",
           effect="research_started"),
        _e("btn_close", 1150, 30, 90, 70, target="build_menu"),
    ],
    # Pseudo-screen used only to generate templates for the dynamic march
    # status indicators rendered on the world map.
    "march_slots": [
        _e("march_busy", 0, 0, 36, 36, plain=True),
        _e("march_idle", 0, 0, 36, 36, plain=True),
    ],
}

# Palette (BGR-independent RGB tuples) by element id prefix.
_CATEGORY_COLORS = {
    "btn_": (46, 116, 229),      # blue buttons
    "tile_": (76, 175, 80),      # green resource tiles
    "bubble_": (255, 193, 7),    # amber collect bubbles
    "preset_": (0, 121, 107),    # teal formation presets
}
_EXACT_COLORS = {
    "march_idle": (76, 175, 80),
    "march_busy": (96, 100, 108),
}

DEFAULT_FLAGS = {
    "production_collected": False,
    "daily_claimed": False,
    "quests_claimed": False,
    "mail_claimed": False,
    "help_given": False,
    "construction_started": False,
    "research_started": False,
}


# --------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------- #

def _font(size: int = 18) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size
        )
    except OSError:  # fallback on any platform
        return ImageFont.load_default()


def _element_color(elem: Element) -> Tuple[int, int, int]:
    if elem.id in _EXACT_COLORS:
        return _EXACT_COLORS[elem.id]
    for prefix, color in _CATEGORY_COLORS.items():
        if elem.id.startswith(prefix):
            return color
    return (156, 39, 176)


def _draw_element(
    draw: ImageDraw.ImageDraw, rect: Tuple[int, int, int, int], elem: Element
) -> None:
    """Draw one element; used for both screens and template crops."""
    x, y, w, h = rect
    color = _element_color(elem)
    draw.rounded_rectangle((x, y, x + w, y + h), radius=12, fill=color,
                           outline=(255, 255, 255), width=3)
    if elem.plain:
        # Distinct shapes keep idle/busy templates distinguishable even when
        # the vision engine is configured for grayscale matching.
        if elem.id == "march_busy":
            draw.line((x + 10, y + 10, x + w - 10, y + h - 10),
                      fill=(255, 255, 255), width=4)
            draw.line((x + w - 10, y + 10, x + 10, y + h - 10),
                      fill=(255, 255, 255), width=4)
        else:
            draw.ellipse((x + 12, y + 12, x + w - 12, y + h - 12),
                         fill=(255, 255, 255))
        return
    font = _font(max(14, min(20, w // max(6, len(elem.id)))))
    text = elem.id
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x + (w - tw) / 2 - bbox[0], y + (h - th) / 2 - bbox[1]),
              text, fill=(255, 255, 255), font=font)


def render_template(screen: str, element_id: str) -> np.ndarray:
    """Render a standalone element image to use as a vision template.

    The element is drawn exactly like it appears inside the screen, so
    template matching against mock screenshots is exact.
    """
    for elem in SCREENS[screen]:
        if elem.id == element_id:
            x, y, w, h = elem.rect
            img = Image.new("RGB", (w, h), (30, 30, 40))
            draw = ImageDraw.Draw(img)
            _draw_element(draw, (0, 0, w, h), elem)
            return np.asarray(img)[:, :, ::-1].copy()  # RGB -> BGR
    raise KeyError(f"element {element_id!r} not on screen {screen!r}")


# --------------------------------------------------------------------- #
# the mock device
# --------------------------------------------------------------------- #

@dataclass
class MockDeviceState:
    """Bookkeeping of everything the simulator has done."""

    screen: str = "daily_login"
    flags: Dict[str, bool] = field(default_factory=lambda: dict(DEFAULT_FLAGS))
    marches_available: int = 5
    marches_total: int = 5
    marches_sent: List[Dict[str, object]] = field(default_factory=list)
    pending_resource: Optional[str] = None  # tile selected before the march
    pending_hero: Optional[str] = None  # formation selected before the march
    taps: List[Tuple[int, int]] = field(default_factory=list)
    swipes: List[Tuple[int, int, int, int]] = field(default_factory=list)
    keys: List[int] = field(default_factory=list)
    screenshots: int = 0
    stray_taps: int = 0


class MockDevice:
    """Simulates the game UI well enough to run and test every routine."""

    def __init__(self, marches_available: int = 5, marches_total: int = 5) -> None:
        self.name = "mock:simulator"
        if marches_total < 1:
            raise ValueError("marches_total must be at least 1")
        if not 0 <= marches_available <= marches_total:
            raise ValueError("marches_available must be between 0 and marches_total")
        self.state = MockDeviceState(
            marches_available=marches_available,
            marches_total=marches_total,
        )

    # -- internal helpers -------------------------------------------------
    def _visible_elements(self) -> List[Element]:
        return [
            e for e in SCREENS[self.state.screen]
            if not (e.action == "once" and self.state.flags.get(e.effect, False))
        ]

    def _element_at(self, x: int, y: int) -> Optional[Element]:
        for e in self._visible_elements():
            ex, ey, ew, eh = e.rect
            if ex <= x < ex + ew and ey <= y < ey + eh:
                return e
        return None

    def force_screen(self, name: str) -> None:
        """Jump to a screen (test helper)."""
        if name not in SCREENS:
            raise KeyError(f"unknown screen {name!r}")
        self.state.screen = name

    # -- Device protocol --------------------------------------------------
    def screenshot(self) -> np.ndarray:
        self.state.screenshots += 1
        img = Image.new("RGB", (SCREEN_W, SCREEN_H), (24, 26, 34))
        draw = ImageDraw.Draw(img)
        draw.text((16, 10), f"SCREEN: {self.state.screen}", fill=(220, 220, 120),
                  font=_font(22))
        busy = self.state.marches_total - self.state.marches_available
        draw.text(
            (SCREEN_W - 260, 10),
            f"marches: {busy}/{self.state.marches_total}",
            fill=(150, 220, 150),
            font=_font(22),
        )
        for e in self._visible_elements():
            _draw_element(draw, e.rect, e)
        if self.state.screen == "world_map":
            slots = {e.id: e for e in SCREENS["march_slots"]}
            for index in range(self.state.marches_total):
                status = "march_busy" if index < busy else "march_idle"
                _draw_element(draw, (20 + index * 40, 50, 36, 36), slots[status])
        return np.asarray(img)[:, :, ::-1].copy()  # RGB -> BGR

    def tap(self, x: int, y: int) -> None:
        x, y = int(x), int(y)
        self.state.taps.append((x, y))
        elem = self._element_at(x, y)
        if elem is None:
            self.state.stray_taps += 1
            return
        if elem.action == "once":
            assert elem.effect is not None
            self.state.flags[elem.effect] = True
            if elem.target:
                self.state.screen = elem.target
        elif elem.action == "send_march":
            if self.state.marches_available > 0:
                self.state.marches_available -= 1
                self.state.marches_sent.append(
                    {
                        "resource": self.state.pending_resource,
                        "hero": self.state.pending_hero,
                        "from": self.state.screen,
                    }
                )
            self.state.pending_resource = None
            self.state.pending_hero = None
            if elem.target:
                self.state.screen = elem.target
        elif elem.action == "select":
            self.state.pending_hero = elem.hero
        else:  # nav
            if elem.resource:  # tapping a resource tile selects it
                self.state.pending_resource = elem.resource
            if elem.target:
                self.state.screen = elem.target

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self.state.swipes.append((x1, y1, x2, y2))

    def key(self, keycode: int) -> None:
        self.state.keys.append(keycode)
        # BACK closes any dialog back to the city, like the real game.
        if keycode == 4 and self.state.screen != "city":
            self.state.screen = "city"

    def is_alive(self) -> bool:
        return True
