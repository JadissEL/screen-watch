"""Frame processing pipeline."""

from __future__ import annotations

from screen_watch.pipeline.frame_store import EncodedFrame, FrameStore
from screen_watch.pipeline.process import process_raw_frame

__all__ = ["EncodedFrame", "FrameStore", "process_raw_frame"]
