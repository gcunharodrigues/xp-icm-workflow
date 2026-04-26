#!/usr/bin/env python3
"""Recovery Wizard L1 (R2.7).

Detecta inconsistencias no estado L1 (`<workspace>/CONTEXT.md`) e propoe
um plano de recovery. Acoes podem ser executadas em modo interativo
(escolha humana) ou nao-interativo (`--apply A|B|C`).

Inconsistencias detectadas (codes):
  - HASH_MISMATCH       — profile_effective_hash divergiu do recomputado
  - MISSING_OUTPUT      — history declara output ausente no FS
  - STALE_IN_PROGRESS   — IN_PROGRESS sem commit nas ultimas 24h
  - MISSING_COMMIT      — last_transition.commit_sha nao existe em git
  - MISSING_WORKTREES   — waves.current=N mas worktree ausente / vazia
  - BRANCH_MISSING      — branch workspace/NNN-slug nao existe (R4.5)

Schema canonico em references/state-machine-schema.md.

CLI:
  python scripts/recovery-wizard.py --workspace <path> --dry-run
  python scripts/recovery-wizard.py --workspace <path>           # interactive
  python scripts/recovery-wizard.py --workspace <path> --apply A
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml


# Codes ----------------------------------------------------------------------

CODE_HASH_MISMATCH = "HASH_MISMATCH"
CODE_MISSING_COMMIT = "MISSING_COMMIT"
CODE_MISSING_OUTPUT = "MISSING_OUTPUT"
CODE_STALE_IN_PROGRESS = "STALE_IN_PROGRESS"
CODE_MISSING_WORKTREES = "MISSING_WORKTREES"
CODE_BRANCH_MISSING = "BRANCH_MISSING"

# Ordem canonica determinista (R2.7 batch order).
CANONICAL_ORDER: tuple[str, ...] = (
    CODE_HASH_MISMATCH,
    CODE_MISSING_COMMIT,
    CODE_MISSING_OUTPUT,
    CODE_STALE_IN_PROGRESS,
    CODE_MISSING_WORKTREES,
    CODE_BRANCH_MISSING,
)

STALE_THRESHOLD = timedelta(hours=24)

# Regex pra encontrar referencias `stages/NN_*/output/X.md` em strings.
_OUTPUT_REF_RE = re.compile(
    r"(stages/\d{2}[A-Za-z0-9_\-]*/output/[A-Za-z0-9_\-./]+\.md)"
)

_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(?P<body>.*?)\n---\s*(?:\n(?P<rest>.*))?$",
    re.DOTALL,
)


# Exceptions e dataclasses ---------------------------------------------------

class RecoveryWizardError(Exception):
    """Erro generico do Recovery Wizard."""


@dataclass(frozen=True)
class Inconsistency:
    """Inconsistencia L1 detectada.

    Attributes:
        code: codigo canonico (ver CANONICAL_ORDER).
        message: mensagem humana especifica.
        proposed_action: acao A (preserve) recomendada.
        severity: "critical" | "warning".
        context: campos auxiliares (paths, shas, etc.).
    """

    code: str
    message: str
    proposed_action: str
    severity: str
    context: dict = field(default_factory=dict)


# Parsing helpers ------------------------------------------------------------

def _parse_l1(workspace_path: Path) -> tuple[dict[str, Any], str, str]:
    """Le CONTEXT.md, retorna (state_dict, frontmatter_str, body_str).

    body_str inclui o resto do markdown apos o segundo '---'.
    """
    context_md = workspace_path / "CONTEXT.md"
    if not context_md.is_file():
        raise RecoveryWizardError(
            f"CONTEXT.md nao encontrado em workspace: {context_md}"
        )
    content = context_md.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(content)
    if match is None:
        raise RecoveryWizardError(
            "CONTEXT.md sem YAML frontmatter delimitado por '---'"
        )
    fm_text = match.group("body")
    rest = match.group("rest") or ""
    try:
        state = yaml.safe_load(fm_text)
    except yaml.YAMLError as exc:
        raise RecoveryWizardError(f"YAML frontmatter invalido: {exc}") from exc
    if not isinstance(state, dict):
        raise RecoveryWizardError(
            "Frontmatter deve ser mapping no topo"
        )
    return state, fm_text, rest


def _serialize_l1(state: dict[str, Any], rest: str) -> str:
    """Re-serializa frontmatter + corpo. yaml.safe_dump preserva ordem."""
    fm_text = yaml.safe_dump(
        state, sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    if rest and not rest.startswith("\n"):
        rest = "\n" + rest
    elif not rest:
        rest = "\n"
    return f"---\n{fm_text}---{rest}"


def _write_l1(workspace_path: Path, state: dict[str, Any], rest: str) -> None:
    serialized = _serialize_l1(state, rest)
    (workspace_path / "CONTEXT.md").write_text(serialized, encoding="utf-8")


def _compute_profile_hash(workspace_path: Path) -> str | None:
    """Recomputa sha256 do _config/profile-effective.yaml.

    Retorna None se arquivo ausente.
    """
    profile_yaml = workspace_path / "_config" / "profile-effective.yaml"
    if not profile_yaml.is_file():
        return None
    raw = profile_yaml.read_bytes()
    return hashlib.sha256(raw).hexdigest()


def _parse_iso(stamp: str) -> datetime:
    """Parse ISO 8601 string. Tolera sufixo 'Z' (=UTC)."""
    if stamp.endswith("Z"):
        stamp = stamp[:-1] + "+00:00"
    parsed = datetime.fromisoformat(stamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _extract_output_refs(history: list[dict[str, Any]]) -> list[str]:
    """Coleta paths `stages/.../output/X.md` mencionados em items de history.

    Suporta:
      - campo explicito `outputs: [list de paths]`
      - regex em qualquer string do item (note, event, etc).

    Retorna lista deduplicada preservando ordem.
    """
    found: list[str] = []
    seen: set[str] = set()

    def _add(path: str) -> None:
        if path not in seen:
            seen.add(path)
            found.append(path)

    for item in history:
        if not isinstance(item, dict):
            continue
        explicit = item.get("outputs")
        if isinstance(explicit, list):
            for p in explicit:
                if isinstance(p, str):
                    _add(p)
        # Regex em todos os string-values
        for value in item.values():
            if isinstance(value, str):
                for match in _OUTPUT_REF_RE.findall(value):
                    _add(match)
    return found


# Git helpers ----------------------------------------------------------------

def _run_git(
    args: list[str], *, cwd: Path | None = None
) -> subprocess.CompletedProcess:
    """Wrapper de subprocess.run pro git, com captura silenciosa de stdout/err."""
    cmd = ["git"] + args
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )


def _commit_exists(sha: str, *, cwd: Path | None = None) -> bool:
    if not sha:
        return False
    result = _run_git(["cat-file", "-e", sha], cwd=cwd)
    return result.returncode == 0


def _branch_exists(branch: str, *, cwd: Path | None = None) -> bool:
    result = _run_git(["branch", "--list", branch], cwd=cwd)
    return bool(result.stdout.strip())


def _last_workspace_commit_at(
    workspace_id: str, *, cwd: Path | None = None
) -> datetime | None:
    """Retorna ISO 8601 do commit mais recente que tocou workspaces/<id>/."""
    result = _run_git(
        [
            "log",
            "-1",
            "--pretty=format:%cI",
            "--",
            f"workspaces/{workspace_id}",
        ],
        cwd=cwd,
    )
    stdout = result.stdout.strip()
    if not stdout:
        return None
    try:
        return _parse_iso(stdout)
    except ValueError:
        return None


# Detect ---------------------------------------------------------------------

def detect_inconsistencies(
    workspace_path: Path,
    *,
    project_root: Path | None = None,
    now: datetime | None = None,
) -> list[Inconsistency]:
    """Roda os 6 checks. Retorna inconsistencias em ordem canonica.

    `project_root` defaults para `state["project_root"]` se ausente.
    `now` defaults para `datetime.now(timezone.utc)`.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    state, _, _ = _parse_l1(workspace_path)

    if project_root is None:
        proj_root_str = state.get("project_root")
        project_root = Path(proj_root_str) if proj_root_str else None

    found: list[Inconsistency] = []

    # 1) HASH_MISMATCH
    declared = state.get("profile_effective_hash")
    actual = _compute_profile_hash(workspace_path)
    if actual is not None and declared is not None and actual != declared:
        found.append(
            Inconsistency(
                code=CODE_HASH_MISMATCH,
                message=(
                    f"profile_effective_hash declarado ({declared[:12]}...) "
                    f"divergiu do recomputado ({actual[:12]}...). "
                    "_config/profile-effective.yaml mudou sem update de L1."
                ),
                proposed_action=(
                    "recompute hash + update L1 (preserva profile)"
                ),
                severity="warning",
                context={"declared": declared, "actual": actual},
            )
        )

    # 2) MISSING_COMMIT (chega antes de OUTPUT na ordem canonica)
    last_transition = state.get("last_transition") or {}
    sha = last_transition.get("commit_sha", "")
    cwd_for_git = project_root if project_root else None
    if sha and not _commit_exists(sha, cwd=cwd_for_git):
        found.append(
            Inconsistency(
                code=CODE_MISSING_COMMIT,
                message=(
                    f"last_transition.commit_sha={sha} nao existe em git "
                    "history (rebased away?)."
                ),
                proposed_action=(
                    "rollback last_transition pro penultimo evento valido em "
                    "history"
                ),
                severity="critical",
                context={"commit_sha": sha},
            )
        )

    # 3) MISSING_OUTPUT
    history = state.get("history") or []
    refs = _extract_output_refs(history) if isinstance(history, list) else []
    missing_outputs: list[str] = []
    for ref in refs:
        if not (workspace_path / ref).exists():
            missing_outputs.append(ref)
    if missing_outputs:
        listed = ", ".join(missing_outputs)
        found.append(
            Inconsistency(
                code=CODE_MISSING_OUTPUT,
                message=(
                    "outputs declarados em history nao existem no FS: "
                    f"{listed}"
                ),
                proposed_action=(
                    "remover historia referente + warning (ou rollback "
                    "ao last_transition antes do output)"
                ),
                severity="warning",
                context={"missing": missing_outputs},
            )
        )

    # 4) STALE_IN_PROGRESS
    if state.get("status") == "IN_PROGRESS":
        last_commit = _last_workspace_commit_at(
            state.get("workspace", ""), cwd=cwd_for_git
        )
        # Fallback: usa last_action_at se git log nao retornou nada.
        last_seen: datetime | None = last_commit
        if last_seen is None:
            laa = state.get("last_action_at")
            if isinstance(laa, str):
                try:
                    last_seen = _parse_iso(laa)
                except ValueError:
                    last_seen = None
        if last_seen is not None and (now - last_seen) > STALE_THRESHOLD:
            age = now - last_seen
            found.append(
                Inconsistency(
                    code=CODE_STALE_IN_PROGRESS,
                    message=(
                        f"status=IN_PROGRESS sem commit em workspaces/* "
                        f"ha {age}. Provavel sessao orfa."
                    ),
                    proposed_action=(
                        "appender 'recovery_applied' em history + status "
                        "COMPLETED_AWAITING_HUMAN"
                    ),
                    severity="warning",
                    context={"age_hours": int(age.total_seconds() // 3600)},
                )
            )

    # 5) MISSING_WORKTREES
    waves = state.get("waves")
    if isinstance(waves, dict) and project_root is not None:
        current = waves.get("current")
        ws_id = state.get("workspace", "")
        if isinstance(current, int) and ws_id:
            wt_dir = (
                project_root
                / ".worktrees"
                / f"workspace-{ws_id}"
                / f"wave-{current}"
            )
            wt_missing = (not wt_dir.exists()) or (
                wt_dir.is_dir() and not any(wt_dir.iterdir())
            )
            if wt_missing:
                found.append(
                    Inconsistency(
                        code=CODE_MISSING_WORKTREES,
                        message=(
                            f"waves.current={current} declarado, mas worktree "
                            f"{wt_dir} ausente ou vazia."
                        ),
                        proposed_action=(
                            "recriar worktree placeholder + warning "
                            "(ou rollback waves.current pro ultimo completed)"
                        ),
                        severity="critical",
                        context={
                            "expected_path": str(wt_dir),
                            "wave": current,
                        },
                    )
                )

    # 6) BRANCH_MISSING (R4.5)
    branch = state.get("workspace_branch")
    if isinstance(branch, str) and branch:
        if not _branch_exists(branch, cwd=cwd_for_git):
            found.append(
                Inconsistency(
                    code=CODE_BRANCH_MISSING,
                    message=(
                        f"branch '{branch}' ausente. Tentar restore via "
                        "reflog: git reflog | grep "
                        f"'{branch}' (R4.5)."
                    ),
                    proposed_action=(
                        "tentar restore via reflog ou criar branch novo "
                        "do last_transition.commit_sha"
                    ),
                    severity="critical",
                    context={"branch": branch},
                )
            )

    # Reordenar pra ordem canonica
    by_code: dict[str, Inconsistency] = {i.code: i for i in found}
    ordered = [by_code[c] for c in CANONICAL_ORDER if c in by_code]
    return ordered


# Plan rendering -------------------------------------------------------------

def propose_recovery_plan(inconsistencies: list[Inconsistency]) -> str:
    """Renderiza plano de recovery em markdown."""
    if not inconsistencies:
        return "Workspace consistent. Nada a recuperar.\n"

    lines: list[str] = []
    lines.append("# Recovery Plan\n")
    lines.append(
        f"Detectadas {len(inconsistencies)} inconsistencia(s) em L1.\n"
    )

    # Tabela summary
    lines.append("## Resumo\n")
    lines.append("| Code | Severity | Message |")
    lines.append("|---|---|---|")
    for inc in inconsistencies:
        msg = inc.message.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {inc.code} | {inc.severity} | {msg} |")
    lines.append("")

    # Detalhes por inconsistencia + 3 opcoes
    lines.append("## Detalhe e acoes\n")
    for idx, inc in enumerate(inconsistencies, start=1):
        lines.append(f"### {idx}. {inc.code} ({inc.severity})\n")
        lines.append(f"{inc.message}\n")
        lines.append("**Plan A (preserve):** " + inc.proposed_action)
        lines.append(
            "**Plan B (rollback):** rollback L1 pro ultimo estado consistente"
            " antes do evento problematico"
        )
        lines.append(
            "**Plan C (escalate):** marcar status=BLOCKED_ERROR e "
            "escalar pra humano (sem mudanca automatizada)"
        )
        lines.append("")

    lines.append("## Escolha")
    lines.append(
        "Selecione A | B | C aplicavel a TODAS as inconsistencias "
        "(batch). Para resolucao individual, edite L1 manualmente."
    )
    return "\n".join(lines) + "\n"


# Apply ----------------------------------------------------------------------

def _append_history(
    state: dict[str, Any], event: dict[str, Any]
) -> None:
    history = state.setdefault("history", [])
    if not isinstance(history, list):
        raise RecoveryWizardError("history nao eh lista — L1 corrompido")
    history.append(event)


def _now_iso(now: datetime | None = None) -> str:
    if now is None:
        now = datetime.now(timezone.utc)
    # ISO 8601 com 'Z'
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _apply_plan_a(
    workspace_path: Path,
    state: dict[str, Any],
    inconsistencies: list[Inconsistency],
    now: datetime,
) -> None:
    """Plan A — preserve. Aplica fix por code."""
    codes = [i.code for i in inconsistencies]

    for inc in inconsistencies:
        if inc.code == CODE_HASH_MISMATCH:
            actual = inc.context.get("actual") or _compute_profile_hash(
                workspace_path
            )
            if actual:
                state["profile_effective_hash"] = actual

        elif inc.code == CODE_MISSING_COMMIT:
            history = state.get("history") or []
            # Acha penultimo evento com commit_sha valido (preferencia: stage_transition)
            valid: list[dict[str, Any]] = [
                ev
                for ev in history
                if isinstance(ev, dict)
                and ev.get("commit_sha")
                and ev.get("commit_sha") != state.get(
                    "last_transition", {}
                ).get("commit_sha")
            ]
            if valid:
                fallback = valid[-1]
                state["last_transition"] = {
                    "from": fallback.get("from", "unknown"),
                    "to": fallback.get("to", state.get("sub_stage")),
                    "at": fallback.get("at", _now_iso(now)),
                    "commit_sha": fallback["commit_sha"],
                }

        elif inc.code == CODE_MISSING_OUTPUT:
            # Append warning event; nao apaga history existente (append-only).
            _append_history(
                state,
                {
                    "at": _now_iso(now),
                    "event": "recovery_warning",
                    "note": (
                        "outputs ausentes: "
                        + ", ".join(inc.context.get("missing", []))
                    ),
                },
            )

        elif inc.code == CODE_STALE_IN_PROGRESS:
            state["status"] = "COMPLETED_AWAITING_HUMAN"

        elif inc.code == CODE_MISSING_WORKTREES:
            # Cria placeholder
            wt_path = inc.context.get("expected_path")
            if wt_path:
                p = Path(wt_path)
                p.mkdir(parents=True, exist_ok=True)
                placeholder = p / ".recovery-placeholder"
                placeholder.write_text(
                    "placeholder criado por recovery-wizard\n",
                    encoding="utf-8",
                )

        elif inc.code == CODE_BRANCH_MISSING:
            # Plan A pra branch missing nao re-cria automaticamente —
            # apenas registra warning. Recreate exige humano.
            _append_history(
                state,
                {
                    "at": _now_iso(now),
                    "event": "recovery_warning",
                    "note": (
                        "branch ausente: "
                        + inc.context.get("branch", "")
                        + ". Sugestao: git reflog | grep "
                        + inc.context.get("branch", "")
                    ),
                },
            )

    # Append evento sumario recovery_applied
    _append_history(
        state,
        {
            "at": _now_iso(now),
            "event": "recovery_applied",
            "note": f"wizard fix (Plan A): {','.join(codes)}",
            "context": {"codes": codes, "plan": "A"},
        },
    )


def _apply_plan_b(
    workspace_path: Path,
    state: dict[str, Any],
    inconsistencies: list[Inconsistency],
    now: datetime,
) -> None:
    """Plan B — rollback. Reverte L1 pro ultimo estado consistente."""
    codes = [i.code for i in inconsistencies]
    history = state.get("history") or []

    # Estrategia: pra cada code aplicavel, reverter o campo pro penultimo
    # evento valido em history. Mais conservador que Plan A.
    if any(i.code == CODE_MISSING_COMMIT for i in inconsistencies):
        # Mesmo handler do A
        valid = [
            ev
            for ev in history
            if isinstance(ev, dict)
            and ev.get("commit_sha")
            and ev.get("commit_sha") != state.get(
                "last_transition", {}
            ).get("commit_sha")
        ]
        if valid:
            fallback = valid[-1]
            state["last_transition"] = {
                "from": fallback.get("from", "unknown"),
                "to": fallback.get("to", state.get("sub_stage")),
                "at": fallback.get("at", _now_iso(now)),
                "commit_sha": fallback["commit_sha"],
            }

    if any(i.code == CODE_HASH_MISMATCH for i in inconsistencies):
        # Plan B: nao mexe em L1 (assume profile-effective.yaml errado);
        # registra warning para humano regenerar profile.
        pass

    if any(i.code == CODE_MISSING_WORKTREES for i in inconsistencies):
        # Rollback waves.current pro ultimo completed
        waves = state.get("waves") or {}
        completed = waves.get("completed") or []
        if isinstance(completed, list) and completed:
            waves["current"] = max(int(c) for c in completed)
            state["waves"] = waves

    if any(i.code == CODE_STALE_IN_PROGRESS for i in inconsistencies):
        # Plan B identico ao A
        state["status"] = "COMPLETED_AWAITING_HUMAN"

    _append_history(
        state,
        {
            "at": _now_iso(now),
            "event": "recovery_applied",
            "note": f"wizard fix (Plan B rollback): {','.join(codes)}",
            "context": {"codes": codes, "plan": "B"},
        },
    )


def _apply_plan_c(
    workspace_path: Path,
    state: dict[str, Any],
    inconsistencies: list[Inconsistency],
    now: datetime,
) -> None:
    """Plan C — escalate. Marca BLOCKED_ERROR + history append. Sem mudanca."""
    codes = [i.code for i in inconsistencies]
    state["status"] = "BLOCKED_ERROR"
    _append_history(
        state,
        {
            "at": _now_iso(now),
            "event": "recovery_applied",
            "note": f"wizard escalate (Plan C): {','.join(codes)}",
            "context": {"codes": codes, "plan": "C"},
        },
    )


def apply_recovery(
    workspace_path: Path,
    plan_choice: str,
    *,
    project_root: Path | None = None,
    now: datetime | None = None,
) -> None:
    """Aplica recovery escolhido. plan_choice in {A, B, C}.

    Workspace consistente -> no-op (sem write).
    """
    if plan_choice not in {"A", "B", "C"}:
        raise RecoveryWizardError(
            f"plan_choice invalido: '{plan_choice}'. Esperado A | B | C."
        )

    if now is None:
        now = datetime.now(timezone.utc)

    inconsistencies = detect_inconsistencies(
        workspace_path, project_root=project_root, now=now
    )
    if not inconsistencies:
        return  # No-op em workspace consistente

    state, _, rest = _parse_l1(workspace_path)

    if plan_choice == "A":
        _apply_plan_a(workspace_path, state, inconsistencies, now)
    elif plan_choice == "B":
        _apply_plan_b(workspace_path, state, inconsistencies, now)
    else:  # C
        _apply_plan_c(workspace_path, state, inconsistencies, now)

    _write_l1(workspace_path, state, rest)


# CLI ------------------------------------------------------------------------

def _print_audit(
    workspace_path: Path,
    inconsistencies: list[Inconsistency],
) -> None:
    if not inconsistencies:
        print(f"Workspace consistent: {workspace_path}")
        return
    print(propose_recovery_plan(inconsistencies))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="recovery-wizard.py",
        description=(
            "Detecta inconsistencias L1 (CONTEXT.md raiz) e propoe / "
            "aplica recovery."
        ),
    )
    parser.add_argument(
        "--workspace", required=True, help="Caminho do workspace"
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Override pro project_root (default: lido de L1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Audit only — imprime inconsistencias e plano sem aplicar",
    )
    parser.add_argument(
        "--apply",
        choices=["A", "B", "C"],
        default=None,
        help="Aplica plan A | B | C nao-interativo",
    )
    args = parser.parse_args(argv)

    workspace = Path(args.workspace)
    project_root = Path(args.project_root) if args.project_root else None

    if not workspace.is_dir():
        print(
            f"RecoveryWizardError: workspace nao existe: {workspace}",
            file=sys.stderr,
        )
        return 1

    try:
        inconsistencies = detect_inconsistencies(
            workspace, project_root=project_root
        )
    except RecoveryWizardError as exc:
        print(f"RecoveryWizardError: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        _print_audit(workspace, inconsistencies)
        return 0  # Audit mode sempre exit 0

    if args.apply:
        if not inconsistencies:
            print(f"Workspace consistent: {workspace}")
            return 0
        try:
            apply_recovery(
                workspace, args.apply, project_root=project_root
            )
        except RecoveryWizardError as exc:
            print(f"RecoveryWizardError: {exc}", file=sys.stderr)
            return 1
        print(
            f"Recovery applied (Plan {args.apply}): "
            f"{len(inconsistencies)} inconsistencia(s) processada(s)."
        )
        return 0

    # Modo interativo
    if not inconsistencies:
        print(f"Workspace consistent: {workspace}")
        return 0

    print(propose_recovery_plan(inconsistencies))
    print("Escolha plano (A / B / C) ou Q pra sair:")
    try:
        choice = input("> ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        print("Cancelado.")
        return 1
    if choice == "Q":
        print("Cancelado.")
        return 1
    if choice not in {"A", "B", "C"}:
        print(f"Escolha invalida: {choice}", file=sys.stderr)
        return 1
    try:
        apply_recovery(workspace, choice, project_root=project_root)
    except RecoveryWizardError as exc:
        print(f"RecoveryWizardError: {exc}", file=sys.stderr)
        return 1
    print(f"Recovery applied (Plan {choice}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
