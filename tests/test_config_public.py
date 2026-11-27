"""Settings.as_public_dict + CLI config."""

from __future__ import annotations

from screen_watch.cli import main
from screen_watch.config import Settings


def test_as_public_dict_paths() -> None:
    s = Settings(recording_enabled=True, fps=3.0)
    d = s.as_public_dict()
    assert d["fps"] == 3.0
    assert d["capped_fps"] == 3.0
    assert d["recording_enabled"] is True
    assert "recordings_dir" in d
    assert "config_path" in d


def test_cli_config(capsys) -> None:
    code = main(["config"])
    assert code == 0
    out = capsys.readouterr().out
    assert "jpeg_quality" in out
    assert "recordings_dir" in out
