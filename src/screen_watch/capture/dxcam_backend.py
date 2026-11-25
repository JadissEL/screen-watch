"""Optional DXCam backend for Windows (falls back if unavailable)."""

from __future__ import annotations

import logging
import time

from screen_watch.capture.base import CaptureError, DisplayInfo, RawFrame

logger = logging.getLogger(__name__)


class DxcamBackend:
    """High-performance Windows capture via Desktop Duplication (dxcam)."""

    def __init__(self) -> None:
        try:
            import dxcam  # type: ignore
        except ImportError as exc:
            raise CaptureError("dxcam is not installed; pip install screen-watch[windows]") from exc
        self._dxcam = dxcam
        self._camera = None

    @property
    def name(self) -> str:
        return "dxcam"

    def list_displays(self) -> list[DisplayInfo]:
        # dxcam exposes output metadata via device enumeration; keep simple for v1
        try:
            cam = self._dxcam.create()
            # Single primary for listing; mss remains authoritative for multi-monitor IDs
            h, w = 1080, 1920
            if cam is not None:
                frame = cam.grab()
                if frame is not None:
                    h, w = frame.shape[0], frame.shape[1]
                del cam
            return [DisplayInfo(id=1, width=w, height=h, is_primary=True, name="Primary (dxcam)")]
        except Exception as exc:  # pragma: no cover
            raise CaptureError(f"dxcam list_displays failed: {exc}") from exc

    def grab(self, display_id: int | None = None) -> RawFrame:
        try:
            output_idx = 0 if display_id is None else max(0, int(display_id) - 1)
            if self._camera is None:
                self._camera = self._dxcam.create(output_idx=output_idx)
            frame = self._camera.grab()
            if frame is None:
                raise CaptureError("dxcam returned no frame")
            # dxcam returns BGR ndarray
            h, w = frame.shape[0], frame.shape[1]
            # BGR → RGB
            rgb = frame[:, :, ::-1].tobytes()
            return RawFrame(
                width=w,
                height=h,
                rgb=rgb,
                timestamp_ms=time.time() * 1000.0,
                display_id=display_id or 1,
                backend=self.name,
            )
        except CaptureError:
            raise
        except Exception as exc:
            logger.exception("dxcam grab failed")
            raise CaptureError(f"dxcam grab failed: {exc}") from exc

    def grab_virtual(self) -> RawFrame:
        """DXCam is per-output; fall back to primary for v1."""
        return self.grab(None)
