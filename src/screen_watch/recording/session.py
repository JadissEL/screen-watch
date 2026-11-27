"""Opt-in recording sessions — local artifacts with timeline sync hooks (no STT)."""

from __future__ import annotations

import json
import logging
import shutil
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from screen_watch.advisor.profiler import (
    capacity_advice_message,
    profile_machine,
    recommend_settings,
)
from screen_watch.backoff import idle_wait_factor
from screen_watch.capture.factory import create_backend
from screen_watch.config import Settings
from screen_watch.pipeline.process import process_raw_frame

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
        self._thumb = None
        self._root = Path(settings.recordings_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def active(self) -> RecordingSession | None:
        return self._active

    def start(self, title: str | None = None) -> dict[str, Any]:
        """Start recording if enabled. Always returns advice; never refuses for capacity."""
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
            meta = {
                "id": sid,
                "title": session.title,
                "started_ms": started,
                "sync": {"epoch_ms": started, "note": "Align agent STT timestamps to started_ms / frame t_ms"},
                "advice": advice,
                "profile": recommend_settings(profile_machine()),
            }
            (sess_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            self._active = session
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="screen-watch-record", daemon=True)
            self._thread.start()
            return {"ok": True, "session": asdict(session), "advice": advice}

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if self._active is None:
                return {"ok": False, "error": "No active recording"}
            self._stop.set()
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
                if tl_path.exists():
                    frames = len(json.loads(tl_path.read_text(encoding="utf-8")).get("frames", []))
                out.append(
                    {
                        "id": meta.get("id", path.name),
                        "title": meta.get("title"),
                        "started_ms": meta.get("started_ms"),
                        "dir": str(path),
                        "frame_count": frames,
                    }
                )
            except Exception:
                logger.debug("skip corrupt session %s", path, exc_info=True)
        return out

    def get_timeline(self, session_id: str) -> dict[str, Any]:
        path = self._root / session_id / "timeline.json"
        meta = self._root / session_id / "meta.json"
        if not path.exists():
            return {"error": f"No timeline for {session_id}"}
        data = json.loads(path.read_text(encoding="utf-8"))
        if meta.exists():
            data["meta"] = json.loads(meta.read_text(encoding="utf-8"))
        return data

    def delete_session(self, session_id: str) -> dict[str, Any]:
        """Delete a finished session directory (path-traversal safe)."""
        sid = Path(session_id).name
        if not sid or sid in {".", ".."}:
            return {"ok": False, "error": "Invalid session id"}
        with self._lock:
            if self._active is not None and self._active.id == sid:
                return {"ok": False, "error": "Stop the active recording before deleting it"}
        path = (self._root / sid).resolve()
        try:
            path.relative_to(self._root.resolve())
        except ValueError:
            return {"ok": False, "error": "Invalid session path"}
        if not path.is_dir():
            return {"ok": False, "error": f"No session {sid}"}
        shutil.rmtree(path)
        return {"ok": True, "deleted": sid}

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
        if data[:2] != b"\xff\xd8":
            return {"ok": False, "error": "Not a JPEG frame"}
        return {
            "ok": True,
            "session_id": sid,
            "file": str(rel).replace("\\", "/"),
            "bytes": len(data),
            "jpeg": data,
        }

    def _run(self) -> None:
        backend = create_backend(self._settings)
        base_interval = 1.0 / max(1.0, min(self._settings.capped_fps(), 3.0))  # gentler while recording
        unchanged_streak = 0
        while not self._stop.is_set():
            t0 = time.perf_counter()
            try:
                raw = backend.grab(self._settings.display)
                encoded, self._thumb = process_raw_frame(
                    raw, self._settings, previous_thumb=self._thumb
                )
                if encoded.unchanged and self._active and self._active.frame_count > 0:
                    # Still log a timeline tick without rewriting identical JPEG
                    t_ms = raw.timestamp_ms - (self._active.started_ms)
                    self._active.timeline.append(
                        {"t_ms": round(t_ms, 1), "unchanged": True, "file": None}
                    )
                    unchanged_streak += 1
                else:
                    if encoded.unchanged or not encoded.jpeg:
                        encoded, self._thumb = process_raw_frame(
                            raw, self._settings, previous_thumb=None, skip_change_detect=True
                        )
                    self._append_frame(encoded)
                    unchanged_streak = 0
            except Exception as exc:
                logger.warning("Recording tick failed: %s", exc)
            elapsed = time.perf_counter() - t0
            factor = idle_wait_factor(
                unchanged_streak,
                enabled=self._settings.idle_backoff,
                max_factor=self._settings.idle_backoff_max,
            )
            self._stop.wait(max(0.0, base_interval * factor - elapsed))

    def _append_frame(self, encoded: Any) -> None:
        session = self._active
        if session is None:
            return
        sess_dir = Path(session.dir)
        idx = session.frame_count
        filename = f"frame_{idx:06d}.jpg"
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
