# Agent usage pattern

Observation-only. Prefer hash polling so identical frames are not re-billed.

```text
1. doctor / get_version
2. list_displays → set_capture_display(id) if needed
3. start_watch()
4. wait_for_change(since_hash=last)  # or poll get_latest_frame_info
5. get_change_region() for a crop of what moved (seed once first)
6. get_latest_frame(since_hash=last) / save_latest_frame when hash changes
7. optional: get_frame_history(changed_only=true) for a change timeline
8. for UI detail: guided_region_focus / get_region_frame
```

Cursor MCP snippet: [cursor-mcp.json](cursor-mcp.json).  
Local hash demo: [poll_since_hash.py](poll_since_hash.py).
