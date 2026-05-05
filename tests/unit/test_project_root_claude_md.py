"""Testes para gerência do `<project_root>/CLAUDE.md` (T1.1).

Cobertura:
  - Greenfield (arquivo ausente)
  - Brownfield com marcadores ICM existentes
  - Brownfield sem marcadores (insere após primeiro H1)
  - Multi-workspace (preserva blocos de outros workspaces ao update)
  - Remove bloco; remove último ativa região idle
  - deactivate substitui região por mensagem idle
  - Atomic write (arquivo .tmp é removido após replace)
  - Round-trip JSON: parse → update → parse retorna mesmo bloco

Doc canônico: references/project-root-claude-md.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Path hack: adicionar scripts/ ao sys.path para importar handoff
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import handoff  # noqa: E402
from handoff import (  # noqa: E402
    ICM_END_MARKER,
    ICM_START_MARKER,
    WorkspaceBlock,
    deactivate_project_claude_md,
    list_active_workspace_ids,
    remove_workspace_block,
    update_project_claude_md,
)


SKILL_DIR_FIXTURE = "/home/user/.claude/skills/xp-icm-workflow"


def _make_block(workspace: str = "001-test", **overrides) -> WorkspaceBlock:
    """Factory helper. Defaults razoáveis sobreescritos via kwargs."""
    defaults = dict(
        workspace=workspace,
        profile="app_web_backend",
        tier="development",
        stage_atual="00",
        stage_dir="00_recon",
        sub_stage="00_in_progress",
        iteration=0,
        status="IN_PROGRESS",
        last_action="bootstrap",
        last_action_at="2026-04-29T10:00:00Z",
        next_action="iniciar stage 00",
    )
    defaults.update(overrides)
    return WorkspaceBlock(**defaults)


# ========== Greenfield ==========


def test_greenfield_creates_full_file(tmp_path: Path):
    """Arquivo CLAUDE.md ausente → bootstrap cria do template completo."""
    block = _make_block()
    out = update_project_claude_md(tmp_path, block, SKILL_DIR_FIXTURE)
    assert out == tmp_path / "CLAUDE.md"
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert content.startswith(f"# CLAUDE.md — {tmp_path.name}")
    assert ICM_START_MARKER in content
    assert ICM_END_MARKER in content
    assert "001-test" in content
    assert "app_web_backend" in content
    assert "development" in content


# ========== Brownfield com marcadores ==========


def test_brownfield_with_markers_replaces_region(tmp_path: Path):
    """Arquivo existente com marcadores ICM → substitui só conteúdo entre marcadores."""
    pre_existing = (
        "# My Custom Project\n"
        "\n"
        "Some custom content above.\n"
        "\n"
        f"{ICM_START_MARKER}\n"
        "old icm content\n"
        f"{ICM_END_MARKER}\n"
        "\n"
        "## Custom section below\n"
        "Preserved content.\n"
    )
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(pre_existing, encoding="utf-8")

    block = _make_block()
    update_project_claude_md(tmp_path, block, SKILL_DIR_FIXTURE)

    content = claude_md.read_text(encoding="utf-8")
    # Conteúdo fora dos marcadores preservado
    assert "Some custom content above." in content
    assert "## Custom section below" in content
    assert "Preserved content." in content
    # Conteúdo antigo entre marcadores foi substituído
    assert "old icm content" not in content
    # Bloco do workspace renderizado
    assert "001-test" in content


# ========== Brownfield sem marcadores ==========


def test_brownfield_without_markers_inserts_after_h1(tmp_path: Path):
    """Arquivo existente sem marcadores → insere região após primeiro H1."""
    pre_existing = (
        "# My Project\n"
        "\n"
        "Some description.\n"
        "\n"
        "## Architecture\n"
        "Architecture details preserved.\n"
    )
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(pre_existing, encoding="utf-8")

    block = _make_block()
    update_project_claude_md(tmp_path, block, SKILL_DIR_FIXTURE)

    content = claude_md.read_text(encoding="utf-8")
    # Título H1 preservado no topo
    assert content.startswith("# My Project")
    # Marcadores presentes
    assert ICM_START_MARKER in content
    assert ICM_END_MARKER in content
    # Conteúdo abaixo preservado
    assert "## Architecture" in content
    assert "Architecture details preserved." in content
    # Bloco do workspace presente
    assert "001-test" in content
    # Marcador START vem antes da seção Architecture
    icm_start_pos = content.find(ICM_START_MARKER)
    arch_pos = content.find("## Architecture")
    assert icm_start_pos < arch_pos


def test_brownfield_no_h1_prepends(tmp_path: Path):
    """Arquivo sem H1 → região prependa no topo."""
    pre_existing = "Just some text without a title.\n"
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(pre_existing, encoding="utf-8")

    block = _make_block()
    update_project_claude_md(tmp_path, block, SKILL_DIR_FIXTURE)

    content = claude_md.read_text(encoding="utf-8")
    assert content.startswith(ICM_START_MARKER)
    assert "Just some text without a title." in content


# ========== Multi-workspace ==========


def test_multi_workspace_adds_block_preserves_existing(tmp_path: Path):
    """Adicionar segundo workspace preserva bloco do primeiro."""
    block1 = _make_block(workspace="001-first")
    block2 = _make_block(workspace="002-second", profile="cli_tool", tier="tool")

    update_project_claude_md(tmp_path, block1, SKILL_DIR_FIXTURE)
    update_project_claude_md(tmp_path, block2, SKILL_DIR_FIXTURE)

    content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "001-first" in content
    assert "002-second" in content
    assert content.find("001-first") < content.find("002-second")  # ordem por workspace


def test_update_existing_workspace_replaces_only_its_block(tmp_path: Path):
    """Update do workspace 001 não toca bloco do 002."""
    b1_initial = _make_block(workspace="001-foo", stage_atual="00")
    b2 = _make_block(workspace="002-bar", stage_atual="03")
    update_project_claude_md(tmp_path, b1_initial, SKILL_DIR_FIXTURE)
    update_project_claude_md(tmp_path, b2, SKILL_DIR_FIXTURE)

    # Update workspace 001 para stage 02
    b1_updated = _make_block(workspace="001-foo", stage_atual="02", stage_dir="02_design")
    update_project_claude_md(tmp_path, b1_updated, SKILL_DIR_FIXTURE)

    content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    # 001 atualizado para stage 02
    assert "001-foo" in content
    assert "02_design" in content
    # 002 ainda no stage 03
    assert "002-bar" in content
    # IDs dos workspaces presentes
    ids = list_active_workspace_ids(tmp_path)
    assert ids == ["001-foo", "002-bar"]


# ========== Remove ==========


def test_remove_workspace_block(tmp_path: Path):
    """Remove bloco específico, mantém outros."""
    b1 = _make_block(workspace="001-foo")
    b2 = _make_block(workspace="002-bar")
    update_project_claude_md(tmp_path, b1, SKILL_DIR_FIXTURE)
    update_project_claude_md(tmp_path, b2, SKILL_DIR_FIXTURE)

    remove_workspace_block(tmp_path, "001-foo", SKILL_DIR_FIXTURE)

    content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "001-foo" not in content
    assert "002-bar" in content


def test_remove_last_workspace_activates_idle(tmp_path: Path):
    """Remover último workspace ativa mensagem 'nenhum ativo'."""
    b1 = _make_block(workspace="001-only")
    update_project_claude_md(tmp_path, b1, SKILL_DIR_FIXTURE)

    remove_workspace_block(tmp_path, "001-only", SKILL_DIR_FIXTURE, closed_at="2026-04-29T12:00:00Z")

    content = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "001-only" not in content
    assert "No active workspace" in content
    assert "/init" in content
    assert "2026-04-29T12:00:00Z" in content


def test_remove_nonexistent_workspace_is_noop(tmp_path: Path):
    """Remover workspace inexistente não toca arquivo."""
    b1 = _make_block(workspace="001-foo")
    update_project_claude_md(tmp_path, b1, SKILL_DIR_FIXTURE)
    before = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")

    remove_workspace_block(tmp_path, "999-ghost", SKILL_DIR_FIXTURE)

    after = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert before == after


# ========== Deactivate ==========


def test_deactivate_replaces_region_with_idle(tmp_path: Path):
    """deactivate substitui região por mensagem idle, preserva resto."""
    pre_existing = (
        "# My Project\n"
        "\n"
        f"{ICM_START_MARKER}\n"
        "active workspace block\n"
        f"{ICM_END_MARKER}\n"
        "\n"
        "## Custom\n"
        "Preserved.\n"
    )
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(pre_existing, encoding="utf-8")

    deactivate_project_claude_md(tmp_path, closed_at="2026-04-29T15:00:00Z")

    content = claude_md.read_text(encoding="utf-8")
    assert "active workspace block" not in content
    assert "No active workspace" in content
    assert "## Custom" in content  # preserved
    assert "Preserved." in content
    assert "2026-04-29T15:00:00Z" in content


# ========== Atomic write ==========


def test_atomic_write_no_tmp_file_left(tmp_path: Path):
    """Após update, arquivo .tmp não deve existir."""
    block = _make_block()
    update_project_claude_md(tmp_path, block, SKILL_DIR_FIXTURE)

    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == []


# ========== Round-trip JSON ==========


def test_round_trip_preserves_all_fields(tmp_path: Path):
    """Parse após update retorna WorkspaceBlock com todos os campos preservados."""
    original = _make_block(
        workspace="042-feat-auth",
        profile="agent_ia",
        tier="production",
        stage_atual="04",
        stage_dir="04_implementation_waves",
        sub_stage="04_in_progress",
        iteration=2,
        status="BLOCKED_STOP_POINT",
        last_action="stop point disparado",
        last_action_at="2026-04-29T16:30:00Z",
        next_action="aguardar humano",
    )
    update_project_claude_md(tmp_path, original, SKILL_DIR_FIXTURE)

    parsed = handoff._parse_workspace_blocks(tmp_path / "CLAUDE.md")
    assert "042-feat-auth" in parsed
    block = parsed["042-feat-auth"]
    assert block == original  # frozen dataclass equality


# ========== list_active_workspace_ids ==========


def test_list_active_workspace_ids_empty(tmp_path: Path):
    """Sem CLAUDE.md → lista vazia."""
    assert list_active_workspace_ids(tmp_path) == []


def test_list_active_workspace_ids_sorted(tmp_path: Path):
    """Lista retornada em ordem ascendente por workspace ID."""
    update_project_claude_md(tmp_path, _make_block(workspace="003-c"), SKILL_DIR_FIXTURE)
    update_project_claude_md(tmp_path, _make_block(workspace="001-a"), SKILL_DIR_FIXTURE)
    update_project_claude_md(tmp_path, _make_block(workspace="002-b"), SKILL_DIR_FIXTURE)

    assert list_active_workspace_ids(tmp_path) == ["001-a", "002-b", "003-c"]


# ========== Idempotência ==========


def test_update_idempotent(tmp_path: Path):
    """Mesmo update aplicado duas vezes produz arquivo idêntico."""
    block = _make_block()
    update_project_claude_md(tmp_path, block, SKILL_DIR_FIXTURE)
    first = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    update_project_claude_md(tmp_path, block, SKILL_DIR_FIXTURE)
    second = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert first == second


# ========== Helpers internos ==========


def test_render_workspace_block_md_contains_required_fields():
    block = _make_block(workspace="042-feat", stage_atual="03", stage_dir="03_wave_planner")
    md = handoff._render_workspace_block_md(block)
    assert "042-feat" in md
    assert "03_wave_planner" in md
    assert "Read order" in md
    assert "L0" in md
    assert "L1" in md
    assert "L2" in md


def test_wrap_block_with_markers_includes_json():
    """Bloco wrappado tem comentário ICM-DATA com JSON parseável."""
    import json as _json
    block = _make_block(workspace="100-test")
    wrapped = handoff._wrap_block_with_markers(block)
    assert "<!-- ICM-WORKSPACE:100-test -->" in wrapped
    assert "<!-- /ICM-WORKSPACE:100-test -->" in wrapped
    # Extrair JSON
    import re
    m = re.search(r"<!-- ICM-DATA:(.+?) -->", wrapped)
    assert m is not None
    data = _json.loads(m.group(1))
    assert data["workspace"] == "100-test"
    assert data["profile"] == "app_web_backend"
