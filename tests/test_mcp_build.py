"""MCP server construction."""

from __future__ import annotations

from screen_watch.mcp.server import build_server
from screen_watch.mcp.tools_catalog import TOOL_NAMES


def test_build_server_runnable() -> None:
    mcp = build_server()
    assert hasattr(mcp, "run")
    assert len(TOOL_NAMES) >= 20
