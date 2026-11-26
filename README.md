# Red Through the Years — The Heritage Short

**Public repository:** https://github.com/henask12/heritage-short  
**Live showcase:** https://heritage-short.vercel.app  
**Assignment:** TenX B2W0 — The Heritage Short  
**Author:** Henok (`henask12`)

> **Logline:** A boy in Addis Ababa falls for Manchester United — the Red Devils — and carries that loyalty through glory, drought, and adulthood.

This repo is the complete original submission: a reproducible multi-model film pipeline, bilingual short film (English + Amharic), evidence docs graders expect, and a Vercel web showcase.

---

## Submit this link

```text
https://github.com/henask12/heritage-short
```

Public · default branch `main` · no secrets committed.

---

## What you will find (deliverables)

| Deliverable | Location |
|-------------|----------|
| Storyboard contract (10 shots) | [`storyboard.json`](storyboard.json) |
| JSON Schema + validator | [`schema/storyboard.schema.json`](schema/storyboard.schema.json), [`pipeline/validate.py`](pipeline/validate.py) |
| Full pipeline stages | [`pipeline/`](pipeline/) + [`Makefile`](Makefile) |
| English film 16:9 / 9:16 | [`outputs/final/red-through-the-years-16x9.mp4`](outputs/final/red-through-the-years-16x9.mp4), [`…-9x16.mp4`](outputs/final/red-through-the-years-9x16.mp4) |
| Amharic film 16:9 / 9:16 | [`outputs/final/red-through-the-years-16x9-am.mp4`](outputs/final/red-through-the-years-16x9-am.mp4), [`…-9x16-am.mp4`](outputs/final/red-through-the-years-9x16-am.mp4) |
| Radio cuts | [`outputs/radio-cut.mp4`](outputs/radio-cut.mp4), [`outputs/radio-cut-am.mp4`](outputs/radio-cut-am.mp4) |
| Telemetry log | [`runs.jsonl`](runs.jsonl) |
| Design / architecture / ethics / experiments / failures / costs | [`DESIGN.md`](DESIGN.md), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`ETHICS.md`](ETHICS.md), [`EXPERIMENTS.md`](EXPERIMENTS.md), [`FAILURES.md`](FAILURES.md), [`COSTS.md`](COSTS.md) |
| Web showcase (Vercel) | [`web/`](web/) → https://heritage-short.vercel.app |

---

## Original contributions (this project)

1. **Creative lock** — Working title *Red Through the Years*; heritage-as-fandom arc from Addis Ababa childhood to present-day Red Devils loyalty; English primary + Amharic second track; English burned-in subtitles always.
2. **Storyboard as contract** — Single `storyboard.json` with image/motion prompts, narration, music cues, and a stated reason per shot; validated before every run.
3. **Engineering pipeline** — Python stages with clear boundaries: validate → script → narration → music → keyframes → shots → assemble; `make film` / `make film-am` / per-stage targets.
4. **Grade magnets implemented** — Schema validation every run; SHA-256 input-hash caching; retries with 429-aware backoff + TTS model fallbacks; secrets via `.env` only; every call logged to `runs.jsonl`.
5. **Film floor shipped** — Gemini TTS (EN + AM), dual-plate cinematic motion from keyframes, original soft anthem-style score (not the copyrighted club theme), FFmpeg assembly with ducking / −14 LUFS / AI end card, both aspect ratios.
6. **Public web app** — Next.js landing page with EN/Amharic player, story, pipeline summary, and AI disclosure.

See also [`CONTRIBUTIONS.md`](CONTRIBUTIONS.md) for a contribution map by file.

---

## Implementation overview

```text
storyboard.json  ──validated──►  pipeline stages
                                      │
         ┌────────────┬───────────────┼───────────────┬────────────┐
         ▼            ▼               ▼               ▼            ▼
      narration     music         keyframes         shots       assemble
     Gemini TTS   soft anthem    still plates    dual-plate     FFmpeg
      EN + AM      (original)                    motion clips   16:9+9:16
                                      │
                                      ▼
                         outputs/final/*  +  web/
```

**Full stage diagram, contracts, caching, motion/audio lanes, and fallbacks:** [`ARCHITECTURE.md`](ARCHITECTURE.md) (kept in sync with the shipped pipeline).

**Stack (as shipped):** Gemini TTS (EN+AM) · keyframe A/B plates + dual-plate cinematic motion · original soft anthem score · FFmpeg assemble · Next.js showcase.  
Wan 2.2 / Cloudflare FLUX / ACE-Step remain documented upgrade paths when GPU/credentials are available.

---

## One-command run (clean clone)

**Prerequisites:** Python 3.10+, FFmpeg/ffprobe, optional Make.

```bash
git clone https://github.com/henask12/heritage-short.git
cd heritage-short

# Validate storyboard + rebuild what credentials allow
make validate
make film          # English (falls back cleanly if keys missing)
make film-am       # Amharic audio track (needs GEMINI_API_KEY)
```

```bash
cp .env.example .env   # set GEMINI_API_KEY for real TTS
```

Web showcase locally:

```bash
cd web && npm install && npm run dev
```

---

## Repository map

```text
heritage-short/
├── README.md / CONTRIBUTIONS.md
├── storyboard.json
├── schema/storyboard.schema.json
├── pipeline/          # validate, script, narration, music, keyframes, shots, assemble, run
├── Makefile
├── outputs/final/     # EN + AM masters (16:9 and 9:16)
├── outputs/keyframes/ # A/B motion plates
├── web/               # Vercel Next.js showcase
├── DESIGN.md ARCHITECTURE.md ETHICS.md EXPERIMENTS.md FAILURES.md COSTS.md
├── runs.jsonl
└── .env.example
```

---

## Ethics note

- Personal likeness photo was removed by creator request; characters are fictional.
- No living footballer faces.
- Narration uses stock Gemini TTS (no voice clone).
- Score is an **original** soft anthem-style bed — not the copyrighted Manchester United theme.
- Full record: [`ETHICS.md`](ETHICS.md).

---

## Licence / course context

Built for **TenX B2W0 — The Heritage Short** (educational). Use of club colours/kits is narrative atmosphere; this is not an official club product.
