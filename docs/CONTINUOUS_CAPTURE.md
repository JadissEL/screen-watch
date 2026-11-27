# Continuous capture roadmap

Today every backend is still **snapshot-based** (`grab()` / portal / `screencapture`), but continuous loops go through **FramePump → FrameStream**.

## Current seam

`screen_watch.capture.loop.FramePump` is the continuous API surface:

- opens a `FrameStream` via `open_capture_stream()` (from v0.2.16)
- default: `SnapshotFrameStream` (grab-per-tick wrapper)
- yields processed `EncodedFrame`s at capped FPS
- applies shared idle backoff (`screen_watch.backoff`)
- **WatchDaemon** consumes FramePump into `FrameStore` (from v0.2.4)
- **RecordingManager** consumes FramePump (fps capped at 3) with `force_keyframe()` (from v0.2.5)
- When watch is already running, recording **taps** that `FrameStore` instead of a second grab loop (from v0.2.6)

### Plugging a native stream

Implement `open_stream(display_id) -> FrameStream` on a backend (`read()` / `close()`).
FramePump prefers that over `SnapshotFrameStream`. MCP tools stay unchanged.

## Planned native streams (not shipped)

| Platform | Target | Status |
|----------|--------|--------|
| Windows | DXCam / Desktop Duplication streaming | **`DxcamFrameStream`** via `start()` + `get_latest_frame()` (v0.2.17); snapshot fallback |
| macOS | ScreenCaptureKit stream | `open_stream` → SnapshotFrameStream (Quartz/screencapture); SCStream TBD |
| Linux | PipeWire screencast portal | `open_stream` → SnapshotFrameStream (grim/portal); PW reader TBD |

Observation-only constraint remains: no input injection.
