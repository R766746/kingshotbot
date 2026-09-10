# Kingshot research notes (September 2026)

The data behind this bot's defaults and knowledge base, gathered from public
online sources. This document is the "analysis with online data" the project
was built on.

## The game

**Kingshot** is an idle medieval survival strategy game (4X + tower defense)
by **Century Games Pte. Ltd.** — the studio behind Whiteout Survival. It
released globally on 2025-02-22 (iOS first, Android shortly after) and has
50M+ downloads on Google Play with a 4.4★ rating. You play a Governor
rebuilding society after a rebellion: city building, survivor management,
hero recruitment, alliance warfare.

- App Store: https://apps.apple.com/us/app/kingshot/id6739554056
- Google Play: `com.run.tower.defense`
- Official gift-code center: https://ks-giftcode.centurygame.com/

## Economy & gathering (drives the `gather` routine)

Four city resources, each with a matching building and a specialist blue hero:

| Resource | Building | Gathering hero |
| --- | --- | --- |
| Bread | Mill | Olive |
| Wood | Sawmill | Forrest |
| Stone | Quarry | Edwin |
| Iron | Iron Mine | Seth |

Community-verified facts encoded in `config.example.yaml`:

- **Tiles only go up to level 8** — there are no level 9-10 tiles; L6-8 is
  the sweet spot for yield vs. availability.
- Town Center inside **alliance territory** grants +50-100% gathering.
- **Stone and iron** are usually the bottleneck for building upgrades —
  hence the default `resource_priority: [stone, iron, bread, wood]`.
- Efficient farms keep 4 marches gathering and **one march free for
  auto-rally-join**; queue ~8h gathers before bed, collect and requeue in
  the morning (default `march_count: 4`, `keep_one_march_free: true`).

## Daily loop (drives the `daily` + `build` routines)

The community "15-minute routine": collect production → daily login reward →
start construction/research timers → spend Governor Stamina on Intel missions
→ help all alliance timers → claim mail/quests/gifts → train troops → send
marches → check the Nomadic Merchant. Daily reset is **00:00 UTC**; play your
**10 arena attacks** in the final minutes before reset so nobody can counter
your ranking.

## Events (drives the `events` routine)

Kingshot runs on two clocks — a fixed weekly spine and a ~4-week rotation:

| Event | Cadence | Notes |
| --- | --- | --- |
| **Bear Hunt (Bear Trap)** | every 2 days, 30 min | Alliance rally vs a trapped bear; scheduled by R4/R5. Pure damage check — the bear never fights back. Formation ≈ 1/10/89 infantry/cavalry/archers at Gen4+. Donate Hunting Arrows: Pitfall L5 = +25% alliance attack. **Auto-rally does not work** — you must join rallies manually. Stay in the alliance until tally or lose personal rewards. |
| Alliance Championship | weekly | alliance-vs-alliance bracket |
| Armament Competition | 2-day, alternating biweekly | gear-growth spending |
| Officer Project | 2-day, alternating biweekly | hero/troop spending |
| Swordland Showdown | recurring | instanced alliance battle; Sunday matches |
| Strongest Governor | 7 days | rotating; one scoring theme per day |
| Kingdom of Power (KvK) | 5 days | kingdom-vs-kingdom, prep phase first |
| Alliance Brawl | 6 days | combined individual + alliance scoring |
| Champagne Fair | monthly | trade-and-collect shop event |

Because trap times are set per-alliance, the bot takes yours from config
(`events.bear_hunt_utc: "19:30"`) instead of assuming a schedule.

## Gift codes (drives the `gifts` routine)

Century Games drops codes on socials and the official redemption center
(Player ID + Kingdom + code; rewards arrive in-game mail). Active codes
around September 2026 include `Kingshot888`, `VIP777` (200 gems, mythic
skill books/manuals, gold keys) and time-limited drops like
`CHILLWEEKEND`; typical rewards are gems, speedups, resources and hero XP.

The bot scrapes the same public aggregator pages players use
(pockettactics.com, pocketgamer.com, topuplive.com, lootbar.com), splits
active vs expired sections, validates code-shaped tokens with heuristics,
dedupes across sources and against its own memory, and announces only
**new** codes. Redemption itself is manual (deliberately — auto-redeeming
against the official site is where ToS risk gets serious).

## Bot landscape (what already exists)

- Discord bots dominate: event schedulers (bear-attack timers, arena alerts,
  reaction roles) and gift-code announcers/redeemers. Some use browser
  automation (Playwright) against the redemption site for bulk claims.
- No open-source **local AI agent** (screen vision + taps on the emulator)
  existed for Kingshot at research time — which is the gap this project
  fills.
- Standard local-automation stack for this game family: Android emulator +
  ADB input + screenshot + template matching. This bot follows that stack
  and adds a rule/LLM hybrid brain and a mock simulator for safe testing.

## Sources

- kingshotwiki.com — Beginner Bear Hunt Guide (2026-09)
- boostbot.org — Kingshot event calendar & 4-week rotation (2026-08)
- kingshotmastery.com — Bear Trap formations & scheduling (2026-07)
- kingshothandbook.com — events calendar, daily routine guide (2026-09)
- kingshot.fandom.com — hero FAQ, new-player questions
- heaven-guardian.com — resource & gathering guide (2026-08)
- kingshotwin.com — farm-account daily routine, tile levels
- pockettactics.com / pocketgamer.com / topuplive.com / lootbar.com /
  gamsgo.com — gift-code lists (2026-09)
- Grokipedia, App Store and Google Play listings — game overview
