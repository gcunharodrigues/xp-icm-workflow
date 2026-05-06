"""Verify task report write path is reachable from workspace branch (v4.0 fix).

Before v4.0, the subagent was told to write task reports to workspace branch
paths from an isolated worktree on a different branch — physically impossible
without git worktree manipulation.

v4.0 fix: lead writes task reports from workspace branch checkout, synthesizing
from Agent tool output. This test verifies the write path is documented as
lead responsibility and reachable.
"""

from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent.parent


def test_lead_is_on_workspace_branch_when_writing_task_reports():
    """Lead CWD = PROJECT_ROOT, branch = workspace/<NNN-slug>. Can write to workspace/ path."""
    l0 = SKILL_ROOT / "templates/workspace/CLAUDE.md.tpl"
    assert l0.exists()
    content = l0.read_text()

    # Lead's session CWD (v4.0: grouped listing)
    assert "04" in content and "CWD = `{{PROJECT_ROOT}}` (workspace branch checkout)" in content, (
        "L0 must state lead CWD = PROJECT_ROOT on workspace branch"
    )


def test_task_report_output_path_is_on_workspace_branch():
    """Task report output path lives under workspaces/ which is on workspace branch."""
    l2 = SKILL_ROOT / "templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl"
    assert l2.exists()
    content = l2.read_text()

    # The task report path must be under workspaces/NNN/...
    assert "workspaces/{{WORKSPACE}}/stages/04_implementation_waves/output/wave" in content, (
        "L2 missing correct task report output path on workspace branch"
    )


def test_lead_merge_step_returns_to_workspace_branch():
    """After merge, lead must return to workspace branch before writing state."""
    sp = SKILL_ROOT / "references/subagent-protocol.md"
    assert sp.exists()
    content = sp.read_text()

    # Lead returns to workspace branch after merge
    assert "git checkout workspace" in content, (
        "subagent-protocol.md must instruct lead to return to workspace branch after merge"
    )


def test_no_subagent_write_path_conflict():
    """Verify no governance file tells subagent to write to both worktree AND workspace branch."""
    files_to_check = [
        SKILL_ROOT / "scripts/agent-brief-render.py",
        SKILL_ROOT / "references/agent-brief-template.md",
        SKILL_ROOT / "references/4-block-contract-template.md",
    ]
    conflict_lines = []
    for path in files_to_check:
        if not path.exists():
            continue
        content = path.read_text()
        in_isolation = False
        for line in content.splitlines():
            if "Isolation rules" in line or "isolation rules" in line:
                in_isolation = True
            if "Write code ONLY" in line or "NEVER write via absolute" in line:
                # Good — this is correct isolation
                pass
            if "write task output" in line.lower() and "never" not in line.lower():
                if "lead" not in line.lower():
                    conflict_lines.append(f"{path.name}: {line.strip()}")

    assert not conflict_lines, (
        f"Found {len(conflict_lines)} lines with subagent write to workspace path:\n"
        + "\n".join(conflict_lines)
    )
