"""Configuration loading and validation.

Configuration comes from a YAML file (see ``config.example.yaml``) with
environment-variable overrides for anything sensitive (Discord webhook
URLs, LLM API keys).
"""

from __future__ import annotations

import copy
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

log = logging.getLogger("kingshotbot.config")

ENV_PREFIX = "KSB_"


@dataclass
class DeviceConfig:
    """How to reach the Android device / emulator running Kingshot."""

    mode: str = "adb"  # "adb" or "mock" (simulation / dry-run)
    adb_path: str = "adb"
    serial: Optional[str] = None  # e.g. "127.0.0.1:5555" for BlueStacks
    screenshot_interval: float = 0.6  # seconds between screen polls
    tap_delay: float = 0.35  # seconds to wait after a tap


@dataclass
class VisionConfig:
    """Computer-vision tuning."""

    templates_dir: str = "templates"
    match_threshold: float = 0.80  # template-match confidence
    grayscale: bool = True
    ocr_enabled: bool = True  # auto-disabled if tesseract is missing
    # Optional [x, y, width, height] crop for the march-counter OCR fallback.
    march_counter_region: Optional[List[int]] = None


@dataclass
class LLMConfig:
    """Optional LLM "brain" for interpreting unfamiliar screens.

    Uses any OpenAI-compatible chat-completions API. Disabled by default;
    the rule-based brain is fully functional without it.
    """

    enabled: bool = False
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    api_key_env: str = "KSB_LLM_API_KEY"  # env var holding the key
    temperature: float = 0.1
    max_tokens: int = 400


@dataclass
class NotifyConfig:
    """Notification channels."""

    discord_webhook_env: str = "KSB_DISCORD_WEBHOOK"  # env var with webhook URL
    console: bool = True


@dataclass
class GatherConfig:
    """Resource gathering routine tuning (from community research).

    Best tile levels are 6-8 (there are no level 9-10 tiles in Kingshot).
    """

    enabled: bool = True
    tile_levels: str = "6-8"
    march_count: int = 4  # marches to keep gathering
    resource_priority: List[str] = field(
        default_factory=lambda: ["stone", "iron", "bread", "wood"]
    )
    keep_one_march_free: bool = True  # reserve a march for auto-rally-join
    formations: Dict[str, str] = field(
        default_factory=lambda: {
            "bread": "olive",
            "wood": "forrest",
            "stone": "edwin",
            "iron": "seth",
        }
    )


@dataclass
class EventsConfig:
    """Event tracking (schedules verified against community calendars)."""

    enabled: bool = True
    daily_reset_utc_hour: int = 0  # Kingshot daily reset is 00:00 UTC
    bear_hunt_interval_days: int = 2  # Bear Trap runs every ~2 days
    bear_hunt_utc: Optional[str] = None  # "19:30" - your alliance's trap time
    arena_attacks_per_day: int = 10  # do them in the last minutes before reset
    reminder_minutes_before: List[int] = field(
        default_factory=lambda: [60, 15]
    )


@dataclass
class GiftsConfig:
    """Gift-code discovery from public online sources."""

    enabled: bool = True
    sources: List[str] = field(
        default_factory=lambda: [
            "pockettactics",
            "pocketgamer",
            "topuplive",
            "lootbar",
        ]
    )
    check_interval_minutes: int = 60
    manual_codes_file: str = "templates/manual_codes.txt"
    player_id: str = ""  # your in-game Player ID (avatar -> top-left)
    kingdom: str = ""  # your Kingdom number
    redeem_url: str = "https://ks-giftcode.centurygame.com/"


@dataclass
class AccountConfig:
    """Overrides for one emulator/account in a multi-account setup."""

    name: str
    device: Dict[str, Any] = field(default_factory=dict)
    vision: Dict[str, Any] = field(default_factory=dict)
    llm: Dict[str, Any] = field(default_factory=dict)
    notify: Dict[str, Any] = field(default_factory=dict)
    gather: Dict[str, Any] = field(default_factory=dict)
    events: Dict[str, Any] = field(default_factory=dict)
    gifts: Dict[str, Any] = field(default_factory=dict)
    routines: Optional[List[str]] = None
    state_file: Optional[str] = None
    dry_run: Optional[bool] = None


@dataclass
class BotConfig:
    """Top-level configuration."""

    device: DeviceConfig = field(default_factory=DeviceConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    gather: GatherConfig = field(default_factory=GatherConfig)
    events: EventsConfig = field(default_factory=EventsConfig)
    gifts: GiftsConfig = field(default_factory=GiftsConfig)
    accounts: List[AccountConfig] = field(default_factory=list)
    routines: List[str] = field(
        default_factory=lambda: ["daily", "gather", "build", "gifts", "events"]
    )
    state_file: str = "state.json"
    loop_interval_seconds: int = 300  # between full cycles in watch mode
    dry_run: bool = False  # observe + log, never tap


def _apply_env_overrides(cfg: BotConfig) -> None:
    """Let environment variables override sensitive config values."""
    env = os.environ
    if env.get("KSB_DEVICE_MODE"):
        cfg.device.mode = env["KSB_DEVICE_MODE"].strip().lower()
    if env.get("KSB_ADB_SERIAL"):
        cfg.device.serial = env["KSB_ADB_SERIAL"].strip()
    if env.get("KSB_STATE_FILE"):
        cfg.state_file = env["KSB_STATE_FILE"].strip()
    if env.get("KSB_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}:
        cfg.dry_run = True
    if env.get("KSB_LLM_ENABLED", "").strip().lower() in {"1", "true", "yes"}:
        cfg.llm.enabled = True


def _build_section(section: Any, data: Dict[str, Any], name: str) -> None:
    """Copy known keys from ``data`` onto a dataclass instance."""
    if not isinstance(data, dict):
        return
    valid = {f for f in section.__dataclass_fields__}  # type: ignore[attr-defined]
    for key, value in data.items():
        if key in valid:
            setattr(section, key, value)
        else:
            log.warning("config: unknown key %r in section '%s' - ignored", key, name)


def _build_accounts(data: Any) -> List[AccountConfig]:
    """Parse and validate the top-level ``accounts`` list."""
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError("config.accounts must be a YAML list")
    valid = set(AccountConfig.__dataclass_fields__)
    accounts: List[AccountConfig] = []
    names = set()
    for index, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(f"config.accounts[{index}] must be a mapping")
        name = str(entry.get("name", "")).strip()
        if not name:
            raise ValueError(f"config.accounts[{index}] requires a non-empty name")
        if name in names:
            raise ValueError(f"duplicate account name: {name!r}")
        names.add(name)
        kwargs: Dict[str, Any] = {"name": name}
        for key, value in entry.items():
            if key == "name":
                continue
            if key in valid:
                if key in {
                    "device", "vision", "llm", "notify", "gather", "events", "gifts"
                } and not isinstance(value, dict):
                    raise ValueError(
                        f"config.accounts[{index}].{key} must be a mapping"
                    )
                if key == "routines" and value is not None and not isinstance(value, list):
                    raise ValueError(
                        f"config.accounts[{index}].routines must be a list"
                    )
                kwargs[key] = value
            else:
                log.warning(
                    "config: unknown key %r in account %r - ignored", key, name
                )
        accounts.append(AccountConfig(**kwargs))
    return accounts


def load_config(path: str | Path | None = None) -> BotConfig:
    """Load ``BotConfig`` from YAML (if given) plus env overrides.

    Missing files / empty config are fine: defaults are used.
    """
    cfg = BotConfig()
    if path is not None:
        path = Path(path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
            if not isinstance(raw, dict):
                raise ValueError(f"Config file {path} must contain a YAML mapping")
            sections = {
                "device": cfg.device,
                "vision": cfg.vision,
                "llm": cfg.llm,
                "notify": cfg.notify,
                "gather": cfg.gather,
                "events": cfg.events,
                "gifts": cfg.gifts,
            }
            for key, value in raw.items():
                if key in sections:
                    _build_section(sections[key], value, key)
                elif key == "accounts":
                    cfg.accounts = _build_accounts(value)
                elif key == "routines":
                    cfg.routines = list(value)
                elif key == "state_file":
                    cfg.state_file = str(value)
                elif key == "loop_interval_seconds":
                    cfg.loop_interval_seconds = int(value)
                elif key == "dry_run":
                    cfg.dry_run = bool(value)
                else:
                    log.warning("config: unknown top-level key %r - ignored", key)
        else:
            log.warning("config file %s not found - using defaults", path)
    _apply_env_overrides(cfg)
    return cfg


def for_account(cfg: BotConfig, name: str) -> BotConfig:
    """Return an independent config with one account's overrides applied.

    Accounts inherit all top-level settings.  A unique state filename is
    generated when the account does not explicitly provide one, preventing
    account histories and gift-code memories from being mixed together.
    """
    configured = {account.name: account for account in cfg.accounts}
    if name not in configured:
        available = ", ".join(sorted(configured)) or "none"
        raise KeyError(f"unknown account {name!r}; configured accounts: {available}")

    account = configured[name]
    merged = copy.deepcopy(cfg)
    merged.accounts = []
    for section_name in (
        "device", "vision", "llm", "notify", "gather", "events", "gifts"
    ):
        overrides = copy.deepcopy(getattr(account, section_name))
        if overrides:
            section = getattr(merged, section_name)
            # Mapping-valued settings such as gather.formations are merged so
            # an account can customize one resource without repeating all four.
            for key, value in list(overrides.items()):
                inherited = getattr(section, key, None)
                if isinstance(inherited, dict) and isinstance(value, dict):
                    combined = copy.deepcopy(inherited)
                    combined.update(value)
                    overrides[key] = combined
            _build_section(
                section,
                overrides,
                f"accounts.{name}.{section_name}",
            )

    if account.routines is not None:
        merged.routines = list(account.routines)
    if account.dry_run is not None:
        merged.dry_run = bool(account.dry_run)
    if account.state_file:
        merged.state_file = str(account.state_file)
    else:
        state = Path(merged.state_file)
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._") or "account"
        suffix = state.suffix or ".json"
        merged.state_file = str(
            state.with_name(f"{state.stem}_{safe_name}{suffix}")
        )
    return merged


def discord_webhook_url(cfg: BotConfig) -> Optional[str]:
    """Read the Discord webhook URL from its environment variable."""
    return os.environ.get(cfg.notify.discord_webhook_env) or None


def llm_api_key(cfg: BotConfig) -> Optional[str]:
    """Read the LLM API key from its environment variable."""
    return os.environ.get(cfg.llm.api_key_env) or None
