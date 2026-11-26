"""Stage 3 (music): ACE-Step 1.5 candidate ingestion or royalty-free ambient chord bed generator."""

from __future__ import annotations

import argparse
import json
import math
import struct
import time
import wave
from pathlib import Path
from typing import Any

from pipeline.common import (
    CACHE_DIR,
    OUTPUTS_DIR,
    STORYBOARD_PATH,
    compute_input_hash,
    copy_artifact,
    ensure_dir,
    file_sha256,
    load_env,
    log_run,
    probe_duration,
    run_ffmpeg,
)
from pipeline.validate import load_and_validate_storyboard

# Original soft terrace-anthem progression (NOT the copyrighted Man Utd theme melody).
# Hymn-like major warmth with quiet hope — G -> Em -> C -> D -> Em -> G -> C -> D -> G -> G
CHORD_PROGRESSION: list[tuple[float, float, float, float]] = [
    (98.00, 123.47, 146.83, 196.00),   # G (childhood wonder)
    (82.41, 123.47, 164.81, 196.00),   # Em (living room belonging)
    (130.81, 164.81, 196.00, 261.63),  # C (floodlight glory)
    (146.83, 185.00, 220.00, 293.66),  # D (seasons turning)
    (82.41, 123.47, 164.81, 246.94),  # Em7 (quiet drought)
    (98.00, 123.47, 146.83, 196.00),   # G (adult ritual)
    (130.81, 164.81, 196.00, 246.94),  # Cadd9 (heritage)
    (146.83, 185.00, 220.00, 293.66),  # D (golden hour lift)
    (98.00, 123.47, 196.00, 246.94),   # Gmaj9 (we stayed)
    (98.00, 146.83, 196.00, 246.94),   # G tail (end card)
]


def _synthesize_ambient_bed(
    shot_slots: list[dict[str, Any]],
    sample_rate: int,
    out_path: Path,
) -> None:
    """Synthesize an original soft anthem-style bed (choir-pad + distant pulse), royalty-free."""
    ensure_dir(out_path.parent)
    total_dur = sum(float(s["slot_duration_sec"]) for s in shot_slots)
    total_samples = max(1, int(round(total_dur * sample_rate)))

    boundaries: list[tuple[float, float, tuple[float, float, float, float], float]] = []
    cursor = 0.0
    for idx, slot in enumerate(shot_slots):
        dur = float(slot["slot_duration_sec"])
        chord = CHORD_PROGRESSION[idx % len(CHORD_PROGRESSION)]
        intensity = float(slot.get("intensity", 0.4))
        boundaries.append((cursor, cursor + dur, chord, intensity))
        cursor += dur

    frames = bytearray(total_samples * 2)
    fade_in_samples = int(2.4 * sample_rate)
    fade_out_samples = int(5.0 * sample_rate)
    two_pi = 2.0 * math.pi
    # Soft slow "heartbeat / distant terrace" pulse (~66 BPM feel), not a chant melody
    pulse_hz = 66.0 / 60.0

    b_idx = 0
    num_b = len(boundaries)
    for i in range(total_samples):
        t = i / float(sample_rate)
        while b_idx + 1 < num_b and t >= boundaries[b_idx][1]:
            b_idx += 1

        start_t, end_t, chord, intensity = boundaries[b_idx]
        local_t = t - start_t

        edge_fade = 1.0
        if local_t < 1.0:
            edge_fade = 0.5 - 0.5 * math.cos(math.pi * (local_t / 1.0))
        elif end_t - t < 1.0 and b_idx < num_b - 1:
            edge_fade = 0.5 - 0.5 * math.cos(math.pi * ((end_t - t) / 1.0))

        global_env = 1.0
        if i < fade_in_samples:
            global_env *= i / float(max(1, fade_in_samples))
        if i > total_samples - fade_out_samples:
            global_env *= max(0.0, (total_samples - i) / float(max(1, fade_out_samples)))

        # Choir-like stacked sines with slow vibrato (anthem pad, wordless)
        vibrato = 1.0 + 0.0035 * math.sin(two_pi * 4.8 * t)
        choir = 0.0
        for voice_idx, freq in enumerate(chord):
            f = freq * vibrato
            weight = 0.30 if voice_idx == 0 else (0.22 if voice_idx < 3 else 0.16)
            choir += weight * (
                0.70 * math.sin(two_pi * f * t)
                + 0.18 * math.sin(two_pi * (f * 2.0) * t + 0.2 * voice_idx)
                + 0.08 * math.sin(two_pi * (f * 3.0) * t + 0.4 * voice_idx)
                + 0.04 * math.sin(two_pi * (f * 0.5) * t)
            )

        # Soft brass-ish fifth shimmer above the pad
        shimmer = 0.08 * math.sin(two_pi * (chord[2] * 2.0) * t) * (0.55 + 0.45 * math.sin(two_pi * 0.12 * t))

        # Distant soft pulse under the bed (very quiet)
        pulse_phase = (t * pulse_hz) % 1.0
        pulse_env = math.exp(-6.0 * pulse_phase) if pulse_phase < 0.35 else 0.0
        pulse = 0.07 * pulse_env * math.sin(two_pi * (chord[0] * 0.5) * t)

        # Opening piano-like chime each beat (except end card)
        chime = 0.0
        if b_idx < num_b - 1 and local_t < 1.8:
            chime_env = math.exp(-2.0 * local_t) * min(1.0, local_t / 0.02)
            chime = 0.11 * chime_env * math.sin(two_pi * (chord[3]) * t)

        # Keep soft under narration: lower overall gain than before
        gain = (0.10 + 0.12 * intensity) * global_env
        sample = ((choir + shimmer) * (0.5 + 0.5 * edge_fade) + pulse + chime) * gain
        sample = max(-0.88, min(0.88, sample))
        struct.pack_into("<h", frames, i * 2, int(sample * 32767))

    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))


def _resolve_shot_slots(storyboard: dict[str, Any], lang: str = "en") -> list[dict[str, Any]]:
    manifest_path = OUTPUTS_DIR / "narration" / lang / "manifest.json"
    measured_map: dict[str, float] = {}
    tts_mode = "placeholder_silence"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        tts_mode = manifest.get("tts_mode", "placeholder_silence")
        for entry in manifest.get("shots", []):
            measured_map[entry["shot_id"]] = float(entry.get("audio_duration_sec", 0.0))

    slots: list[dict[str, Any]] = []
    for shot in storyboard["shots"]:
        sid = shot["id"]
        planned = float(shot["duration_sec"])
        measured = measured_map.get(sid, 0.0)
        slot_dur = max(planned, measured + 0.6) if (tts_mode == "gemini_tts" and measured > 0) else planned
        slots.append(
            {
                "shot_id": sid,
                "slot_duration_sec": round(slot_dur, 3),
                "cue_id": shot["music_cue"]["id"],
                "intensity": float(shot["music_cue"]["intensity"]),
            }
        )
    return slots


def run_music_stage(
    *,
    storyboard_path: Path = STORYBOARD_PATH,
    candidate_path: Path | None = None,
    lang: str = "en",
) -> Path:
    load_env()
    storyboard = load_and_validate_storyboard(storyboard_path)
    music_cfg = storyboard["audio"]["music"]
    sample_rate = 24000

    slots = _resolve_shot_slots(storyboard, lang=lang)
    total_dur = round(sum(s["slot_duration_sec"] for s in slots), 3)

    cache_root = ensure_dir(CACHE_DIR / "music")
    out_root = ensure_dir(OUTPUTS_DIR / "music")
    out_file = out_root / f"score-{lang}.wav"
    # Keep legacy alias for English so older docs/commands keep working.
    legacy_out = out_root / "score.wav"

    default_ace = out_root / "ace-step-selected.wav"
    source_candidate = candidate_path or (default_ace if default_ace.exists() else None)

    t0 = time.perf_counter()
    if source_candidate and source_candidate.exists():
        cand_hash = file_sha256(source_candidate)
        cache_payload = {
            "stage": "music",
            "mode": "ace_step_candidate",
            "candidate_sha": cand_hash,
            "total_dur": total_dur,
            "sample_rate": sample_rate,
        }
        input_hash = compute_input_hash(cache_payload)
        cache_file = cache_root / f"score_acestep_{input_hash}.wav"
        provider = "ace-step-kaggle"
        model = music_cfg["model"]

        if cache_file.exists():
            copy_artifact(cache_file, out_file)
            log_run(
                stage="music",
                shot_id=None,
                provider=provider,
                model=model,
                params={"source": str(source_candidate.name), "total_duration_sec": total_dur},
                seed=None,
                input_hash=input_hash,
                cache_hit=True,
                status="ok",
                latency_ms=int((time.perf_counter() - t0) * 1000),
                cost_usd=0.0,
                output_path=out_file,
            )
            if lang == "en":
                copy_artifact(out_file, legacy_out)
            print(f"[music] Cache hit for ACE-Step score ({total_dur:.2f}s)")
            return out_file

        fade_start = max(0.0, total_dur - 3.5)
        run_ffmpeg(
            [
                "-stream_loop",
                "-1",
                "-i",
                str(source_candidate),
                "-t",
                f"{total_dur:.3f}",
                "-af",
                f"afade=t=in:st=0:d=1.5,afade=t=out:st={fade_start:.3f}:d=3.5",
                "-ar",
                str(sample_rate),
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(cache_file),
            ]
        )
        copy_artifact(cache_file, out_file)
        if lang == "en":
            copy_artifact(out_file, legacy_out)
        log_run(
            stage="music",
            shot_id=None,
            provider=provider,
            model=model,
            params={"source": str(source_candidate.name), "total_duration_sec": total_dur},
            seed=None,
            input_hash=input_hash,
            cache_hit=False,
            status="ok",
            latency_ms=int((time.perf_counter() - t0) * 1000),
            cost_usd=0.0,
            output_path=out_file,
        )
        print(f"[music] Conformed ACE-Step score -> {out_file.name} ({total_dur:.2f}s)")
        return out_file

    # Phase 1 royalty-free warm ambient bed
    cache_payload = {
        "stage": "music",
        "mode": music_cfg["placeholder_mode"],
        "key_signature": music_cfg["key_signature"],
        "bpm": music_cfg["bpm"],
        "sample_rate": sample_rate,
        "slots": slots,
    }
    input_hash = compute_input_hash(cache_payload)
    cache_file = cache_root / f"score_placeholder_{input_hash}.wav"
    provider = "local-synth"
    model = f"placeholder-{music_cfg['placeholder_mode']}"

    if cache_file.exists():
        copy_artifact(cache_file, out_file)
        if lang == "en":
            copy_artifact(out_file, legacy_out)
        log_run(
            stage="music",
            shot_id=None,
            provider=provider,
            model=model,
            params={"total_duration_sec": total_dur, "key": music_cfg["key_signature"]},
            seed=42,
            input_hash=input_hash,
            cache_hit=True,
            status="ok",
            latency_ms=int((time.perf_counter() - t0) * 1000),
            cost_usd=0.0,
            output_path=out_file,
        )
        print(f"[music] Cache hit for soft anthem score ({total_dur:.2f}s)")
        return out_file

    _synthesize_ambient_bed(slots, sample_rate, cache_file)
    copy_artifact(cache_file, out_file)
    if lang == "en":
        copy_artifact(out_file, legacy_out)
    dur = probe_duration(out_file)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    log_run(
        stage="music",
        shot_id=None,
        provider=provider,
        model=model,
        params={"total_duration_sec": round(dur, 2), "key": music_cfg["key_signature"]},
        seed=42,
        input_hash=input_hash,
        cache_hit=False,
        status="ok",
        latency_ms=latency_ms,
        cost_usd=0.0,
        output_path=out_file,
    )
    print(f"[music] Synthesized original soft anthem bed ({dur:.2f}s, {latency_ms}ms) -> {out_file}")
    return out_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare music score (ACE-Step candidate or Phase 1 ambient bed).")
    parser.add_argument("--storyboard", type=Path, default=STORYBOARD_PATH)
    parser.add_argument("--candidate", type=Path, default=None, help="Optional ACE-Step .wav/.mp3 candidate path")
    parser.add_argument("--lang", default="en", choices=["en", "am"])
    args = parser.parse_args(argv)
    run_music_stage(storyboard_path=args.storyboard, candidate_path=args.candidate, lang=args.lang)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
