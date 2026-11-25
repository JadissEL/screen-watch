# Changelog

## 0.1.6 — 2026-11-25

- Configurable `SCREEN_WATCH_MIN_CAPTURE_INTERVAL` (wired into grab gate)
- MCP `save_latest_frame` (path write, no image tokens) + `list_tools`
- `docs/PERF.md` checklist; `py.typed`; tools catalog for tests
- Status exposes `min_capture_interval_s`

## 0.1.5 — 2026-11-25

- Grab lock + min-interval gate on capture paths
- MCP `get_latest_frame_info` (metadata without image tokens)
- Portal URI helpers extracted + unit tested
- `docs/SECURITY.md`

## 0.1.4 — 2026-11-25

- Linux: xdg-desktop-portal Screenshot via `gdbus` when grim is missing
- macOS: optional Quartz via `pip install screen-watch[macos]` (pyobjc)
- Mock capture backend + headless service tests

## 0.1.3 — 2026-11-25

- macOS capture prefers system **`screencapture`**, else mss
- `screen-watch doctor` + MCP `doctor` for capability report
- CI workflow (Wolt monorepo + standalone copy under `screen-watch/.github`)
- CONTRIBUTING.md

## 0.1.2 — 2026-11-25

- Guided focus uses **virtual-desktop** capture so multi-monitor gestures map correctly
- Linux backend tries **grim** when available, else mss
- Global hotkeys on macOS/Linux via optional **`pynput`** (`pip install screen-watch[hotkey]`)
- Windows hotkeys unchanged (Win32 `RegisterHotKey`)

## 0.1.1 — 2026-11-25

- Windows global hotkey daemon (`screen-watch hotkey`)
- `get_latest_focus` MCP tool; focus artifacts under `latest_focus/`
- Overlay accepts on mouse release

## 0.1.0 — 2026-11-25

- Initial release: mss capture, JPEG pipeline, change-detect, blur, MCP watch tools, advisor, opt-in recording, guided region focus v1
