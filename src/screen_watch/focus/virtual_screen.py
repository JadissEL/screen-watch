"""Virtual-desktop geometry for multi-monitor overlays."""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class VirtualScreen:
    """Desktop bounding box in screen coordinates (may be negative origin)."""

    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


def virtual_screen_geometry(
    *,
    fallback_width: int = 1920,
    fallback_height: int = 1080,
) -> VirtualScreen:
    """
    Return the full virtual desktop used by the OS for multi-monitor layouts.

    On Windows uses ``GetSystemMetrics`` virtual-screen values. Elsewhere falls
    back to the provided size at origin (0, 0) — callers typically pass tk
    ``winfo_screenwidth/height``.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            user32 = ctypes.windll.user32
            # SM_XVIRTUALSCREEN / Y / CX / CY
            left = int(user32.GetSystemMetrics(76))
            top = int(user32.GetSystemMetrics(77))
            width = int(user32.GetSystemMetrics(78))
            height = int(user32.GetSystemMetrics(79))
            if width > 0 and height > 0:
                return VirtualScreen(left, top, width, height)
        except Exception:
            pass
    return VirtualScreen(0, 0, max(1, fallback_width), max(1, fallback_height))
