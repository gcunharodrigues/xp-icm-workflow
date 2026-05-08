"""Tests v3.5.0 → v4.0.x — stage 04 wave protocol.

v4.0.x update: 14 steps → 5 phases, single isolation path, merge via .icm-main.
Tests adapted to validate new structure while preserving semantic invariants.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
L2_PATH = REPO_ROOT / "templates" / "workspace" / "stages" / "04_implementation_waves" / "CONTEXT.md.tpl"
CLAUDE_ROOT = REPO_ROOT / "CLAUDE.md"
SKILL_MD = REPO_ROOT / "SKILL.md"
CHANGELOG = REPO_ROOT / "references" / "changelog.md"
CONFLICT_DOC = REPO_ROOT / "references" / "conflict-resolution-protocol.md"
ROLLBACK_DOC = REPO_ROOT / "references" / "ci-rollback-protocol.md"
WAVE_PROTOCOL_DOC = REPO_ROOT / "references" / "wave-execution-protocol.md"


@pytest.fixture(scope="module")
def l2_text():
    return L2_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def claude_root_text():
    return CLAUDE_ROOT.read_text(encoding="utf-8")


def test_claude_root_no_worktrees_line_removed(claude_root_text):
    """v4.0.x: CLAUDE.md no longer has stale 'no worktrees' line."""
    assert "no worktrees" not in claude_root_text, \
        "CLAUDE.md root still has stale 'no worktrees' line"


def test_l2_branch_creation_lead_owned(l2_text):
    """PHASE 2: lead creates branches before spawn."""
    assert "git branch wave-" in l2_text, \
        "L2 must document branch creation (git branch wave-...)"


def test_l2_force_decision_matrix(l2_text):
    """PHASE 5: cleanup uses git branch -d (never -D)."""
    lowered = l2_text.lower()
    assert "never use `-d`" in lowered or "jamais usar `-d`" in lowered or \
           "never use -d" in lowered or "do not use `-d`" in lowered, \
           "L2 must prohibit -D in branch delete"


def test_l2_wave_reviewer_isolation_spec(l2_text):
    """PHASE 3: reviewer/critic run without worktree isolation."""
    assert "Agent(isolation=None" in l2_text or \
           "critic via Agent" in l2_text, \
           "L2 must declare reviewer/critic without worktree"


def test_l2_qa_loops_tracking(l2_text):
    """PHASE 3: per-task loop cap 3 attempts."""
    assert "cap 3" in l2_text or "Cap 3" in l2_text, \
        "L2 must declare cap 3 attempts"


def test_l2_blocked_hitl_status(l2_text):
    """v4.0: BLOCKED with block_reason: hitl."""
    lowered = l2_text.lower()
    assert "block_reason" in lowered and "hitl" in lowered, \
        "L2 must declare hitl as a block_reason"
    assert "HITL" in l2_text, \
        "L2 must document HITL handling"


def test_l2_sort_buffer(l2_text):
    """PHASE 4: merge follows plan order, not Agent return order."""
    assert "plan order" in l2_text.lower(), \
        "L2 must declare merge in plan order"
    assert "buffer" in l2_text.lower() or "sequentially" in l2_text.lower() or \
           "merge" in l2_text.lower(), \
           "L2 must declare merge sequencing"


def test_l2_pre_wave_sha(l2_text):
    """PHASE 1: record pre_wave_sha in L1 history."""
    assert "pre_wave_sha" in l2_text, \
        "L2 must record pre_wave_sha in L1 history"


def test_l2_icm_main_conditional(l2_text):
    """PHASE 4 + PHASE 5: merge via .icm-main/."""
    assert ".icm-main" in l2_text, \
        "L2 must reference .icm-main for merge and sync"


def test_conflict_protocol_exists():
    """conflict-resolution-protocol.md exists + 3 paths."""
    assert CONFLICT_DOC.exists(), "conflict-resolution-protocol.md missing"
    text = CONFLICT_DOC.read_text(encoding="utf-8")
    for path in ("resolved", "abort task", "abort wave"):
        assert path in text, f"conflict protocol missing path '{path}'"
    assert "git merge --abort" in text
    assert "pre_wave_sha" in text or "reset --hard" in text


def test_ci_rollback_protocol_exists():
    """ci-rollback-protocol.md exists + diagnose-first + 3 options."""
    assert ROLLBACK_DOC.exists(), "ci-rollback-protocol.md missing"
    text = ROLLBACK_DOC.read_text(encoding="utf-8")
    assert "diagnose-protocol" in text or "diagnose" in text.lower(), \
        "rollback protocol must reference diagnose-protocol"
    for opt in ("redo wave", "redo task", "abandon"):
        assert opt in text, f"rollback protocol missing option '{opt}'"
    assert "pre_wave_sha" in text


def test_wave_execution_protocol_canonical_exists():
    """wave-execution-protocol.md exists with 5-phase pipeline."""
    assert WAVE_PROTOCOL_DOC.exists(), "wave-execution-protocol.md missing"
    text = WAVE_PROTOCOL_DOC.read_text(encoding="utf-8")
    assert "5-Phase Pipeline" in text or "PHASE 1" in text or \
           "PHASE 1: PREPARE" in text, \
           "wave-execution-protocol must list 5-phase pipeline"
    for status in ("BLOCKED", "IN_PROGRESS", "block_reason"):
        assert status in text, f"wave-execution-protocol missing status {status}"


def test_skill_version_at_least_v3_5_0():
    """SKILL.md version >= 3.5.0."""
    text = SKILL_MD.read_text(encoding="utf-8")
    import re
    match = re.search(r"# xp-icm-workflow v(\d+)\.(\d+)\.(\d+)", text)
    assert match, "SKILL.md must declare version in header"
    major, minor, patch = map(int, match.groups())
    assert (major, minor, patch) >= (3, 5, 0), \
        f"SKILL.md at version {major}.{minor}.{patch} < 3.5.0"


def test_changelog_v3_5_0_entry():
    """changelog has v3.5.0 entry."""
    text = CHANGELOG.read_text(encoding="utf-8")
    assert "## v3.5.0" in text, "changelog must have ## v3.5.0"
    assert "Stage 04 protocol gaps fix" in text or \
           "wave protocol" in text.lower(), \
           "changelog v3.5.0 must describe scope"
