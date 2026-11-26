"""Stage 2 (narration): Gemini TTS per shot with input-hash caching, retries, and offline placeholder."""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import struct
import sys
import tempfile
import time
import urllib.error
import urllib.request
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
    load_env,
    log_run,
    probe_duration,
    run_ffmpeg,
    with_retries,
)
from pipeline.validate import load_and_validate_storyboard


def _parse_pcm_rate(mime_type: str, default_rate: int = 24000) -> int:
    match = re.search(r"rate=(\d+)", mime_type)
    return int(match.group(1)) if match else default_rate


def _write_pcm_wav(pcm_bytes: bytes, out_path: Path, sample_rate: int) -> None:
    ensure_dir(out_path.parent)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit signed LE PCM
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)


def _call_gemini_tts(
    *,
    api_key: str,
    model: str,
    voice_name: str,
    style_prompt: str,
    text: str,
    target_rate: int,
    out_path: Path,
) -> dict[str, Any]:
    """Call Gemini TTS REST endpoint and save 16-bit mono WAV at target_rate."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    prompt_text = f"{style_prompt}\n\nSpeak the following line naturally:\n{text}"
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": voice_name,
                    }
                }
            },
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    parts = data["candidates"][0]["content"]["parts"]
    inline = None
    for part in parts:
        if "inlineData" in part and part["inlineData"].get("data"):
            inline = part["inlineData"]
            break
    if inline is None:
        raise RuntimeError(f"Gemini TTS response contained no inlineData audio: {json.dumps(data)[:300]}")

    mime_type = inline.get("mimeType", "audio/L16;codec=pcm;rate=24000")
    raw_audio = base64.b64decode(inline["data"])

    if "pcm" in mime_type.lower() or "l16" in mime_type.lower():
        src_rate = _parse_pcm_rate(mime_type, default_rate=target_rate)
        if src_rate == target_rate:
            _write_pcm_wav(raw_audio, out_path, target_rate)
        else:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                _write_pcm_wav(raw_audio, tmp_path, src_rate)
                run_ffmpeg(["-i", str(tmp_path), "-ar", str(target_rate), "-ac", "1", str(out_path)])
            finally:
                tmp_path.unlink(missing_ok=True)
    else:
        ext = ".mp3" if "mpeg" in mime_type.lower() else ".wav"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(raw_audio)
            tmp_path = Path(tmp.name)
        try:
            run_ffmpeg(["-i", str(tmp_path), "-ar", str(target_rate), "-ac", "1", "-c:a", "pcm_s16le", str(out_path)])
        finally:
            tmp_path.unlink(missing_ok=True)

    return {"mime_type": mime_type, "bytes": len(raw_audio)}


# Prefer storyboard / GEMINI_TTS_MODEL first; fall over on 429/503/404 to other TTS SKUs.
DEFAULT_TTS_FALLBACKS = (
    "gemini-2.5-flash-preview-tts",
    "gemini-3.8-flash-lite-tts",
    "gemini-3.8-flash-tts",
    "gemini-3.1-flash-tts-preview",
)


def _tts_model_candidates(preferred: str) -> list[str]:
    """Build ordered TTS model list: preferred, then GEMINI_TTS_MODELS, then built-in fallbacks."""
    env_list = [
        m.strip()
        for m in os.environ.get("GEMINI_TTS_MODELS", "").split(",")
        if m.strip()
    ]
    ordered: list[str] = []
    for model in [preferred, *env_list, *DEFAULT_TTS_FALLBACKS]:
        if model and model not in ordered:
            ordered.append(model)
    return ordered


def _is_rate_or_capacity_error(exc: BaseException) -> bool:
    code = getattr(exc, "code", None)
    if code in {429, 503}:
        return True
    message = str(exc).lower()
    return "429" in message or "too many requests" in message or "high demand" in message or "unavailable" in message


def _call_gemini_tts_with_model_fallback(
    *,
    api_key: str,
    preferred_model: str,
    voice_name: str,
    style_prompt: str,
    text: str,
    target_rate: int,
    out_path: Path,
    shot_id: str,
) -> str:
    """Try preferred TTS model, then fallbacks, with per-model retries on transient errors."""
    last_error: BaseException | None = None
    for model in _tts_model_candidates(preferred_model):
        try:
            with_retries(
                lambda m=model: _call_gemini_tts(
                    api_key=api_key,
                    model=m,
                    voice_name=voice_name,
                    style_prompt=style_prompt,
                    text=text,
                    target_rate=target_rate,
                    out_path=out_path,
                ),
                max_attempts=4,
                base_delay_sec=4.0,
                on_retry=lambda att, exc, d, m=model: print(
                    f"[narration] {shot_id}/{m}: attempt {att} failed ({exc}), retrying in {d:.1f}s...",
                    file=sys.stderr,
                ),
            )
            if model != preferred_model:
                print(
                    f"[narration] {shot_id}: preferred model {preferred_model!r} unavailable; "
                    f"used fallback {model!r}",
                    file=sys.stderr,
                )
            return model
        except Exception as exc:  # noqa: BLE001 - fall over to next TTS model on capacity errors
            last_error = exc
            code = getattr(exc, "code", None)
            if code == 404 or _is_rate_or_capacity_error(exc):
                print(
                    f"[narration] {shot_id}: model {model!r} failed ({exc}); trying next TTS fallback...",
                    file=sys.stderr,
                )
                time.sleep(2.0)
                continue
            raise
    assert last_error is not None
    raise last_error


def _trim_silence(src: Path, dst: Path, sample_rate: int) -> None:
    """Trim leading/trailing near-silence so Gemini TTS padding does not blow the 60–90s budget."""
    ensure_dir(dst.parent)
    run_ffmpeg(
        [
            "-i",
            str(src),
            "-af",
            "silenceremove=start_periods=1:start_silence=0.12:start_threshold=-40dB:"
            "stop_periods=-1:stop_silence=0.22:stop_threshold=-40dB",
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(dst),
        ]
    )


def _generate_placeholder_wav(duration_sec: float, sample_rate: int, out_path: Path) -> None:
    """Create a quiet placeholder WAV with a soft 60ms pacing cue at t=0.15s for offline radio-cut tests."""
    ensure_dir(out_path.parent)
    total_samples = max(1, int(round(duration_sec * sample_rate)))
    cue_start = int(0.15 * sample_rate)
    cue_len = int(0.06 * sample_rate)
    freq = 587.33  # D5 soft marker chime matching D-minor score

    frames = bytearray(total_samples * 2)
    for i in range(total_samples):
        sample = 0.0
        if cue_start <= i < cue_start + cue_len:
            t = (i - cue_start) / float(sample_rate)
            env = math.sin(math.pi * (i - cue_start) / float(cue_len))
            sample = 0.06 * env * math.sin(2.0 * math.pi * freq * t)
        val = max(-32767, min(32767, int(sample * 32767)))
        struct.pack_into("<h", frames, i * 2, val)

    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))


def run_narration_stage(
    *,
    storyboard_path: Path = STORYBOARD_PATH,
    lang: str = "en",
    shot_filter: str | None = None,
    allow_placeholder: bool = False,
) -> dict[str, Any]:
    load_env()
    storyboard = load_and_validate_storyboard(storyboard_path)

    nar_cfg = storyboard["audio"]["narration"]
    model = os.environ.get("GEMINI_TTS_MODEL") or nar_cfg["model"]
    voice_name = os.environ.get("GEMINI_TTS_VOICE") or nar_cfg["voice_name"]
    if lang == "am":
        style_prompt = (
            "Speak clear, warm Amharic in a reflective documentary narrator voice. "
            "Natural pacing, sincere emotion, brief pauses at sentence ends."
        )
    else:
        style_prompt = nar_cfg["style_prompt"]
    sample_rate = int(nar_cfg["sample_rate_hz"])
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    use_placeholder = not bool(api_key)
    if use_placeholder and not allow_placeholder:
        print(
            "[narration] GEMINI_API_KEY is not set.\n"
            "  To generate real Gemini TTS narration:\n"
            "    1. cp .env.example .env\n"
            "    2. Add GEMINI_API_KEY=<your-key> to .env\n"
            "    3. Run: make stage-narration\n"
            "  Or for an offline silent/cue radio cut, run: make radio-cut",
            file=sys.stderr,
        )
        raise RuntimeError("GEMINI_API_KEY missing (run with --allow-placeholder for offline radio cut).")

    if use_placeholder:
        print(
            "[narration] GEMINI_API_KEY is unset — running in offline placeholder mode.\n"
            "            Placeholder cache keys are isolated from Gemini TTS keys; once GEMINI_API_KEY is set,\n"
            "            re-running `make stage-narration` or `make radio-cut` will automatically generate real voice."
        )

    cache_root = ensure_dir(CACHE_DIR / "narration")
    out_root = ensure_dir(OUTPUTS_DIR / "narration" / lang)

    manifest_shots: list[dict[str, Any]] = []
    generated_count = 0
    cached_count = 0

    for shot in storyboard["shots"]:
        sid = shot["id"]
        if shot_filter and sid != shot_filter:
            continue

        text = shot["narration"].get(lang, "").strip()
        if not text:
            manifest_shots.append(
                {
                    "shot_id": sid,
                    "has_narration": False,
                    "mode": "silent_card",
                    "planned_duration_sec": float(shot["duration_sec"]),
                    "audio_duration_sec": 0.0,
                    "audio_path": None,
                    "text": "",
                }
            )
            continue

        provider = "local-synth" if use_placeholder else "google-gemini"
        effective_model = "placeholder-silence-cue" if use_placeholder else model
        mode = "placeholder_silence" if use_placeholder else "gemini_tts"

        cache_payload = {
            "stage": "narration",
            "mode": mode,
            "lang": lang,
            "provider": provider,
            "model": effective_model,
            "voice_name": voice_name,
            "style_prompt": style_prompt,
            "sample_rate_hz": sample_rate,
            "text": text,
            "planned_duration_sec": float(shot["duration_sec"]) if use_placeholder else None,
        }
        input_hash = compute_input_hash(cache_payload)
        cache_file = cache_root / f"{sid}_{lang}_{input_hash}.wav"
        out_file = out_root / f"{sid}.wav"

        t0 = time.perf_counter()
        trimmed_cache = cache_root / f"{sid}_{lang}_{input_hash}.trimmed.wav"
        if trimmed_cache.exists():
            copy_artifact(trimmed_cache, out_file)
            dur = probe_duration(out_file)
            latency_ms = int((time.perf_counter() - t0) * 1000)
            cached_count += 1
            log_run(
                stage="narration",
                shot_id=sid,
                provider=provider,
                model=effective_model,
                params={"lang": lang, "voice_name": voice_name, "mode": mode, "words": len(text.split()), "trimmed": True},
                seed=shot["seed"],
                input_hash=input_hash,
                cache_hit=True,
                status="ok",
                latency_ms=latency_ms,
                cost_usd=0.0,
                output_path=out_file,
            )
            print(f"[narration] {sid}: cache hit ({dur:.2f}s, {mode})")
        else:
            try:
                raw_cache = cache_file
                if use_placeholder:
                    _generate_placeholder_wav(float(shot["duration_sec"]), sample_rate, raw_cache)
                    copy_artifact(raw_cache, trimmed_cache)
                else:
                    used_model = model
                    if not raw_cache.exists():
                        used_model = _call_gemini_tts_with_model_fallback(
                            api_key=api_key,
                            preferred_model=model,
                            voice_name=voice_name,
                            style_prompt=style_prompt,
                            text=text,
                            target_rate=sample_rate,
                            out_path=raw_cache,
                            shot_id=sid,
                        )
                        # Soft pacing between TTS calls to stay under free-tier RPM limits
                        time.sleep(1.5)
                    else:
                        used_model = model
                    effective_model = used_model
                    _trim_silence(raw_cache, trimmed_cache, sample_rate)
                copy_artifact(trimmed_cache, out_file)
                dur = probe_duration(out_file)
                latency_ms = int((time.perf_counter() - t0) * 1000)
                generated_count += 1
                log_run(
                    stage="narration",
                    shot_id=sid,
                    provider=provider,
                    model=effective_model,
                    params={"lang": lang, "voice_name": voice_name, "mode": mode, "words": len(text.split()), "trimmed": True},
                    seed=shot["seed"],
                    input_hash=input_hash,
                    cache_hit=raw_cache.exists() and not use_placeholder and latency_ms < 500,
                    status="ok",
                    latency_ms=latency_ms,
                    cost_usd=0.0,
                    output_path=out_file,
                )
                print(f"[narration] {sid}: generated {dur:.2f}s ({mode}, {latency_ms}ms)")
            except Exception as exc:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                log_run(
                    stage="narration",
                    shot_id=sid,
                    provider=provider,
                    model=effective_model,
                    params={"lang": lang, "voice_name": voice_name, "mode": mode, "words": len(text.split())},
                    seed=shot["seed"],
                    input_hash=input_hash,
                    cache_hit=False,
                    status="error",
                    latency_ms=latency_ms,
                    cost_usd=0.0,
                    error=str(exc),
                )
                raise

        manifest_shots.append(
            {
                "shot_id": sid,
                "has_narration": True,
                "mode": mode,
                "planned_duration_sec": float(shot["duration_sec"]),
                "audio_duration_sec": round(dur, 3),
                "audio_path": str(out_file.relative_to(OUTPUTS_DIR.parent)),
                "text": text,
            }
        )

    manifest = {
        "lang": lang,
        "tts_mode": "placeholder_silence" if use_placeholder else "gemini_tts",
        "model": "placeholder-silence-cue" if use_placeholder else model,
        "voice_name": voice_name,
        "sample_rate_hz": sample_rate,
        "generated": generated_count,
        "cached": cached_count,
        "shots": manifest_shots,
    }
    manifest_path = out_root / "manifest.json"
    if not shot_filter:
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate per-shot narration via Gemini TTS.")
    parser.add_argument("--storyboard", type=Path, default=STORYBOARD_PATH)
    parser.add_argument("--lang", default="en", choices=["en", "am"])
    parser.add_argument("--shot", default=None, help="Optional single shot_id to regenerate")
    parser.add_argument(
        "--allow-placeholder",
        action="store_true",
        help="Allow offline silent+cue placeholder stubs when GEMINI_API_KEY is unset",
    )
    args = parser.parse_args(argv)
    run_narration_stage(
        storyboard_path=args.storyboard,
        lang=args.lang,
        shot_filter=args.shot,
        allow_placeholder=args.allow_placeholder,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
