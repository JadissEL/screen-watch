"""Min-interval gate."""

from __future__ import annotations

import time

from screen_watch.rate_limit import MinIntervalGate


def test_min_interval_enforced() -> None:
    gate = MinIntervalGate(0.05)
    t0 = time.monotonic()
    gate.wait()
    gate.wait()
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.04
