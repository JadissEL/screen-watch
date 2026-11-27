"""Frame metadata history ring buffer."""

from __future__ import annotations

from screen_watch.pipeline.frame_store import EncodedFrame, FrameStore


def _frame(hash_: str, *, unchanged: bool = False) -> EncodedFrame:
    return EncodedFrame(
        jpeg=b"\xff\xd8" + hash_.encode(),
        width=10,
        height=10,
        timestamp_ms=1.0,
        content_hash=hash_,
        unchanged=unchanged,
        backend="mock",
        display_id=1,
    )


def test_history_newest_first_changed_only() -> None:
    store = FrameStore(history_size=5)
    store.set(_frame("a"))
    store.set(_frame("a", unchanged=True))
    store.set(_frame("b"))
    hist = store.history(limit=10, changed_only=True)
    assert [h["content_hash"] for h in hist] == ["b", "a"]
    assert store.history_len() == 3


def test_history_maxlen() -> None:
    store = FrameStore(history_size=2)
    store.set(_frame("1"))
    store.set(_frame("2"))
    store.set(_frame("3"))
    assert store.history_len() == 2
    assert store.history(limit=10)[0]["content_hash"] == "3"


def test_history_min_change_score() -> None:
    store = FrameStore(history_size=10)
    low = _frame("low")
    low.change_score = 1.0
    high = _frame("high")
    high.change_score = 10.0
    store.set(low)
    store.set(high)
    hist = store.history(limit=10, min_change_score=5.0)
    assert [h["content_hash"] for h in hist] == ["high"]
