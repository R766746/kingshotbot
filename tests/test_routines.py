"""End-to-end routine tests on the mock simulator."""

from kingshotbot.mock_device import MockDevice
from conftest import RecordingNotifier


def test_daily_routine_claims_everything(make_agent):
    agent, dev = make_agent()
    result = agent.run_routine("daily")
    assert result.ok, result.summary
    flags = dev.state.flags
    assert flags["daily_claimed"]
    assert flags["quests_claimed"]
    assert flags["mail_claimed"]
    assert flags["help_given"]
    assert flags["production_collected"]
    # ended back on the city screen
    assert dev.state.screen == "city"
    assert dev.state.stray_taps == 0


def test_daily_routine_is_idempotent(make_agent):
    agent, dev = make_agent()
    first = agent.run_routine("daily")
    second = agent.run_routine("daily")
    assert first.ok and second.ok
    # second run: bubbles/claims already gone, routine still succeeds


def test_gather_routine_sends_marches(make_agent):
    agent, dev = make_agent(marches=5)
    result = agent.run_routine("gather")
    assert result.ok, result.summary
    sent = dev.state.marches_sent
    assert len(sent) == 4                     # march_count default = 4
    assert dev.state.marches_available == 1   # one march kept free
    resources = {m["resource"] for m in sent}
    assert resources == {"stone", "iron", "bread", "wood"}
    assert dev.state.screen == "city"         # returned home


def test_gather_routine_keeps_last_idle_march_free(make_agent):
    agent, dev = make_agent(marches=1)
    result = agent.run_routine("gather")
    assert len(dev.state.marches_sent) == 0
    assert dev.state.marches_available == 1
    assert result.ok
    assert "no idle marches" in result.summary


def test_gather_can_use_last_march_when_reservation_disabled(make_agent):
    agent, dev = make_agent(marches=1)
    agent.config.gather.keep_one_march_free = False
    result = agent.run_routine("gather")
    assert result.ok
    assert len(dev.state.marches_sent) == 1
    assert dev.state.marches_available == 0


def test_gather_sends_only_detected_idle_marches(make_agent):
    agent, dev = make_agent(marches=2)
    result = agent.run_routine("gather")
    assert result.ok
    assert len(dev.state.marches_sent) == 1
    assert dev.state.marches_available == 1
    status = agent.state.data["marches"]
    assert status["busy"] == 4
    assert status["idle"] == 1
    assert status["source"] == "templates"


def test_gather_selects_formation_for_each_resource(make_agent):
    agent, dev = make_agent(marches=5)
    result = agent.run_routine("gather")
    assert result.ok
    formations = {item["resource"]: item["hero"] for item in dev.state.marches_sent}
    assert formations == {
        "stone": "edwin",
        "iron": "seth",
        "bread": "olive",
        "wood": "forrest",
    }


def test_gather_routine_respects_priority(make_agent):
    agent, dev = make_agent(marches=5)
    agent.config.gather.march_count = 2
    agent.config.gather.resource_priority = ["iron", "stone", "bread", "wood"]
    agent.run_routine("gather")
    resources = [m["resource"] for m in dev.state.marches_sent]
    assert resources == ["iron", "stone"]


def test_gather_disabled(make_agent):
    agent, dev = make_agent()
    agent.config.gather.enabled = False
    result = agent.run_routine("gather")
    assert result.ok and "disabled" in result.summary
    assert dev.state.taps == []


def test_build_routine_starts_both_queues(make_agent):
    agent, dev = make_agent()
    result = agent.run_routine("build")
    assert result.ok, result.summary
    assert dev.state.flags["construction_started"]
    assert dev.state.flags["research_started"]
    assert dev.state.screen == "city"


def test_full_cycle(make_agent):
    """daily + gather + build in sequence, like `run --all`."""
    agent, dev = make_agent(marches=5)
    results = [agent.run_routine(name) for name in ("daily", "gather", "build")]
    assert all(r.ok for r in results), [r.summary for r in results]
    assert dev.state.flags["production_collected"]
    assert len(dev.state.marches_sent) == 4
    assert dev.state.flags["research_started"]
    assert dev.state.screen == "city"


def test_gifts_routine_announces_new_codes(make_agent, tmp_path, monkeypatch):
    from kingshotbot.codes import CodeFinding

    def fake_fetch(name, timeout=15.0, session=None):
        return [
            CodeFinding("VIP777", "pockettactics", "https://x"),
            CodeFinding("Kingshot888", "pockettactics", "https://x"),
        ]

    import kingshotbot.codes.manager as mgr

    monkeypatch.setattr(mgr, "fetch_source", fake_fetch)

    agent, dev = make_agent()
    notifier = RecordingNotifier()
    agent.notifier = notifier
    result = agent.run_routine("gifts")
    assert result.ok, result.summary
    assert len(notifier.sent) == 1
    assert "VIP777" in notifier.sent[0]
    assert "Kingshot888" in notifier.sent[0]

    # second run: no new codes -> no new announcement
    result2 = agent.run_routine("gifts")
    assert result2.ok
    assert len(notifier.sent) == 1
    assert "no new codes" in result2.summary


def test_gifts_routine_survives_source_errors(make_agent, monkeypatch):
    def failing_fetch(name, timeout=15.0, session=None):
        raise ConnectionError("site down")

    import kingshotbot.codes.manager as mgr

    monkeypatch.setattr(mgr, "fetch_source", failing_fetch)
    agent, _ = make_agent()
    agent.config.gifts.manual_codes_file = ""  # no manual file
    result = agent.run_routine("gifts")
    assert result.ok  # errors are reported, not fatal
    assert "source error" in result.summary


def test_manual_codes_are_included(make_agent, tmp_path, monkeypatch):
    from kingshotbot.codes import CodeFinding

    def empty_fetch(name, timeout=15.0, session=None):
        return []

    import kingshotbot.codes.manager as mgr

    monkeypatch.setattr(mgr, "fetch_source", empty_fetch)
    manual = tmp_path / "manual_codes.txt"
    manual.write_text("# my codes\nVIP777\nOLDCODE expired\nNOT-A-CODE!!\n")

    agent, _ = make_agent()
    agent.config.gifts.manual_codes_file = str(manual)
    result = agent.run_routine("gifts")
    assert "VIP777" in result.summary
    assert "OLDCODE" not in result.summary
