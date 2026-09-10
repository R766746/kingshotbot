"""Command-line interface.

Examples:
    python main.py doctor                     # check adb/opencv/config
    python main.py screenshot out.png         # grab a screenshot
    python main.py run --routine daily        # run one routine
    python main.py run --all                  # full cycle
    python main.py watch                      # endless loop, full cycles
    python main.py codes                      # fetch gift codes online
    python main.py info                       # show embedded game knowledge
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Tuple

from . import __version__
from .agent import Agent
from .config import (
    BotConfig,
    discord_webhook_url,
    for_account,
    llm_api_key,
    load_config,
)
from .device import ADBDevice, DeviceError
from .logging_setup import setup_logging
from .mock_device import MockDevice
from .notify import Notifier
from .routines import ROUTINES
from .state import BotState
from .vision import Vision


def build_device(cfg: BotConfig):
    """Create the configured device (ADB or mock simulator)."""
    if cfg.device.mode == "mock":
        return MockDevice()
    dev = ADBDevice(serial=cfg.device.serial, adb_path=cfg.device.adb_path)
    if not dev.connect():
        raise SystemExit(
            "no ADB device available - start your emulator (BlueStacks/LDPlayer/"
            "MuMu) with ADB enabled, or set device.mode=mock to try the simulator"
        )
    return dev


def _mock_templates_dir() -> Path:
    """Generate vision templates for the built-in simulator."""
    import cv2

    from .mock_device import SCREENS, render_template

    out = Path(tempfile.mkdtemp(prefix="ksb_mock_templates_"))
    for screen, elements in SCREENS.items():
        for elem in elements:
            cv2.imwrite(str(out / f"{elem.id}.png"),
                        render_template(screen, elem.id))
    return out


def build_agent(cfg: BotConfig, brain=None, account_name: Optional[str] = None):
    """Assemble the full agent stack from an effective account config."""
    device = build_device(cfg)
    templates_dir = cfg.vision.templates_dir
    if cfg.device.mode == "mock":
        # the simulator renders its own UI, so it always gets matching
        # templates generated on the fly - the demo works out of the box
        templates_dir = _mock_templates_dir()
    vision = Vision(
        templates_dir=templates_dir,
        threshold=cfg.vision.match_threshold,
        grayscale=cfg.vision.grayscale,
        ocr_enabled=cfg.vision.ocr_enabled,
    )
    state = BotState(cfg.state_file)
    notifier = Notifier(
        webhook_url=discord_webhook_url(cfg),
        console=cfg.notify.console,
        title_prefix=account_name or "",
    )
    return Agent(device, vision, state, cfg, notifier, brain)


def maybe_llm_brain(cfg: BotConfig):
    """Build the LLM brain if enabled and key present; else None."""
    if not cfg.llm.enabled:
        return None
    from .brain import LLMBrain

    key = llm_api_key(cfg)
    if not key:
        print("llm.enabled=true but no API key in "
              f"{cfg.llm.api_key_env} - LLM brain disabled", file=sys.stderr)
        return None
    return LLMBrain(api_key=key, base_url=cfg.llm.base_url, model=cfg.llm.model)


def _account_configs(
    args, cfg: BotConfig
) -> List[Tuple[Optional[str], BotConfig]]:
    """Select effective account configs for account-aware commands.

    Once ``accounts`` is configured, run/watch/status target all accounts by
    default. ``--account`` narrows execution to one named account.
    """
    requested = getattr(args, "account", None)
    all_requested = bool(getattr(args, "all_accounts", False))
    if requested and all_requested:
        raise ValueError("--account and --all-accounts cannot be used together")
    if requested:
        return [(requested, for_account(cfg, requested))]
    if cfg.accounts:
        return [
            (account.name, for_account(cfg, account.name))
            for account in cfg.accounts
        ]
    return [(None, cfg)]


def _single_account_config(args, cfg: BotConfig) -> BotConfig:
    """Apply an optional ``--account`` to a single-device command."""
    requested = getattr(args, "account", None)
    return for_account(cfg, requested) if requested else cfg


# ---------------------------------------------------------------------- #
# commands
# ---------------------------------------------------------------------- #

def cmd_doctor(args, cfg: BotConfig) -> int:
    base_cfg = cfg
    cfg = _single_account_config(args, cfg)
    print(f"KingshotBot v{__version__} - environment check\n" + "-" * 46)
    ok = True

    import cv2  # noqa: F401

    print(f"[ok] python {sys.version.split()[0]}, opencv available")

    if cfg.device.mode == "mock":
        print("[ok] device mode = mock (simulator, no emulator needed)")
        vision = Vision(_mock_templates_dir(), cfg.vision.match_threshold)
        print(f"[ok] {len(vision.template_names)} simulator templates generated")
    else:
        try:
            dev = ADBDevice(serial=cfg.device.serial, adb_path=cfg.device.adb_path)
            if dev.connect():
                print(f"[ok] adb device connected: {dev.serial}")
                shot = dev.screenshot()
                print(f"[ok] screenshot works: {shot.shape[1]}x{shot.shape[0]}")
            else:
                ok = False
                print("[!!] no adb device online")
        except DeviceError as exc:
            ok = False
            print(f"[!!] adb problem: {exc}")

        vision = Vision(cfg.vision.templates_dir, cfg.vision.match_threshold)
        print(f"[{'ok' if vision.template_names else '!!'}] "
              f"{len(vision.template_names)} templates in {vision.templates_dir}")
        if not vision.template_names:
            print("     run `python main.py capture` and crop UI templates "
                  "(templates/README.md)")

    if cfg.notify.discord_webhook_env:
        import os

        hooked = bool(os.environ.get(cfg.notify.discord_webhook_env))
        print(f"[{'ok' if hooked else '--'}] discord webhook "
              f"({'set' if hooked else 'not set (optional)'})")
    if cfg.llm.enabled:
        print(f"[{'ok' if llm_api_key(cfg) else '!!'}] llm brain enabled")
    if cfg.vision.ocr_enabled:
        import shutil

        has_tesseract = shutil.which("tesseract") is not None
        print(
            f"[{'ok' if has_tesseract else '--'}] march-counter OCR "
            f"({'available' if has_tesseract else 'Tesseract not found; templates work'})"
        )
    print(f"[ok] routines available: {', '.join(sorted(ROUTINES))}")
    if base_cfg.accounts:
        print("[ok] accounts configured: "
              + ", ".join(account.name for account in base_cfg.accounts))
        if not getattr(args, "account", None):
            print("     use `doctor --account NAME` to check an account override")
    print("\nAll good!" if ok else "\nSome checks failed - see above.")
    return 0 if ok else 1


def cmd_screenshot(args, cfg: BotConfig) -> int:
    cfg = _single_account_config(args, cfg)
    device = build_device(cfg)
    img = device.screenshot()
    out = Path(args.output or "screenshot.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    import cv2

    cv2.imwrite(str(out), img)
    print(f"saved {out} ({img.shape[1]}x{img.shape[0]})")
    return 0


def cmd_capture(args, cfg: BotConfig) -> int:
    """Take screenshots the user can crop into templates."""
    cfg = _single_account_config(args, cfg)
    device = build_device(cfg)
    out_dir = Path(args.out or "captures")
    out_dir.mkdir(parents=True, exist_ok=True)
    count = args.count
    for i in range(count):
        img = device.screenshot()
        path = out_dir / f"capture_{time.strftime('%Y%m%d_%H%M%S')}_{i}.png"
        import cv2

        cv2.imwrite(str(path), img)
        print(f"saved {path}")
        if i < count - 1:
            time.sleep(args.delay)
    print(f"\n{count} screenshot(s) in {out_dir}/ - crop UI elements into "
          f"{cfg.vision.templates_dir}/ as PNG files named after what they are "
          "(btn_world_map.png, tile_stone.png, ...). See templates/README.md.")
    return 0


def cmd_run(args, cfg: BotConfig) -> int:
    names = list(ROUTINES) if args.all else (args.routine or [])
    if not names:
        print(f"no routine selected; available: {', '.join(sorted(ROUTINES))}",
              file=sys.stderr)
        return 2

    results = []
    selected = _account_configs(args, cfg)
    for account_name, account_cfg in selected:
        if account_name and not args.json:
            print(f"=== account: {account_name} ===")
        agent = build_agent(
            account_cfg,
            brain=maybe_llm_brain(account_cfg),
            account_name=account_name,
        )
        for name in names:
            result = agent.run_routine(name)
            results.append((account_name, result))

    if args.json:
        payload = []
        for account_name, result in results:
            item = dict(result.__dict__)
            if account_name:
                item["account"] = account_name
            payload.append(item)
        print(json.dumps(payload, indent=2))
    return 0 if all(result.ok for _, result in results) else 1


def cmd_watch(args, cfg: BotConfig) -> int:
    interval = args.interval or cfg.loop_interval_seconds
    agents = []
    for account_name, account_cfg in _account_configs(args, cfg):
        agents.append(
            (
                account_name,
                build_agent(
                    account_cfg,
                    brain=maybe_llm_brain(account_cfg),
                    account_name=account_name,
                ),
            )
        )
    labels = [name or "default" for name, _ in agents]
    print(f"watch mode: accounts={labels}, every {interval}s "
          f"(Ctrl+C to stop)")
    while True:
        for account_name, agent in agents:
            if account_name:
                print(f"=== account: {account_name} ===")
            for name in agent.config.routines:
                if name in ROUTINES:
                    agent.run_routine(name)
            agent.state.mark_cycle()
            agent.state.save()
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nbye!")
            return 0


def cmd_codes(args, cfg: BotConfig) -> int:
    cfg = _single_account_config(args, cfg)
    from .codes import CodeManager

    manager = CodeManager(
        sources=cfg.gifts.sources,
        manual_codes_file=cfg.gifts.manual_codes_file,
        timeout=20.0,
    )
    findings = manager.fetch_all()
    if args.json:
        print(json.dumps([f.__dict__ for f in findings], indent=2))
    else:
        print(f"Active Kingshot gift codes ({len(findings)}):")
        for f in findings:
            print(f"  {f.code:<22} [{f.source}]")
        for url, err in manager.errors:
            print(f"  (source failed: {url}: {err[:80]})")
        print(f"\nRedeem at {cfg.gifts.redeem_url} "
              f"(Player ID + Kingdom + code; rewards arrive in your in-game mail).")
    if findings:
        if args.announce:
            Notifier(
                webhook_url=discord_webhook_url(cfg),
                title_prefix=getattr(args, "account", None) or "",
            ).send(
                "Active Kingshot codes: " + ", ".join(f"`{f.code}`" for f in findings),
                title="Kingshot gift codes",
            )
        return 0
    return 1


def cmd_info(args, cfg: BotConfig) -> int:
    import yaml

    data_path = Path(__file__).parent / "data" / "game_knowledge.yaml"
    data = yaml.safe_load(data_path.read_text(encoding="utf-8"))
    if args.section:
        data = data.get(args.section, {})
    print(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    return 0


def cmd_status(args, cfg: BotConfig) -> int:
    selected = _account_configs(args, cfg)
    if len(selected) == 1 and selected[0][0] is None:
        state = BotState(selected[0][1].state_file)
        print(json.dumps(state.data, indent=2, default=str))
        return 0

    payload = {}
    for account_name, account_cfg in selected:
        state = BotState(account_cfg.state_file)
        payload[account_name or "default"] = {
            "state_file": account_cfg.state_file,
            "state": state.data,
        }
    print(json.dumps(payload, indent=2, default=str))
    return 0


# ---------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kingshotbot",
        description="Local AI agent for the mobile game Kingshot (unofficial).",
    )
    parser.add_argument("--config", default="config.yaml", help="config file path")
    parser.add_argument("--verbose", "-v", action="store_true")
    sub = parser.add_subparsers(dest="command")

    p_doctor = sub.add_parser("doctor", help="check adb/opencv/templates/config")
    p_doctor.add_argument("--account", help="check one configured account")

    p_shot = sub.add_parser("screenshot", help="save one screenshot")
    p_shot.add_argument("output", nargs="?", default="screenshot.png")
    p_shot.add_argument("--account", help="capture one configured account")

    p_cap = sub.add_parser("capture", help="save screenshots for template cropping")
    p_cap.add_argument("--count", type=int, default=3)
    p_cap.add_argument("--delay", type=float, default=2.0)
    p_cap.add_argument("--out", default="captures")
    p_cap.add_argument("--account", help="capture one configured account")

    p_run = sub.add_parser("run", help="run one or more routines")
    p_run.add_argument("--routine", "-r", action="append",
                       choices=sorted(ROUTINES), help="routine to run")
    p_run.add_argument("--all", action="store_true", help="run every routine")
    p_run.add_argument("--json", action="store_true", help="print JSON results")
    p_run.add_argument("--dry-run", action="store_true",
                       help="observe and log, never tap")
    p_run.add_argument("--mock", action="store_true", help="force the simulator")
    p_run.add_argument("--account", help="run only one configured account")
    p_run.add_argument("--all-accounts", action="store_true",
                       help="run all configured accounts (the default when present)")

    p_watch = sub.add_parser("watch", help="run routines in an endless loop")
    p_watch.add_argument("--interval", type=int, default=None)
    p_watch.add_argument("--mock", action="store_true")
    p_watch.add_argument("--dry-run", action="store_true")
    p_watch.add_argument("--account", help="watch only one configured account")
    p_watch.add_argument("--all-accounts", action="store_true",
                         help="watch all configured accounts")

    p_codes = sub.add_parser("codes", help="fetch active gift codes online")
    p_codes.add_argument("--json", action="store_true")
    p_codes.add_argument("--announce", action="store_true",
                         help="also post to Discord if configured")
    p_codes.add_argument("--account", help="use one account's code settings")

    p_info = sub.add_parser("info", help="show embedded game knowledge")
    p_info.add_argument("section", nargs="?", default=None)

    p_status = sub.add_parser("status", help="dump persisted state")
    p_status.add_argument("--account", help="show only one configured account")
    p_status.add_argument("--all-accounts", action="store_true",
                          help="show all configured accounts")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    try:
        cfg = load_config(args.config)
    except ValueError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    if getattr(args, "mock", False):
        cfg.device.mode = "mock"
        for account in cfg.accounts:
            account.device = dict(account.device)
            account.device["mode"] = "mock"
    if getattr(args, "dry_run", False):
        cfg.dry_run = True
        for account in cfg.accounts:
            account.dry_run = True
    setup_logging(verbose=args.verbose)
    handlers = {
        "doctor": cmd_doctor, "screenshot": cmd_screenshot, "capture": cmd_capture,
        "run": cmd_run, "watch": cmd_watch, "codes": cmd_codes,
        "info": cmd_info, "status": cmd_status,
    }
    try:
        return handlers[args.command](args, cfg)
    except KeyboardInterrupt:
        print("\ninterrupted")
        return 130
    except DeviceError as exc:
        print(f"device error: {exc}", file=sys.stderr)
        return 1
    except (KeyError, ValueError) as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
