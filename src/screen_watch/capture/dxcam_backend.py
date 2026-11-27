"""Optional DXCam backend for Windows (falls back if unavailable)."""

from __future__ import annotations

import logging
import time
from typing import Any

from screen_watch.capture.base import CaptureError, DisplayInfo, FrameStream, RawFrame

logger = logging.getLogger(__name__)


class DxcamFrameStream:
    """
    Continuous DXCam stream via ``camera.start()`` + ``get_latest_frame()``.

    Observation-only. Falls back callers should use SnapshotFrameStream if start fails.
    """

    def __init__(
        self,
        dxcam_mod: Any,
        *,
        display_id: int | None,
        target_fps: float = 30.0,
    ) -> None:
        self._dxcam = dxcam_mod
        self._display_id = display_id
        self._target_fps = max(1.0, min(float(target_fps), 60.0))
        self._camera: Any = None
        self._closed = False
        output_idx = 0 if display_id is None else max(0, int(display_id) - 1)
        self._camera = self._dxcam.create(output_idx=output_idx)
        if self._camera is None:
            raise CaptureError("dxcam.create returned None")
        # Prefer buffered stream; older dxcam builds may lack start()
        start = getattr(self._camera, "start", None)
        if callable(start):
            try:
                start(target_fps=self._target_fps, video_mode=True)
            except TypeError:
                start(target_fps=self._target_fps)
            self._streaming = True
        else:
            self._streaming = False
            logger.info("dxcam camera has no start(); using grab()-style reads")

    @property
    def name(self) -> str:
        mode = "stream" if self._streaming else "grab"
        return f"dxcam:{mode}"

    def read(self) -> RawFrame:
        if self._closed or self._camera is None:
            raise CaptureError("DxcamFrameStream is closed")
        frame = None
        if self._streaming:
            getter = getattr(self._camera, "get_latest_frame", None)
            if callable(getter):
                # get_latest_frame can block indefinitely if the buffer never fills
                # (e.g. after a rapid stop/restart). Bound the wait, then grab().
                import threading

                box: dict[str, Any] = {}
                done = threading.Event()

                def _pull() -> None:
                    try:
                        box["frame"] = getter()
                    except Exception as exc:  # pragma: no cover
                        box["error"] = exc
                    finally:
                        done.set()

                t = threading.Thread(target=_pull, name="dxcam-latest", daemon=True)
                t.start()
                if done.wait(1.5):
                    if "error" in box:
                        raise CaptureError(f"dxcam get_latest_frame failed: {box['error']}")
                    frame = box.get("frame")
        if frame is None:
            frame = self._camera.grab()
        if frame is None:
            raise CaptureError("dxcam stream returned no frame")
        h, w = frame.shape[0], frame.shape[1]
        rgb = frame[:, :, ::-1].tobytes()
        return RawFrame(
            width=w,
            height=h,
            rgb=rgb,
            timestamp_ms=time.time() * 1000.0,
            display_id=self._display_id or 1,
            backend="dxcam",
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        cam = self._camera
        self._camera = None
        if cam is None:
            return
        stop = getattr(cam, "stop", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                logger.debug("dxcam stop failed", exc_info=True)
        try:
            del cam
        except Exception:
            pass


class DxcamBackend:
    """High-performance Windows capture via Desktop Duplication (dxcam)."""

    def __init__(self) -> None:
        try:
            import dxcam  # type: ignore
        except ImportError as exc:
            raise CaptureError("dxcam is not installed; pip install screen-watch[windows]") from exc
        self._dxcam = dxcam
        self._camera = None
        self._stream_fps = 30.0

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

    def open_stream(self, display_id: int | None = None) -> FrameStream | None:
        """
        Prefer a buffered DXCam stream. Returns ``None`` so FramePump can fall back
        to SnapshotFrameStream if streaming cannot start.
        """
        try:
            return DxcamFrameStream(
                self._dxcam,
                display_id=display_id,
                target_fps=self._stream_fps,
            )
        except Exception as exc:
            logger.warning("dxcam open_stream failed; snapshot fallback: %s", exc)
            return None
