"""Configuration loading and defaults for screen-watch."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

BackendName = Literal["auto", "mss", "dxcam", "sck", "pipewire"]

# Locked defaults (IMPLEMENTATION_PLAN.md §11)
DEFAULT_MAX_WIDTH = 1280
DEFAULT_MAX_HEIGHT = 720
DEFAULT_FPS = 5.0
DEFAULT_JPEG_QUALITY = 60
DEFAULT_CHANGE_THRESHOLD = 2.0  # mean absolute diff on 32x32 grayscale; lower = more sensitive
DEFAULT_FPS_CAP = 5.0
DEFAULT_BLUR = False
DEFAULT_BLUR_BLOCK = 16
DEFAULT_MIN_CAPTURE_INTERVAL = 0.12
DEFAULT_HISTORY_SIZE = 64


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def config_dir() -> Path:
    """Return the per-user config directory (XDG / APPDATA)."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "screen-watch"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "screen-watch"
    return Path.home() / ".config" / "screen-watch"


def data_dir() -> Path:
    """Return the per-user data directory for recordings and local stores."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "screen-watch"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "screen-watch"
    return Path.home() / ".local" / "share" / "screen-watch"


def default_config_path() -> Path:
    """``config.toml`` under the user config directory."""
    return config_dir() / "config.toml"


def load_toml_file(path: Path | None = None) -> dict[str, Any]:
    """Load optional TOML config; missing file → empty dict."""
    cfg_path = path or default_config_path()
    env_path = os.environ.get("SCREEN_WATCH_CONFIG")
    if env_path:
        cfg_path = Path(env_path)
    if not cfg_path.is_file():
        return {}
    with cfg_path.open("rb") as fh:
        data = tomllib.load(fh)
    return data if isinstance(data, dict) else {}


@dataclass
class Settings:
    """Runtime settings. Precedence: constructor overrides > env > config.toml > defaults."""

    max_width: int = DEFAULT_MAX_WIDTH
    max_height: int = DEFAULT_MAX_HEIGHT
    fps: float = DEFAULT_FPS
    jpeg_quality: int = DEFAULT_JPEG_QUALITY
    change_threshold: float = DEFAULT_CHANGE_THRESHOLD
    backend: BackendName = "auto"
    display: int | None = None  # 1-based mss monitor index; None = primary
    blur: bool = DEFAULT_BLUR
    blur_block: int = DEFAULT_BLUR_BLOCK
    log_level: str = "INFO"
    recording_enabled: bool = False
    recordings_dir: Path = field(default_factory=lambda: data_dir() / "recordings")
    preferred_llm: str | None = None
    focus_hotkey: str = "ctrl+shift+f"
    min_capture_interval_s: float = DEFAULT_MIN_CAPTURE_INTERVAL
    history_size: int = DEFAULT_HISTORY_SIZE

    def capped_fps(self) -> float:
        return max(0.1, min(float(self.fps), DEFAULT_FPS_CAP))


def load_settings(**overrides: Any) -> Settings:
    """Load settings from config.toml, then environment, then explicit overrides."""
    file_cfg = load_toml_file()

    def fget(key: str, default: Any) -> Any:
        return file_cfg[key] if key in file_cfg else default

    backend_default = str(fget("backend", "auto")).strip().lower()
    backend_raw = os.environ.get("SCREEN_WATCH_BACKEND", backend_default).strip().lower()
    backend: BackendName
    if backend_raw in {"auto", "mss", "dxcam", "sck", "pipewire"}:
        backend = backend_raw  # type: ignore[assignment]
    else:
        backend = "auto"

    display_file = fget("display", None)
    display_raw = os.environ.get("SCREEN_WATCH_DISPLAY")
    display: int | None
    if display_raw is not None and display_raw.strip() != "":
        display = int(display_raw)
    elif display_file is None or display_file == "":
        display = None
    else:
        display = int(display_file)

    settings = Settings(
        max_width=_env_int("SCREEN_WATCH_MAX_WIDTH", int(fget("max_width", DEFAULT_MAX_WIDTH))),
        max_height=_env_int("SCREEN_WATCH_MAX_HEIGHT", int(fget("max_height", DEFAULT_MAX_HEIGHT))),
        fps=_env_float("SCREEN_WATCH_FPS", float(fget("fps", DEFAULT_FPS))),
        jpeg_quality=_env_int(
            "SCREEN_WATCH_JPEG_QUALITY", int(fget("jpeg_quality", DEFAULT_JPEG_QUALITY))
        ),
        change_threshold=_env_float(
            "SCREEN_WATCH_CHANGE_THRESHOLD",
            float(fget("change_threshold", DEFAULT_CHANGE_THRESHOLD)),
        ),
        backend=backend,
        display=display,
        blur=_env_bool("SCREEN_WATCH_BLUR", bool(fget("blur", DEFAULT_BLUR))),
        blur_block=_env_int(
            "SCREEN_WATCH_BLUR_BLOCK", int(fget("blur_block", DEFAULT_BLUR_BLOCK))
        ),
        log_level=os.environ.get(
            "SCREEN_WATCH_LOG_LEVEL", str(fget("log_level", "INFO"))
        ).upper(),
        recording_enabled=_env_bool(
            "SCREEN_WATCH_RECORDING_ENABLED",
            bool(fget("recording_enabled", False)),
        ),
        preferred_llm=(
            os.environ.get("SCREEN_WATCH_PREFERRED_LLM")
            or (str(fget("preferred_llm", "")) or None)
        ),
        focus_hotkey=os.environ.get(
            "SCREEN_WATCH_FOCUS_HOTKEY",
            str(fget("focus_hotkey", "ctrl+shift+f")),
        ),
        min_capture_interval_s=_env_float(
            "SCREEN_WATCH_MIN_CAPTURE_INTERVAL",
            float(fget("min_capture_interval_s", DEFAULT_MIN_CAPTURE_INTERVAL)),
        ),
        history_size=_env_int(
            "SCREEN_WATCH_HISTORY_SIZE",
            int(fget("history_size", DEFAULT_HISTORY_SIZE)),
        ),
    )
    rec = os.environ.get("SCREEN_WATCH_RECORDINGS_DIR") or fget("recordings_dir", None)
    if rec:
        settings.recordings_dir = Path(str(rec))

    for key, value in overrides.items():
        if value is not None and hasattr(settings, key):
            setattr(settings, key, value)
    return settings
