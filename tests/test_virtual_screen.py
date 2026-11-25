"""Virtual screen geometry helper."""

from __future__ import annotations

import sys

from screen_watch.focus.virtual_screen import VirtualScreen, virtual_screen_geometry


def test_fallback_geometry() -> None:
    if sys.platform == "win32":
        vs = virtual_screen_geometry(fallback_width=800, fallback_height=600)
        assert vs.width >= 1 and vs.height >= 1
        assert isinstance(vs, VirtualScreen)
    else:
        vs = virtual_screen_geometry(fallback_width=800, fallback_height=600)
        assert vs == VirtualScreen(0, 0, 800, 600)


def test_virtual_screen_edges() -> None:
    vs = VirtualScreen(-100, 0, 2000, 1080)
    assert vs.right == 1900
    assert vs.bottom == 1080
