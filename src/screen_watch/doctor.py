"""Environment / capability report for screen-watch."""

from __future__ import annotations

import importlib.util
import platform
import shutil
import sys
from typing import Any

from screen_watch import __version__
from screen_watch.capture.factory import create_backend
from screen_watch.config import load_settings
from screen_watch.privacy import privacy_blurb


def run_doctor() -> dict[str, Any]:
    """Collect install, backend, and optional-feature status (never fails hard)."""
    settings = load_settings()
    backend_info: dict[str, Any] = {"ok": False}
    try:
        backend = create_backend(settings)
        displays = backend.list_displays()
        backend_info = {
            "ok": True,
            "name": backend.name,
            "displays": len(displays),
            "display_ids": [d.id for d in displays],
        }
    except Exception as exc:
        backend_info = {"ok": False, "error": str(exc)}

    return {
        "version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "settings": {
            "max_width": settings.max_width,
            "max_height": settings.max_height,
            "fps": settings.capped_fps(),
            "jpeg_quality": settings.jpeg_quality,
            "backend": settings.backend,
            "focus_hotkey": settings.focus_hotkey,
            "recording_enabled": settings.recording_enabled,
        },
        "backend": backend_info,
        "tools": {
            "grim": bool(shutil.which("grim")),
            "gdbus": bool(shutil.which("gdbus")),
            "screencapture": bool(shutil.which("screencapture")),
            "dxcam": importlib.util.find_spec("dxcam") is not None,
            "pynput": importlib.util.find_spec("pynput") is not None,
            "quartz": importlib.util.find_spec("Quartz") is not None,
            "mss": importlib.util.find_spec("mss") is not None,
            "mcp": importlib.util.find_spec("mcp") is not None,
        },
        "privacy": privacy_blurb(),
    }
