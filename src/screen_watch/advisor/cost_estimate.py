"""Session cost estimates from the static LLM catalog."""

from __future__ import annotations

from typing import Any

from screen_watch.advisor.llm_catalog import LlmModel, get_model


def estimate_session_cost(
    model_id: str,
    *,
    fps: float = 5.0,
    change_ratio: float = 0.4,
    minutes: float = 10.0,
) -> dict[str, Any]:
    """
    Estimate image-input cost for continuous watch.

    Assumes change-detection sends only `change_ratio` of frames (default 40%).
    Excludes text prompt / output tokens.
    """
    model = get_model(model_id)
    if model is None:
        return {"error": f"Unknown model_id={model_id!r}", "models": "use list_models()"}

    tokens = model.tokens_per_frame_1280x720
    cost_per_frame = (tokens / 1_000_000.0) * model.input_usd_per_mtok
    frames_per_min = fps * 60.0 * change_ratio
    cost_per_min = cost_per_frame * frames_per_min
    cost_session = cost_per_min * minutes

    return {
        "model_id": model.id,
        "label": model.label,
        "provider": model.provider,
        "tokenization": model.tokenization,
        "tokens_per_frame": tokens,
        "cost_per_frame_usd": round(cost_per_frame, 6),
        "assumptions": {
            "resolution": "1280x720",
            "jpeg_quality": 60,
            "fps": fps,
            "change_ratio": change_ratio,
            "minutes": minutes,
            "includes": "image input tokens only",
        },
        "cost_per_minute_usd": round(cost_per_min, 4),
        "cost_per_10min_session_usd": round(cost_per_min * 10.0, 3),
        "cost_for_requested_minutes_usd": round(cost_session, 3),
        "notes": model.notes,
        "disclaimer": "Estimates only — provider pricing and token rules change; see docs/TOKEN_COSTS.md.",
    }


def format_estimate(model: LlmModel, **kwargs: Any) -> str:
    data = estimate_session_cost(model.id, **kwargs)
    return (
        f"{data['label']}: ~{data['tokens_per_frame']} tok/frame, "
        f"${data['cost_per_frame_usd']}/frame, "
        f"${data['cost_per_minute_usd']}/min, "
        f"~${data['cost_per_10min_session_usd']}/10min "
        f"(40% change-detection @ {kwargs.get('fps', 5)} FPS)"
    )
