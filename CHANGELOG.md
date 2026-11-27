# Changelog

## 0.2.3 — 2026-11-27

- `FramePump` continuous grab seam (`capture/loop.py`) + CONTINUOUS_CAPTURE.md roadmap
- MCP `get_recording_keyframe` (safe path-checked JPEG load)

## 0.2.2 — 2026-11-27

- Recording: `delete_recording`, `list_recording_keyframes`; idle backoff while recording
- MCP prompt `observation_workflow`; docs/PYPI.md for future publish

## 0.2.1 — 2026-11-27

- Watch **idle backoff** (default on): slows capture while the desktop is unchanged
- `get_frame_history(min_change_score=…)` filter; status exposes `unchanged_streak`
- CI concurrency group to avoid cancelled matrix jobs stomping each other

## 0.2.0 — 2026-11-25

- **Stable MCP surface** documented in `docs/STABLE_API.md`
- `change_score` on frames / history / status (mean-abs thumb diff)
- CI/release Actions bumped to checkout/setup-python/upload-artifact **v7**

## 0.1.13 — 2026-11-25

- Frame metadata ring buffer + MCP `get_frame_history` (`changed_only`)
- CLI `watch` foreground daemon; `SCREEN_WATCH_HISTORY_SIZE` / config.toml `history_size`

## 0.1.12 — 2026-11-25

- Virtual-screen geometry via mss on non-Windows (better multi-monitor focus)
- MCP `get_version`; root `SECURITY.md`; Dependabot; agent usage example
- Fix release workflow (invalid secrets `if` broke Actions on main)

## 0.1.11 — 2026-11-25

- `start_watch(display_id)` + MCP `set_capture_display`; status exposes `display`
- CI wheel smoke build; issue templates; PyPI publish only when token is set

## 0.1.10 — 2026-11-25

- MCP resources: `screen://privacy`, `screen://status`, `screen://tools`
- CLI `once --display`; docs/MCP.md
- Pin ruff lint rule set in `pyproject.toml` so CI stays deterministic

## 0.1.9 — 2026-11-25

- Optional user `config.toml` (env still wins); example under `examples/`
- MCP `get_display_frame` + `bench_capture`; CLI `bench`
- Docs: config precedence

## 0.1.8 — 2026-11-25

- Focus overlay covers the full **virtual desktop** on Windows (multi-monitor)
- `examples/poll_since_hash.py` agent polling demo
- CI runs `ruff check`; doctor reports repo URL + min capture interval

## 0.1.7 — 2026-11-25

- `get_latest_frame(since_hash=…)` / `get_latest_frame_info` — skip image tokens when hash matches
- `project.urls` (Homepage / Repository / Issues / Changelog)
- GitHub Actions `release.yml` (build artifacts; PyPI on `v*` tags when token set)
- Public repo: https://github.com/JadissEL/screen-watch

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
