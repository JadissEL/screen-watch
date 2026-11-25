# Privacy

- screen-watch **never** controls mouse or keyboard.
- Frames stay **on this machine** (MCP stdio to your chosen agent host).
- **Blur** is off by default; enable per `get_latest_frame(blur=true)`.
- Prefer `get_latest_frame_info` when you only need dimensions/hash (no image tokens).
- **Recording** is off until `SCREEN_WATCH_RECORDING_ENABLED=1`. Recordings stay under your data directory unless you export them.
- Anything visible on screen (passwords, secrets) can be seen by any agent connected to this MCP server.
- Advisor profiles and preferred LLM id are stored locally under the OS config directory.
