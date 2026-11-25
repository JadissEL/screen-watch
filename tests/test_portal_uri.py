"""Portal URI parsing."""

from __future__ import annotations

import pytest

from screen_watch.capture.portal_uri import extract_file_uri, file_uri_to_path


def test_extract_file_uri() -> None:
    text = "(objectpath '/org/freedesktop/portal/desktop/request/1',), uri: <'file:///tmp/shot.png'>"
    assert extract_file_uri(text) == "file:///tmp/shot.png"


def test_extract_none() -> None:
    assert extract_file_uri("no uri here") is None


def test_file_uri_to_path() -> None:
    path = file_uri_to_path("file:///tmp/foo%20bar.png")
    assert "foo bar.png" in str(path)


def test_bad_scheme() -> None:
    with pytest.raises(ValueError):
        file_uri_to_path("https://example.com/x.png")
