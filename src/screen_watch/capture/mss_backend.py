"""mss-based capture — pure Python, works on Windows / macOS / Linux."""

from __future__ import annotations

import logging
import time
from typing import Any

from PIL import Image

from screen_watch.capture.base import CaptureError, DisplayInfo, RawFrame

logger = logging.getLogger(__name__)


class MssBackend:
    """Capture via the `mss` library (BGRA → RGB via Pillow)."""

    def __init__(self) -> None:
        try:
            import mss  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise CaptureError("mss is required; pip install mss") from exc
        self._mss_mod = __import__("mss")

    @property
    def name(self) -> str:
        return "mss"

    def list_displays(self) -> list[DisplayInfo]:
        with self._mss_ctx() as sct:
            displays: list[DisplayInfo] = []
            for idx, mon in enumerate(sct.monitors[1:], start=1):
                displays.append(
                    DisplayInfo(
                        id=idx,
                        width=int(mon["width"]),
                        height=int(mon["height"]),
                        left=int(mon["left"]),
                        top=int(mon["top"]),
                        is_primary=(idx == 1),
                        name=f"Monitor {idx}",
                    )
                )
            return displays

    def _mss_ctx(self) -> Any:
        """Prefer mss.MSS(); fall back to deprecated mss.mss()."""
        if hasattr(self._mss_mod, "MSS"):
            return self._mss_mod.MSS()
        return self._mss_mod.mss()

    def grab(self, display_id: int | None = None) -> RawFrame:
        try:
            with self._mss_ctx() as sct:
                monitors = sct.monitors
                if len(monitors) < 2:
                    raise CaptureError("No monitors detected")
                idx = 1 if display_id is None else int(display_id)
                if idx < 1 or idx >= len(monitors):
                    raise CaptureError(f"Invalid display_id={idx}; valid 1..{len(monitors) - 1}")
                return self._shot_to_frame(sct.grab(monitors[idx]), display_id=idx, mon=monitors[idx])
        except CaptureError:
            raise
        except Exception as exc:  # pragma: no cover
            logger.exception("mss grab failed")
            raise CaptureError(f"mss grab failed: {exc}") from exc

    def grab_virtual(self) -> RawFrame:
        """Capture monitors[0] — the virtual desktop spanning all displays."""
        try:
            with self._mss_ctx() as sct:
                if not sct.monitors:
                    raise CaptureError("No monitors detected")
                virtual = sct.monitors[0]
                return self._shot_to_frame(sct.grab(virtual), display_id=0, mon=virtual)
        except CaptureError:
            raise
        except Exception as exc:  # pragma: no cover
            logger.exception("mss grab_virtual failed")
            raise CaptureError(f"mss grab_virtual failed: {exc}") from exc

    def _shot_to_frame(self, shot: Any, *, display_id: int, mon: dict) -> RawFrame:
        w, h = shot.width, shot.height
        img = Image.frombytes("RGB", (w, h), shot.bgra, "raw", "BGRX")
        return RawFrame(
            width=w,
            height=h,
            rgb=img.tobytes(),
            timestamp_ms=time.time() * 1000.0,
            display_id=display_id,
            backend=self.name,
            origin_left=int(mon.get("left", 0)),
            origin_top=int(mon.get("top", 0)),
        )
