"""ICM cleanup after exit A/C of the last active workspace (v3.7.2).

Reverts the ICM-ephemeral structure to the natural post-project state:
  - `git checkout <BASE_BRANCH>` in project_root (root reflects product code
    again, not workspace branch state).
  - `git worktree remove .icm-main` (redundant parallel worktree).
  - `git branch -D workspace/<NNN>-<slug>` (closed workspace branch).
  - `git worktree prune` (removes orphaned stage 04 subagent worktrees).

Canonical doc: `references/icm-cleanup-protocol.md`.

CLI:
    python scripts/icm-cleanup.py \
        --project-root <path> \
        --workspace <NNN-slug> \
        --base-branch main \
        [--dry-run]              # prints commands without executing
        [--force]                # accepts uncommitted changes (dangerous)

Exit codes:
    0 = success
    1 = aborted by pre-check (uncommitted changes / diverged branch)
    2 = execution error (git command failed)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass
class CleanupReport:
    """Result of the cleanup operation. Stub-friendly for tests."""
    aborted: bool = False
    abort_reason: str = ""
    actions_taken: list[str] = field(default_factory=list)
    actions_skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dry_run: bool = False

    def add_action(self, msg: str) -> None:
        self.actions_taken.append(msg)

    def add_skip(self, msg: str) -> None:
        self.actions_skipped.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def abort(self, reason: str) -> None:
        self.aborted = True
        self.abort_reason = reason


def _run_git(
    args: list[str],
    *,
    cwd: Path,
    check: bool = False,
    dry_run: bool = False,
    report: CleanupReport,
) -> subprocess.CompletedProcess[str]:
    cmd = ["git"] + args
    cmd_str = " ".join(cmd) + f"  # cwd={cwd}"
    if dry_run:
        report.add_action(f"[dry-run] {cmd_str}")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    result = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git failed ({result.returncode}): {cmd_str}\n"
            f"stderr: {result.stderr.strip()}"
        )
    return result


def _git_status_clean(cwd: Path) -> tuple[bool, str]:
    """Returns (clean, status_output)."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(cwd), capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return False, result.stderr.strip()
    return result.stdout.strip() == "", result.stdout.strip()


def _list_subagent_worktrees(project_root: Path) -> list[Path]:
    """List worktrees registered under `.git/worktrees/<task-slug>` that are NOT
    project_root or `.icm-main`. These are orphaned subagent worktrees from stage 04.
    """
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=str(project_root), capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return []
    paths: list[Path] = []
    pr_resolved = project_root.resolve()
    icm_main = (project_root / ".icm-main").resolve()
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            path_str = line.split(" ", 1)[1].strip()
            wt_path = Path(path_str).resolve()
            if wt_path == pr_resolved:
                continue
            if wt_path == icm_main:
                continue
            paths.append(wt_path)
    return paths


def _detect_current_branch(cwd: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(cwd), capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _branch_exists(project_root: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=str(project_root), capture_output=True, text=True, check=False,
    )
    return result.returncode == 0


def cleanup_after_close(
    project_root: Path,
    workspace: str,
    *,
    base_branch: str = "main",
    dry_run: bool = False,
    force: bool = False,
) -> CleanupReport:
    """Run cleanup after exit A/C of the last active workspace.

    Pre-checks (abort if they fail):
    - project_root is a git repo.
    - workspace branch exists (`workspace/<workspace>`).
    - workspace branch tree is clean (no uncommitted changes) unless `--force`.
    - `.icm-main/` worktree (if present) is clean unless `--force`.

    Sequence (all idempotent):
    1. Orphaned subagent worktrees → `git worktree remove --force` each.
    2. Remove `.icm-main/` worktree (releases base_branch held there).
    3. `git checkout <base_branch>` in project_root — now possible because
       the concurrent worktree on base_branch was removed in step 2.
    4. `git branch -D workspace/<workspace>` (deletes closed branch).
    5. `git worktree prune` final.

    Order matters: `.icm-main/` must be removed BEFORE checkout in project_root,
    otherwise git rejects "branch already checked out in another worktree".

    Returns: `CleanupReport` with list of actions taken/skipped/warnings.
    Caller (template stage 08) uses report for logging + continue decision.
    """
    report = CleanupReport(dry_run=dry_run)

    if not (project_root / ".git").exists():
        report.abort(f"project_root {project_root} is not a git repo")
        return report

    workspace_branch = f"workspace/{workspace}"
    if not _branch_exists(project_root, workspace_branch):
        report.add_warning(
            f"branch {workspace_branch} does not exist (already deleted?) — continuing cleanup"
        )

    # Pre-check workspace branch tree is clean (if still checked out)
    current = _detect_current_branch(project_root)
    if current == workspace_branch and not force:
        clean, status_out = _git_status_clean(project_root)
        if not clean:
            report.abort(
                f"workspace branch ({workspace_branch}) has uncommitted changes:\n"
                f"{status_out}\n"
                f"Commit or stash before cleanup, or run --force (dangerous)."
            )
            return report

    # Pre-check .icm-main/ worktree
    icm_main = project_root / ".icm-main"
    icm_main_present = icm_main.exists()
    if icm_main_present and not force:
        clean, status_out = _git_status_clean(icm_main)
        if not clean:
            report.abort(
                f".icm-main/ has uncommitted changes:\n{status_out}\n"
                f"Commit or stash before cleanup, or run --force (dangerous)."
            )
            return report

    # 1. Orphaned subagent worktrees
    subagent_wts = _list_subagent_worktrees(project_root)
    for wt in subagent_wts:
        try:
            _run_git(
                ["worktree", "remove", str(wt), "--force"],
                cwd=project_root, dry_run=dry_run, report=report,
            )
            report.add_action(f"removed subagent worktree: {wt}")
        except RuntimeError as exc:
            report.add_warning(f"failed to remove subagent worktree {wt}: {exc}")

    if not subagent_wts:
        report.add_skip("no orphaned subagent worktrees detected")

    # 2. Remove .icm-main worktree BEFORE checkout (releases base_branch)
    if icm_main_present:
        result = _run_git(
            ["worktree", "remove", ".icm-main"],
            cwd=project_root, dry_run=dry_run, report=report,
        )
        if not dry_run and result.returncode != 0:
            result2 = _run_git(
                ["worktree", "remove", ".icm-main", "--force"],
                cwd=project_root, dry_run=dry_run, report=report,
            )
            if not dry_run and result2.returncode != 0:
                report.add_warning(
                    f"git worktree remove .icm-main failed: {result2.stderr.strip()}"
                )
            else:
                report.add_action("removed .icm-main worktree (--force)")
        else:
            report.add_action("removed .icm-main worktree")
    else:
        report.add_skip(".icm-main/ absent — nothing to remove")

    # 3. checkout base_branch in project_root (now possible after step 2)
    if current != base_branch:
        result = _run_git(
            ["checkout", base_branch],
            cwd=project_root, dry_run=dry_run, report=report,
        )
        if not dry_run and result.returncode != 0:
            report.abort(
                f"git checkout {base_branch} failed:\n{result.stderr.strip()}"
            )
            return report
        report.add_action(f"checkout {base_branch} em project_root")
    else:
        report.add_skip(f"project_root already on {base_branch}")

    # 4. Delete workspace branch (we left it in step 3)
    if _branch_exists(project_root, workspace_branch):
        result = _run_git(
            ["branch", "-D", workspace_branch],
            cwd=project_root, dry_run=dry_run, report=report,
        )
        if not dry_run and result.returncode != 0:
            report.add_warning(
                f"git branch -D {workspace_branch} failed: {result.stderr.strip()}"
            )
        else:
            report.add_action(f"deleted branch {workspace_branch}")
    else:
        report.add_skip(f"branch {workspace_branch} already absent")

    # 5. prune final
    _run_git(
        ["worktree", "prune"],
        cwd=project_root, dry_run=dry_run, report=report,
    )
    report.add_action("git worktree prune")

    return report


def _format_report(report: CleanupReport) -> str:
    lines: list[str] = []
    if report.dry_run:
        lines.append("=== DRY RUN — no actions executed ===")
    if report.aborted:
        lines.append(f"❌ ABORTED: {report.abort_reason}")
        return "\n".join(lines)
    lines.append("✅ ICM cleanup complete.")
    if report.actions_taken:
        lines.append("\nActions:")
        for a in report.actions_taken:
            lines.append(f"  • {a}")
    if report.actions_skipped:
        lines.append("\nSkipped (idempotent):")
        for s in report.actions_skipped:
            lines.append(f"  • {s}")
    if report.warnings:
        lines.append("\n⚠️  Warnings:")
        for w in report.warnings:
            lines.append(f"  • {w}")
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="ICM cleanup after exit A/C of last active workspace (v3.7.2)"
    )
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--workspace", required=True, help="NNN-slug")
    parser.add_argument("--base-branch", default="main")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--force", action="store_true",
        help="ignore uncommitted changes (dangerous — may lose work)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = cleanup_after_close(
        args.project_root.resolve(),
        args.workspace,
        base_branch=args.base_branch,
        dry_run=args.dry_run,
        force=args.force,
    )
    print(_format_report(report))
    if report.aborted:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
