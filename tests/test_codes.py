"""Gift-code parsing tests: heuristics, HTML parsing, manager merging."""

from kingshotbot.codes import CodeManager, SOURCES, looks_like_code, parse_html
from kingshotbot.codes.sources import fetch_source

# --- validation heuristics ------------------------------------------------ #

GOOD = [
    "VIP777", "Kingshot888", "CHILLWEEKEND", "KS0822", "rK9e6vKXu",
    "OFFICIALSTORE0904", "1INAMILLION", "0425FORU", "KINGSHOT13M",
]

BAD = [
    "2026",            # pure digits
    "SEPTEMBER",       # blocklist (month)
    "september",       # not all-caps + blocklist
    "Kingshot",        # blocklist
    "discord",         # blocklist, lowercase
    "DISCORD",         # blocklist
    "ok",              # too short
    "a" * 25,          # too long
    "WITH SPACE",      # invalid charset
    "WITH-DASH",       # invalid charset
    "",                # empty
]


def test_looks_like_code_accepts_real_codes():
    for code in GOOD:
        assert looks_like_code(code), code


def test_looks_like_code_rejects_junk():
    for token in BAD:
        assert not looks_like_code(token), token


# --- HTML parsing ---------------------------------------------------------- #

POCKETTACTICS_LIKE = """
<html><body>
<h1>Kingshot codes for September 2026</h1>
<h2>Active codes</h2>
<ul>
<li><strong>CHILLWEEKEND</strong> - rewards (new!)</li>
<li><strong>Kingshot888</strong> - rewards</li>
<li><strong>VIP777</strong> - 200 gems</li>
</ul>
<h2>How can I get more Kingshot codes?</h2>
<h2>Expired codes</h2>
<ul>
<li><strong>KS0715</strong></li>
<li><strong>KAS0615</strong></li>
<li><strong>AJISAI26JP</strong></li>
</ul>
</body></html>
"""

TABLE_LIKE = """
<html><body>
<h2>Active Kingshot Gift Codes (September 2026)</h2>
<table><tr><th>Code</th><th>Rewards</th></tr>
<tr><td>Kingshot888</td><td>2x 100 Gems</td></tr>
<tr><td>VIP777</td><td>200x Gems</td></tr>
<tr><td>CHILLWEEKEND</td><td>image.png</td></tr>
</table>
<h2>Expired Kingshot Gift Codes</h2>
<ul><li><strong>S0803</strong></li><li><strong>DC500KWEMADEIT</strong></li></ul>
</body></html>
"""


def test_parse_html_active_vs_expired():
    findings = parse_html("test", "https://t", POCKETTACTICS_LIKE)
    codes = {f.code for f in findings}
    assert codes == {"CHILLWEEKEND", "Kingshot888", "VIP777"}
    for f in findings:
        assert f.source == "test" and f.url == "https://t"


def test_parse_html_table_layout():
    findings = parse_html("test", "https://t", TABLE_LIKE)
    codes = {f.code for f in findings}
    assert {"Kingshot888", "VIP777", "CHILLWEEKEND"} <= codes
    assert "S0803" not in codes
    assert "DC500KWEMADEIT" not in codes


def test_parse_html_no_expired_section():
    html = "<p><strong>VIP777</strong></p><p><strong>Kingshot888</strong></p>"
    findings = parse_html("t", "u", html)
    assert {f.code for f in findings} == {"VIP777", "Kingshot888"}


def test_parse_html_empty_page():
    assert parse_html("t", "u", "") == []


# --- manager --------------------------------------------------------------- #

def test_manager_merges_and_dedupes(monkeypatch, tmp_path):
    from kingshotbot.codes import CodeFinding

    responses = {
        "pockettactics": [CodeFinding("VIP777", "pockettactics", "u1"),
                          CodeFinding("KS0822", "pockettactics", "u1")],
        "pocketgamer": [CodeFinding("vip777", "pocketgamer", "u2")],
    }
    monkeypatch.setattr(
        "kingshotbot.codes.manager.fetch_source",
        lambda name, timeout=15.0, session=None: responses[name],
    )
    manager = CodeManager(sources=["pockettactics", "pocketgamer"],
                          manual_codes_file=None)
    findings = manager.fetch_all()
    codes = {f.code.upper() for f in findings}
    assert codes == {"VIP777", "KS0822"}   # deduped across sources
    assert not manager.errors


def test_manager_collects_errors(monkeypatch):
    def boom(name, timeout=15.0, session=None):
        raise TimeoutError("slow")

    monkeypatch.setattr("kingshotbot.codes.manager.fetch_source", boom)
    manager = CodeManager(sources=["pockettactics"], manual_codes_file=None)
    findings = manager.fetch_all()
    assert findings == []
    assert len(manager.errors) == 1
    assert "slow" in manager.errors[0][1]


def test_manager_manual_file(tmp_path):
    manual = tmp_path / "manual_codes.txt"
    manual.write_text("VIP777\nKS0822 active\nOLDCODE expired\n# comment\n\n")
    manager = CodeManager(sources=[], manual_codes_file=manual)
    findings = manager.fetch_all()
    assert {f.code for f in findings} == {"VIP777", "KS0822"}
    assert all(f.source == "manual" for f in findings)


def test_manager_ignores_unknown_sources(tmp_path):
    manager = CodeManager(sources=["not-a-site", "pockettactics"],
                          manual_codes_file=None)
    assert manager.source_names == ["pockettactics"]


def test_known_sources_exist():
    assert "pockettactics" in SOURCES
    assert SOURCES["pockettactics"].startswith("https://")
