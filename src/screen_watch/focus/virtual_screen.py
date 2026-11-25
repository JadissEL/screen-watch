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


def _mss_virtual_screen() -> VirtualScreen | None:
    """Use mss monitors[0] (virtual desktop) when a display is available."""
    try:
        import mss

        ctx = mss.MSS() if hasattr(mss, "MSS") else mss.mss()
        with ctx as sct:
            if not sct.monitors:
                return None
            virtual = sct.monitors[0]
            width = int(virtual["width"])
            height = int(virtual["height"])
            if width <= 0 or height <= 0:
                return None
            return VirtualScreen(
                int(virtual["left"]),
                int(virtual["top"]),
                width,
                height,
            )
    except Exception:
        return None


def virtual_screen_geometry(
    *,
    fallback_width: int = 1920,
    fallback_height: int = 1080,
) -> VirtualScreen:
    """
    Return the full virtual desktop used by the OS for multi-monitor layouts.

    Priority: Windows ``GetSystemMetrics`` → mss virtual monitor → tk fallback size.
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

    mss_vs = _mss_virtual_screen()
    if mss_vs is not None:
        return mss_vs

    return VirtualScreen(0, 0, max(1, fallback_width), max(1, fallback_height))
