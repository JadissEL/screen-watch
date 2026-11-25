"""Config defaults."""

from __future__ import annotations

from screen_watch.config import (
    DEFAULT_FPS,
    DEFAULT_JPEG_QUALITY,
    DEFAULT_MAX_HEIGHT,
    DEFAULT_MAX_WIDTH,
    load_settings,
)


def test_locked_defaults() -> None:
    s = load_settings()
    assert s.max_width == DEFAULT_MAX_WIDTH == 1280
    assert s.max_height == DEFAULT_MAX_HEIGHT == 720
    assert s.fps == DEFAULT_FPS == 5.0
    assert s.jpeg_quality == DEFAULT_JPEG_QUALITY == 60
    assert s.blur is False
    assert s.recording_enabled is False
    assert s.min_capture_interval_s == 0.12


def test_min_capture_interval_env(monkeypatch) -> None:
    monkeypatch.setenv("SCREEN_WATCH_MIN_CAPTURE_INTERVAL", "0.25")
    s = load_settings()
    assert s.min_capture_interval_s == 0.25
