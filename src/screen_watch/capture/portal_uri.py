"""Helpers for xdg-desktop-portal screenshot URIs (pure, testable)."""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

_FILE_URI_RE = re.compile(r"(file://[^\s'\">\],]+)")


def extract_file_uri(text: str) -> str | None:
    """Pull the first file:// URI from gdbus / portal response text."""
    if not text:
        return None
    match = _FILE_URI_RE.search(text)
    if not match:
        return None
    return match.group(1).rstrip(">',)")


def file_uri_to_path(uri: str) -> Path:
    """Convert file:// URI to a local Path."""
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"Unsupported URI scheme: {uri}")
    return Path(urllib.parse.unquote(parsed.path))
