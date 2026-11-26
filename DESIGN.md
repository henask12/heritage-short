# DESIGN.md — *Red Through the Years*

## Audience
Anyone who understands lifelong loyalty: friends, family, football supporters, and curious non-fans watching on phone or desktop feeds. Non-fans must stay emotionally oriented throughout — no insider football jargon, club trivia, or assumed familiarity with players.

## Creative Intent
When the film ends, the viewer should feel that supporting a club can be a form of **family heritage**: a red thread stretching from childhood in Addis Ababa to adulthood, enduring through glory, quiet drought years, and the club's present-day rebuild.

## Working Title & Logline
- **Working Title:** *Red Through the Years*
- **Logline:** A boy in Ethiopia falls for Manchester United and carries that loyalty through wins, droughts, and adulthood until the club's present day.

## Languages & Accessibility
- **Primary narration:** English (`en`), warm documentary delivery via stock Gemini TTS (`Charon`).
- **Subtitles:** Burned-in English subtitles always on for silent-autoplay phone feeds and accessibility.
- **Secondary track:** Amharic (`am`) narration over the same storyboard/motion cut, with burned-in English subtitles kept. Build with `make film-am`.

## Visual & Character Direction
- **Visual language:** 35mm poetic documentary realism (Kodak Portra warmth, shallow depth of field) rooted in authentic Addis Ababa interiors and highland golden-hour light.
- **Recurring motif:** Deep Manchester crimson (`#9E1B24`) carried across an oversized childhood jersey, a knit supporter scarf, floodlight mist, and a sunlit adult ritual.
- **Likeness anchor:** Characters are fictional synthetic fans (no personal likeness). Wardrobe must read as Manchester United / Red Devils kits — not generic unlabeled red.
- **Guardrail:** Zero living or recognizable footballer faces. Football eras are expressed through atmosphere, scarves, woven textures, floodlights, rain, and shared living rooms.

## Storyboard Arc (10 Shots · 74.0s · 166 EN Words)

| Shot | Beat | Era | Dur | Words | Stated Reason |
|------|------|-----|-----|-------|---------------|
| `shot_01` | The First Red Devils Shirt | Childhood — Addis Ababa | 8.0s | 19 | Grounds fans and non-fans immediately in place and tactile childhood memory. |
| `shot_02` | Match Night Living Room | Childhood — Family & Neighbors | 8.0s | 20 | Reframes fandom as communal belonging and family ritual. |
| `shot_03` | Floodlights and Certainty | Glory Era — Pure Atmosphere | 7.0s | 18 | Conveys peak glory via scarf, rain, and floodlights without living player faces. |
| `shot_04` | Seasons Turning | Adolescence — Passing Time | 7.0s | 17 | Signals growing up and the shift to lean years through everyday desk objects. |
| `shot_05` | The Quiet Drought Years | Lean Years — Patient Loyalty | 8.0s | 20 | States the universal thesis for non-fans: devotion that outlasts winning. |
| `shot_06` | Same Ritual, Sharper Screen | Present Day — Adult Henok | 8.0s | 20 | Introduces consented adult Henok, rhyming the adult ritual with `shot_01`. |
| `shot_07` | What We Inherit | Continuity — Heritage Motif | 7.0s | 18 | Delivers the core heirloom metaphor via hands folding old and new red fabrics. |
| `shot_08` | Addis Golden Hour, Next Chapter | Present Day — Hope Renewed | 8.0s | 19 | Connects Manchester United's present rebuild to Henok's Addis horizon. |
| `shot_09` | We Stayed | Closing — Timeless Loyalty | 7.0s | 15 | Lands the closing thesis on a restrained human portrait. |
| `shot_10` | AI Provenance End Card | Credits & Disclosure | 6.0s | 0 | Mandatory AI provenance and consent disclosure with space for resonance. |

## User Tests

### Test 1 — Radio Cut (Ready for Henok — play `outputs/radio-cut.mp4`)
- **Date:** _Henok to fill after showing ≥3 people_
- **People (≥3, mix of fans & non-fans):**
  1. _Participant 1 (role / fan or non-fan)_
  2. _Participant 2 (role / fan or non-fan)_
  3. _Participant 3 (role / fan or non-fan)_
- **Questions to ask:**
  - Without seeing pictures yet, what did you feel by the end?
  - Did any line feel confusing if you don't follow football?
  - Which moment dragged or rushed?
- **What landed:** _To record after test._
- **What confused:** _To record after test._
- **Storyboard changes applied:** _To record after test._

### Test 2 — Near-Final Cut (Ready for Henok — play `outputs/final/red-through-the-years-16x9.mp4` or 9:16)
- **Date:** _Henok to fill_
- **People (≥3):** _TBD_
- **What landed:** _To record after test._
- **What confused:** _To record after test._
- **Storyboard changes applied:** _To record after test._

## Picture lock (Phase 2/3 floor)
- Golden identity sheet: `outputs/keyframes/character-ref-sheet.png` (fictional fan; personal photo removed)
- Kit rule: Manchester United / Red Devils crest visible on shirts and scarves
- Motion strategy shipped: Ken Burns over keyframes for all narrative shots (Wan upgrade optional)
- Finals: `outputs/final/red-through-the-years-16x9.mp4` and `outputs/final/red-through-the-years-9x16.mp4` (~84.8s)
