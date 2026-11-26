"""Unified CLI orchestrator for the Heritage Short pipeline."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pipeline.assemble import run_assemble_stage
from pipeline.common import STORYBOARD_PATH, load_env
from pipeline.keyframes import run_keyframes_stage
from pipeline.music import run_music_stage
from pipeline.narration import run_narration_stage
from pipeline.script import run_script_stage
from pipeline.shots import run_shots_stage
from pipeline.validate import load_and_validate_storyboard


def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Run the Red Through the Years film pipeline.")
    parser.add_argument(
        "target",
        choices=["validate", "radio-cut", "film", "script", "narration", "music", "keyframes", "shots", "assemble"],
        help="Pipeline target or single stage to execute.",
    )
    parser.add_argument("--storyboard", type=Path, default=STORYBOARD_PATH)
    parser.add_argument("--lang", default="en", choices=["en", "am"])
    parser.add_argument("--shot", default=None, help="Limit narration/keyframes/shots to one shot_id.")
    parser.add_argument(
        "--allow-placeholder",
        action="store_true",
        help="Allow offline placeholder narration if GEMINI_API_KEY is unset.",
    )
    parser.add_argument("--ref-sheet", action="store_true", help="For keyframes: generate character ref sheet only.")
    args = parser.parse_args(argv)

    # Always validate contract before any stage executes
    load_and_validate_storyboard(args.storyboard)

    if args.target == "validate":
        print("[ok] storyboard.json passed schema + domain validation.")
        return 0

    if args.target == "script":
        run_script_stage(storyboard_path=args.storyboard)
        return 0

    if args.target == "narration":
        run_narration_stage(
            storyboard_path=args.storyboard,
            lang=args.lang,
            shot_filter=args.shot,
            allow_placeholder=args.allow_placeholder,
        )
        return 0

    if args.target == "music":
        run_music_stage(storyboard_path=args.storyboard, lang=args.lang)
        return 0

    if args.target == "keyframes":
        run_keyframes_stage(
            storyboard_path=args.storyboard,
            shot_filter=args.shot,
            ref_sheet_only=args.ref_sheet,
        )
        return 0

    if args.target == "shots":
        for aspect in ("16:9", "9:16"):
            run_shots_stage(storyboard_path=args.storyboard, aspect=aspect, shot_filter=args.shot)
        return 0

    if args.target == "assemble":
        run_assemble_stage(storyboard_path=args.storyboard, mode="radio-cut", lang=args.lang)
        return 0

    if args.target == "radio-cut":
        run_script_stage(storyboard_path=args.storyboard)
        run_narration_stage(
            storyboard_path=args.storyboard,
            lang=args.lang,
            allow_placeholder=True if (args.allow_placeholder or not os.environ.get("GEMINI_API_KEY")) else False,
        )
        run_music_stage(storyboard_path=args.storyboard, lang=args.lang)
        run_assemble_stage(storyboard_path=args.storyboard, mode="radio-cut", lang=args.lang)
        return 0

    if args.target == "film":
        run_script_stage(storyboard_path=args.storyboard)
        run_narration_stage(
            storyboard_path=args.storyboard,
            lang=args.lang,
            allow_placeholder=True if (args.allow_placeholder or not os.environ.get("GEMINI_API_KEY")) else False,
        )
        run_music_stage(storyboard_path=args.storyboard, lang=args.lang)
        has_cf = bool(os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_API_TOKEN"))
        keyframes_dir = Path("outputs/keyframes")
        has_keyframes = keyframes_dir.exists() and any(keyframes_dir.glob("shot_*.png"))
        if has_cf:
            run_keyframes_stage(storyboard_path=args.storyboard)
            has_keyframes = True
        if has_keyframes:
            for aspect in ("16:9", "9:16"):
                run_shots_stage(storyboard_path=args.storyboard, aspect=aspect)
            run_assemble_stage(storyboard_path=args.storyboard, mode="film", lang=args.lang)
        else:
            print(
                "[film] Visual keyframes/shots not yet generated (Phase 2 Cloudflare/Wan credentials unset).\n"
                "       Falling back cleanly to Phase 1 radio-cut assembly (`outputs/radio-cut.mp4`).",
                file=sys.stderr,
            )
            run_assemble_stage(storyboard_path=args.storyboard, mode="radio-cut", lang=args.lang)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
