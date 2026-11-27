# Continuous capture roadmap

Today every backend is **snapshot-based** (`grab()` / portal / `screencapture`). Continuous loops go through **FramePump**.

## Current seam

`screen_watch.capture.loop.FramePump` is the continuous API surface:

- yields processed `EncodedFrame`s at capped FPS
- applies shared idle backoff (`screen_watch.backoff`)
- **WatchDaemon** consumes FramePump into `FrameStore` (from v0.2.4)
- **RecordingManager** consumes FramePump (fps capped at 3) with `force_keyframe()` for disk JPEGs (from v0.2.5)
- backends can later replace the inner `grab()` with a native stream reader without changing MCP tools

## Planned native streams (not shipped)

| Platform | Target | Status |
|----------|--------|--------|
| Windows | DXCam / Desktop Duplication streaming | Snapshot via dxcam today |
| macOS | ScreenCaptureKit stream | `screencapture` / Quartz stills today |
| Linux | PipeWire screencast portal | grim / portal Screenshot stills today |

Observation-only constraint remains: no input injection.
