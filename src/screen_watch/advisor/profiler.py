"""Best-effort local machine profile — advisory only, never blocking."""

from __future__ import annotations

import logging
import os
import platform
import shutil
from dataclasses import asdict, dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MachineProfile:
    """Snapshot of host capacity indicators."""

    os: str
    cpu_model: str
    cpu_cores: int
    ram_gb: float | None
    gpu: str | None
    disk_free_gb: float | None
    disk_total_gb: float | None


def profile_machine() -> MachineProfile:
    """Collect basic machine info without requiring optional deps when possible."""
    cpu_model = platform.processor() or platform.machine() or "unknown"
    cores = os.cpu_count() or 1
    ram_gb: float | None = None
    gpu: str | None = None

    try:
        import psutil  # type: ignore

        ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
        cpu_model = platform.processor() or cpu_model
    except Exception:
        logger.debug("psutil unavailable; RAM unknown", exc_info=True)

    gpu = _detect_gpu()

    disk_free_gb = disk_total_gb = None
    try:
        usage = shutil.disk_usage(os.path.expanduser("~"))
        disk_free_gb = round(usage.free / (1024**3), 2)
        disk_total_gb = round(usage.total / (1024**3), 2)
    except Exception:
        logger.debug("disk usage unavailable", exc_info=True)

    return MachineProfile(
        os=f"{platform.system()} {platform.release()}",
        cpu_model=cpu_model,
        cpu_cores=cores,
        ram_gb=ram_gb,
        gpu=gpu,
        disk_free_gb=disk_free_gb,
        disk_total_gb=disk_total_gb,
    )


def _detect_gpu() -> str | None:
    if platform.system() == "Windows":
        try:
            import subprocess

            out = subprocess.check_output(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
            lines = [ln.strip() for ln in out.splitlines() if ln.strip() and ln.strip().lower() != "name"]
            if lines:
                return ", ".join(lines[:3])
        except Exception:
            return None
    return None


def recommend_settings(profile: MachineProfile) -> dict[str, Any]:
    """
    Suggest capture settings and whether recording looks advisable.

    Never blocks — soft recommendations only.
    """
    cores = profile.cpu_cores
    ram = profile.ram_gb or 8.0
    disk = profile.disk_free_gb

    if cores <= 2 or ram < 6:
        res = {"max_width": 960, "max_height": 540, "fps": 2.0, "jpeg_quality": 50}
        recording = "caution"
        note = "Low cores/RAM — prefer lower resolution and FPS; recording may stress this PC."
    elif cores <= 4 or ram < 12:
        res = {"max_width": 1280, "max_height": 720, "fps": 3.0, "jpeg_quality": 55}
        recording = "ok_with_limits"
        note = "Mid-range — defaults are fine for watch; keep recording FPS modest."
    else:
        res = {"max_width": 1280, "max_height": 720, "fps": 5.0, "jpeg_quality": 60}
        recording = "comfortable"
        note = "Capable machine — 1280×720 @ 5 FPS is appropriate."

    warnings: list[str] = []
    if disk is not None and disk < 5:
        warnings.append(f"Low free disk ({disk} GB) — recording may fill storage quickly.")
        if recording == "comfortable":
            recording = "ok_with_limits"

    return {
        "recommended_capture": res,
        "recording_advisability": recording,
        "note": note,
        "warnings": warnings,
        "profile": asdict(profile),
    }


def capacity_advice_message(profile: MachineProfile | None = None) -> str:
    """Non-blocking one-liner for pre-recording / advise CLI."""
    prof = profile or profile_machine()
    rec = recommend_settings(prof)
    parts = [rec["note"]]
    parts.extend(rec["warnings"])
    if rec["recording_advisability"] == "caution":
        parts.append("Your PC may struggle with recording at high settings — advice only, not a block.")
    return " ".join(parts)
