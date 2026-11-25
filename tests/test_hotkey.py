"""Hotkey parsing tests (no Win32 registration required)."""

from __future__ import annotations

import pytest

from screen_watch.focus.hotkey import MOD_CONTROL, MOD_SHIFT, parse_hotkey


def test_parse_ctrl_shift_f() -> None:
    spec = parse_hotkey("ctrl+shift+f")
    assert spec.modifiers == (MOD_CONTROL | MOD_SHIFT)
    assert spec.vk == ord("F")


def test_parse_f2() -> None:
    spec = parse_hotkey("ctrl+alt+f2")
    assert spec.vk == 0x71


def test_parse_invalid() -> None:
    with pytest.raises(ValueError):
        parse_hotkey("ctrl+notakey")
