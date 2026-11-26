# ETHICS.md — Consent, Likeness, Voice, Labelling & Licences

> **Update (2026-11-26):** Personal adult reference photo removed by creator request. The film now uses **fictional synthetic characters** only. No real-person face cloning.

## 1. Subject Likeness Consent Record

| Field | Record |
|-------|--------|
| **Subject** | None (fictional Manchester United fan characters) |
| **Reference asset** | Removed — `assets/refs/henok-adult.jpg` deleted from repo |
| **Consent status** | Creator withdrew personal likeness from the film; regenerate with random fictional faces |
| **Childhood portrayal** | Fictional child only (`synthetic_anonymous`) |
| **Wardrobe** | Manchester United / Red Devils kits and scarves as story identity (not generic unlabeled red) |

## 2. Voice Policy (No Voice Cloning)
- Narration uses stock Gemini TTS (`Charon`).
- No voice cloning of any real person.

## 3. Third-Party Likeness & Trademark Guardrails
- **No living footballer faces** in prompts or frames.
- Club identity shown via Manchester United / Red Devils jerseys, scarves, and crest motifs as narrative wardrobe.
- Automated player-name scan remains in `pipeline/validate.py`.

## 4. AI Disclosure & Labelling Plan
1. In-film AI end card (`shot_10`) states fictional characters + AI pipeline.
2. Public post should label the work AI-assisted and link this repo.
3. `runs.jsonl` logs generations.

## 5. Model & Asset Licence Notes

| Component | Model / Source | Notes |
|-----------|----------------|-------|
| Narration | Gemini TTS | Stock voice |
| Keyframes | AI image generation (fictional faces) | No personal photo conditioning after likeness removal |
| Motion | FFmpeg Ken Burns | Local |
| Score | Original soft terrace-anthem-style bed (choir pad + distant pulse) | Royalty-free original synthesis — **not** the copyrighted Manchester United theme / “Glory Glory” melody |
| Font | Inter (OFL 1.1) | Embedded in video |
