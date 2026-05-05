"""Testes para scripts/agent-brief-render.py (T1.2)."""

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

### O QUE
Implementar refresh tokens JWT com TTL de 7 dias.

### COMO
Adicionar endpoint POST /auth/refresh que aceita refresh_token e
retorna novo access_token. Validar refresh_token via assinatura HMAC.

### NÃO QUERO
Não invalidar refresh tokens ainda válidos. Não tocar em
mecanismo de session existente.

### VALIDAÇÃO
Test que envia refresh_token válido retorna 200 com novo
access_token. Test que envia token expirado retorna 401.

## Task choose-orm: Escolher ORM (HITL)

**Type:** HITL
**Files touched:** docs/decisions/0007-orm.md

### O QUE
Escolher ORM entre Prisma, Drizzle e raw SQL.

### COMO
Avaliar trade-offs de type safety, performance, lock-in.

### NÃO QUERO
Não implementar antes do humano decidir.

### VALIDAÇÃO
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
    assert "Implementar refresh tokens" in parsed["o_que"]
    assert "POST /auth/refresh" in parsed["como"]
    assert "session existente" in parsed["nao_quero"]
    assert "200 com novo" in parsed["validacao"]


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
