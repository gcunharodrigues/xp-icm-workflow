"""Tests for scripts/agent-brief-render.py (T1.2).

v4.0.x: single isolation mode — all subagents use manual worktrees in
.claude/worktrees/icm-wave-<NNN>-<N>-<slug>/.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent.parent
_MODULE_PATH = _REPO / "scripts" / "agent-brief-render.py"
_spec = importlib.util.spec_from_file_location("agent_brief_render", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
agent_brief_render = importlib.util.module_from_spec(_spec)
sys.modules["agent_brief_render"] = agent_brief_render
_spec.loader.exec_module(agent_brief_render)


SAMPLE_PLAN = """\
# Plan — workspace 042-test

## Test Strategy

(omitido para teste)

## Task implementar-jwt-refresh: Refresh tokens JWT com TTL 7 dias

**Type:** AFK
**Files touched:** src/auth/jwt.ts, src/auth/jwt.test.ts

### WHAT
Implementar refresh tokens JWT com TTL de 7 dias.

### HOW
Adicionar endpoint POST /auth/refresh que aceita refresh_token e
retorna novo access_token. Validar refresh_token via assinatura HMAC.

### OUT OF SCOPE
Não invalidar refresh tokens ainda válidos. Não tocar em
mecanismo de session existente.

### VALIDATION
Test que envia refresh_token válido retorna 200 com novo
access_token. Test que envia token expirado retorna 401.

## Task choose-orm: Escolher ORM (HITL)

**Type:** HITL
**Files touched:** docs/decisions/0007-orm.md

### WHAT
Escolher ORM entre Prisma, Drizzle e raw SQL.

### HOW
Avaliar trade-offs de type safety, performance, lock-in.

### OUT OF SCOPE
Não implementar antes do humano decidir.

### VALIDATION
ADR criado em docs/decisions/0007-orm.md.
"""


def test_extract_task_section_found():
    section = agent_brief_render.extract_task_section(SAMPLE_PLAN, "implementar-jwt-refresh")
    assert "implementar-jwt-refresh" in section
    assert "AFK" in section
    assert "choose-orm" not in section


def test_extract_task_section_last_task():
    section = agent_brief_render.extract_task_section(SAMPLE_PLAN, "choose-orm")
    assert "choose-orm" in section
    assert "HITL" in section


def test_extract_task_section_not_found():
    with pytest.raises(agent_brief_render.AgentBriefError):
        agent_brief_render.extract_task_section(SAMPLE_PLAN, "ghost-task")


def test_parse_4block_extracts_all_sections():
    section = agent_brief_render.extract_task_section(SAMPLE_PLAN, "implementar-jwt-refresh")
    parsed = agent_brief_render.parse_4block(section)
    assert parsed["type"] == "AFK"
    assert "src/auth/jwt.ts" in parsed["files_touched"]
    assert "Implementar refresh tokens" in parsed["what"]
    assert "POST /auth/refresh" in parsed["how"]
    assert "session existente" in parsed["out_of_scope"]
    assert "200 com novo" in parsed["validation"]


def test_parse_4block_hitl_type():
    section = agent_brief_render.extract_task_section(SAMPLE_PLAN, "choose-orm")
    parsed = agent_brief_render.parse_4block(section)
    assert parsed["type"] == "HITL"


def test_render_brief_contains_all_sections():
    section = agent_brief_render.extract_task_section(SAMPLE_PLAN, "implementar-jwt-refresh")
    parsed = agent_brief_render.parse_4block(section)
    brief = agent_brief_render.render_brief(
        "implementar-jwt-refresh", parsed, [],
        workspace_num="042", wave_num=1,
        project_root="/tmp/test", base_branch="main",
    )

    assert "Agent Brief — implementar-jwt-refresh" in brief
    assert "HARD GATES" in brief
    assert "GATE 1" in brief
    assert "GATE 2" in brief
    assert "GATE 3" in brief
    assert "**Type:** AFK" in brief
    assert "**Summary:**" in brief
    assert "**Desired behavior:**" in brief
    assert "**Key interfaces:**" in brief
    assert "**Acceptance criteria:**" in brief
    assert "**Out of scope:**" in brief
    assert "Isolation rules" in brief


def test_render_brief_with_adrs():
    section = agent_brief_render.extract_task_section(SAMPLE_PLAN, "implementar-jwt-refresh")
    parsed = agent_brief_render.parse_4block(section)
    brief = agent_brief_render.render_brief(
        "implementar-jwt-refresh", parsed,
        ["0001-stack.md", "0004-auth.md"],
        workspace_num="042", wave_num=1,
        project_root="/tmp/test", base_branch="main",
    )
    assert "Applicable ADRs" in brief
    assert "0001-stack.md" in brief
    assert "0004-auth.md" in brief


def test_warn_if_brittle_detects_absolute_paths():
    bad_brief = (
        "## Agent Brief\n"
        "Modify /home/user/project/src/foo.ts to fix the bug.\n"
    )
    warnings = agent_brief_render.warn_if_brittle(bad_brief)
    assert any("Absolute paths" in w for w in warnings)


def test_warn_if_brittle_detects_line_numbers():
    bad_brief = (
        "## Agent Brief\n"
        "Edit handler.ts:42 to add the new logic.\n"
    )
    warnings = agent_brief_render.warn_if_brittle(bad_brief)
    assert any("Line numbers" in w for w in warnings)


def test_warn_if_brittle_clean():
    clean_brief = (
        "## Agent Brief\n"
        "Add `refreshToken()` method to the AuthService interface.\n"
        "Acceptance: test that valid token returns new access token.\n"
    )
    warnings = agent_brief_render.warn_if_brittle(clean_brief)
    assert warnings == []


# ============================================================================
# HARD GATES (v4.0.x)
# ============================================================================


class TestHardGates:
    """Tests for _render_hard_gates() — 3 mandatory gates."""

    def _call(self, **kwargs):
        defaults = dict(
            slug="test-task",
            workspace_num="001",
            wave_num=1,
            base_branch="main",
        )
        defaults.update(kwargs)
        return agent_brief_render._render_hard_gates(**defaults)

    def test_gate1_branch_verification(self):
        gates = self._call()
        assert "GATE 1" in gates
        assert "git branch --show-current" in gates
        assert "wave-001-1/test-task" in gates
        assert "STOP" in gates

    def test_gate2_synchronous_first(self):
        gates = self._call()
        assert "GATE 2" in gates
        assert "synchronous" in gates.lower()
        assert "Monitor" in gates

    def test_gate3_commit_verify(self):
        gates = self._call()
        assert "GATE 3" in gates
        assert "git log --oneline" in gates
        assert "git status --short" in gates
        assert ">= 1 commit" in gates.lower() or "≥ 1 commit" in gates


# ============================================================================
# Single isolation mode (v4.0.x)
# ============================================================================


class TestRenderIsolationBlock:
    """Tests for _render_isolation_block() — single manual worktree mode."""

    def _call(self, **kwargs):
        defaults = dict(
            slug="test-task",
            workspace_num="001",
            wave_num=1,
            project_root="/tmp/test-project",
            base_branch="main",
        )
        defaults.update(kwargs)
        return agent_brief_render._render_isolation_block(**defaults)

    def test_single_mode_contains_worktree_path(self):
        block = self._call()
        assert ".claude/worktrees/icm-wave-001-1-test-task" in block
        assert "wave-001-1/test-task" in block

    def test_single_mode_includes_isolation_rules(self):
        block = self._call()
        assert "NEVER write via absolute paths" in block
        assert "/tmp/test-project/.icm-main/" in block
        assert "NEVER run `git checkout`" in block

    def test_single_mode_includes_return_format(self):
        block = self._call()
        assert "git diff --name-only main...HEAD" in block
        assert "**Status:** COMPLETE | BLOCKED" in block


class TestRenderBrief:
    """Tests for render_brief() — HARD GATES + single isolation."""

    def test_brief_has_hard_gates_first(self):
        section = agent_brief_render.extract_task_section(SAMPLE_PLAN, "implementar-jwt-refresh")
        parsed = agent_brief_render.parse_4block(section)
        brief = agent_brief_render.render_brief(
            "implementar-jwt-refresh", parsed, [],
            workspace_num="042", wave_num=1,
            project_root="/tmp/test", base_branch="main",
        )
        # HARD GATES must appear before Summary
        gates_pos = brief.index("HARD GATES")
        summary_pos = brief.index("**Summary:**")
        assert gates_pos < summary_pos, "HARD GATES must be before Summary"

    def test_brief_isolation_has_claude_worktrees_path(self):
        section = agent_brief_render.extract_task_section(SAMPLE_PLAN, "implementar-jwt-refresh")
        parsed = agent_brief_render.parse_4block(section)
        brief = agent_brief_render.render_brief(
            "implementar-jwt-refresh", parsed, [],
            workspace_num="042", wave_num=1,
            project_root="/tmp/test", base_branch="main",
        )
        assert ".claude/worktrees/icm-wave-042-1-implementar-jwt-refresh" in brief

    def test_brief_does_not_mention_isolation_mode_field(self):
        section = agent_brief_render.extract_task_section(SAMPLE_PLAN, "implementar-jwt-refresh")
        parsed = agent_brief_render.parse_4block(section)
        brief = agent_brief_render.render_brief(
            "implementar-jwt-refresh", parsed, [],
            workspace_num="042", wave_num=1,
            project_root="/tmp/test", base_branch="main",
        )
        assert "**Isolation mode:**" not in brief


# ============================================================================
# CLI tests
# ============================================================================


class TestCliHappyPath:
    """Tests for CLI — workspace-num, wave, project-root now required."""

    def test_cli_renders_brief(self, tmp_path):
        plan = tmp_path / "plan.md"
        plan.write_text("""\
## Task my-task: Test task

**Type:** AFK
**Files touched:** src/x.py

### WHAT
Do something.

### HOW
Use something.

### OUT OF SCOPE
Nothing.

### VALIDATION
Test passes.
""")
        rc = agent_brief_render.main([
            "--task", "my-task",
            "--plan", str(plan),
            "--workspace-num", "042",
            "--wave", "1",
            "--project-root", str(tmp_path),
            "--base-branch", "main",
        ])
        assert rc == 0
