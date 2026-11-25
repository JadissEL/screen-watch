"""Linux capture: grim → xdg-desktop-portal (gdbus) → mss."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from screen_watch.capture.base import CaptureError, DisplayInfo, RawFrame
from screen_watch.capture.mss_backend import MssBackend
from screen_watch.capture.portal_uri import extract_file_uri, file_uri_to_path

logger = logging.getLogger(__name__)


def _frame_from_image_path(path: Path, backend: str) -> RawFrame:
    from PIL import Image

    img = Image.open(path).convert("RGB")
    return RawFrame(
        width=img.width,
        height=img.height,
        rgb=img.tobytes(),
        timestamp_ms=time.time() * 1000.0,
        display_id=0,
        backend=backend,
        origin_left=0,
        origin_top=0,
    )


def _copy_uri_to(uri: str, out: Path) -> None:
    src = file_uri_to_path(uri)
    if not src.exists():
        raise CaptureError(f"Portal screenshot file missing: {src}")
    out.write_bytes(src.read_bytes())


def _portal_screenshot(out: Path) -> None:
    """
    Non-interactive screenshot via xdg-desktop-portal using gdbus.

    Requires a session bus and a portal implementation. May still show a
    permission prompt the first time on some desktops.
    """
    gdbus = shutil.which("gdbus")
    if not gdbus:
        raise CaptureError("gdbus not found (install glib2 / libglib)")

    # Request screenshot; Interactive=false where supported
    cmd = [
        gdbus,
        "call",
        "--session",
        "--dest",
        "org.freedesktop.portal.Desktop",
        "--object-path",
        "/org/freedesktop/portal/desktop",
        "--method",
        "org.freedesktop.portal.Screenshot.Screenshot",
        "",
        "{'interactive': <false>, 'modal': <false>}",
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
    # Typical stdout: (objectpath '/org/freedesktop/portal/desktop/request/…',)
    direct = extract_file_uri(proc.stdout)
    if direct:
        _copy_uri_to(direct, out)
        return

    handle_match = re.search(r"objectpath\s+'([^']+)'", proc.stdout)
    if not handle_match:
        raise CaptureError(f"portal Screenshot: unexpected response: {proc.stdout!r}")

    handle = handle_match.group(1)
    deadline = time.time() + 15
    uri: str | None = None
    while time.time() < deadline:
        inspect = subprocess.run(
            [
                gdbus,
                "call",
                "--session",
                "--dest",
                "org.freedesktop.portal.Desktop",
                "--object-path",
                handle,
                "--method",
                "org.freedesktop.DBus.Properties.GetAll",
                "org.freedesktop.portal.Request",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        uri = extract_file_uri(inspect.stdout) or extract_file_uri(proc.stdout)
        if uri:
            break
        time.sleep(0.25)

    if not uri:
        raise CaptureError(
            "portal Screenshot completed without a file URI "
            f"(stdout={proc.stdout!r}). Try installing grim for Wayland."
        )
    _copy_uri_to(uri, out)


class PipewireBackend:
    """
    Linux backend priority:

    1. ``grim`` (wlroots Wayland) — fast, no portal prompt after setup
    2. xdg-desktop-portal Screenshot via ``gdbus``
    3. ``mss`` (X11 / compatibility)
    """

    def __init__(self) -> None:
        if not sys.platform.startswith("linux"):
            raise CaptureError("PipeWire/Linux backend is only available on Linux")
        self._grim = shutil.which("grim")
        self._gdbus = shutil.which("gdbus")
        self._mode = "mss"
        self._mss: MssBackend | None = None

        if self._grim:
            self._mode = "grim"
            logger.info("Linux capture using grim (%s)", self._grim)
        elif self._gdbus:
            self._mode = "portal"
            logger.info("Linux capture using xdg-desktop-portal (gdbus)")
        else:
            self._mode = "mss"
            logger.info("grim/gdbus not found; Linux capture using mss fallback")
            self._mss = MssBackend()

    @property
    def name(self) -> str:
        return {
            "grim": "grim",
            "portal": "xdg-portal",
            "mss": "pipewire-mss-fallback",
        }[self._mode]

    def list_displays(self) -> list[DisplayInfo]:
        if self._mss is not None:
            return self._mss.list_displays()
        label = "Wayland (grim)" if self._mode == "grim" else "Portal"
        return [DisplayInfo(id=1, width=1920, height=1080, is_primary=True, name=label)]

    def grab(self, display_id: int | None = None) -> RawFrame:
        if self._mode == "mss":
            assert self._mss is not None
            return self._mss.grab(display_id)
        if self._mode == "grim":
            return self._grab_grim()
        return self._grab_portal()

    def grab_virtual(self) -> RawFrame:
        if self._mode == "mss":
            assert self._mss is not None
            return self._mss.grab_virtual()
        if self._mode == "grim":
            return self._grab_grim()
        return self._grab_portal()

    def _grab_grim(self) -> RawFrame:
        assert self._grim
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "shot.png"
            try:
                subprocess.run(
                    [self._grim, str(out)],
                    check=True,
                    capture_output=True,
                    timeout=10,
                )
            except Exception as exc:
                raise CaptureError(f"grim capture failed: {exc}") from exc
            return _frame_from_image_path(out, self.name)

    def _grab_portal(self) -> RawFrame:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "shot.png"
            try:
                _portal_screenshot(out)
            except CaptureError:
                raise
            except Exception as exc:
                raise CaptureError(f"portal capture failed: {exc}") from exc
            return _frame_from_image_path(out, self.name)
