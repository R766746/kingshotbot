"""Computer vision: template matching plus optional OCR.

Templates are small PNG crops of UI elements the user captures from
their own game (see ``templates/README.md``). Matching is plain OpenCV
``matchTemplate`` with a confidence threshold; the mock simulator's
templates match exactly, so the whole pipeline is testable offline.
"""

from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np

log = logging.getLogger("kingshotbot.vision")


@dataclass(frozen=True)
class Match:
    """A located UI element."""

    name: str
    confidence: float
    x: int  # center
    y: int
    w: int
    h: int

    @property
    def top_left(self) -> Tuple[int, int]:
        return (self.x - self.w // 2, self.y - self.h // 2)


class Vision:
    """Finds UI elements on screenshots using pre-captured templates."""

    def __init__(
        self,
        templates_dir: str | Path = "templates",
        threshold: float = 0.80,
        grayscale: bool = True,
    ) -> None:
        self.templates_dir = Path(templates_dir)
        self.threshold = threshold
        self.grayscale = grayscale
        self._templates: Dict[str, np.ndarray] = {}
        self._load_templates()
        self._tesseract = shutil.which("tesseract") is not None
        if not self._templates:
            log.warning(
                "no templates found in %s - UI routines will not match anything. "
                "Run `python main.py capture` and crop templates (see "
                "templates/README.md).", self.templates_dir
            )

    def _load_templates(self) -> None:
        if not self.templates_dir.exists():
            return
        for path in sorted(self.templates_dir.glob("*.png")):
            img = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if img is not None:
                self._templates[path.stem] = img
                log.debug("loaded template %s (%s)", path.stem, img.shape[:2][::-1])
        log.info("loaded %d templates from %s", len(self._templates), self.templates_dir)

    def reload(self) -> None:
        self._templates.clear()
        self._load_templates()

    @property
    def template_names(self) -> List[str]:
        return sorted(self._templates)

    def has(self, name: str) -> bool:
        return name in self._templates

    # ------------------------------------------------------------------ #
    def _prepare(self, img: np.ndarray) -> np.ndarray:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if self.grayscale else img

    def find(
        self,
        screen: np.ndarray,
        name: str,
        threshold: Optional[float] = None,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> Optional[Match]:
        """Find the best occurrence of template ``name`` on ``screen``."""
        template = self._templates.get(name)
        if template is None:
            return None
        threshold = self.threshold if threshold is None else threshold
        off_x = off_y = 0
        if region:
            rx, ry, rw, rh = region
            screen = screen[ry:ry + rh, rx:rx + rw]
            off_x, off_y = rx, ry
        if screen.size == 0:
            return None
        src = self._prepare(screen)
        tpl = self._prepare(template)
        if tpl.shape[0] > src.shape[0] or tpl.shape[1] > src.shape[1]:
            return None
        result = cv2.matchTemplate(src, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val < threshold:
            log.debug("template %r best=%.3f < %.3f", name, max_val, threshold)
            return None
        th, tw = tpl.shape[:2]
        return Match(
            name=name,
            confidence=round(float(max_val), 4),
            x=max_loc[0] + tw // 2 + off_x,
            y=max_loc[1] + th // 2 + off_y,
            w=tw,
            h=th,
        )

    def find_any(
        self, screen: np.ndarray, names: Iterable[str], **kwargs
    ) -> Optional[Match]:
        """Return the first match among ``names`` (in priority order)."""
        for name in names:
            m = self.find(screen, name, **kwargs)
            if m:
                return m
        return None

    def find_all(
        self,
        screen: np.ndarray,
        name: str,
        threshold: Optional[float] = None,
        max_results: int = 20,
    ) -> List[Match]:
        """Find every non-overlapping occurrence of ``name``."""
        template = self._templates.get(name)
        if template is None:
            return []
        threshold = self.threshold if threshold is None else threshold
        src = self._prepare(screen)
        tpl = self._prepare(template)
        if tpl.shape[0] > src.shape[0] or tpl.shape[1] > src.shape[1]:
            return []
        result = cv2.matchTemplate(src, tpl, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(result >= threshold)
        th, tw = tpl.shape[:2]
        # sort by confidence descending
        order = np.argsort(result[ys, xs])[::-1]
        taken: List[Match] = []
        for idx in order[: max_results * 4]:
            cx, cy = int(xs[idx]), int(ys[idx])
            conf = float(result[cy, cx])
            if any(
                abs(cx - m.top_left[0]) < tw // 2 and abs(cy - m.top_left[1]) < th // 2
                for m in taken
            ):
                continue
            taken.append(
                Match(name, round(conf, 4), cx + tw // 2, cy + th // 2, tw, th)
            )
            if len(taken) >= max_results:
                break
        return taken

    # ------------------------------------------------------------------ #
    def wait_for(
        self,
        device,
        names: Sequence[str],
        timeout: float = 8.0,
        poll: float = 0.5,
        sleep_fn=time.sleep,
    ) -> Optional[Match]:
        """Poll the device until one of ``names`` appears."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            screen = device.screenshot()
            m = self.find_any(screen, names)
            if m:
                return m
            sleep_fn(poll)
        log.debug("wait_for timeout after %.1fs: %s", timeout, list(names))
        return None

    # ------------------------------------------------------------------ #
    def ocr(self, screen: np.ndarray, region: Optional[Tuple[int, int, int, int]] = None) -> str:
        """Read text with pytesseract if available (optional feature)."""
        if not self._tesseract:
            log.debug("tesseract not installed - OCR skipped")
            return ""
        try:
            import pytesseract  # type: ignore[import-not-found]
        except ImportError:
            return ""
        if region:
            rx, ry, rw, rh = region
            screen = screen[ry:ry + rh, rx:rx + rw]
        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        return pytesseract.image_to_string(gray).strip()
