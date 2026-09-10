# 👑 KingshotBot — a local AI agent for Kingshot

[![CI](https://github.com/R766746/kingshotbot/actions/workflows/ci.yml/badge.svg)](https://github.com/R766746/kingshotbot/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**KingshotBot** is a local AI agent that plays the boring parts of
[Kingshot](https://kingshot.centurygame.com) (Century Games' medieval survival
strategy game) for you: it watches the game through screenshots, understands
the screen with computer vision, and acts through taps — while tracking gift
codes online and your alliance's event schedule.

> ⚠️ **Unofficial & educational.** Not affiliated with or endorsed by Century
> Games. Automating a game client can violate its Terms of Service and risk
> your account. Use at your own risk — start with `dry_run: true`.

---

## What it does

| Routine | What the agent does |
| --- | --- |
| `daily` | Claims daily login, quests, mail, alliance help; collects production bubbles |
| `gather` | Detects returned/idle marches, keeps one free for rallies, selects Olive/Forrest/Edwin/Seth formations, then gathers stone/iron/bread/wood (tiles L6–8) |
| `build` | Starts construction & research upgrades whenever the queues go idle |
| `gifts` | Scrapes public gift-code sites, dedupes against its memory, and **announces new codes** (console + Discord webhook) |
| `events` | Tracks the 00:00 UTC daily reset, reminds you to spend arena attacks and stamina, and counts down to your alliance's Bear Hunt |

**Demo mode works with zero setup** — the bot ships with a built-in Kingshot
*simulator* (mock device) so you can watch every routine run end-to-end before
touching a real emulator:

```bash
python main.py run --all --mock
```

## How it works

```
                ┌──────────────────────────────────────────────┐
                │                  AGENT                        │
  screenshots   │  ┌────────┐   ┌─────────┐   ┌────────────┐   │   taps/swipes
┌──────────┐    │  │        │   │         │   │            │   │    ┌──────────┐
│  Device  │────┼─▶│ Vision │──▶│  Brain  │──▶│  Routines  │───┼───▶│  Device  │
│ (ADB /   │    │  │ OpenCV │   │ rules + │   │ daily/     │   │    │ (ADB /   │
│  mock)   │◀───┼──│ + OCR  │   │ opt. LLM│   │ gather/... │   │    │  mock)   │
└──────────┘    │  └────────┘   └─────────┘   └────────────┘   │    └──────────┘
                │      state.json ▲   Discord webhook ▲        │
                └──────────────────┼──────────────────┼────────┘
                                   └── gift-code sources (online)
```

* **Device layer** — `adb` (BlueStacks, LDPlayer, MuMu, Google Play Games on
  PC, or a USB phone) or the built-in mock simulator.
* **Vision** — OpenCV template matching against PNG templates you capture
  once from your own screen (10 minutes, one time), including march-slot
  counting with Tesseract OCR fallback for `busy/total` counters.
* **Brain** — a deterministic rule engine by default; optionally an
  OpenAI-compatible LLM brain for screens the rules don't recognize (it can
  only choose from a fixed action vocabulary — it can't invent actions).
* **Routines** — small, self-contained automation units with recovery
  (press BACK, re-find, bail out safely). `dry_run` mode observes and logs
  without ever tapping. Named accounts can each override device, routines,
  gathering priorities, formations, notifications, and state storage.
* **Online data** — gift-code discovery from public code pages
  (pockettactics, pocketgamer, topuplive, lootbar) + a manual-codes file,
  and an embedded game-knowledge base distilled from community research
  (see [docs/RESEARCH.md](docs/RESEARCH.md)).

## Quick start

```bash
git clone https://github.com/R766746/kingshotbot.git
cd kingshotbot
pip install -r requirements.txt

# 1. try it with the built-in simulator (no emulator needed)
python main.py run --all --mock

# 2. check your setup against a real emulator
python main.py doctor

# 3. capture your UI templates (one time)
python main.py capture --count 5      # then crop PNGs into templates/

# 4. run for real
python main.py run -r daily --dry-run # watch what it *would* do first
python main.py run -r daily           # then let it act
python main.py watch                  # endless loop of all routines
```

Full emulator setup (BlueStacks/LDPlayer/MuMu, ADB ports, resolution advice)
is in [docs/SETUP.md](docs/SETUP.md). Template capture is documented in
[templates/README.md](templates/README.md).

## Commands

```
python main.py doctor                 # environment + device + template check
python main.py run -r daily           # run one routine (repeat -r for more)
python main.py run --all [--mock]     # every routine / force simulator
python main.py run -r gather --dry-run# observe + log, never tap
python main.py watch [--interval 300] # endless supervisor loop
python main.py run -r daily --account farm1  # run one configured account
python main.py run -r gather --all-accounts # run every configured account
python main.py codes [--announce]     # fetch gift codes online now
python main.py capture [--count 5]    # screenshots for template cropping
python main.py screenshot out.png     # single screenshot
python main.py info [section]         # embedded game knowledge (bear_hunt, ...)
python main.py status                 # persisted state (runs, codes, reminders)
```

## Configuration

Copy `config.example.yaml` to `config.yaml` (an empty file is also valid —
everything has defaults). Sensitive values live in environment variables:

```bash
export KSB_DISCORD_WEBHOOK="https://discord.com/api/webhooks/..."  # optional
export KSB_LLM_API_KEY="sk-..."                                    # optional
export KSB_ADB_SERIAL="127.0.0.1:5555"   # optional (BlueStacks default)
export KSB_STATE_FILE="data/state.json"      # optional persistence path
export KSB_DRY_RUN=1                         # safety: observe only
```

Multi-account setups inherit the top-level config and apply per-account
settings. `run`, `watch`, and `status` operate on all configured accounts by
default; use `--account NAME` to select one:

```yaml
accounts:
  - name: main
    device: {serial: "127.0.0.1:5555"}
  - name: farm1
    device: {serial: "127.0.0.1:5565"}
    gather:
      march_count: 2
      resource_priority: [bread, wood]
```

Each account gets a separate state file automatically. See
[`config.example.yaml`](config.example.yaml) for every supported override.

## Docker

Docker includes ADB and Tesseract. Copy the example config, make the data
directory writable by container UID 1000, then start the supervisor:

```bash
cp config.example.yaml config.yaml
mkdir -p data
# Linux: sudo chown 1000:1000 data
docker compose up -d --build
docker compose logs -f
```

The Compose service reaches a host emulator through
`host.docker.internal:5555`; set `KSB_ADB_SERIAL` if your emulator uses another
port. Full instructions are in [docs/SETUP.md](docs/SETUP.md#8-docker).

## Project layout

```
kingshotbot/
├── main.py                  # CLI entry point
├── config.example.yaml      # documented config template
├── Dockerfile               # ADB + Tesseract runtime image
├── docker-compose.yml       # persistent supervisor service
├── kingshotbot/
│   ├── agent.py             # observe → decide → act loop, dry-run safety
│   ├── device.py            # ADB device layer
│   ├── mock_device.py       # built-in Kingshot simulator (demo/tests)
│   ├── vision.py            # OpenCV template matching + optional OCR
│   ├── state.py             # JSON persistence (runs, codes, reminders)
│   ├── notify.py            # console + Discord webhook notifications
│   ├── config.py            # YAML + env configuration
│   ├── cli.py               # argparse CLI
│   ├── brain/               # rules engine + optional LLM brain
│   ├── routines/            # daily, gather, build, gifts, events
│   ├── codes/               # online gift-code scrapers
│   └── data/game_knowledge.yaml   # distilled community research
├── templates/               # your captured UI templates (see its README)
├── tests/                   # 74 tests (pytest) incl. full agent pipeline
└── docs/                    # RESEARCH.md, SETUP.md
```

## Testing

```bash
pip install -r requirements-dev.txt
pytest               # 74 tests, no device/emulator needed
```

The test-suite runs the *entire* pipeline — vision, agent, routines — against
the mock simulator with generated templates, so it validates real behavior,
not mocks of it.

## Limitations & roadmap

- UI routines need one-time template capture per device/resolution (by
  design — no bundled assets can match your exact screen).
- Gift-code sources are public websites; layouts change and sources
  occasionally fail (errors are reported, never fatal). Add your own codes to
  `templates/manual_codes.txt`.
- March-counter OCR depends on the game exposing a readable `busy/total`
  value; capturing `march_idle.png` and `march_busy.png` is more reliable.
- Future work: in-game mail parsing, smarter event participation, march ETA
  scheduling, and a small local status dashboard.

## Credits & disclaimer

Game knowledge distilled from public community research — see
[docs/RESEARCH.md](docs/RESEARCH.md) for sources. This project is unofficial,
MIT-licensed, and not affiliated with Century Games Pte. Ltd. You are
responsible for how you use it.
