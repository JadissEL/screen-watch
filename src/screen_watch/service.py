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
from screen_watch.pipeline.change_detect import change_bbox
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
    _prev_change_jpeg: bytes | None = None
    _grab_lock: threading.Lock = field(default_factory=threading.Lock)
    _gate: MinIntervalGate = field(default_factory=MinIntervalGate)

    @classmethod
    def create(cls, settings: Settings | None = None) -> ScreenWatchService:
        cfg = settings or load_settings()
        backend = create_backend(cfg)
        store = FrameStore(history_size=cfg.history_size)
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

    def set_display(self, display_id: int | None) -> dict[str, Any]:
        """
        Set the default monitor for watch/one-shot grabs (1-based; None = primary).

        Takes effect on the next grab; the watch daemon reads settings each tick.
        """
        self.settings.display = display_id
        return {
            "ok": True,
            "display": display_id,
            "watch_running": self.daemon.running,
            "status": self.status(),
        }

    def capture_once(
        self,
        *,
        blur: bool | None = None,
        display_id: int | None = None,
    ) -> EncodedFrame:
        """One-shot grab through the pipeline (ignores unchanged short-circuit for callers that need bytes)."""
        self._gate.wait()
        with self._grab_lock:
            backend = create_backend(self.settings)
            target = self.settings.display if display_id is None else display_id
            raw = backend.grab(target)
            encoded, self._thumb = process_raw_frame(
                raw,
                self.settings,
                previous_thumb=None,
                force_blur=blur,
                skip_change_detect=True,
            )
            self.store.set(encoded)
            return encoded

    def bench(self, *, iterations: int = 5, display_id: int | None = None) -> dict[str, Any]:
        """Measure grab+encode latency (local diagnostics; never blocks agents)."""
        import time

        n = max(1, min(int(iterations), 50))
        samples_ms: list[float] = []
        last: EncodedFrame | None = None
        for _ in range(n):
            t0 = time.perf_counter()
            last = self.capture_once(display_id=display_id)
            samples_ms.append((time.perf_counter() - t0) * 1000.0)
        samples_ms.sort()
        return {
            "iterations": n,
            "display_id": display_id if display_id is not None else self.settings.display,
            "backend": last.backend if last else self.backend_name,
            "width": last.width if last else None,
            "height": last.height if last else None,
            "jpeg_bytes": len(last.jpeg) if last else None,
            "ms_min": round(samples_ms[0], 2),
            "ms_median": round(samples_ms[len(samples_ms) // 2], 2),
            "ms_max": round(samples_ms[-1], 2),
            "ms_mean": round(sum(samples_ms) / len(samples_ms), 2),
        }

    def get_change_region(
        self,
        *,
        blur: bool | None = None,
        pixel_threshold: int = 12,
        include_crop: bool = True,
    ) -> dict[str, Any]:
        """
        Compare the previous observed JPEG to the latest frame; return a change bbox.

        Call after ``wait_for_change`` / a poll cycle. First call seeds baseline only.
        Coordinates are in the downsampled frame space (same as returned JPEG).
        """
        from io import BytesIO

        from PIL import Image

        # Prefer an existing store frame (watch / tests); otherwise one-shot.
        current = self.store.get()
        if current is None or not current.jpeg:
            current = self.latest_for_agent(blur=blur)
        elif blur is not None and current.blur != blur:
            current = self.capture_once(blur=blur)
        if not current.jpeg:
            current = self.capture_once(blur=blur)
        prev = self._prev_change_jpeg
        self._prev_change_jpeg = current.jpeg
        base = {
            "ok": True,
            "content_hash": current.content_hash,
            "width": current.width,
            "height": current.height,
            "change_score": current.change_score,
            "backend": current.backend,
        }
        if not prev:
            return {**base, "bbox": None, "seeded": True, "note": "Baseline stored; call again after a change"}
        try:
            img_a = Image.open(BytesIO(prev)).convert("RGB")
            img_b = Image.open(BytesIO(current.jpeg)).convert("RGB")
        except Exception as exc:
            return {**base, "ok": False, "error": f"JPEG decode failed: {exc}", "bbox": None}
        bbox = change_bbox(
            img_a,
            img_b,
            frame_width=current.width,
            frame_height=current.height,
            pixel_threshold=max(1, int(pixel_threshold)),
        )
        out: dict[str, Any] = {**base, "bbox": bbox, "seeded": False}
        if bbox and include_crop:
            crop = img_b.crop(
                (bbox["x"], bbox["y"], bbox["x"] + bbox["width"], bbox["y"] + bbox["height"])
            )
            buf = BytesIO()
            crop.save(buf, format="JPEG", quality=self.settings.jpeg_quality)
            out["region_jpeg"] = buf.getvalue()
            out["region_width"] = crop.width
            out["region_height"] = crop.height
        return out

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

    def wait_for_change(
        self,
        *,
        since_hash: str = "",
        min_change_score: float = 0.0,
        timeout_s: float = 30.0,
        poll_s: float = 0.25,
    ) -> dict[str, Any]:
        """
        Block until the screen differs from ``since_hash`` (or the current frame).

        Prefer ``start_watch`` first so polls read the store instead of re-grabbing.
        Never blocks longer than 120s. Observation only — no input injection.
        """
        import time

        timeout = max(0.1, min(float(timeout_s), 120.0))
        poll = max(0.05, min(float(poll_s), 2.0))
        min_score = max(0.0, float(min_change_score))
        baseline = (since_hash or "").strip()
        if not baseline:
            current = self.store.get()
            if current is None:
                current = self.capture_once()
            baseline = current.content_hash

        def _hit(frame: EncodedFrame) -> dict[str, Any] | None:
            if frame.content_hash == baseline:
                return None
            if min_score > 0.0 and frame.change_score < min_score:
                return None
            return {
                "ok": True,
                "changed": True,
                "timed_out": False,
                "since_hash": baseline,
                "content_hash": frame.content_hash,
                "change_score": frame.change_score,
                "width": frame.width,
                "height": frame.height,
                "timestamp_ms": frame.timestamp_ms,
                "watch_running": self.daemon.running,
                "waited_ms": round((timeout - (deadline - time.time())) * 1000.0, 1),
            }

        deadline = time.time() + timeout
        last: EncodedFrame | None = self.store.get()
        while time.time() < deadline:
            store_frame = self.store.get()
            if store_frame is not None:
                last = store_frame
                hit = _hit(store_frame)
                if hit is not None:
                    return hit
            if not self.daemon.running:
                try:
                    frame = self.capture_once()
                    last = frame
                    hit = _hit(frame)
                    if hit is not None:
                        return hit
                except Exception:
                    logger.debug("wait_for_change grab failed; retrying", exc_info=True)
            time.sleep(poll)

        return {
            "ok": True,
            "changed": False,
            "timed_out": True,
            "since_hash": baseline,
            "content_hash": last.content_hash if last else None,
            "change_score": last.change_score if last else None,
            "watch_running": self.daemon.running,
            "timeout_s": timeout,
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
            "display": self.settings.display,
            "history_len": self.store.history_len(),
            "history_size": self.settings.history_size,
            "idle_backoff": self.settings.idle_backoff,
            "unchanged_streak": self.daemon.unchanged_streak,
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
                "change_score": frame.change_score,
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
