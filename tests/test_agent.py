"""Agent-level tests: primitives, dry-run safety, routine registry."""

import pytest

from kingshotbot.routines import ROUTINES


def test_find_and_tap(make_agent):
    agent, dev = make_agent()
    dev.force_screen("city")
    m = agent.find_and_tap(["btn_world_map"], timeout=2.0)
    assert m is not None
    assert dev.state.screen == "world_map"
    assert dev.state.taps and agent.actions >= 1


def test_find_and_tap_timeout_returns_none(make_agent):
    agent, dev = make_agent()
    dev.force_screen("city")
    assert agent.find_and_tap(["btn_upgrade"], timeout=0.3) is None
    assert dev.state.taps == []


def test_dry_run_never_taps(make_agent):
    agent, dev = make_agent(dry_run=True)
    dev.force_screen("city")
    m = agent.find_and_tap(["btn_world_map"], timeout=2.0)
    assert m is not None            # it still "found" the element
    assert dev.state.taps == []     # but never touched the device
    assert agent.actions >= 1       # and counted the (virtual) action
    assert dev.state.screen == "city"


def test_close_dialog_prefers_x_button(make_agent):
    agent, dev = make_agent()
    dev.force_screen("quests")
    agent.close_dialog()
    assert dev.state.screen == "city"


def test_back_recovery(make_agent):
    agent, dev = make_agent()
    dev.force_screen("tile_detail")
    assert agent.recover() is True
    assert dev.state.screen == "city"


def test_observe_lists_visible(templates_dir, make_agent):
    agent, dev = make_agent()
    dev.force_screen("world_map")
    visible = agent.what_is_visible()
    assert "tile_stone" in visible
    assert "btn_city" in visible


def test_run_unknown_routine_raises(make_agent):
    agent, _ = make_agent()
    with pytest.raises(KeyError):
        agent.run_routine("does-not-exist")


def test_all_routines_registered():
    assert set(ROUTINES) >= {"daily", "gather", "build", "gifts", "events"}


def test_routine_result_recorded_in_state(make_agent):
    agent, _ = make_agent()
    result = agent.run_routine("events")
    assert result.ok
    last = agent.state.last_run("events")
    assert last is not None and last["ok"] is True
