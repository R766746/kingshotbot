# UI templates for the vision engine

The agent finds UI elements by matching small PNG crops of them against
the live screenshot (OpenCV template matching). Templates are
device/resolution-specific, so you capture your own once — it takes
about 10 minutes.

## Naming convention

Name files after the element they show. The routines look for these
names (missing ones are skipped gracefully, alternatives in brackets):

| Template file | Where to find it | Used by |
| --- | --- | --- |
| `btn_world_map.png` (`world_map`) | city view, map button | gather |
| `btn_build_menu.png` (`btn_build`) | city view, build/hammer button | build |
| `btn_construction.png` (`btn_build_slot`) | build menu | build |
| `btn_upgrade.png` (`btn_build_now`) | construction dialog | build |
| `btn_research.png` (`btn_academy`) | build menu / academy | build |
| `btn_research_start.png` (`btn_study`) | research dialog | build |
| `btn_quest.png` | city view, quest icon | daily |
| `btn_claim.png` | quest dialog | daily |
| `btn_mail.png` | city view, mail icon | daily |
| `btn_claim_all.png` | mail dialog | daily |
| `btn_alliance.png` | city view, alliance icon | daily |
| `btn_help_all.png` | alliance help dialog | daily |
| `btn_daily_claim.png` | daily login dialog | daily |
| `bubble_production.png` (`production_bubble`) | collectible resource bubbles | daily |
| `btn_city.png` (`btn_city_view`) | world map, city button | gather |
| `tile_stone.png` | world map stone tile | gather |
| `tile_iron.png` | world map iron tile | gather |
| `tile_bread.png` (`tile_food`) | world map bread/food tile | gather |
| `tile_wood.png` (`tile_lumber`) | world map wood tile | gather |
| `btn_search_gather.png` (`btn_gather`, `btn_search`) | tile detail dialog | gather |
| `btn_march_send.png` (`btn_send`, `btn_march`) | march confirm dialog | gather |
| `march_idle.png`, `march_busy.png` | march status slots/counter on world map | gather march-return detection |
| `preset_olive.png` | Olive formation/preset in march dialog | bread gathering |
| `preset_forrest.png` | Forrest formation/preset in march dialog | wood gathering |
| `preset_edwin.png` | Edwin formation/preset in march dialog | stone gathering |
| `preset_seth.png` | Seth formation/preset in march dialog | iron gathering |
| `btn_close.png` (`close`, `x_button`) | top-right X of any dialog | all |

## How to capture

1. Start your emulator + Kingshot, then run:
   ```bash
   python main.py screenshot city.png     # while the city is visible
   python main.py capture --count 5       # a burst while navigating the UI
   ```
2. Open the PNG in any editor (GIMP, Paint, Photopea...) and crop the
   element **tightly** (include its background within the button, avoid
   dynamic text/counters inside the crop).
3. Save as PNG into `templates/` with the name from the table above.
4. Verify: `python main.py doctor` (shows how many templates loaded) and
   `python main.py run --routine daily --dry-run` (logs what it would tap).

## Notes

- Resolution matters: keep the emulator at a fixed resolution
  (1280x720 is a good default) and capture templates at that resolution.
- If taps land on the wrong thing, raise `vision.match_threshold` in
  `config.yaml` (e.g. 0.85-0.9). If elements are not found, lower it.
- For march-return detection, capture both idle and busy slot/icon states.
  If they are unavailable, Tesseract OCR reads a `busy/total` counter such as
  `3/5` instead. Set `vision.march_counter_region: [x, y, width, height]` if
  other fractions elsewhere on the screen confuse OCR.
- Formation names are configurable under `gather.formations`; a value like
  `olive` maps to `preset_olive.png`.
- `manual_codes.txt` in this folder can hold gift codes you found
  yourself — one per line, `# comments` allowed.
