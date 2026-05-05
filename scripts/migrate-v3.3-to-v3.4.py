"""Migration script v3.3.x -> v3.4.x (cross-branch worktree model).

Detects workspaces created by skill v3.3.x and applies idempotent migration:

  1. Creates `.icm-main/` linked worktree pointing to `base_branch`.
  2. Adds `.icm-main/` to `.gitignore` in project_root.
  3. Ensures `docs/decisions/.keep`, `docs/lessons.md`, `docs/tech_debt.md`
     exist on base branch (commits if absent).
  4. Updates `icm_skill_version: v3.3.x -> v3.4.1` in workspace L0.
  5. (Optional --update-paths) Substring replace
     `{{PROJECT_ROOT}}/docs/` -> `{{PROJECT_ROOT}}/.icm-main/docs/` in L0/L2
     CONTEXT.md.

CLI:
  python scripts/migrate-v3.3-to-v3.4.py --project-root <path> [--workspace <NNN-slug>] [--update-paths] [--dry-run]

Idempotent: re-running causes no harm. Workspaces already on v3.4.x are skipped.

Doc: references/worktree-model.md.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SKILL_VERSION_TARGET = "3.4.1"

VERSION_RE = re.compile(r'^icm_skill_version:\s*"?(?P<ver>[^"\s]+)"?\s*$', re.MULTILINE)


class MigrationError(Exception):
    pass


def _run_git(args: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def detect_workspace_version(claude_md_path: Path) -> str | None:
    """Read L0 frontmatter, return icm_skill_version or None if absent."""
    if not claude_md_path.is_file():
        return None
    text = claude_md_path.read_text(encoding="utf-8")
    match = VERSION_RE.search(text)
    return match.group("ver") if match else None


def is_v3_3_x(version: str | None) -> bool:
    """True if version matches v3.3.x (or absent — likely pre-3.3)."""
    if version is None:
        return True  # old workspaces without the field
    v = version.lstrip("v")
    parts = v.split(".")
    return len(parts) >= 2 and parts[0] == "3" and parts[1] == "3"


def discover_workspaces(project_root: Path) -> list[Path]:
    """List workspaces under project_root/workspaces/NNN-slug/ that have CLAUDE.md."""
    ws_root = project_root / "workspaces"
    if not ws_root.is_dir():
        return []
    found: list[Path] = []
    for entry in sorted(ws_root.iterdir()):
        if entry.is_dir() and (entry / "CLAUDE.md").is_file():
            if re.match(r"^\d{3}-", entry.name):
                found.append(entry)
    return found


def update_gitignore(project_root: Path, dry_run: bool) -> bool:
    """Add '.icm-main/' to .gitignore if absent. Returns True if changed."""
    gi = project_root / ".gitignore"
    target = ".icm-main/"
    existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
    lines = {ln.strip() for ln in existing.splitlines() if ln.strip()}
    if target in lines:
        return False
    if dry_run:
        return True
    new_content = existing
    if new_content and not new_content.endswith("\n"):
        new_content += "\n"
    new_content += target + "\n"
    gi.write_text(new_content, encoding="utf-8")
    return True


def ensure_base_branch_docs(project_root: Path, base_branch: str, dry_run: bool) -> bool:
    """If base_branch is checked out: create docs/ scaffold + commit if something changed.

    Caller must have switched to base_branch before calling OR already be on it.
    Returns True if any file was created.
    """
    docs = project_root / "docs"
    decisions = docs / "decisions"
    keep = decisions / ".keep"
    lessons = docs / "lessons.md"
    tech_debt = docs / "tech_debt.md"

    changed = False
    if not keep.exists():
        changed = True
        if not dry_run:
            decisions.mkdir(parents=True, exist_ok=True)
            keep.touch()
    if not lessons.exists():
        changed = True
        if not dry_run:
            lessons.write_text(
                "# Lessons Learned\n\nRegisto append-only de lições por workspace e iteração.\n\n",
                encoding="utf-8",
            )
    if not tech_debt.exists():
        changed = True
        if not dry_run:
            tech_debt.write_text(
                "# Tech Debt\n\nRegisto append-only de débitos técnicos.\n\n",
                encoding="utf-8",
            )

    if changed and not dry_run:
        _run_git(["add", "docs/decisions/.keep", "docs/lessons.md", "docs/tech_debt.md"],
                 cwd=project_root, check=False)
        _run_git(
            ["commit", "--no-verify", "-m",
             "chore(icm): backfill docs/ on base for ICM cross-branch model (v3.4.0 migration)"],
            cwd=project_root,
            check=False,
        )
    return changed


def setup_worktree(project_root: Path, base_branch: str, dry_run: bool) -> bool:
    """Create `.icm-main/` worktree if absent. Returns True if created."""
    wt = project_root / ".icm-main"
    if wt.exists():
        # Validate it is a genuine linked worktree
        try:
            res = _run_git(
                ["rev-parse", "--show-toplevel"],
                cwd=wt,
                check=False,
            )
            if res.returncode == 0:
                toplevel = Path(res.stdout.strip()).resolve()
                if toplevel == wt.resolve():
                    return False  # idempotente
        except Exception:
            pass
        raise MigrationError(
            f".icm-main/ exists at {project_root} but is not a linked worktree. "
            "Remove manually or run `git worktree repair`."
        )
    if dry_run:
        return True
    _run_git(["worktree", "add", str(wt), base_branch], cwd=project_root)
    return True


def update_l0_version(claude_md: Path, dry_run: bool) -> bool:
    """Replace icm_skill_version in L0 frontmatter. Returns True if changed."""
    text = claude_md.read_text(encoding="utf-8")
    new_text, n = VERSION_RE.subn(
        f'icm_skill_version: "{SKILL_VERSION_TARGET}"',
        text,
        count=1,
    )
    if n == 0 or new_text == text:
        return False
    if not dry_run:
        claude_md.write_text(new_text, encoding="utf-8")
    return True


def update_paths_in_file(path: Path, project_root: Path, dry_run: bool) -> bool:
    """Substring replace `<project_root>/docs/` -> `<project_root>/.icm-main/docs/`.

    Applied to CLAUDE.md (L0) and stages/*/CONTEXT.md (L2). Idempotent: if the
    new path already appears, no-op. Returns True if anything changed.
    """
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    pr_str = str(project_root).replace("\\", "/")
    old = f"{pr_str}/docs/"
    new = f"{pr_str}/.icm-main/docs/"
    if old not in text:
        return False
    new_text = text.replace(old, new)
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return True


def migrate_workspace(
    workspace_dir: Path,
    project_root: Path,
    *,
    update_paths: bool,
    dry_run: bool,
) -> dict[str, bool]:
    """Run migration on ONE workspace. Returns dict of detected changes."""
    claude_md = workspace_dir / "CLAUDE.md"
    version = detect_workspace_version(claude_md)
    if not is_v3_3_x(version):
        return {"skipped": True, "reason": f"version={version}"}  # type: ignore[dict-item]

    changes: dict[str, bool] = {"skipped": False}

    # 1. L0 version bump
    changes["l0_version_bumped"] = update_l0_version(claude_md, dry_run)

    # 2. Path replace (opcional)
    if update_paths:
        path_changes = False
        path_changes |= update_paths_in_file(claude_md, project_root, dry_run)
        for stage_ctx in (workspace_dir / "stages").glob("*/CONTEXT.md"):
            path_changes |= update_paths_in_file(stage_ctx, project_root, dry_run)
        changes["paths_updated"] = path_changes

    return changes


def migrate_project(
    project_root: Path,
    *,
    workspace_filter: str | None = None,
    update_paths: bool = False,
    dry_run: bool = False,
) -> dict[str, dict]:
    """Migrate ALL v3.3.x workspaces in project_root. Idempotent."""
    if not (project_root / ".git").exists():
        raise MigrationError(f"project_root has no .git: {project_root}")

    workspaces = discover_workspaces(project_root)
    if workspace_filter:
        workspaces = [w for w in workspaces if w.name == workspace_filter]
        if not workspaces:
            raise MigrationError(f"workspace not found: {workspace_filter}")

    if not workspaces:
        return {"_global": {"workspaces_found": 0}}

    # Detect base_branch (assumes first workspace represents it via L0).
    first_l0 = (workspaces[0] / "CLAUDE.md").read_text(encoding="utf-8")
    base_match = re.search(r'^base_branch:\s*"?([^"\s]+)"?', first_l0, re.MULTILINE)
    base_branch = base_match.group(1) if base_match else "main"

    current_branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=project_root).stdout.strip()

    summary: dict[str, dict] = {"_global": {}}

    # 1. Ensure docs/ scaffolding on base_branch (must be on base)
    needs_switch = current_branch != base_branch
    if needs_switch and not dry_run:
        _run_git(["checkout", base_branch], cwd=project_root)
    docs_changed = ensure_base_branch_docs(project_root, base_branch, dry_run)
    summary["_global"]["docs_scaffolded"] = docs_changed

    # 2. Setup worktree (branch-independent — git worktree add works from any branch)
    if needs_switch and not dry_run:
        # Switch back to current branch before creating worktree (linked worktree
        # only works if base_branch is not already checked out)
        _run_git(["checkout", current_branch], cwd=project_root)
    worktree_changed = setup_worktree(project_root, base_branch, dry_run)
    summary["_global"]["worktree_setup"] = worktree_changed

    # 3. .gitignore update
    gi_changed = update_gitignore(project_root, dry_run)
    summary["_global"]["gitignore_updated"] = gi_changed

    # 4. Per-workspace L0/L2 update
    for ws in workspaces:
        summary[ws.name] = migrate_workspace(
            ws, project_root,
            update_paths=update_paths,
            dry_run=dry_run,
        )

    return summary


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Migrate ICM workspaces v3.3.x -> v3.4.x.")
    p.add_argument("--project-root", required=True, help="Path to project with workspaces/")
    p.add_argument("--workspace", default=None, help="Filter to 1 workspace (NNN-slug). Default: all.")
    p.add_argument("--update-paths", action="store_true",
                   help="Substring replace <project_root>/docs/ -> <project_root>/.icm-main/docs/ in L0/L2.")
    p.add_argument("--dry-run", action="store_true", help="Detect only, do not modify.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    project_root = Path(args.project_root).resolve()
    try:
        summary = migrate_project(
            project_root,
            workspace_filter=args.workspace,
            update_paths=args.update_paths,
            dry_run=args.dry_run,
        )
    except MigrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    import json
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
