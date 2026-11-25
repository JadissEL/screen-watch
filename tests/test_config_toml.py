"""TOML config file loading."""

from __future__ import annotations

from pathlib import Path

from screen_watch.config import load_settings, load_toml_file


def test_load_toml_missing(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("SCREEN_WATCH_CONFIG", str(tmp_path / "nope.toml"))
    assert load_toml_file() == {}


def test_load_toml_overrides_defaults(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "config.toml"
    path.write_text("max_width = 640\njpeg_quality = 40\nbackend = \"mss\"\n", encoding="utf-8")
    monkeypatch.setenv("SCREEN_WATCH_CONFIG", str(path))
    for key in list(__import__("os").environ):
        if key.startswith("SCREEN_WATCH_") and key != "SCREEN_WATCH_CONFIG":
            monkeypatch.delenv(key, raising=False)
    s = load_settings()
    assert s.max_width == 640
    assert s.jpeg_quality == 40
    assert s.backend == "mss"


def test_env_beats_toml(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "config.toml"
    path.write_text("max_width = 640\n", encoding="utf-8")
    monkeypatch.setenv("SCREEN_WATCH_CONFIG", str(path))
    monkeypatch.setenv("SCREEN_WATCH_MAX_WIDTH", "800")
    s = load_settings()
    assert s.max_width == 800
