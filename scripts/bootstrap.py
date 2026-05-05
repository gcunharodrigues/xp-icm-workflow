"""Python backend for the one-shot bootstrap of the xp-icm-workflow skill.

Creates an ICM workspace inside a project_root: dedicated branch, stage
scaffold, L0/L1 with filled placeholders, effective profile + hash, project
index, updated .gitignore, installed pre-commit hook, atomic commits.

Pure functions (templating, validation, index/.gitignore manipulation) are
tested in tests/unit/test_bootstrap.py. The end-to-end flow is tested in
tests/integration/test_bootstrap.bats (CI-only Ubuntu).

CLI: the main path is via the scripts/bootstrap.sh wrapper. This module
exposes `main()` for direct invocation as a debug entry point.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

# ============================================================================
# Constants
# ============================================================================

SKILL_VERSION = "3.12.0"  # template prepends `v`

SLUG_RE = re.compile(r"^[a-z0-9-]+$")
# Bootstrap auto-prefixes NNN- to the slug. A slug that already starts with NNN-
# produces a duplicate ID like "001-001-foo". Explicit reject with hint for the user.
NNN_PREFIX_RE = re.compile(r"^\d{3}-")
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_][A-Z0-9_]*)\}\}")
INDEX_ROW_RE = re.compile(
    r"^\|\s*(\d{3})\s*\|\s*([a-z0-9-]+)\s*\|"
)

STAGES: tuple[str, ...] = (
    "00_recon",
    "01_discovery",
    "02_design",
    "03_wave_planner",
    "04_implementation_waves",
    "05_verification",
    "06_review",
    "07_merge",
    "08_feedback_intake",
)

STAGE_NAMES: dict[int, str] = {
    0: "recon",
    1: "discovery",
    2: "design",
    3: "wave_planner",
    4: "implementation_waves",
    5: "verification",
    6: "review",
    7: "merge",
    8: "feedback_intake",
}

GITIGNORE_LINES: tuple[str, ...] = (
    ".icm-profile.local.yaml",
    ".icm-main/",  # v3.4.0 — linked worktree from base branch (cross-branch model)
    ".icm-chrome-profile/",  # v3.6.0 — preview loop CDP profile dir
    ".icm/spawn-pending.json",  # v3.7.0 — handoff stage 08 exit C → bootstrap
    "workspaces/*/_state/",  # v3.7.0 — local-only runtime registry
    "**/coverage/",  # v3.7.0 — untracked artifact (jest, playwright, etc)
    "**/coverage.json",  # v3.7.0 — coverage summary
    "**/tsconfig.tsbuildinfo",  # v3.7.0 — TS incremental build state
    "**/.vite/",  # v3.7.0 — vite cache
    "__pycache__/",
    ".pytest_cache/",
    ".coverage",
)


# ============================================================================
# Package manager detection (v3.6.0 preview loop)
# ============================================================================

# Priority: bun > pnpm > yarn > npm. Most specific lockfile wins.
# Lookup tuple is order-sensitive.
PACKAGE_MANAGERS: tuple[tuple[str, str, str], ...] = (
    ("bun.lockb", "bun", "bun dev"),
    ("bun.lock", "bun", "bun dev"),
    ("pnpm-lock.yaml", "pnpm", "pnpm dev"),
    ("yarn.lock", "yarn", "yarn dev"),
    ("package-lock.json", "npm", "npm run dev"),
)


def detect_package_manager(project_root: Path) -> tuple[str, str] | None:
    """Detects package manager by lockfile present in project_root.

    Returns:
        (pm_name, dev_cmd) or None if no lockfile found.
        E.g.: ("pnpm", "pnpm dev")
    """
    for lockfile, pm, dev_cmd in PACKAGE_MANAGERS:
        if (project_root / lockfile).is_file():
            return pm, dev_cmd
    return None


def yaml_safe_list(items: list[str]) -> str:
    """Render list[str] as YAML flow sequence for frontmatter: ``[item1, item2]``."""
    if not items:
        return "[]"
    return "[" + ", ".join(f'"{i}"' for i in items) + "]"

INDEX_HEADER = (
    "# Workspaces index\n"
    "\n"
    "Append-only index of workspaces created by the xp-icm-workflow skill\n"
    "bootstrap. NEVER edit existing lines manually.\n"
    "\n"
    "| ID | Slug | Profile/Tier | Created at | Status |\n"
    "|---|---|---|---|---|\n"
)


class BootstrapError(Exception):
    """Bootstrap error (validation, IO, git, runtime)."""


# ============================================================================
# Spawn-pending handoff (v3.7.0 — stage 08 exit C → bootstrap)
# ============================================================================

SPAWN_PENDING_PATH = ".icm/spawn-pending.json"

SPAWN_PENDING_REQUIRED_FIELDS: tuple[str, ...] = (
    "spawn_from",
    "intake_report_path",
    "intake_report_branch",
    "proposed_workspace_name",
    "proposed_profile",
    "proposed_tier",
    "intake_commit_sha",
    "agent_brief",
    "created_at",
)


def detect_spawn_pending(project_root: Path) -> dict | None:
    """Reads `<project_root>/.icm/spawn-pending.json` and validates schema.

    Returns parsed dict if valid, None if file is absent.
    Raises BootstrapError if JSON is invalid or schema is incomplete.
    """
    pending_path = project_root / SPAWN_PENDING_PATH
    if not pending_path.is_file():
        return None
    try:
        text = pending_path.read_text(encoding="utf-8")
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BootstrapError(
            f"spawn-pending.json invalid: {pending_path} ({exc})"
        ) from exc
    if not isinstance(data, dict):
        raise BootstrapError(
            f"spawn-pending.json expected dict, got {type(data).__name__}"
        )
    missing = [f for f in SPAWN_PENDING_REQUIRED_FIELDS if f not in data]
    if missing:
        raise BootstrapError(
            f"spawn-pending.json missing required fields: {missing}"
        )
    return data


def resolve_spawn_source(
    project_root: Path,
    spawn_from_arg: str | None,
) -> dict:
    """Resolves the spawn information source (file vs CLI arg).

    Returns dict with key `source` ∈ {"file", "arg", "conflict", "none"}:
    - "file": only file present, or file+arg match → file wins.
    - "arg": only arg present. `spawn_from` populated.
    - "conflict": file+arg from different workspaces. Caller decides via
      human menu. Includes `file_value` + `arg_value` for UI.
    - "none": neither. Bootstrap follows normal flow.
    """
    pending = detect_spawn_pending(project_root)
    if pending is None and spawn_from_arg is None:
        return {"source": "none"}
    if pending is None:
        return {"source": "arg", "spawn_from": spawn_from_arg}
    if spawn_from_arg is None:
        return {"source": "file", "payload": pending,
                "spawn_from": pending["spawn_from"]}
    if pending["spawn_from"] == spawn_from_arg:
        return {"source": "file", "payload": pending,
                "spawn_from": pending["spawn_from"]}
    return {
        "source": "conflict",
        "file_value": pending["spawn_from"],
        "arg_value": spawn_from_arg,
        "payload": pending,
    }


def consume_spawn_pending(project_root: Path) -> None:
    """Removes `<project_root>/.icm/spawn-pending.json` after bootstrap.

    Idempotent — no-op if absent. Called AFTER new workspace is committed
    to avoid re-triggering on the next invocation.
    """
    pending = project_root / SPAWN_PENDING_PATH
    if pending.is_file():
        pending.unlink()


# ============================================================================
# Pure functions (tested in test_bootstrap.py)
# ============================================================================

def render_template(tpl_path: Path, vars: dict[str, str]) -> str:
    """Substitutes {{KEY}} -> vars[KEY] in template content.

    Raises BootstrapError if template is absent OR if any `{{X}}` remains unresolved.
    """
    if not tpl_path.exists():
        raise BootstrapError(f"template absent: {tpl_path}")

    content = tpl_path.read_text(encoding="utf-8")

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in vars:
            raise BootstrapError(
                f"unresolved placeholder: {{{{{key}}}}} in {tpl_path.name}"
            )
        return vars[key]

    rendered = PLACEHOLDER_RE.sub(_sub, content)

    # Sanity check (in case the substitution regex has gaps): no `{{X}}` should remain
    leftover = PLACEHOLDER_RE.search(rendered)
    if leftover:
        raise BootstrapError(
            f"unresolved placeholder: {leftover.group(0)} in {tpl_path.name}"
        )

    return rendered


def resolve_workspace_id(index_path: Path) -> int:
    """Reads `.index.md`, returns next NNN (= max(IDs) + 1, or 1 if empty)."""
    if not index_path.exists():
        return 1
    text = index_path.read_text(encoding="utf-8")
    if not text.strip():
        return 1
    max_id = 0
    for line in text.splitlines():
        match = INDEX_ROW_RE.match(line.strip())
        if match:
            id_int = int(match.group(1))
            if id_int > max_id:
                max_id = id_int
    return max_id + 1


def update_index(
    index_path: Path,
    *,
    workspace: str,
    profile: str,
    tier: str,
    created_at: str,
) -> None:
    """Appends a row to .index.md. Creates header if absent.

    `workspace` = "NNN-slug" (ID + slug separated by first hyphen).
    """
    nnn, _, slug = workspace.partition("-")
    row = f"| {nnn} | {slug} | {profile}/{tier} | {created_at} | active |\n"

    if not index_path.exists() or not index_path.read_text(encoding="utf-8").strip():
        index_path.write_text(INDEX_HEADER + row, encoding="utf-8")
        return

    current = index_path.read_text(encoding="utf-8")
    if not current.endswith("\n"):
        current += "\n"
    index_path.write_text(current + row, encoding="utf-8")


def update_gitignore(gitignore_path: Path, lines_to_add: list[str]) -> None:
    """Idempotent: adds only missing lines; preserves existing ones."""
    if gitignore_path.exists():
        existing = gitignore_path.read_text(encoding="utf-8")
    else:
        existing = ""

    existing_lines = {ln.strip() for ln in existing.splitlines() if ln.strip()}

    missing = [ln for ln in lines_to_add if ln.strip() not in existing_lines]
    if not missing:
        return

    new_content = existing
    if new_content and not new_content.endswith("\n"):
        new_content += "\n"
    new_content += "\n".join(missing) + "\n"
    gitignore_path.write_text(new_content, encoding="utf-8")


def validate_slug(slug: str) -> None:
    """Accepts kebab-case `^[a-z0-9-]+$`. Raises BootstrapError otherwise.

    Extra reject: slug starting with `NNN-` (3 digits + hyphen) — bootstrap
    already prefixes NNN, so slug `001-foo` would produce workspace `001-001-foo`.
    """
    if not slug:
        raise BootstrapError("slug cannot be empty")
    if NNN_PREFIX_RE.match(slug):
        raise BootstrapError(
            f"invalid slug: {slug!r} already has prefix NNN- "
            "(bootstrap auto-prefixes the ID). Use a bare slug without the NNN-, "
            f"e.g.: {slug.split('-', 1)[1] if '-' in slug else slug!r}"
        )
    if not SLUG_RE.match(slug):
        raise BootstrapError(
            f"invalid slug: {slug!r} (expected kebab-case [a-z0-9-]+, "
            "no uppercase/space/accent)"
        )


def parse_profile_merge_output(json_str: str) -> tuple[dict[str, Any], str]:
    """Parses JSON from profile-merge.py. Returns (effective_dict, hash_str)."""
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise BootstrapError(f"profile-merge output JSON invalid: {exc}") from exc

    if not isinstance(parsed, dict):
        raise BootstrapError("profile-merge output must be a dict at top level")

    if "effective" not in parsed:
        raise BootstrapError("profile-merge output missing key 'effective'")
    if "hash" not in parsed:
        raise BootstrapError("profile-merge output missing key 'hash'")

    effective = parsed["effective"]
    if not isinstance(effective, dict):
        raise BootstrapError("'effective' must be a dict")

    h = parsed["hash"]
    if not isinstance(h, str):
        raise BootstrapError("'hash' must be a string")

    return effective, h


# ============================================================================
# Stop points: placeholder derivation + custom block rendering
# ============================================================================

def derive_stop_point_placeholders(effective: dict[str, Any]) -> dict[str, str]:
    """Extracts dict[str, str] with TIER_PAID_MODE/TIER_PAID_THRESHOLD_BRL/
    TIER_OVER_ENG_MODE/TIER_PII_MODE from `stop_points_calibration` in the
    effective profile.

    Expected schema (from profile-merge.py):
        stop_points_calibration:
          item_5: {mode: warning|hard, limite_mensal_BRL: int}
          item_7: {mode: warning|hard}
          item_8: {mode: warning|hard|hard+DPO}

    Raises BootstrapError if required keys are absent.
    """
    cal = effective.get("stop_points_calibration")
    if not isinstance(cal, dict):
        raise BootstrapError(
            "effective profile missing 'stop_points_calibration' (expected dict)"
        )

    def _required(key: str, sub: str) -> Any:
        item = cal.get(key)
        if not isinstance(item, dict):
            raise BootstrapError(
                f"stop_points_calibration.{key} absent or not a dict"
            )
        if sub not in item:
            raise BootstrapError(
                f"stop_points_calibration.{key}.{sub} absent"
            )
        return item[sub]

    return {
        "TIER_PAID_MODE": str(_required("item_5", "mode")),
        "TIER_PAID_THRESHOLD_BRL": str(_required("item_5", "limite_mensal_BRL")),
        "TIER_OVER_ENG_MODE": str(_required("item_7", "mode")),
        "TIER_PII_MODE": str(_required("item_8", "mode")),
    }


def render_custom_stop_points_block(
    custom_stops: list[dict[str, Any]] | None,
    tier: str,
) -> str:
    """Renders a markdown block with custom stop points for the template.

    `custom_stops` follows the schema from `_config/profile-matrix.md` -> custom_stop_points:
        - id: str (non-empty)
          description: str (non-empty)
          threshold: dict[tier_name -> mode_str]

    If list is empty/None: returns "(no custom stop points declared by this workspace)".
    Otherwise: for each custom stop, a `### custom: <id>` section + description
    + threshold for the current tier (or "n/a" if tier has no entry in threshold).
    """
    if not custom_stops:
        return "(no custom stop points declared by this workspace)"

    lines: list[str] = []
    for sp in custom_stops:
        if not isinstance(sp, dict):
            raise BootstrapError(f"custom_stop_point invalid (not a dict): {sp!r}")
        sp_id = sp.get("id")
        sp_desc = sp.get("description")
        sp_thresh = sp.get("threshold") or {}
        if not sp_id or not sp_desc:
            raise BootstrapError(
                f"custom_stop_point requires non-empty 'id' and 'description': {sp!r}"
            )
        threshold_for_tier = sp_thresh.get(tier, "n/a") if isinstance(sp_thresh, dict) else "n/a"
        lines.append(f"### custom: {sp_id}")
        lines.append("")
        lines.append(str(sp_desc))
        lines.append("")
        lines.append(f"Threshold tier `{tier}`: `{threshold_for_tier}`")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ============================================================================
# Orchestration helpers (covered by bats integration)
# ============================================================================

def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_git(args: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Git wrapper with output capture and configurable check."""
    cmd = ["git", "-C", str(cwd), *args]
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def _run_profile_merge(
    skill_root: Path,
    profile: str,
    tier: str,
    override: Path | None,
) -> tuple[dict[str, Any], str]:
    """Invokes scripts/profile-merge.py via subprocess; parses output."""
    cmd = [
        sys.executable,
        str(skill_root / "scripts" / "profile-merge.py"),
        "--profile", profile,
        "--tier", tier,
    ]
    if override is not None:
        cmd.extend(["--override", str(override)])
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise BootstrapError(
            f"profile-merge failed (rc={result.returncode}): {result.stderr.strip()}"
        )
    return parse_profile_merge_output(result.stdout)


def _greenfield_init(project_root: Path) -> None:
    """git init -b main + .gitignore + initial commit in a new project.

    Hook not yet installed at this point, so --no-verify is not needed.
    """
    _run_git(["init", "-b", "main"], cwd=project_root)
    gi = project_root / ".gitignore"
    update_gitignore(gi, list(GITIGNORE_LINES))
    _run_git(["add", ".gitignore"], cwd=project_root)
    _run_git(["commit", "-m", "initial commit"], cwd=project_root)


def _capture_base_branch(project_root: Path) -> str:
    res = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=project_root)
    branch = res.stdout.strip()
    if not branch or branch == "HEAD":
        raise BootstrapError(
            f"could not detect base_branch in {project_root} "
            "(detached HEAD?)"
        )
    return branch


def _create_workspace_branch(project_root: Path, branch: str, base: str) -> None:
    _run_git(["checkout", "-b", branch, base], cwd=project_root)


def _ensure_base_branch_docs(project_root: Path) -> None:
    """Creates docs/decisions/, docs/lessons.md, docs/tech_debt.md in the base branch.

    Precondition: caller has the base branch checked out (before workspace branch
    is created). Idempotent: skipped if already exists.

    v3.4.0: docs/ live ONLY in the base branch. Workspace branch has no direct
    visibility — uses `.icm-main/` worktree. See references/worktree-model.md.
    """
    decisions_dir = project_root / "docs" / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    (decisions_dir / ".keep").touch()  # ensures the directory is non-empty for git

    lessons = project_root / "docs" / "lessons.md"
    if not lessons.exists():
        lessons.write_text(
            "# Lessons Learned\n\nAppend-only log of lessons per workspace and iteration.\n\n",
            encoding="utf-8",
        )

    tech_debt = project_root / "docs" / "tech_debt.md"
    if not tech_debt.exists():
        tech_debt.write_text(
            "# Tech Debt\n\nAppend-only log of technical debt. Each item: source workspace+task, severity P2/P3, description.\n\n",
            encoding="utf-8",
        )

    # Commit docs scaffolding in base if there are changes
    res = _run_git(["status", "--porcelain", "docs/"], cwd=project_root, check=False)
    if res.stdout.strip():
        _run_git(["add", "docs/decisions/.keep", "docs/lessons.md", "docs/tech_debt.md"], cwd=project_root, check=False)
        _run_git(
            ["commit", "-m", "chore(icm): scaffold docs/ on base for ICM cross-branch model (v3.4.0)", "--no-verify"],
            cwd=project_root,
            check=False,
        )


def _setup_main_worktree(project_root: Path, base_branch: str) -> None:
    """Creates linked worktree `.icm-main/` checked out at base_branch (v3.4.0).

    Idempotent: skipped if already exists and is valid.

    Essential function of the cross-branch model v3.4.0: workspace branch does
    not have `docs/`, `src/`, etc. in the working tree, so agents read/write
    those paths via a permanent linked worktree.

    See references/worktree-model.md (canonical).
    """
    worktree_path = project_root / ".icm-main"
    if worktree_path.exists():
        # Validate that it is a genuine linked git worktree (not a subdir of project_root).
        # `git rev-parse --show-toplevel` returns the toplevel of the current worktree.
        # If worktree_path is a linked worktree: toplevel = worktree_path.
        # If it is just a subdir of project_root: toplevel = project_root (no match).
        try:
            res = _run_git(
                ["rev-parse", "--show-toplevel"],
                cwd=worktree_path,
                check=False,
            )
            if res.returncode == 0:
                toplevel = Path(res.stdout.strip()).resolve()
                if toplevel == worktree_path.resolve():
                    return  # idempotent — genuine linked worktree
        except Exception:
            pass
        # Exists but is not a linked worktree — human must resolve manually
        raise BootstrapError(
            f".icm-main/ exists in {project_root} but is not a valid git worktree. "
            "Remove it or run `git worktree repair` before bootstrapping."
        )

    _run_git(
        ["worktree", "add", str(worktree_path), base_branch],
        cwd=project_root,
    )


def _scaffold_workspace_dirs(workspace_dir: Path, skill_root: Path, project_root: Path) -> None:
    """Creates stages/00..08 (with output/), _config/, _references/.

    v3.4.0: docs/decisions/, docs/lessons.md, docs/tech_debt.md are NOT
    created here. They live in the base branch (created by
    `_ensure_base_branch_docs` before the workspace branch). Access via
    worktree `.icm-main/`.
    """
    workspace_dir.mkdir(parents=True, exist_ok=False)
    stages = workspace_dir / "stages"
    stages.mkdir()
    for s in STAGES:
        (stages / s).mkdir()
        (stages / s / "output").mkdir()

    config_dir = workspace_dir / "_config"
    config_dir.mkdir()
    matrix_src = skill_root / "templates" / "_config" / "profile-matrix.md"
    if matrix_src.exists():
        shutil.copy2(matrix_src, config_dir / "profile-matrix.md")

    # T2.5: hitl-loop template (HITL bash loop pra diagnose Phase 1 item 10)
    hitl_src = skill_root / "templates" / "workspace" / "_config" / "hitl-loop.template.sh"
    if hitl_src.exists():
        shutil.copy2(hitl_src, config_dir / "hitl-loop.template.sh")

    # T2.8: _out-of-scope/ knowledge base (vazio + README explicativo)
    oos_dir = workspace_dir / "_out-of-scope"
    oos_dir.mkdir()
    oos_tpl = skill_root / "templates" / "workspace" / "_out-of-scope" / "README.md.tpl"
    if oos_tpl.exists():
        # Render placeholders básicos (só {{WORKSPACE}})
        oos_content = oos_tpl.read_text(encoding="utf-8").replace(
            "{{WORKSPACE}}", workspace_dir.name
        )
        (oos_dir / "README.md").write_text(oos_content, encoding="utf-8")

    refs_dir = workspace_dir / "_references"
    sp_dst = refs_dir / "superpowers-summary"
    sp_dst.mkdir(parents=True)
    sp_src = skill_root / "templates" / "_references" / "superpowers-summary"
    if sp_src.is_dir():
        for f in sp_src.iterdir():
            if f.is_file() and f.suffix == ".md":
                shutil.copy2(f, sp_dst / f.name)

    runtime_dst = refs_dir / "runtime"
    runtime_dst.mkdir(parents=True)
    # Bootstrap copies canonical refs from <skill_root>/references/<file>.md INTO
    # <workspace>/_references/runtime/<file>.md during scaffold (R2.5 of plan v3).
    #
    # Why: the ICM workspace is self-contained after bootstrap. Sessions only read
    # from <workspace>/_references/runtime/ — they never cross into <skill_root>/.
    # Bootstrap is the only bridge, frozen at creation time. The skill can
    # evolve without breaking old workspaces.
    #
    # Why there is no `templates/_references/runtime/` in the skill source: to avoid
    # duplication. The canonical source in `references/` is unique. The list below
    # defines the copied subset. Doc: templates/_references/runtime/README.md.
    runtime_refs = (
        "subagent-protocol.md",
        "wave-planner-algorithm.md",
        "state-machine-schema.md",
        "recovery-wizard.md",
        "stop-points-canonical.md",
        "4-block-contract-template.md",
        "feedback-intake-stage08.md",
        "session-handoff-protocol.md",
        # v3.1 (Tier 1 + Tier 2 patterns adopted from mattpocock/skills)
        "project-root-claude-md.md",     # T1.1
        "context-format.md",              # T1.3 — ubiquitous language
        "agent-brief-template.md",        # T1.2
        "adr-format.md",                  # T1.4
        "diagnose-protocol.md",           # T2.5
        "task-types-hitl-afk.md",         # T2.6
        "triage-state-machine.md",        # T2.7
        "out-of-scope-kb.md",             # T2.8
        "design-it-twice.md",             # T3 — parallel interface design
        "deep-modules.md",                # T3 — architecture review (v3.4.1)
        "design-system.md",               # v3.4.4 — DESIGN.md format pra frontend/fullstack
        "forensic-plus-protocol.md",     # v3.8.0 — Forensic+ audit canonical
        "critic-protocol.md",            # v3.9.0 — L3 critic ortogonal
        "lead-resolution-protocol.md",   # v3.9.0 — buckets B1/B3/B4
        "mocking-guidelines.md",         # v3.9.0 — boundaries only
        "e2e-coverage-protocol.md",      # v3.10.0 — E2E reinforcement
    )
    refs_src = skill_root / "references"
    for fname in runtime_refs:
        src = refs_src / fname
        if src.is_file():
            shutil.copy2(src, runtime_dst / fname)



def _save_profile_effective(
    workspace_dir: Path,
    effective: dict[str, Any],
    profile_hash: str,
) -> None:
    """Persists profile-effective.yaml + hash for validate-state to use later."""
    import yaml  # noqa: PLC0415  — yaml is a runtime dep of the skill
    payload = dict(effective)
    payload["__hash__"] = profile_hash
    out = workspace_dir / "_config" / "profile-effective.yaml"
    out.write_text(
        yaml.safe_dump(payload, sort_keys=True, allow_unicode=True),
        encoding="utf-8",
    )


_MANAGED_HOOKS: tuple[str, ...] = ("pre-commit", "commit-msg")


def _install_hooks(project_root: Path, skill_root: Path) -> None:
    """Idempotent: installs all ICM hooks in .git/hooks/.

    Managed hooks (canonical stages):
      - pre-commit: file/atomicity checks
      - commit-msg: message prefix validation (receives COMMIT_EDITMSG in $1)

    pre-commit cannot validate the message because it runs BEFORE
    COMMIT_EDITMSG is persisted — it would read the previous commit's message.
    Original bug in v1, fixed via split.

    If already exists and diff != 0, makes a .bak.<timestamp> backup then overwrites.
    On IO error (Windows file-in-use, etc), logs a warning and continues.
    """
    dst_dir = project_root / ".git" / "hooks"
    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        sys.stderr.write(f"warning: could not create {dst_dir}: {exc}\n")
        return

    for hook in _MANAGED_HOOKS:
        src = skill_root / "templates" / ".git-hooks" / hook
        if not src.exists():
            sys.stderr.write(f"warning: hook source absent: {src}\n")
            continue
        dst = dst_dir / hook
        try:
            # Normalize CRLF→LF — git hooks run via shebang exec; CRLF
            # causes the kernel to look for interpreter "bash\r" and fail.
            new = src.read_bytes().replace(b"\r\n", b"\n")
            if dst.exists():
                current = dst.read_bytes()
                if current == new:
                    continue
                ts = _now_iso().replace(":", "").replace("-", "")
                backup = dst.with_suffix(f".bak.{ts}")
                shutil.copy2(dst, backup)
            dst.write_bytes(new)
            try:
                os.chmod(dst, 0o755)
            except OSError as _chmod_exc:
                # Windows does not support executable permissions — Git Bash resolves
                # via ACL, and os.chmod is silently ignored. Log warning only
                # if NOT on Windows (unexpected error on POSIX).
                if os.name != "nt":
                    sys.stderr.write(
                        f"warning: failed to make hook executable: {dst}: {_chmod_exc}\n"
                    )
        except OSError as exc:
            sys.stderr.write(f"warning: failed to install hook {hook}: {exc}\n")


_WORKSPACE_HOOK_FILES: tuple[str, ...] = (
    "context-check.sh",            # PostToolUse — registered in workspace settings.local.json
    "icm-session-check.sh",        # SessionStart — registration lives in project_root settings.local.json (v3.4.0)
    "block-init-during-icm.sh",    # PreToolUse — blocks /init while ICM workspace is active (v3.4.1)
)

# Hooks installed only for tier=production (v3.4.1)
_PRODUCTION_HOOK_FILES: tuple[str, ...] = (
    "block-dangerous-git.sh",      # PreToolUse — blocks push --force, reset --hard, etc.
)


def _install_context_hook(project_root: Path, skill_root: Path, workspace: str, tier: str = "") -> None:
    """Idempotent: installs workspace ICM hooks + PostToolUse registration.

    Copies hooks from the skill template to workspaces/<workspace>/.claude/hooks/:
      - context-check.sh — anti-compact PostToolUse (registered in workspace settings).
      - icm-session-check.sh — branch/worktree validation SessionStart (v3.4.0;
        registration lives in project_root settings.local.json rendered via
        _render_project_settings_example).

    Only context-check.sh is registered in
    workspaces/<workspace>/.claude/settings.local.json as a PostToolUse hook
    (path relative to workspace: bash .claude/hooks/context-check.sh).

    If workspace settings.local.json does not exist, creates it with minimal structure.
    If it already exists, adds the hook without duplicating.
    """
    workspace_dir = project_root / "workspaces" / workspace
    hooks_dir = workspace_dir / ".claude" / "hooks"
    try:
        hooks_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        sys.stderr.write(f"warning: could not create {hooks_dir}: {exc}\n")
        return

    # Copy all workspace hooks + production hooks if applicable
    hooks_to_install = list(_WORKSPACE_HOOK_FILES)
    if tier == "production":
        hooks_to_install.extend(_PRODUCTION_HOOK_FILES)

    for hook_filename in hooks_to_install:
        src_hook = skill_root / "templates" / ".claude" / "hooks" / hook_filename
        dst_hook = hooks_dir / hook_filename
        if not src_hook.exists():
            sys.stderr.write(f"warning: {hook_filename} template absent: {src_hook}\n")
            continue
        try:
            # Bytes copy + CRLF→LF normalize. shutil.copy2 would preserve CRLF from
            # the template on Windows; CRLF in the shebang causes kernel exec to fail with
            # "No such file or directory" (kernel looks for interpreter "bash\r").
            raw = src_hook.read_bytes()
            dst_hook.write_bytes(raw.replace(b"\r\n", b"\n"))
            try:
                os.chmod(dst_hook, 0o755)
            except OSError as _chmod_exc2:
                if os.name != "nt":
                    sys.stderr.write(
                        f"warning: failed to make hook executable: {dst_hook}: {_chmod_exc2}\n"
                    )
        except OSError as exc:
            sys.stderr.write(f"warning: failed to install {hook_filename}: {exc}\n")

    # Register hook in workspaces/<workspace>/.claude/settings.local.json.
    # Uses $CLAUDE_PROJECT_DIR (cwd-independent) — Claude Code runs hooks with
    # cwd potentially != project_root (worktree .icm-main/, subdir, etc).
    # Relative path "workspaces/..." fails with bash "No such file or
    # directory". $CLAUDE_PROJECT_DIR always points to the project_root where
    # the session was started.
    hook_command = (
        f'bash "$CLAUDE_PROJECT_DIR/workspaces/{workspace}/'
        f'.claude/hooks/context-check.sh"'
    )
    settings_path = workspace_dir / ".claude" / "settings.local.json"
    hook_entry = {
        "matcher": "",
        "hooks": [{"type": "command", "command": hook_command}],
    }

    settings: dict[str, Any] = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            if not isinstance(settings, dict):
                settings = {}
        except (json.JSONDecodeError, OSError):
            settings = {}

    # Add PostToolUse hook without duplicating
    post_tool_hooks = settings.get("hooks", {}).get("PostToolUse", [])
    already_exists = any(
        isinstance(entry, dict)
        and entry.get("hooks") == hook_entry["hooks"]
        and entry.get("matcher") == ""
        for entry in post_tool_hooks
    )
    if not already_exists:
        post_tool_hooks.append(hook_entry)
        if "hooks" not in settings:
            settings["hooks"] = {}
        settings["hooks"]["PostToolUse"] = post_tool_hooks

        try:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            sys.stderr.write(f"warning: failed to write settings.local.json: {exc}\n")

    # Cleanup: remove legacy hook from project_root/.claude/ if it exists.
    # Old bootstrap (pre-v3.1) installed it in project_root/.claude/hooks/.
    # New design installs in workspaces/<workspace>/.claude/hooks/ + workspace settings.
    _cleanup_legacy_context_hook(project_root)


def _cleanup_legacy_context_hook(project_root: Path) -> None:
    """Removes legacy context-check.sh from project_root/.claude/hooks/ and
    its entry in project_root/.claude/settings.local.json.

    Bootstrap pre-v3.1 installed the hook at the project root. The new design
    installs everything inside the workspace. This function migrates/removes the legacy.
    """
    # Remove legacy script
    legacy_hook = project_root / ".claude" / "hooks" / "context-check.sh"
    if legacy_hook.exists():
        try:
            legacy_hook.unlink()
        except OSError as exc:
            sys.stderr.write(f"warning: could not remove {legacy_hook}: {exc}\n")

    # Remove empty hooks directory
    legacy_hooks_dir = project_root / ".claude" / "hooks"
    if legacy_hooks_dir.exists() and legacy_hooks_dir.is_dir():
        try:
            # rmdir only works if empty
            legacy_hooks_dir.rmdir()
        except OSError:
            pass  # dir not empty, don't remove

    # Remove legacy hook entry from project_root/.claude/settings.local.json
    legacy_settings = project_root / ".claude" / "settings.local.json"
    if not legacy_settings.exists():
        return

    settings: dict[str, Any] = {}
    try:
        settings = json.loads(legacy_settings.read_text(encoding="utf-8"))
        if not isinstance(settings, dict):
            return
    except (json.JSONDecodeError, OSError):
        return

    post_tool_hooks: list[dict[str, Any]] = settings.get("hooks", {}).get("PostToolUse", [])
    original_len = len(post_tool_hooks)

    # Remove entries with context-check.sh (legacy = relative path .claude/hooks/ or
    # workspaces/NNN-slug/.claude/hooks/)
    post_tool_hooks[:] = [
        entry for entry in post_tool_hooks
        if not (
            isinstance(entry, dict)
            and isinstance(entry.get("hooks"), list)
            and any(
                isinstance(h, dict)
                and h.get("type") == "command"
                and "context-check.sh" in h.get("command", "")
                for h in entry["hooks"]
            )
        )
    ]

    if len(post_tool_hooks) != original_len:
        if post_tool_hooks:
            settings["hooks"]["PostToolUse"] = post_tool_hooks
        else:
            settings["hooks"].pop("PostToolUse", None)
            if not settings["hooks"]:
                settings.pop("hooks", None)

        try:
            legacy_settings.write_text(
                json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            sys.stderr.write(f"warning: failed to clean legacy settings.local.json: {exc}\n")


# Backward-compat alias (testes ou call sites antigos)
_install_pre_commit_hook = _install_hooks


def _commit_scaffold(
    project_root: Path,
    workspace: str,
    profile: str,
    tier: str,
) -> str:
    """git add + commit of the initial scaffold. Returns the commit sha.

    Uses --no-verify because previous workspace hooks may be installed
    and reject paths like .gitignore and workspaces/.index.md that are
    valid in bootstrap but outside the workspace NNN-slug/.
    Bootstrap is trusted; hooks protect future user activity.
    """
    _run_git(["add", f"workspaces/{workspace}/", "workspaces/.index.md"], cwd=project_root)
    # .gitignore may or may not have changed; add is idempotent
    _run_git(["add", ".gitignore"], cwd=project_root, check=False)
    # CLAUDE.md root: created/updated by _render_project_claude_md;
    # add is idempotent (check=False) — may be clean if brownfield and nothing changed.
    _run_git(["add", "CLAUDE.md"], cwd=project_root, check=False)
    msg = f"workspace {workspace.split('-', 1)[0]}: bootstrap scaffold (profile={profile} tier={tier})"
    _run_git(["commit", "--no-verify", "-m", msg], cwd=project_root)
    res = _run_git(["rev-parse", "HEAD"], cwd=project_root)
    return res.stdout.strip()


def _render_project_claude_md(
    project_root: Path,
    *,
    workspace: str,
    profile: str,
    tier: str,
    stage_atual: str,
    stage_dir: str,
    sub_stage: str,
    iteration: int,
    status: str,
    last_action: str,
    last_action_at: str,
    next_action: str,
    skill_dir: str,
) -> Path:
    """Creates/updates <project_root>/CLAUDE.md with the workspace ICM block.

    Idempotent. Brownfield-safe (preserves content outside ICM markers).
    Multi-workspace: adds block while preserving blocks of other workspaces.
    Canonical doc: references/project-root-claude-md.md.
    """
    # Lazy import: handoff.py is in the same scripts/ directory but there's no __init__.py,
    # so direct import via sys.path adjustment.
    _scripts_dir = str(Path(__file__).parent)
    if _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)
    from handoff import WorkspaceBlock, update_project_claude_md  # noqa: PLC0415

    block = WorkspaceBlock(
        workspace=workspace,
        profile=profile,
        tier=tier,
        stage_atual=stage_atual,
        stage_dir=stage_dir,
        sub_stage=sub_stage,
        iteration=iteration,
        status=status,
        last_action=last_action,
        last_action_at=last_action_at,
        next_action=next_action,
    )
    return update_project_claude_md(project_root, block, skill_dir)


def _render_project_settings_example(
    project_root: Path,
    skill_root: Path,
    workspace: str,
) -> None:
    """Idempotent: renders settings.local.json.example in project_root (v3.4.0).

    Copies templates/project_root/.claude/settings.local.json.example to
    <project_root>/.claude/settings.local.json.example replacing
    `<NNN-slug>` with the active workspace.

    `.example` is kept as documentation/reference. v3.4.2 adds
    `_merge_project_settings_local` which auto-merges into the real settings.local.json
    (without `.example` in the path), eliminating the manual copy step.

    Doc: references/worktree-model.md + references/git-hooks.md.
    """
    src = skill_root / "templates" / "project_root" / ".claude" / "settings.local.json.example"
    if not src.exists():
        sys.stderr.write(
            f"warning: settings.local.json.example template absent: {src}\n"
        )
        return

    dst_dir = project_root / ".claude"
    dst = dst_dir / "settings.local.json.example"
    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        sys.stderr.write(f"warning: could not create {dst_dir}: {exc}\n")
        return

    try:
        content = src.read_text(encoding="utf-8").replace("<NNN-slug>", workspace)
        dst.write_text(content, encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(
            f"warning: failed to render settings.local.json.example: {exc}\n"
        )


def _merge_project_settings_local(
    project_root: Path,
    workspace: str,
    tier: str = "",
) -> None:
    """Idempotent: auto-merge ICM hooks into <project_root>/.claude/settings.local.json (v3.4.2).

    Before v3.4.2, bootstrap only rendered `.example` and humans copied
    manually. Inconsistency: workspace-scope settings.local.json (in
    workspaces/<NNN>/.claude/) was already auto-created idempotently, but
    project_root scope was not. Fix: replicate that pattern.

    Hooks added (commands cwd-independent via $CLAUDE_PROJECT_DIR —
    see §"Absolute vs relative path" below):
      - SessionStart (matcher .*): icm-session-check.sh
      - PreToolUse (matcher SlashCommand|Bash): block-init-during-icm.sh
      - PreToolUse (matcher Bash, ONLY tier=production): block-dangerous-git.sh
      - PostToolUse (matcher .*): context-check.sh

    **Absolute vs relative path:** commands use $CLAUDE_PROJECT_DIR (env var
    that Claude Code exposes to the hook process, always pointing to project_root).
    Relative path "workspaces/..." breaks when the Claude Code session runs with
    cwd != project_root (e.g. inside worktree .icm-main/) — bash fails
    with "No such file or directory".

    Preserves existing user customizations: only ADDS ICM entries
    identifiable by commands containing `<workspace>/.claude/hooks/`. Does not
    touch hooks from other workspaces or non-ICM hooks.

    Doc: references/git-hooks.md (section project_root scope).
    """
    settings_path = project_root / ".claude" / "settings.local.json"

    # ICM hooks to register. List of (event, matcher, command) — multiple
    # entries per event supported (e.g. 2 PreToolUse with distinct matchers).
    # Command uses $CLAUDE_PROJECT_DIR (Claude Code env var) to be cwd-independent.
    def _cmd(hook_filename: str) -> str:
        return (
            f'bash "$CLAUDE_PROJECT_DIR/workspaces/{workspace}/'
            f'.claude/hooks/{hook_filename}"'
        )

    icm_hooks: list[tuple[str, str, str]] = [
        ("SessionStart", ".*", _cmd("icm-session-check.sh")),
        ("PreToolUse", "SlashCommand|Bash", _cmd("block-init-during-icm.sh")),
        ("PostToolUse", ".*", _cmd("context-check.sh")),
    ]

    # Conditional: tier=production adds block-dangerous-git (matcher Bash).
    # Hook .sh is only COPIED on tier=production (see _PRODUCTION_HOOK_FILES);
    # registration follows the same gate.
    if tier == "production":
        icm_hooks.append(
            ("PreToolUse", "Bash", _cmd("block-dangerous-git.sh"))
        )

    settings: dict[str, Any] = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            if not isinstance(settings, dict):
                settings = {}
        except (json.JSONDecodeError, OSError):
            settings = {}

    if "hooks" not in settings or not isinstance(settings.get("hooks"), dict):
        settings["hooks"] = {}

    changed = False
    for hook_event, matcher, hook_command in icm_hooks:
        existing_entries = settings["hooks"].get(hook_event, [])
        if not isinstance(existing_entries, list):
            existing_entries = []

        # Detecta entrada ICM existente (mesmo command exato OU command apontando
        # pra mesmo script no mesmo workspace, p.ex. matcher diferente).
        already_present = False
        for entry in existing_entries:
            if not isinstance(entry, dict):
                continue
            for h in entry.get("hooks", []) or []:
                if not isinstance(h, dict):
                    continue
                if h.get("command") == hook_command:
                    already_present = True
                    break
            if already_present:
                break

        if not already_present:
            existing_entries.append({
                "matcher": matcher,
                "hooks": [{"type": "command", "command": hook_command}],
            })
            settings["hooks"][hook_event] = existing_entries
            changed = True

    if not changed:
        return  # idempotent — nothing to write

    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        sys.stderr.write(
            f"warning: failed to write {settings_path}: {exc}\n"
        )


def _patch_context_with_sha(context_path: Path, commit_sha: str) -> None:
    text = context_path.read_text(encoding="utf-8")
    patched = text.replace("{{BOOTSTRAP_COMMIT_SHA}}", commit_sha)
    context_path.write_text(patched, encoding="utf-8")


def _commit_context_sha(project_root: Path, workspace: str) -> None:
    nnn = workspace.split("-", 1)[0]
    _run_git(
        ["add", f"workspaces/{workspace}/CONTEXT.md"],
        cwd=project_root,
    )
    msg = f"workspace {nnn}: persist bootstrap commit_sha"
    _run_git(["commit", "--no-verify", "-m", msg], cwd=project_root)


# ============================================================================
# High-level orchestration (covered by bats)
# ============================================================================

def bootstrap(
    *,
    project_root: Path,
    profile: str,
    tier: str,
    workspace_slug: str,
    skill_root: Path,
    logs_root: str | None = None,
    override_path: Path | None = None,
) -> dict[str, Any]:
    """Runs full bootstrap. Returns summary dict {workspace, branch, hash, sha}."""
    validate_slug(workspace_slug)

    if not project_root.exists() or not project_root.is_dir():
        raise BootstrapError(f"project_root is not a directory: {project_root}")

    # Greenfield: git init if necessary
    if not (project_root / ".git").exists():
        _greenfield_init(project_root)

    base_branch = _capture_base_branch(project_root)

    # Resolve workspace ID
    index_path = project_root / "workspaces" / ".index.md"
    nnn = resolve_workspace_id(index_path)
    workspace = f"{nnn:03d}-{workspace_slug}"
    workspace_dir = project_root / "workspaces" / workspace

    if workspace_dir.exists():
        raise BootstrapError(
            f"workspace dir ja existe: {workspace_dir} "
            "(rode recovery-wizard.py)"
        )

    # Profile merge
    effective, profile_hash = _run_profile_merge(skill_root, profile, tier, override_path)

    # v3.4.0: garantir docs/ scaffolding na base ANTES de switch pra
    # workspace branch (commit fica em base_branch).
    _ensure_base_branch_docs(project_root)

    # Cria workspace branch — project_root passa a ter workspace branch checada,
    # liberando base_branch para `.icm-main/` worktree.
    workspace_branch = f"workspace/{workspace}"
    _create_workspace_branch(project_root, workspace_branch, base_branch)

    # v3.4.0: workspace branch nao deve ter docs/ no tree — vive APENAS na
    # base branch via `.icm-main/` worktree. Workspace branch herda docs/ do
    # checkout-from-base; remover explicitamente garante que Read em
    # <project_root>/docs/... retorne ENOENT, forcando uso de `.icm-main/`.
    docs_dir = project_root / "docs"
    if docs_dir.exists():
        _run_git(["rm", "-rf", "docs/"], cwd=project_root, check=False)
        _run_git(
            ["commit", "--no-verify", "-m",
             f"workspace {workspace.split('-', 1)[0]}: remove docs/ from workspace branch (cross-branch v3.4.0)"],
            cwd=project_root,
            check=False,
        )

    # Linked worktree `.icm-main/` on base_branch — AFTER checkout to
    # workspace branch (otherwise `git worktree add` fails because
    # base_branch is already checked out in project_root).
    _setup_main_worktree(project_root, base_branch)

    # Scaffold
    _scaffold_workspace_dirs(workspace_dir, skill_root, project_root)

    # Copy test-recipe specific to the effective profile into _references/test-recipes/.
    # Only the active profile file is copied; profiles without a recipe (experiment,
    # technical_article) have a minimal file in the template.
    test_recipes_src = skill_root / "templates" / "_references" / "test-recipes"
    if test_recipes_src.is_dir():
        recipe_file = test_recipes_src / f"{profile}.md"
        if recipe_file.is_file():
            test_recipes_dst = workspace_dir / "_references" / "test-recipes"
            test_recipes_dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(recipe_file, test_recipes_dst / f"{profile}.md")

    # Stages skipped: derive from profile-effective and write SKIP.md markers
    stages_skipped: list[str] = effective.get("stages_skipped", [])
    for skip_id in stages_skipped:
        skip_dir = workspace_dir / "stages" / f"{skip_id}_{STAGE_NAMES[int(skip_id)]}"
        if skip_dir.exists():
            skip_file = skip_dir / "SKIP.md"
            skip_file.write_text(
                f"---\nlayer: L2-skip\nstage: \"{skip_id}\"\nreason: \"skipped by profile/tier\"\n---\n\n"
                f"# Stage {skip_id} ({STAGE_NAMES[int(skip_id)]}) — SKIPPED\n\n"
                f"This stage was skipped by the profile/tier of this workspace.\n"
                f"The flow transitions automatically from this stage to the next non-skipped one.\n",
                encoding="utf-8",
            )

    # Templates
    created_at = _now_iso()
    placeholders: dict[str, str] = {
        "WORKSPACE": workspace,
        "PROFILE": profile,
        "TIER": tier,
        "PROJECT_ROOT": str(project_root).replace("\\", "/"),
        "BASE_BRANCH": base_branch,
        "LOGS_ROOT": f'"{logs_root}"' if logs_root else "null",
        "PROFILE_EFFECTIVE_HASH": profile_hash,
        "CREATED_AT": created_at,
        "SKILL_VERSION": SKILL_VERSION,
        "SKILL_DIR": str(skill_root).replace("\\", "/"),
        "BOOTSTRAP_COMMIT_SHA": "{{BOOTSTRAP_COMMIT_SHA}}",  # patched depois
        "STAGES_SKIPPED": yaml_safe_list(stages_skipped),
        "WORKSPACE_NUM": workspace.split("-", 1)[0],
    }

    tpl_dir = skill_root / "templates" / "workspace"

    # Render L2 CONTEXT.md for each stage
    stages_tpl_dir = tpl_dir / "stages"
    for stage_dir_name in STAGES:
        l2_tpl = stages_tpl_dir / stage_dir_name / "CONTEXT.md.tpl"
        if l2_tpl.exists():
            l2_rendered = render_template(l2_tpl, placeholders)
            l2_out = workspace_dir / "stages" / stage_dir_name / "CONTEXT.md"
            l2_out.write_text(l2_rendered, encoding="utf-8")

    claude_md = render_template(tpl_dir / "CLAUDE.md.tpl", placeholders)
    (workspace_dir / "CLAUDE.md").write_text(claude_md, encoding="utf-8")

    # xp-conventions.md (L3 — convenções de código/processo)
    xp_conv_tpl = tpl_dir / "_config" / "xp-conventions.md.tpl"
    if xp_conv_tpl.exists():
        xp_conv_rendered = render_template(xp_conv_tpl, placeholders)
        (workspace_dir / "_config" / "xp-conventions.md").write_text(
            xp_conv_rendered, encoding="utf-8"
        )

    # CONTEXT.md (L3 — ubiquitous language; empty at bootstrap, populated in stage 01)
    ub_tpl = tpl_dir / "_config" / "CONTEXT.md.tpl"
    if ub_tpl.exists():
        ub_rendered = render_template(ub_tpl, placeholders)
        (workspace_dir / "_config" / "CONTEXT.md").write_text(
            ub_rendered, encoding="utf-8"
        )

    # CONTEXT.md has placeholder BOOTSTRAP_COMMIT_SHA that only exists post-commit.
    # Use a collision-safe UUID sentinel instead of "PENDING" (which could collide
    # with other fields). Patched after the first commit.
    _sha_sentinel = f"__BOOTSTRAP_SHA_{uuid.uuid4().hex[:12]}__"
    placeholders_l1 = dict(placeholders)
    placeholders_l1["BOOTSTRAP_COMMIT_SHA"] = _sha_sentinel
    context_md = render_template(tpl_dir / "CONTEXT.md.tpl", placeholders_l1)
    # Restore the sentinel to literal `{{BOOTSTRAP_COMMIT_SHA}}`; patched after
    context_md = context_md.replace(_sha_sentinel, "{{BOOTSTRAP_COMMIT_SHA}}")
    (workspace_dir / "CONTEXT.md").write_text(context_md, encoding="utf-8")

    # Stop points: render template _config/stop-points.md with tier placeholders
    # (TIER_PAID_MODE etc) + custom stop points block.
    sp_placeholders = derive_stop_point_placeholders(effective)
    custom_block = render_custom_stop_points_block(
        effective.get("custom_stop_points"),
        tier=tier,
    )
    sp_template_vars = dict(placeholders)
    sp_template_vars.update(sp_placeholders)
    sp_template_vars["CUSTOM_STOP_POINTS_BLOCK"] = custom_block
    sp_tpl = skill_root / "templates" / "_config" / "stop-points.md"
    sp_rendered = render_template(sp_tpl, sp_template_vars)
    (workspace_dir / "_config" / "stop-points.md").write_text(sp_rendered, encoding="utf-8")

    # Effective profile persisted for validate-state
    _save_profile_effective(workspace_dir, effective, profile_hash)

    # CLAUDE.md in project_root: create/update with new workspace block.
    # Brownfield-safe: ICM markers delimit the region; content outside is preserved.
    # Multi-workspace: existing workspace blocks are preserved.
    # Canonical doc: references/project-root-claude-md.md.
    _render_project_claude_md(
        project_root=project_root,
        workspace=workspace,
        profile=profile,
        tier=tier,
        stage_atual="00",
        stage_dir="00_recon",
        sub_stage="00_in_progress",
        iteration=0,
        status="IN_PROGRESS",
        last_action=f"bootstrap (profile={profile} tier={tier})",
        last_action_at=created_at,
        next_action="start stage 00 recon",
        skill_dir=str(skill_root).replace("\\", "/"),
    )

    # Index + project .gitignore
    update_index(
        index_path,
        workspace=workspace,
        profile=profile,
        tier=tier,
        created_at=created_at,
    )
    update_gitignore(project_root / ".gitignore", list(GITIGNORE_LINES))

    # Commit 1: scaffold with --no-verify. Previous workspace hooks may be
    # installed and reject paths that are valid in bootstrap (.gitignore,
    # workspaces/.index.md). Bootstrap is trusted; hooks protect future
    # user activity.
    commit_sha = _commit_scaffold(project_root, workspace, profile, tier)

    # Patch CONTEXT.md com sha do commit + commit 2
    _patch_context_with_sha(workspace_dir / "CONTEXT.md", commit_sha)
    _commit_context_sha(project_root, workspace)
    final_sha = _run_git(["rev-parse", "HEAD"], cwd=project_root).stdout.strip()

    # Hooks installed LAST: protect future user commits without interfering
    # with atomic bootstrap commits. pre-commit + commit-msg together cover
    # file checks and message validation respectively.
    _install_hooks(project_root, skill_root)

    # Context checkpoint hook (anti-compact): detects context >= 70% and
    # triggers mandatory early handoff. Installed after git hooks.
    # v3.4.0: also copies icm-session-check.sh (SessionStart) — registration
    # lives in project_root settings.local.json rendered below.
    # v3.4.1: tier=production also gets block-dangerous-git.sh.
    _install_context_hook(project_root, skill_root, workspace, tier=tier)

    # v3.4.0: render project_root/.claude/settings.local.json.example
    # with <NNN-slug> resolved. Kept as documentation/reference.
    _render_project_settings_example(project_root, skill_root, workspace)

    # v3.4.2: auto-merge ICM hooks into <project_root>/.claude/settings.local.json
    # idempotently (preserves user customizations). Replaces the manual step
    # of copying .example.
    _merge_project_settings_local(project_root, workspace, tier=tier)

    return {
        "workspace": workspace,
        "branch": workspace_branch,
        "base_branch": base_branch,
        "profile": profile,
        "tier": tier,
        "hash": profile_hash,
        "scaffold_commit_sha": commit_sha,
        "final_commit_sha": final_sha,
    }


# ============================================================================
# CLI (debug; .sh wrapper is the main path)
# ============================================================================

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="One-shot ICM workspace bootstrap (debug CLI; use .sh wrapper in prod).",
    )
    parser.add_argument("--profile", required=True)
    parser.add_argument("--tier", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--workspace-name", required=True, help="slug kebab-case")
    parser.add_argument("--logs-root", default=None)
    parser.add_argument("--override", default=None)
    parser.add_argument("--skill-root", default=None, help="default: parent of this script")
    parser.add_argument(
        "--spawn-from", default=None, dest="spawn_from",
        help="parent workspace slug (v3.7.0). Stage 08 Exit C session writes "
             ".icm/spawn-pending.json automatically; this arg is explicit "
             "fallback or manual re-spawn.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    skill_root = Path(args.skill_root) if args.skill_root else Path(__file__).resolve().parent.parent
    try:
        summary = bootstrap(
            project_root=Path(args.project_root).resolve(),
            profile=args.profile,
            tier=args.tier,
            workspace_slug=args.workspace_name,
            skill_root=skill_root,
            logs_root=args.logs_root,
            override_path=Path(args.override).resolve() if args.override else None,
        )
    except subprocess.CalledProcessError as exc:
        print(f"error: git command failed (rc={exc.returncode}): {exc.stderr.strip() if exc.stderr else exc}", file=sys.stderr)
        return 1
    except BootstrapError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
