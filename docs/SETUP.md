# Setup guide: emulator, ADB, templates, first run

## 1. Install

```bash
git clone https://github.com/R766746/kingshotbot.git
cd kingshotbot
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Python 3.9+ required. On Windows, install
[platform-tools](https://developer.android.com/tools/releases/platform-tools)
(contains `adb`) and add it to your PATH.

## 2. Emulator with ADB

Kingshot runs fine on any Android emulator. Recommended settings: **1280x720,
landscape, fixed DPI** (templates are resolution-specific — lock it down).

| Emulator | ADB address (serial) | Notes |
| --- | --- | --- |
| BlueStacks 5 | `127.0.0.1:5555` (or 5565/5575 for more instances) | Settings → Advanced → Android Debug Bridge → enable |
| LDPlayer 9 | `emulator-5554` (first instance) | ADB is on by default |
| MuMu Player 12 | `127.0.0.1:16384` | Settings → extras → ADB |
| USB phone | device id from `adb devices` | Enable USB debugging |

Set it in `config.yaml`:

```yaml
device:
  mode: adb
  serial: "127.0.0.1:5555"
```

or via environment: `export KSB_ADB_SERIAL=127.0.0.1:5555`.

Verify:

```bash
python main.py doctor
# [ok] adb device connected: 127.0.0.1:5555
# [ok] screenshot works: 1280x720
```

## 3. Capture UI templates (one time, ~10 minutes)

1. Launch Kingshot in the emulator and log in.
2. While on each screen, grab screenshots:
   ```bash
   python main.py screenshot city.png
   python main.py capture --count 5     # burst while navigating menus
   ```
3. Open each PNG in an image editor and **tightly crop** the UI elements
   listed in [templates/README.md](../templates/README.md) — buttons like
   `btn_world_map.png`, `tile_stone.png`, `btn_march_send.png`...
   Tips:
   - crop the button plus a few pixels of its own background
   - avoid dynamic parts (counters, timers) inside the crop
   - same resolution as the live screen (don't resize)
4. Save the crops into `templates/`.
5. Validate:
   ```bash
   python main.py doctor                  # should show N templates
   python main.py run -r daily --dry-run  # logs what it would tap
   ```

If the bot misses elements, lower `vision.match_threshold` (0.75); if it taps
the wrong things, raise it (0.85-0.9).

## 4. First real runs

```bash
# always preview with dry-run first:
python main.py run -r daily --dry-run

# then for real, one routine at a time:
python main.py run -r daily
python main.py run -r gather
python main.py run -r build

# supervisor loop (default: every 300s):
python main.py watch
```

## 5. Notifications (optional)

Discord webhook — create one in your server (Channel Settings → Integrations
→ Webhooks), then:

```bash
export KSB_DISCORD_WEBHOOK="https://discord.com/api/webhooks/123..."
python main.py codes --announce    # test it
```

The bot posts new gift codes, daily-reset and Bear Hunt reminders there.

## 6. Optional LLM brain

If you want the agent to reason about screens the rules don't recognize:

```yaml
llm:
  enabled: true
  base_url: https://api.openai.com/v1   # or any OpenAI-compatible URL
  model: gpt-4o-mini
```

```bash
export KSB_LLM_API_KEY="sk-..."
```

The LLM only ever picks from a fixed action vocabulary (`tap` a detected
element, `back`, `wait`, `abort`) — it cannot invent free-form input.

## 7. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `adb binary not found` | Install platform-tools; set `device.adb_path` to the full path |
| `no ADB devices online` | Start the emulator first; enable ADB in its settings; try `adb connect 127.0.0.1:5555` |
| Screenshot is black | Some emulators need a moment after boot; re-run. Disable hardware overlays in emulator settings |
| Nothing matches | Templates missing or wrong resolution — re-capture at the same resolution as `python main.py screenshot` |
| Wrong taps | Raise `match_threshold`; re-crop templates tighter |
| Codes command finds nothing | Source sites change layouts / are down; add codes to `templates/manual_codes.txt` |
| Bot taps during a battle | Run `watch` only when you're away; use `--interval` to slow it down |

## 8. Safety

- Start with `KSB_DRY_RUN=1`.
- The bot never spends gems or makes purchases; if it ever sees a purchase
  prompt it doesn't recognize, it presses BACK (and the LLM brain is
  instructed to `abort` on purchase/captcha screens).
- Game automation may violate Kingshot's Terms of Service — that risk is
  yours. This project is educational and unofficial.
