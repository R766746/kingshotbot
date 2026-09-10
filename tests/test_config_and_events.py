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


def test_account_config_inherits_and_overrides_sections(tmp_path):
    from kingshotbot.config import for_account

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "device:\n  mode: adb\n  tap_delay: 0.2\n"
        "state_file: data/state.json\n"
        "accounts:\n"
        "  - name: main\n"
        "    device: {serial: '127.0.0.1:5555'}\n"
        "  - name: farm-one\n"
        "    device: {serial: '127.0.0.1:5565'}\n"
        "    state_file: data/farm.json\n"
        "    gather:\n"
        "      march_count: 2\n"
        "      resource_priority: [bread, wood]\n"
        "      formations: {bread: custom_baker}\n"
    )
    cfg = load_config(config_file)

    main = for_account(cfg, "main")
    farm = for_account(cfg, "farm-one")

    assert [account.name for account in cfg.accounts] == ["main", "farm-one"]
    assert main.device.serial == "127.0.0.1:5555"
    assert main.device.tap_delay == 0.2
    assert main.state_file == "data/state_main.json"
    assert farm.device.serial == "127.0.0.1:5565"
    assert farm.gather.march_count == 2
    assert farm.gather.resource_priority == ["bread", "wood"]
    assert farm.gather.formations["bread"] == "custom_baker"
    assert farm.gather.formations["stone"] == "edwin"
    assert farm.state_file == "data/farm.json"
    # Merging an account must not mutate the base config.
    assert cfg.device.serial is None
    assert cfg.gather.march_count == 4


def test_account_names_must_be_unique(tmp_path):
    import pytest

    config_file = tmp_path / "config.yaml"
    config_file.write_text("accounts:\n  - {name: farm}\n  - {name: farm}\n")
    with pytest.raises(ValueError, match="duplicate account"):
        load_config(config_file)


def test_unknown_account_is_rejected():
    import pytest
    from kingshotbot.config import AccountConfig, for_account

    cfg = BotConfig(accounts=[AccountConfig(name="main")])
    with pytest.raises(KeyError, match="unknown account"):
        for_account(cfg, "farm")


def test_state_file_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("KSB_STATE_FILE", str(tmp_path / "custom.json"))
    cfg = load_config(None)
    assert cfg.state_file == str(tmp_path / "custom.json")
