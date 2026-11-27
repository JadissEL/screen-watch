"""Rename recording sessions."""

from __future__ import annotations

import json
from pathlib import Path

from screen_watch.config import Settings
from screen_watch.recording.session import RecordingManager


def test_rename_session(tmp_path: Path) -> None:
    sid = "ren01"
    sess = tmp_path / sid
    sess.mkdir()
    (sess / "meta.json").write_text(
        json.dumps({"id": sid, "title": "old", "started_ms": 1}),
        encoding="utf-8",
    )
    (sess / "timeline.json").write_text(
        json.dumps({"session_id": sid, "title": "old", "frames": []}),
        encoding="utf-8",
    )
    mgr = RecordingManager(Settings(recording_enabled=True, recordings_dir=tmp_path))
    result = mgr.rename_session(sid, "  new title  ")
    assert result["ok"] is True
    assert result["title"] == "new title"
    meta = json.loads((sess / "meta.json").read_text(encoding="utf-8"))
    assert meta["title"] == "new title"
    tl = json.loads((sess / "timeline.json").read_text(encoding="utf-8"))
    assert tl["title"] == "new title"


def test_rename_rejects_empty(tmp_path: Path) -> None:
    mgr = RecordingManager(Settings(recording_enabled=True, recordings_dir=tmp_path))
    assert mgr.rename_session("x", "   ")["ok"] is False
