"""Vision layer tests against mock screenshots."""

import numpy as np

from kingshotbot.mock_device import MockDevice
from kingshotbot.vision import Vision


def test_finds_element_on_screen(templates_dir):
    vision = Vision(templates_dir=templates_dir, threshold=0.85)
    dev = MockDevice()
    dev.force_screen("city")
    m = vision.find(dev.screenshot(), "btn_world_map")
    assert m is not None
    assert m.confidence > 0.99
    # element rect for btn_world_map is (1080, 640, 170, 60)
    assert abs(m.x - (1080 + 85)) <= 3
    assert abs(m.y - (640 + 30)) <= 3


def test_missing_element_returns_none(templates_dir):
    vision = Vision(templates_dir=templates_dir, threshold=0.85)
    dev = MockDevice()
    dev.force_screen("city")
    assert vision.find(dev.screenshot(), "btn_upgrade") is None


def test_find_respects_threshold(templates_dir):
    vision = Vision(templates_dir=templates_dir, threshold=0.99)
    dev = MockDevice()
    dev.force_screen("city")
    # same rendering -> perfect match even at 0.99
    assert vision.find(dev.screenshot(), "btn_mail") is not None
    # impossible threshold
    assert vision.find(dev.screenshot(), "btn_mail", threshold=1.01) is None


def test_find_any_priority_order(templates_dir):
    vision = Vision(templates_dir=templates_dir, threshold=0.85)
    dev = MockDevice()
    dev.force_screen("world_map")
    m = vision.find_any(dev.screenshot(), ["tile_wood", "tile_stone"])
    assert m.name == "tile_wood"  # first in list wins


def test_region_search(templates_dir):
    vision = Vision(templates_dir=templates_dir, threshold=0.85)
    dev = MockDevice()
    dev.force_screen("city")
    screen = dev.screenshot()
    # btn_quest lives at (40, 200, 150, 60) - search only the left column
    m = vision.find(screen, "btn_quest", region=(0, 150, 300, 300))
    assert m is not None
    # search a region that cannot contain it
    assert vision.find(screen, "btn_quest", region=(800, 400, 400, 300)) is None


def test_wait_for_success(templates_dir):
    vision = Vision(templates_dir=templates_dir, threshold=0.85)
    dev = MockDevice()
    dev.force_screen("daily_login")
    m = vision.wait_for(dev, ["btn_daily_claim"], timeout=2.0,
                        sleep_fn=lambda s: None)
    assert m is not None and m.name == "btn_daily_claim"


def test_wait_for_timeout(templates_dir):
    vision = Vision(templates_dir=templates_dir, threshold=0.85)
    dev = MockDevice()
    dev.force_screen("city")
    m = vision.wait_for(dev, ["btn_daily_claim"], timeout=0.2, poll=0.05,
                        sleep_fn=lambda s: None)
    assert m is None


def test_has_and_template_names(templates_dir):
    vision = Vision(templates_dir=templates_dir)
    assert vision.has("btn_close")
    assert not vision.has("nonexistent")
    assert "btn_close" in vision.template_names


def test_empty_templates_dir_warning(tmp_path):
    Vision(templates_dir=tmp_path / "nope")  # must not raise
