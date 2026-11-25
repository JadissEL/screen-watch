"""Virtual screen geometry helper."""

from __future__ import annotations

import sys

from screen_watch.focus.virtual_screen import VirtualScreen, virtual_screen_geometry


def test_geometry_nonzero() -> None:
    vs = virtual_screen_geometry(fallback_width=800, fallback_height=600)
    assert isinstance(vs, VirtualScreen)
    assert vs.width >= 1 and vs.height >= 1
    # On machines with a display, mss/Win metrics may exceed the tk fallback.
    if sys.platform != "win32" and vs.left == 0 and vs.top == 0 and vs.width == 800:
        assert vs.height == 600


def test_virtual_screen_edges() -> None:
    vs = VirtualScreen(-100, 0, 2000, 1080)
    assert vs.right == 1900
    assert vs.bottom == 1080
