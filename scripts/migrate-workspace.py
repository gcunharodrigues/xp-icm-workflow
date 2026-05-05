"""Migrate workspace — chained migration orchestrator (v3.8.0).

Detects current version via L0 frontmatter `icm_skill_version` and applies
the migration sequence up to `--target` (default: current SKILL_VERSION).

Supported versions: v3.3.0+. Beta1/beta2 explicitly unsupported
(batched/legacy pre-3.3 state with no automatable path).

Trigger:
- `auto-prompt`: workspace status ∈ {COMPLETED, COMPLETED_AWAITING_HUMAN}
  → bootstrap/stage 08 session should offer migration.
- `warning-only`: status IN_PROGRESS → do not interrupt work mid-stage,
  only log warning.

Automatic backup at <project_root>/.icm-migration-backup/<timestamp>/
before each step. Idempotent: re-running does not duplicate state.

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
# Constants
# ============================================================================

CURRENT_SKILL_VERSION = "3.12.1"
FLOOR_VERSION = "3.3.0"

# Supported version sequence. Migration steps are consecutive pairs.
# v3.7.1 collapsed into v3.7.2 (changelog: intermediate merged). Direct
# migration 3.7.0→3.7.2 covers both — no schema change in L0.
SUPPORTED_VERSIONS: tuple[str, ...] = (
    "3.3.0",
    "3.4.0",
    "3.5.0",
    "3.6.0",
    "3.7.0",
    "3.7.2",
    "3.8.0",
    "3.9.0",
    "3.10.0",
    "3.11.0",
    "3.12.0",
    "3.12.1",
)


class MigrationError(Exception):
    """Migration error (unsupported version, conflict, IO)."""


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
    """Reads L0 (`<ws>/CLAUDE.md`) and extracts icm_skill_version from frontmatter.

    Returns semver string or None if L0 absent / field missing.
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
    """Decides trigger: auto-prompt vs warning-only.

    Status COMPLETED/AWAITING → auto-prompt (safe to interrupt).
    IN_PROGRESS → warning-only (do not interrupt active work).
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
    """Returns list of steps `<a>-><b>` ordered from → to.

    Raises MigrationError if from < FLOOR_VERSION.
    """
    if from_version not in SUPPORTED_VERSIONS:
        raise MigrationError(
            f"version {from_version} below floor {FLOOR_VERSION} "
            f"(supported: {SUPPORTED_VERSIONS}). "
            "Manual migration required for pre-3.3.0 workspaces."
        )
    if to_version not in SUPPORTED_VERSIONS:
        raise MigrationError(
            f"target {to_version} unknown (supported: {SUPPORTED_VERSIONS})"
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
    """Copies workspace to `<project_root>/.icm-migration-backup/<ts>/<ws>/`.

    Does not copy `_state/` (local-only) or `output/` (heavy artifacts — git
    has the version).
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
    - Create _state/ dir
    - Migrate .icm-main/.dev-server.pid → runtime-registry (if PID alive)
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
            # Idempotent: only register if no entry with same pid exists yet
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


# No-op steps for intermediate versions (changes were backward-compat).
# Each step only bumps L0 version to the next version in the sequence.
# v3.4/v3.5/v3.6 workspaces already have compatible schemas; no data migrates.

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
    """v3.3 → v3.4: cross-branch worktree model. Substantive migration
    in scripts/migrate-v3.3-to-v3.4.py (pre-existing). Here only version
    bump if already migrated manually."""
    _bump_version_only(workspace_root, "3.4.0")


def migrate_3_4_to_3_5(workspace_root: Path, project_root: Path) -> None:
    """v3.4 → v3.5: stage 04 protocol gaps. Fully backward-compat."""
    _bump_version_only(workspace_root, "3.5.0")


def migrate_3_5_to_3_6(workspace_root: Path, project_root: Path) -> None:
    """v3.5 → v3.6: preview loop frontend. Opt-in profile-based."""
    _bump_version_only(workspace_root, "3.6.0")


def migrate_3_7_0_to_3_7_2(workspace_root: Path, project_root: Path) -> None:
    """v3.7.0 → v3.7.2: output A/C cleanup + recovery wizard new detector.

    No schema change in L0 — only runtime/handoff behavior. v3.7.1
    was collapsed into v3.7.2 (changelog: intermediate merged). Bump-only.
    """
    _bump_version_only(workspace_root, "3.7.2")


def migrate_3_7_2_to_3_8_0(workspace_root: Path, project_root: Path) -> None:
    """v3.7.2 → v3.8.0: Forensic+ wave reviewer. Bump-only.

    No schema change in L0 — new fields in task-md frontmatter are optional
    with absence-tolerant defaults. Existing workspaces are compatible
    without destructive mutation.
    """
    _bump_version_only(workspace_root, "3.8.0")


def migrate_3_8_0_to_3_9_0(workspace_root: Path, project_root: Path) -> None:
    """v3.8.0 → v3.9.0: Layered QA loop (L2 forensic+ extended + L3 critic +
    lead-resolution tier).

    Bump-only. No destructive schema change in L0/L1:
    - Status enum gains LEAD_RESOLUTION_IN_PROGRESS (additive); existing
      workspaces mid-stage 04 do NOT activate new flow until current stage ends.
    - Akita 15-item drop in 4-block-contract-template.md affects only new tasks;
      legacy task reports (with Auto-QA Akita block) parse OK
      (field is tolerant of absence OR presence).
    - New forensic+ checks 5/6/7 only activate on new waves; do not re-audit
      pre-bump tasks.
    - pick-model fields (model_recommended_writer/critic) are optional in
      AGENT-BRIEF — existing workspaces continue without them.
    """
    _bump_version_only(workspace_root, "3.9.0")


def migrate_3_9_0_to_3_10_0(workspace_root: Path, project_root: Path) -> None:
    """v3.9.0 → v3.10.0: E2E coverage reinforcement.

    Bump-only. No destructive schema change in L0/L1:
    - 4-block schema +Requires E2E update optional field; legacy tasks without
      the field are treated as False (Check 8 skip).
    - Forensic+ Check 8 only activates on new waves; does not re-audit pre-bump tasks.
    - L4 wave gate e2e (step 11b) only activates on new waves tier dev/prod;
      workspaces mid-stage 04 keep v3.9.0 flow until current wave ends.
    - Stage 05 audit 4.7 only activates on new verification runs; legacy
      reports are not re-audited.
    - profile-effective.yaml gains e2e section (optional); existing workspaces
      continue with defaults hardcoded in wave-planner-script.
    """
    _bump_version_only(workspace_root, "3.10.0")


def migrate_3_10_0_to_3_11_0(workspace_root: Path, project_root: Path) -> None:
    """v3.10.0 -> v3.11.0: Full migration to en-US.

    Bump-only. No destructive schema change in L0/L1:
    - All user-facing text (templates, reference docs, scripts, SKILL.md)
      translated from pt-BR to en-US. No behavioral or schema change.
    - Optionally injects `language: en-US` into L1 frontmatter if the
      field is absent (additive, non-breaking).
    - Existing workspaces continue without interruption; the language
      field is advisory only.
    """
    _bump_version_only(workspace_root, "3.11.0")

    # Inject `language: en-US` into L1 frontmatter if absent (advisory).
    l1 = workspace_root / "CONTEXT.md"
    if l1.is_file():
        text = l1.read_text(encoding="utf-8")
        if "language:" not in text:
            # Insert after the opening `---` line of the frontmatter.
            text = text.replace("---\n", "---\nlanguage: en-US\n", 1)
            l1.write_text(text, encoding="utf-8")


def migrate_3_12_0_to_3_12_1(workspace_root: Path, project_root: Path) -> None:
    """v3.12.0 -> v3.12.1: Bump-only (no workspace changes needed).

    Fixes in v3.12.1 are backward-compatible: wave-planner now accepts both
    "none" and "nenhum" as empty-dependency sentinels; handoff parser is
    comma-safe; parenthetical notes in deps are stripped. No workspace
    file format changed.
    """
    _bump_version_only(workspace_root, "3.12.1")


def migrate_3_11_0_to_3_12_0(workspace_root: Path, project_root: Path) -> None:
    """v3.11.0 -> v3.12.0: Zero pt-BR (full migration).

    Rewrites plan.md 4-block headers from pt-BR to en-US in the workspace.
    Rewrites L1 history stop_point_id `feedback_ambiguous` -> `ambiguous_feedback`
    (en-US adj-noun word order, introduced in v3.11.0 but originally pt-BR-derived).
    Bumps L0 icm_skill_version.

    Idempotent: running on an already-migrated workspace is a no-op.
    """
    _bump_version_only(workspace_root, "3.12.0")

    # Rewrite plan.md 4-block headers in all stages.
    # i18n-allow: these are the pt-BR strings we are REPLACING (migration source literals)
    _4BLOCK_REPLACEMENTS: list[tuple[str, str]] = [
        ("### O QUE NÃO FUNCIONOU", "### WHAT DID NOT WORK"),  # i18n-allow: migration source literal
        ("### O QUE FUNCIONOU", "### WHAT WORKED"),
        ("### QUAL DOR PERSISTE", "### WHAT PAIN PERSISTS"),
        ("### QUE LIÇÃO TIRAR", "### WHAT LESSON TO DRAW"),
        ("### O QUE", "### WHAT"),
        ("### COMO", "### HOW"),
        ("### NÃO QUERO", "### OUT OF SCOPE"),  # i18n-allow: migration source literal
        ("### VALIDAÇÃO", "### VALIDATION"),
        ("### VALIDAÇAO", "### VALIDATION"),
        ("### ADRs aplicáveis", "### Applicable ADRs"),
    ]
    for plan_md in workspace_root.rglob("plan.md"):
        try:
            text = plan_md.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        new_text = text
        for old, new in _4BLOCK_REPLACEMENTS:
            new_text = new_text.replace(old, new)
        if new_text != text:
            plan_md.write_text(new_text, encoding="utf-8")

    # Rewrite L1 history stop_point_id: feedback_ambiguous (old pt-BR-derived ID).
    # v3.11.0 ADR listed it as "ambiguous_feedback" but some workspaces may have
    # the old form in their history.  Rewrite for consistency.
    l1 = workspace_root / "CONTEXT.md"
    if l1.is_file():
        try:
            text = l1.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return
        new_text = text.replace(
            "stop_point_id: feedback_ambiguous",
            "stop_point_id: ambiguous_feedback",
        )
        if new_text != text:
            l1.write_text(new_text, encoding="utf-8")


STEP_FUNCTIONS = {
    "3.3.0->3.4.0": migrate_3_3_to_3_4,
    "3.4.0->3.5.0": migrate_3_4_to_3_5,
    "3.5.0->3.6.0": migrate_3_5_to_3_6,
    "3.6.0->3.7.0": migrate_3_6_to_3_7,
    "3.7.0->3.7.2": migrate_3_7_0_to_3_7_2,
    "3.7.2->3.8.0": migrate_3_7_2_to_3_8_0,
    "3.8.0->3.9.0": migrate_3_8_0_to_3_9_0,
    "3.9.0->3.10.0": migrate_3_9_0_to_3_10_0,
    "3.10.0->3.11.0": migrate_3_10_0_to_3_11_0,
    "3.11.0->3.12.0": migrate_3_11_0_to_3_12_0,
    "3.12.0->3.12.1": migrate_3_12_0_to_3_12_1,
}


# ============================================================================
# Orchestrator
# ============================================================================

def migrate(
    workspace_root: Path,
    *,
    project_root: Path | None = None,
    target: str = CURRENT_SKILL_VERSION,
    dry_run: bool = False,
    do_backup: bool = True,
) -> dict:
    """Applies chained migration to the workspace.

    Returns: dict with `from_version`, `to_version`, `steps_planned`,
    `steps_applied`, `backup_path`, `trigger_mode`.
    """
    if project_root is None:
        project_root = workspace_root.parent.parent
    current = detect_workspace_version(workspace_root)
    if current is None:
        raise MigrationError(
            f"workspace {workspace_root} missing icm_skill_version in L0 "
            "(possibly beta1/beta2 unsupported)"
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
            raise MigrationError(f"unknown step: {step}")
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
                   help="default: workspace_root.parent.parent (two levels up)")
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
