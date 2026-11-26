# Contributions & implementation map

This document maps **original work** in https://github.com/henask12/heritage-short for Assignment 1 reviewers.

**Owner / sole contributor:** Henok Mekonnen (`henask12`)  
**Project:** *Red Through the Years* — TenX B2W0 Heritage Short

---

## Authorship summary

| Area | Contribution |
|------|----------------|
| Creative brief | Story, audience, intent, bilingual plan, Red Devils identity (not generic red) |
| Storyboard | 10-shot contract with prompts, narration EN+AM, music cues, reasons |
| Pipeline engineering | Schema validation, caching, retries, logging, stage CLIs, Makefile |
| Narration | Gemini TTS English + Amharic; silence trim; model fallback on 429 |
| Music | Original soft terrace-anthem-style synthesizer (royalty-free; not club theme IP) |
| Picture / motion | Keyframes + dual-plate cinematic motion assembly (Wan upgrade path documented) |
| Edit | FFmpeg assemble: ducking, −14 LUFS, EN burned-in subs, AI end card, 16:9 + 9:16 |
| Evidence docs | DESIGN, ARCHITECTURE, ETHICS, EXPERIMENTS, FAILURES, COSTS, runs.jsonl |
| Web showcase | Next.js/Vercel site with EN/Amharic players and project story |

---

## File-level map

### Contract & validation
- `storyboard.json` — single source of truth
- `schema/storyboard.schema.json` — Draft 2020-12 schema
- `pipeline/validate.py` — schema + domain rules (duration, word count, player-face guardrail)

### Pipeline (`pipeline/`)
- `common.py` — env load, input-hash cache, retries, `runs.jsonl` logger, FFmpeg helpers
- `script.py` — storyboard inspect / optional critique
- `narration.py` — Gemini TTS EN/AM with cache + fallbacks
- `music.py` — original soft anthem bed (+ ACE-Step candidate hook)
- `keyframes.py` — FLUX/Cloudflare path (Phase 2 provider); plates also stored under `outputs/keyframes/`
- `shots.py` — dual-plate cinematic motion / Ken Burns / Wan conform
- `assemble.py` — radio cut + final films (EN/AM naming)
- `run.py` — orchestrator (`film`, `radio-cut`, stages)

### Film outputs
- `outputs/final/red-through-the-years-{16x9,9x16}.mp4` — English
- `outputs/final/red-through-the-years-{16x9,9x16}-am.mp4` — Amharic audio, EN subs
- `outputs/radio-cut.mp4`, `outputs/radio-cut-am.mp4`
- `outputs/keyframes/shot_XX.png` + `shot_XX_b.png` — motion plates

### Documentation (grader evidence)
- `DESIGN.md` — audience, intent, arc, user-test templates
- `ARCHITECTURE.md` — **current** stages, dual-plate motion, bilingual audio, caching, fallbacks, web layer
- `ETHICS.md` — likeness/voice policy, AI labelling, licences
- `EXPERIMENTS.md` — iteration log (≥10 entries)
- `FAILURES.md` — failures + mitigations
- `COSTS.md` — zero-cost stack ledger
- `runs.jsonl` — per-call telemetry

### Web
- `web/` — Next.js showcase deployed at https://heritage-short.vercel.app

---

## How to verify originality quickly

1. Open `storyboard.json` — unique heritage/Red Devils arc and bilingual narration.
2. Run `make validate` — schema + domain guardrails.
3. Skim `runs.jsonl` — real generation/assembly telemetry.
4. Play `outputs/final/red-through-the-years-16x9.mp4` and the `-am` sibling.
5. Open https://heritage-short.vercel.app for the public presentation.

---

## What was intentionally not copied

- No official Manchester United theme recording or melody.
- No living player likenesses.
- No personal face likeness in the final cut (fictional characters after creator request).
- API keys never committed (`.env.example` only).
