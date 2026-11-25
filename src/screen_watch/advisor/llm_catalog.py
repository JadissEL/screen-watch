"""Built-in catalog of vision-capable LLMs for cost estimates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class LlmModel:
    """One catalog entry. Prices are USD per 1M input tokens (approx, maintained in TOKEN_COSTS)."""

    id: str
    label: str
    provider: str
    input_usd_per_mtok: float
    tokens_per_frame_1280x720: int
    tokenization: str
    notes: str = ""


# Estimates for 1280×720 JPEG @ q60. See docs/TOKEN_COSTS.md for methodology.
MODELS: tuple[LlmModel, ...] = (
    LlmModel(
        id="gpt-4o",
        label="GPT-4o",
        provider="OpenAI",
        input_usd_per_mtok=2.50,
        tokens_per_frame_1280x720=765,
        tokenization="tile-based (base 85 + 170×tiles, detail=high)",
        notes="Approx after 768 short-side scale; verify with OpenAI image cost calculator.",
    ),
    LlmModel(
        id="gpt-4.1",
        label="GPT-4.1",
        provider="OpenAI",
        input_usd_per_mtok=2.00,
        tokens_per_frame_1280x720=765,
        tokenization="tile-based (same family as GPT-4o)",
    ),
    LlmModel(
        id="claude-sonnet",
        label="Claude Sonnet",
        provider="Anthropic",
        input_usd_per_mtok=3.00,
        tokens_per_frame_1280x720=1677,
        tokenization="28×28 patches: ⌈w/28⌉×⌈h/28⌉",
        notes="Standard-tier long-edge may downscale; high-res tier costs more.",
    ),
    LlmModel(
        id="claude-opus",
        label="Claude Opus",
        provider="Anthropic",
        input_usd_per_mtok=5.00,
        tokens_per_frame_1280x720=1677,
        tokenization="28×28 patches",
    ),
    LlmModel(
        id="gemini-flash",
        label="Gemini Flash",
        provider="Google",
        input_usd_per_mtok=0.15,
        tokens_per_frame_1280x720=774,
        tokenization="258 tokens per 768×768 tile (images >384px tiled)",
        notes="Flash input prices vary by version; figure is illustrative.",
    ),
    LlmModel(
        id="gemini-pro",
        label="Gemini Pro",
        provider="Google",
        input_usd_per_mtok=1.25,
        tokens_per_frame_1280x720=774,
        tokenization="258 tokens per tile",
    ),
    LlmModel(
        id="qwen-vl",
        label="Qwen-VL",
        provider="Alibaba / open",
        input_usd_per_mtok=0.0,
        tokens_per_frame_1280x720=1200,
        tokenization="vendor/host dependent",
        notes="Self-host ≈ $0 API; hosted APIs vary. Token count is a rough midpoint.",
    ),
    LlmModel(
        id="llama-vision",
        label="Llama vision",
        provider="Meta / open",
        input_usd_per_mtok=0.0,
        tokens_per_frame_1280x720=1200,
        tokenization="host dependent",
        notes="Self-host ≈ $0 API; cloud hosts bill differently.",
    ),
)


def list_models() -> list[dict[str, Any]]:
    return [asdict(m) for m in MODELS]


def get_model(model_id: str) -> LlmModel | None:
    key = model_id.strip().lower()
    for m in MODELS:
        if m.id == key or m.label.lower() == key:
            return m
    return None
