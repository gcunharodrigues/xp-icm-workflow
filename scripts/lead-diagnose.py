#!/usr/bin/env python3
"""Lead-diagnose — deterministic per-task diagnostic when loop fails.

Renders `output/wave-N/task-<slug>-diagnose.md` triggered by:
  T1 — cap 3 retries exhausted
  T2 — Jaccard convergence trip (>= 0.7) across rounds
  T3 — catastrophic detected (tests broken outside scope, build red, etc.)

Reads critic JSON outputs (per-round) + plan.md task spec + git state.
Outputs Markdown diagnose file per `references/lead-resolution-protocol.md`.

Canonical: references/lead-resolution-protocol.md
Plan: v3.9.0 §lead-resolution tier
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ============================================================================
# Constants
# ============================================================================

CURRENT_SKILL_VERSION = "3.9.0"

# Convergence threshold — drift-checked against canonical doc.
JACCARD_THRESHOLD = 0.7

# Catastrophic scope creep multiplier (Check 2 evidence threshold for catastrophic).
CATASTROPHIC_FILES_OUTSIDE_THRESHOLD = 5

VALID_TIERS = ("experimental", "tool", "development", "production")
VALID_TRIGGERS = ("T1_cap_exhausted", "T2_convergence_trip", "T3_catastrophic")
VALID_BUCKETS = ("B1", "B3", "B4")


# ============================================================================
# Concern clustering — Jaccard similarity across rounds
# ============================================================================

def _normalize_claim(claim: str) -> str:
    """Reduce claim to comparable token-set: lowercase + alphanum tokens >=4 chars."""
    tokens = re.findall(r"[a-z0-9_]{4,}", claim.lower())
    return " ".join(sorted(set(tokens)))


def _critic_to_set(critic_json: dict) -> set[str]:
    """Extract normalized claim signatures from critic concerns (BLOCKING+MAJOR only)."""
    out: set[str] = set()
    for c in critic_json.get("concerns", []):
        sev = c.get("severity", "MINOR")
        if sev not in ("BLOCKING", "MAJOR"):
            continue
        sig = _normalize_claim(c.get("claim", ""))
        if sig:
            out.add(sig)
    return out


def jaccard(a: set[str], b: set[str]) -> float:
    """Standard Jaccard: |A ∩ B| / |A ∪ B|. Empty union → 0.0."""
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


# ============================================================================
# Catastrophic detection (T3)
# ============================================================================

def _git_run(cwd: Path, *args: str) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as e:
        return 1, "", str(e)
    return result.returncode, result.stdout, result.stderr


def detect_catastrophic(
    cwd: Path,
    branch: str,
    base_branch: str,
    files_touched_declared: list[str],
    forensic_files_outside: int,
    build_command: str | None = None,
) -> list[dict]:
    """Return list of catastrophic signals detected (empty if none)."""
    signals: list[dict] = []

    # Signal 1: massive scope creep (forensic Check 2 evidence)
    if forensic_files_outside > CATASTROPHIC_FILES_OUTSIDE_THRESHOLD:
        signals.append({
            "name": "massive_scope_creep",
            "evidence": f"forensic+ Check 2: {forensic_files_outside} files outside declared (threshold: {CATASTROPHIC_FILES_OUTSIDE_THRESHOLD})",
            "bucket_hint": "B3",
        })

    # Signal 2: test files modified outside declared scope
    rc, out, err = _git_run(cwd, "diff", "--name-only", f"{base_branch}...{branch}")
    if rc == 0:
        modified = {ln.strip() for ln in out.splitlines() if ln.strip()}
        declared = set(files_touched_declared)
        # Test-file-shaped paths not in declared
        test_outside = {
            p for p in (modified - declared)
            if any(t in p for t in ("/test", "/tests/", "/__tests__/", "/spec/", "_test.", ".test.", ".spec."))
        }
        if test_outside:
            signals.append({
                "name": "tests_broken_outside_scope",
                "evidence": f"Test files modified outside declared scope: {sorted(test_outside)[:5]}",
                "bucket_hint": "B3",
            })

    # Signal 3: build globally broken
    if build_command:
        try:
            result = subprocess.run(
                build_command, shell=True, cwd=str(cwd),
                capture_output=True, text=True, check=False, timeout=120,
            )
            if result.returncode != 0:
                signals.append({
                    "name": "build_globally_broken",
                    "evidence": f"build command `{build_command}` exit {result.returncode}",
                    "bucket_hint": "B3",
                })
        except subprocess.TimeoutExpired:
            signals.append({
                "name": "build_globally_broken",
                "evidence": f"build command `{build_command}` timeout > 120s",
                "bucket_hint": "B3",
            })
        except OSError:
            pass  # build command unavailable; treat as not-catastrophic

    return signals


# ============================================================================
# Bucket recommendation
# ============================================================================

def recommend_bucket(
    trigger: str,
    catastrophic_signals: list[dict],
    convergence_score: float,
) -> tuple[str, str]:
    """Return (bucket, rationale) tuple."""
    if trigger == "T3_catastrophic":
        # Use first signal's hint, default B3
        hint = catastrophic_signals[0]["bucket_hint"] if catastrophic_signals else "B3"
        names = ", ".join(s["name"] for s in catastrophic_signals)
        return hint, f"catastrophic: {names}"

    if trigger == "T2_convergence_trip":
        return "B1", (
            f"Jaccard {convergence_score:.2f} ≥ {JACCARD_THRESHOLD}: writer e critic ciclam "
            "sobre mesmas concerns. Spec ambígua/insuficiente. B1 reescreve spec mais rigorosa."
        )

    if trigger == "T1_cap_exhausted":
        return "B1", "Cap 3 retries exhausted sem convergence trip. Default B1 (rewrite spec)."

    raise ValueError(f"unknown trigger: {trigger}")


# ============================================================================
# Surgical brief render (B1 helper)
# ============================================================================

def render_surgical_brief(
    rounds: list[dict],
) -> str:
    """Build top-3 concerns + acceptance delta brief for B1 spawn."""
    # Aggregate all BLOCKING+MAJOR concerns across rounds
    all_concerns: list[dict] = []
    for r in rounds:
        for c in r.get("concerns", []):
            if c.get("severity") in ("BLOCKING", "MAJOR"):
                all_concerns.append(c)

    # Count signature recurrences
    counter: dict[str, int] = {}
    examples: dict[str, dict] = {}
    for c in all_concerns:
        sig = _normalize_claim(c.get("claim", ""))
        if not sig:
            continue
        counter[sig] = counter.get(sig, 0) + 1
        if sig not in examples:
            examples[sig] = c

    top = sorted(counter.items(), key=lambda kv: -kv[1])[:3]
    if not top:
        return "(no recurring BLOCKING/MAJOR concerns to summarize)"

    lines = ["### Top concerns (recurring across rounds)\n"]
    for i, (sig, count) in enumerate(top, 1):
        c = examples[sig]
        lines.append(
            f"{i}. **{c.get('claim', '(no claim)')}** "
            f"(rounds: {count}, evidence: `{c.get('evidence', 'n/a')}`, severity: {c.get('severity', '?')})"
        )
        ce = c.get("counterexample")
        if ce:
            lines.append(f"   Counterexample: {ce}")
    lines.append("\n### Acceptance delta")
    lines.append("Spec original tem critérios ambíguos. Reescreva VALIDAÇÃO com:")
    for sig, _count in top:
        c = examples[sig]
        lines.append(f"- Test name específico cobrindo: {c.get('claim', '?')[:80]}")
    return "\n".join(lines)


# ============================================================================
# Diagnose document render
# ============================================================================

def render_diagnose_md(
    task_slug: str,
    wave_num: int,
    trigger: str,
    rounds: list[dict],
    convergence_pairs: list[tuple[int, int, float]],
    catastrophic_signals: list[dict],
    bucket: str,
    rationale: str,
    surgical_brief: str | None,
) -> str:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        f"# Diagnose — task {task_slug} (wave {wave_num})",
        "",
        "## Trigger",
        f"- condition: `{trigger}`",
        f"- detected_at: {now}",
        f"- attempts_so_far: {len(rounds)}",
        "",
        "## Critic concerns clustered (rounds 1-N)",
        "",
        "| Round | BLOCKING | MAJOR | Jaccard vs prev |",
        "|-------|----------|-------|-----------------|",
    ]
    jaccard_map = {b: score for _a, b, score in convergence_pairs}
    for i, r in enumerate(rounds, 1):
        blocking = sum(1 for c in r.get("concerns", []) if c.get("severity") == "BLOCKING")
        major = sum(1 for c in r.get("concerns", []) if c.get("severity") == "MAJOR")
        score_str = f"{jaccard_map[i]:.2f}" if i in jaccard_map else "n/a"
        lines.append(f"| {i} | {blocking} | {major} | {score_str} |")
    lines.append("")

    if catastrophic_signals:
        lines.append("## Catastrophic signals (T3)")
        lines.append("")
        for s in catastrophic_signals:
            lines.append(f"- **{s['name']}** — {s['evidence']} (hint: {s['bucket_hint']})")
        lines.append("")

    lines.append("## Bucket recommendation")
    lines.append(f"- bucket: **{bucket}**")
    lines.append(f"- rationale: {rationale}")
    lines.append("")

    if bucket == "B1" and surgical_brief:
        lines.append("## Surgical brief")
        lines.append("")
        lines.append(surgical_brief)
        lines.append("")

    return "\n".join(lines)


# ============================================================================
# Main orchestration
# ============================================================================

def diagnose(
    task_slug: str,
    wave_num: int,
    rounds: list[dict],
    files_touched_declared: list[str],
    cwd: Path,
    branch: str,
    base_branch: str,
    forensic_files_outside: int,
    build_command: str | None,
    explicit_trigger: str | None,
) -> dict:
    """Compute diagnose result. Returns dict with bucket, rationale, signals, etc."""
    # Compute convergence pairs (round i vs i-1)
    convergence_pairs: list[tuple[int, int, float]] = []
    for i in range(1, len(rounds)):
        prev_set = _critic_to_set(rounds[i - 1])
        curr_set = _critic_to_set(rounds[i])
        score = jaccard(prev_set, curr_set)
        convergence_pairs.append((i, i + 1, score))  # 1-indexed for display

    # Detect catastrophic
    catastrophic_signals = detect_catastrophic(
        cwd, branch, base_branch,
        files_touched_declared,
        forensic_files_outside,
        build_command,
    )

    # Determine trigger (caller may explicitly pass one; else auto-detect)
    if explicit_trigger:
        trigger = explicit_trigger
    elif catastrophic_signals:
        trigger = "T3_catastrophic"
    elif convergence_pairs and any(score >= JACCARD_THRESHOLD for _a, _b, score in convergence_pairs):
        trigger = "T2_convergence_trip"
    elif len(rounds) >= 3:
        trigger = "T1_cap_exhausted"
    else:
        # No trigger met; return empty recommendation
        return {
            "trigger": None,
            "bucket": None,
            "rationale": "no trigger met (rounds < 3, no convergence, no catastrophic)",
            "convergence_pairs": convergence_pairs,
            "catastrophic_signals": catastrophic_signals,
            "rounds": rounds,
        }

    convergence_score = max(
        (score for _a, _b, score in convergence_pairs), default=0.0,
    )
    bucket, rationale = recommend_bucket(trigger, catastrophic_signals, convergence_score)

    surgical = render_surgical_brief(rounds) if bucket == "B1" else None

    return {
        "trigger": trigger,
        "bucket": bucket,
        "rationale": rationale,
        "convergence_pairs": convergence_pairs,
        "convergence_max_score": convergence_score,
        "catastrophic_signals": catastrophic_signals,
        "rounds": rounds,
        "surgical_brief": surgical,
        "task_slug": task_slug,
        "wave_num": wave_num,
    }


# ============================================================================
# CLI
# ============================================================================

def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Lead-diagnose: per-task diagnostic + bucket recommendation.")
    p.add_argument("--task-slug", required=True)
    p.add_argument("--wave", required=True, type=int)
    p.add_argument("--workspace-num", required=True)
    p.add_argument("--base-branch", required=True)
    p.add_argument(
        "--critic-rounds", required=True,
        help="Comma-separated paths to critic JSON outputs in round order.",
    )
    p.add_argument("--files-touched", default="", help="Comma-separated declared files.")
    p.add_argument("--forensic-files-outside", type=int, default=0)
    p.add_argument("--build-command", default=None)
    p.add_argument("--trigger", choices=VALID_TRIGGERS, default=None,
                   help="Force trigger (override auto-detect).")
    p.add_argument("--output", default=None,
                   help="Path to write diagnose.md (default: stdout).")
    p.add_argument("--format", choices=("md", "json"), default="md")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    rounds: list[dict] = []
    for round_path in args.critic_rounds.split(","):
        rp = Path(round_path.strip())
        if not rp.is_file():
            sys.stderr.write(f"lead-diagnose: critic round file not found: {rp}\n")
            return 1
        try:
            rounds.append(json.loads(rp.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            sys.stderr.write(f"lead-diagnose: malformed JSON in {rp}: {e}\n")
            return 1

    files_touched = [f.strip() for f in args.files_touched.split(",") if f.strip()]
    branch = f"wave-{args.workspace_num}-{args.wave}/{args.task_slug}"

    result = diagnose(
        task_slug=args.task_slug,
        wave_num=args.wave,
        rounds=rounds,
        files_touched_declared=files_touched,
        cwd=Path.cwd(),
        branch=branch,
        base_branch=args.base_branch,
        forensic_files_outside=args.forensic_files_outside,
        build_command=args.build_command,
        explicit_trigger=args.trigger,
    )

    if args.format == "json":
        out_text = json.dumps(result, indent=2, default=str) + "\n"
    else:
        if result["trigger"] is None:
            out_text = (
                f"# Diagnose — task {args.task_slug} (wave {args.wave})\n\n"
                "## Trigger\n- condition: none (no trigger met)\n"
            )
        else:
            out_text = render_diagnose_md(
                task_slug=args.task_slug,
                wave_num=args.wave,
                trigger=result["trigger"],
                rounds=rounds,
                convergence_pairs=result["convergence_pairs"],
                catastrophic_signals=result["catastrophic_signals"],
                bucket=result["bucket"],
                rationale=result["rationale"],
                surgical_brief=result.get("surgical_brief"),
            )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out_text, encoding="utf-8")
    else:
        sys.stdout.write(out_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
