"""Persist machine profile + preferred LLM locally."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from screen_watch.config import config_dir

logger = logging.getLogger(__name__)


def _state_path() -> Path:
    return config_dir() / "advisor_state.json"


def load_advisor_state() -> dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Corrupt advisor state at %s", path)
        return {}


def save_advisor_state(state: dict[str, Any]) -> Path:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return path
