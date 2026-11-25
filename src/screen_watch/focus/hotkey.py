"""System-wide hotkey listener (Windows first; other OS: no-op with clear error)."""

from __future__ import annotations

import json
import logging
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from screen_watch.config import data_dir

logger = logging.getLogger(__name__)

# Win32 modifiers / virtual keys
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
WM_HOTKEY = 0x0312

_VK_BY_NAME = {
    **{chr(c): c for c in range(ord("A"), ord("Z") + 1)},
    **{str(d): 0x30 + d for d in range(10)},
    "F1": 0x70,
    "F2": 0x71,
    "F3": 0x72,
    "F4": 0x73,
    "F5": 0x74,
    "F6": 0x75,
    "F7": 0x76,
    "F8": 0x77,
    "F9": 0x78,
    "F10": 0x79,
    "F11": 0x7A,
    "F12": 0x7B,
}


@dataclass(frozen=True)
class HotkeySpec:
    """Parsed hotkey like 'ctrl+shift+f'."""

    modifiers: int
    vk: int
    label: str


def parse_hotkey(spec: str) -> HotkeySpec:
    """Parse 'ctrl+shift+f' / 'ctrl+alt+f2' into Win32 modifiers + VK."""
    parts = [p.strip().lower() for p in spec.replace("-", "+").split("+") if p.strip()]
    if not parts:
        raise ValueError("Empty hotkey spec")
    key = parts[-1].upper()
    mods = 0
    for p in parts[:-1]:
        if p in {"ctrl", "control"}:
            mods |= MOD_CONTROL
        elif p == "shift":
            mods |= MOD_SHIFT
        elif p == "alt":
            mods |= MOD_ALT
        elif p in {"win", "meta", "cmd"}:
            mods |= MOD_WIN
        else:
            raise ValueError(f"Unknown modifier {p!r}")
    if key not in _VK_BY_NAME:
        raise ValueError(f"Unknown key {key!r}")
    return HotkeySpec(modifiers=mods, vk=_VK_BY_NAME[key], label=spec)


def latest_focus_dir() -> Path:
    path = data_dir() / "latest_focus"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_focus_artifacts(gesture: dict, region_jpeg: bytes, full_jpeg: bytes | None = None) -> Path:
    """Persist last focus result for MCP/CLI consumers."""
    out = latest_focus_dir()
    (out / "gesture.json").write_text(json.dumps(gesture, indent=2), encoding="utf-8")
    (out / "region.jpg").write_bytes(region_jpeg)
    if full_jpeg:
        (out / "full.jpg").write_bytes(full_jpeg)
    meta = {"saved_at": time.time(), "has_full": bool(full_jpeg)}
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return out


def load_latest_focus() -> dict | None:
    out = latest_focus_dir()
    gesture_path = out / "gesture.json"
    region_path = out / "region.jpg"
    if not gesture_path.exists() or not region_path.exists():
        return None
    import base64

    gesture = json.loads(gesture_path.read_text(encoding="utf-8"))
    region = region_path.read_bytes()
    full_path = out / "full.jpg"
    full = full_path.read_bytes() if full_path.exists() else None
    meta = {}
    if (out / "meta.json").exists():
        meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    return {
        "gesture": gesture,
        "region_b64": base64.b64encode(region).decode("ascii"),
        "full_b64": base64.b64encode(full).decode("ascii") if full else None,
        "dir": str(out),
        "meta": meta,
    }


def _to_pynput_combo(spec: HotkeySpec) -> str:
    """Build a pynput GlobalHotKeys combo string from HotkeySpec."""
    parts: list[str] = []
    if spec.modifiers & MOD_CONTROL:
        parts.append("<ctrl>")
    if spec.modifiers & MOD_SHIFT:
        parts.append("<shift>")
    if spec.modifiers & MOD_ALT:
        parts.append("<alt>")
    if spec.modifiers & MOD_WIN:
        parts.append("<cmd>")
    # Map VK back to key name
    key_name = None
    for name, vk in _VK_BY_NAME.items():
        if vk == spec.vk:
            key_name = name.lower()
            break
    if key_name is None:
        raise ValueError(f"Cannot map vk={spec.vk} for pynput")
    parts.append(key_name)
    return "+".join(parts)


class HotkeyDaemon:
    """
    Background global hotkey → callback.

    Windows: Win32 RegisterHotKey. Other OS: optional pynput
    (`pip install screen-watch[hotkey]`).
    """

    def __init__(self, spec: HotkeySpec, on_hotkey: Callable[[], None]) -> None:
        self._spec = spec
        self._on_hotkey = on_hotkey
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_error: str | None = None
        self._pynput_listener: Any = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def label(self) -> str:
        return self._spec.label

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        if sys.platform == "win32":
            target = self._run_win32
        else:
            target = self._run_pynput
        self._thread = threading.Thread(target=target, name="screen-watch-hotkey", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        listener = self._pynput_listener
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._thread = None
        self._pynput_listener = None

    def _run_win32(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hotkey_id = 1
        if not user32.RegisterHotKey(None, hotkey_id, self._spec.modifiers, self._spec.vk):
            self._last_error = f"RegisterHotKey failed for {self._spec.label}"
            logger.error(self._last_error)
            return
        logger.info("Hotkey registered (Win32): %s", self._spec.label)
        msg = wintypes.MSG()
        try:
            while not self._stop.is_set():
                has = user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1)
                if has:
                    if msg.message == WM_HOTKEY and msg.wParam == hotkey_id:
                        try:
                            self._on_hotkey()
                        except Exception:
                            logger.exception("Hotkey callback failed")
                    else:
                        user32.TranslateMessage(ctypes.byref(msg))
                        user32.DispatchMessageW(ctypes.byref(msg))
                else:
                    time.sleep(0.05)
        finally:
            user32.UnregisterHotKey(None, hotkey_id)
            logger.info("Hotkey unregistered: %s", self._spec.label)

    def _run_pynput(self) -> None:
        try:
            from pynput import keyboard
        except ImportError:
            self._last_error = (
                "Global hotkeys on this OS need pynput. "
                "Install with: pip install 'screen-watch[hotkey]'"
            )
            logger.error(self._last_error)
            return
        combo = _to_pynput_combo(self._spec)

        def _fire() -> None:
            try:
                self._on_hotkey()
            except Exception:
                logger.exception("Hotkey callback failed")

        try:
            listener = keyboard.GlobalHotKeys({combo: _fire})
        except Exception as exc:
            self._last_error = f"Failed to bind {combo}: {exc}"
            logger.error(self._last_error)
            return
        self._pynput_listener = listener
        logger.info("Hotkey registered (pynput): %s → %s", self._spec.label, combo)
        listener.start()
        try:
            while not self._stop.is_set():
                time.sleep(0.2)
        finally:
            listener.stop()
            logger.info("Hotkey unregistered: %s", self._spec.label)
