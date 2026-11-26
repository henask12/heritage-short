"""Stage 5 (shots): Wan 2.2 clips, dual-plate cinematic motion, or Ken Burns fallback."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from pipeline.common import (
    CACHE_DIR,
    OUTPUTS_DIR,
    STORYBOARD_PATH,
    check_ffmpeg_available,
    compute_input_hash,
    copy_artifact,
    ensure_dir,
    file_sha256,
    load_env,
    log_run,
    run_ffmpeg,
)
from pipeline.validate import load_and_validate_storyboard

ASPECT_DIMENSIONS = {
    "16:9": (1280, 720),
    "9:16": (720, 1280),
}


def _motion_profile(motion_prompt: str, order: int) -> dict[str, str | bool]:
    """Map storyboard motion language into camera path presets."""
    text = motion_prompt.lower()
    if "tilt" in text or "upward" in text:
        return {"style": "tilt_up", "zoom_in": True}
    if "pan" in text or "lateral" in text or "glide" in text or "drift" in text:
        return {"style": "pan_right" if order % 2 == 0 else "pan_left", "zoom_in": True}
    if "pull-back" in text or "zoom-out" in text or "pull back" in text:
        return {"style": "pull_back", "zoom_in": False}
    if "arc" in text or "sweep" in text:
        return {"style": "arc_right", "zoom_in": True}
    if "push" in text or "dolly" in text or "hold" in text:
        return {"style": "push_in", "zoom_in": True}
    return {"style": "push_in" if order % 2 == 0 else "pull_back", "zoom_in": order % 2 == 0}


def _zoompan_filter(
    *,
    width: int,
    height: int,
    fps: int,
    total_frames: int,
    style: str,
    zoom_in: bool,
) -> str:
    if zoom_in:
        zoom_expr = f"min(1.18,1+0.16*(on/{total_frames}))"
    else:
        zoom_expr = f"max(1.0,1.16-0.16*(on/{total_frames}))"

    if style == "pan_right":
        x_expr = f"(iw-iw/zoom)*({total_frames}-on)/{total_frames}"
        y_expr = "ih/2-(ih/zoom/2)"
    elif style == "pan_left":
        x_expr = f"(iw-iw/zoom)*(on/{total_frames})"
        y_expr = "ih/2-(ih/zoom/2)"
    elif style == "tilt_up":
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = f"(ih-ih/zoom)*({total_frames}-on)/{total_frames}"
    elif style == "arc_right":
        x_expr = f"(iw-iw/zoom)*(0.15+0.7*(on/{total_frames}))"
        y_expr = f"ih/2-(ih/zoom/2)-(ih*0.04*sin(2*PI*on/{total_frames}))"
    elif style == "pull_back":
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    else:  # push_in
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = f"ih/2-(ih/zoom/2)+(ih*0.03*(on/{total_frames}))"

    return (
        f"scale={width * 3}:{height * 3}:force_original_aspect_ratio=increase,"
        f"crop={width * 3}:{height * 3},"
        f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':"
        f"d={total_frames}:s={width}x{height}:fps={fps}"
    )


def _render_ken_burns(
    *,
    keyframe: Path,
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
    zoom_in: bool,
    style: str,
    out_path: Path,
) -> None:
    total_frames = max(1, int(round(duration_sec * fps)))
    vf = _zoompan_filter(
        width=width,
        height=height,
        fps=fps,
        total_frames=total_frames,
        style=style,
        zoom_in=zoom_in,
    ) + ",format=yuv420p"
    run_ffmpeg(
        [
            "-loop",
            "1",
            "-i",
            str(keyframe),
            "-vf",
            vf,
            "-t",
            f"{duration_sec:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-an",
            str(out_path),
        ]
    )


def _render_dual_plate_motion(
    *,
    plate_a: Path,
    plate_b: Path,
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
    style: str,
    atmospheric: str | None,
    work_dir: Path,
    out_path: Path,
) -> None:
    """Animate A and B plates then crossfade for continuous camera-move motion video."""
    ensure_dir(work_dir)
    total_frames = max(2, int(round(duration_sec * fps)))
    half = max(duration_sec * 0.62, duration_sec * 0.5 + 0.4)
    fade = min(2.4, duration_sec * 0.42)
    fade_offset = max(0.2, half - fade)

    clip_a = work_dir / "plate_a.mp4"
    clip_b = work_dir / "plate_b.mp4"
    merged = work_dir / "merged.mp4"

    vf_a = _zoompan_filter(
        width=width,
        height=height,
        fps=fps,
        total_frames=max(2, int(round(half * fps))),
        style=style,
        zoom_in=True,
    ) + ",format=yuv420p"
    vf_b = _zoompan_filter(
        width=width,
        height=height,
        fps=fps,
        total_frames=max(2, int(round(half * fps))),
        style=style,
        zoom_in=style != "pull_back",
    ) + ",format=yuv420p"

    run_ffmpeg(
        [
            "-loop",
            "1",
            "-i",
            str(plate_a),
            "-vf",
            vf_a,
            "-t",
            f"{half:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-an",
            str(clip_a),
        ]
    )
    run_ffmpeg(
        [
            "-loop",
            "1",
            "-i",
            str(plate_b),
            "-vf",
            vf_b,
            "-t",
            f"{half:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-an",
            str(clip_b),
        ]
    )

    # Smooth morph between the two moving plates
    run_ffmpeg(
        [
            "-i",
            str(clip_a),
            "-i",
            str(clip_b),
            "-filter_complex",
            f"[0:v][1:v]xfade=transition=fade:duration={fade:.3f}:offset={fade_offset:.3f},format=yuv420p[v]",
            "-map",
            "[v]",
            "-t",
            f"{duration_sec:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-an",
            str(merged),
        ]
    )

    if atmospheric == "rain":
        run_ffmpeg(
            [
                "-i",
                str(merged),
                "-f",
                "lavfi",
                "-i",
                f"nullsrc=size={width}x{height}:rate={fps}:duration={duration_sec:.3f},"
                f"noise=alls=26:allf=t+u,format=gray,eq=contrast=2.4:brightness=0.08,"
                f"format=rgba,colorchannelmixer=aa=0.16",
                "-filter_complex",
                "[0:v][1:v]overlay=0:0:shortest=1,format=yuv420p",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-an",
                "-t",
                f"{duration_sec:.3f}",
                str(out_path),
            ]
        )
    else:
        copy_artifact(merged, out_path)


def _conform_wan_clip(
    *,
    wan_clip: Path,
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
    out_path: Path,
) -> None:
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={fps},format=yuv420p"
    )
    run_ffmpeg(
        [
            "-stream_loop",
            "-1",
            "-i",
            str(wan_clip),
            "-vf",
            vf,
            "-t",
            f"{duration_sec:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-an",
            str(out_path),
        ]
    )


def run_shots_stage(
    *,
    storyboard_path: Path = STORYBOARD_PATH,
    aspect: str = "16:9",
    shot_filter: str | None = None,
) -> list[Path]:
    load_env()
    check_ffmpeg_available()
    storyboard = load_and_validate_storyboard(storyboard_path)

    fps = int(storyboard["project"]["fps"])
    width, height = ASPECT_DIMENSIONS[aspect]
    tag = aspect.replace(":", "x")

    keyframes_dir = OUTPUTS_DIR / "keyframes"
    wan_dir = OUTPUTS_DIR / "shots" / "wan"
    cache_root = ensure_dir(CACHE_DIR / "shots" / tag)
    out_root = ensure_dir(OUTPUTS_DIR / "shots" / tag)
    work_root = ensure_dir(CACHE_DIR / "shots" / f"{tag}-work")

    produced: list[Path] = []
    for idx, shot in enumerate(storyboard["shots"]):
        sid = shot["id"]
        if shot["shot_type"] == "end_card":
            continue
        if shot_filter and sid != shot_filter:
            continue

        wan_clip = wan_dir / f"{sid}.mp4"
        keyframe = keyframes_dir / f"{sid}.png"
        keyframe_b = keyframes_dir / f"{sid}_b.png"
        # also accept jpg companions
        if not keyframe.exists():
            alt = keyframes_dir / f"{sid}.jpg"
            if alt.exists():
                keyframe = alt
        if not keyframe_b.exists():
            alt_b = keyframes_dir / f"{sid}_b.jpg"
            if alt_b.exists():
                keyframe_b = alt_b

        duration_sec = float(shot["duration_sec"])
        profile = _motion_profile(shot.get("motion_prompt", ""), shot.get("order", idx + 1))
        atmosphere = "rain" if any(k in shot.get("motion_prompt", "").lower() for k in ("rain", "floodlight")) else None

        if wan_clip.exists():
            mode = "wan_i2v_conform"
            src_sha = file_sha256(wan_clip)
            provider = "wan-2.2-kaggle"
            model = "wan-2.2-ti2v-5b"
        elif keyframe.exists() and keyframe_b.exists():
            mode = "dual_plate_motion"
            src_sha = file_sha256(keyframe) + file_sha256(keyframe_b)
            provider = "local-ffmpeg"
            model = "ffmpeg-dual-plate-cinematic-motion"
        elif keyframe.exists():
            mode = "ken_burns"
            src_sha = file_sha256(keyframe)
            provider = "local-ffmpeg"
            model = "ffmpeg-zoompan-ken-burns"
        else:
            print(
                f"[shots] {sid}: neither Wan clip ({wan_clip}) nor keyframe ({keyframe}) exists yet.",
                file=sys.stderr,
            )
            continue

        cache_payload = {
            "stage": "shots",
            "shot_id": sid,
            "mode": mode,
            "src_sha": src_sha,
            "duration_sec": duration_sec,
            "aspect": aspect,
            "fps": fps,
            "style": profile["style"],
            "atmosphere": atmosphere,
        }
        input_hash = compute_input_hash(cache_payload)
        cache_file = cache_root / f"{sid}_{input_hash}.mp4"
        out_file = out_root / f"{sid}.mp4"

        t0 = time.perf_counter()
        if cache_file.exists():
            copy_artifact(cache_file, out_file)
            log_run(
                stage="shots",
                shot_id=sid,
                provider=provider,
                model=model,
                params={"aspect": aspect, "duration_sec": duration_sec, "mode": mode, "style": profile["style"]},
                seed=shot["seed"],
                input_hash=input_hash,
                cache_hit=True,
                status="ok",
                latency_ms=int((time.perf_counter() - t0) * 1000),
                cost_usd=0.0,
                output_path=out_file,
            )
            print(f"[shots] {sid} ({aspect}): cache hit ({mode})")
            produced.append(out_file)
            continue

        if mode == "wan_i2v_conform":
            _conform_wan_clip(
                wan_clip=wan_clip,
                duration_sec=duration_sec,
                width=width,
                height=height,
                fps=fps,
                out_path=cache_file,
            )
        elif mode == "dual_plate_motion":
            _render_dual_plate_motion(
                plate_a=keyframe,
                plate_b=keyframe_b,
                duration_sec=duration_sec,
                width=width,
                height=height,
                fps=fps,
                style=str(profile["style"]),
                atmospheric=atmosphere,
                work_dir=work_root / sid,
                out_path=cache_file,
            )
        else:
            _render_ken_burns(
                keyframe=keyframe,
                duration_sec=duration_sec,
                width=width,
                height=height,
                fps=fps,
                zoom_in=bool(profile["zoom_in"]),
                style=str(profile["style"]),
                out_path=cache_file,
            )

        copy_artifact(cache_file, out_file)
        log_run(
            stage="shots",
            shot_id=sid,
            provider=provider,
            model=model,
            params={"aspect": aspect, "duration_sec": duration_sec, "mode": mode, "style": profile["style"]},
            seed=shot["seed"],
            input_hash=input_hash,
            cache_hit=False,
            status="ok",
            latency_ms=int((time.perf_counter() - t0) * 1000),
            cost_usd=0.0,
            output_path=out_file,
        )
        print(f"[shots] {sid} ({aspect}): rendered ({mode}/{profile['style']}) -> {out_file}")
        produced.append(out_file)

    return produced


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render cinematic motion shots (dual-plate / Ken Burns / Wan).")
    parser.add_argument("--storyboard", type=Path, default=STORYBOARD_PATH)
    parser.add_argument("--aspect", default="16:9", choices=["16:9", "9:16"])
    parser.add_argument("--shot", default=None)
    args = parser.parse_args(argv)
    run_shots_stage(storyboard_path=args.storyboard, aspect=args.aspect, shot_filter=args.shot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
