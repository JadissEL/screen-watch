# Architecture

```
Display → CaptureBackend (mss / dxcam / …)
       → downsample (≤1280×720)
       → optional blur
       → change-detect
       → JPEG encode
       → FrameStore
       → MCP tools / watch daemon / recording sessions
```

- **MCP** is identical on every OS; only the capture factory differs.
- **Observation only** — no input injection.
- **Local only** — no upload path in the product.
