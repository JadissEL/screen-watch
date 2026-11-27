"""Idle watch backoff helper."""

from __future__ import annotations

from screen_watch.daemon.watcher import idle_wait_factor


def test_idle_wait_disabled() -> None:
    assert idle_wait_factor(10, enabled=False, max_factor=4.0) == 1.0


def test_idle_wait_grows_and_caps() -> None:
    assert idle_wait_factor(0, enabled=True, max_factor=4.0) == 1.0
    assert idle_wait_factor(1, enabled=True, max_factor=4.0) == 1.25
    assert idle_wait_factor(4, enabled=True, max_factor=4.0) == 2.0
    assert idle_wait_factor(100, enabled=True, max_factor=4.0) == 4.0
