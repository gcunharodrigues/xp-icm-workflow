"""Tests v3.5.0 — stage 04 wave protocol gaps fix.

Cobertura:
- CLAUDE.md root drift fixed (linha "no worktrees" removida)
- L2 template tem branch creation lead-owned
- L2 tem decision matrix --force
- L2 tem wave-reviewer isolation spec
- L2 tem qa_loops_used tracking
- L2 tem BLOCKED_HITL status
- L2 tem sort buffer pre-merge
- conflict-resolution-protocol.md existe + 3 paths A/B/C
- ci-rollback-protocol.md existe + diagnose-first
- L2 tem .icm-main presence check
- wave-execution-protocol.md existe + 12 passos
- Changelog v3.5.0 entry presente
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
    """Gap 1: linha 'no worktrees' não deve mais existir."""
    assert "no worktrees" not in claude_root_text, \
        "CLAUDE.md root ainda tem linha stale 'no worktrees'"
    assert "isolation: \"worktree\"" in claude_root_text, \
        "CLAUDE.md root deve mencionar isolation: worktree"


def test_l2_branch_creation_lead_owned(l2_text):
    """Gap 2: passo 2 deve declarar lead cria branch antes do spawn."""
    assert "Lead cria branch ANTES do spawn" in l2_text or \
           "git branch wave-" in l2_text, \
           "L2 deve documentar branch creation lead-owned"


def test_l2_force_decision_matrix(l2_text):
    """Gap 8: passo 11 deve ter decision matrix --force."""
    assert "Decision matrix `--force`" in l2_text or \
           "auto_qa_passed: true" in l2_text, \
           "L2 deve ter decision matrix --force"
    assert "JAMAIS usar `-D`" in l2_text or \
           "não usar `-D`" in l2_text, \
           "L2 deve proibir -D em branch delete"


def test_l2_wave_reviewer_isolation_spec(l2_text):
    """Gap 3: passo 8 deve declarar reviewer SEM worktree."""
    assert "SEM `isolation: \"worktree\"`" in l2_text or \
           "git show wave-" in l2_text, \
           "L2 deve declarar wave-reviewer sem worktree (git show)"


def test_l2_qa_loops_tracking(l2_text):
    """Gap 4: subagente grava qa_loops_used no task report."""
    assert "qa_loops_used" in l2_text, \
        "L2 deve declarar qa_loops_used field"


def test_l2_blocked_hitl_status(l2_text):
    """Gap 7: BLOCKED_HITL status canônico presente."""
    assert "BLOCKED_HITL" in l2_text, \
        "L2 deve declarar status BLOCKED_HITL"
    assert "Task-level HITL" in l2_text or \
           "task-level granularity" in l2_text.lower(), \
           "L2 deve documentar HITL task-level"


def test_l2_sort_buffer(l2_text):
    """Gap 5: passo 7 declara sort por plan order pré-merge."""
    assert "ordem do plan" in l2_text and \
           ("bufferiza" in l2_text or "buferizada" in l2_text), \
           "L2 deve declarar sort buffer pré-merge"


def test_l2_pre_wave_sha(l2_text):
    """Gap 9 dependência: passo 1 grava pre_wave_sha."""
    assert "pre_wave_sha" in l2_text, \
        "L2 passo 1 deve gravar pre_wave_sha em L1 history"


def test_l2_icm_main_conditional(l2_text):
    """Gap 10: .icm-main sync condicional via presence check."""
    assert "git worktree list" in l2_text and \
           ".icm-main" in l2_text, \
           "L2 deve checar presença de .icm-main antes de pull"


def test_conflict_protocol_exists():
    """Gap 6: conflict-resolution-protocol.md existe + 3 paths."""
    assert CONFLICT_DOC.exists(), "conflict-resolution-protocol.md ausente"
    text = CONFLICT_DOC.read_text(encoding="utf-8")
    for path in ("resolvido", "abort task", "abort wave"):
        assert path in text, f"conflict protocol falta path '{path}'"
    assert "git merge --abort" in text
    assert "pre_wave_sha" in text or "reset --hard" in text


def test_ci_rollback_protocol_exists():
    """Gap 9: ci-rollback-protocol.md existe + diagnose-first + 3 opções."""
    assert ROLLBACK_DOC.exists(), "ci-rollback-protocol.md ausente"
    text = ROLLBACK_DOC.read_text(encoding="utf-8")
    assert "diagnose-protocol" in text or "diagnose" in text.lower(), \
        "rollback protocol deve referenciar diagnose-protocol"
    for opt in ("redo wave", "redo task", "abandon"):
        assert opt in text, f"rollback protocol falta opção '{opt}'"
    assert "pre_wave_sha" in text


def test_wave_execution_protocol_canonical_exists():
    """Task 12: wave-execution-protocol.md existe + 12 passos."""
    assert WAVE_PROTOCOL_DOC.exists(), "wave-execution-protocol.md ausente"
    text = WAVE_PROTOCOL_DOC.read_text(encoding="utf-8")
    assert "12 passos" in text or "12-passos" in text or \
           "## Pipeline" in text, \
           "wave-execution-protocol deve listar pipeline"
    for status in ("BLOCKED_HITL", "BLOCKED_ERROR", "IN_PROGRESS"):
        assert status in text, f"wave-execution-protocol falta status {status}"


def test_skill_version_at_least_v3_5_0():
    """Task 2: SKILL.md bumped para v3.5.0+. Aceita versões mais recentes
    pq esse teste cobria o bump original v3.5.0; versões futuras seguem
    seu próprio gate (test_no_drift garante consistência cross-file)."""
    text = SKILL_MD.read_text(encoding="utf-8")
    import re
    match = re.search(r"# xp-icm-workflow v(\d+)\.(\d+)\.(\d+)", text)
    assert match, "SKILL.md deve declarar versão no header"
    major, minor, patch = map(int, match.groups())
    assert (major, minor, patch) >= (3, 5, 0), \
        f"SKILL.md em versão {major}.{minor}.{patch} < 3.5.0"


def test_changelog_v3_5_0_entry():
    """Task 2/14: changelog tem entrada v3.5.0."""
    text = CHANGELOG.read_text(encoding="utf-8")
    assert "## v3.5.0" in text, "changelog deve ter ## v3.5.0"
    assert "Stage 04 protocol gaps fix" in text or \
           "wave protocol" in text.lower(), \
           "changelog v3.5.0 deve descrever escopo"
