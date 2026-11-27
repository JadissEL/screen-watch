"""MCP stdio server exposing screen-watch tools."""

from __future__ import annotations

import json
import logging
from typing import Any

from screen_watch import __version__
from screen_watch.advisor.cost_estimate import estimate_session_cost
from screen_watch.advisor.llm_catalog import list_models
from screen_watch.advisor.profiler import profile_machine, recommend_settings
from screen_watch.advisor.store import load_advisor_state, save_advisor_state
from screen_watch.logging_setup import configure_logging
from screen_watch.mcp.tools_catalog import TOOL_NAMES
from screen_watch.privacy import privacy_blurb
from screen_watch.recording.session import RecordingManager
from screen_watch.service import get_service

logger = logging.getLogger(__name__)

_recorder: RecordingManager | None = None


def _get_recorder() -> RecordingManager:
    global _recorder
    svc = get_service()
    if _recorder is None:
        _recorder = RecordingManager(svc.settings)
    return _recorder


def _image_result(jpeg: bytes, meta: dict[str, Any]) -> Any:
    """Return MCP Image when possible, else JSON with base64 (fallback)."""
    try:
        try:
            from mcp.server.fastmcp import Image
        except ImportError:
            from mcp.server.mcpserver import Image  # type: ignore

        # Prefer returning Image; also include meta via side channel is hard —
        # FastMCP Image is the primary payload. Callers can use get_watch_status for meta.
        return Image(data=jpeg, format="jpeg")
    except Exception:
        import base64

        return {
            "mime": "image/jpeg",
            "base64": base64.b64encode(jpeg).decode("ascii"),
            **meta,
        }


def build_server() -> Any:
    """Construct the MCP server object (FastMCP / MCPServer)."""
    try:
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("screen-watch")
    except ImportError:
        from mcp.server import MCPServer as FastMCP  # type: ignore

        mcp = FastMCP("screen-watch")

    # Resources (best-effort — older MCPServer builds may lack @resource)
    try:

        @mcp.resource("screen://privacy")
        def privacy_resource() -> str:
            """Local privacy blurb for agents."""
            return privacy_blurb()

        @mcp.resource("screen://status")
        def status_resource() -> str:
            """JSON watch/capture status (no image bytes)."""
            return json.dumps(get_service().status(), indent=2)

        @mcp.resource("screen://tools")
        def tools_resource() -> str:
            """Canonical tool name catalog."""
            return json.dumps({"tools": list(TOOL_NAMES), "count": len(TOOL_NAMES)}, indent=2)

    except Exception:
        logger.debug("MCP resources not registered on this SDK", exc_info=True)

    try:

        @mcp.prompt()
        def observation_workflow() -> str:
            """Recommended observation-only polling pattern for agents."""
            from pathlib import Path

            path = Path(__file__).resolve().parents[3] / "examples" / "agent-usage.md"
            if path.is_file():
                return path.read_text(encoding="utf-8")
            return (
                "1. doctor / get_version\n"
                "2. start_watch\n"
                "3. wait_for_change(since_hash=…) or poll get_latest_frame_info\n"
                "4. get_latest_frame only when hash changes\n"
            )

    except Exception:
        logger.debug("MCP prompts not registered on this SDK", exc_info=True)

    @mcp.tool()
    def get_version() -> dict[str, Any]:
        """Return package version and repo URL."""
        return {
            "version": __version__,
            "repo": "https://github.com/JadissEL/screen-watch",
            "privacy": privacy_blurb(),
        }

    @mcp.tool()
    def get_latest_frame(blur: bool = False, since_hash: str = "") -> Any:
        """
        Capture or return the latest desktop frame as JPEG (observation only).

        blur: if true, pixelate the frame before send (privacy). Off by default.
        since_hash: if set and equal to the current content_hash, return a small JSON
        stub instead of image bytes (avoids re-billing identical frames).
        """
        svc = get_service()
        frame = svc.latest_for_agent(blur=blur)
        if not frame.jpeg:
            frame = svc.capture_once(blur=blur)
        meta = {
            "width": frame.width,
            "height": frame.height,
            "timestamp_ms": frame.timestamp_ms,
            "content_hash": frame.content_hash,
            "unchanged": frame.unchanged,
            "blur": frame.blur,
            "backend": frame.backend,
            "change_score": frame.change_score,
        }
        if since_hash and since_hash == frame.content_hash:
            logger.info("get_latest_frame unchanged hash=%s", since_hash[:12])
            return {
                "unchanged": True,
                "skipped_image": True,
                **meta,
                "age_ms": svc.store.age_ms(),
            }
        logger.info("get_latest_frame %sx%s blur=%s", frame.width, frame.height, frame.blur)
        return _image_result(frame.jpeg, meta)

    @mcp.tool()
    def get_latest_frame_info(blur: bool = False, since_hash: str = "") -> dict[str, Any]:
        """
        Same as get_latest_frame but returns JSON metadata (no image bytes).

        Pass since_hash from a prior poll; when it matches, ``unchanged`` is true and
        you can skip calling get_latest_frame.
        """
        svc = get_service()
        frame = svc.latest_for_agent(blur=blur)
        if not frame.jpeg:
            frame = svc.capture_once(blur=blur)
        unchanged_vs_client = bool(since_hash) and since_hash == frame.content_hash
        return {
            "width": frame.width,
            "height": frame.height,
            "timestamp_ms": frame.timestamp_ms,
            "content_hash": frame.content_hash,
            "unchanged": frame.unchanged or unchanged_vs_client,
            "unchanged_vs_client": unchanged_vs_client,
            "blur": frame.blur,
            "backend": frame.backend,
            "change_score": frame.change_score,
            "bytes": len(frame.jpeg),
            "age_ms": svc.store.age_ms(),
        }

    @mcp.tool()
    def get_frame_history(
        limit: int = 20,
        changed_only: bool = False,
        min_change_score: float = 0.0,
    ) -> dict[str, Any]:
        """
        Return newest-first frame metadata from the watch ring buffer (no image bytes).

        Useful to see when the desktop last changed without paying image tokens.
        min_change_score: keep entries whose change_score is at least this value.
        """
        svc = get_service()
        entries = svc.store.history(
            limit=limit,
            changed_only=changed_only,
            min_change_score=min_change_score,
        )
        return {
            "count": len(entries),
            "history_len": svc.store.history_len(),
            "changed_only": changed_only,
            "min_change_score": min_change_score,
            "entries": entries,
        }

    @mcp.tool()
    def get_display_frame(
        display_id: int,
        blur: bool = False,
        since_hash: str = "",
    ) -> Any:
        """
        Capture a specific monitor by id (from list_displays).

        since_hash: skip image bytes when the hash still matches.
        """
        svc = get_service()
        frame = svc.capture_once(blur=blur if blur else None, display_id=display_id)
        meta = {
            "width": frame.width,
            "height": frame.height,
            "timestamp_ms": frame.timestamp_ms,
            "content_hash": frame.content_hash,
            "unchanged": frame.unchanged,
            "blur": frame.blur,
            "backend": frame.backend,
            "display_id": frame.display_id,
        }
        if since_hash and since_hash == frame.content_hash:
            return {"unchanged": True, "skipped_image": True, **meta}
        return _image_result(frame.jpeg, meta)

    @mcp.tool()
    def bench_capture(iterations: int = 5, display_id: int = 0) -> dict[str, Any]:
        """Measure local grab+encode latency (ms). display_id 0 = default/primary."""
        svc = get_service()
        target = None if display_id <= 0 else display_id
        return svc.bench(iterations=iterations, display_id=target)

    @mcp.tool()
    def wait_for_change(
        since_hash: str = "",
        min_change_score: float = 0.0,
        timeout_s: float = 30.0,
        poll_s: float = 0.25,
    ) -> dict[str, Any]:
        """
        Block until the desktop changes vs ``since_hash`` (or the current frame).

        Prefer ``start_watch`` first. Caps at 120s. Returns metadata only (no image).
        """
        return get_service().wait_for_change(
            since_hash=since_hash,
            min_change_score=min_change_score,
            timeout_s=timeout_s,
            poll_s=poll_s,
        )

    @mcp.tool()
    def save_latest_frame(
        path: str = "",
        blur: bool = False,
        force_capture: bool = False,
    ) -> dict[str, Any]:
        """
        Write the latest JPEG to a local filesystem path (no image tokens in the reply).

        path: destination file; empty → OS data dir / latest.jpg
        force_capture: ignore store and grab a fresh frame
        """
        from pathlib import Path

        from screen_watch.config import data_dir

        svc = get_service()
        out = Path(path) if path.strip() else data_dir() / "latest.jpg"
        return svc.save_frame_to(out, blur=blur if blur else None, force_capture=force_capture)

    @mcp.tool()
    def list_tools() -> dict[str, Any]:
        """Return the canonical screen-watch MCP tool catalog (names only)."""
        return {"tools": list(TOOL_NAMES), "count": len(TOOL_NAMES)}

    @mcp.tool()
    def start_watch(display_id: int = 0) -> dict[str, Any]:
        """
        Start the background watch daemon (keeps latest frame fresh).

        display_id: 1-based monitor from list_displays; 0 keeps current/primary.
        """
        svc = get_service()
        if display_id > 0:
            svc.set_display(display_id)
        started = svc.daemon.start()
        return {"ok": True, "started": started, "status": svc.status()}

    @mcp.tool()
    def stop_watch() -> dict[str, Any]:
        """Stop the background watch daemon."""
        svc = get_service()
        stopped = svc.daemon.stop()
        return {"ok": True, "stopped": stopped, "status": svc.status()}

    @mcp.tool()
    def set_capture_display(display_id: int = 0) -> dict[str, Any]:
        """
        Set default monitor for watch / get_latest_frame (1-based; 0 = primary/auto).
        """
        svc = get_service()
        return svc.set_display(None if display_id <= 0 else display_id)

    @mcp.tool()
    def get_watch_status() -> dict[str, Any]:
        """Return watch/daemon status and last frame metadata."""
        svc = get_service()
        data = svc.status()
        data["privacy"] = privacy_blurb()
        return data

    @mcp.tool()
    def list_displays() -> list[dict[str, Any]]:
        """List available monitors."""
        return get_service().list_displays()

    @mcp.tool()
    def get_advisor_summary() -> dict[str, Any]:
        """PC capacity advice + preferred LLM cost estimates (local, optional)."""
        state = load_advisor_state()
        profile = state.get("profile") or recommend_settings(profile_machine())
        if "profile" not in state:
            state["profile"] = profile
            save_advisor_state(state)
        model_id = state.get("preferred_llm") or get_service().settings.preferred_llm or "gpt-4o"
        costs = estimate_session_cost(model_id)
        return {
            "capacity": profile,
            "preferred_llm": model_id,
            "costs": costs,
            "privacy": privacy_blurb(),
        }

    @mcp.tool()
    def set_preferred_llm(model_id: str) -> dict[str, Any]:
        """Persist the user's preferred vision LLM for cost estimates."""
        state = load_advisor_state()
        state["preferred_llm"] = model_id
        save_advisor_state(state)
        return {"ok": True, "preferred_llm": model_id, "costs": estimate_session_cost(model_id)}

    @mcp.tool()
    def run_capacity_profile() -> dict[str, Any]:
        """Refresh local machine profile and recommendations (never blocks)."""
        rec = recommend_settings(profile_machine())
        state = load_advisor_state()
        state["profile"] = rec
        save_advisor_state(state)
        return rec

    @mcp.tool()
    def list_llm_models() -> list[dict[str, Any]]:
        """List built-in vision LLM catalog for the cost advisor."""
        return list_models()

    @mcp.tool()
    def start_recording(title: str = "") -> dict[str, Any]:
        """
        Start an opt-in local recording session (off unless recording.enabled).

        Returns capacity advice but never refuses for hardware reasons.
        When the watch daemon is already running, recording taps its FrameStore
        instead of opening a second capture loop.
        """
        svc = get_service()
        shared = svc.store if svc.daemon.running else None
        return _get_recorder().start(title=title or None, shared_store=shared)

    @mcp.tool()
    def stop_recording() -> dict[str, Any]:
        """Stop the active recording session and flush timeline sync hooks."""
        return _get_recorder().stop()

    @mcp.tool()
    def list_recordings() -> list[dict[str, Any]]:
        """List local recording sessions (branch-like artifacts)."""
        return _get_recorder().list_sessions()

    @mcp.tool()
    def get_recording_timeline(session_id: str) -> dict[str, Any]:
        """Return timeline + sync hooks for a recording (agent supplies its own STT)."""
        return _get_recorder().get_timeline(session_id)

    @mcp.tool()
    def list_recording_keyframes(session_id: str, limit: int = 50) -> dict[str, Any]:
        """List changed JPEG paths for a recording session (no image bytes)."""
        return _get_recorder().list_keyframes(session_id, limit=limit)

    @mcp.tool()
    def get_recording_keyframe(session_id: str, file: str) -> Any:
        """
        Load one recording keyframe JPEG by relative path (from list_recording_keyframes).

        Example file: ``frames/frame_000000.jpg``
        """
        result = _get_recorder().read_keyframe(session_id, file)
        if not result.get("ok"):
            return result
        jpeg = result.pop("jpeg")
        return _image_result(jpeg, result)

    @mcp.tool()
    def delete_recording(session_id: str) -> dict[str, Any]:
        """Delete a finished local recording session directory."""
        return _get_recorder().delete_session(session_id)

    @mcp.tool()
    def attach_recording_context(session_id: str) -> dict[str, Any]:
        """Return recording meta/timeline suitable for injecting into agent context."""
        data = _get_recorder().get_timeline(session_id)
        if "error" in data:
            return data
        # Compact: omit binary; keep hooks + frame index
        frames = data.get("frames", [])
        return {
            "session_id": data.get("session_id"),
            "title": data.get("title"),
            "sync_hooks": data.get("sync_hooks"),
            "frame_count": data.get("frame_count"),
            "sample_keyframes": [f for f in frames if not f.get("unchanged")][:20],
            "note": "No transcript from screen-watch — attach your agent STT using sync_hooks.",
        }

    @mcp.tool()
    def get_region_frame(
        x: int,
        y: int,
        width: int,
        height: int,
        blur: bool = False,
    ) -> Any:
        """
        Capture a region by bbox (screen/capture pixels) for lower token use.

        Returns the cropped JPEG. Prefer guided_region_focus for interactive selection.
        """
        from screen_watch.focus.region import BBox

        svc = get_service()
        result = svc.capture_region(BBox(x, y, width, height), blur=blur, also_full_frame=False)
        return _image_result(
            result["region_jpeg"],
            {"gesture": result["gesture"], "width": result["region_width"], "height": result["region_height"]},
        )

    @mcp.tool()
    def guided_region_focus(blur: bool = False) -> dict[str, Any]:
        """
        Flash an overlay; user drags a loose box; returns gesture + region JPEG (base64).

        The agent should infer the precise UI element from the loose gesture + pixels.
        Blocks until release (accept) or Esc (cancel). Also saves under latest_focus/.
        """
        from screen_watch.focus.hotkey import load_latest_focus
        from screen_watch.focus.runner import run_guided_focus

        result = run_guided_focus(blur=blur if blur else None)
        if not result.get("ok"):
            return {"ok": False, "cancelled": True}
        latest = load_latest_focus() or {}
        return {
            "ok": True,
            "cancelled": False,
            "gesture": result["gesture"],
            "dir": result.get("dir"),
            "region": {
                "width": result["region_width"],
                "height": result["region_height"],
                "mime": "image/jpeg",
                "base64": latest.get("region_b64"),
            },
            "full_frame": None
            if not latest.get("full_b64")
            else {"mime": "image/jpeg", "base64": latest["full_b64"]},
            "note": result["note"],
        }

    @mcp.tool()
    def get_latest_focus() -> dict[str, Any]:
        """Return the last guided-focus artifacts (from hotkey or guided_region_focus)."""
        from screen_watch.focus.hotkey import load_latest_focus

        data = load_latest_focus()
        if data is None:
            return {"ok": False, "error": "No focus artifacts yet"}
        return {"ok": True, **data}

    @mcp.tool()
    def doctor() -> dict[str, Any]:
        """Report install, capture backend, and optional tool availability."""
        from screen_watch.doctor import run_doctor

        return run_doctor()

    return mcp


def run_server() -> None:
    """Run MCP over stdio (default for Cursor / Claude Code)."""
    configure_logging(get_service().settings.log_level)
    logger.info("Starting screen-watch MCP server")
    mcp = build_server()
    mcp.run()
