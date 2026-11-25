"""macOS capture: Quartz (optional pyobjc) → screencapture → mss."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from screen_watch.capture.base import CaptureError, DisplayInfo, RawFrame
from screen_watch.capture.mss_backend import MssBackend

logger = logging.getLogger(__name__)


def _try_quartz_frame() -> RawFrame | None:
    """Grab main display via Quartz if pyobjc is installed."""
    try:
        import Quartz  # type: ignore
        from PIL import Image
    except ImportError:
        return None

    try:
        display_id = Quartz.CGMainDisplayID()
        image_ref = Quartz.CGDisplayCreateImage(display_id)
        if image_ref is None:
            return None
        width = Quartz.CGImageGetWidth(image_ref)
        height = Quartz.CGImageGetHeight(image_ref)
        # Render via temporary PNG using Quartz / fallback to screencapture if complex
        # Use bitmap context for RGB
        bytes_per_row = Quartz.CGImageGetBytesPerRow(image_ref)
        data_provider = Quartz.CGImageGetDataProvider(image_ref)
        data = Quartz.CGDataProviderCopyData(data_provider)
        # BGRA buffer from Quartz
        raw = bytes(data)
        img = Image.frombuffer("RGBA", (width, height), raw, "raw", "BGRA", bytes_per_row, 1)
        rgb = img.convert("RGB")
        return RawFrame(
            width=rgb.width,
            height=rgb.height,
            rgb=rgb.tobytes(),
            timestamp_ms=time.time() * 1000.0,
            display_id=0,
            backend="quartz",
            origin_left=0,
            origin_top=0,
        )
    except Exception:
        logger.debug("Quartz grab failed", exc_info=True)
        return None


class ScreenCaptureKitBackend:
    """
    macOS backend priority:

    1. Quartz via optional ``pyobjc-framework-Quartz`` (``screen-watch[macos]``)
    2. System ``screencapture`` binary (Screen Recording permission)
    3. ``mss``
    """

    def __init__(self) -> None:
        if sys.platform != "darwin":
            raise CaptureError("ScreenCaptureKit/macOS backend is only available on macOS")
        self._bin = shutil.which("screencapture")
        self._mss: MssBackend | None = None
        self._mode = "mss"

        if _quartz_importable():
            self._mode = "quartz"
            logger.info("macOS capture using Quartz (pyobjc)")
        elif self._bin:
            self._mode = "screencapture"
            logger.info("macOS capture using screencapture (%s)", self._bin)
        else:
            self._mode = "mss"
            logger.info("macOS capture using mss fallback")
            self._mss = MssBackend()

    @property
    def name(self) -> str:
        return {
            "quartz": "quartz",
            "screencapture": "screencapture",
            "mss": "sck-mss-fallback",
        }[self._mode]

    def list_displays(self) -> list[DisplayInfo]:
        if self._mss is not None:
            return self._mss.list_displays()
        return [DisplayInfo(id=1, width=1920, height=1080, is_primary=True, name=f"macOS ({self._mode})")]

    def grab(self, display_id: int | None = None) -> RawFrame:
        return self._grab()

    def grab_virtual(self) -> RawFrame:
        return self._grab()

    def _grab(self) -> RawFrame:
        if self._mode == "quartz":
            frame = _try_quartz_frame()
            if frame is not None:
                return frame
            logger.warning("Quartz grab failed; falling back to screencapture/mss")
            if self._bin:
                return self._grab_screencapture()
            self._mss = self._mss or MssBackend()
            return self._mss.grab_virtual()
        if self._mode == "screencapture":
            return self._grab_screencapture()
        assert self._mss is not None
        return self._mss.grab_virtual()

    def _grab_screencapture(self) -> RawFrame:
        assert self._bin
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "shot.png"
            try:
                subprocess.run(
                    [self._bin, "-x", str(out)],
                    check=True,
                    capture_output=True,
                    timeout=15,
                )
            except Exception as exc:
                raise CaptureError(
                    f"screencapture failed: {exc}. "
                    "Grant Screen Recording permission to the terminal/Python in System Settings."
                ) from exc
            if not out.exists():
                raise CaptureError("screencapture produced no file")
            img = Image.open(out).convert("RGB")
            return RawFrame(
                width=img.width,
                height=img.height,
                rgb=img.tobytes(),
                timestamp_ms=time.time() * 1000.0,
                display_id=0,
                backend=self.name,
                origin_left=0,
                origin_top=0,
            )


def _quartz_importable() -> bool:
    try:
        import Quartz  # noqa: F401

        return True
    except ImportError:
        return False
