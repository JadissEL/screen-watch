#!/usr/bin/env python3
"""Example agent-side polling loop using content_hash / since_hash.

Run with watch daemon preferred:

    python -m screen_watch serve   # in another process / MCP
    # or locally:
    python examples/poll_since_hash.py
"""

from __future__ import annotations

import time

from screen_watch.service import get_service, reset_service


def main() -> None:
    reset_service()
    svc = get_service()
    svc.daemon.start()
    last_hash = ""
    try:
        for _ in range(10):
            frame = svc.latest_for_agent()
            if not frame.jpeg:
                frame = svc.capture_once()
            if last_hash and frame.content_hash == last_hash:
                print(f"unchanged {frame.content_hash[:12]}… age_ms={svc.store.age_ms()}")
            else:
                print(
                    f"new frame {frame.width}x{frame.height} "
                    f"hash={frame.content_hash[:12]}… bytes={len(frame.jpeg)}"
                )
                last_hash = frame.content_hash
            time.sleep(0.4)
    finally:
        svc.daemon.stop()
        reset_service()


if __name__ == "__main__":
    main()
