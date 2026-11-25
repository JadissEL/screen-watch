"""Guided region focus — loose user gesture + frame for agent vision snap."""

from __future__ import annotations

from screen_watch.focus.hotkey import HotkeyDaemon, load_latest_focus, parse_hotkey
from screen_watch.focus.overlay import RegionGesture, select_region_interactive
from screen_watch.focus.region import crop_rgb, normalize_bbox

__all__ = [
    "HotkeyDaemon",
    "RegionGesture",
    "crop_rgb",
    "load_latest_focus",
    "normalize_bbox",
    "parse_hotkey",
    "select_region_interactive",
]
