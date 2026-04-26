#!/usr/bin/env python3
"""Wave Planner deterministico (Sessao 2 - fase sem LLM).

Le um plan.md, constroi DAG de tasks (deps explicitas + file conflicts),
detecta ciclos, faz topological sort em waves, subdivide em sub-waves
quando excedem o cap por tier/profile, marca ambiguidades e renderiza
wave-plan.md (Markdown com YAML frontmatter) + ambiguities-resolved.md.

CLI:
  python scripts/wave-planner-script.py
      --plan stages/02_design/output/plan.md
      --tier development
      --profile app_web_backend
      --workspace 042-feat-auth
      --output stages/03_wave_planner/output/wave-plan.md
      [--ambiguities-output stages/03_wave_planner/output/ambiguities-resolved.md]

Stdout: total_tasks=N total_waves=M total_sub_waves=K ambiguities=A
Exit 0 = sucesso. Exit 1 = erro (ciclo, schema invalido, etc).

Algoritmos:
  - Kahn (topological sort por niveis) -> evita stack overflow.
  - DFS (3 cores) -> deteccao de ciclo determinista.
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
# Constantes (sincronas com profile-merge)
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

SLUG_RE = re.compile(r"^## Task ([a-z0-9][a-z0-9-]*):", re.MULTILINE)
TASK_HEADER_RE = re.compile(r"^## Task (\S+):", re.MULTILINE)
KEBAB_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


# ----------------------------------------------------------------------------
# Errors + dataclass
# ----------------------------------------------------------------------------
class WavePlannerError(Exception):
    """Erro de parse, validacao ou planejamento de waves."""


@dataclass
class Task:
    """Task parseada do plan.md."""

    slug: str
    files_touched: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


# ----------------------------------------------------------------------------
# Parser plan.md
# ----------------------------------------------------------------------------

def _split_into_task_blocks(text: str) -> list[tuple[str, str]]:
    """Quebra o plan.md em (slug, conteudo_do_bloco) preservando ordem."""
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
    """Extrai bullets de uma secao `### <title>` ate proxima `### ` ou `## `."""
    pattern = re.compile(
        rf"^###\s+{re.escape(section_title)}\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    match = pattern.search(block)
    if not match:
        return []
    tail = block[match.end():]
    # Para na proxima secao
    next_section = re.search(r"^(##\s|###\s)", tail, re.MULTILINE)
    body = tail[: next_section.start()] if next_section else tail

    items: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("- "):
            value = line[2:].strip()
            if value and value.lower() != "nenhum":
                items.append(value)
    return items


def parse_plan(path: Path) -> list[Task]:
    """Le plan.md e devolve lista ordenada de Task. Aborta em slug duplicado."""
    if not path.exists():
        raise WavePlannerError(f"plan file not found: {path}")
    text = path.read_text(encoding="utf-8")
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
        ))
    return tasks


# ----------------------------------------------------------------------------
# Cap resolution (tier x profile)
# ----------------------------------------------------------------------------

def resolve_cap(*, tier: str, profile: str) -> int:
    """Retorna cap efetivo: min(tier_cap, profile_override)."""
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
    """Constroi arestas dirigidas:
    - dep explicita: t1 in t2.depends_on => aresta (t1, t2).
    - file conflict: files_touched(t1) & files_touched(t2) != {} e t1 antes
      de t2 no plan.md => aresta (t1, t2).
    """
    by_slug = {t.slug: t for t in tasks}
    edges: set[tuple[str, str]] = set()

    # Dep explicitas
    for t in tasks:
        for dep in t.depends_on:
            if dep not in by_slug:
                raise WavePlannerError(f"unknown dependency: {dep} (in task {t.slug})")
            edges.add((dep, t.slug))

    # File conflicts (ordem do plan.md serializa)
    for i, t1 in enumerate(tasks):
        files1 = set(t1.files_touched)
        if not files1:
            continue
        for t2 in tasks[i + 1:]:
            if files1 & set(t2.files_touched):
                edges.add((t1.slug, t2.slug))

    return edges


def detect_cycle(nodes: list[str], edges: Iterable[tuple[str, str]]) -> None:
    """DFS 3-color. Levanta WavePlannerError se detectar ciclo."""
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
    """Kahn por niveis. Cada wave = todos os nos sem in-edges restantes."""
    nodes = [t.slug for t in tasks]
    detect_cycle(nodes, edges)

    in_degree: dict[str, int] = {n: 0 for n in nodes}
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for u, v in edges:
        in_degree[v] = in_degree.get(v, 0) + 1
        adj[u].append(v)

    # Preserva ordem do plan.md ao popular cada wave
    order = {slug: idx for idx, slug in enumerate(nodes)}
    waves: list[list[str]] = []
    remaining = set(nodes)

    while remaining:
        ready = sorted(
            [n for n in remaining if in_degree[n] == 0],
            key=lambda s: order[s],
        )
        if not ready:
            # Salvaguarda: detect_cycle ja deveria ter pego, mas guard.
            raise WavePlannerError("cycle detected (no ready nodes remaining)")
        waves.append(ready)
        for n in ready:
            remaining.remove(n)
            for nxt in adj[n]:
                in_degree[nxt] -= 1

    return waves


def subdivide_waves(waves: list[list[str]], *, cap: int) -> list[list[list[str]]]:
    """Quebra cada wave em sub-waves de tamanho <= cap."""
    if cap <= 0:
        raise WavePlannerError(f"invalid cap: {cap}")
    result: list[list[list[str]]] = []
    for wave in waves:
        sub_waves = [wave[i:i + cap] for i in range(0, len(wave), cap)] or [[]]
        # Se wave vazia (nao deveria acontecer), preserva como []
        if wave:
            result.append(sub_waves)
        else:
            result.append([[]])
    return result


# ----------------------------------------------------------------------------
# Ambiguidades (mesmo dir, files diferentes)
# ----------------------------------------------------------------------------

def detect_ambiguities(tasks: list[Task]) -> list[str]:
    """Pares de tasks que tocam mesmo diretorio sem intersecao exata.

    Marca para revisao do LLM (nao serializa, apenas registra).
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
                continue  # ja vira aresta (file conflict)
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
                    f"Task {t1.slug} e {t2.slug} tocam mesmo dir {d}; "
                    "LLM review deve confirmar separacao."
                )
    return notes


# ----------------------------------------------------------------------------
# Pipeline integrado
# ----------------------------------------------------------------------------

def plan_waves(*, plan_path: Path, tier: str, profile: str) -> dict:
    """Pipeline completo: parse -> graph -> waves -> subdivide -> ambiguidades.

    Retorna dict com:
      - tasks: lista de Task
      - cap_teammates_per_wave
      - waves: list[list[list[str]]]   waves -> sub_waves -> slugs
      - total_tasks, total_waves, total_sub_waves
      - ambiguities: list[str]
      - tier, profile
    """
    cap = resolve_cap(tier=tier, profile=profile)
    tasks = parse_plan(plan_path)
    edges = build_graph(tasks)
    raw_waves = topological_waves(tasks, edges=edges)
    sub = subdivide_waves(raw_waves, cap=cap)
    ambiguities = detect_ambiguities(tasks)

    total_sub_waves = sum(len(w) for w in sub)

    return {
        "tasks": tasks,
        "tier": tier,
        "profile": profile,
        "cap_teammates_per_wave": cap,
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
    # Fallback robusto para sub-waves > 26 (raro)
    return f"x{idx}"


def render_wave_plan(result: dict, *, plan_source: str, workspace: str) -> str:
    """Renderiza wave-plan.md (frontmatter YAML + tabelas)."""
    tasks_by_slug = {t.slug: t for t in result["tasks"]}
    frontmatter = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "plan_source": plan_source,
        "tier": result["tier"],
        "profile": result["profile"],
        "cap_teammates_per_wave": result["cap_teammates_per_wave"],
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
                cap_note = " (cap atingido)" if sw_idx > 0 else ""
            lines.append(
                f"## Wave {w_idx} (sub-wave {w_idx}.{label}) - {count} tasks paralelas{cap_note}"
            )
            lines.append("")
            lines.append("| Task slug | Files touched | Depends on | Branch |")
            lines.append("|---|---|---|---|")
            for slug in slugs:
                t = tasks_by_slug[slug]
                files_str = ", ".join(t.files_touched) if t.files_touched else "-"
                deps_str = ", ".join(t.depends_on) if t.depends_on else "-"
                branch = f"wave-{workspace}-{w_idx}/{slug}"
                lines.append(f"| {slug} | {files_str} | {deps_str} | {branch} |")
            lines.append("")

    lines.append("## Audit")
    lines.append("")
    file_conflicts = _file_conflict_pairs(result["tasks"])
    if file_conflicts:
        lines.append("- Tasks com files conflict serializadas:")
        for a, b in file_conflicts:
            lines.append(f"  - ({a}, {b})")
    else:
        lines.append("- Nenhum file conflict serializado.")
    if result["ambiguities"]:
        lines.append(
            f"- {len(result['ambiguities'])} ambiguidade(s) registrada(s) em "
            "`ambiguities-resolved.md`."
        )
    else:
        lines.append("- Nenhuma ambiguidade registrada.")
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
        return "# Ambiguities Resolved\n\nNenhuma ambiguidade detectada na fase deterministica.\n"
    lines = ["# Ambiguities Resolved", ""]
    for note in ambiguities:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wave Planner deterministico (sem LLM).")
    parser.add_argument("--plan", required=True, type=Path, help="path para plan.md")
    parser.add_argument("--tier", required=True, choices=sorted(VALID_TIERS))
    parser.add_argument("--profile", required=True, choices=sorted(VALID_PROFILES))
    parser.add_argument("--workspace", required=True, help="ID do workspace (ex: 042-feat-auth)")
    parser.add_argument("--output", required=True, type=Path, help="path para wave-plan.md")
    parser.add_argument(
        "--ambiguities-output",
        type=Path,
        default=None,
        help="path para ambiguities-resolved.md (default: ao lado de --output)",
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
