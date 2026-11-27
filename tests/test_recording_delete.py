"""Recording delete + keyframes listing."""

from __future__ import annotations

import json
from pathlib import Path

from screen_watch.config import Settings
from screen_watch.recording.session import RecordingManager


def test_delete_and_keyframes(tmp_path: Path) -> None:
    settings = Settings(recording_enabled=True, recordings_dir=tmp_path, idle_backoff=False)
    mgr = RecordingManager(settings)
    sid = "abc123deadbe"
    sess = tmp_path / sid
    (sess / "frames").mkdir(parents=True)
    jpeg = b"\xff\xd8\xff\xd9" + b"x" * 20
    (sess / "frames" / "frame_000000.jpg").write_bytes(jpeg)
    (sess / "meta.json").write_text(json.dumps({"id": sid, "title": "t"}), encoding="utf-8")
    (sess / "timeline.json").write_text(
        json.dumps(
            {
                "session_id": sid,
                "frames": [
                    {"t_ms": 0, "unchanged": True, "file": None},
                    {"t_ms": 100, "unchanged": False, "file": "frames/frame_000000.jpg"},
                ],
            }
        ),
        encoding="utf-8",
    )
    keys = mgr.list_keyframes(sid)
    assert keys["total_keyframes"] == 1
    assert keys["keyframes"][0]["file"].endswith(".jpg")

    loaded = mgr.read_keyframe(sid, "frames/frame_000000.jpg")
    assert loaded["ok"] is True
    assert loaded["jpeg"][:2] == b"\xff\xd8"
    assert mgr.read_keyframe(sid, "../secrets.jpg")["ok"] is False

    assert mgr.delete_session("..")["ok"] is False
    assert mgr.delete_session(sid)["ok"] is True
    assert not sess.exists()
    assert mgr.delete_session(sid)["ok"] is False
