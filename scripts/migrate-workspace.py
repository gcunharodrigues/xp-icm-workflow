"""Migrate workspace — orquestrador de migrations encadeadas (v3.8.0).

Detecta versão atual via L0 frontmatter `icm_skill_version` e aplica
sequência de migrations até `--target` (default: SKILL_VERSION corrente).

Versões suportadas: v3.3.0+. Beta1/beta2 explicitamente unsupported
(estado batched/legacy de pre-3.3 sem path automatizável).

Trigger:
- `auto-prompt`: workspace status ∈ {COMPLETED, COMPLETED_AWAITING_HUMAN}
  → bootstrap/sessão fase 08 deve oferecer migration.
- `warning-only`: status IN_PROGRESS → não interromper trabalho mid-stage,
  só logar warning.

Backup automático em <project_root>/.icm-migration-backup/<timestamp>/
antes de cada step. Idempotente: re-rodar não duplica state.

CLI:
    python migrate-workspace.py --workspace-root <path> [--target 3.7.2] \\
        [--project-root <path>] [--dry-run] [--no-backup]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import re
import shutil
import sys
from pathlib import Path
from typing import Sequence


# ============================================================================
# Constantes
# ============================================================================

CURRENT_SKILL_VERSION = "3.9.0"
FLOOR_VERSION = "3.3.0"

# Sequência de versões suportadas. Migration steps são pares consecutivos.
# v3.7.1 colapsada em v3.7.2 (changelog: intermediária mergeada). Migration
# direta 3.7.0→3.7.2 cobre ambas — sem schema change em L0.
SUPPORTED_VERSIONS: tuple[str, ...] = (
    "3.3.0",
    "3.4.0",
    "3.5.0",
    "3.6.0",
    "3.7.0",
    "3.7.2",
    "3.8.0",
    "3.9.0",
)


class MigrationError(Exception):
    """Erro de migration (versão não suportada, conflito, IO)."""


# ============================================================================
# Lazy import helpers (scripts com hyphen)
# ============================================================================

def _load_runtime_registry():
    if "runtime_registry" in sys.modules:
        return sys.modules["runtime_registry"]
    path = Path(__file__).resolve().parent / "runtime-registry.py"
    spec = importlib.util.spec_from_file_location("runtime_registry", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["runtime_registry"] = mod
    spec.loader.exec_module(mod)
    return mod


# ============================================================================
# Version detection
# ============================================================================

VERSION_RE = re.compile(
    r'icm_skill_version:\s*"?([0-9]+\.[0-9]+\.[0-9]+)"?',
)

STATUS_RE = re.compile(
    r'status:\s*"?([A-Z_]+)"?',
)


def detect_workspace_version(workspace_root: Path) -> str | None:
    """Lê L0 (`<ws>/CLAUDE.md`) e extrai icm_skill_version do frontmatter.

    Retorna versão semver ou None se L0 ausente / sem campo.
    """
    l0 = workspace_root / "CLAUDE.md"
    if not l0.is_file():
        return None
    text = l0.read_text(encoding="utf-8")
    match = VERSION_RE.search(text)
    if not match:
        return None
    return match.group(1)


def detect_trigger_mode(workspace_root: Path) -> str:
    """Decide trigger: auto-prompt vs warning-only.

    Status COMPLETED/AWAITING → auto-prompt (seguro interromper).
    IN_PROGRESS → warning-only (não interromper trabalho ativo).
    """
    l1 = workspace_root / "CONTEXT.md"
    if not l1.is_file():
        return "auto-prompt"
    text = l1.read_text(encoding="utf-8")
    match = STATUS_RE.search(text)
    if not match:
        return "auto-prompt"
    status = match.group(1)
    if status in ("COMPLETED", "COMPLETED_AWAITING_HUMAN"):
        return "auto-prompt"
    return "warning-only"


# ============================================================================
# Plan
# ============================================================================

def plan_migration(from_version: str, to_version: str) -> list[str]:
    """Retorna lista de steps `<a>-><b>` ordenada from → to.

    Raise MigrationError se from < FLOOR_VERSION.
    """
    if from_version not in SUPPORTED_VERSIONS:
        raise MigrationError(
            f"versão {from_version} abaixo do floor {FLOOR_VERSION} "
            f"(supported: {SUPPORTED_VERSIONS}). "
            "Migration manual necessária pra workspaces pre-3.3.0."
        )
    if to_version not in SUPPORTED_VERSIONS:
        raise MigrationError(
            f"target {to_version} desconhecido (supported: {SUPPORTED_VERSIONS})"
        )
    from_idx = SUPPORTED_VERSIONS.index(from_version)
    to_idx = SUPPORTED_VERSIONS.index(to_version)
    if from_idx >= to_idx:
        return []
    steps = []
    for i in range(from_idx, to_idx):
        a = SUPPORTED_VERSIONS[i]
        b = SUPPORTED_VERSIONS[i + 1]
        steps.append(f"{a}->{b}")
    return steps


# ============================================================================
# Backup
# ============================================================================

def backup_workspace(workspace_root: Path) -> Path:
    """Copia workspace pra `<project_root>/.icm-migration-backup/<ts>/<ws>/`.

    Não copia `_state/` (local-only) nem `output/` (artefatos pesados — git
    tem versão).
    """
    project_root = workspace_root.parent.parent
    ts = _dt.datetime.now(_dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_root = project_root / ".icm-migration-backup" / ts / workspace_root.name
    backup_root.mkdir(parents=True, exist_ok=True)
    for entry in workspace_root.iterdir():
        if entry.name in ("_state", "output"):
            continue
        if entry.is_file():
            shutil.copy2(entry, backup_root / entry.name)
        elif entry.is_dir():
            shutil.copytree(entry, backup_root / entry.name,
                            dirs_exist_ok=True)
    return backup_root


# ============================================================================
# Migration steps
# ============================================================================

def migrate_3_6_to_3_7(workspace_root: Path, project_root: Path) -> None:
    """v3.6.0 → v3.7.0 step:
    - Bump L0 icm_skill_version
    - Cria _state/ dir
    - Migra .icm-main/.dev-server.pid → runtime-registry (se PID alive)
    """
    rr = _load_runtime_registry()

    # 1. Bump L0 version
    l0 = workspace_root / "CLAUDE.md"
    if l0.is_file():
        text = l0.read_text(encoding="utf-8")
        new_text = VERSION_RE.sub(
            'icm_skill_version: "3.7.0"', text,
        )
        if new_text != text:
            l0.write_text(new_text, encoding="utf-8")

    # 2. _state/ dir
    state_dir = workspace_root / "_state"
    state_dir.mkdir(exist_ok=True)

    # 3. Migrate legacy .dev-server.pid
    pid_file = project_root / ".icm-main" / ".dev-server.pid"
    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
        except ValueError:
            pid = -1
        if pid > 0 and rr._is_pid_alive(pid):
            # Idempotente: só registra se ainda não existe entry com mesmo pid
            existing = rr.list_entries(workspace_root, kind="dev_server")
            if not any(e.get("pid") == pid for e in existing):
                rr.register(
                    workspace_root,
                    kind="dev_server",
                    pid=pid,
                    cmd="(migrated from .icm-main/.dev-server.pid)",
                )
        # Remove legacy file (alive ou morto — registry assume tracking)
        pid_file.unlink()


# Steps no-op pra versões intermediárias (mudanças foram backward-compat).
# Cada step só bumpa L0 version pra próxima versão da sequência. Workspaces
# v3.4/v3.5/v3.6 já têm schemas compatíveis; nenhum dado migrate.

def _bump_version_only(workspace_root: Path, target: str) -> None:
    l0 = workspace_root / "CLAUDE.md"
    if l0.is_file():
        text = l0.read_text(encoding="utf-8")
        new_text = VERSION_RE.sub(
            f'icm_skill_version: "{target}"', text,
        )
        if new_text != text:
            l0.write_text(new_text, encoding="utf-8")


def migrate_3_3_to_3_4(workspace_root: Path, project_root: Path) -> None:
    """v3.3 → v3.4: cross-branch worktree model. Migration substantive
    em scripts/migrate-v3.3-to-v3.4.py (pre-existing). Aqui apenas bump
    de version se já foi migrado manualmente."""
    _bump_version_only(workspace_root, "3.4.0")


def migrate_3_4_to_3_5(workspace_root: Path, project_root: Path) -> None:
    """v3.4 → v3.5: stage 04 protocol gaps. Backward-compat full."""
    _bump_version_only(workspace_root, "3.5.0")


def migrate_3_5_to_3_6(workspace_root: Path, project_root: Path) -> None:
    """v3.5 → v3.6: preview loop frontend. Opt-in profile-based."""
    _bump_version_only(workspace_root, "3.6.0")


def migrate_3_7_0_to_3_7_2(workspace_root: Path, project_root: Path) -> None:
    """v3.7.0 → v3.7.2: saída A/C cleanup + recovery wizard novo detector.

    Sem schema change em L0 — apenas runtime/handoff behavior. v3.7.1
    foi colapsada em v3.7.2 (changelog: intermediária mergeada). Bump-only.
    """
    _bump_version_only(workspace_root, "3.7.2")


def migrate_3_7_2_to_3_8_0(workspace_root: Path, project_root: Path) -> None:
    """v3.7.2 → v3.8.0: Forensic+ wave reviewer. Bump-only.

    Sem schema change em L0 — campos novos em task-md frontmatter são opcionais
    com default tolerante a ausência. Workspaces existentes são compatíveis
    sem mutação destrutiva.
    """
    _bump_version_only(workspace_root, "3.8.0")


def migrate_3_8_0_to_3_9_0(workspace_root: Path, project_root: Path) -> None:
    """v3.8.0 → v3.9.0: Layered QA loop (L2 forensic+ extended + L3 critic +
    lead-resolution tier).

    Bump-only. Sem schema change destrutivo em L0/L1:
    - Status enum ganha LEAD_RESOLUTION_IN_PROGRESS (additive); workspaces
      existentes mid-stage 04 NÃO ativam novo flow até terminarem stage atual.
    - Akita 15-itens drop em 4-block-contract-template.md afeta apenas tasks
      novas; task reports legacy (com bloco Auto-QA Akita) parseiam OK
      (campo é tolerante a ausência OR presença).
    - Novos checks forensic+ 5/6/7 só ativam em wave novas; não re-auditam
      tasks pre-bump.
    - pick-model fields (model_recommended_writer/critic) são opcionais em
      AGENT-BRIEF — workspaces existentes continuam sem.
    """
    _bump_version_only(workspace_root, "3.9.0")


STEP_FUNCTIONS = {
    "3.3.0->3.4.0": migrate_3_3_to_3_4,
    "3.4.0->3.5.0": migrate_3_4_to_3_5,
    "3.5.0->3.6.0": migrate_3_5_to_3_6,
    "3.6.0->3.7.0": migrate_3_6_to_3_7,
    "3.7.0->3.7.2": migrate_3_7_0_to_3_7_2,
    "3.7.2->3.8.0": migrate_3_7_2_to_3_8_0,
    "3.8.0->3.9.0": migrate_3_8_0_to_3_9_0,
}


# ============================================================================
# Orquestrador
# ============================================================================

def migrate(
    workspace_root: Path,
    *,
    project_root: Path | None = None,
    target: str = CURRENT_SKILL_VERSION,
    dry_run: bool = False,
    do_backup: bool = True,
) -> dict:
    """Aplica migration encadeada do workspace.

    Returns: dict com `from_version`, `to_version`, `steps_planned`,
    `steps_applied`, `backup_path`, `trigger_mode`.
    """
    if project_root is None:
        project_root = workspace_root.parent.parent
    current = detect_workspace_version(workspace_root)
    if current is None:
        raise MigrationError(
            f"workspace {workspace_root} sem icm_skill_version em L0 "
            "(possivelmente beta1/beta2 unsupported)"
        )
    plan = plan_migration(current, target)
    trigger = detect_trigger_mode(workspace_root)
    result: dict = {
        "from_version": current,
        "to_version": target,
        "steps_planned": plan,
        "steps_applied": [],
        "trigger_mode": trigger,
        "backup_path": None,
        "dry_run": dry_run,
    }
    if dry_run or not plan:
        return result

    if do_backup:
        result["backup_path"] = str(backup_workspace(workspace_root))

    for step in plan:
        fn = STEP_FUNCTIONS.get(step)
        if fn is None:
            raise MigrationError(f"step desconhecido: {step}")
        fn(workspace_root, project_root)
        result["steps_applied"].append(step)
    return result


# ============================================================================
# CLI
# ============================================================================

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="migrate-workspace.py")
    p.add_argument("--workspace-root", type=Path, required=True)
    p.add_argument("--project-root", type=Path, default=None,
                   help="default: workspace_root.parent.parent")
    p.add_argument("--target", default=CURRENT_SKILL_VERSION)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-backup", action="store_true")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    import json as _json
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        result = migrate(
            args.workspace_root.resolve(),
            project_root=args.project_root.resolve() if args.project_root else None,
            target=args.target,
            dry_run=args.dry_run,
            do_backup=not args.no_backup,
        )
    except MigrationError as exc:
        print(f"MigrationError: {exc}", file=sys.stderr)
        return 1
    print(_json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
