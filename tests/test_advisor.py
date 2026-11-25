"""Advisor catalog and cost estimates."""

from __future__ import annotations

from screen_watch.advisor.cost_estimate import estimate_session_cost
from screen_watch.advisor.llm_catalog import get_model, list_models
from screen_watch.advisor.profiler import MachineProfile, recommend_settings


def test_list_models_contains_gpt4o() -> None:
    ids = {m["id"] for m in list_models()}
    assert "gpt-4o" in ids
    assert "claude-sonnet" in ids
    assert "gemini-flash" in ids


def test_estimate_session_cost() -> None:
    data = estimate_session_cost("gpt-4o", fps=5.0, change_ratio=0.4, minutes=10)
    assert data["tokens_per_frame"] > 0
    assert "cost_per_10min_session_usd" in data
    assert data["cost_per_frame_usd"] >= 0


def test_recommend_low_end() -> None:
    profile = MachineProfile(
        os="test",
        cpu_model="tiny",
        cpu_cores=2,
        ram_gb=4.0,
        gpu=None,
        disk_free_gb=20.0,
        disk_total_gb=100.0,
    )
    rec = recommend_settings(profile)
    assert rec["recording_advisability"] == "caution"
    assert rec["recommended_capture"]["fps"] <= 3


def test_get_model() -> None:
    assert get_model("GPT-4o") is not None
    assert get_model("nope") is None
