"""Export recording session as a local zip."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from screen_watch.config import Settings
from screen_watch.recording.session import RecordingManager


def _seed_session(root: Path, sid: str = "sess01") -> Path:
    sess = root / sid
    (sess / "frames").mkdir(parents=True)
    (sess / "meta.json").write_text(
        json.dumps({"id": sid, "title": "t", "started_ms": 1}),
        encoding="utf-8",
    )
    (sess / "timeline.json").write_text(
        json.dumps(
            {
                "session_id": sid,
                "frames": [
                    {"t_ms": 0, "unchanged": False, "file": "frames/frame_000000.jpg"},
                    {"t_ms": 100, "unchanged": True, "file": None},
                    {"t_ms": 200, "unchanged": False, "file": "frames/frame_000001.jpg"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (sess / "frames" / "frame_000000.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (sess / "frames" / "frame_000001.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (sess / "frames" / "noise.bin").write_bytes(b"skip-me-in-keyframes")
    return sess


def test_export_full_zip(tmp_path: Path) -> None:
    _seed_session(tmp_path)
    mgr = RecordingManager(Settings(recording_enabled=True, recordings_dir=tmp_path))
    result = mgr.export_session("sess01")
    assert result["ok"] is True
    zpath = Path(result["path"])
    assert zpath.is_file()
    assert zpath.name == "sess01.zip"
    with zipfile.ZipFile(zpath) as zf:
        names = set(zf.namelist())
    assert "sess01/meta.json" in names
    assert "sess01/frames/frame_000000.jpg" in names
    assert "sess01/frames/noise.bin" in names


def test_export_keyframes_only(tmp_path: Path) -> None:
    _seed_session(tmp_path)
    mgr = RecordingManager(Settings(recording_enabled=True, recordings_dir=tmp_path))
    result = mgr.export_session("sess01", keyframes_only=True)
    assert result["ok"] is True
    with zipfile.ZipFile(result["path"]) as zf:
        names = set(zf.namelist())
    assert "sess01/meta.json" in names
    assert "sess01/timeline.json" in names
    assert "sess01/frames/frame_000000.jpg" in names
    assert "sess01/frames/noise.bin" not in names
