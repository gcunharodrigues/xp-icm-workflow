#!/usr/bin/env python
"""Match algorithm for lessons.md (xp-icm-workflow v3.0.0).

Reads a lessons.md (sequence of lessons separated by `---`, each with
YAML frontmatter + Markdown body) and selects the N most relevant for
a task context (profile/tier/tags/files).

Principles:
- G1 (strict on append, tolerant on read): malformed lessons are skipped
  with a warning on stderr; we never abort mid-parse.
- G2 (separate critical channel): lessons with `severity: critical` go into
  `result["critical"]`, and do NOT compete for slots in top_n normals.
- Q10 (deterministic ordering with clear tie-breaks).
- G3 (aging detection): function `find_aging_candidates` for curation.

CLI:
  python scripts/lessons-match.py --lessons lessons.md \
      --profile <p> --tier <t> --tags <csv> --files <csv> [--top-n 3] [--aging]
"""

from __future__ import annotations

import argparse
import dataclasses
import fnmatch
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

# --- Constants ---------------------------------------------------------------

SEPARATOR = "---"
SEVERITY_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}
VALID_SEVERITIES = frozenset(SEVERITY_RANK)
AGING_DAYS_THRESHOLD = 180
AGING_RECENT_MATCHES_THRESHOLD = 5

WEIGHT_TAGS = 0.4
WEIGHT_PROFILE = 0.2
WEIGHT_TIER = 0.2
WEIGHT_FILES = 0.2


# --- Types -------------------------------------------------------------------


class LessonsMatchError(Exception):
    """Fatal parse or I/O error from lessons-match."""


@dataclasses.dataclass(frozen=True)
class Lesson:
    """A lesson parsed from lessons.md."""

    id: int
    date: date
    tags: tuple[str, ...]
    severity: str
    title: str
    profile_match: tuple[str, ...] | None = None
    tier_match: tuple[str, ...] | None = None
    related_files: tuple[str, ...] | None = None
    match_history: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class MatchContext:
    """Task context to be matched against lessons."""

    profile: str
    tier: str
    tags: list[str]
    files: list[str]


# --- Parsing -----------------------------------------------------------------


def _split_blocks(raw: str) -> list[tuple[int, str]]:
    """Split the file into lesson blocks, returning (line_offset, block)."""
    if not raw.strip():
        return []
    lines = raw.splitlines()
    blocks: list[tuple[int, str]] = []
    current: list[str] = []
    current_start = 0
    in_frontmatter = False
    has_started = False
    for idx, line in enumerate(lines):
        if line.strip() == SEPARATOR:
            if not has_started:
                # Opening `---` of the first frontmatter.
                has_started = True
                in_frontmatter = True
                current_start = idx
                current = [line]
                continue
            if in_frontmatter:
                # `---` closing the current frontmatter; still part of the same block.
                in_frontmatter = False
                current.append(line)
                continue
            # `---` separator between lessons: emit current block and open new one.
            blocks.append((current_start, "\n".join(current)))
            in_frontmatter = True
            current_start = idx
            current = [line]
            continue
        if has_started:
            current.append(line)
    if has_started and current:
        blocks.append((current_start, "\n".join(current)))
    return blocks


def _parse_block(block: str) -> tuple[dict[str, Any], str]:
    """Separate YAML frontmatter from the body of a lesson block."""
    lines = block.splitlines()
    if not lines or lines[0].strip() != SEPARATOR:
        raise ValueError("block does not start with '---'")
    fm_end = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == SEPARATOR:
            fm_end = idx
            break
    if fm_end is None:
        raise ValueError("frontmatter not closed")
    fm_text = "\n".join(lines[1:fm_end])
    body = "\n".join(lines[fm_end + 1:]).strip()
    try:
        data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML: {exc}")
    if not isinstance(data, dict):
        raise ValueError("frontmatter is not a YAML mapping")
    return data, body


def _extract_title(body: str) -> str:
    """Extract the title from the first `# Lesson NN — <title>` line."""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            text = stripped.lstrip("#").strip()
            for sep in (" — ", " - ", " – "):
                if sep in text:
                    return text.split(sep, 1)[1].strip()
            return text
    return ""


def _coerce_lesson(data: dict[str, Any], body: str) -> Lesson:
    """Validate required fields and return an immutable Lesson."""
    lesson_id = data.get("id")
    if not isinstance(lesson_id, int) or isinstance(lesson_id, bool):
        raise ValueError("field 'id' missing or not an int")
    raw_date = data.get("date")
    if not isinstance(raw_date, str):
        raise ValueError("field 'date' missing or not an ISO string")
    try:
        parsed_date = date.fromisoformat(raw_date)
    except ValueError as exc:
        raise ValueError(f"invalid date: {exc}")
    tags = data.get("tags")
    if not isinstance(tags, list) or not tags:
        raise ValueError("field 'tags' missing or empty")
    severity = data.get("severity")
    if severity not in VALID_SEVERITIES:
        raise ValueError(f"invalid severity: {severity!r}")
    return Lesson(
        id=lesson_id,
        date=parsed_date,
        tags=tuple(str(t) for t in tags),
        severity=severity,
        title=_extract_title(body),
        profile_match=_optional_tuple(data.get("profile_match")),
        tier_match=_optional_tuple(data.get("tier_match")),
        related_files=_optional_tuple(data.get("related_files")),
        match_history=tuple(str(x) for x in data.get("_match_history", []) or []),
    )


def _optional_tuple(value: Any) -> tuple[str, ...] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError(f"expected list field, got {type(value).__name__}")
    return tuple(str(x) for x in value)


def parse_lessons(path: Path) -> tuple[list[Lesson], int]:
    """Parse lessons.md tolerating malformed entries (G1).

    Returns (valid_lessons, num_skipped). Emits warning on stderr for each
    malformed entry found, in format: `WARN: lesson at offset N malformed: <reason>`.
    """
    if not path.exists():
        raise LessonsMatchError(f"file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    lessons: list[Lesson] = []
    skipped = 0
    for offset, block in _split_blocks(raw):
        try:
            data, body = _parse_block(block)
            lessons.append(_coerce_lesson(data, body))
        except ValueError as exc:
            print(
                f"WARN: lesson at offset {offset} malformed: {exc}",
                file=sys.stderr,
            )
            skipped += 1
    return lessons, skipped


# --- Scoring -----------------------------------------------------------------


def _tag_overlap_ratio(lesson_tags: tuple[str, ...], task_tags: list[str]) -> float:
    if not task_tags:
        return 0.0
    lesson_set = set(lesson_tags)
    overlap = sum(1 for t in task_tags if t in lesson_set)
    return overlap / len(task_tags)


def _files_glob_hit(lesson_globs: tuple[str, ...] | None, task_files: list[str]) -> float:
    """1.0 if at least one (glob, file) pair matches; 0.0 otherwise.

    Convention `None` (no restriction) is handled outside this function by the caller.
    """
    if not lesson_globs or not task_files:
        return 0.0
    for pattern in lesson_globs:
        for f in task_files:
            if fnmatch.fnmatch(f, pattern):
                return 1.0
    return 0.0


def score_lesson(lesson: Lesson, ctx: MatchContext) -> float:
    """Score [0, 1] of the lesson for the context. Deterministic."""
    tag_score = _tag_overlap_ratio(lesson.tags, ctx.tags)
    profile_score = (
        1.0 if lesson.profile_match is None else (1.0 if ctx.profile in lesson.profile_match else 0.0)
    )
    tier_score = (
        1.0 if lesson.tier_match is None else (1.0 if ctx.tier in lesson.tier_match else 0.0)
    )
    files_score = (
        1.0 if lesson.related_files is None else _files_glob_hit(lesson.related_files, ctx.files)
    )
    return (
        WEIGHT_TAGS * tag_score
        + WEIGHT_PROFILE * profile_score
        + WEIGHT_TIER * tier_score
        + WEIGHT_FILES * files_score
    )


# --- Match (top_n + critical) ------------------------------------------------


def _sort_key(scored: tuple[Lesson, float], ctx: MatchContext) -> tuple:
    """Sort by score desc, severity desc, date desc, tag overlap desc.

    Ascending tuple → negate the "desc" fields.
    """
    lesson, score = scored
    overlap = sum(1 for t in ctx.tags if t in set(lesson.tags))
    return (
        -score,
        -SEVERITY_RANK[lesson.severity],
        -lesson.date.toordinal(),
        -overlap,
        lesson.id,
    )


def _to_payload(lesson: Lesson, score: float) -> dict[str, Any]:
    return {
        "id": lesson.id,
        "score": round(score, 6),
        "severity": lesson.severity,
        "title": lesson.title,
    }


def match(path: Path, ctx: MatchContext, top_n: int = 3) -> dict[str, Any]:
    """Full match: top_n normals + critical separated.

    Critical (severity=critical) go to their own channel, capped at 3, and
    do NOT enter top_n normals (G2). Score>0 required to enter any channel.
    """
    lessons, skipped = parse_lessons(path)
    scored = [(lesson, score_lesson(lesson, ctx)) for lesson in lessons]
    scored = [(l, s) for l, s in scored if s > 0]
    normals = [(l, s) for l, s in scored if l.severity != "critical"]
    criticals = [(l, s) for l, s in scored if l.severity == "critical"]
    normals.sort(key=lambda x: _sort_key(x, ctx))
    criticals.sort(key=lambda x: _sort_key(x, ctx))
    return {
        "top_n": [_to_payload(l, s) for l, s in normals[:top_n]],
        "critical": [_to_payload(l, s) for l, s in criticals[:3]],
        "skipped_malformed": skipped,
    }


# --- Aging detection (G3) ----------------------------------------------------


def find_aging_candidates(lessons: list[Lesson], today: date) -> list[dict[str, Any]]:
    """Old lessons (>180 days) with few recent matches (<5).

    Returns candidates for human curation — does not archive automatically.
    """
    candidates: list[dict[str, Any]] = []
    for lesson in lessons:
        days_since = (today - lesson.date).days
        if days_since <= AGING_DAYS_THRESHOLD:
            continue
        if len(lesson.match_history) >= AGING_RECENT_MATCHES_THRESHOLD:
            continue
        candidates.append(
            {
                "id": lesson.id,
                "date": lesson.date.isoformat(),
                "days_since": days_since,
                "last_matched": lesson.match_history[0] if lesson.match_history else None,
            }
        )
    candidates.sort(key=lambda c: -c["days_since"])
    return candidates


# --- CLI ---------------------------------------------------------------------


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Match lessons.md against task context.")
    parser.add_argument("--lessons", required=True, help="Path to lessons.md")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--tier", required=True)
    parser.add_argument("--tags", required=True, help="CSV of task tags")
    parser.add_argument("--files", required=True, help="CSV of touched files")
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument("--aging", action="store_true", help="Curation mode: list aging lessons.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    path = Path(args.lessons)
    try:
        if args.aging:
            lessons, skipped = parse_lessons(path)
            payload = {
                "aging": find_aging_candidates(lessons, date.today()),
                "skipped_malformed": skipped,
            }
        else:
            ctx = MatchContext(
                profile=args.profile,
                tier=args.tier,
                tags=_parse_csv(args.tags),
                files=_parse_csv(args.files),
            )
            payload = match(path, ctx, top_n=args.top_n)
    except LessonsMatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
