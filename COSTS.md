# COSTS.md — Cost & Quota Ledger

Target budget: **$0.00 USD** using free-tier / open-weight providers across all stages. Actual per-call cost estimates are also logged automatically to `runs.jsonl`.

## Stack & Free-Tier Budget

| Stage | Provider & Model | Pricing / Quota Tier | Phase 1 Spend | Projected Total |
|-------|------------------|----------------------|---------------|-----------------|
| Script critique | Google Gemini API (`gemini-2.5-flash`) | Free tier | $0.00 | $0.00 |
| Narration | Google Gemini API (`gemini-2.5-flash-preview-tts`) | Free tier (9 lines × ~18 words) | $0.00 *(pending key)* | $0.00 |
| Keyframes (Phase 2) | Cursor image gen (floor) / Cloudflare FLUX when keys arrive | $0.00 this run (Cloudflare unset; Gemini image quota blocked) | $0.00 | $0.00 |
| Moving shots (Phase 2) | Local FFmpeg Ken Burns (Wan 2.2 deferred — no Kaggle session) | Free local CPU | $0.00 | $0.00 |
| Score (Phase 1 & 2) | Local warm ambient pad (ACE-Step deferred — no Kaggle/Colab) | Open / local | $0.00 | $0.00 |
| Assembly | Local FFmpeg | Open source, local CPU | $0.00 | $0.00 |
| **Total** | | | **$0.00** | **$0.00** |

## Cost Controls Built Into Pipeline
1. **Input-hash caching:** Unchanged shots are served from `outputs/cache/` (`cache_hit: true`) with zero repeat API calls.
2. **Pre-flight validation:** `pipeline/validate.py` blocks malformed storyboards or forbidden prompts before any provider call is made.
3. **Reference sheet before keyframes (Phase 2):** Locks character consistency on 1 image before burning FLUX quota across 9 shots.
4. **Telemetry ledger:** Every call records `cost_usd` and `latency_ms` in `runs.jsonl` for transparent end-of-project totals.
