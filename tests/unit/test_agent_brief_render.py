"""Tests for scripts/agent-brief-render.py (T1.2)."""

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
    assert "choose-orm" not in section  # did not capture next section


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
    brief = agent_brief_render.render_brief("implementar-jwt-refresh", parsed, [])

    assert "Agent Brief — implementar-jwt-refresh" in brief
    assert "**Type:** AFK" in brief
    assert "**Summary:**" in brief
    assert "**Desired behavior:**" in brief
    assert "**Key interfaces:**" in brief
    assert "**Acceptance criteria:**" in brief
    assert "**Out of scope:**" in brief


def test_render_brief_with_adrs():
    section = agent_brief_render.extract_task_section(SAMPLE_PLAN, "implementar-jwt-refresh")
    parsed = agent_brief_render.parse_4block(section)
    brief = agent_brief_render.render_brief(
        "implementar-jwt-refresh", parsed,
        ["0001-stack.md", "0004-auth.md"],
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
# Isolation mode & nested worktree detection (v4.0.x)
# ============================================================================


class TestDetectIsolationMode:
    """Tests for detect_isolation_mode() — .git file vs directory."""

    def test_returns_worktree_when_project_root_empty(self):
        assert agent_brief_render.detect_isolation_mode("") == "worktree"

    def test_returns_worktree_when_dot_git_is_directory(self, tmp_path):
        dot_git = tmp_path / ".git"
        dot_git.mkdir()
        assert agent_brief_render.detect_isolation_mode(str(tmp_path)) == "worktree"

    def test_returns_manual_worktree_when_dot_git_is_file(self, tmp_path):
        dot_git = tmp_path / ".git"
        dot_git.write_text("gitdir: /some/real/.git")
        assert agent_brief_render.detect_isolation_mode(str(tmp_path)) == "manual-worktree"

    def test_returns_worktree_when_dot_git_absent(self, tmp_path):
        # No .git at all — safe default is worktree (will fail fast in pre-flight)
        assert agent_brief_render.detect_isolation_mode(str(tmp_path)) == "worktree"


class TestRenderIsolationBlock:
    """Tests for _render_isolation_block() — isolation rules per mode."""

    def _call(self, **kwargs):
        defaults = dict(
            slug="test-task",
            workspace_num="001",
            wave_num=1,
            project_root="/tmp/test-project",
            base_branch="main",
            mode="worktree",
        )
        defaults.update(kwargs)
        return agent_brief_render._render_isolation_block(**defaults)

    def test_returns_empty_when_no_workspace_num(self):
        block = self._call(workspace_num="")
        assert block == ""

    def test_returns_empty_when_no_wave_num(self):
        block = self._call(wave_num=0)
        assert block == ""

    def test_worktree_mode_contains_agent_isolation_header(self):
        block = self._call(mode="worktree")
        assert "worktree mode" in block
        assert 'Agent(isolation: "worktree")' in block
        assert "wave-001-1/test-task" in block
        assert "NOT the project root" in block

    def test_worktree_mode_includes_isolation_rules(self):
        block = self._call(mode="worktree")
        assert "git branch --show-current" in block
        assert "git status --short" in block
        assert "git diff --name-only main...HEAD" in block
        assert "NEVER write to" in block
        assert "/tmp/test-project/.icm-main/" in block

    def test_manual_worktree_mode_contains_manual_header(self):
        block = self._call(mode="manual-worktree")
        assert "manual-worktree mode" in block
        assert "Agent(isolation=none, cwd=<worktree>)" in block
        assert "wave-001-1/test-task" in block
        assert "Your CWD IS the isolation" in block

    def test_manual_worktree_mode_mentions_tmp_path(self):
        block = self._call(mode="manual-worktree")
        assert "/tmp/icm-wave-" in block

    def test_direct_mode_forbids_code_writing(self):
        block = self._call(mode="direct")
        assert "direct mode" in block
        assert "REVIEWER/CRITIC ONLY" in block
        assert "NEVER write code" in block
        assert "NEVER modify `src/` or `tests/`" in block

    def test_direct_mode_does_not_mention_branch_verification(self):
        block = self._call(mode="direct")
        assert "git branch --show-current" not in block


class TestRenderBriefWithIsolationMode:
    """Tests for render_brief() — isolation_mode parameter."""

    def test_brief_includes_isolation_mode_field(self):
        section = agent_brief_render.extract_task_section(SAMPLE_PLAN, "implementar-jwt-refresh")
        parsed = agent_brief_render.parse_4block(section)
        brief = agent_brief_render.render_brief(
            "implementar-jwt-refresh", parsed, [],
            workspace_num="042", wave_num=1,
            project_root="/tmp/test", base_branch="main",
            isolation_mode="manual-worktree",
        )
        assert "**Isolation mode:** manual-worktree" in brief

    def test_brief_uses_manual_worktree_isolation_block(self):
        section = agent_brief_render.extract_task_section(SAMPLE_PLAN, "implementar-jwt-refresh")
        parsed = agent_brief_render.parse_4block(section)
        brief = agent_brief_render.render_brief(
            "implementar-jwt-refresh", parsed, [],
            workspace_num="042", wave_num=1,
            project_root="/tmp/test", base_branch="main",
            isolation_mode="manual-worktree",
        )
        assert "manual-worktree mode" in brief
        assert "Your CWD IS the isolation" in brief

    def test_brief_uses_direct_mode_isolation_block(self):
        section = agent_brief_render.extract_task_section(SAMPLE_PLAN, "implementar-jwt-refresh")
        parsed = agent_brief_render.parse_4block(section)
        brief = agent_brief_render.render_brief(
            "implementar-jwt-refresh", parsed, [],
            workspace_num="042", wave_num=1,
            project_root="/tmp/test", base_branch="main",
            isolation_mode="direct",
        )
        assert "direct mode" in brief
        assert "REVIEWER/CRITIC ONLY" in brief

    def test_brief_defaults_to_worktree_when_no_mode_specified(self):
        section = agent_brief_render.extract_task_section(SAMPLE_PLAN, "implementar-jwt-refresh")
        parsed = agent_brief_render.parse_4block(section)
        brief = agent_brief_render.render_brief(
            "implementar-jwt-refresh", parsed, [],
            workspace_num="042", wave_num=1,
            project_root="/tmp/test", base_branch="main",
        )
        assert "Isolation rules" in brief
        assert "worktree mode" in brief


# ============================================================================
# CLI --isolation-mode flag (v4.0.x)
# ============================================================================


class TestCliIsolationMode:
    """Tests for CLI --isolation-mode flag behavior."""

    def test_auto_detects_nested_worktree_from_git_file(self, tmp_path):
        (tmp_path / ".git").write_text("gitdir: /some/real/.git")
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
            "--isolation-mode", "auto",
        ])
        assert rc == 0

    def test_explicit_manual_worktree_mode(self, tmp_path):
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
            "--isolation-mode", "manual-worktree",
        ])
        assert rc == 0

    def test_direct_mode_allowed(self, tmp_path):
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
            "--isolation-mode", "direct",
        ])
        assert rc == 0
