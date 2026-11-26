"""Shared utilities: env loading, deterministic caching, retries, runs.jsonl logging, FFmpeg."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

T = TypeVar("T")

REPO_ROOT = Path(__file__).resolve().parent.parent
STORYBOARD_PATH = REPO_ROOT / "storyboard.json"
SCHEMA_PATH = REPO_ROOT / "schema" / "storyboard.schema.json"
OUTPUTS_DIR = REPO_ROOT / "outputs"
CACHE_DIR = OUTPUTS_DIR / "cache"
RUNS_LOG_PATH = REPO_ROOT / "runs.jsonl"

RUN_SESSION_ID = os.environ.get("HERITAGE_RUN_ID") or f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"


def load_env(env_path: Path | None = None) -> None:
    """Load key=value pairs from .env without overriding existing environment variables."""
    target = env_path or (REPO_ROOT / ".env")
    if not target.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(dotenv_path=target, override=False)
        return
    except ImportError:
        pass

    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def compute_input_hash(payload: dict[str, Any]) -> str:
    """Return a stable 16-char SHA-256 hex digest for canonicalized JSON inputs."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def file_sha256(path: Path) -> str:
    """Return a 16-char SHA-256 digest of a file's bytes."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _retry_delay_seconds(exc: BaseException, attempt: int, base_delay_sec: float) -> float:
    """Prefer Retry-After for HTTP 429; otherwise exponential backoff with a 429-aware floor."""
    delay = base_delay_sec * (2 ** (attempt - 1))
    code = getattr(exc, "code", None)
    headers = getattr(exc, "headers", None)
    if code == 429:
        delay = max(delay, 8.0)
        if headers is not None:
            retry_after = headers.get("Retry-After")
            if retry_after:
                try:
                    delay = max(delay, float(retry_after))
                except ValueError:
                    pass
    return delay


def with_retries(
    fn: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay_sec: float = 1.5,
    retryable: tuple[type[BaseException], ...] = (Exception,),
    on_retry: Callable[[int, BaseException, float], None] | None = None,
) -> T:
    """Run fn with exponential backoff retries."""
    attempt = 1
    while True:
        try:
            return fn()
        except retryable as exc:
            if attempt >= max_attempts:
                raise
            delay = _retry_delay_seconds(exc, attempt, base_delay_sec)
            if on_retry is not None:
                on_retry(attempt, exc, delay)
            time.sleep(delay)
            attempt += 1


def log_run(
    *,
    stage: str,
    shot_id: str | None,
    provider: str,
    model: str,
    params: dict[str, Any],
    seed: int | None,
    input_hash: str,
    cache_hit: bool,
    status: str,
    latency_ms: int,
    cost_usd: float = 0.0,
    output_path: str | Path | None = None,
    error: str | None = None,
    log_path: Path | None = None,
) -> dict[str, Any]:
    """Append a single structured JSON record to runs.jsonl."""
    record: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_id": RUN_SESSION_ID,
        "stage": stage,
        "shot_id": shot_id,
        "provider": provider,
        "model": model,
        "params": params,
        "seed": seed,
        "input_hash": input_hash,
        "cache_hit": cache_hit,
        "status": status,
        "latency_ms": latency_ms,
        "cost_usd": round(cost_usd, 6),
        "output_path": _rel_path(output_path) if output_path else None,
        "error": error,
    }
    target = log_path or RUNS_LOG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _rel_path(path: str | Path) -> str:
    p = Path(path)
    try:
        return str(p.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(p)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def copy_artifact(src: Path, dst: Path) -> Path:
    ensure_dir(dst.parent)
    if src.resolve() != dst.resolve():
        shutil.copy2(src, dst)
    return dst


def probe_duration(media_path: Path) -> float:
    """Measure audio or video duration in seconds using wave (for WAV) or ffprobe."""
    if media_path.suffix.lower() == ".wav":
        try:
            with wave.open(str(media_path), "rb") as wf:
                rate = wf.getframerate()
                if rate > 0:
                    return wf.getnframes() / float(rate)
        except wave.Error:
            pass

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(media_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(proc.stdout.strip())


def run_ffmpeg(args: Iterable[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Execute ffmpeg with quiet logging and clear error reporting."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"FFmpeg failed (exit {proc.returncode}): {proc.stderr.strip()}\nCmd: {' '.join(cmd)}")
    return proc


def check_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("FFmpeg and ffprobe are required on PATH. Install FFmpeg and retry.")
