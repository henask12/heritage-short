# ARCHITECTURE.md — Pipeline Stages, Contracts, Caching & Failures

**Repo:** https://github.com/henask12/heritage-short  
**Film:** *Red Through the Years* (TenX B2W0 Heritage Short)  
**As shipped on `main`:** bilingual EN/AM masters, dual-plate motion, original soft anthem score, Vercel showcase.

---

## 1. Design principles

1. **Single contract (`storyboard.json`)** — Every stage validates against `schema/storyboard.schema.json` **plus** domain guardrails before any work.
2. **Deterministic caching by input hash** — Artifacts live under `outputs/cache/<stage>/…_<sha256[:16]>.<ext>`. Change one shot → regenerate only that shot.
3. **Resilience & secrets** — Retries with exponential backoff + Retry-After for HTTP 429; API keys only in gitignored `.env` (header auth, never in URLs or commits).
4. **Observability** — Every model/synthesis/FFmpeg call appends one JSON line to `runs.jsonl` (`timestamp_utc`, `run_id`, `stage`, `shot_id`, `provider`, `model`, `params`, `seed`, `input_hash`, `cache_hit`, `status`, `latency_ms`, `cost_usd`, `output_path`, `error`).
5. **Language lanes** — English is primary; Amharic is a full second audio track. **English burned-in subtitles stay on for both.**

---

## 2. System dataflow (as shipped)

```text
                 schema/storyboard.schema.json
                              │
                              ▼  validate before EVERY stage
                       storyboard.json
          (10 shots · EN+AM narration · Red Devils wardrobe · music cues)
                              │
      ┌───────────┬───────────┼───────────┬───────────┬───────────┐
      ▼           ▼           ▼           ▼           ▼           ▼
 [1 script] [2 narration] [3 music] [4 keyframes] [5 shots] [6 assemble]
  inspect/   Gemini TTS    original    A + B still   dual-plate   FFmpeg
  optional   EN and/or AM  soft        plates in     cinematic    duck + LUFS
  critique   + trim/cache  anthem bed  outputs/      motion       + EN SRT
                                       keyframes/    clips        + end card
      │           │           │           │           │           │
      └───────────┴───────────┴─────┬─────┴───────────┘           │
                                    ▼                             ▼
                         outputs/music/score-{en,am}.wav
                         outputs/narration/{en,am}/
                         outputs/shots/{16x9,9x16}/
                                                              ┌───┴───┐
                                                              ▼       ▼
                                                    radio-cut*.mp4   final/*
                                                    (EN / AM)       16x9+9x16
                                                                    EN + *-am
                                                              │
                                                              ▼
                                                         web/ (Vercel)
                                              https://heritage-short.vercel.app
```

**Orchestration:** `pipeline/run.py` + `Makefile`  
- `make validate` · `make film` · `make film-am` · `make radio-cut` · `make radio-cut-am` · `make stage-*`

---

## 3. Stage boundaries & contracts

| # | Stage | Module | Inputs | Outputs (shipped) | Cache / identity inputs |
|---|--------|--------|--------|-------------------|-------------------------|
| 0 | Validate | `pipeline/validate.py` | `storyboard.json`, schema | Exit 0 or `ValueError` | Always runs |
| 1 | Script | `pipeline/script.py` | Validated storyboard | Beat summary; optional Gemini critique cache | `{model, prompt}` |
| 2 | Narration | `pipeline/narration.py` | Storyboard, `GEMINI_API_KEY` (or `--allow-placeholder`) | `outputs/narration/<lang>/<shot_id>.wav`, `manifest.json` | `{mode, lang, provider, model, voice, style, rate, text}` · trimmed WAV companion |
| 3 | Music | `pipeline/music.py` | Storyboard + narration manifest (slot lengths) · optional ACE-Step candidate | `outputs/music/score-en.wav`, `score-am.wav` (+ legacy `score.wav` for EN) | `{mode, key, bpm, slots}` or `{candidate_sha, total_dur}` |
| 4 | Keyframes | `pipeline/keyframes.py` + stored plates | Storyboard; Cloudflare FLUX when credentials exist | `outputs/keyframes/shot_XX.png`, `shot_XX_b.png`, `character-ref-sheet.png` | Provider path: `{shot, model, steps, seed, prompt, refs}` |
| 5 | Shots | `pipeline/shots.py` | Storyboard + keyframe A/B (or Wan clip) | `outputs/shots/16x9/*.mp4`, `outputs/shots/9x16/*.mp4` | `{shot, mode, src_sha, duration, aspect, fps, style, atmosphere}` |
| 6 | Assemble | `pipeline/assemble.py` | Storyboard, narration manifest, `score-{lang}.wav`, shot clips | Radio cuts + finals + SRT | Logged timeline + mix params per run |
| — | Web | `web/` (Next.js) | Compressed masters under `web/public/videos/` | Static site on Vercel | N/A (presentation layer) |

### Assemble naming (important)

| Lang | Radio cut | Finals |
|------|-----------|--------|
| `en` | `outputs/radio-cut.mp4` | `outputs/final/red-through-the-years-{16x9,9x16}.mp4` |
| `am` | `outputs/radio-cut-am.mp4` | `outputs/final/red-through-the-years-{16x9,9x16}-am.mp4` |

Amharic audio always burns **English** subtitles (`outputs/subtitles/en-over-am*.srt`).

---

## 4. Motion architecture (shots)

Priority order per shot inside `pipeline/shots.py`:

1. **Wan 2.2 clip** at `outputs/shots/wan/<shot_id>.mp4` → conform to aspect/fps (upgrade path; needs Kaggle GPU).
2. **Dual-plate cinematic motion** (shipped floor) — requires `shot_XX.png` + `shot_XX_b.png`:
   - Animate each plate with storyboard-driven camera path (`push_in`, `pull_back`, `pan_*`, `tilt_up`, `arc_right`) via FFmpeg `zoompan`.
   - Crossfade (`xfade`) for continuous motion.
   - Optional rain atmosphere overlay when motion prompt implies rain/floodlights.
3. **Ken Burns** — single plate only (`zoompan`) if B plate missing.

This is why finals read as **motion video**, not still slideshows, even without Wan/Veo on the build VM.

---

## 5. Audio architecture

### Narration
- Provider: Gemini TTS (`gemini-2.5-flash-preview-tts` preferred).
- On 429/503/404: automatic fallback chain → `gemini-3.8-flash-lite-tts` → `gemini-3.8-flash-tts` → `gemini-3.1-flash-tts-preview` (override with `GEMINI_TTS_MODELS`).
- Post-process: silence trim into `.trimmed.wav`; Amharic uses a dedicated style prompt.
- Offline: `--allow-placeholder` / `make radio-cut` uses isolated `placeholder_silence` cache keys so real TTS is never poisoned.

### Music
- **Shipped:** original soft terrace-anthem-style synthesizer in `music.py` (choir-like pads + distant pulse + chimes).  
  **Not** the copyrighted Manchester United theme / “Glory Glory” melody (`ETHICS.md`).
- Per-language beds: `score-en.wav` / `score-am.wav` sized to that language’s narration timeline.
- Mix: sidechain duck under real TTS; target **−14 LUFS**, true peak **−1 dBTP** (`storyboard.json` → `audio.mix`).

### Subtitles
- Always English burned-in (assignment rule), including Amharic-audio finals.

---

## 6. Caching isolation

| Concern | Mechanism |
|---------|-----------|
| Placeholder vs Gemini TTS | `mode` + `provider` inside narration hash |
| EN vs AM | `lang` inside narration + music hashes; separate output folders |
| Trimmed vs raw TTS | Raw cache + `.trimmed.wav` companion |
| Dual-plate vs Ken Burns | `mode` + both plate digests in shots hash |
| Preferred TTS model vs fallback | Preferred model stays in hash; actual serving model logged in `runs.jsonl` |

---

## 7. Validation & guardrails (`pipeline/validate.py`)

1. JSON Schema Draft 2020-12 (`jsonschema` if installed; pure-Python fallback otherwise).
2. Planned shot durations sum ∈ `[60, 90]` seconds.
3. English narration word count ∈ `[130, 220]`.
4. Unique sequential `order`, known `characters` keys, `end_card.shot_id` linkage.
5. If `reference_image` is set, file must exist (final cut uses `synthetic_anonymous` / `null` refs — fictional fans).
6. Living/recognizable footballer **name** scan on `image_prompt` + `motion_prompt`.

---

## 8. Failure handling & fallbacks

| Failure | Handling |
|---------|----------|
| Invalid storyboard | Fail before any API spend; path-accurate errors |
| HTTP 429 / capacity | Retry-After-aware backoff; TTS model fallback chain; pace between calls |
| Missing `GEMINI_API_KEY` | Offline placeholder radio cut still builds; clear setup message |
| Line longer than planned | Assemble slots = `max(planned, measured + 0.6)` (EN); Amharic may atempo-fit outliers |
| No Wan / no Veo / no GPU | Dual-plate motion floor (documented Wan path remains) |
| No Cloudflare FLUX key | Keyframes may be supplied as plates under `outputs/keyframes/`; FLUX module ready when keys exist |
| No ACE-Step | Original soft anthem synthesizer |
| Club theme copyright | Never ship official MU theme audio — original score only |

Evidence of real failures and mitigations: [`FAILURES.md`](FAILURES.md). Experiments: [`EXPERIMENTS.md`](EXPERIMENTS.md).

---

## 9. Web presentation layer

```text
web/   Next.js 15 + Tailwind
  public/videos/   compressed EN + AM × 16:9 + 9:16 masters for streaming
  public/stills/   hero / story imagery
  app/page.tsx     brand hero, player (EN|AM), story, pipeline summary, AI disclosure
```

Deploy: Vercel → **Root Directory = `web`** → https://heritage-short.vercel.app  
No server secrets required for the public site.

---

## 10. Module index

| Path | Role |
|------|------|
| `storyboard.json` | Contract |
| `schema/storyboard.schema.json` | Schema |
| `pipeline/common.py` | Env, hash cache, retries, `runs.jsonl`, FFmpeg helpers |
| `pipeline/validate.py` | Schema + domain + likeness guardrails |
| `pipeline/script.py` | Inspect / optional critique |
| `pipeline/narration.py` | Gemini TTS EN/AM |
| `pipeline/music.py` | Soft anthem bed / ACE-Step hook |
| `pipeline/keyframes.py` | FLUX provider path |
| `pipeline/shots.py` | Dual-plate / Ken Burns / Wan |
| `pipeline/assemble.py` | Radio cut + finals |
| `pipeline/run.py` | CLI orchestrator |
| `Makefile` | `film`, `film-am`, `radio-cut`, `stage-*` |
| `runs.jsonl` | Telemetry ledger |
| `web/` | Public showcase |

---

## 11. One-command mental model

```bash
make validate          # contract OK?
make film              # EN narration → music → assemble (uses existing shots/keyframes)
make film-am           # AM narration → music → assemble (*-am.mp4, EN subs)
cd web && npm run build  # showcase
```

Clean clone without keys still validates and can build an offline radio cut; with `GEMINI_API_KEY`, bilingual voice regenerates; motion plates and finals already committed for graders to open without GPU.
