"""Multi-account CLI integration tests."""

import json

import pytest

from kingshotbot.cli import main


@pytest.fixture(autouse=True)
def disable_global_logging_setup(monkeypatch):
    """Keep CLI tests from retaining pytest's temporary captured streams."""
    monkeypatch.setattr("kingshotbot.cli.setup_logging", lambda **_kwargs: None)


def test_run_all_accounts_uses_separate_state_files(tmp_path, capsys):
    main_state = tmp_path / "main.json"
    farm_state = tmp_path / "farm.json"
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "device:\n  mode: mock\n  tap_delay: 0\n"
        "accounts:\n"
        "  - name: main\n"
        f"    state_file: {main_state}\n"
        "  - name: farm\n"
        f"    state_file: {farm_state}\n"
    )

    result = main([
        "--config", str(config_file), "run", "--all-accounts", "-r", "daily"
    ])

    assert result == 0
    output = capsys.readouterr().out
    assert "account: main" in output
    assert "account: farm" in output
    assert main_state.exists()
    assert farm_state.exists()
    assert json.loads(main_state.read_text())["routine_runs"]["daily"][-1]["ok"]
    assert json.loads(farm_state.read_text())["routine_runs"]["daily"][-1]["ok"]


def test_run_can_target_one_account(tmp_path, capsys):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "device:\n  mode: mock\n  tap_delay: 0\n"
        f"state_file: {tmp_path / 'state.json'}\n"
        "accounts:\n  - {name: main}\n  - {name: farm}\n"
    )

    result = main([
        "--config", str(config_file), "run", "--account", "farm", "-r", "daily"
    ])

    assert result == 0
    output = capsys.readouterr().out
    assert "account: farm" in output
    assert "account: main" not in output
    assert (tmp_path / "state_farm.json").exists()
    assert not (tmp_path / "state_main.json").exists()


def test_unknown_account_returns_configuration_error(tmp_path, capsys):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("device:\n  mode: mock\naccounts:\n  - {name: main}\n")

    result = main([
        "--config", str(config_file), "run", "--account", "missing", "-r", "daily"
    ])

    assert result == 2
    assert "unknown account" in capsys.readouterr().err


def test_multi_account_json_output_is_valid(tmp_path, capsys):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "device:\n  mode: mock\n  tap_delay: 0\n"
        f"state_file: {tmp_path / 'state.json'}\n"
        "accounts:\n  - {name: main}\n  - {name: farm}\n"
    )

    result = main([
        "--config", str(config_file), "run", "-r", "events", "--json"
    ])

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert [item["account"] for item in payload] == ["main", "farm"]
    assert all(item["routine"] == "events" for item in payload)
