"""Local advisor: PC profiler + LLM cost estimates."""

from __future__ import annotations

from screen_watch.advisor.cost_estimate import estimate_session_cost
from screen_watch.advisor.llm_catalog import list_models
from screen_watch.advisor.profiler import profile_machine, recommend_settings
from screen_watch.advisor.store import load_advisor_state, save_advisor_state

__all__ = [
    "estimate_session_cost",
    "list_models",
    "load_advisor_state",
    "profile_machine",
    "recommend_settings",
    "save_advisor_state",
]
