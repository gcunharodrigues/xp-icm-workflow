"""Verify CWD/write consistency across governance files (v4.0 fix).

Before v4.0, three governance files gave subagents conflicting instructions:
- L0 (CLAUDE.md.tpl) said CWD = PROJECT_ROOT
- L2 (stage 04 CONTEXT.md.tpl) said CWD = project root
- subagent-protocol.md and agent-brief-render.py said CWD = worktree root

These tests verify the v4.0 fix: all governance files agree CWD = worktree root,
NOT PROJECT_ROOT, and task reports are lead-written, not subagent-written.
"""

import re
from pathlib import Path


SKILL_ROOT = Path(__file__).parent.parent.parent

FILES_WITH_SUBAGENT_CWD = [
    "templates/workspace/CLAUDE.md.tpl",
    "templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl",
    "references/subagent-protocol.md",
    "references/agent-brief-template.md",
    "scripts/agent-brief-render.py",
]


def _read(path: Path) -> str:
    return path.read_text()


def _find_subagent_cwd_lines(content: str) -> list[str]:
    """Extract lines mentioning subagent CWD."""
    lines = []
    for i, line in enumerate(content.splitlines(), 1):
        lowered = line.lower()
        if "subagent" in lowered and ("cwd" in lowered or "worktree" in lowered):
            lines.append(f"{i}: {line.strip()}")
    return lines


def test_no_file_says_subagent_cwd_is_project_root():
    """No governance file should claim subagent CWD = PROJECT_ROOT."""
    violations = []
    for rel_path in FILES_WITH_SUBAGENT_CWD:
        path = SKILL_ROOT / rel_path
        if not path.exists():
            continue
        content = _read(path)
        for line in content.splitlines():
            lowered = line.lower()
            # Match patterns like "CWD = project root" or "CWD = {{PROJECT_ROOT}}"
            if "subagent" in lowered and ("cwd" in lowered or "worktree" in lowered):
                if re.search(
                    r"CWD\s*=\s*(`?\{\{PROJECT_ROOT\}\}`?|`?project root`?)",
                    line,
                    re.IGNORECASE,
                ):
                    # Exception: if line also contains "NOT" before PROJECT_ROOT
                    if "not {{PROJECT_ROOT}}" in lowered or "NOT `{{PROJECT_ROOT}}`" in lowered:
                        continue
                    if "NOT project root" in lowered or "NOT the project root" in lowered:
                        continue
                    if "not" in lowered and "project_root" in lowered:
                        continue
                    violations.append(f"{rel_path}:{line.strip()}")
    assert not violations, (
        f"Found {len(violations)} lines claiming subagent CWD = PROJECT_ROOT:\n"
        + "\n".join(violations)
    )


def test_no_file_tells_subagent_to_write_to_workspace_branch():
    """Subagent must NOT be told to write to workspace branch paths."""
    violations = []
    write_patterns = [
        re.compile(r"write.*workspace worktree", re.IGNORECASE),  # "write via workspace worktree" (exact phrase)
        re.compile(r"write.*task.*output.*stages/", re.IGNORECASE),
        re.compile(r"write.*\{\{PROJECT_ROOT\}\}/workspaces/", re.IGNORECASE),
        re.compile(r"git show.*workspace.*write", re.IGNORECASE),
    ]
    for rel_path in FILES_WITH_SUBAGENT_CWD:
        path = SKILL_ROOT / rel_path
        if not path.exists():
            continue
        content = _read(path)
        for line in content.splitlines():
            for pat in write_patterns:
                if pat.search(line):
                    # Skip false positives: documentation lines about worktree model
                    if "Parallel worktree model" in line:
                        continue
                    # Exceptions: lines that say "lead writes" or "lead creates"
                    if "lead writes" in line.lower() or "lead creates" in line.lower():
                        continue
                    if "lead synthesizes" in line.lower():
                        continue
                    if "Never write" in line or "NEVER write" in line:
                        continue
                    if "never writes" in line.lower():
                        continue
                    if "subagent never" in line.lower():
                        continue
                    violations.append(f"{rel_path} (pat={pat.pattern}): {line.strip()}")
                    break
    assert not violations, (
        f"Found {len(violations)} lines telling subagent to write to workspace branch:\n"
        + "\n".join(violations)
    )


def test_agent_brief_isolation_rules_consistent():
    """AGENT-BRIEF isolation rules in agent-brief-render.py and agent-brief-template.md must agree."""
    render_path = SKILL_ROOT / "scripts/agent-brief-render.py"
    template_path = SKILL_ROOT / "references/agent-brief-template.md"

    render_content = _read(render_path)
    template_content = _read(template_path)

    # Both must say "NOT the project root" / "NOT {{PROJECT_ROOT}}" for CWD
    assert "NOT the project root" in render_content, "agent-brief-render.py missing CWD negation"
    assert "NOT" in template_content and ("project root" in template_content.lower() or "{{project_root}}" in template_content.lower()), (
        "agent-brief-template.md missing CWD negation"
    )

    # Both must say lead writes / NEVER write to workspace branch
    assert "lead writes" in render_content.lower() or "lead creates" in render_content.lower(), (
        "agent-brief-render.py missing 'lead writes' directive"
    )
    assert "lead writes" in template_content.lower() or "lead creates" in template_content.lower(), (
        "agent-brief-template.md missing 'lead writes' directive"
    )

    # Neither should mention "write via workspace worktree"
    assert "write via workspace worktree" not in render_content.lower(), (
        "agent-brief-render.py still has 'write via workspace worktree'"
    )
    assert "write via workspace worktree" not in template_content.lower(), (
        "agent-brief-template.md still has 'write via workspace worktree'"
    )


def test_subagent_protocol_says_lead_writes():
    """subagent-protocol.md Section 3 must say lead writes, not subagent writes."""
    sp_path = SKILL_ROOT / "references/subagent-protocol.md"
    content = _read(sp_path)
    # Must contain lead synthesizes or lead writes
    assert "lead synthesizes" in content.lower() or "lead writes" in content.lower(), (
        "subagent-protocol.md missing lead responsibility for task reports"
    )
    # Must NOT say subagent writes the task report to workspace branch
    assert "Subagent writes" not in content, (
        "subagent-protocol.md still says 'Subagent writes'"
    )
    assert any(phrase in content.lower() for phrase in (
        "subagent never writes", "subagent must not write", "subagent NEVER writes"
    )), (
        "subagent-protocol.md missing explicit subagent write prohibition"
    )


def test_stage04_l2_says_lead_writes_task_report():
    """Stage 04 L2 step 4.5 must say lead writes task report."""
    l2_path = SKILL_ROOT / "templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl"
    content = _read(l2_path)
    assert "lead writes task report" in content.lower(), (
        "Stage 04 L2 missing 'Lead writes task report' in step 4.5"
    )
    assert "subagent never writes workspace state" in content.lower(), (
        "Stage 04 L2 missing explicit subagent write prohibition"
    )
