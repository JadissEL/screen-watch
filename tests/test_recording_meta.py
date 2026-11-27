"""Recording list enrichment + get_meta."""

from __future__ import annotations

import json
from pathlib import Path

from screen_watch.config import Settings
from screen_watch.recording.session import RecordingManager


def test_list_and_meta(tmp_path: Path) -> None:
    sid = "meta01"
    sess = tmp_path / sid
    (sess / "frames").mkdir(parents=True)
    (sess / "meta.json").write_text(
        json.dumps(
            {
                "id": sid,
                "title": "t",
                "started_ms": 10,
                "ended_ms": 99,
                "capture_source": "frame_pump",
            }
        ),
        encoding="utf-8",
    )
    (sess / "timeline.json").write_text(
        json.dumps(
            {
                "session_id": sid,
                "frames": [
                    {"unchanged": False, "file": "frames/a.jpg"},
                    {"unchanged": True, "file": None},
                ],
            }
        ),
        encoding="utf-8",
    )
    mgr = RecordingManager(Settings(recording_enabled=True, recordings_dir=tmp_path))
    listed = mgr.list_sessions()
    assert len(listed) == 1
    assert listed[0]["capture_source"] == "frame_pump"
    assert listed[0]["ended_ms"] == 99
    assert listed[0]["frame_count"] == 2
    assert listed[0]["active"] is False

    meta = mgr.get_meta(sid)
    assert meta["ok"] is True
    assert meta["frame_count"] == 2
    assert meta["keyframe_count"] == 1
    assert meta["meta"]["title"] == "t"
