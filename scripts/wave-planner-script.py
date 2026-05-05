#!/usr/bin/env python3
"""Deterministic Wave Planner (Stage 03 — no LLM).

Reads plan.md, builds a DAG of tasks (explicit deps + file conflicts),
detects cycles, performs topological sort into waves, subdivides into
sub-waves when they exceed the cap for the tier/profile, flags
ambiguities, and renders wave-plan.md (Markdown with YAML frontmatter)
+ ambiguities-resolved.md.

CLI:
  python scripts/wave-planner-script.py
      --plan stages/02_design/output/plan.md
      --tier development
      --profile app_web_backend
      --workspace 042-feat-auth
      --output stages/03_wave_planner/output/wave-plan.md
      [--ambiguities-output stages/03_wave_planner/output/ambiguities-resolved.md]

Stdout: total_tasks=N total_waves=M total_sub_waves=K ambiguities=A
Exit 0 = success. Exit 1 = error (cycle, invalid schema, etc).

Algorithms:
  - Kahn (level-based topological sort) -> avoids stack overflow.
  - DFS (3-color) -> deterministic cycle detection.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

# ----------------------------------------------------------------------------
# Constants (kept in sync with profile-merge)
# ----------------------------------------------------------------------------
TIER_CAP: dict[str, int] = {
    "experimental": 2,
    "tool": 3,
    "development": 5,
    "production": 5,
}

PROFILE_CAP_OVERRIDE: dict[str, int] = {
    "framework_library": 3,
    "ml_project": 3,
    "technical_article": 5,
}

VALID_PROFILES: frozenset[str] = frozenset({
    "app_web_backend",
    "app_web_frontend",
    "fullstack",
    "dashboard",
    "data_analysis",
    "ml_project",
    "agent_ia",
    "cli_tool",
    "framework_library",
    "technical_article",
    "experiment",
})

VALID_TIERS: frozenset[str] = frozenset(TIER_CAP.keys())


# v3.10.0 — User-facing paths per profile (defaults).
# Override via _config/profile-effective.yaml:e2e.user_facing_paths.
USER_FACING_PATHS_BY_PROFILE: dict[str, tuple[str, ...]] = {
    "app_web_backend": ("routes/", "controllers/", "handlers/", "endpoints/", "api/", "graphql/"),
    "app_web_frontend": ("pages/", "views/", "app/", "components/pages/", "src/routes/"),
    "fullstack": (
        "routes/", "controllers/", "handlers/", "endpoints/", "api/", "graphql/",
        "pages/", "views/", "app/", "components/pages/", "src/routes/",
    ),
    "cli_tool": ("cmd/", "cli/", "commands/"),
    "agent_ia": ("prompts/", "agents/", "tools/"),
    "framework_library": ("api/", "exports/"),
    "dashboard": ("pages/", "views/", "dashboards/"),
    "data_analysis": (),  # notebook-based, e2e not applicable
    "ml_project": ("pipelines/", "inference/"),
    "technical_article": (),  # doc-only
    "experiment": (),  # POC, e2e opt-in
}


def _task_requires_e2e(files_touched: list[str], profile: str) -> bool:
    """True if any declared file path matches user_facing_paths of profile."""
    paths = USER_FACING_PATHS_BY_PROFILE.get(profile, ())
    if not paths:
        return False
    return any(any(p in f for p in paths) for f in files_touched)

SLUG_RE = re.compile(r"^## Task ([a-z0-9][a-z0-9-]*):", re.MULTILINE)
TASK_HEADER_RE = re.compile(r"^## Task (\S+):", re.MULTILINE)
KEBAB_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Heading drift detection — canonical schema in
# references/4-block-contract-template.md requires task headers at h2 and
# 4-block subsections + metadata at h3. LLM occasionally generates plan.md
# with offset (h4/h5/h6). Without this pre-flight the parser would return
# silently "no tasks found" far from the real cause.
TASK_HEADING_DRIFT_RE = re.compile(r"^#{3,6}\s+Task\s+\S+\s*:", re.MULTILINE)
SUBSECTION_DRIFT_RE = re.compile(
    r"^#{4,6}\s+(WHAT|HOW|OUT OF SCOPE|VALIDATION|Files touched|Depends on)\b",
    re.MULTILINE,
)


# ----------------------------------------------------------------------------
# Errors + dataclass
# ----------------------------------------------------------------------------
class WavePlannerError(Exception):
    """Parse, validation, or wave-planning error."""


@dataclass
class Task:
    """Task parsed from plan.md."""

    slug: str
    files_touched: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    type: str = "AFK"  # T2.6: HITL | AFK. Default AFK; HITL activates isolated wave cap=1.


# ----------------------------------------------------------------------------
# Parser plan.md
# ----------------------------------------------------------------------------

def _split_into_task_blocks(text: str) -> list[tuple[str, str]]:
    """Splits plan.md into (slug, block_content) pairs preserving order."""
    matches = list(TASK_HEADER_RE.finditer(text))
    if not matches:
        return []

    blocks: list[tuple[str, str]] = []
    for idx, match in enumerate(matches):
        raw_slug = match.group(1)
        if not KEBAB_RE.match(raw_slug):
            raise WavePlannerError(
                f"invalid slug {raw_slug!r}: must be kebab-case (lowercase + digits + hyphens)"
            )
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        blocks.append((raw_slug, text[start:end]))
    return blocks


def _extract_section(block: str, section_title: str) -> list[str]:
    """Extracts bullets from a `### <title>` section up to the next `### ` or `## `."""
    pattern = re.compile(
        rf"^###\s+{re.escape(section_title)}\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    match = pattern.search(block)
    if not match:
        return []
    tail = block[match.end():]
    # Stop at the next section
    next_section = re.search(r"^(##\s|###\s)", tail, re.MULTILINE)
    body = tail[: next_section.start()] if next_section else tail

    items: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("- "):
            value = line[2:].strip()
            if value:
                # Strip parenthetical notes (e.g. "config-module (needs api_key)" → "config-module")
                value = re.sub(r'\s*\([^)]*\)', '', value).strip()
            if value and value.lower() not in ("none", "nenhum"):
                items.append(value)
    return items


def _extract_type_field(block: str) -> str:
    """Extracts the `**Type:**` field from the task block. Defaults to AFK if absent.

    Expected format: `**Type:** HITL` or `**Type:** AFK`.
    Canonical doc: references/task-types-hitl-afk.md.
    """
    match = re.search(r"\*\*Type:\*\*\s*(HITL|AFK)\b", block, re.IGNORECASE)
    if not match:
        return "AFK"
    return match.group(1).upper()


def _detect_heading_drift(text: str) -> None:
    """Pre-flight: aborts if plan.md has task headers at h4-h6 or
    4-block subsections at h5-h6. Canonical schema requires h2/h3."""
    task_drift = TASK_HEADING_DRIFT_RE.findall(text)
    sub_drift = SUBSECTION_DRIFT_RE.findall(text)
    if not task_drift and not sub_drift:
        return
    parts: list[str] = []
    if task_drift:
        parts.append(
            f"{len(task_drift)} task header(s) at level >h2 "
            f"(expected '## Task <slug>: <title>')"
        )
    if sub_drift:
        parts.append(
            f"{len(sub_drift)} subsection(s) at level >h3 "
            f"(expected '### WHAT/HOW/OUT OF SCOPE/VALIDATION/Files touched/Depends on')"
        )
    raise WavePlannerError(
        "plan.md heading drift: " + "; ".join(parts) + ". "
        "Canonical schema in references/4-block-contract-template.md. "
        "Mechanical fix: ^#### Task -> ## Task; ^##### <subsec> -> ### <subsec>."
    )


def parse_plan(path: Path) -> list[Task]:
    """Reads plan.md and returns an ordered list of Tasks. Aborts on duplicate slug."""
    if not path.exists():
        raise WavePlannerError(f"plan file not found: {path}")
    text = path.read_text(encoding="utf-8")
    _detect_heading_drift(text)
    blocks = _split_into_task_blocks(text)
    if not blocks:
        raise WavePlannerError(f"no tasks found in plan: {path}")

    seen: set[str] = set()
    tasks: list[Task] = []
    for slug, block in blocks:
        if slug in seen:
            raise WavePlannerError(f"duplicate slug: {slug}")
        seen.add(slug)
        tasks.append(Task(
            slug=slug,
            files_touched=_extract_section(block, "Files touched"),
            depends_on=_extract_section(block, "Depends on"),
            type=_extract_type_field(block),
        ))
    return tasks


# ----------------------------------------------------------------------------
# Cap resolution (tier x profile)
# ----------------------------------------------------------------------------

def resolve_cap(*, tier: str, profile: str) -> int:
    """Returns effective cap: min(tier_cap, profile_override)."""
    if tier not in VALID_TIERS:
        raise WavePlannerError(f"invalid tier: {tier!r}")
    if profile not in VALID_PROFILES:
        raise WavePlannerError(f"invalid profile: {profile!r}")
    tier_cap = TIER_CAP[tier]
    profile_cap = PROFILE_CAP_OVERRIDE.get(profile)
    if profile_cap is None:
        return tier_cap
    return min(tier_cap, profile_cap)


# ----------------------------------------------------------------------------
# DAG: build, cycle detect, topo sort, subdivide
# ----------------------------------------------------------------------------

def build_graph(tasks: list[Task]) -> set[tuple[str, str]]:
    """Builds directed edges:
    - explicit dep: t1 in t2.depends_on => edge (t1, t2).
    - file conflict: files_touched(t1) & files_touched(t2) != {} and t1 before
      t2 in plan.md => edge (t1, t2).
    """
    by_slug = {t.slug: t for t in tasks}
    edges: set[tuple[str, str]] = set()

    # Explicit deps
    for t in tasks:
        for dep in t.depends_on:
            if dep not in by_slug:
                raise WavePlannerError(f"unknown dependency: {dep} (in task {t.slug})")
            edges.add((dep, t.slug))

    # File conflicts (plan.md order serializes)
    for i, t1 in enumerate(tasks):
        files1 = set(t1.files_touched)
        if not files1:
            continue
        for t2 in tasks[i + 1:]:
            if files1 & set(t2.files_touched):
                edges.add((t1.slug, t2.slug))

    return edges


def detect_cycle(nodes: list[str], edges: Iterable[tuple[str, str]]) -> None:
    """DFS 3-color. Raises WavePlannerError if a cycle is detected."""
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in edges:
        if u in adj:
            adj[u].append(v)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in nodes}
    stack_path: list[str] = []

    def visit(node: str) -> None:
        color[node] = GRAY
        stack_path.append(node)
        for nxt in adj.get(node, []):
            if color.get(nxt, WHITE) == GRAY:
                cycle_start = stack_path.index(nxt)
                path = " -> ".join(stack_path[cycle_start:] + [nxt])
                raise WavePlannerError(f"cycle detected: {path}")
            if color.get(nxt, WHITE) == WHITE:
                visit(nxt)
        color[node] = BLACK
        stack_path.pop()

    for n in nodes:
        if color[n] == WHITE:
            visit(n)


def topological_waves(tasks: list[Task], *, edges: set[tuple[str, str]]) -> list[list[str]]:
    """Kahn level-by-level. Each wave = all nodes with no remaining in-edges."""
    nodes = [t.slug for t in tasks]
    detect_cycle(nodes, edges)

    in_degree: dict[str, int] = {n: 0 for n in nodes}
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in edges:
        in_degree[v] = in_degree.get(v, 0) + 1
        adj[u].append(v)

    # Preserves plan.md order when populating each wave
    order = {slug: idx for idx, slug in enumerate(nodes)}
    waves: list[list[str]] = []
    remaining = set(nodes)

    while remaining:
        ready = sorted(
            [n for n in remaining if in_degree[n] == 0],
            key=lambda s: order[s],
        )
        if not ready:
            # Safeguard: detect_cycle should have caught this, but guard anyway.
            raise WavePlannerError("cycle detected (no ready nodes remaining)")
        waves.append(ready)
        for n in ready:
            remaining.remove(n)
            for nxt in adj[n]:
                in_degree[nxt] -= 1

    return waves


def subdivide_waves(
    waves: list[list[str]],
    *,
    cap: int,
    task_types: dict[str, str] | None = None,
) -> list[list[list[str]]]:
    """Breaks each wave into sub-waves of size <= cap.

    T2.6: tasks with `type=HITL` go into isolated sub-waves (cap=1) — lead
    session does NOT spawn a subagent, generates AGENT-BRIEF and awaits human. AFK
    tasks grouped normally up to `cap`.

    Args:
        waves: list[list[str]] of raw waves (Kahn output).
        cap: effective cap (tier x profile).
        task_types: dict slug -> "HITL"|"AFK". If None or absent, defaults to AFK.
    """
    if cap <= 0:
        raise WavePlannerError(f"invalid cap: {cap}")
    types = task_types or {}
    result: list[list[list[str]]] = []
    for wave in waves:
        if not wave:
            result.append([[]])
            continue
        # Separate HITL vs AFK preserving plan.md order
        hitl_subs: list[list[str]] = [[s] for s in wave if types.get(s, "AFK") == "HITL"]
        afk_slugs: list[str] = [s for s in wave if types.get(s, "AFK") != "HITL"]
        afk_subs: list[list[str]] = [
            afk_slugs[i:i + cap] for i in range(0, len(afk_slugs), cap)
        ]
        # AFK first, HITL after (human resolves in order after AFK done)
        sub_waves = afk_subs + hitl_subs or [[]]
        result.append(sub_waves)
    return result


# ----------------------------------------------------------------------------
# Ambiguidades (mesmo dir, files diferentes)
# ----------------------------------------------------------------------------

def detect_ambiguities(tasks: list[Task]) -> list[str]:
    """Task pairs that touch the same directory without an exact intersection.

    Flagged for LLM review (not serialized, just recorded).
    """
    notes: list[str] = []
    seen_pairs: set[tuple[str, str]] = set()

    def dirs_of(task: Task) -> set[str]:
        return {str(Path(f).parent.as_posix()) for f in task.files_touched if f}

    for i, t1 in enumerate(tasks):
        files1 = set(t1.files_touched)
        dirs1 = dirs_of(t1)
        for t2 in tasks[i + 1:]:
            files2 = set(t2.files_touched)
            if files1 & files2:
                continue  # already becomes an edge (file conflict)
            common_dirs = dirs1 & dirs_of(t2)
            if not common_dirs:
                continue
            ordered = sorted([t1.slug, t2.slug])
            pair_key: tuple[str, str] = (ordered[0], ordered[1])
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            for d in sorted(common_dirs):
                notes.append(
                    f"Task {t1.slug} and {t2.slug} touch same dir {d}; "
                    "LLM review should confirm separation."
                )
    return notes


# ----------------------------------------------------------------------------
# Pipeline integrado
# ----------------------------------------------------------------------------

def plan_waves(*, plan_path: Path, tier: str, profile: str) -> dict:
    """Full pipeline: parse -> graph -> waves -> subdivide -> ambiguities.

    Returns dict with:
      - tasks: list of Task
      - cap_subagents_per_wave
      - waves: list[list[list[str]]]   waves -> sub_waves -> slugs
      - total_tasks, total_waves, total_sub_waves
      - ambiguities: list[str]
      - tier, profile
    """
    cap = resolve_cap(tier=tier, profile=profile)
    tasks = parse_plan(plan_path)
    edges = build_graph(tasks)
    raw_waves = topological_waves(tasks, edges=edges)
    task_types = {t.slug: t.type for t in tasks}
    sub = subdivide_waves(raw_waves, cap=cap, task_types=task_types)
    ambiguities = detect_ambiguities(tasks)

    total_sub_waves = sum(len(w) for w in sub)

    return {
        "tasks": tasks,
        "tier": tier,
        "profile": profile,
        "cap_subagents_per_wave": cap,
        "waves": sub,
        "total_tasks": len(tasks),
        "total_waves": len(sub),
        "total_sub_waves": total_sub_waves,
        "ambiguities": ambiguities,
    }


# ----------------------------------------------------------------------------
# Renderers
# ----------------------------------------------------------------------------

_LETTERS = "abcdefghijklmnopqrstuvwxyz"


def _sub_label(idx: int) -> str:
    if idx < len(_LETTERS):
        return _LETTERS[idx]
    # Robust fallback for sub-waves > 26 (rare)
    return f"x{idx}"


def render_wave_plan(result: dict, *, plan_source: str, workspace: str) -> str:
    """Renders wave-plan.md (YAML frontmatter + tables)."""
    tasks_by_slug = {t.slug: t for t in result["tasks"]}
    frontmatter = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "plan_source": plan_source,
        "tier": result["tier"],
        "profile": result["profile"],
        "cap_subagents_per_wave": result["cap_subagents_per_wave"],
        "total_tasks": result["total_tasks"],
        "total_waves": result["total_waves"],
        "total_sub_waves": result["total_sub_waves"],
        "llm_review": "PENDING",
        "llm_review_iterations": 0,
    }

    lines: list[str] = []
    lines.append("---")
    lines.append(yaml.safe_dump(frontmatter, sort_keys=False).rstrip())
    lines.append("---")
    lines.append("")
    lines.append("# Wave Plan")
    lines.append("")

    for w_idx, sub_waves in enumerate(result["waves"], start=1):
        for sw_idx, slugs in enumerate(sub_waves):
            label = _sub_label(sw_idx)
            count = len(slugs)
            cap_note = ""
            if len(sub_waves) > 1:
                cap_note = " (cap reached)" if sw_idx > 0 else ""
            lines.append(
                f"## Wave {w_idx} (sub-wave {w_idx}.{label}) - {count} parallel tasks{cap_note}"
            )
            if count == 1:
                lines.append("")
                lines.append(
                    "> **skip_cross_task_audit: true** — wave 1-task pula audit cross-task no step 8b (Forensic+ ainda roda em 8a). Doc: references/wave-planner-algorithm.md §10."
                )
            lines.append("")
            lines.append("| Task slug | Files touched | Depends on | E2E required? | Branch |")
            lines.append("|---|---|---|---|---|")
            for slug in slugs:
                t = tasks_by_slug[slug]
                files_str = ", ".join(t.files_touched) if t.files_touched else "-"
                deps_str = ", ".join(t.depends_on) if t.depends_on else "-"
                branch = f"wave-{workspace}-{w_idx}/{slug}"
                e2e_required = _task_requires_e2e(t.files_touched, result["profile"])
                e2e_cell = "yes (auto)" if e2e_required else "no"
                lines.append(f"| {slug} | {files_str} | {deps_str} | {e2e_cell} | {branch} |")
            lines.append("")
            # v3.10.0 — annotation when ≥1 task flagged
            flagged = [
                slug for slug in slugs
                if _task_requires_e2e(tasks_by_slug[slug].files_touched, result["profile"])
            ]
            if flagged:
                lines.append(
                    f"> **E2E coverage required** ({len(flagged)} task[s]): "
                    f"{', '.join(flagged)}. Lead must add "
                    "`### Requires E2E update\\n- true` to plan.md task. "
                    "Forensic+ Check 8 enforces (HARD in tier dev/prod)."
                )
                lines.append("")

    lines.append("## Audit")
    lines.append("")
    file_conflicts = _file_conflict_pairs(result["tasks"])
    if file_conflicts:
        lines.append("- Tasks with file conflicts serialized:")
        for a, b in file_conflicts:
            lines.append(f"  - ({a}, {b})")
    else:
        lines.append("- No file conflicts serialized.")
    if result["ambiguities"]:
        lines.append(
            f"- {len(result['ambiguities'])} ambiguity(ies) recorded in "
            "`ambiguities-resolved.md`."
        )
    else:
        lines.append("- No ambiguities recorded.")
    lines.append("")

    return "\n".join(lines)


def _file_conflict_pairs(tasks: list[Task]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for i, t1 in enumerate(tasks):
        f1 = set(t1.files_touched)
        if not f1:
            continue
        for t2 in tasks[i + 1:]:
            if f1 & set(t2.files_touched):
                pairs.append((t1.slug, t2.slug))
    return pairs


def render_ambiguities(ambiguities: list[str]) -> str:
    if not ambiguities:
        return "# Ambiguities Resolved\n\nNo ambiguities detected in the deterministic phase.\n"
    lines = ["# Ambiguities Resolved", ""]
    for note in ambiguities:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic Wave Planner (no LLM).")
    parser.add_argument("--plan", required=True, type=Path, help="path to plan.md")
    parser.add_argument("--tier", required=True, choices=sorted(VALID_TIERS))
    parser.add_argument("--profile", required=True, choices=sorted(VALID_PROFILES))
    parser.add_argument("--workspace", required=True, help="workspace ID (e.g. 042-feat-auth)")
    parser.add_argument("--output", required=True, type=Path, help="path to wave-plan.md")
    parser.add_argument(
        "--ambiguities-output",
        type=Path,
        default=None,
        help="path to ambiguities-resolved.md (default: next to --output)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        result = plan_waves(plan_path=args.plan, tier=args.tier, profile=args.profile)
        rendered = render_wave_plan(
            result,
            plan_source=str(args.plan).replace("\\", "/"),
            workspace=args.workspace,
        )
    except WavePlannerError as exc:
        print(f"wave-planner error: {exc}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")

    amb_path = args.ambiguities_output
    if amb_path is None:
        amb_path = args.output.parent / "ambiguities-resolved.md"
    amb_path.parent.mkdir(parents=True, exist_ok=True)
    amb_path.write_text(render_ambiguities(result["ambiguities"]), encoding="utf-8")

    print(
        f"total_tasks={result['total_tasks']} "
        f"total_waves={result['total_waves']} "
        f"total_sub_waves={result['total_sub_waves']} "
        f"ambiguities={len(result['ambiguities'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
