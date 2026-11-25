# Configuration

Precedence: **constructor / MCP overrides** → **environment** → **`config.toml`** → built-in defaults.

## Config file

Optional TOML at:

- Windows: `%APPDATA%\screen-watch\config.toml`
- macOS/Linux: `~/.config/screen-watch/config.toml`
- Or `SCREEN_WATCH_CONFIG=/path/to/file.toml`

Example: [examples/config.toml](../examples/config.toml).

## Environment variables (all optional)

| Variable | Default | Meaning |
|----------|---------|---------|
| `SCREEN_WATCH_MAX_WIDTH` | 1280 | Capture box width |
| `SCREEN_WATCH_MAX_HEIGHT` | 720 | Capture box height |
| `SCREEN_WATCH_FPS` | 5 | Watch/record target FPS (capped at 5) |
| `SCREEN_WATCH_JPEG_QUALITY` | 60 | JPEG quality |
| `SCREEN_WATCH_CHANGE_THRESHOLD` | 2.0 | Change-detect sensitivity |
| `SCREEN_WATCH_BACKEND` | auto | `auto` \| `mss` \| `dxcam` \| `sck` \| `pipewire` |
| `SCREEN_WATCH_DISPLAY` | (primary) | 1-based monitor index |
| `SCREEN_WATCH_BLUR` | false | Default blur |
| `SCREEN_WATCH_RECORDING_ENABLED` | false | Allow recording tools |
| `SCREEN_WATCH_RECORDINGS_DIR` | OS data dir | Session storage |
| `SCREEN_WATCH_PREFERRED_LLM` | — | Advisor default model id |
| `SCREEN_WATCH_FOCUS_HOTKEY` | ctrl+shift+f | Global focus hotkey (Windows `hotkey` command) |
| `SCREEN_WATCH_MIN_CAPTURE_INTERVAL` | 0.12 | Min seconds between MCP/CLI one-shot grabs |
| `SCREEN_WATCH_HISTORY_SIZE` | 64 | Metadata ring buffer size for `get_frame_history` |
| `SCREEN_WATCH_CONFIG` | (default path) | Override path to `config.toml` |
| `SCREEN_WATCH_LOG_LEVEL` | INFO | Logging (stderr only) |
