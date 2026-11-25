# MCP surface

Transport: **stdio** (`python -m screen_watch serve`). Observation only.

## Resources

| URI | Content |
|-----|---------|
| `screen://privacy` | Privacy blurb (text) |
| `screen://status` | Watch/capture status JSON |
| `screen://tools` | Tool name catalog JSON |

## Tools

| Tool | Notes |
|------|-------|
| `get_version` | Package version + repo |
| `get_latest_frame` | JPEG; `blur`, `since_hash` |
| `get_latest_frame_info` | Metadata only; `since_hash` |
| `get_frame_history` | Ring-buffer metadata (no images); `changed_only` |
| `get_display_frame` | Specific monitor id |
| `save_latest_frame` | Write JPEG to disk path |
| `bench_capture` | Local latency ms |
| `start_watch` / `stop_watch` / `get_watch_status` | Daemon (`start_watch(display_id=…)`) |
| `set_capture_display` | Default monitor for watch / latest frame |
| `list_displays` | Monitors |
| `list_tools` | Same catalog as `screen://tools` |
| `get_advisor_summary` / `set_preferred_llm` / `run_capacity_profile` / `list_llm_models` | Local advisor |
| `start_recording` / `stop_recording` / `list_recordings` / `get_recording_timeline` / `attach_recording_context` | Opt-in sessions |
| `get_region_frame` / `guided_region_focus` / `get_latest_focus` | Region focus |
| `doctor` | Install / backend report |

Canonical names live in `screen_watch.mcp.tools_catalog.TOOL_NAMES` (kept in sync by tests).  
Compatibility promise: [STABLE_API.md](STABLE_API.md) (from **v0.2.0**).

## Token tips

1. `start_watch` then poll `get_latest_frame_info` / `get_latest_frame(since_hash=…)`.
2. Prefer crops (`get_region_frame` / guided focus) over full desktop.
3. Use `save_latest_frame` when the host cannot ingest image content.
