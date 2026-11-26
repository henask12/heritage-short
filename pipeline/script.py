"""Stage 1 (script): Validate storyboard contract and optionally critique/refine via Gemini Flash."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from pipeline.common import (
    CACHE_DIR,
    STORYBOARD_PATH,
    compute_input_hash,
    ensure_dir,
    load_env,
    log_run,
    with_retries,
)
from pipeline.validate import load_and_validate_storyboard, summarize_storyboard

GEMINI_FLASH_MODEL = "gemini-3.8-flash"


def _call_gemini_flash(api_key: str, prompt: str, model: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["candidates"][0]["content"]["parts"][0]["text"]


def run_script_stage(
    *,
    storyboard_path: Path = STORYBOARD_PATH,
    critique: bool = False,
) -> dict[str, Any]:
    load_env()
    storyboard = load_and_validate_storyboard(storyboard_path)
    summary = summarize_storyboard(storyboard)

    print(
        f"[script] Validated '{summary['title']}': "
        f"{summary['shots']} shots | {summary['total_duration_sec']}s | "
        f"{summary['en_word_count']} EN words (~{summary['estimated_wpm']} WPM)"
    )
    for shot in storyboard["shots"]:
        wc = len(shot["narration"]["en"].split())
        print(
            f"  - {shot['id']} ({shot['duration_sec']:4.1f}s | {wc:2d}w | {shot['motion_strategy']:11s}) "
            f"{shot['beat_title']} — {shot['era']}"
        )

    if not critique:
        return summary

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[script] GEMINI_API_KEY is unset; skipping Gemini Flash critique.", file=sys.stderr)
        return summary

    prompt = (
        "Review this 60-90s documentary storyboard for pacing, non-fan emotional clarity, "
        "and adherence to the theme 'fandom as family heritage'. Give 3 concise actionable notes.\n\n"
        + json.dumps(storyboard, ensure_ascii=False, indent=2)
    )
    payload_hash = compute_input_hash({"stage": "script_critique", "model": GEMINI_FLASH_MODEL, "prompt": prompt})
    cache_file = ensure_dir(CACHE_DIR / "script") / f"critique_{payload_hash}.txt"

    start = time.perf_counter()
    if cache_file.exists():
        text = cache_file.read_text(encoding="utf-8")
        log_run(
            stage="script",
            shot_id=None,
            provider="google-gemini",
            model=GEMINI_FLASH_MODEL,
            params={"task": "storyboard_critique"},
            seed=None,
            input_hash=payload_hash,
            cache_hit=True,
            status="ok",
            latency_ms=int((time.perf_counter() - start) * 1000),
            cost_usd=0.0,
            output_path=cache_file,
        )
        print(f"[script] Cached Gemini critique ({cache_file.name}):\n{text}")
        return summary

    try:
        text = with_retries(lambda: _call_gemini_flash(api_key, prompt, GEMINI_FLASH_MODEL))
        cache_file.write_text(text, encoding="utf-8")
        log_run(
            stage="script",
            shot_id=None,
            provider="google-gemini",
            model=GEMINI_FLASH_MODEL,
            params={"task": "storyboard_critique"},
            seed=None,
            input_hash=payload_hash,
            cache_hit=False,
            status="ok",
            latency_ms=int((time.perf_counter() - start) * 1000),
            cost_usd=0.0,
            output_path=cache_file,
        )
        print(f"[script] Gemini critique:\n{text}")
    except (urllib.error.URLError, KeyError, RuntimeError) as exc:
        log_run(
            stage="script",
            shot_id=None,
            provider="google-gemini",
            model=GEMINI_FLASH_MODEL,
            params={"task": "storyboard_critique"},
            seed=None,
            input_hash=payload_hash,
            cache_hit=False,
            status="error",
            latency_ms=int((time.perf_counter() - start) * 1000),
            cost_usd=0.0,
            error=str(exc),
        )
        raise
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and inspect storyboard script stage.")
    parser.add_argument("--storyboard", type=Path, default=STORYBOARD_PATH)
    parser.add_argument("--critique", action="store_true", help="Run optional Gemini Flash pacing critique.")
    args = parser.parse_args(argv)
    run_script_stage(storyboard_path=args.storyboard, critique=args.critique)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
