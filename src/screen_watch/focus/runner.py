"""Shared focus capture → save artifacts pipeline."""

from __future__ import annotations

import logging
from typing import Any

from screen_watch.focus.hotkey import save_focus_artifacts
from screen_watch.focus.overlay import select_region_interactive
from screen_watch.service import ScreenWatchService, get_service

logger = logging.getLogger(__name__)


def run_guided_focus(
    *,
    blur: bool | None = None,
    service: ScreenWatchService | None = None,
) -> dict[str, Any]:
    """Open overlay, capture region + full frame, persist under data_dir/latest_focus."""
    gesture = select_region_interactive()
    if gesture.cancelled:
        return {"ok": False, "cancelled": True}
    svc = service or get_service()
    result = svc.capture_region(gesture.bbox, blur=blur, also_full_frame=True)
    full = result["full_frame"]
    out_dir = save_focus_artifacts(
        result["gesture"],
        result["region_jpeg"],
        full.jpeg if full is not None else None,
    )
    logger.info("Focus saved to %s", out_dir)
    return {
        "ok": True,
        "cancelled": False,
        "gesture": result["gesture"],
        "dir": str(out_dir),
        "region_width": result["region_width"],
        "region_height": result["region_height"],
        "note": result["note"],
    }
