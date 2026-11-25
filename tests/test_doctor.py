"""Doctor command smoke test."""

from __future__ import annotations

from screen_watch.doctor import run_doctor


def test_doctor_shape() -> None:
    data = run_doctor()
    assert "version" in data
    assert "backend" in data
    assert "tools" in data
    assert data["tools"]["mss"] is True
    assert "gdbus" in data["tools"]
    assert "quartz" in data["tools"]
