"""Shared idle-backoff helpers for watch / record / FramePump."""

from __future__ import annotations


def idle_wait_factor(unchanged_streak: int, *, enabled: bool, max_factor: float) -> float:
    """
    Scale the base capture interval when the desktop is static.

    streak 0 → 1.0; grows by 0.25 per unchanged tick, capped at max_factor.
    """
    if not enabled or unchanged_streak <= 0:
        return 1.0
    return min(max(1.0, float(max_factor)), 1.0 + unchanged_streak * 0.25)
