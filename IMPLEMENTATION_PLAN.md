# screen-watch — Implementation Plan

**Status:** Decisions locked — **P0–P3 implemented in-tree (v0.1.0).** Native DXCam/SCK/PipeWire still optional/fallback; guided region focus remains wishlist.  
**Goal:** Production-quality, publicly visible, cross-platform, read-only desktop observation for AI agents via MCP.

---

## 1. Language & project layout

### Recommendation: **Python 3.11+** for v1

| Criterion | Python | Rust |
|-----------|--------|------|
| Official MCP SDK | Mature (`mcp` / modelcontextprotocol python-sdk, FastMCP patterns) | Mature (`rmcp`) |
| Capture libs | **mss** (all OS), **dxcam** (Windows), Pillow; macOS via pyobjc/ScreenCaptureKit bindings or mss fallback; Linux PipeWire via `pipewire`/`python-pipewire` or subprocess + portal | Strong native APIs, more glue per OS |
| Packaging | `pip` / `uv` / PyPI — agents install in minutes | `cargo install` — great binary, heavier contrib barrier |
| Maintainability | Faster iteration, wider MCP contributor pool | Best raw perf; longer bootstrap |

**Why Python first:** MCP is the product surface; the official Python SDK + FastMCP keeps the server thin and idiomatic. Capture can still be high-quality (DXCam on Windows, ScreenCaptureKit bridge on macOS, PipeWire on Linux) behind one abstract interface. If profiling later shows Python is the bottleneck, extract a small native capture helper (Rust/C) without changing MCP tools.

**Defer Rust rewrite** unless v1 fails CPU/latency targets after encode + change-detection are tuned.

### Proposed layout

```
screen-watch/
  README.md                 # user-facing (expand from concept)
  IMPLEMENTATION_PLAN.md    # this document
  pyproject.toml            # package: screen-watch / screen_watch
  src/screen_watch/
    __init__.py
    __main__.py             # python -m screen_watch
    cli.py                  # argparse / typer entry
    config.py               # settings load/validate
    logging_setup.py
    capture/
      __init__.py
      base.py               # CaptureBackend protocol
      factory.py            # pick backend by platform + config
      mss_backend.py        # portable fallback (Win/macOS/Linux)
      dxcam_backend.py      # Windows high-perf
      screencapturekit.py    # macOS (pyobjc or thin wrapper)
      pipewire_backend.py   # Linux
    pipeline/
      __init__.py
      downsample.py
      encode.py             # JPEG (v1); optional WebP later
      change_detect.py      # hash / perceptual diff
      frame_store.py        # latest encoded frame + metadata
    daemon/
      watcher.py            # background capture loop
    advisor/                # P2 — optional PC profiler + LLM cost selector
      profiler.py
      llm_catalog.py
      cost_estimate.py
      store.py              # local machine profile + chosen model
    mcp/
      server.py             # MCP tools + resources
      tools.py              # get_latest_frame, start/stop_watch, status
    privacy.py              # local-only assertions / redaction hooks
  tests/
    unit/ …
    integration/ …
  docs/
    ARCHITECTURE.md
    PRIVACY.md
    CONFIG.md
    TOKEN_COSTS.md          # vision token/cost comparison for advisor (doc, not runtime fetch)
```

Public package name: **`screen-watch`** (CLI / module: `screen_watch`).

---

## 2. Module breakdown

### 2.1 Capture backend abstraction

```text
CaptureBackend
  list_displays() -> list[DisplayInfo]
  grab(display_id | primary, max_width?, max_height?) -> RawFrame  # RGB/BGR ndarray or bytes + size
  name / capabilities
```

| Platform | Primary | Fallback |
|----------|---------|----------|
| Windows | **DXCam** (Desktop Duplication) | **mss** |
| macOS | **ScreenCaptureKit** (via pyobjc or thin helper) | **mss** |
| Linux | **PipeWire** (xdg-desktop-portal screen cast where required) | **mss** |

Factory selects by `sys.platform` + config override (`capture.backend = auto|dxcam|mss|sck|pipewire`). Missing optional deps → log warning → fallback; never crash the MCP process on import.

**RawFrame:** width, height, pixel format, timestamp, display_id. No file I/O on hot path.

### 2.2 Pipeline (always on before agent sees pixels)

1. **Downscale** — longest edge ≤ `max_dimension` (default e.g. 1280); keep aspect ratio.  
2. **Change-detect** — compare to last accepted frame (aHash / mean-hash or downscaled grayscale MSE). If below `change_threshold`, skip encode & mark `unchanged=true`.  
3. **Encode** — JPEG quality `jpeg_quality` (default ~70); optional WebP later.  
4. **FrameStore** — atomic replace of `{ jpeg_bytes, width, height, ts, content_hash, unchanged }`.

### 2.3 MCP server

Transport: **stdio** (Cursor / Claude Code default). Optional SSE later — not v1.

| Tool | Behavior |
|------|----------|
| `get_latest_frame` | If daemon running: return store (or “unchanged” stub). Else: one-shot grab → pipeline → return. Prefer **image content** in MCP response; optional `path` write under temp only if requested. |
| `start_watch` | Start watch-daemon (interval = `fps` capped). Idempotent. |
| `stop_watch` | Stop daemon. |
| `get_watch_status` | Running?, last frame age, backend, resolution, last change time. |
| `list_displays` | Enumerate monitors for targeting. |

**Watch-daemon:** asyncio/thread loop at target FPS (default **1–2 fps**, hard cap e.g. 5). Runs pipeline each tick; CPU stays low via downscale + change-detect short-circuit.

MCP layer **identical** on all OS; only `factory` + backend modules differ.

### 2.4 CLI

- `screen-watch` / `python -m screen_watch` → MCP stdio server (default for agent config).  
- `screen-watch once` → smoke: capture + save JPEG (dev).  
- `screen-watch status` → print config + backend availability.

---

## 3. Performance requirements

| Constraint | Target / approach |
|------------|-------------------|
| User PC impact | Negligible at default 1–2 fps + change-detect |
| Capture res | Fit within **1280×720** (default); never send full 4K/5K raw |
| Target FPS | Default **5** (daemon phase); configurable |
| Wire size | JPEG quality **60** default (or WebP later); typical tens–low hundreds KB |
| Sending | Change-only: tool may return `{ unchanged: true, age_ms }` without image bytes |
| Hot path | No unnecessary copies; reuse buffers where backends allow |
| GPU | Prefer DXCam / SCK / PipeWire desktop paths; do not force GPU encode in v1 |
| Backpressure | If encode lags, drop intermediate grabs; always keep *latest* |

Document defaults in CONFIG; expose overrides without restart where safe (daemon restart for FPS).

---

## 4. Config, logging, errors

### Config (precedence: CLI > env `SCREEN_WATCH_*` > config file > defaults)

Example keys:

- `display` — primary | index | id  
- `max_dimension` — int (default 1280)  
- `fps` — float (default 1.0, max 5)  
- `jpeg_quality` — 40–95 (default 70)  
- `change_threshold` — sensitivity  
- `backend` — auto | …  
- `log_level` — INFO default  

File: `~/.config/screen-watch/config.toml` (XDG) / `%APPDATA%\screen-watch\config.toml`.

### Logging

- stdlib `logging` → stderr only (never corrupt MCP stdio JSON-RPC on stdout).  
- Structured optional (`LOG_FORMAT=json`).  
- No pixel data in logs.

### Error handling

- Backend failures → clear MCP error + `get_watch_status` shows last error.  
- Permission denied (macOS Screen Recording / Linux portal) → actionable message.  
- Never exit mid-session on a single bad frame; retry with backoff.  
- Typed exceptions at boundaries (`CaptureError`, `EncodeError`, `ConfigError`).

---

## 5. Testing strategy

| Layer | What |
|-------|------|
| Unit | Downscale sizes; JPEG round-trip; change-detect identical vs different; config parse/validate; FrameStore atomicity |
| Backend | Mock `CaptureBackend`; platform tests marked `@pytest.mark.platform_win` etc., skip CI without display |
| MCP | In-memory / stdio client fixture: tool schemas, `get_latest_frame` shape, start/stop watch |
| Smoke (manual) | Each OS: Cursor MCP connect + one frame; daemon + static desktop → unchanged |
| Perf (optional) | Script: CPU % over 60s at 1 fps idle desktop |

CI: Linux unit + mocks; Windows/macOS via optional runners or contributor checklist. No secret/env dependency.

---

## 6. Docs & packaging

### Packaging

- `pyproject.toml` (hatchling or uv), console script `screen-watch`.  
- Extras: `screen-watch[windows]` → dxcam; `[macos]` → pyobjc bits; `[linux]` → pipewire deps; `[all]`. Core always includes **mss** + Pillow + mcp.  
- Publish: PyPI when Jadiss approves public release.  
- Version: semver; CHANGELOG.md.

### Docs

- **README** — install, Cursor MCP JSON snippet, privacy one-liner, non-goals.  
- **ARCHITECTURE.md** — diagram of capture → pipeline → store → MCP.  
- **PRIVACY.md** — local-only, what is stored, retention (in-memory / optional temp).  
- **CONFIG.md** — all knobs.  
- GitHub: LICENSE (recommend MIT or Apache-2.0), CONTRIBUTING, CODE_OF_CONDUCT when going public.

Cursor example (illustrative):

```json
{
  "mcpServers": {
    "screen-watch": {
      "command": "uvx",
      "args": ["screen-watch"]
    }
  }
}
```

---

## 7. Security & privacy

| Rule | Detail |
|------|--------|
| Local-only | No network client in v1; MCP stdio only. Refuse any “upload frame” feature. |
| Observation only | No mouse/keyboard APIs; code review gate against input injection deps. |
| Data residency | Frames in process memory; optional temp file only if tool requests path; wipe on stop. |
| Permissions | Document OS prompts (macOS Screen Recording, Windows, PipeWire portal). |
| Agent trust | User chooses which agent host can call MCP; document that *any* connected agent can see the screen. |
| Secrets on screen | No OCR/exfil extras in v1; warn in PRIVACY.md that passwords visible on screen are visible to the agent. |
| Blur toggle | Optional **screen blur / pixelation** (full frame or region) via MCP tool flag; **off by default**. No “firepad” concept. |
| Supply chain | Pin deps; minimal dependency set; optional SBOM later. |
| Recordings (later) | **Off by default.** No session files unless the user explicitly starts recording. Artifacts stay on-disk locally unless the user chooses to share/export. |

---

## 8. Combined advisor module (P2 — optional, local, non-blocking)

Lightweight helper shipped **after P0 capture works**. Opt-in / on-demand; never required to use `get_latest_frame`. All data stays **local**. Advice is **never a gate** (same rule as recording capacity warnings).

### Part A — PC capacity profiler

- **When:** first run, or explicit refresh (`screen-watch advise` / MCP `run_capacity_profile`).
- **Collect (best-effort):** CPU model + core count, RAM, GPU if detectable, free/total disk.
- **Store locally** (e.g. `~/.config/screen-watch/machine_profile.json` / `%APPDATA%\screen-watch\`).
- **Advise:**
  - whether **recording** looks advisable on this machine (soft recommendation only);
  - recommended **capture settings** (resolution / FPS) matched to the hardware (may differ from the global defaults 1280×720 @ 5 FPS).
- Recording’s pre-start check (**§9**) should **reuse** this profiler rather than inventing a second capacity path.

### Part B — LLM selector + session cost estimate

- Built-in catalog of major **vision-capable** models (e.g. GPT-4o / GPT-4.1, Claude Sonnet / Opus, Gemini Flash / Pro, Qwen-VL, Llama vision variants). User picks **once** (stored locally; changeable later).
- Using `docs/TOKEN_COSTS.md` (static tables maintained in-repo — **no live price scraping** in the product), show for the **selected** model at screen-watch defaults (1280×720 JPEG q60, 5 FPS, change-detection ~30–50% of frames sent):
  - estimated **tokens per frame**
  - **cost per frame**
  - **cost per minute**
  - **cost per 10-minute session**
- Catalog entries include tokenizer method notes (tiles vs patches vs area) so estimates stay honest.

### MCP / CLI (P2)

| Surface | Behavior |
|---------|----------|
| `get_advisor_summary` | Profile snippet + selected model + cost estimates |
| `set_preferred_llm` | Persist user model choice |
| `run_capacity_profile` | Refresh machine profile; return advice |
| CLI `screen-watch advise` | Same summary for humans |

### Non-goals

- Not a cloud service; not telemetry; not auto-changing capture settings without user consent.
- Not blocking start of watch/record.
- Not shipping live billing APIs — costs are **estimates** from `TOKEN_COSTS.md`.

---

## 9. Optional recording mode (later phase)

**Not part of P0/P1.** Live watch (`get_latest_frame` / watch-daemon) must work with recording permanently disabled. Recording is an explicit opt-in feature for revisiting sessions—think **GitHub branches**: each recording is a named, durable artifact you can open later, review, and feed back into agent context.

### Requirements

1. **Off by default** — no screen registration, no disk writes for sessions unless the user explicitly enables/starts a recording. Config default: `recording.enabled = false`. MCP must not auto-start recording when the agent connects.
2. **While talking with the agent** — when the user starts a session, capture **screen video** (or an efficient frame timeline from the same capture pipeline; lower FPS / resolution than raw desktop is fine). **Speech-to-text is out of scope:** the user’s AI agent runs STT itself. screen-watch may expose **timing/sync hooks** (session start clock, frame timestamps, optional simple algorithm helpers for aligning agent-side transcript to the recording timeline) but must **not** run, bundle, or depend on any STT engine.
3. **Session artifacts (“branches”)** — each recording is a saved unit (id, title, started/ended, paths to media + timeline metadata). User can list, open, scrub/review, delete, and **attach a past session as context** for later agent turns or edits (e.g. MCP tool `list_recordings` / `get_recording_timeline` / `attach_recording_context`). Agent-owned transcripts can be associated by the agent using sync hooks—not produced by screen-watch.
4. **Privacy** — recordings remain **local** under a user-controlled directory (e.g. `~/screen-watch/recordings/`). No upload, sync, or telemetry. Share/export only via explicit user action.
5. **Performance** — recording path must not break the “don’t slow the PC” rules: capped FPS, compressed video (e.g. fragmented MP4 / WebM), reuse change-detection where useful.
6. **Pre-recording advisory (warning, not a gate)** — before a session starts, reuse the **P2 capacity profiler** (CPU load / disk / encoder). Surface a **non-blocking** advice message (e.g. “your PC may struggle with recording at this setting”). **Never refuse to start**.

### Suggested module sketch (implement only in recording phase)

```
src/screen_watch/recording/
  session.py       # start/stop, artifact layout
  mux.py           # video container
  timeline.py      # frame timestamps / sync hooks for agent-side STT
  store.py         # list/load/delete sessions (“branches”)
  # capacity checks → call advisor.profiler (P2), do not duplicate
```

### MCP surface (recording phase only)

| Tool | Notes |
|------|--------|
| `start_recording` / `stop_recording` | Explicit user/agent intent; confirm enabled in config; return any capacity **advice** but always allow start |
| `list_recordings` | Session index like branches |
| `get_recording_meta` / `get_recording_timeline` | Review + sync hooks for agent |
| `attach_recording_context` | Inject timeline / keyframe refs (not screen-watch transcripts) into agent context |

Watch tools stay independent; recording is additive.

### Phase placement

Target **P3** (after advisor + MCP polish in P2). Do not block P0/P1. If public launch polish should ship first, recording can slip to **P4**.

---

## 10. Phased delivery

| Phase | Deliverable |
|-------|-------------|
| **P0** | Package skeleton, config, logging, **mss** backend (pure Python V1), downsample + JPEG + change-detect + **optional blur**, `get_latest_frame`, tests — **recording absent / hard-off** |
| **P1** | Watch-daemon + start/stop/status tools; Cursor MCP docs — **still no recording** |
| **P2** | **Combined advisor** (PC capacity profiler + LLM selector / cost estimates) + **MCP server polish**; native backends (DXCam / ScreenCaptureKit / PipeWire) + extras; author/maintain `docs/TOKEN_COSTS.md` for the selector |
| **P3** | **Optional recording mode** — opt-in sessions, local video + timeline sync hooks (no bundled STT), pre-start advice via profiler, session store (“branches”), MCP list/attach tools; PRIVACY.md recording section |
| **P4** | PyPI, hardening, perf checklist; **own public GitHub repo** (done) |

---

## 11. Locked decisions (Jadiss — 2026-11-25)

| Topic | Choice |
|-------|--------|
| Language | **Python 3.11+** |
| Defaults | **1280×720**, **5 FPS**, **JPEG quality 60** — configurable via config/env/CLI |
| License | **MIT** |
| Repo | **Own public GitHub:** https://github.com/JadissEL/screen-watch (workspace folder may still live under Wolt locally) |
| Frame return | MCP **image blobs** primary; optional path later if needed |
| Privacy UI | Optional **blur/pixelation toggle** on MCP tools (**off by default**). No “firepad”. |
| STT | **Not in screen-watch** — agent-owned; sync hooks only in recording phase |
| Recording phase | **P3** (after native backends) |
| Recording media | Prefer **video + timeline metadata**; agent attaches its own transcript |
| Who starts recording | Agent may call `start_recording` **only if** user already set `recording.enabled` |
| Capacity advisory | Warn on high CPU / low disk / missing encoder; **never block** (thresholds tunable later) |
| Advisor module | **P2** — local PC profiler + LLM selector/cost estimates; optional; never blocks |
| Token/cost tables | Static `docs/TOKEN_COSTS.md` (maintained in-repo); no live price API in product |

---

## 12. Wishlist / enhancements (post-core)

Ideas below are **not** P0–P1 scope. They are tracked here so overlapping concepts stay merged instead of forking into duplicate workstreams.

### Guided region focus *(single merged feature)* — **v1 landed**

**Replaces** two formerly separate ideas: (1) region-of-interest capture and (2) guided focus / hover snap. Ship as **one** capability.

| Piece | Behavior | Status |
|-------|----------|--------|
| **Flash overlay** | `screen-watch focus` / MCP `guided_region_focus` — tkinter topmost overlay; drag loose box; Enter accept / Esc cancel | **Done (v1)** |
| **Payload to agent** | Gesture bbox + region JPEG (+ full frame in MCP JSON) | **Done** |
| **BBox-only crop** | MCP `get_region_frame(x,y,w,h)` | **Done** |
| **Vision snap** | Agent infers nearest UI element; no a11y-tree dependency | **Agent-side** |
| **Global hotkey** | Windows: `RegisterHotKey`. macOS/Linux: optional `pynput` (`[hotkey]` extra). Default Ctrl+Shift+F; artifacts in `latest_focus/` + MCP `get_latest_focus` | **Done** |
| **Multi-monitor focus** | Virtual-desktop grab + origin offset when cropping gestures; overlay spans virtual screen (Win) | **Done (0.1.2 / 0.1.8)** |
| **Linux Wayland** | `grim` when present, else mss | **Done (0.1.2)** |
| **macOS capture** | System `screencapture` when present, else mss (pyobjc SCK still future) | **Done (0.1.3)** |
| **Doctor / CI** | `doctor` CLI+MCP; GitHub Actions matrix | **Done (0.1.3)** |
| **True click-through** | Overlay must capture input while dragging; layered tool-window styles applied; not permanent click-through | Partial — OK by design while selecting |
| **Native SCK / PipeWire portal** | Quartz optional (`[macos]`); portal Screenshot via gdbus; full ScreenCaptureKit screencast stream still future | **Partial (0.1.4)** |
| **Mock backend** | Headless tests without a display | **Done (0.1.4)** |
| **Capture gating** | Serialize grabs + min interval; `get_latest_frame_info` | **Done (0.1.5)** |
| **P4 hardening slice** | Path export tool, tool catalog, PERF.md, configurable gate, py.typed | **Done (0.1.6)** |
| **since_hash + release CI** | Client hash short-circuit; project.urls; release workflow; public GitHub | **Done (0.1.7)** |
| **config.toml + per-display + bench** | User TOML config; `get_display_frame`; latency bench | **Done (0.1.9)** |
| **MCP resources + lint pin** | `screen://` resources; `once --display`; deterministic ruff select | **Done (0.1.10)** |

**Out of scope:** mouse/keyboard control of the desktop; permanent always-on overlay.

---

*P0 coding authorized for capture core; advisor is plan-locked for **P2** — no advisor product code until that phase.*
