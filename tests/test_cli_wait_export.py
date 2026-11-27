"""CLI wait / export subcommands parse and run."""

from __future__ import annotations

from pathlib import Path

from screen_watch.cli import main
from screen_watch.config import Settings


def test_cli_export(tmp_path: Path, monkeypatch) -> None:
    sess = tmp_path / "abc"
    (sess / "frames").mkdir(parents=True)
    (sess / "meta.json").write_text('{"id":"abc","title":"t","started_ms":1}', encoding="utf-8")
    (sess / "timeline.json").write_text(
        '{"session_id":"abc","frames":[]}',
        encoding="utf-8",
    )
    (sess / "frames" / "frame_000000.jpg").write_bytes(b"\xff\xd8\xff\xd9")

    monkeypatch.setenv("SCREEN_WATCH_RECORDINGS_DIR", str(tmp_path))
    code = main(["export", "abc"])
    assert code == 0
    assert (tmp_path / "abc.zip").is_file()


def test_cli_wait_timeout(monkeypatch, tmp_path: Path) -> None:
    import screen_watch.cli as cli_mod
    from screen_watch.capture.mock_backend import MockBackend
    from screen_watch.daemon.watcher import WatchDaemon
    from screen_watch.pipeline.frame_store import EncodedFrame, FrameStore
    from screen_watch.service import ScreenWatchService

    settings = Settings(
        max_width=40,
        max_height=30,
        jpeg_quality=40,
        fps=5.0,
        idle_backoff=False,
        min_capture_interval_s=0.0,
        recordings_dir=tmp_path,
    )
    store = FrameStore(history_size=2)
    store.set(
        EncodedFrame(
            jpeg=b"\xff\xd8\xff\xd9",
            width=10,
            height=10,
            timestamp_ms=1.0,
            content_hash="fixed",
            unchanged=True,
            backend="mock",
            display_id=0,
        )
    )
    fake = ScreenWatchService(
        settings=settings,
        store=store,
        daemon=WatchDaemon(MockBackend(40, 30), store, settings),
        backend_name="mock",
    )
    fake.capture_once = lambda **_k: store.get()  # type: ignore[method-assign]
    monkeypatch.setattr(cli_mod, "reset_service", lambda: None)
    monkeypatch.setattr(cli_mod, "get_service", lambda: fake)
    code = main(["wait", "--since-hash", "fixed", "--timeout", "0.2", "--poll", "0.05"])
    assert code == 2


def test_cli_export_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SCREEN_WATCH_RECORDINGS_DIR", str(tmp_path))
    code = main(["export", "nope"])
    assert code == 1
