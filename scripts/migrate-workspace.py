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
    """v3.12.0 → v3.12.1: Full workspace migration.

    Automated fixes (40+ surgical replacements):
    - L0 CLAUDE.md: stop count, script path, stop ID.
    - _config/stop-points.md: phantom fix, count fix, new stop points.
    - _config/xp-conventions.md: branch placeholders, TDD tier descriptions.
    - Stage 04: 7→8 checks, 12→14-step, REFACTOR, cross-task coherence,
      lead override, merge conflict, blocked output, references header,
      critic invocation (render-critic-prompt.py).
    - Stage 08: stop point #13→#15, tech debt decision tree.
    - Stages 00/01/02/03/05: script-cli-reference cross-ref.
    - Re-copies all 32 reference docs to _references/runtime/.
    - Prints post-migration LLM verification checklist.

    Idempotent: safe to run on already-migrated workspace.
    """

    _bump_version_only(workspace_root, "3.12.1")
    skill_root = Path(__file__).resolve().parent.parent
    skill_dir = str(skill_root).replace("\\", "/")
    changed: list[str] = []

    def _apply(path: Path, replacements: list[tuple[str, str]], label: str) -> None:
        """Apply surgical text replacements to a file if it exists."""
        if not path.is_file():
            return
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return
        applied = False
        for old, new in replacements:
            if old in text:
                text = text.replace(old, new)
                applied = True
        if applied:
            path.write_text(text, encoding="utf-8")
            changed.append(f"  - {label}")

    # ---- 1. Re-copy reference docs ----
    refs_src = skill_root / "references"
    runtime_dst = workspace_root / "_references" / "runtime"
    copied = 0
    if refs_src.is_dir() and runtime_dst.exists():
        _RUNTIME_REFS: tuple[str, ...] = (
            "subagent-protocol.md", "wave-planner-algorithm.md",
            "state-machine-schema.md", "recovery-wizard.md",
            "stop-points-canonical.md", "4-block-contract-template.md",
            "feedback-intake-stage08.md", "session-handoff-protocol.md",
            "project-root-claude-md.md", "context-format.md",
            "agent-brief-template.md", "adr-format.md",
            "diagnose-protocol.md", "task-types-hitl-afk.md",
            "triage-state-machine.md", "out-of-scope-kb.md",
            "design-it-twice.md", "deep-modules.md", "design-system.md",
            "forensic-plus-protocol.md", "critic-protocol.md",
            "lead-resolution-protocol.md", "mocking-guidelines.md",
            "preview-loop-protocol.md", "runtime-cleanup-protocol.md",
            "e2e-coverage-protocol.md", "ci-rollback-protocol.md",
            "conflict-resolution-protocol.md", "icm-cleanup-protocol.md",
            "script-cli-reference.md", "wave-execution-protocol.md",
            "worktree-model.md",
        )
        for fname in _RUNTIME_REFS:
            src = refs_src / fname
            dst = runtime_dst / fname
            if src.is_file():
                try:
                    dst.write_text(src.read_text(encoding="utf-8"))
                    copied += 1
                except (UnicodeDecodeError, OSError):
                    pass
    if copied:
        changed.append(f"  - {copied} reference docs re-copied to _references/runtime/")

    # ---- 2. L0 CLAUDE.md — text corrections ----
    _apply(workspace_root / "CLAUDE.md", [
        ("12 canonical stop points", "15 canonical stop points"),
        ("via scripts/runtime-status.py", f"via {skill_dir}/scripts/runtime-status.py"),
        ("runtime_cleanup_failed (#13)", "runtime_cleanup_failed (#15)"),
        ("_references/runtime/worktree-model.md",
         f"{{PROJECT_ROOT}}/workspaces/{workspace_root.name}/_references/runtime/worktree-model.md"),
    ], "L0 CLAUDE.md: 4 text corrections")

    # ---- 3. _config/stop-points.md — comprehensive fix ----
    _apply(workspace_root / "_config" / "stop-points.md", [
        ("13 stop points + thresholds", "15 stop points + thresholds"),
        ("Canonical list of 13 stop points", "Canonical list of 15 stop points"),
        ("## 1. Canonical list (13 items)", "## 1. Canonical list (15 items)"),
        # Phantom → correct (LONGER match first)
        ("`wave_branch_missing` — Missing wave branch",
         "`workspace_corrupt` — ICM workspace corrupted"),
        ("`wave_branch_missing`", "`workspace_corrupt`"),
        # Renumber runtime_cleanup_failed if it got shifted into #13 slot by old template
        ("### 13. `runtime_cleanup_failed`",
         "### 15. `runtime_cleanup_failed`"),
        # Applicability table
        ("| 00 recon | 11 (`wave_branch_missing`)",
         "| 00 recon | 11 (`workspace_corrupt`)"),
    ], "_config/stop-points.md: 7 fixes")

    # ---- 4. _config/xp-conventions.md — branch + TDD ----
    _apply(workspace_root / "_config" / "xp-conventions.md", [
        # Branch placeholders
        ("`wave-{{WORKSPACE}}-<N>/<task>`", "`wave-{{WORKSPACE_NUM}}-<N>/<task-slug>`"),
        ("`wave-{{WORKSPACE}}-<N>/<task>` for code",
         "`wave-{{WORKSPACE_NUM}}-<N>/<task-slug>` for code"),
        # TDD tier descriptions
        ("- **experimental:** TDD optional",
         "- **experimental:** TDD optional (skip allowed; no penalty in verification)"),
        ("- **tool:** TDD recommended",
         "- **tool:** TDD mandatory when task touches >1 module or public API; optional for single-file/internal tasks"),
        ("- **development:** TDD mandatory",
         "- **development:** TDD mandatory (all tasks; stage 05 verification enforces)"),
        ("- **production:** TDD mandatory + security gate",
         "- **production:** TDD mandatory + security gate (all tasks; stage 05 + stage 06 enforce)"),
    ], "_config/xp-conventions.md: branch + TDD fixes")

    # ---- 5. Stage 04 — comprehensive fixes ----
    _STAGE04_CRITIC_OLD = (
        "       ```python\n"
        "       Agent(\n"
        '           description="L3 critic ortogonal task <slug>",\n'
        '           subagent_type="general-purpose",\n'
        "           model=<critic_model_from_pick_model_py>,  # = TIER_CEILING[tier]\n"
        "           prompt=render_critic_prompt(<slug>, <wave>),  # templates/critic-prompt.md\n"
        "       )\n"
        "       ```"
    )
    _STAGE04_CRITIC_NEW = (
        "       1. **Render critic prompt** (automated — script captures diff + test output):\n"
        "          ```bash\n"
        f"          python {skill_dir}/scripts/render-critic-prompt.py \\\n"
        "              --task-slug <slug> --wave <N> --tier <TIER> \\\n"
        "              --workspace-num {{WORKSPACE_NUM}} --base-branch {{BASE_BRANCH}} \\\n"
        "              --plan {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/02_design/output/plan.md \\\n"
        "              --critic-model <critic_model_from_pick_model_py> \\\n"
        "              --output output/wave-<N>/task-<slug>-critic-prompt-round<R>.md\n"
        "          ```\n"
        "       2. **Spawn critic** with the rendered prompt:\n"
        "          ```python\n"
        "          Agent(\n"
        '              description="L3 critic task <slug> wave <N>",\n'
        '              subagent_type="general-purpose",\n'
        "              model=<critic_model_from_pick_model_py>,  # = TIER_CEILING[tier]\n"
        '              prompt=Read("output/wave-<N>/task-<slug>-critic-prompt-round<R>.md"),\n'
        "          )\n"
        "          ```"
    )
    _apply(workspace_root / "stages" / "04_implementation_waves" / "CONTEXT.md", [
        # Count + branch fixes
        ("7 deterministic checks", "8 deterministic checks"),
        ("12-step pipeline", "14-step pipeline"),
        ("7 checks (extended v3.9.0)", "8 checks (extended v3.10.0)"),
        ("7 checks extended (v3.9.0)", "8 checks extended (v3.10.0)"),
        ("wave-{{WORKSPACE}}-<N>/<task-slug>", "wave-{{WORKSPACE_NUM}}-<N>/<task-slug>"),
        # REFACTOR
        ("REFACTOR → optional, only if obvious complexity reduction",
         "REFACTOR → mandatory after every GREEN. Skip ONLY when all three Dirt Check questions (duplication, naming, function/file size) answer NO."),
        # Cross-task coherence
        ("optional v3.9.0.",
         "mandatory v3.12.1. Skip only when tier < production OR all tasks in wave touch disjoint file sets with no shared APIs."),
        # Lead override
        ("Lead may override (records choice in",
         "Lead may override ONLY with explicit justification recorded in"),
        # Merge conflict
        ("Merge conflict → `references/conflict-resolution-protocol.md`.",
         "**Merge conflict → STOP — NEVER resolve autonomously.** Merge code is high risk. Follow `references/conflict-resolution-protocol.md`: human must decide (rebase/abort/manual resolution). Autonomous merge conflict resolution = `BLOCKED_ERROR`."),
        # Blocked output
        ("blocked.md` — optional, created when subagent triggers",
         "blocked.md` — conditional: MUST be written when subagent triggers"),
        # References header
        ("## v3.3.0 references applicable to this stage",
         "## References applicable to this stage (v3.3.0+, consolidated through v3.12.1)"),
        # Critic invocation (longest match last)
        (_STAGE04_CRITIC_OLD, _STAGE04_CRITIC_NEW),
    ], "stage 04: comprehensive fixes")

    # ---- 6. Stage 08 — stop points + tech debt + script ref ----
    _apply(workspace_root / "stages" / "08_feedback_intake" / "CONTEXT.md", [
        ("#13 `runtime_cleanup_failed`", "#15 `runtime_cleanup_failed`"),
        ("stop point #13 `runtime_cleanup_failed`", "stop point #15 `runtime_cleanup_failed`"),
        ("conditional: optional — sample", "conditional: sample"),
        # Tech debt decision tree
        ("**(v3.7.0) Append tech debt during intake — optional:** if free-form feedback reveals durable technical debt (not a lesson), append to",
         "**(v3.7.0) Append tech debt during intake — conditional, mandatory when debt is cited.** If free-form feedback reveals durable technical debt (not a lesson), append to"),
    ], "stage 08: stop points + tech debt + script ref")

    # ---- 7. Stages 00/01/02/03/05 — script-cli-reference cross-ref ----
    for stage_num in ("00", "01", "02", "03", "05"):
        stage_names = {
            "00": "00_recon", "01": "01_discovery", "02": "02_design",
            "03": "03_wave_planner", "05": "05_verification",
        }
        _apply(
            workspace_root / "stages" / stage_names[stage_num] / "CONTEXT.md",
            [(
                "   - L4-kickoff YAML frontmatter per schema in `references/session-handoff-protocol.md`",
                "   - **Script CLI reference:** `references/script-cli-reference.md` — exact format for `--prev-outputs`, `--pending`, and all other flags.\n"
                "   - L4-kickoff YAML frontmatter per schema in `references/session-handoff-protocol.md`",
            )],
            f"stage {stage_num}: script-cli-reference cross-ref",
        )

    # ---- 8. Print LLM verification checklist ----
    print("")
    print("=" * 60)
    print(f" Migration v3.12.0 → v3.12.1: {workspace_root.name}")
    print("=" * 60)
    print("")
    if changed:
        print("Automated fixes applied:")
        for c in changed:
            print(c)
    else:
        print("Already at v3.12.1 — no changes needed.")
        print("")
        return
    print("")
    print("MANUAL VERIFICATION — LLM must complete these items:")
    print("")
    print("  1. _config/stop-points.md:")
    print("     Surgical fix applied, but detail sections for #13 ambiguous_feedback")
    print("     and #14 design_system_cascade are MISSING. Add them manually:")
    print(f"     Source: {skill_dir}/references/stop-points-canonical.md")
    print("     Template: {skill_dir}/templates/_config/stop-points.md")
    print("     Sections needed: ### 13. ambiguous_feedback, ### 14. design_system_cascade")
    print("")
    print("  2. stages/04_implementation_waves/CONTEXT.md:")
    print("     Surgical fixes applied for most changes. Verify these structural items")
    print("     (not automatable — session-specific content may exist):")
    print("     - 'Common protocol violations' table exists (6 rows)")
    print("     - Pre-flight checklist has 5 items (MANDATORY — do NOT skip)")
    print("     - Agent() spawn includes model: <writer_model> parameter")
    print("     - B4 VOID_TASK block shows Reason/Evidence/Action proposed schema")
    print("     - Step 8d --files-touched has source annotation")
    print("     If ANY are missing: copy from current skill template:")
    print(f"     {skill_dir}/templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl")
    print("")
    print("  3. stages/08_feedback_intake/CONTEXT.md:")
    print("     Tech debt now has decision tree. Verify 5 questions present.")
    print("     If missing: copy from current template.")
    print("")
    print("  4. stages/00,01,02,03,05 _kickoff.md files:")
    print("     If any _kickoff.md has Portuguese headers 'Estado entregue' or")
    print("     'O que esta sessao deve fazer', translate to 'State delivered by")
    print("     previous session' / 'What this session must do'.")
    print("")
    print("  5. Run state validation:")
    print(f"     python {skill_dir}/scripts/validate_state.py \\")
    print(f"         --context-md {workspace_root}/CONTEXT.md")
    print("")
    print(f"  6. Commit: workspace {workspace_root.name.split('-', 1)[0]}: migrate v3.12.0→v3.12.1")
    print("=" * 60)


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
