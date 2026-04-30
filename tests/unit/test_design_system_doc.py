"""Smoke test para references/design-system.md (v3.4.4).

Verifica:
  - Arquivo existe e é parseável
  - Section headers canônicos presentes
  - Schema canônico DESIGN.md mencionado
  - 3-layer token architecture documentada
  - Stage 02 process descrito
  - Fluxo por stage 00-08 mapeado
  - Escape hatch ui-ux-pro-max documentado
  - design-system.md está em runtime_refs do bootstrap (copiado pro workspace)
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOC_PATH = REPO / "references" / "design-system.md"
BOOTSTRAP = REPO / "scripts" / "bootstrap.py"


def test_doc_exists():
    assert DOC_PATH.is_file()


def test_doc_has_canonical_sections():
    content = DOC_PATH.read_text(encoding="utf-8")
    expected_sections = [
        "## Por que DESIGN.md",
        "## Estrutura canônica do arquivo",
        "## 3-layer token architecture",
        "## Component spec table",
        "## Fluxo por stage ICM",
        "## Stage 02 process",
        "## Stage 04 canal 2",
        "## Galeria de referência",
        "## Tool externo opcional — designlang",
        "## Escape hatch — ui-ux-pro-max-skill",
        "## Conversão pra outras representações",
        "## Anti-patterns",
        "## Referências cruzadas",
    ]
    for section in expected_sections:
        assert section in content, f"seção faltando: {section!r}"


def test_doc_mentions_design_md_schema_keys():
    content = DOC_PATH.read_text(encoding="utf-8")
    # Schema canônico mencionado
    for key in ["colors", "typography", "rounded", "spacing", "components"]:
        assert key in content, f"schema key faltando: {key!r}"


def test_doc_mentions_canonical_section_order():
    content = DOC_PATH.read_text(encoding="utf-8")
    # Section order da spec Google Stitch
    for section in [
        "Overview", "Colors", "Typography", "Layout",
        "Elevation", "Shapes", "Components", "Do's and Don'ts",
    ]:
        assert section in content, f"section order incompleto: {section!r}"


def test_doc_mentions_token_layers():
    content = DOC_PATH.read_text(encoding="utf-8")
    for layer in ["Primitive", "Semantic", "Component"]:
        assert layer in content, f"token layer faltando: {layer!r}"


def test_doc_mentions_component_spec_states():
    content = DOC_PATH.read_text(encoding="utf-8")
    for state in ["Default", "Hover", "Active", "Disabled"]:
        assert state in content, f"component state faltando: {state!r}"


def test_doc_mentions_stage_02_menu_options():
    content = DOC_PATH.read_text(encoding="utf-8")
    # Menu A/B/C: criar do zero, awesome-design-md, designlang
    assert "Criar do zero" in content
    assert "awesome-design-md" in content
    assert "designlang" in content


def test_doc_mentions_design_md_path():
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "<project_root>/.icm-main/DESIGN.md" in content


def test_doc_mentions_escape_hatch_boundary():
    content = DOC_PATH.read_text(encoding="utf-8")
    # Escape hatch documentado + boundary explicado
    assert "ui-ux-pro-max" in content
    assert "Escape hatch" in content
    # Boundary: skill paralela, invocação humana explícita
    assert "humana explícita" in content or "humana explicita" in content


def test_design_system_in_runtime_refs():
    """Bootstrap deve copiar design-system.md para <workspace>/_references/runtime/."""
    bootstrap_content = BOOTSTRAP.read_text(encoding="utf-8")
    assert '"design-system.md"' in bootstrap_content, (
        "design-system.md não está em runtime_refs tuple do bootstrap.py"
    )


def test_doc_links_external_resources():
    """Doc deve linkar spec Google + galeria VoltAgent + tool designlang."""
    content = DOC_PATH.read_text(encoding="utf-8")
    assert "stitch.withgoogle.com" in content
    assert "VoltAgent/awesome-design-md" in content
    assert "Manavarya09/design-extract" in content
