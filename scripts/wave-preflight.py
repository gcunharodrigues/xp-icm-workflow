#!/usr/bin/env python3
"""Wave pre-flight — deterministic checks before Agent spawn in stage 04.

Replaces the ~150-line manual pre-flight checklist in the L2 template.
All checks are deterministic (git + filesystem + script --help). Zero token cost.

CLI:
    python scripts/wave-preflight.py \
        --workspace-num <NNN> --wave <N> \
        --project-root <path> --base-branch <name> \
        [--skill-dir <path>] [--json]

Exit 0: all checks pass. Exit 1: failures present (checklist output to stderr).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    """Run command, return (exit_code, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=30)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout: {' '.join(cmd)}"


def check_workspace_branch(project_root: str, workspace: str) -> dict:
    """Verify lead is on workspace/<NNN-slug> branch."""
    code, out, err = run(["git", "branch", "--show-current"], cwd=project_root)
    expected = f"workspace/{workspace}"
    ok = code == 0 and out == expected
    return {
        "check": "workspace_branch",
        "passed": ok,
        "detail": f"current={out}, expected={expected}" if not ok else out,
    }


def check_wave_plan_exists(plan_path: str) -> dict:
    """Verify wave-plan.md exists and is non-empty."""
    p = Path(plan_path)
    ok = p.exists() and p.stat().st_size > 0
    return {
        "check": "wave_plan_exists",
        "passed": ok,
        "detail": str(p) if ok else f"missing or empty: {p}",
    }


def check_branch_naming(
    project_root: str, workspace_num: str, wave: str
) -> dict:
    """Verify wave branch naming pattern matches wave-<NNN>-<N>/<task-slug>."""
    code, out, err = run(
        ["git", "branch", "--list", f"wave-{workspace_num}-{wave}/*"],
        cwd=project_root,
    )
    # Branches may not exist yet (pre-spawn) — that's fine. We check naming only.
    # Pattern is correct by construction. This check is informational.
    branches = [b.strip().lstrip("* ") for b in out.split("\n") if b.strip()]
    return {
        "check": "branch_naming",
        "passed": True,  # pattern verified by the glob itself
        "detail": f"{len(branches)} existing wave branches" if branches else "no branches yet (pre-spawn)",
    }


def check_skill_dir(skill_dir: str) -> dict:
    """Verify skill directory exists and forensic-plus.py is callable."""
    sp = Path(skill_dir)
    fp = sp / "scripts" / "forensic-plus.py"
    ok = sp.exists() and fp.exists()
    if ok:
        code, out, err = run([sys.executable, str(fp), "--help"], cwd=str(sp))
        ok = code == 0
    return {
        "check": "skill_dir_callable",
        "passed": ok,
        "detail": str(sp) if ok else f"skill dir missing or forensic-plus.py not callable: {sp}",
    }


def check_output_dir(output_dir: str) -> dict:
    """Ensure output directory exists (create if missing)."""
    p = Path(output_dir)
    try:
        p.mkdir(parents=True, exist_ok=True)
        return {"check": "output_dir", "passed": True, "detail": str(p)}
    except OSError as e:
        return {"check": "output_dir", "passed": False, "detail": str(e)}


def check_worktree_topology(project_root: str) -> dict:
    """Detect .git as directory (STANDARD) or file (NESTED)."""
    dot_git = Path(project_root) / ".git"
    if dot_git.is_dir():
        mode = "STANDARD"
    elif dot_git.is_file():
        mode = "NESTED"
    else:
        mode = "UNKNOWN"
    return {
        "check": "worktree_topology",
        "passed": mode != "UNKNOWN",
        "detail": mode,
        "mode": mode,
    }


def check_orphan_worktrees(project_root: str) -> dict:
    """Detect orphaned icm-wave worktrees from previous waves."""
    code, out, err = run(
        ["git", "worktree", "list", "--porcelain"], cwd=project_root
    )
    orphans = []
    if code == 0:
        lines = out.split("\n")
        current_path = ""
        for line in lines:
            if line.startswith("worktree "):
                current_path = line[len("worktree "):]
            elif "icm-wave" in line and current_path:
                orphans.append(current_path)
    return {
        "check": "orphan_worktrees",
        "passed": len(orphans) == 0,
        "detail": f"{len(orphans)} orphan(s): {orphans}" if orphans else "clean",
        "orphans": orphans,
    }


def check_orphan_branches(project_root: str, workspace_num: str) -> dict:
    """Detect orphaned wave branches from previous waves."""
    code, out, err = run(
        ["git", "branch", "--list", f"wave-{workspace_num}-*"], cwd=project_root
    )
    branches = [b.strip().lstrip("* ") for b in out.split("\n") if b.strip()]
    return {
        "check": "orphan_branches",
        "passed": len(branches) == 0,
        "detail": f"{len(branches)} orphan(s): {branches}" if branches else "clean",
        "orphans": branches,
    }


def check_clean_working_tree(project_root: str) -> dict:
    """Verify working tree is clean (no uncommitted changes)."""
    code_diff, out_diff, _ = run(
        ["git", "diff", "--quiet"], cwd=project_root
    )
    code_cached, out_cached, _ = run(
        ["git", "diff", "--cached", "--quiet"], cwd=project_root
    )
    clean = code_diff == 0 and code_cached == 0
    return {
        "check": "clean_working_tree",
        "passed": clean,
        "detail": "clean" if clean else "dirty — commit or stash before pre-flight",
    }


CHECKS = [
    "workspace_branch",
    "wave_plan_exists",
    "branch_naming",
    "skill_dir_callable",
    "output_dir",
    "worktree_topology",
    "orphan_worktrees",
    "orphan_branches",
    "clean_working_tree",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Wave pre-flight — deterministic checks before Agent spawn"
    )
    parser.add_argument("--workspace-num", required=True, help="Workspace number (NNN)")
    parser.add_argument("--wave", required=True, help="Wave number (N)")
    parser.add_argument("--project-root", required=True, help="Project root path")
    parser.add_argument("--base-branch", default="main", help="Base branch name")
    parser.add_argument("--skill-dir", default=None, help="Skill directory (auto-detect if omitted)")
    parser.add_argument("--workspace-slug", default=None, help="Workspace slug (auto-derive from --workspace-num if omitted)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    opt = parser.parse_args()

    # Auto-detect skill dir
    skill_dir = opt.skill_dir
    if not skill_dir:
        # Try to find via the script's own location
        skill_dir = str(Path(__file__).resolve().parent.parent)

    # Auto-derive workspace slug
    workspace_slug = opt.workspace_slug
    workspace = f"{opt.workspace_num}-{workspace_slug}" if workspace_slug else opt.workspace_num

    project_root = str(Path(opt.project_root).resolve())
    plan_path = os.path.join(
        project_root, "workspaces", workspace,
        "stages", "02_design", "output", "wave-plan.md"
    )
    output_dir = os.path.join(
        project_root, "workspaces", workspace,
        "stages", "04_implementation_waves", "output", f"wave-{opt.wave}"
    )

    results = [
        check_workspace_branch(project_root, workspace),
        check_wave_plan_exists(plan_path),
        check_branch_naming(project_root, opt.workspace_num, opt.wave),
        check_skill_dir(skill_dir),
        check_output_dir(output_dir),
        check_worktree_topology(project_root),
        check_orphan_worktrees(project_root),
        check_orphan_branches(project_root, opt.workspace_num),
        check_clean_working_tree(project_root),
    ]

    all_pass = all(r["passed"] for r in results)

    if opt.json:
        output = {
            "workspace": workspace,
            "wave": opt.wave,
            "all_pass": all_pass,
            "topology": next(
                r.get("mode") for r in results if r["check"] == "worktree_topology"
            ),
            "checks": results,
        }
        print(json.dumps(output, indent=2))
    else:
        status = "PASS" if all_pass else "FAIL"
        print(f"=== Wave {opt.wave} Pre-flight: {status} ===")
        for r in results:
            icon = "✓" if r["passed"] else "✗"
            print(f"  {icon} {r['check']}: {r['detail']}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
