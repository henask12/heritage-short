"""Stage 6 (assemble): Build Phase 1 radio-cut.mp4 or Phase 3 16:9 + 9:16 final films via FFmpeg."""

from __future__ import annotations

import argparse
import json
import textwrap
import time
import wave
from pathlib import Path
from typing import Any

from pipeline.common import (
    CACHE_DIR,
    OUTPUTS_DIR,
    REPO_ROOT,
    STORYBOARD_PATH,
    check_ffmpeg_available,
    compute_input_hash,
    ensure_dir,
    load_env,
    log_run,
    probe_duration,
    run_ffmpeg,
)
from pipeline.validate import load_and_validate_storyboard

ASPECT_DIMENSIONS = {
    "16:9": (1280, 720),
    "9:16": (720, 1280),
}


def _format_srt_timestamp(seconds: float) -> str:
    ms_total = max(0, int(round(seconds * 1000)))
    hours, rem = divmod(ms_total, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _wrap_subtitle(text: str, width: int = 44) -> str:
    lines = textwrap.wrap(text.strip(), width=width)
    return "\n".join(lines[:3])


def _write_silence_wav(duration_sec: float, sample_rate: int, out_path: Path) -> None:
    ensure_dir(out_path.parent)
    n_frames = max(1, int(round(duration_sec * sample_rate)))
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)


def _pad_or_trim_wav(src: Path, target_duration_sec: float, sample_rate: int, out_path: Path) -> None:
    run_ffmpeg(
        [
            "-i",
            str(src),
            "-af",
            f"apad=whole_dur={target_duration_sec:.3f},atrim=0:{target_duration_sec:.3f}",
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(out_path),
        ]
    )


def _build_timeline(storyboard: dict[str, Any], lang: str) -> tuple[list[dict[str, Any]], str]:
    manifest_path = OUTPUTS_DIR / "narration" / lang / "manifest.json"
    manifest_map: dict[str, dict[str, Any]] = {}
    tts_mode = "placeholder_silence"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        tts_mode = manifest.get("tts_mode", "placeholder_silence")
        for item in manifest.get("shots", []):
            manifest_map[item["shot_id"]] = item

    timeline: list[dict[str, Any]] = []
    cursor = 0.0
    for shot in storyboard["shots"]:
        sid = shot["id"]
        m_entry = manifest_map.get(sid, {})
        audio_rel = m_entry.get("audio_path")
        audio_path = (REPO_ROOT / audio_rel) if audio_rel else None
        measured_sec = float(m_entry.get("audio_duration_sec", 0.0))
        planned_sec = float(shot["duration_sec"])
        slot_sec = max(planned_sec, measured_sec + 0.6) if (tts_mode == "gemini_tts" and measured_sec > 0) else planned_sec

        timeline.append(
            {
                "shot": shot,
                "start_sec": round(cursor, 3),
                "end_sec": round(cursor + slot_sec, 3),
                "slot_sec": round(slot_sec, 3),
                "audio_path": audio_path if (audio_path and audio_path.exists()) else None,
                "measured_sec": measured_sec,
            }
        )
        cursor += slot_sec
    return timeline, tts_mode


def _write_srt(timeline: list[dict[str, Any]], lang: str, srt_path: Path, wrap_width: int = 44) -> Path:
    ensure_dir(srt_path.parent)
    blocks: list[str] = []
    idx = 1
    for item in timeline:
        text = item["shot"]["narration"].get(lang, "").strip()
        if not text:
            continue
        start = _format_srt_timestamp(item["start_sec"] + 0.15)
        end = _format_srt_timestamp(max(item["start_sec"] + 1.0, item["end_sec"] - 0.25))
        blocks.append(f"{idx}\n{start} --> {end}\n{_wrap_subtitle(text, width=wrap_width)}\n")
        idx += 1
    srt_path.write_text("\n".join(blocks), encoding="utf-8")
    return srt_path


def _concat_narration_track(
    timeline: list[dict[str, Any]],
    sample_rate: int,
    work_dir: Path,
) -> Path:
    seg_paths: list[Path] = []
    for item in timeline:
        sid = item["shot"]["id"]
        seg_out = work_dir / f"nar_{sid}.wav"
        if item["audio_path"] is not None:
            _pad_or_trim_wav(item["audio_path"], item["slot_sec"], sample_rate, seg_out)
        else:
            _write_silence_wav(item["slot_sec"], sample_rate, seg_out)
        seg_paths.append(seg_out)

    concat_list = work_dir / "nar_concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in seg_paths) + "\n",
        encoding="utf-8",
    )
    nar_full = work_dir / "narration_full.wav"
    run_ffmpeg(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(nar_full),
        ]
    )
    return nar_full


def _mix_audio(
    *,
    narration_wav: Path,
    music_wav: Path,
    storyboard: dict[str, Any],
    tts_mode: str,
    work_dir: Path,
) -> Path:
    mix_cfg = storyboard["audio"]["mix"]
    target_lufs = float(mix_cfg["target_lufs"])
    true_peak = float(mix_cfg["true_peak_dbtp"])
    music_base_db = float(mix_cfg["music_base_gain_db"])

    mixed_wav = work_dir / "mixed_master.wav"
    if tts_mode == "gemini_tts":
        # Real narration: duck music underneath voice using sidechain compression, then normalize to -14 LUFS
        filter_complex = (
            f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[voice_mix][voice_sc];"
            f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={music_base_db}dB[music_base];"
            f"[music_base][voice_sc]sidechaincompress=threshold=0.02:ratio=6:attack=25:release=350[music_ducked];"
            f"[voice_mix][music_ducked]amix=inputs=2:duration=first:normalize=0,"
            f"loudnorm=I={target_lufs}:TP={true_peak}:LRA=11[outa]"
        )
    else:
        # Offline placeholder narration: blend soft pacing cues with audible warm ambient score
        filter_complex = (
            f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0dB[voice_cue];"
            f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=-6dB[music_bed];"
            f"[voice_cue][music_bed]amix=inputs=2:duration=first:normalize=0,"
            f"loudnorm=I={target_lufs}:TP={true_peak}:LRA=11[outa]"
        )

    run_ffmpeg(
        [
            "-i",
            str(narration_wav),
            "-i",
            str(music_wav),
            "-filter_complex",
            filter_complex,
            "-map",
            "[outa]",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(mixed_wav),
        ]
    )
    return mixed_wav


def _render_end_card_segment(
    *,
    storyboard: dict[str, Any],
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
    work_dir: Path,
    out_path: Path,
) -> Path:
    ec = storyboard["end_card"]
    title_file = work_dir / "ec_title.txt"
    credit_file = work_dir / "ec_credit.txt"
    disclosure_file = work_dir / "ec_disclosure.txt"
    consent_file = work_dir / "ec_consent.txt"

    wrap_cols = 58 if width >= height else 34
    title_file.write_text(ec["title"], encoding="utf-8")
    credit_file.write_text(ec["credit"], encoding="utf-8")
    disclosure_file.write_text("\n".join(textwrap.wrap(ec["ai_disclosure"], width=wrap_cols)), encoding="utf-8")
    consent_file.write_text("\n".join(textwrap.wrap(ec["consent_notice"], width=wrap_cols)), encoding="utf-8")

    title_size = 46 if width >= height else 38
    credit_size = 24 if width >= height else 22
    body_size = 18 if width >= height else 17
    fade_out_start = max(0.0, duration_sec - 1.0)

    vf = (
        f"drawbox=x=iw*0.18:y=ih*0.44:w=iw*0.64:h=2:color=#9E1B24@0.9:t=fill,"
        f"drawtext=font='Inter':textfile='{title_file.resolve()}':fontcolor=#F5EFE6:fontsize={title_size}:"
        f"x=(w-text_w)/2:y=h*0.26,"
        f"drawtext=font='Inter':textfile='{credit_file.resolve()}':fontcolor=#D99A4E:fontsize={credit_size}:"
        f"x=(w-text_w)/2:y=h*0.36,"
        f"drawtext=font='Inter':textfile='{disclosure_file.resolve()}':fontcolor=#D8D4CE:fontsize={body_size}:"
        f"line_spacing=6:x=(w-text_w)/2:y=h*0.50,"
        f"drawtext=font='Inter':textfile='{consent_file.resolve()}':fontcolor=#A8A29A:fontsize={body_size - 2}:"
        f"line_spacing=5:x=(w-text_w)/2:y=h*0.68,"
        f"fade=t=in:st=0:d=0.6,fade=t=out:st={fade_out_start:.3f}:d=0.9,format=yuv420p"
    )
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c=#121014:s={width}x{height}:r={fps}:d={duration_sec:.3f}",
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "24",
            "-an",
            str(out_path),
        ]
    )
    return out_path


def _render_radio_slate_segment(
    *,
    shot: dict[str, Any],
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
    tts_mode: str,
    work_dir: Path,
    out_path: Path,
) -> Path:
    sid = shot["id"]
    header_file = work_dir / f"slate_hdr_{sid}.txt"
    beat_file = work_dir / f"slate_beat_{sid}.txt"
    cue_file = work_dir / f"slate_cue_{sid}.txt"

    mode_badge = "GEMINI TTS" if tts_mode == "gemini_tts" else "RADIO CUT (OFFLINE AUDIO PLACEHOLDER)"
    header_file.write_text(f"RED THROUGH THE YEARS  |  {mode_badge}", encoding="utf-8")
    beat_file.write_text(f"{sid.upper()}  •  {shot['beat_title']}\n{shot['era']}", encoding="utf-8")
    cue_file.write_text(f"Music cue: {shot['music_cue']['id']} ({shot['music_cue']['mood']})", encoding="utf-8")

    vf = (
        f"drawbox=x=64:y=92:w=iw-128:h=2:color=#9E1B24@0.85:t=fill,"
        f"drawtext=font='Inter':textfile='{header_file.resolve()}':fontcolor=#9E1B24:fontsize=16:x=64:y=56,"
        f"drawtext=font='Inter':textfile='{beat_file.resolve()}':fontcolor=#EAE2D3:fontsize=28:"
        f"line_spacing=10:x=64:y=120,"
        f"drawtext=font='Inter':textfile='{cue_file.resolve()}':fontcolor=#8C8680:fontsize=16:x=64:y=204,"
        f"format=yuv420p"
    )
    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"color=c=#0D0C0F:s={width}x{height}:r={fps}:d={duration_sec:.3f}",
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "26",
            "-an",
            str(out_path),
        ]
    )
    return out_path


def _burn_subtitles_and_mux(
    *,
    video_in: Path,
    audio_in: Path,
    srt_path: Path,
    storyboard: dict[str, Any],
    out_path: Path,
    crf: int = 23,
) -> None:
    ensure_dir(out_path.parent)
    sub_cfg = storyboard["subtitles"]
    # Escape colons/backslashes for FFmpeg subtitles filter
    srt_escaped = str(srt_path.resolve()).replace("\\", "/").replace(":", "\\:")
    style_str = (
        f"FontName={sub_cfg['font_name']},"
        f"FontSize={sub_cfg['font_size']},"
        f"PrimaryColour=&H00F7F4EE,"
        f"OutlineColour=&H00101014,"
        f"BackColour=&H70000000,"
        f"BorderStyle=1,Outline=2,Shadow=1,MarginV=42"
    )
    vf = f"subtitles='{srt_escaped}':force_style='{style_str}'" if sub_cfg["burned_in"] else "null"

    run_ffmpeg(
        [
            "-i",
            str(video_in),
            "-i",
            str(audio_in),
            "-vf",
            vf,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(out_path),
        ]
    )


def run_assemble_stage(
    *,
    storyboard_path: Path = STORYBOARD_PATH,
    mode: str = "radio-cut",
    lang: str = "en",
    aspects: list[str] | None = None,
) -> list[Path]:
    load_env()
    check_ffmpeg_available()
    storyboard = load_and_validate_storyboard(storyboard_path)

    fps = int(storyboard["project"]["fps"])
    sample_rate = int(storyboard["audio"]["narration"]["sample_rate_hz"])
    timeline, tts_mode = _build_timeline(storyboard, lang=lang)

    music_wav = OUTPUTS_DIR / "music" / f"score-{lang}.wav"
    if not music_wav.exists():
        music_wav = OUTPUTS_DIR / "music" / "score.wav"
    if not music_wav.exists():
        raise FileNotFoundError(
            f"Music bed missing at {music_wav}. Run `make stage-music` first."
        )

    work_dir = ensure_dir(CACHE_DIR / "assemble" / mode)
    narration_wav = _concat_narration_track(timeline, sample_rate, work_dir)
    mixed_audio = _mix_audio(
        narration_wav=narration_wav,
        music_wav=music_wav,
        storyboard=storyboard,
        tts_mode=tts_mode,
        work_dir=work_dir,
    )

    outputs: list[Path] = []
    target_aspects = ["16:9"] if mode == "radio-cut" else (aspects or storyboard["project"]["aspect_ratios"])

    for aspect in target_aspects:
        t0 = time.perf_counter()
        width, height = ASPECT_DIMENSIONS[aspect]
        tag = aspect.replace(":", "x")
        wrap_width = 48 if width >= height else 28

        # Brief requires burned-in English subtitles always, even on the Amharic audio track.
        subtitle_lang = "en"
        srt_name = f"{lang}.srt" if aspect == "16:9" else f"{lang}-{tag}.srt"
        if lang == "am":
            srt_name = f"en-over-am.srt" if aspect == "16:9" else f"en-over-am-{tag}.srt"
        srt_path = OUTPUTS_DIR / "subtitles" / srt_name
        _write_srt(timeline, subtitle_lang, srt_path, wrap_width=wrap_width)

        seg_files: list[Path] = []
        for item in timeline:
            shot = item["shot"]
            sid = shot["id"]
            seg_out = work_dir / f"seg_{tag}_{sid}.mp4"
            if shot["shot_type"] == "end_card":
                _render_end_card_segment(
                    storyboard=storyboard,
                    duration_sec=item["slot_sec"],
                    width=width,
                    height=height,
                    fps=fps,
                    work_dir=work_dir,
                    out_path=seg_out,
                )
            elif mode == "radio-cut":
                _render_radio_slate_segment(
                    shot=shot,
                    duration_sec=item["slot_sec"],
                    width=width,
                    height=height,
                    fps=fps,
                    tts_mode=tts_mode,
                    work_dir=work_dir,
                    out_path=seg_out,
                )
            else:
                clip = OUTPUTS_DIR / "shots" / tag / f"{sid}.mp4"
                if not clip.exists():
                    raise FileNotFoundError(
                        f"Missing rendered shot clip {clip}. Run `make stage-keyframes && make stage-shots` "
                        f"or assemble the Phase 1 radio cut with `make radio-cut`."
                    )
                run_ffmpeg(
                    [
                        "-stream_loop",
                        "-1",
                        "-i",
                        str(clip),
                        "-t",
                        f"{item['slot_sec']:.3f}",
                        "-vf",
                        f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={fps},format=yuv420p",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "medium",
                        "-crf",
                        "20",
                        "-an",
                        str(seg_out),
                    ]
                )
            seg_files.append(seg_out)

        concat_txt = work_dir / f"video_concat_{tag}.txt"
        concat_txt.write_text(
            "\n".join(f"file '{p.resolve()}'" for p in seg_files) + "\n",
            encoding="utf-8",
        )
        video_joined = work_dir / f"video_joined_{tag}.mp4"
        run_ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_txt),
                "-c",
                "copy",
                str(video_joined),
            ]
        )

        if mode == "radio-cut":
            out_path = OUTPUTS_DIR / ("radio-cut-am.mp4" if lang == "am" else "radio-cut.mp4")
            crf = 27
        else:
            slug = storyboard["project"]["slug"]
            suffix = f"{slug}-{tag}-am.mp4" if lang == "am" else f"{slug}-{tag}.mp4"
            out_path = OUTPUTS_DIR / "final" / suffix
            crf = 21

        _burn_subtitles_and_mux(
            video_in=video_joined,
            audio_in=mixed_audio,
            srt_path=srt_path,
            storyboard=storyboard,
            out_path=out_path,
            crf=crf,
        )

        final_dur = probe_duration(out_path)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        input_hash = compute_input_hash(
            {
                "stage": "assemble",
                "mode": mode,
                "aspect": aspect,
                "lang": lang,
                "tts_mode": tts_mode,
                "shots": [(i["shot"]["id"], i["slot_sec"]) for i in timeline],
            }
        )
        log_run(
            stage="assemble",
            shot_id=None,
            provider="local-ffmpeg",
            model=f"ffmpeg-assemble-{mode}",
            params={
                "aspect": aspect,
                "lang": lang,
                "tts_mode": tts_mode,
                "duration_sec": round(final_dur, 2),
                "target_lufs": storyboard["audio"]["mix"]["target_lufs"],
                "burned_in_subtitles": storyboard["subtitles"]["burned_in"],
            },
            seed=None,
            input_hash=input_hash,
            cache_hit=False,
            status="ok",
            latency_ms=latency_ms,
            cost_usd=0.0,
            output_path=out_path,
        )
        print(f"[assemble] Built {out_path} ({final_dur:.2f}s, {aspect}, {latency_ms}ms)")
        outputs.append(out_path)

    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assemble radio cut or full film via FFmpeg.")
    parser.add_argument("--storyboard", type=Path, default=STORYBOARD_PATH)
    parser.add_argument("--mode", default="radio-cut", choices=["radio-cut", "film"])
    parser.add_argument("--lang", default="en", choices=["en", "am"])
    args = parser.parse_args(argv)
    run_assemble_stage(storyboard_path=args.storyboard, mode=args.mode, lang=args.lang)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
