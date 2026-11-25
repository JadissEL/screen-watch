"""since_hash short-circuit for MCP frame tools."""

from __future__ import annotations

from screen_watch.capture.mock_backend import MockBackend
from screen_watch.config import Settings
from screen_watch.daemon.watcher import WatchDaemon
from screen_watch.pipeline.frame_store import FrameStore
from screen_watch.service import ScreenWatchService, get_service, reset_service


def _mock_svc(monkeypatch) -> ScreenWatchService:  # type: ignore[no-untyped-def]
    reset_service()
    settings = Settings(max_width=160, max_height=90, jpeg_quality=50)
    store = FrameStore()
    backend = MockBackend(320, 180)
    daemon = WatchDaemon(backend, store, settings)
    svc = ScreenWatchService(settings=settings, store=store, daemon=daemon, backend_name="mock")
    monkeypatch.setattr("screen_watch.service.create_backend", lambda _s=None: backend)
    monkeypatch.setattr("screen_watch.service.get_service", lambda: svc)
    monkeypatch.setattr("screen_watch.mcp.server.get_service", lambda: svc)
    return svc


def test_since_hash_skips_image(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    svc = _mock_svc(monkeypatch)
    frame = svc.capture_once()
    mcp = __import__("screen_watch.mcp.server", fromlist=["build_server"]).build_server()
    # Invoke registered tool via manager when available
    manager = getattr(mcp, "_tool_manager", None)
    assert manager is not None
    tool = manager._tools["get_latest_frame"]
    fn = tool.fn if hasattr(tool, "fn") else tool
    result = fn(blur=False, since_hash=frame.content_hash)
    assert isinstance(result, dict)
    assert result["skipped_image"] is True
    assert result["content_hash"] == frame.content_hash
    reset_service()


def test_info_unchanged_vs_client(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    svc = _mock_svc(monkeypatch)
    frame = svc.capture_once()
    from screen_watch.mcp.server import build_server

    mcp = build_server()
    manager = getattr(mcp, "_tool_manager", None)
    assert manager is not None
    tool = manager._tools["get_latest_frame_info"]
    fn = tool.fn if hasattr(tool, "fn") else tool
    info = fn(blur=False, since_hash=frame.content_hash)
    assert info["unchanged_vs_client"] is True
    reset_service()
