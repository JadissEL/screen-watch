# Vision token & cost estimates (screen-watch)

**Purpose:** Static tables for the local LLM advisor. Not live pricing — re-check provider docs before relying on dollars.

**Assumptions for all rows**

| Knob | Value |
|------|--------|
| Frame size | **1280×720** |
| Encode | JPEG quality **60** |
| Watch FPS | **5** |
| Change-detection | **~40%** of frames actually sent (30–50% band) |
| Cost scope | **Image input tokens only** (no text prompt / completion) |

Token math is **model-specific** (tiles vs patches vs area). JPEG byte size does **not** equal tokens.

---

## How tokens are counted

| Family | Method (simplified) | 1280×720 estimate |
|--------|---------------------|-------------------|
| **OpenAI GPT-4o / GPT-4.1** | Tile-based: scale short side ≤768, cover with 512px tiles; `tokens ≈ 85 + 170 × tiles` (`detail=high`) | **~765** |
| **Claude Sonnet / Opus** | `⌈w/28⌉ × ⌈h/28⌉` patches (may downscale on standard tier) | **~1,677** (no downscale) |
| **Gemini Flash / Pro** | ≤384px → 258 tok; larger → 258 tok per ~768×768 tile | **~774** (≈3 tiles) |
| **Qwen-VL / Llama vision** | Host/vendor dependent | **~1,200** midpoint placeholder |

OpenAI `detail=low` is base tokens only (~85 for GPT-4o) — cheaper but weaker for UI work. screen-watch assumes **high/auto**-class fidelity.

---

## Cost per frame / minute / 10-minute session

USD ≈ `(tokens_per_frame / 1e6) × input_$per_MTok`.  
Frames/min ≈ `5 × 60 × 0.4 = 120`.

| Model | $/1M input (approx) | Tok/frame | $/frame | $/min @40% | $/10 min |
|-------|---------------------|-----------|---------|------------|----------|
| GPT-4o | $2.50 | 765 | ~$0.0019 | ~$0.23 | **~$2.30** |
| GPT-4.1 | $2.00 | 765 | ~$0.0015 | ~$0.18 | **~$1.80** |
| Claude Sonnet | $3.00 | 1677 | ~$0.0050 | ~$0.60 | **~$6.00** |
| Claude Opus | $5.00 | 1677 | ~$0.0084 | ~$1.01 | **~$10.10** |
| Gemini Flash | $0.15 | 774 | ~$0.0001 | ~$0.01 | **~$0.14** |
| Gemini Pro | $1.25 | 774 | ~$0.0010 | ~$0.12 | **~$1.16** |
| Qwen-VL (self-host) | $0 | ~1200 | $0 | $0 | **$0** |
| Llama vision (self-host) | $0 | ~1200 | $0 | $0 | **$0** |

Hosted open-model APIs (Together, Fireworks, etc.) replace the $0 column with that host’s rates.

---

## Practical tips for users

1. **Change-detection** is the biggest lever — static IDE → far fewer billable frames.  
2. Prefer **Gemini Flash** or **self-hosted VL** for always-on watch; use Sonnet/Opus/GPT for harder UI reasoning.  
3. **Blur** does not reduce tokens (same resolution). Crop via `get_region_frame` / `guided_region_focus` does. Prefer `get_latest_frame_info` or `save_latest_frame` when you do not need image bytes in-context.  
4. Re-validate prices on [OpenAI](https://platform.openai.com/docs/pricing), [Anthropic](https://claude.com/pricing), [Google AI](https://ai.google.dev/pricing).

*Last reviewed for screen-watch advisor: 2026-11-25.*
