# Continuous capture roadmap

Today every backend is **snapshot-based** (`grab()` / portal / `screencapture`). The watch daemon and recording loop call grab on a timer.

## Current seam

`screen_watch.capture.loop.FramePump` is the continuous API surface:

- yields processed `EncodedFrame`s at capped FPS
- applies the same idle backoff as the watch daemon
- backends can later replace the inner `grab()` with a native stream reader without changing MCP tools

## Planned native streams (not shipped)

| Platform | Target | Status |
|----------|--------|--------|
| Windows | DXCam / Desktop Duplication streaming | Snapshot via dxcam today |
| macOS | ScreenCaptureKit stream | `screencapture` / Quartz stills today |
| Linux | PipeWire screencast portal | grim / portal Screenshot stills today |

Observation-only constraint remains: no input injection.
