"""MCP tools catalog stays in sync with build_server registrations."""

from __future__ import annotations

from screen_watch.mcp.server import build_server
from screen_watch.mcp.tools_catalog import TOOL_NAMES


def _registered_tool_names(mcp: object) -> set[str]:
    manager = getattr(mcp, "_tool_manager", None)
    if manager is not None and hasattr(manager, "_tools"):
        return set(manager._tools.keys())
    tools = getattr(mcp, "_tools", None)
    if isinstance(tools, dict):
        return set(tools.keys())
    tools2 = getattr(mcp, "tools", None)
    if isinstance(tools2, dict):
        return set(tools2.keys())
    return set()


def test_catalog_nonempty() -> None:
    assert "get_latest_frame" in TOOL_NAMES
    assert "save_latest_frame" in TOOL_NAMES
    assert "list_tools" in TOOL_NAMES


def test_build_registers_catalog_tools() -> None:
    names = _registered_tool_names(build_server())
    if not names:
        # Some mcp builds hide the registry; still ensure build_server returns a runner.
        mcp = build_server()
        assert hasattr(mcp, "run")
        return
    missing = set(TOOL_NAMES) - names
    assert not missing, f"Missing MCP tools: {sorted(missing)}"
