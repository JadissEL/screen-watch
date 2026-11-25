"""Select a capture backend by platform and config."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from screen_watch.capture.base import CaptureBackend, CaptureError
from screen_watch.capture.mss_backend import MssBackend

if TYPE_CHECKING:
    from screen_watch.config import BackendName, Settings

logger = logging.getLogger(__name__)


def create_backend(settings: Settings | None = None, backend: BackendName | None = None) -> CaptureBackend:
    """
    Create the best available capture backend.

    Never raises on optional-dep import failure: falls back to mss.
    """
    from screen_watch.config import load_settings

    cfg = settings or load_settings()
    choice = backend or cfg.backend

    if choice == "mss":
        return MssBackend()

    if choice == "dxcam":
        return _try_dxcam() or _require_mss("dxcam unavailable")

    if choice == "sck":
        return _try_sck() or _require_mss("sck unavailable")

    if choice == "pipewire":
        return _try_pipewire() or _require_mss("pipewire unavailable")

    # auto
    if sys.platform == "win32":
        dx = _try_dxcam()
        if dx is not None:
            return dx
    elif sys.platform == "darwin":
        sck = _try_sck()
        if sck is not None:
            return sck
    elif sys.platform.startswith("linux"):
        pw = _try_pipewire()
        if pw is not None:
            return pw

    return MssBackend()


def _require_mss(reason: str) -> CaptureBackend:
    logger.warning("%s; falling back to mss", reason)
    return MssBackend()


def _try_dxcam() -> CaptureBackend | None:
    try:
        from screen_watch.capture.dxcam_backend import DxcamBackend

        return DxcamBackend()
    except CaptureError as exc:
        logger.info("dxcam not used: %s", exc)
        return None
    except Exception as exc:  # pragma: no cover
        logger.info("dxcam not used: %s", exc)
        return None


def _try_sck() -> CaptureBackend | None:
    try:
        from screen_watch.capture.screencapturekit import ScreenCaptureKitBackend

        return ScreenCaptureKitBackend()
    except CaptureError as exc:
        logger.info("sck not used: %s", exc)
        return None
    except Exception as exc:  # pragma: no cover
        logger.info("sck not used: %s", exc)
        return None


def _try_pipewire() -> CaptureBackend | None:
    try:
        from screen_watch.capture.pipewire_backend import PipewireBackend

        return PipewireBackend()
    except CaptureError as exc:
        logger.info("pipewire not used: %s", exc)
        return None
    except Exception as exc:  # pragma: no cover
        logger.info("pipewire not used: %s", exc)
        return None
