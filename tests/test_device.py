"""MockDevice behaviour tests."""

from kingshotbot.device import KEY_BACK
from kingshotbot.mock_device import SCREENS, MockDevice, render_template


def test_screenshot_shape():
    dev = MockDevice()
    img = dev.screenshot()
    assert img.shape[:2] == (720, 1280)  # BGR image


def test_initial_screen_is_daily_login():
    dev = MockDevice()
    assert dev.state.screen == "daily_login"


def test_tap_navigates():
    dev = MockDevice()
    dev.force_screen("city")
    btn = next(e for e in SCREENS["city"] if e.id == "btn_world_map")
    x, y, w, h = btn.rect
    dev.tap(x + w // 2, y + h // 2)
    assert dev.state.screen == "world_map"


def test_stray_tap_counted():
    dev = MockDevice()
    dev.force_screen("city")
    dev.tap(5, 5)  # corner - no element there
    assert dev.state.stray_taps == 1


def test_once_element_disappears_after_tap():
    dev = MockDevice()
    dev.force_screen("city")
    elem = next(e for e in SCREENS["city"] if e.id == "bubble_production")
    x, y, w, h = elem.rect
    assert dev._element_at(x + 5, y + 5) is not None
    dev.tap(x + w // 2, y + h // 2)
    assert dev.state.flags["production_collected"]
    assert dev._element_at(x + 5, y + 5) is None  # gone


def test_send_march_decrements_and_returns_to_map():
    dev = MockDevice(marches_available=2)
    dev.force_screen("march_confirm")
    elem = next(e for e in SCREENS["march_confirm"] if e.id == "btn_march_send")
    x, y, w, h = elem.rect
    dev.tap(x + w // 2, y + h // 2)
    assert dev.state.marches_available == 1
    assert dev.state.screen == "world_map"
    assert len(dev.state.marches_sent) == 1


def test_send_march_at_zero_does_not_go_negative():
    dev = MockDevice(marches_available=0)
    dev.force_screen("march_confirm")
    elem = next(e for e in SCREENS["march_confirm"] if e.id == "btn_march_send")
    x, y, w, h = elem.rect
    dev.tap(x + w // 2, y + h // 2)
    assert dev.state.marches_available == 0
    assert dev.state.marches_sent == []


def test_back_key_returns_to_city():
    dev = MockDevice()
    dev.force_screen("quests")
    dev.key(KEY_BACK)
    assert dev.state.screen == "city"
    dev.key(KEY_BACK)  # already city - stays
    assert dev.state.screen == "city"


def test_render_template_matches_screen_exactly():
    import cv2
    import numpy as np

    dev = MockDevice()
    dev.force_screen("city")
    screen = dev.screenshot()
    tpl = render_template("city", "btn_world_map")
    result = cv2.matchTemplate(
        cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY),
        cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY),
        cv2.TM_CCOEFF_NORMED,
    )
    assert result.max() > 0.99


def test_is_alive_and_name():
    dev = MockDevice()
    assert dev.is_alive()
    assert dev.name == "mock:simulator"
