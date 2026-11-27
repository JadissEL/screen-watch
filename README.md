# screen-watch

[![ci](https://github.com/JadissEL/screen-watch/actions/workflows/ci.yml/badge.svg)](https://github.com/JadissEL/screen-watch/actions/workflows/ci.yml)

Passive desktop watching for AI coding agents. **Observation only** — no click, type, or remote control.

**Repo:** https://github.com/JadissEL/screen-watch  

Local MCP server so Cursor, Claude Code, and similar agents can see your desktop while you talk — same spirit as Google AI Studio Share Screen / Stream.

## Install

```bash
# From GitHub (recommended while pre-PyPI)
pip install "git+https://github.com/JadissEL/screen-watch.git"

# Or clone + editable
git clone https://github.com/JadissEL/screen-watch.git
cd screen-watch
pip install -e ".[dev]"
```

Optional extras:

```bash
pip install -e ".[windows]"   # dxcam
pip install -e ".[macos]"     # Quartz via pyobjc
pip install -e ".[hotkey]"    # pynput (macOS/Linux global hotkeys)
```

## Quick use

```bash
# One-shot smoke capture (optional --display N)
python -m screen_watch once -o desk.jpg

# Capacity + LLM cost advice (local)
python -m screen_watch advise --model gpt-4o

# Backend / deps check
python -m screen_watch doctor

# Grab+encode latency
python -m screen_watch bench -n 5

# Foreground watch (logs content-hash changes)
python -m screen_watch watch --seconds 5

# MCP stdio server (default)
python -m screen_watch serve
```

(`screen-watch` console script works if your Python Scripts folder is on PATH.)

### Cursor MCP snippet

```json
{
  "mcpServers": {
    "screen-watch": {
      "command": "python",
      "args": ["-m", "screen_watch", "serve"]
    }
  }
}
```

## Defaults (configurable)

| Setting | Default |
|---------|---------|
| Resolution | 1280×720 |
| FPS | 5 |
| JPEG quality | 60 |
| Blur | off |
| Recording | off |

See [docs/CONFIG.md](docs/CONFIG.md).

## MCP tools

| Tool | Purpose |
|------|---------|
| `get_version` | Package version |
| `get_latest_frame` | Latest JPEG (`blur`, `since_hash` to skip identical frames) |
| `get_latest_frame_info` | Frame metadata only (no image bytes; supports `since_hash`) |
| `get_frame_history` | Recent frame metadata ring buffer (no images) |
| `get_display_frame` | Capture a specific monitor id |
| `save_latest_frame` | Write JPEG to a local path (no image tokens) |
| `bench_capture` | Local grab+encode latency (ms) |
| `list_tools` | Canonical tool name catalog |
| `start_watch` / `stop_watch` / `get_watch_status` | Background daemon (`display_id` optional) |
| `set_capture_display` | Default monitor for watch / latest |
| `list_displays` | Monitors |
| `get_advisor_summary` / `set_preferred_llm` / `run_capacity_profile` / `list_llm_models` | Local advisor |
| `start_recording` / `stop_recording` / `list_recordings` / `get_recording_timeline` / `list_recording_keyframes` / `delete_recording` / `attach_recording_context` | Opt-in local sessions |
| `guided_region_focus` / `get_region_frame` | Loose drag overlay or bbox crop; agent snaps to UI |

Interactive focus from a terminal:

```bash
python -m screen_watch focus -o region.jpg --gesture gesture.json

# Global hotkey (default Ctrl+Shift+F) opens the same overlay
python -m screen_watch hotkey
# or: python -m screen_watch hotkey --bind ctrl+shift+f
# macOS/Linux: pip install "screen-watch[hotkey]"  # pynput
```


Cursor example config: [examples/cursor-mcp.json](examples/cursor-mcp.json).  
Hash-poll demo: [examples/poll_since_hash.py](examples/poll_since_hash.py).

## Architecture sketch

1. **Capture** — cross-platform; **mss** always available; DXCam optional on Windows; SCK/PipeWire fall back to mss until native bindings land.
2. **Pipeline** — downsample → optional blur → change-detect → JPEG.
3. **MCP** — identical tool surface on every OS.

MCP reference: [docs/MCP.md](docs/MCP.md) · Stable API: [docs/STABLE_API.md](docs/STABLE_API.md). PyPI: [docs/PYPI.md](docs/PYPI.md). Performance: [docs/PERF.md](docs/PERF.md). Privacy: [docs/PRIVACY.md](docs/PRIVACY.md). Security: [docs/SECURITY.md](docs/SECURITY.md). Token costs: [docs/TOKEN_COSTS.md](docs/TOKEN_COSTS.md). Plan: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## License

MIT
