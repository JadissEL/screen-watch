"""Virtual-desktop coordinate mapping for guided focus."""

from __future__ import annotations

from screen_watch.capture.base import RawFrame
from screen_watch.focus.region import BBox, crop_rgb


def test_screen_to_frame_local_crop() -> None:
    # Simulate virtual desktop origin at (-100, 0) — secondary monitor left of primary
    w, h = 200, 100
    rgb = bytes([10, 20, 30] * (w * h))
    raw = RawFrame(w, h, rgb, 0.0, 0, "test", origin_left=-100, origin_top=0)
    screen_box = BBox(x=-50, y=10, width=40, height=20)
    local = BBox(
        screen_box.x - raw.origin_left,
        screen_box.y - raw.origin_top,
        screen_box.width,
        screen_box.height,
    )
    assert local == BBox(50, 10, 40, 20)
    out, cw, ch = crop_rgb(raw.rgb, raw.width, raw.height, local)
    assert cw == 40 and ch == 20
    assert len(out) == 40 * 20 * 3
