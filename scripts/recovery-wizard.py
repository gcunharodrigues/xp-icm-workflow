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
CODE_BRANCH_MISSING = "BRANCH_MISSING"
CODE_CLAUDE_MD_ROOT_STALE = "CLAUDE_MD_ROOT_STALE"
CODE_CLAUDE_MD_ROOT_MISSING = "CLAUDE_MD_ROOT_MISSING"
# v3.4.0: worktree model
CODE_WORKTREE_MISSING = "WORKTREE_MISSING"
CODE_WORKTREE_WRONG_BRANCH = "WORKTREE_WRONG_BRANCH"
CODE_WRONG_BRANCH_CHECKOUT = "WRONG_BRANCH_CHECKOUT"
# v3.4.2: gate inline antes do kickoff
CODE_KICKOFF_WITHOUT_GATE = "KICKOFF_WITHOUT_GATE"
# v3.4.3: wave worktree cleanup
CODE_WAVE_WORKTREE_ORPHAN = "WAVE_WORKTREE_ORPHAN"

# Ordem canonica determinista (R2.7 batch order).
CANONICAL_ORDER: tuple[str, ...] = (
    CODE_HASH_MISMATCH,
    CODE_MISSING_COMMIT,
    CODE_MISSING_OUTPUT,
    CODE_STALE_IN_PROGRESS,
    CODE_BRANCH_MISSING,
    CODE_CLAUDE_MD_ROOT_STALE,
    CODE_CLAUDE_MD_ROOT_MISSING,
    CODE_WORKTREE_MISSING,
    CODE_WORKTREE_WRONG_BRANCH,
    CODE_WRONG_BRANCH_CHECKOUT,
    CODE_KICKOFF_WITHOUT_GATE,
    CODE_WAVE_WORKTREE_ORPHAN,
)

# Mapping stage_atual → next stage dir (pra detectar KICKOFF_WITHOUT_GATE).
# Stage 04 omitido por ter logica de waves complexa; 00 e 08 nao se aplicam.
_NEXT_STAGE_DIR: dict[str, str] = {
    "01": "02_design",
    "02": "03_wave_planner",
    "03": "04_implementation_waves",
    "05": "06_review",
    "06": "07_merge",
    "07": "08_feedback_intake",
}

# Mapping pra Plan A do KICKOFF_WITHOUT_GATE: stage_atual → (next_stage_id,
# next_sub_stage, next_status). Stage 07 special (auto-transit pra 08 com
# status=COMPLETED_AWAITING_HUMAN, workspace fica vivo aguardando feedback).
_GATE_RETRO_TRANSITION: dict[str, tuple[str, str, str]] = {
    "01": ("02", "02_in_progress", "IN_PROGRESS"),
    "02": ("03", "03_in_progress", "IN_PROGRESS"),
    "03": ("04", "04_wave_1_in_progress", "IN_PROGRESS"),
    "05": ("06", "06_in_progress", "IN_PROGRESS"),
    "06": ("07", "07_in_progress", "IN_PROGRESS"),
    "07": ("08", "08_in_progress", "COMPLETED_AWAITING_HUMAN"),
}

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


def _list_worktrees(cwd: Path) -> list[tuple[str, str]]:
    """Parse `git worktree list --porcelain`. Retorna [(path, branch), ...].

    Worktree sem branch (detached HEAD) tem branch="". Path sempre absoluto.
    """
    result = _run_git(["worktree", "list", "--porcelain"], cwd=cwd)
    if result.returncode != 0:
        return []
    out: list[tuple[str, str]] = []
    cur_path = ""
    cur_branch = ""
    for line in result.stdout.split("\n"):
        line = line.rstrip()
        if line.startswith("worktree "):
            if cur_path:
                out.append((cur_path, cur_branch))
            cur_path = line[len("worktree "):]
            cur_branch = ""
        elif line.startswith("branch refs/heads/"):
            cur_branch = line[len("branch refs/heads/"):]
    if cur_path:
        out.append((cur_path, cur_branch))
    return out


def _is_branch_merged(
    branch: str, base_branch: str, *, cwd: Path | None = None
) -> bool:
    """True se `branch` ja foi merged em `base_branch` (i.e., ancestor)."""
    if not branch or not base_branch:
        return False
    result = _run_git(
        ["merge-base", "--is-ancestor", branch, base_branch], cwd=cwd
    )
    return result.returncode == 0


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
    """Roda os 5 checks. Retorna inconsistencias em ordem canonica.

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

    # 5) BRANCH_MISSING (R4.5)
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

    # 6) CLAUDE_MD_ROOT_STALE / MISSING (G5)
    # Verifica consistência entre L1.stage_atual e bloco do workspace no
    # <project_root>/CLAUDE.md (região ICM). Doc: references/project-root-claude-md.md.
    if project_root is not None and project_root.is_dir():
        ws_id = state.get("workspace", "")
        l1_status = state.get("status", "")
        l1_stage = str(state.get("stage_atual", ""))
        if ws_id and l1_status == "IN_PROGRESS":
            root_block = _get_root_workspace_block(project_root, ws_id)
            if root_block is None:
                found.append(
                    Inconsistency(
                        code=CODE_CLAUDE_MD_ROOT_MISSING,
                        message=(
                            f"workspace {ws_id} status=IN_PROGRESS mas não "
                            "aparece como bloco em <project_root>/CLAUDE.md "
                            "região ICM. Bootstrap não rodou ou bloco foi "
                            "removido manualmente."
                        ),
                        proposed_action=(
                            "regerar bloco do workspace a partir do L1 via "
                            "handoff.py update-project-md"
                        ),
                        severity="warning",
                        context={"workspace": ws_id},
                    )
                )
            else:
                root_stage = str(root_block.get("stage_atual", ""))
                if root_stage and l1_stage and root_stage != l1_stage:
                    found.append(
                        Inconsistency(
                            code=CODE_CLAUDE_MD_ROOT_STALE,
                            message=(
                                f"<project_root>/CLAUDE.md mostra stage "
                                f"{root_stage!r} para workspace {ws_id} mas "
                                f"L1 declara {l1_stage!r}. Sessão anterior "
                                "crash sem chamar handoff."
                            ),
                            proposed_action=(
                                "regerar bloco a partir do L1 via "
                                "handoff.py update-project-md"
                            ),
                            severity="warning",
                            context={
                                "workspace": ws_id,
                                "root_stage": root_stage,
                                "l1_stage": l1_stage,
                            },
                        )
                    )

    # 7) WORKTREE_MISSING / WORKTREE_WRONG_BRANCH (v3.4.0)
    # `.icm-main/` worktree linkada eh obrigatoria desde v3.4.0. Doc:
    # references/worktree-model.md.
    if project_root is not None and project_root.is_dir():
        base_branch = state.get("base_branch", "")
        worktree_path = project_root / ".icm-main"
        if not worktree_path.exists():
            found.append(
                Inconsistency(
                    code=CODE_WORKTREE_MISSING,
                    message=(
                        f"`.icm-main/` worktree ausente em {project_root}. "
                        "Modelo cross-branch v3.4.0 exige worktree linkada da "
                        "base branch. Sessoes futuras nao conseguirao ler "
                        "ADRs/lessons/tech_debt."
                    ),
                    proposed_action=(
                        f"git -C {project_root} worktree add .icm-main {base_branch or '<BASE_BRANCH>'}"
                    ),
                    severity="critical",
                    context={"project_root": str(project_root), "base_branch": base_branch},
                )
            )
        else:
            # Validar branch checada
            try:
                import subprocess as _sp
                res = _sp.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=worktree_path,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                wt_branch = res.stdout.strip()
                if base_branch and wt_branch and wt_branch != base_branch:
                    found.append(
                        Inconsistency(
                            code=CODE_WORKTREE_WRONG_BRANCH,
                            message=(
                                f"`.icm-main/` esta em '{wt_branch}', deveria "
                                f"estar em base_branch '{base_branch}'."
                            ),
                            proposed_action=(
                                f"cd {worktree_path} && git checkout {base_branch}"
                            ),
                            severity="warning",
                            context={"current": wt_branch, "expected": base_branch},
                        )
                    )
            except Exception:
                pass

    # 8) WRONG_BRANCH_CHECKOUT (v3.4.0)
    # Worktree principal deveria estar em workspace branch durante ciclo ICM
    # ativo. Se humano abriu sessao em base_branch por engano, sinaliza.
    expected_ws_branch = state.get("workspace_branch", "")
    if expected_ws_branch and project_root is not None and project_root.is_dir():
        try:
            import subprocess as _sp2
            res2 = _sp2.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=False,
            )
            current_branch = res2.stdout.strip()
            l1_status = state.get("status", "")
            if (
                current_branch
                and current_branch != expected_ws_branch
                and l1_status not in ("COMPLETED",)
            ):
                found.append(
                    Inconsistency(
                        code=CODE_WRONG_BRANCH_CHECKOUT,
                        message=(
                            f"branch atual em {project_root} eh '{current_branch}', "
                            f"esperado '{expected_ws_branch}' (workspace ainda ativo, "
                            f"status={l1_status})."
                        ),
                        proposed_action=(
                            f"git -C {project_root} checkout {expected_ws_branch}"
                        ),
                        severity="warning",
                        context={"current": current_branch, "expected": expected_ws_branch},
                    )
                )
        except Exception:
            pass

    # 9) KICKOFF_WITHOUT_GATE (v3.4.2)
    # Sintoma do bug pre-v3.4.2: sessao anterior renderizou _kickoff.md do
    # stage NN+1 mas L1 indica stage_atual=NN com status=COMPLETED_AWAITING_HUMAN
    # (gate nao aprovado). Workspaces criados antes do fix podem estar
    # neste estado. Detect: kickoff existe AND status pendente AND
    # sub_stage termina em _completed.
    stage_atual = str(state.get("stage_atual", ""))
    sub_stage = str(state.get("sub_stage", ""))
    status = state.get("status", "")
    next_dir = _NEXT_STAGE_DIR.get(stage_atual)
    if (
        next_dir
        and status == "COMPLETED_AWAITING_HUMAN"
        and sub_stage.endswith("_completed")
    ):
        kickoff_path = workspace_path / "stages" / next_dir / "_kickoff.md"
        if kickoff_path.is_file():
            found.append(
                Inconsistency(
                    code=CODE_KICKOFF_WITHOUT_GATE,
                    message=(
                        f"_kickoff.md de {next_dir} existe mas L1 declara "
                        f"stage_atual={stage_atual!r} sub_stage={sub_stage!r} "
                        "status=COMPLETED_AWAITING_HUMAN. Sintoma do bug "
                        "pre-v3.4.2: sessao anterior renderizou kickoff sem "
                        "aguardar gate humano."
                    ),
                    proposed_action=(
                        "aprovar gate retroativo (mantém kickoff, transita "
                        "L1 pra próximo stage)"
                    ),
                    severity="warning",
                    context={
                        "stage_atual": stage_atual,
                        "sub_stage": sub_stage,
                        "kickoff_path": str(kickoff_path),
                        "next_dir": next_dir,
                    },
                )
            )

    # 10) WAVE_WORKTREE_ORPHAN (v3.4.3)
    # Worktrees efemeras criadas pelo Agent tool em fase 04 deveriam ser
    # removidas pelo lead apos merge sequencial + CI verde. Bug pre-v3.4.3:
    # cleanup ausente fazia worktrees + branches `wave-<NNN>-N/<task>`
    # acumularem em <project_root>/.icm-wave-* (ou path retornado pelo
    # Agent tool). Detect: worktrees com branch pattern `wave-<NNN>-`
    # onde NNN bate workspace_num, AND branch ja merged em base_branch
    # (cleanup safe).
    if project_root is not None and project_root.is_dir():
        ws_id = state.get("workspace", "")
        base_branch = state.get("base_branch", "")
        if ws_id and base_branch:
            workspace_num = ws_id.split("-", 1)[0]  # "001-..." -> "001"
            wave_branch_prefix = f"wave-{workspace_num}-"
            worktrees = _list_worktrees(project_root)
            orphans: list[tuple[str, str]] = []
            for wt_path, wt_branch in worktrees:
                # Skip worktree principal (project_root) e .icm-main
                wt_path_resolved = Path(wt_path).resolve()
                if wt_path_resolved == project_root.resolve():
                    continue
                if wt_path_resolved == (project_root / ".icm-main").resolve():
                    continue
                if not wt_branch.startswith(wave_branch_prefix):
                    continue
                # Cleanup safe apenas se branch ja merged
                if _is_branch_merged(wt_branch, base_branch, cwd=project_root):
                    orphans.append((wt_path, wt_branch))
            if orphans:
                listed = ", ".join(f"{p} ({b})" for p, b in orphans[:3])
                more = f" (+{len(orphans) - 3} more)" if len(orphans) > 3 else ""
                found.append(
                    Inconsistency(
                        code=CODE_WAVE_WORKTREE_ORPHAN,
                        message=(
                            f"{len(orphans)} wave worktree(s) orfa(s) "
                            f"detectada(s): {listed}{more}. Bug pre-v3.4.3: "
                            "lead nao executou cleanup pos-merge."
                        ),
                        proposed_action=(
                            "auto-cleanup: git worktree remove + "
                            "git branch -d (safe pq ja merged)"
                        ),
                        severity="warning",
                        context={
                            "orphans": orphans,
                            "workspace_num": workspace_num,
                            "base_branch": base_branch,
                        },
                    )
                )

    # Reordenar pra ordem canonica
    by_code: dict[str, Inconsistency] = {i.code: i for i in found}
    ordered = [by_code[c] for c in CANONICAL_ORDER if c in by_code]
    return ordered


def _get_root_workspace_block(project_root: Path, workspace_id: str) -> dict | None:
    """Lê <project_root>/CLAUDE.md, retorna dict do bloco do workspace ou None.

    Parse via comentários `<!-- ICM-DATA:... -->` (JSON). Lazy import de handoff
    via sys.path para evitar dependência circular.
    """
    claude_md = project_root / "CLAUDE.md"
    if not claude_md.is_file():
        return None
    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        import handoff  # noqa: PLC0415
    except ImportError:
        return None
    blocks = handoff._parse_workspace_blocks(claude_md)
    block = blocks.get(workspace_id)
    if block is None:
        return None
    from dataclasses import asdict  # noqa: PLC0415
    return asdict(block)


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

        elif inc.code == CODE_WAVE_WORKTREE_ORPHAN:
            # Plan A: auto-cleanup. Para cada orfa: git worktree remove +
            # git branch -d. Cleanup safe pq deteccao filtrou por branch
            # ja merged em base_branch.
            project_root_str = state.get("project_root", "")
            if not project_root_str:
                continue
            cwd = Path(project_root_str)
            orphans = inc.context.get("orphans", []) or []
            removed: list[str] = []
            failed: list[str] = []
            for wt_path, wt_branch in orphans:
                # 1. Remove worktree
                wt_result = _run_git(
                    ["worktree", "remove", wt_path], cwd=cwd
                )
                if wt_result.returncode != 0:
                    # Tenta com --force se cleanup falhou
                    wt_result = _run_git(
                        ["worktree", "remove", "--force", wt_path], cwd=cwd
                    )
                # 2. Delete branch (safe pq merged)
                br_result = _run_git(
                    ["branch", "-d", wt_branch], cwd=cwd
                )
                if wt_result.returncode == 0 and br_result.returncode == 0:
                    removed.append(f"{wt_path} ({wt_branch})")
                else:
                    failed.append(
                        f"{wt_path} ({wt_branch}): "
                        f"worktree_rc={wt_result.returncode}, "
                        f"branch_rc={br_result.returncode}"
                    )
            note = (
                f"removed {len(removed)} orfa(s); "
                f"failed {len(failed)}: {failed[:3]}"
            )
            _append_history(
                state,
                {
                    "at": _now_iso(now),
                    "event": "recovery_warning"
                    if failed
                    else "recovery_applied",
                    "note": (
                        "wave worktree cleanup (Plan A): " + note
                    ),
                },
            )

        elif inc.code == CODE_KICKOFF_WITHOUT_GATE:
            # Plan A: aprovar gate retroativamente. Transita L1 pro próximo
            # stage usando _GATE_RETRO_TRANSITION (mantém kickoff já gerado).
            stage_atual_str = str(state.get("stage_atual", ""))
            transition = _GATE_RETRO_TRANSITION.get(stage_atual_str)
            if transition:
                next_stage, next_sub, next_status = transition
                prev_sub = str(state.get("sub_stage", ""))
                state["stage_atual"] = next_stage
                state["sub_stage"] = next_sub
                state["status"] = next_status
                state["last_transition"] = {
                    "from": prev_sub,
                    "to": next_sub,
                    "at": _now_iso(now),
                    "commit_sha": state.get("last_transition", {}).get(
                        "commit_sha", ""
                    ),
                }
                _append_history(
                    state,
                    {
                        "at": _now_iso(now),
                        "event": "stage_transition",
                        "from": prev_sub,
                        "to": next_sub,
                        "note": (
                            "gate approved retroactively via recovery wizard "
                            "(KICKOFF_WITHOUT_GATE Plan A)"
                        ),
                    },
                )

        elif inc.code in (CODE_CLAUDE_MD_ROOT_STALE, CODE_CLAUDE_MD_ROOT_MISSING):
            # Plan A: regerar bloco do workspace no <project_root>/CLAUDE.md
            # a partir do estado L1 atual. Lazy import de handoff.
            scripts_dir = str(Path(__file__).resolve().parent)
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            try:
                import handoff  # noqa: PLC0415
            except ImportError:
                _append_history(
                    state,
                    {
                        "at": _now_iso(now),
                        "event": "recovery_warning",
                        "note": "handoff.py indisponível; bloco CLAUDE.md root não regenerado",
                    },
                )
                continue
            ws_id = state.get("workspace", "")
            proj_root_str = state.get("project_root", "")
            if not (ws_id and proj_root_str):
                continue
            proj_root = Path(proj_root_str)
            sub_stage = state.get("sub_stage", f"{state.get('stage_atual', '00')}_in_progress")
            stage_id = str(state.get("stage_atual", "00"))
            stage_dir = handoff.STAGE_DIR_BY_ID.get(stage_id, f"{stage_id}_unknown")
            block = handoff.WorkspaceBlock(
                workspace=ws_id,
                profile=state.get("profile_base", ""),
                tier=state.get("tier", ""),
                stage_atual=stage_id,
                stage_dir=stage_dir,
                sub_stage=sub_stage,
                iteration=int(state.get("iteration", 0)),
                status=state.get("status", "IN_PROGRESS"),
                last_action="recovery_wizard regenerated block",
                last_action_at=_now_iso(now),
                next_action=state.get("next_action", ""),
            )
            # SKILL_DIR não está em L1; usar placeholder (workspace L0 tem skill_dir
            # absoluto, mas recovery não consulta L0). Doc canônico orienta usuário.
            handoff.update_project_claude_md(proj_root, block, skill_dir="<skill-dir>")

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

    if any(i.code == CODE_STALE_IN_PROGRESS for i in inconsistencies):
        # Plan B identico ao A
        state["status"] = "COMPLETED_AWAITING_HUMAN"

    # KICKOFF_WITHOUT_GATE: Plan B = deleta kickoff + volta L1 pra in_progress.
    # Workspace continua trabalhando no stage NN (refaz outputs).
    for inc in inconsistencies:
        if inc.code == CODE_KICKOFF_WITHOUT_GATE:
            kickoff_path_str = inc.context.get("kickoff_path", "")
            if kickoff_path_str:
                kickoff_path = Path(kickoff_path_str)
                if kickoff_path.is_file():
                    try:
                        kickoff_path.unlink()
                    except OSError:
                        pass  # warning silencioso — humano vê history
            stage_atual_str = str(state.get("stage_atual", ""))
            prev_sub = str(state.get("sub_stage", ""))
            new_sub = f"{stage_atual_str}_in_progress"
            state["sub_stage"] = new_sub
            state["status"] = "IN_PROGRESS"
            state["last_transition"] = {
                "from": prev_sub,
                "to": new_sub,
                "at": _now_iso(now),
                "commit_sha": state.get("last_transition", {}).get(
                    "commit_sha", ""
                ),
            }
            _append_history(
                state,
                {
                    "at": _now_iso(now),
                    "event": "stage_transition",
                    "from": prev_sub,
                    "to": new_sub,
                    "note": (
                        "kickoff deletado, voltando ao trabalho via "
                        "recovery wizard (KICKOFF_WITHOUT_GATE Plan B)"
                    ),
                },
            )

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
