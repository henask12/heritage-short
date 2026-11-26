"""Validate storyboard.json against schema/storyboard.schema.json and domain guardrails."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from pipeline.common import REPO_ROOT, SCHEMA_PATH, STORYBOARD_PATH

# Living / recognizable football figures prohibited in visual prompts per ETHICS.md
FORBIDDEN_PLAYER_PATTERNS = [
    r"\bcristiano\s+ronaldo\b",
    r"\bwayne\s+rooney\b",
    r"\bbruno\s+fernandes\b",
    r"\bmarcus\s+rashford\b",
    r"\bkobbie\s+mainoo\b",
    r"\balejandro\s+garnacho\b",
    r"\bharry\s+maguire\b",
    r"\bdavid\s+beckham\b",
    r"\beric\s+cantona\b",
    r"\balex\s+ferguson\b",
    r"\brub[eé]n\s+amorim\b",
    r"\berik\s+ten\s+hag\b",
    r"\bryan\s+giggs\b",
    r"\bpaul\s+scholes\b",
]


def _check_type(value: Any, expected: str | list[str]) -> bool:
    if isinstance(expected, list):
        return any(_check_type(value, t) for t in expected)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _validate_fallback(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Pure-Python Draft 2020-12 subset validator so validation works with zero pip installs."""
    errors: list[str] = []

    expected_type = schema.get("type")
    if expected_type is not None and not _check_type(instance, expected_type):
        errors.append(f"{path}: expected type {expected_type}, got {type(instance).__name__}")
        return errors

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value {instance!r} not in allowed enum {schema['enum']}")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: string length {len(instance)} < minLength {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: string length {len(instance)} > maxLength {schema['maxLength']}")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            errors.append(f"{path}: string {instance!r} does not match pattern {schema['pattern']!r}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: value {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: value {instance} > maximum {schema['maximum']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: array length {len(instance)} < minItems {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: array length {len(instance)} > maxItems {schema['maxItems']}")
        if "items" in schema and isinstance(schema["items"], dict):
            for idx, item in enumerate(instance):
                errors.extend(_validate_fallback(item, schema["items"], f"{path}[{idx}]"))

    if isinstance(instance, dict):
        if "minProperties" in schema and len(instance) < schema["minProperties"]:
            errors.append(f"{path}: object has {len(instance)} properties < minProperties {schema['minProperties']}")
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{path}: missing required property {req!r}")

        props = schema.get("properties", {})
        addl = schema.get("additionalProperties", True)
        for key, val in instance.items():
            child_path = f"{path}.{key}"
            if key in props:
                errors.extend(_validate_fallback(val, props[key], child_path))
            elif addl is False:
                errors.append(f"{path}: unexpected additional property {key!r}")
            elif isinstance(addl, dict):
                errors.extend(_validate_fallback(val, addl, child_path))

    return errors


def _validate_json_schema(storyboard: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    try:
        from jsonschema import Draft202012Validator  # type: ignore

        validator = Draft202012Validator(schema)
        errs = sorted(validator.iter_errors(storyboard), key=lambda e: list(e.path))
        return [f"$.{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errs]
    except ImportError:
        return _validate_fallback(storyboard, schema)


def _validate_domain_rules(storyboard: dict[str, Any], repo_root: Path) -> list[str]:
    errors: list[str] = []
    shots = storyboard.get("shots", [])
    project = storyboard.get("project", {})
    characters = storyboard.get("characters", {})
    end_card = storyboard.get("end_card", {})

    # 1. Total duration within target bounds (60-90s)
    total_duration = sum(float(s.get("duration_sec", 0)) for s in shots)
    dur_min = float(project.get("target_duration_sec", {}).get("min", 60))
    dur_max = float(project.get("target_duration_sec", {}).get("max", 90))
    if not (dur_min <= total_duration <= dur_max):
        errors.append(
            f"Domain rule: total shot duration is {total_duration:.1f}s, outside target range [{dur_min:.0f}s, {dur_max:.0f}s]"
        )

    # 2. Narration English word count within 130-220 words
    en_words = sum(len(s.get("narration", {}).get("en", "").split()) for s in shots)
    if not (130 <= en_words <= 220):
        errors.append(f"Domain rule: total English narration is {en_words} words, expected 130-220 words")

    # 3. Shot IDs unique and sequential order 1..N
    seen_ids: set[str] = set()
    for idx, shot in enumerate(shots, start=1):
        sid = shot.get("id", "")
        if sid in seen_ids:
            errors.append(f"Domain rule: duplicate shot id {sid!r}")
        seen_ids.add(sid)
        if shot.get("order") != idx:
            errors.append(f"Domain rule: shot {sid!r} has order={shot.get('order')}, expected {idx}")

        # 4. Character references must exist
        for char_key in shot.get("characters", []):
            if char_key not in characters:
                errors.append(f"Domain rule: shot {sid!r} references unknown character {char_key!r}")

        # 5. Guardrail: no living footballer names in visual/motion prompts
        combined_prompt = f"{shot.get('image_prompt', '')} {shot.get('motion_prompt', '')}"
        for pattern in FORBIDDEN_PLAYER_PATTERNS:
            if re.search(pattern, combined_prompt, flags=re.IGNORECASE):
                errors.append(
                    f"Likeness guardrail violation in {sid!r}: prompt matched forbidden player pattern {pattern!r}"
                )

    # 6. End card shot linkage
    end_card_id = end_card.get("shot_id")
    matching = [s for s in shots if s.get("id") == end_card_id]
    if not matching:
        errors.append(f"Domain rule: end_card.shot_id {end_card_id!r} not found in shots")
    elif matching[0].get("shot_type") != "end_card":
        errors.append(f"Domain rule: end_card shot {end_card_id!r} must have shot_type='end_card'")

    # 7. Character reference images must exist on disk
    for char_key, char_cfg in characters.items():
        ref_path = char_cfg.get("reference_image")
        if ref_path:
            full_ref = repo_root / ref_path
            if not full_ref.exists():
                errors.append(
                    f"Domain rule: character {char_key!r} reference_image not found at {ref_path}"
                )

    return errors


def load_and_validate_storyboard(
    storyboard_path: Path | None = None,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    """Load storyboard.json and raise ValueError if schema or domain validation fails."""
    sb_path = storyboard_path or STORYBOARD_PATH
    sc_path = schema_path or SCHEMA_PATH

    if not sb_path.exists():
        raise FileNotFoundError(f"Storyboard not found: {sb_path}")
    if not sc_path.exists():
        raise FileNotFoundError(f"Schema not found: {sc_path}")

    storyboard = json.loads(sb_path.read_text(encoding="utf-8"))
    schema = json.loads(sc_path.read_text(encoding="utf-8"))

    errors = _validate_json_schema(storyboard, schema)
    if not errors:
        errors.extend(_validate_domain_rules(storyboard, sb_path.parent))

    if errors:
        formatted = "\n  - ".join(errors)
        raise ValueError(f"Storyboard validation failed ({len(errors)} error(s)):\n  - {formatted}")

    return storyboard


def summarize_storyboard(storyboard: dict[str, Any]) -> dict[str, Any]:
    shots = storyboard["shots"]
    total_duration = sum(float(s["duration_sec"]) for s in shots)
    spoken_duration = sum(float(s["duration_sec"]) for s in shots if s["narration"]["en"].strip())
    en_words = sum(len(s["narration"]["en"].split()) for s in shots)
    wpm = (en_words / spoken_duration) * 60.0 if spoken_duration > 0 else 0.0
    return {
        "title": storyboard["project"]["title"],
        "shots": len(shots),
        "total_duration_sec": round(total_duration, 2),
        "spoken_duration_sec": round(spoken_duration, 2),
        "en_word_count": en_words,
        "estimated_wpm": round(wpm, 1),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate storyboard.json against schema and guardrails.")
    parser.add_argument("--storyboard", type=Path, default=STORYBOARD_PATH)
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    args = parser.parse_args(argv)

    try:
        sb = load_and_validate_storyboard(args.storyboard, args.schema)
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    summary = summarize_storyboard(sb)
    print(
        f"[OK] {args.storyboard.name} valid — "
        f"{summary['shots']} shots, {summary['total_duration_sec']}s total, "
        f"{summary['en_word_count']} EN words (~{summary['estimated_wpm']} WPM)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
