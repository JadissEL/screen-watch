"""Privacy helpers — local-only observation; no network exfil."""

from __future__ import annotations

PRIVACY_SUMMARY = (
    "screen-watch is observation-only and local-only: frames stay on this machine, "
    "there is no mouse/keyboard control, blur is off by default, and recording is "
    "off until you explicitly enable it."
)


def privacy_blurb() -> str:
    """Short privacy statement for CLI / MCP status."""
    return PRIVACY_SUMMARY
