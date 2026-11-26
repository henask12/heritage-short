"""Stage 4 (keyframes): FLUX via Cloudflare Workers AI (Phase 2) with input-hash cache & retries."""

from __future__ import annotations

import argparse
import base64
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
    OUTPUTS_DIR,
    REPO_ROOT,
    STORYBOARD_PATH,
    compute_input_hash,
    copy_artifact,
    ensure_dir,
    file_sha256,
    load_env,
    log_run,
    with_retries,
)
from pipeline.validate import load_and_validate_storyboard

DEFAULT_FLUX_MODEL = "@cf/black-forest-labs/flux-1-schnell"


def _compose_prompt(storyboard: dict[str, Any], shot: dict[str, Any]) -> str:
    style = storyboard["style"]
    char_notes = []
    for key in shot.get("characters", []):
        char = storyboard["characters"][key]
        char_notes.append(f"{char['display_name']}: {char['physical_description']} Wearing: {char['wardrobe_anchor']}")
    parts = [shot["image_prompt"]]
    if char_notes:
        parts.append("Character consistency: " + " ".join(char_notes))
    parts.append(style["prompt_suffix"])
    return " ".join(parts)


def _call_cloudflare_flux(
    *,
    account_id: str,
    api_token: str,
    model: str,
    prompt: str,
    seed: int,
    steps: int,
    out_path: Path,
) -> None:
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    payload = {
        "prompt": prompt,
        "num_steps": steps,
        "seed": seed,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()
        content_type = resp.headers.get("Content-Type", "")

    ensure_dir(out_path.parent)
    if "application/json" in content_type:
        body = json.loads(raw.decode("utf-8"))
        img_b64 = body.get("result", {}).get("image")
        if not img_b64:
            raise RuntimeError(f"Cloudflare FLUX returned JSON without image: {str(body)[:300]}")
        out_path.write_bytes(base64.b64decode(img_b64))
    else:
        out_path.write_bytes(raw)


def run_keyframes_stage(
    *,
    storyboard_path: Path = STORYBOARD_PATH,
    shot_filter: str | None = None,
    ref_sheet_only: bool = False,
    model: str = DEFAULT_FLUX_MODEL,
    steps: int = 6,
) -> list[Path]:
    load_env()
    storyboard = load_and_validate_storyboard(storyboard_path)

    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not account_id or not api_token:
        print(
            "[keyframes] CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN not set (Phase 2 stage).\n"
            "            Add them to .env to generate FLUX keyframes via Cloudflare Workers AI.",
            file=sys.stderr,
        )
        raise RuntimeError("Cloudflare Workers AI credentials missing.")

    cache_root = ensure_dir(CACHE_DIR / "keyframes")
    out_root = ensure_dir(OUTPUTS_DIR / "keyframes")
    generated: list[Path] = []

    if ref_sheet_only:
        henok = storyboard["characters"]["henok_adult"]
        ref_img = REPO_ROOT / henok["reference_image"]
        ref_sha = file_sha256(ref_img) if ref_img.exists() else "none"
        prompt = (
            f"Character turnaround reference sheet (front, three-quarter, warm smile profile) of "
            f"{henok['physical_description']} Wearing {henok['wardrobe_anchor']} "
            f"{storyboard['style']['prompt_suffix']}"
        )
        cache_payload = {
            "stage": "keyframes_ref_sheet",
            "model": model,
            "steps": steps,
            "seed": 77701,
            "ref_sha": ref_sha,
            "prompt": prompt,
        }
        input_hash = compute_input_hash(cache_payload)
        cache_file = cache_root / f"ref_sheet_{input_hash}.png"
        out_file = out_root / "character-ref-sheet.png"
        t0 = time.perf_counter()
        if cache_file.exists():
            copy_artifact(cache_file, out_file)
            log_run(
                stage="keyframes",
                shot_id="ref_sheet",
                provider="cloudflare-workers-ai",
                model=model,
                params={"steps": steps, "task": "character_ref_sheet"},
                seed=77701,
                input_hash=input_hash,
                cache_hit=True,
                status="ok",
                latency_ms=int((time.perf_counter() - t0) * 1000),
                cost_usd=0.0,
                output_path=out_file,
            )
            print(f"[keyframes] ref_sheet: cache hit -> {out_file}")
            return [out_file]

        with_retries(
            lambda: _call_cloudflare_flux(
                account_id=account_id,
                api_token=api_token,
                model=model,
                prompt=prompt,
                seed=77701,
                steps=steps,
                out_path=cache_file,
            )
        )
        copy_artifact(cache_file, out_file)
        log_run(
            stage="keyframes",
            shot_id="ref_sheet",
            provider="cloudflare-workers-ai",
            model=model,
            params={"steps": steps, "task": "character_ref_sheet"},
            seed=77701,
            input_hash=input_hash,
            cache_hit=False,
            status="ok",
            latency_ms=int((time.perf_counter() - t0) * 1000),
            cost_usd=0.0,
            output_path=out_file,
        )
        print(f"[keyframes] ref_sheet: generated -> {out_file}")
        return [out_file]

    for shot in storyboard["shots"]:
        sid = shot["id"]
        if shot["shot_type"] == "end_card":
            continue
        if shot_filter and sid != shot_filter:
            continue

        prompt = _compose_prompt(storyboard, shot)
        ref_hashes = {}
        for ckey in shot.get("characters", []):
            rpath = storyboard["characters"][ckey].get("reference_image")
            if rpath and (REPO_ROOT / rpath).exists():
                ref_hashes[ckey] = file_sha256(REPO_ROOT / rpath)

        cache_payload = {
            "stage": "keyframes",
            "shot_id": sid,
            "model": model,
            "steps": steps,
            "seed": shot["seed"],
            "prompt": prompt,
            "negative_prompt": storyboard["style"]["negative_prompt"],
            "ref_hashes": ref_hashes,
        }
        input_hash = compute_input_hash(cache_payload)
        cache_file = cache_root / f"{sid}_{input_hash}.png"
        out_file = out_root / f"{sid}.png"

        t0 = time.perf_counter()
        if cache_file.exists():
            copy_artifact(cache_file, out_file)
            log_run(
                stage="keyframes",
                shot_id=sid,
                provider="cloudflare-workers-ai",
                model=model,
                params={"steps": steps},
                seed=shot["seed"],
                input_hash=input_hash,
                cache_hit=True,
                status="ok",
                latency_ms=int((time.perf_counter() - t0) * 1000),
                cost_usd=0.0,
                output_path=out_file,
            )
            print(f"[keyframes] {sid}: cache hit")
            generated.append(out_file)
            continue

        try:
            with_retries(
                lambda: _call_cloudflare_flux(
                    account_id=account_id,
                    api_token=api_token,
                    model=model,
                    prompt=prompt,
                    seed=shot["seed"],
                    steps=steps,
                    out_path=cache_file,
                ),
                max_attempts=3,
                base_delay_sec=2.0,
            )
            copy_artifact(cache_file, out_file)
            log_run(
                stage="keyframes",
                shot_id=sid,
                provider="cloudflare-workers-ai",
                model=model,
                params={"steps": steps},
                seed=shot["seed"],
                input_hash=input_hash,
                cache_hit=False,
                status="ok",
                latency_ms=int((time.perf_counter() - t0) * 1000),
                cost_usd=0.0,
                output_path=out_file,
            )
            print(f"[keyframes] {sid}: generated -> {out_file}")
            generated.append(out_file)
        except Exception as exc:
            log_run(
                stage="keyframes",
                shot_id=sid,
                provider="cloudflare-workers-ai",
                model=model,
                params={"steps": steps},
                seed=shot["seed"],
                input_hash=input_hash,
                cache_hit=False,
                status="error",
                latency_ms=int((time.perf_counter() - t0) * 1000),
                cost_usd=0.0,
                error=str(exc),
            )
            raise

    return generated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate FLUX keyframes via Cloudflare Workers AI (Phase 2).")
    parser.add_argument("--storyboard", type=Path, default=STORYBOARD_PATH)
    parser.add_argument("--shot", default=None, help="Regenerate only this shot_id")
    parser.add_argument("--ref-sheet", action="store_true", help="Generate character reference sheet only")
    parser.add_argument("--model", default=DEFAULT_FLUX_MODEL)
    parser.add_argument("--steps", type=int, default=6)
    args = parser.parse_args(argv)
    run_keyframes_stage(
        storyboard_path=args.storyboard,
        shot_filter=args.shot,
        ref_sheet_only=args.ref_sheet,
        model=args.model,
        steps=args.steps,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
