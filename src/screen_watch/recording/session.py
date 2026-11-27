"""Opt-in recording sessions — local artifacts with timeline sync hooks (no STT)."""

from __future__ import annotations

import json
import logging
import shutil
import threading
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from screen_watch.advisor.profiler import (
    capacity_advice_message,
    profile_machine,
    recommend_settings,
)
from screen_watch.capture.factory import create_backend
from screen_watch.capture.loop import FramePump
from screen_watch.config import Settings
from screen_watch.pipeline.encode import extension_for_format, normalize_format, sniff_format
from screen_watch.pipeline.frame_store import FrameStore

logger = logging.getLogger(__name__)


@dataclass
class RecordingSession:
    id: str
    title: str
    started_ms: float
    ended_ms: float | None = None
    dir: str = ""
    frame_count: int = 0
    timeline: list[dict[str, Any]] = field(default_factory=list)


class RecordingManager:
    """Manages opt-in recording sessions on disk."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = threading.Lock()
        self._active: RecordingSession | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._pump: FramePump | None = None
        self._shared_store: FrameStore | None = None
        self._capture_source: str = "frame_pump"
        self._root = Path(settings.recordings_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def active(self) -> RecordingSession | None:
        return self._active

    def start(
        self,
        title: str | None = None,
        *,
        shared_store: FrameStore | None = None,
    ) -> dict[str, Any]:
        """
        Start recording if enabled. Always returns advice; never refuses for capacity.

        When ``shared_store`` is set (watch daemon already filling it), record taps
        that store instead of opening a second capture loop.
        """
        advice = capacity_advice_message()
        if not self._settings.recording_enabled:
            return {
                "ok": False,
                "error": "Recording is disabled. Set SCREEN_WATCH_RECORDING_ENABLED=1 or recording.enabled.",
                "advice": advice,
            }
        with self._lock:
            if self._active is not None:
                return {"ok": False, "error": "Recording already active", "session": asdict(self._active), "advice": advice}

            sid = uuid.uuid4().hex[:12]
            started = time.time() * 1000.0
            sess_dir = self._root / sid
            sess_dir.mkdir(parents=True, exist_ok=True)
            session = RecordingSession(
                id=sid,
                title=title or f"session-{sid}",
                started_ms=started,
                dir=str(sess_dir),
            )
            source = "shared_store" if shared_store is not None else "frame_pump"
            meta = {
                "id": sid,
                "title": session.title,
                "started_ms": started,
                "capture_source": source,
                "sync": {"epoch_ms": started, "note": "Align agent STT timestamps to started_ms / frame t_ms"},
                "advice": advice,
                "profile": recommend_settings(profile_machine()),
            }
            (sess_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            self._active = session
            self._shared_store = shared_store
            self._capture_source = source
            self._stop.clear()
            self._pump = None
            self._thread = threading.Thread(target=self._run, name="screen-watch-record", daemon=True)
            self._thread.start()
            return {
                "ok": True,
                "session": asdict(session),
                "advice": advice,
                "capture_source": source,
            }

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if self._active is None:
                return {"ok": False, "error": "No active recording"}
            self._stop.set()
            if self._pump is not None:
                self._pump.stop()
        if self._thread is not None:
            self._thread.join(timeout=10.0)
        with self._lock:
            session = self._active
            assert session is not None
            session.ended_ms = time.time() * 1000.0
            self._write_timeline(session)
            result = asdict(session)
            self._active = None
            self._thread = None
            self._shared_store = None
            self._capture_source = "frame_pump"
            return {"ok": True, "session": result}

    def list_sessions(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not self._root.exists():
            return out
        for path in sorted(self._root.iterdir()):
            meta_path = path / "meta.json"
            if not meta_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                tl_path = path / "timeline.json"
                frames = 0
                ended = meta.get("ended_ms")
                if tl_path.exists():
                    tl = json.loads(tl_path.read_text(encoding="utf-8"))
                    frames = len(tl.get("frames", []))
                    ended = ended if ended is not None else tl.get("ended_ms")
                out.append(
                    {
                        "id": meta.get("id", path.name),
                        "title": meta.get("title"),
                        "started_ms": meta.get("started_ms"),
                        "ended_ms": ended,
                        "dir": str(path),
                        "frame_count": frames,
                        "capture_source": meta.get("capture_source"),
                        "active": self._active is not None and self._active.id == path.name,
                    }
                )
            except Exception:
                logger.debug("skip corrupt session %s", path, exc_info=True)
        return out

    def get_meta(self, session_id: str) -> dict[str, Any]:
        """Return session meta.json (+ light timeline stats) without full frame index."""
        path, err = self._session_dir(session_id)
        if err is not None:
            return err
        assert path is not None
        meta_path = path / "meta.json"
        if not meta_path.exists():
            return {"ok": False, "error": f"No meta for {path.name}"}
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"ok": False, "error": f"Corrupt meta: {exc}"}
        frames = 0
        keyframes = 0
        tl_path = path / "timeline.json"
        if tl_path.exists():
            try:
                tl = json.loads(tl_path.read_text(encoding="utf-8"))
                fl = tl.get("frames", [])
                frames = len(fl)
                keyframes = sum(1 for f in fl if not f.get("unchanged") and f.get("file"))
                if meta.get("ended_ms") is None and tl.get("ended_ms") is not None:
                    meta["ended_ms"] = tl.get("ended_ms")
            except Exception:
                logger.debug("timeline stats skipped for %s", path.name, exc_info=True)
        return {
            "ok": True,
            "session_id": path.name,
            "dir": str(path),
            "meta": meta,
            "frame_count": frames,
            "keyframe_count": keyframes,
            "active": self._active is not None and self._active.id == path.name,
        }

    def get_timeline(self, session_id: str) -> dict[str, Any]:
        path = self._root / session_id / "timeline.json"
        meta = self._root / session_id / "meta.json"
        if not path.exists():
            return {"error": f"No timeline for {session_id}"}
        data = json.loads(path.read_text(encoding="utf-8"))
        if meta.exists():
            data["meta"] = json.loads(meta.read_text(encoding="utf-8"))
        return data

    def _session_dir(self, session_id: str) -> tuple[Path | None, dict[str, Any] | None]:
        """Resolve a session directory under recordings root (path-traversal safe)."""
        sid = Path(session_id).name
        if not sid or sid in {".", ".."}:
            return None, {"ok": False, "error": "Invalid session id"}
        path = (self._root / sid).resolve()
        try:
            path.relative_to(self._root.resolve())
        except ValueError:
            return None, {"ok": False, "error": "Invalid session path"}
        if not path.is_dir():
            return None, {"ok": False, "error": f"No session {sid}"}
        return path, None

    def rename_session(self, session_id: str, title: str) -> dict[str, Any]:
        """Rename a session (active or finished). Updates meta.json and timeline title."""
        new_title = (title or "").strip()
        if not new_title:
            return {"ok": False, "error": "Title must be non-empty"}
        if len(new_title) > 200:
            return {"ok": False, "error": "Title too long (max 200 chars)"}
        path, err = self._session_dir(session_id)
        if err is not None:
            return err
        assert path is not None
        sid = path.name
        with self._lock:
            if self._active is not None and self._active.id == sid:
                self._active.title = new_title
        meta_path = path / "meta.json"
        meta: dict[str, Any] = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta = {"id": sid}
        meta["id"] = sid
        meta["title"] = new_title
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        tl_path = path / "timeline.json"
        if tl_path.exists():
            try:
                data = json.loads(tl_path.read_text(encoding="utf-8"))
                data["title"] = new_title
                tl_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                logger.debug("timeline title update skipped for %s", sid, exc_info=True)
        return {"ok": True, "session_id": sid, "title": new_title}

    def delete_session(self, session_id: str) -> dict[str, Any]:
        """Delete a finished session directory (path-traversal safe)."""
        path, err = self._session_dir(session_id)
        if err is not None:
            return err
        assert path is not None
        sid = path.name
        with self._lock:
            if self._active is not None and self._active.id == sid:
                return {"ok": False, "error": "Stop the active recording before deleting it"}
        shutil.rmtree(path)
        return {"ok": True, "deleted": sid}

    def export_session(
        self,
        session_id: str,
        *,
        dest: str | Path | None = None,
        keyframes_only: bool = False,
    ) -> dict[str, Any]:
        """
        Zip a finished session for local share/archive (never uploads).

        Default dest: ``<recordings_dir>/<id>.zip``.
        """
        sess, err = self._session_dir(session_id)
        if err is not None:
            return err
        assert sess is not None
        sid = sess.name
        with self._lock:
            if self._active is not None and self._active.id == sid:
                return {"ok": False, "error": "Stop the active recording before exporting"}

        out = Path(dest) if dest else (self._root / f"{sid}.zip")
        out = out.resolve()
        # Keep zip under recordings root unless caller passed an absolute dest outside
        if dest is None:
            try:
                out.relative_to(self._root.resolve())
            except ValueError:
                return {"ok": False, "error": "Invalid export path"}
        out.parent.mkdir(parents=True, exist_ok=True)

        keyframe_files: set[str] = set()
        if keyframes_only:
            tl = self.get_timeline(sid)
            for fr in tl.get("frames", []):
                if not fr.get("unchanged") and fr.get("file"):
                    keyframe_files.add(str(fr["file"]).replace("\\", "/"))

        count = 0
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sess.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(sess).as_posix()
                if keyframes_only:
                    if rel in {"meta.json", "timeline.json"} or rel in keyframe_files:
                        zf.write(path, arcname=f"{sid}/{rel}")
                        count += 1
                else:
                    zf.write(path, arcname=f"{sid}/{rel}")
                    count += 1
        return {
            "ok": True,
            "session_id": sid,
            "path": str(out),
            "bytes": out.stat().st_size,
            "files": count,
            "keyframes_only": keyframes_only,
        }

    def list_keyframes(self, session_id: str, *, limit: int = 50) -> dict[str, Any]:
        """Return changed-frame entries from a session timeline (paths relative to session dir)."""
        data = self.get_timeline(session_id)
        if "error" in data:
            return data
        frames = [f for f in data.get("frames", []) if not f.get("unchanged") and f.get("file")]
        n = max(1, min(int(limit), 500))
        return {
            "session_id": data.get("session_id", session_id),
            "count": len(frames[:n]),
            "total_keyframes": len(frames),
            "dir": str(self._root / Path(session_id).name),
            "keyframes": frames[:n],
        }

    def read_keyframe(self, session_id: str, file: str) -> dict[str, Any]:
        """
        Read a keyframe JPEG from a session (path must be under session/frames/).

        Returns ``{"ok": True, "jpeg": bytes, ...}`` or an error dict (no path escape).
        """
        sid = Path(session_id).name
        rel = Path(file)
        if rel.is_absolute() or ".." in rel.parts:
            return {"ok": False, "error": "Invalid frame path"}
        sess = (self._root / sid).resolve()
        try:
            sess.relative_to(self._root.resolve())
        except ValueError:
            return {"ok": False, "error": "Invalid session path"}
        target = (sess / rel).resolve()
        try:
            target.relative_to(sess / "frames")
        except ValueError:
            # also allow paths already prefixed with frames/
            try:
                target.relative_to(sess)
            except ValueError:
                return {"ok": False, "error": "Frame path escapes session"}
            if "frames" not in target.parts:
                return {"ok": False, "error": "Frame must be under frames/"}
        if not target.is_file():
            return {"ok": False, "error": f"Missing frame file {file}"}
        data = target.read_bytes()
        fmt = sniff_format(data)
        if fmt is None:
            return {"ok": False, "error": "Not a JPEG/WebP frame"}
        return {
            "ok": True,
            "session_id": sid,
            "file": str(rel).replace("\\", "/"),
            "bytes": len(data),
            "image_format": fmt,
            "jpeg": data,
        }

    def _run(self) -> None:
        if self._shared_store is not None:
            self._run_from_store()
            return
        backend = create_backend(self._settings)
        # Gentler FPS while recording; same FramePump seam as WatchDaemon.
        pump = FramePump(
            backend,
            self._settings,
            stop_event=self._stop,
            fps_cap=3.0,
        )
        self._pump = pump
        try:
            for encoded in pump.frames():
                if self._stop.is_set():
                    break
                try:
                    if encoded.unchanged and self._active and self._active.frame_count > 0:
                        t_ms = encoded.timestamp_ms - self._active.started_ms
                        self._active.timeline.append(
                            {"t_ms": round(t_ms, 1), "unchanged": True, "file": None}
                        )
                    else:
                        if encoded.unchanged or not encoded.jpeg:
                            encoded = pump.force_keyframe()
                        self._append_frame(encoded)
                except Exception as exc:
                    logger.warning("Recording tick failed: %s", exc)
        finally:
            self._pump = None

    def _run_from_store(self) -> None:
        """Tap an existing watch FrameStore — no second grab loop."""
        store = self._shared_store
        assert store is not None
        interval = 1.0 / 3.0
        last_hash: str | None = None
        while not self._stop.is_set():
            t0 = time.perf_counter()
            try:
                frame = store.get()
                if frame is not None and frame.jpeg:
                    if last_hash is not None and frame.content_hash == last_hash:
                        if self._active and self._active.frame_count > 0:
                            t_ms = frame.timestamp_ms - self._active.started_ms
                            self._active.timeline.append(
                                {"t_ms": round(t_ms, 1), "unchanged": True, "file": None}
                            )
                    else:
                        self._append_frame(frame)
                        last_hash = frame.content_hash
            except Exception as exc:
                logger.warning("Recording store-tap failed: %s", exc)
            elapsed = time.perf_counter() - t0
            self._stop.wait(max(0.0, interval - elapsed))

    def _append_frame(self, encoded: Any) -> None:
        session = self._active
        if session is None:
            return
        sess_dir = Path(session.dir)
        idx = session.frame_count
        fmt = normalize_format(getattr(encoded, "image_format", self._settings.image_format))
        ext = extension_for_format(fmt)
        filename = f"frame_{idx:06d}.{ext}"
        (sess_dir / "frames").mkdir(exist_ok=True)
        (sess_dir / "frames" / filename).write_bytes(encoded.jpeg)
        t_ms = encoded.timestamp_ms - session.started_ms
        session.timeline.append(
            {
                "t_ms": round(t_ms, 1),
                "unchanged": False,
                "file": f"frames/{filename}",
                "width": encoded.width,
                "height": encoded.height,
                "hash": encoded.content_hash,
                "image_format": fmt,
            }
        )
        session.frame_count += 1

    def _write_timeline(self, session: RecordingSession) -> None:
        path = Path(session.dir) / "timeline.json"
        payload = {
            "session_id": session.id,
            "title": session.title,
            "started_ms": session.started_ms,
            "ended_ms": session.ended_ms,
            "frame_count": session.frame_count,
            "sync_hooks": {
                "session_start_epoch_ms": session.started_ms,
                "frame_t_ms_relative": True,
                "agent_stt": "Map your transcript utterances to t_ms using session_start_epoch_ms",
            },
            "frames": session.timeline,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        meta_path = Path(session.dir) / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["ended_ms"] = session.ended_ms
            meta["frame_count"] = session.frame_count
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
