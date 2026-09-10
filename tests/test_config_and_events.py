"""Config loading + events routine tests."""

from kingshotbot.config import BotConfig, load_config
from kingshotbot.routines.events import EventsRoutine


# --- config ---------------------------------------------------------------- #

def test_defaults():
    cfg = BotConfig()
    assert cfg.device.mode == "adb"
    assert cfg.gather.march_count == 4
    assert "stone" in cfg.gather.resource_priority
    assert cfg.events.daily_reset_utc_hour == 0
    assert cfg.gifts.redeem_url.startswith("https://")


def test_load_missing_file_uses_defaults(tmp_path):
    cfg = load_config(tmp_path / "nope.yaml")
    assert cfg.device.mode == "adb"


def test_yaml_overrides(tmp_path):
    f = tmp_path / "config.yaml"
    f.write_text(
        "device:\n  mode: mock\n  serial: emulator-5554\n"
        "gather:\n  march_count: 2\n  resource_priority: [wood]\n"
        "routines: [daily]\n"
    )
    cfg = load_config(f)
    assert cfg.device.mode == "mock"
    assert cfg.device.serial == "emulator-5554"
    assert cfg.gather.march_count == 2
    assert cfg.gather.resource_priority == ["wood"]
    assert cfg.routines == ["daily"]


def test_env_overrides(tmp_path, monkeypatch):
    f = tmp_path / "config.yaml"
    f.write_text("device:\n  mode: adb\n")
    monkeypatch.setenv("KSB_DEVICE_MODE", "mock")
    monkeypatch.setenv("KSB_DRY_RUN", "1")
    cfg = load_config(f)
    assert cfg.device.mode == "mock"
    assert cfg.dry_run is True


def test_unknown_keys_are_tolerated(tmp_path):
    f = tmp_path / "config.yaml"
    f.write_text("bogus: 1\ndevice:\n  nonsense: yes\n")
    load_config(f)  # must not raise


# --- events routine --------------------------------------------------------- #

def test_events_reports_reset_countdown(make_agent):
    agent, _ = make_agent()
    result = agent.run_routine("events")
    assert result.ok
    assert "daily reset in" in result.summary


def test_events_arena_reminder_fires_once(make_agent):
    agent, _ = make_agent()
    agent.config.events.reminder_minutes_before = [100000]  # always within window
    notifier = agent.notifier
    r1 = agent.run_routine("events")
    assert any("arena" in m.lower() for m in notifier.sent), r1.summary
    n_after_first = len(notifier.sent)
    agent.run_routine("events")  # second run must not re-fire
    assert len(notifier.sent) == n_after_first


def test_events_bear_hunt_reminder(make_agent):
    agent, _ = make_agent()
    agent.config.events.bear_hunt_utc = "23:59"  # far in the future
    result = agent.run_routine("events")
    assert "bear hunt" in result.summary.lower()


def test_events_bear_hunt_invalid_time_ignored(make_agent):
    agent, _ = make_agent()
    agent.config.events.bear_hunt_utc = "not-a-time"
    result = agent.run_routine("events")
    assert result.ok
