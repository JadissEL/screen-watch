# Performance checklist

Defaults are already conservative (1280×720 @ 5 FPS, JPEG 60, change-detect).

## Before raising FPS / resolution

1. Run `python -m screen_watch advise` — heed CPU / RAM / disk warnings (advisory only).
2. Prefer `start_watch` + `get_latest_frame_info` polling; only pull JPEG when `content_hash` changes.
   Or call `get_latest_frame(since_hash=<last>)` — matching hash returns a tiny JSON stub (no image tokens).
3. Use `get_region_frame` / `guided_region_focus` for UI work — crops beat full desktop for tokens and encode time.
4. Keep `SCREEN_WATCH_MIN_CAPTURE_INTERVAL` ≥ 0.1s unless you measured a need (default 0.12).
5. Leave `SCREEN_WATCH_IDLE_BACKOFF=true` (default) so a static desktop backs off toward 4× the base interval.
6. On Windows gaming PCs, try `SCREEN_WATCH_BACKEND=dxcam` after `pip install "screen-watch[windows]"`.
7. Avoid concurrent one-shot grabs from multiple agent turns — the grab lock serializes; stampeding still wastes time.
8. Recording is heavier than watch: leave `SCREEN_WATCH_RECORDING_ENABLED=false` unless reviewing a session.

## Encode cost (local)

| Knob | Effect |
|------|--------|
| max_width / max_height | Dominates downsample + JPEG time |
| jpeg_quality | Quality 40–70 is usually enough for UI OCR/VLM |
| change_threshold | Higher → fewer “changed” frames through the daemon |
| blur | Extra pixelate pass; does **not** shrink tokens |

## Not yet in-tree

Native ScreenCaptureKit / PipeWire screencast streams — see [CONTINUOUS_CAPTURE.md](CONTINUOUS_CAPTURE.md). `FramePump` is the timed continuous seam today.
