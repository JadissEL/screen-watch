"""Application service wiring capture, store, daemon, and one-shot grabs."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from screen_watch.capture.base import RawFrame
from screen_watch.capture.factory import create_backend
from screen_watch.config import Settings, load_settings
from screen_watch.daemon.watcher import WatchDaemon
from screen_watch.focus.region import BBox, crop_rgb
from screen_watch.pipeline.blur import pixelate_rgb
from screen_watch.pipeline.downsample import downsample_rgb
from screen_watch.pipeline.encode import encode_jpeg
from screen_watch.pipeline.frame_store import EncodedFrame, FrameStore
from screen_watch.pipeline.process import process_raw_frame
from screen_watch.rate_limit import MinIntervalGate

logger = logging.getLogger(__name__)


@dataclass
class ScreenWatchService:
    """Process-wide service used by MCP tools and CLI."""

    settings: Settings
    store: FrameStore
    daemon: WatchDaemon
    backend_name: str

    _thumb: Any = None
    _grab_lock: threading.Lock = field(default_factory=threading.Lock)
    _gate: MinIntervalGate = field(default_factory=MinIntervalGate)

    @classmethod
    def create(cls, settings: Settings | None = None) -> ScreenWatchService:
        cfg = settings or load_settings()
        backend = create_backend(cfg)
        store = FrameStore()
        daemon = WatchDaemon(backend, store, cfg)
        return cls(
            settings=cfg,
            store=store,
            daemon=daemon,
            backend_name=backend.name,
            _gate=MinIntervalGate(cfg.min_capture_interval_s),
        )
    def list_displays(self) -> list[dict[str, Any]]:
        backend = create_backend(self.settings)
        return [
            {
                "id": d.id,
                "name": d.name,
                "width": d.width,
                "height": d.height,
                "left": d.left,
                "top": d.top,
                "is_primary": d.is_primary,
            }
            for d in backend.list_displays()
        ]

    def capture_once(self, *, blur: bool | None = None) -> EncodedFrame:
        """One-shot grab through the pipeline (ignores unchanged short-circuit for callers that need bytes)."""
        self._gate.wait()
        with self._grab_lock:
            backend = create_backend(self.settings)
            raw = backend.grab(self.settings.display)
            encoded, self._thumb = process_raw_frame(
                raw,
                self.settings,
                previous_thumb=None,
                force_blur=blur,
                skip_change_detect=True,
            )
            self.store.set(encoded)
            return encoded

    def latest_for_agent(self, *, blur: bool | None = None) -> EncodedFrame:
        """
        Prefer daemon store; otherwise one-shot.

        If blur override differs from stored frame, re-capture once.
        """
        if self.daemon.running:
            frame = self.store.get()
            if frame is None:
                return self.capture_once(blur=blur)
            want_blur = self.settings.blur if blur is None else blur
            if frame.blur != want_blur:
                return self.capture_once(blur=want_blur)
            return frame
        return self.capture_once(blur=blur)

    def capture_region(
        self,
        box: BBox,
        *,
        blur: bool | None = None,
        also_full_frame: bool = True,
    ) -> dict[str, Any]:
        """
        Grab desktop, return gesture bbox + optional full frame + cropped JPEG.

        Coordinates are screen pixels (same space as the focus overlay).
        Uses virtual-desktop capture so multi-monitor gestures map correctly.
        """
        self._gate.wait()
        with self._grab_lock:
            backend = create_backend(self.settings)
            grab_virtual = getattr(backend, "grab_virtual", None)
            raw = grab_virtual() if callable(grab_virtual) else backend.grab(self.settings.display)
            # Map screen coords → frame-local coords
            local = BBox(
                box.x - raw.origin_left,
                box.y - raw.origin_top,
                box.width,
                box.height,
            )
            apply_blur = self.settings.blur if blur is None else blur

            full = self._encode_raw(raw, force_blur=apply_blur) if also_full_frame else None
            cropped_rgb, cw, ch = crop_rgb(raw.rgb, raw.width, raw.height, local)
            if apply_blur:
                cropped_rgb = pixelate_rgb(cropped_rgb, cw, ch, self.settings.blur_block)
            # Fit crop into settings box
            tmp = RawFrame(cw, ch, cropped_rgb, raw.timestamp_ms, raw.display_id, raw.backend)
            crop_rgb_ds, dw, dh = downsample_rgb(tmp, self.settings.max_width, self.settings.max_height)
            crop_jpeg = encode_jpeg(crop_rgb_ds, dw, dh, self.settings.jpeg_quality)

            return {
                "gesture": {
                    "x": box.x,
                    "y": box.y,
                    "width": box.width,
                    "height": box.height,
                },
                "full_frame": full,
                "region_jpeg": crop_jpeg,
                "region_width": dw,
                "region_height": dh,
                "note": (
                    "Agent should snap the loose gesture to the nearest UI element "
                    "(button/card/window). screen-watch does not run a11y snap."
                ),
            }

    def _encode_raw(self, raw: RawFrame, *, force_blur: bool) -> EncodedFrame:
        encoded, self._thumb = process_raw_frame(
            raw,
            self.settings,
            previous_thumb=None,
            force_blur=force_blur,
            skip_change_detect=True,
        )
        self.store.set(encoded)
        return encoded

    def save_frame_to(
        self,
        path: Path,
        *,
        blur: bool | None = None,
        force_capture: bool = False,
    ) -> dict[str, Any]:
        """Write latest (or freshly captured) JPEG to ``path``; return metadata."""
        out = Path(path)
        frame = self.capture_once(blur=blur) if force_capture else self.latest_for_agent(blur=blur)
        if not frame.jpeg:
            frame = self.capture_once(blur=blur)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(frame.jpeg)
        return {
            "ok": True,
            "path": str(out.resolve()),
            "width": frame.width,
            "height": frame.height,
            "bytes": len(frame.jpeg),
            "content_hash": frame.content_hash,
            "blur": frame.blur,
            "backend": frame.backend,
            "timestamp_ms": frame.timestamp_ms,
        }

    def status(self) -> dict[str, Any]:
        frame = self.store.get()
        return {
            "backend": self.backend_name,
            "watch_running": self.daemon.running,
            "fps": self.settings.capped_fps(),
            "max_width": self.settings.max_width,
            "max_height": self.settings.max_height,
            "jpeg_quality": self.settings.jpeg_quality,
            "blur_default": self.settings.blur,
            "min_capture_interval_s": self.settings.min_capture_interval_s,
            "recording_enabled": self.settings.recording_enabled,
            "last_error": self.daemon.last_error,
            "frame": None
            if frame is None
            else {
                "width": frame.width,
                "height": frame.height,
                "timestamp_ms": frame.timestamp_ms,
                "content_hash": frame.content_hash,
                "unchanged": frame.unchanged,
                "blur": frame.blur,
                "age_ms": self.store.age_ms(),
            },
        }


_SERVICE: ScreenWatchService | None = None


def get_service() -> ScreenWatchService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = ScreenWatchService.create()
    return _SERVICE


def reset_service() -> None:
    """Test helper to clear the singleton."""
    global _SERVICE
    if _SERVICE is not None and _SERVICE.daemon.running:
        _SERVICE.daemon.stop()
    _SERVICE = None
