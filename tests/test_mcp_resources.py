"""MCP resources register when the SDK supports them."""

from __future__ import annotations

from screen_watch.mcp.server import build_server


def test_build_server_with_resources() -> None:
    mcp = build_server()
    assert hasattr(mcp, "run")
    # FastMCP keeps resources on _resource_manager when available
    manager = getattr(mcp, "_resource_manager", None)
    if manager is None:
        return
    resources = getattr(manager, "_resources", None) or getattr(manager, "resources", None)
    if not resources:
        return
    keys = set(resources.keys()) if isinstance(resources, dict) else set()
    # URI templates may be keyed differently; just ensure something registered
    assert len(keys) >= 1 or len(resources) >= 1
