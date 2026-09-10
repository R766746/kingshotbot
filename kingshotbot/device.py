"""Device layer: a common interface over ADB devices and the mock simulator.

The agent talks to the game exclusively through a :class:`Device`:
screenshots in, taps/swipes out. Two implementations are provided:

* :class:`ADBDevice` - drives a real Android device or emulator
  (BlueStacks / LDPlayer / MuMu / Google Play Games on PC ...) over ADB.
* :class:`MockDevice` (``mock_device.py``) - a tiny in-process Kingshot
  simulator used for dry-runs, demos and the test-suite.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from typing import Optional, Protocol

import cv2
import numpy as np

log = logging.getLogger("kingshotbot.device")

# Android keycodes used by the agent.
KEY_BACK = 4
KEY_HOME = 3
KEY_APP_SWITCH = 187


class DeviceError(RuntimeError):
    """Raised when talking to the device fails."""


class Device(Protocol):
    """Minimal interface the agent needs from a device."""

    name: str

    def screenshot(self) -> np.ndarray:  # BGR image
        ...

    def tap(self, x: int, y: int) -> None: ...

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None: ...

    def key(self, keycode: int) -> None: ...

    def is_alive(self) -> bool: ...


class ADBDevice:
    """Controls a real device/emulator through the ``adb`` binary."""

    def __init__(
        self,
        serial: Optional[str] = None,
        adb_path: str = "adb",
        connect_timeout: float = 10.0,
    ) -> None:
        self.name = f"adb:{serial or 'auto'}"
        self.serial = serial
        self.adb_path = adb_path
        self.connect_timeout = connect_timeout
        if shutil.which(adb_path) is None:
            raise DeviceError(
                f"adb binary not found at '{adb_path}'. Install platform-tools "
                "and ensure adb is on your PATH, or set device.adb_path in config."
            )

    # ------------------------------------------------------------------ #
    # low-level helpers
    # ------------------------------------------------------------------ #
    def _adb(
        self,
        *args: str,
        binary_output: bool = False,
        timeout: Optional[float] = None,
    ) -> bytes:
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += list(args)
        log.debug("adb %s", " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout or self.connect_timeout,
            )
        except FileNotFoundError as exc:  # pragma: no cover - covered by ctor
            raise DeviceError(f"adb not found: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise DeviceError(f"adb command timed out: {' '.join(cmd)}") from exc
        if proc.returncode != 0:
            stderr = proc.stderr.decode(errors="replace").strip()
            raise DeviceError(f"adb failed ({proc.returncode}): {stderr}")
        return proc.stdout if binary_output else proc.stdout

    def connect(self) -> bool:
        """Start the ADB server and verify the target device is visible."""
        try:
            subprocess.run(
                [self.adb_path, "start-server"],
                capture_output=True,
                timeout=self.connect_timeout,
            )
            # Network emulator serials are not always registered with a fresh
            # ADB server (notably inside Docker), so connect them explicitly.
            if self.serial and ":" in self.serial:
                connected = subprocess.run(
                    [self.adb_path, "connect", self.serial],
                    capture_output=True,
                    timeout=self.connect_timeout,
                )
                log.debug(
                    "adb connect %s: %s",
                    self.serial,
                    connected.stdout.decode(errors="replace").strip(),
                )
            out = subprocess.run(
                [self.adb_path, "devices"],
                capture_output=True,
                timeout=self.connect_timeout,
            ).stdout.decode(errors="replace")
        except (subprocess.SubprocessError, OSError) as exc:
            raise DeviceError(f"could not run adb: {exc}") from exc
        devices = [
            line.split("\t")[0]
            for line in out.splitlines()[1:]
            if "\tdevice" in line
        ]
        if not devices:
            log.error("no ADB devices online. Start your emulator first.\n%s", out)
            return False
        if self.serial and self.serial not in devices:
            log.error(
                "device %s not online. Online devices: %s", self.serial, devices
            )
            return False
        if not self.serial:
            self.serial = devices[0]
            self.name = f"adb:{self.serial}"
        log.info("connected to device %s", self.serial)
        return True

    # ------------------------------------------------------------------ #
    # Device protocol implementation
    # ------------------------------------------------------------------ #
    def screenshot(self) -> np.ndarray:
        """Capture the screen as a BGR numpy image."""
        raw = self._adb("exec-out", "screencap", "-p", binary_output=True)
        img = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            # Fallback for old adb builds that mangle binary output (CRLF).
            fixed = raw.replace(b"\r\n", b"\n")
            img = cv2.imdecode(np.frombuffer(fixed, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise DeviceError("failed to decode screenshot (screencap returned no PNG)")
        return img

    def tap(self, x: int, y: int) -> None:
        self._adb("shell", "input", "tap", str(int(x)), str(int(y)))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self._adb(
            "shell", "input", "swipe",
            str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)),
            str(int(duration_ms)),
        )

    def key(self, keycode: int) -> None:
        self._adb("shell", "input", "keyevent", str(int(keycode)))

    def is_alive(self) -> bool:
        try:
            out = subprocess.run(
                [self.adb_path, "devices"], capture_output=True, timeout=5
            ).stdout.decode(errors="replace")
            return f"{self.serial}\tdevice" in out if self.serial else "\tdevice" in out
        except (subprocess.SubprocessError, OSError):
            return False


def open_app(dev: ADBDevice, package: str, activity: Optional[str] = None) -> None:
    """Launch the game (``monkey`` works without knowing the activity)."""
    if activity:
        dev._adb("shell", "am", "start", "-n", f"{package}/{activity}")
    else:
        dev._adb(
            "shell", "monkey", "-p", package,
            "-c", "android.intent.category.LAUNCHER", "1",
        )


def sleep_noop(_: float) -> None:  # pragma: no cover - trivial
    """Injectable no-op sleep for tests."""


class Sleeper:
    """Time-based sleep helper the agent uses between actions.

    Tests replace ``fn`` with a no-op to run instantly.
    """

    def __init__(self, fn=time.sleep) -> None:
        self.fn = fn

    def __call__(self, seconds: float) -> None:
        if seconds > 0:
            self.fn(seconds)
