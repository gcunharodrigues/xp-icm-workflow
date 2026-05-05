#!/usr/bin/env python3
"""Recovery Wizard L1 (R2.7).

Detects inconsistencies in L1 state (`<workspace>/CONTEXT.md`) and proposes
a recovery plan. Actions can be executed in interactive mode
(human choice) or non-interactive (`--apply A|B|C`).

Detected inconsistencies (codes):
  - HASH_MISMATCH       — profile_effective_hash diverged from recomputed value
  - MISSING_OUTPUT      — history declares output absent in FS
  - STALE_IN_PROGRESS   — IN_PROGRESS without commit in the last 24h
  - MISSING_COMMIT      — last_transition.commit_sha does not exist in git
  - BRANCH_MISSING      — branch workspace/NNN-slug does not exist (R4.5)

Canonical schema at references/state-machine-schema.md.

CLI:
  python scripts/recovery-wizard.py --workspace <path> --dry-run
  python scripts/recovery-wizard.py --workspace <path>           # interactive
  python scripts/recovery-wizard.py --workspace <path> --apply A
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml


# Codes — inconsistency type constants (UPPER_SNAKE_CASE, never translate) ----

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
# v3.4.2: inline gate before kickoff
CODE_KICKOFF_WITHOUT_GATE = "KICKOFF_WITHOUT_GATE"
# v3.4.3: wave worktree cleanup
CODE_WAVE_WORKTREE_ORPHAN = "WAVE_WORKTREE_ORPHAN"
# v3.5.0: ci-rollback-protocol.md depends on pre_wave_sha in L1 history.
# Workspaces v3.4.x started waves without recording this field — detector
# allows smooth migration (auto-fix marks "unknown").
CODE_MISSING_PRE_WAVE_SHA = "MISSING_PRE_WAVE_SHA"
# v3.6.0: preview loop dev server + CDP browser
CODE_DEV_SERVER_ORPHAN = "DEV_SERVER_ORPHAN"
CODE_CDP_DISCONNECTED = "CDP_DISCONNECTED"
# v3.7.0: runtime registry with dead PID entries (without unregister)
CODE_RUNTIME_REGISTRY_STALE = "RUNTIME_REGISTRY_STALE"
# v3.7.2: .icm-main worktree present without active workspaces (cleanup pending)
CODE_STALE_ICM_MAIN_AFTER_CLOSE = "STALE_ICM_MAIN_AFTER_CLOSE"
# v3.9.0: workspace in LEAD_RESOLUTION_IN_PROGRESS without progress > 24h
CODE_LEAD_RESOLUTION_STALE = "LEAD_RESOLUTION_STALE"
# v3.10.0: e2e suite > 7 days without update + user-facing tasks delivered
CODE_E2E_SUITE_STALE = "E2E_SUITE_STALE"

# Deterministic canonical order (R2.7 batch order).
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
    CODE_MISSING_PRE_WAVE_SHA,
    CODE_DEV_SERVER_ORPHAN,
    CODE_CDP_DISCONNECTED,
    CODE_RUNTIME_REGISTRY_STALE,
    CODE_STALE_ICM_MAIN_AFTER_CLOSE,
    CODE_LEAD_RESOLUTION_STALE,
    CODE_E2E_SUITE_STALE,
)

# Mapping stage_atual → next stage dir (to detect KICKOFF_WITHOUT_GATE).
# Stage 04 omitted due to complex waves logic; 00 and 08 do not apply.
_NEXT_STAGE_DIR: dict[str, str] = {
    "01": "02_design",
    "02": "03_wave_planner",
    "03": "04_implementation_waves",
    "05": "06_review",
    "06": "07_merge",
    "07": "08_feedback_intake",
}

# Mapping for Plan A of KICKOFF_WITHOUT_GATE: stage_atual → (next_stage_id,
# next_sub_stage, next_status). Stage 07 special (auto-transit to 08 with
# status=COMPLETED_AWAITING_HUMAN, workspace stays alive waiting for feedback).
_GATE_RETRO_TRANSITION: dict[str, tuple[str, str, str]] = {
    "01": ("02", "02_in_progress", "IN_PROGRESS"),
    "02": ("03", "03_in_progress", "IN_PROGRESS"),
    "03": ("04", "04_wave_1_in_progress", "IN_PROGRESS"),
    "05": ("06", "06_in_progress", "IN_PROGRESS"),
    "06": ("07", "07_in_progress", "IN_PROGRESS"),
    "07": ("08", "08_in_progress", "COMPLETED_AWAITING_HUMAN"),
}

STALE_THRESHOLD = timedelta(hours=24)

# Regex to find references `stages/NN_*/output/X.md` in strings.
_OUTPUT_REF_RE = re.compile(
    r"(stages/\d{2}[A-Za-z0-9_\-]*/output/[A-Za-z0-9_\-./]+\.md)"
)

_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(?P<body>.*?)\n---\s*(?:\n(?P<rest>.*))?$",
    re.DOTALL,
)


# Exceptions and dataclasses -------------------------------------------------

class RecoveryWizardError(Exception):
    """Generic Recovery Wizard error."""


@dataclass(frozen=True)
class Inconsistency:
    """Detected L1 inconsistency.

    Attributes:
        code: canonical code (see CANONICAL_ORDER).
        message: human-readable specific message.
        proposed_action: recommended Plan A (preserve) action.
        severity: "critical" | "warning".
        context: auxiliary fields (paths, shas, etc.).
    """

    code: str
    message: str
    proposed_action: str
    severity: str
    context: dict = field(default_factory=dict)


# Parsing helpers ------------------------------------------------------------

def _parse_l1(workspace_path: Path) -> tuple[dict[str, Any], str, str]:
    """Reads CONTEXT.md, returns (state_dict, frontmatter_str, body_str).

    body_str includes the rest of the markdown after the second '---'.
    """
    context_md = workspace_path / "CONTEXT.md"
    if not context_md.is_file():
        raise RecoveryWizardError(
            f"CONTEXT.md not found in workspace: {context_md}"
        )
    content = context_md.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(content)
    if match is None:
        raise RecoveryWizardError(
            "CONTEXT.md missing YAML frontmatter delimited by '---'"
        )
    fm_text = match.group("body")
    rest = match.group("rest") or ""
    try:
        state = yaml.safe_load(fm_text)
    except yaml.YAMLError as exc:
        raise RecoveryWizardError(f"Invalid YAML frontmatter: {exc}") from exc
    if not isinstance(state, dict):
        raise RecoveryWizardError(
            "Frontmatter must be a top-level mapping"
        )
    return state, fm_text, rest


def _serialize_l1(state: dict[str, Any], rest: str) -> str:
    """Re-serializes frontmatter + body. yaml.safe_dump preserves order."""
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
    """Recomputes sha256 of _config/profile-effective.yaml.

    Returns None if file is absent.
    """
    profile_yaml = workspace_path / "_config" / "profile-effective.yaml"
    if not profile_yaml.is_file():
        return None
    raw = profile_yaml.read_bytes()
    return hashlib.sha256(raw).hexdigest()


def _parse_iso(stamp: str) -> datetime:
    """Parse ISO 8601 string. Tolerates 'Z' suffix (=UTC)."""
    if stamp.endswith("Z"):
        stamp = stamp[:-1] + "+00:00"
    parsed = datetime.fromisoformat(stamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _extract_output_refs(history: list[dict[str, Any]]) -> list[str]:
    """Collects `stages/.../output/X.md` paths mentioned in history items.

    Supports:
      - explicit field `outputs: [list of paths]`
      - regex in any string value of the item (note, event, etc).

    Returns deduplicated list preserving order.
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
        # Regex across all string values
        for value in item.values():
            if isinstance(value, str):
                for match in _OUTPUT_REF_RE.findall(value):
                    _add(match)
    return found


# Git helpers ----------------------------------------------------------------

def _run_git(
    args: list[str], *, cwd: Path | None = None
) -> subprocess.CompletedProcess:
    """subprocess.run wrapper for git, with silent stdout/err capture."""
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
    """Parse `git worktree list --porcelain`. Returns [(path, branch), ...].

    Worktree without branch (detached HEAD) has branch="". Path is always absolute.
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
    """True if `branch` has already been merged into `base_branch` (i.e., is ancestor)."""
    if not branch or not base_branch:
        return False
    result = _run_git(
        ["merge-base", "--is-ancestor", branch, base_branch], cwd=cwd
    )
    return result.returncode == 0


def _is_pid_alive(pid: int) -> bool:
    """Cross-platform PID liveness check.

    POSIX: os.kill(pid, 0) raises ProcessLookupError if dead.
    Windows: uses OpenProcess via ctypes (no psutil dep).
    False-positive acceptable (warning-level recovery).
    """
    if pid <= 0:
        return False
    try:
        if platform.system() == "Windows":
            import ctypes  # noqa: PLC0415

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # POSIX: process exists but inaccessible. Consider alive.
        return True
    except OSError:
        return False


def _is_port_listening(host: str, port: int, timeout: float = 0.3) -> bool:
    """True if there is a TCP listener accepting connections on host:port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def _last_workspace_commit_at(
    workspace_id: str, *, cwd: Path | None = None
) -> datetime | None:
    """Returns ISO 8601 of the most recent commit that touched workspaces/<id>/."""
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
    """Runs all checks. Returns inconsistencies in canonical order.

    `project_root` defaults to `state["project_root"]` if absent.
    `now` defaults to `datetime.now(timezone.utc)`.
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
                    f"profile_effective_hash declared ({declared[:12]}...) "
                    f"diverged from recomputed ({actual[:12]}...). "
                    "_config/profile-effective.yaml changed without L1 update."
                ),
                proposed_action=(
                    "recompute hash + update L1 (preserves profile)"
                ),
                severity="warning",
                context={"declared": declared, "actual": actual},
            )
        )

    # 2) MISSING_COMMIT (comes before OUTPUT in canonical order)
    last_transition = state.get("last_transition") or {}
    sha = last_transition.get("commit_sha", "")
    cwd_for_git = project_root if project_root else None
    if sha and not _commit_exists(sha, cwd=cwd_for_git):
        found.append(
            Inconsistency(
                code=CODE_MISSING_COMMIT,
                message=(
                    f"last_transition.commit_sha={sha} does not exist in git "
                    "history (rebased away?)."
                ),
                proposed_action=(
                    "rollback last_transition to the second-to-last valid event in "
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
                    "outputs declared in history do not exist in FS: "
                    f"{listed}"
                ),
                proposed_action=(
                    "remove related history entry + warning (or rollback "
                    "to last_transition before the output)"
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
        # Fallback: use last_action_at if git log returned nothing.
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
                        f"status=IN_PROGRESS without commit in workspaces/* "
                        f"for {age}. Probable orphaned session."
                    ),
                    proposed_action=(
                        "append 'recovery_applied' to history + status "
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
                        f"branch '{branch}' absent. Try restore via "
                        "reflog: git reflog | grep "
                        f"'{branch}' (R4.5)."
                    ),
                    proposed_action=(
                        "try restore via reflog or create new branch "
                        "from last_transition.commit_sha"
                    ),
                    severity="critical",
                    context={"branch": branch},
                )
            )

    # 6) CLAUDE_MD_ROOT_STALE / MISSING (G5)
    # Checks consistency between L1.stage_atual and the workspace block in
    # <project_root>/CLAUDE.md (ICM region). Doc: references/project-root-claude-md.md.
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
                            f"workspace {ws_id} status=IN_PROGRESS but does not "
                            "appear as a block in <project_root>/CLAUDE.md "
                            "ICM region. Bootstrap did not run or block was "
                            "manually removed."
                        ),
                        proposed_action=(
                            "regenerate workspace block from L1 via "
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
                                f"<project_root>/CLAUDE.md shows stage "
                                f"{root_stage!r} for workspace {ws_id} but "
                                f"L1 declares {l1_stage!r}. Previous session "
                                "crashed without calling handoff."
                            ),
                            proposed_action=(
                                "regenerate block from L1 via "
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
    # `.icm-main/` linked worktree is mandatory since v3.4.0. Doc:
    # references/worktree-model.md.
    if project_root is not None and project_root.is_dir():
        base_branch = state.get("base_branch", "")
        worktree_path = project_root / ".icm-main"
        if not worktree_path.exists():
            found.append(
                Inconsistency(
                    code=CODE_WORKTREE_MISSING,
                    message=(
                        f"`.icm-main/` worktree absent in {project_root}. "
                        "Cross-branch model v3.4.0 requires linked worktree of "
                        "base branch. Future sessions will not be able to read "
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
            # Validate checked-out branch
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
                                f"`.icm-main/` is on '{wt_branch}', should "
                                f"be on base_branch '{base_branch}'."
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
    # Main worktree should be on workspace branch during active ICM cycle.
    # If human opened session on base_branch by mistake, signal it.
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
                            f"current branch in {project_root} is '{current_branch}', "
                            f"expected '{expected_ws_branch}' (workspace still active, "
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
    # Symptom of pre-v3.4.2 bug: previous session rendered _kickoff.md of
    # stage NN+1 but L1 indicates stage_atual=NN with status=COMPLETED_AWAITING_HUMAN
    # (gate not approved). Workspaces created before the fix may be in
    # this state. Detect: kickoff exists AND status pending AND
    # sub_stage ends in _completed.
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
                        f"_kickoff.md of {next_dir} exists but L1 declares "
                        f"stage_atual={stage_atual!r} sub_stage={sub_stage!r} "
                        "status=COMPLETED_AWAITING_HUMAN. Symptom of pre-v3.4.2 bug: "
                        "previous session rendered kickoff without "
                        "waiting for human gate."
                    ),
                    proposed_action=(
                        "approve gate retroactively (keeps kickoff, transitions "
                        "L1 to next stage)"
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
    # Ephemeral worktrees created by Agent tool in stage 04 should be
    # removed by lead after sequential merge + green CI. Pre-v3.4.3 bug:
    # missing cleanup caused worktrees + branches `wave-<NNN>-N/<task>`
    # to accumulate in <project_root>/.icm-wave-* (or path returned by
    # Agent tool). Detect: worktrees with branch pattern `wave-<NNN>-`
    # where NNN matches workspace_num, AND branch already merged into base_branch
    # (safe cleanup).
    if project_root is not None and project_root.is_dir():
        ws_id = state.get("workspace", "")
        base_branch = state.get("base_branch", "")
        if ws_id and base_branch:
            workspace_num = ws_id.split("-", 1)[0]  # "001-..." -> "001"
            wave_branch_prefix = f"wave-{workspace_num}-"
            worktrees = _list_worktrees(project_root)
            orphans: list[tuple[str, str]] = []
            for wt_path, wt_branch in worktrees:
                # Skip main worktree (project_root) and .icm-main
                wt_path_resolved = Path(wt_path).resolve()
                if wt_path_resolved == project_root.resolve():
                    continue
                if wt_path_resolved == (project_root / ".icm-main").resolve():
                    continue
                if not wt_branch.startswith(wave_branch_prefix):
                    continue
                # Cleanup safe only if branch already merged
                if _is_branch_merged(wt_branch, base_branch, cwd=project_root):
                    orphans.append((wt_path, wt_branch))
            if orphans:
                listed = ", ".join(f"{p} ({b})" for p, b in orphans[:3])
                more = f" (+{len(orphans) - 3} more)" if len(orphans) > 3 else ""
                found.append(
                    Inconsistency(
                        code=CODE_WAVE_WORKTREE_ORPHAN,
                        message=(
                            f"{len(orphans)} orphaned wave worktree(s) "
                            f"detected: {listed}{more}. Pre-v3.4.3 bug: "
                            "lead did not execute post-merge cleanup."
                        ),
                        proposed_action=(
                            "auto-cleanup: git worktree remove + "
                            "git branch -d (safe because already merged)"
                        ),
                        severity="warning",
                        context={
                            "orphans": orphans,
                            "workspace_num": workspace_num,
                            "base_branch": base_branch,
                        },
                    )
                )

    # 11) MISSING_PRE_WAVE_SHA (v3.5.0)
    # ci-rollback-protocol.md requires pre_wave_sha in L1 history event
    # `wave_started` (recorded in Process step 1). Workspaces v3.4.x
    # started waves before the field existed — detect by scanning
    # history events `wave_started` in stage 04 without pre_wave_sha. Auto-fix
    # marks "unknown" (does not attempt to infer SHA — human decides rollback).
    if isinstance(history, list) and stage_atual == "04":
        wave_started_missing = []
        for ev in history:
            if not isinstance(ev, dict):
                continue
            if ev.get("event") != "wave_started":
                continue
            if not ev.get("pre_wave_sha"):
                wave_started_missing.append(ev.get("wave"))
        if wave_started_missing and sub_stage.startswith("04_wave_"):
            waves_listed = ", ".join(str(w) for w in wave_started_missing)
            found.append(
                Inconsistency(
                    code=CODE_MISSING_PRE_WAVE_SHA,
                    message=(
                        f"history event(s) wave_started without pre_wave_sha: "
                        f"waves={waves_listed}. Workspace started wave(s) "
                        "pre-v3.5.0; ci-rollback-protocol is blind if triggered."
                    ),
                    proposed_action=(
                        "auto-fix: mark pre_wave_sha: 'unknown' in "
                        "affected events (human decides rollback if "
                        "BLOCKED_ERROR ci_global_red fires)"
                    ),
                    severity="warning",
                    context={"waves": wave_started_missing},
                )
            )

    # 12) DEV_SERVER_ORPHAN (v3.6.0)
    # Preview loop entry hook saves PID in .icm-main/.dev-server.pid when
    # dev server starts. Exit hook should kill process + delete PID.
    # Symptom: PID file exists AND process is dead (session crashed or exit
    # hook did not run). Plan A: delete PID file, record warning.
    if project_root is not None and project_root.is_dir():
        pid_file = project_root / ".icm-main" / ".dev-server.pid"
        if pid_file.is_file():
            try:
                pid_str = pid_file.read_text(encoding="utf-8").strip()
                pid = int(pid_str)
            except (OSError, ValueError):
                pid = -1
            if pid > 0 and not _is_pid_alive(pid):
                found.append(
                    Inconsistency(
                        code=CODE_DEV_SERVER_ORPHAN,
                        message=(
                            f"PID file {pid_file} points to dead process "
                            f"(pid={pid}). Stage 04 exit hook did not run or "
                            "session crashed. Doc: preview-loop-protocol.md."
                        ),
                        proposed_action=(
                            "delete PID file + record warning (next "
                            "stage 04 entry restarts dev server cleanly)"
                        ),
                        severity="warning",
                        context={"pid_file": str(pid_file), "pid": pid},
                    )
                )

    # 13) CDP_DISCONNECTED (v3.6.0)
    # Preview loop uses Chrome with --remote-debugging-port=9222 and
    # --user-data-dir=.icm-chrome-profile. Symptom: profile dir exists
    # but Chrome is not listening on 9222 (Chrome closed, port busy,
    # helper failed). Warning-level — agent degrades via fallback (route
    # map + manual screenshot).
    if project_root is not None and project_root.is_dir():
        cdp_profile_dir = project_root / ".icm-chrome-profile"
        if cdp_profile_dir.is_dir():
            if not _is_port_listening("127.0.0.1", 9222):
                found.append(
                    Inconsistency(
                        code=CODE_CDP_DISCONNECTED,
                        message=(
                            f"`{cdp_profile_dir.name}/` exists but Chrome "
                            "is not listening on :9222. Launch helper "
                            "`scripts/launch-chrome-cdp.{bat,sh}` or follow "
                            "fallback (route map + manual screenshot)."
                        ),
                        proposed_action=(
                            "record warning; human relaunches Chrome via "
                            "helper script (skill does not remove profile)"
                        ),
                        severity="warning",
                        context={"profile_dir": str(cdp_profile_dir)},
                    )
                )

    # 14) RUNTIME_REGISTRY_STALE (v3.7.0)
    # Detects workspaces/<NNN>/_state/runtime-registry.json with entries
    # of dead PIDs (process terminated without unregister). Plan A: suggests
    # `runtime-registry.py purge-dead`. Does not auto-purge (human confirms).
    found.extend(_detect_runtime_registry_stale(workspace_path))

    # 15) STALE_ICM_MAIN_AFTER_CLOSE (v3.7.2)
    # Trigger: current workspace COMPLETED + .icm-main/ present + zero other
    # active workspaces in project_root. Symptom of exit A/C pre-v3.7.2 that
    # did not run cleanup, or human answered [n] in opt-in menu. Plan A:
    # suggests invoking scripts/icm-cleanup.py interactively.
    if (
        project_root is not None
        and project_root.is_dir()
        and state.get("status") == "COMPLETED"
    ):
        icm_main = project_root / ".icm-main"
        if icm_main.exists() and _count_active_workspaces(project_root) == 0:
            ws_id = state.get("workspace", "")
            found.append(
                Inconsistency(
                    code=CODE_STALE_ICM_MAIN_AFTER_CLOSE,
                    message=(
                        f"workspace {ws_id} COMPLETED + .icm-main/ present "
                        "+ zero active workspaces. ICM cleanup pending "
                        "(exit A/C pre-v3.7.2 or human opt-out)."
                    ),
                    proposed_action=(
                        f"run scripts/icm-cleanup.py --project-root "
                        f"{project_root} --workspace {ws_id} --dry-run "
                        "(human confirms before running without --dry-run)"
                    ),
                    severity="warning",
                    context={
                        "project_root": str(project_root),
                        "workspace": ws_id,
                    },
                )
            )

    # Reorder to canonical order
    by_code: dict[str, Inconsistency] = {i.code: i for i in found}
    ordered = [by_code[c] for c in CANONICAL_ORDER if c in by_code]
    return ordered


# ============================================================================
# v3.7.2 helpers — STALE_ICM_MAIN_AFTER_CLOSE
# ============================================================================


def _count_active_workspaces(project_root: Path) -> int:
    """Counts workspaces in project_root whose L1 status != COMPLETED.

    Iterates dirs in `<project_root>/workspaces/`, reads `CONTEXT.md` frontmatter,
    extracts status. Used by STALE_ICM_MAIN_AFTER_CLOSE detector to
    confirm cleanup is safe (zero active workspaces remaining).
    """
    ws_dir = project_root / "workspaces"
    if not ws_dir.is_dir():
        return 0
    active = 0
    for entry in ws_dir.iterdir():
        if not entry.is_dir():
            continue
        ctx = entry / "CONTEXT.md"
        if not ctx.is_file():
            continue
        try:
            content = ctx.read_text(encoding="utf-8")
        except OSError:
            continue
        match = _FRONTMATTER_RE.match(content)
        if not match:
            continue
        try:
            data = yaml.safe_load(match.group("body")) or {}
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and data.get("status") != "COMPLETED":
            active += 1
    return active


# ============================================================================
# Runtime registry stale detector (v3.7.0)
# ============================================================================

def _pid_alive_for_registry(pid: int) -> bool:
    """Testable wrapper for _is_pid_alive used by runtime-registry.

    Separate function to allow monkeypatching in tests without touching
    the original cross-platform function.
    """
    return _is_pid_alive(pid)


def _detect_runtime_registry_stale(workspace_path: Path) -> list[Inconsistency]:
    """Detects entries with dead PIDs in runtime-registry.json."""
    registry_path = workspace_path / "_state" / "runtime-registry.json"
    if not registry_path.is_file():
        return []
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    entries = data.get("entries", [])
    dead = []
    for entry in entries:
        pid = entry.get("pid")
        if pid is None:
            continue
        if not _pid_alive_for_registry(int(pid)):
            dead.append(entry)
    if not dead:
        return []
    pids = ", ".join(str(e.get("pid")) for e in dead)
    rel = registry_path.relative_to(workspace_path)
    return [Inconsistency(
        code=CODE_RUNTIME_REGISTRY_STALE,
        message=(
            f"`{rel}` contains {len(dead)} entry(ies) with dead PID "
            f"(pids: {pids}). Processes terminated without unregister."
        ),
        proposed_action=(
            f"run `python {{SKILL_DIR}}/scripts/runtime-registry.py "
            f"purge-dead --workspace-root {workspace_path}` "
            "or unregister manually by id"
        ),
        severity="warning",
        context={"registry": str(registry_path),
                 "dead_pids": [e.get("pid") for e in dead]},
    )]


def _get_root_workspace_block(project_root: Path, workspace_id: str) -> dict | None:
    """Reads <project_root>/CLAUDE.md, returns workspace block dict or None.

    Parses via `<!-- ICM-DATA:... -->` comments (JSON). Lazy import of handoff
    via sys.path to avoid circular dependency.
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
    """Renders recovery plan as markdown."""
    if not inconsistencies:
        return "Workspace consistent. Nothing to recover.\n"

    lines: list[str] = []
    lines.append("# Recovery Plan\n")
    lines.append(
        f"Detected {len(inconsistencies)} inconsistency(ies) in L1.\n"
    )

    # Summary table
    lines.append("## Summary\n")
    lines.append("| Code | Severity | Message |")
    lines.append("|---|---|---|")
    for inc in inconsistencies:
        msg = inc.message.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {inc.code} | {inc.severity} | {msg} |")
    lines.append("")

    # Details per inconsistency + 3 options
    lines.append("## Details and actions\n")
    for idx, inc in enumerate(inconsistencies, start=1):
        lines.append(f"### {idx}. {inc.code} ({inc.severity})\n")
        lines.append(f"{inc.message}\n")
        lines.append("**Plan A (preserve):** " + inc.proposed_action)
        lines.append(
            "**Plan B (rollback):** rollback L1 to the last consistent state"
            " before the problematic event"
        )
        lines.append(
            "**Plan C (escalate):** mark status=BLOCKED_ERROR and "
            "escalate to human (no automated change)"
        )
        lines.append("")

    lines.append("## Choice")
    lines.append(
        "Select A | B | C applicable to ALL inconsistencies "
        "(batch). For individual resolution, edit L1 manually."
    )
    return "\n".join(lines) + "\n"


# Apply ----------------------------------------------------------------------

def _append_history(
    state: dict[str, Any], event: dict[str, Any]
) -> None:
    history = state.setdefault("history", [])
    if not isinstance(history, list):
        raise RecoveryWizardError("history is not a list — L1 corrupted")
    history.append(event)


def _now_iso(now: datetime | None = None) -> str:
    if now is None:
        now = datetime.now(timezone.utc)
    # ISO 8601 with 'Z'
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _apply_plan_a(
    workspace_path: Path,
    state: dict[str, Any],
    inconsistencies: list[Inconsistency],
    now: datetime,
) -> None:
    """Plan A — preserve. Applies fix per code."""
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
            # Find second-to-last event with valid commit_sha (preference: stage_transition)
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
            # Append warning event; do not delete existing history (append-only).
            _append_history(
                state,
                {
                    "at": _now_iso(now),
                    "event": "recovery_warning",
                    "note": (
                        "missing outputs: "
                        + ", ".join(inc.context.get("missing", []))
                    ),
                },
            )

        elif inc.code == CODE_STALE_IN_PROGRESS:
            state["status"] = "COMPLETED_AWAITING_HUMAN"

        elif inc.code == CODE_BRANCH_MISSING:
            # Plan A for branch missing does not auto-recreate —
            # only records warning. Recreate requires human.
            _append_history(
                state,
                {
                    "at": _now_iso(now),
                    "event": "recovery_warning",
                    "note": (
                        "branch absent: "
                        + inc.context.get("branch", "")
                        + ". Suggestion: git reflog | grep "
                        + inc.context.get("branch", "")
                    ),
                },
            )

        elif inc.code == CODE_WAVE_WORKTREE_ORPHAN:
            # Plan A: auto-cleanup. For each orphan: git worktree remove +
            # git branch -d. Cleanup safe because detection filtered by branch
            # already merged into base_branch.
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
                    # Retry with --force if cleanup failed
                    wt_result = _run_git(
                        ["worktree", "remove", "--force", wt_path], cwd=cwd
                    )
                # 2. Delete branch (safe because merged)
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
                f"removed {len(removed)} orphan(s); "
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
            # Plan A: approve gate retroactively. Transitions L1 to next
            # stage using _GATE_RETRO_TRANSITION (keeps already generated kickoff).
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

        elif inc.code == CODE_DEV_SERVER_ORPHAN:
            # Plan A: delete PID file + log. Next stage 04 entry restarts cleanly.
            pid_file_str = inc.context.get("pid_file", "")
            if pid_file_str:
                pid_file = Path(pid_file_str)
                try:
                    pid_file.unlink()
                except OSError:
                    pass
                # Also delete .dev-server.log if it exists
                log_file = pid_file.with_suffix(".log")
                if log_file.is_file():
                    try:
                        log_file.unlink()
                    except OSError:
                        pass
            _append_history(
                state,
                {
                    "at": _now_iso(now),
                    "event": "recovery_warning",
                    "note": (
                        f"DEV_SERVER_ORPHAN cleanup: removed "
                        f"{inc.context.get('pid_file', '')}"
                    ),
                },
            )

        elif inc.code == CODE_CDP_DISCONNECTED:
            # Plan A: record warning, do NOT remove profile dir (human may
            # want to reopen via helper script). No state change.
            _append_history(
                state,
                {
                    "at": _now_iso(now),
                    "event": "recovery_warning",
                    "note": (
                        "CDP_DISCONNECTED: relaunch Chrome via "
                        "scripts/launch-chrome-cdp.{bat,sh}. Profile "
                        f"dir preserved at {inc.context.get('profile_dir', '')}"
                    ),
                },
            )

        elif inc.code in (CODE_CLAUDE_MD_ROOT_STALE, CODE_CLAUDE_MD_ROOT_MISSING):
            # Plan A: regenerate workspace block in <project_root>/CLAUDE.md
            # from current L1 state. Lazy import of handoff.
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
                        "note": "handoff.py unavailable; CLAUDE.md root block not regenerated",
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
            # SKILL_DIR not in L1; use placeholder (workspace L0 has absolute
            # skill_dir, but recovery does not consult L0). Canonical doc guides user.
            handoff.update_project_claude_md(proj_root, block, skill_dir="<skill-dir>")

        elif inc.code == CODE_STALE_ICM_MAIN_AFTER_CLOSE:
            # Plan A: record warning (does NOT execute automatic cleanup —
            # destructive, requires human confirmation). History includes the
            # exact command for human to run. Doc: references/icm-cleanup-protocol.md.
            proj_root_str = inc.context.get("project_root", "")
            ws_id = inc.context.get("workspace", "")
            _append_history(
                state,
                {
                    "at": _now_iso(now),
                    "event": "recovery_warning",
                    "note": (
                        f"STALE_ICM_MAIN_AFTER_CLOSE: run "
                        f"`python <skill-dir>/scripts/icm-cleanup.py "
                        f"--project-root {proj_root_str} --workspace {ws_id} "
                        f"--dry-run` for preview, then without --dry-run to "
                        f"execute. Cleanup is opt-in (destructive)."
                    ),
                },
            )

    # Append summary recovery_applied event
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
    """Plan B — rollback. Reverts L1 to the last consistent state."""
    codes = [i.code for i in inconsistencies]
    history = state.get("history") or []

    # Strategy: for each applicable code, revert the field to the second-to-last
    # valid event in history. More conservative than Plan A.
    if any(i.code == CODE_MISSING_COMMIT for i in inconsistencies):
        # Same handler as A
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
        # Plan B: does not touch L1 (assumes profile-effective.yaml is wrong);
        # records warning for human to regenerate profile.
        pass

    if any(i.code == CODE_STALE_IN_PROGRESS for i in inconsistencies):
        # Plan B identical to A
        state["status"] = "COMPLETED_AWAITING_HUMAN"

    # KICKOFF_WITHOUT_GATE: Plan B = deletes kickoff + reverts L1 to in_progress.
    # Workspace continues working on stage NN (redoes outputs).
    for inc in inconsistencies:
        if inc.code == CODE_KICKOFF_WITHOUT_GATE:
            kickoff_path_str = inc.context.get("kickoff_path", "")
            if kickoff_path_str:
                kickoff_path = Path(kickoff_path_str)
                if kickoff_path.is_file():
                    try:
                        kickoff_path.unlink()
                    except OSError:
                        pass  # silent warning — human sees history
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
                        "kickoff deleted, returning to work via "
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
    """Plan C — escalate. Marks BLOCKED_ERROR + history append. No other change."""
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
    """Applies chosen recovery. plan_choice in {A, B, C}.

    Consistent workspace -> no-op (no write).
    """
    if plan_choice not in {"A", "B", "C"}:
        raise RecoveryWizardError(
            f"Invalid plan_choice: '{plan_choice}'. Expected A | B | C."
        )

    if now is None:
        now = datetime.now(timezone.utc)

    inconsistencies = detect_inconsistencies(
        workspace_path, project_root=project_root, now=now
    )
    if not inconsistencies:
        return  # No-op on consistent workspace

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
            "Detects L1 inconsistencies (root CONTEXT.md) and proposes / "
            "applies recovery."
        ),
    )
    parser.add_argument(
        "--workspace", required=True, help="Path to the workspace"
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Override for project_root (default: read from L1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Audit only — prints inconsistencies and plan without applying",
    )
    parser.add_argument(
        "--apply",
        choices=["A", "B", "C"],
        default=None,
        help="Applies plan A | B | C non-interactively",
    )
    args = parser.parse_args(argv)

    workspace = Path(args.workspace)
    project_root = Path(args.project_root) if args.project_root else None

    if not workspace.is_dir():
        print(
            f"RecoveryWizardError: workspace does not exist: {workspace}",
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
        return 0  # Audit mode always exits 0

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
            f"{len(inconsistencies)} inconsistency(ies) processed."
        )
        return 0

    # Interactive mode
    if not inconsistencies:
        print(f"Workspace consistent: {workspace}")
        return 0

    print(propose_recovery_plan(inconsistencies))
    print("Choose plan (A / B / C) or Q to quit:")
    try:
        choice = input("> ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        print("Cancelled.")
        return 1
    if choice == "Q":
        print("Cancelled.")
        return 1
    if choice not in {"A", "B", "C"}:
        print(f"Invalid choice: {choice}", file=sys.stderr)
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
