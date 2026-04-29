"""Smoke test parsability + estrutura de references/deep-modules.md (v3.4.1)."""
from __future__ import annotations

from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / "references" / "deep-modules.md"


def test_doc_exists() -> None:
    assert DOC.is_file()


def test_doc_has_required_sections() -> None:
    text = DOC.read_text(encoding="utf-8")
    required = [
        "# Deep modules",
        "## Conceito — Deep modules",
        "## Os 3 critérios",
        "## Deletion test",
        "## Checklist para stage 02",
        "## Quando pular este check",
    ]
    missing = [s for s in required if s not in text]
    assert not missing, f"Sections missing: {missing}"


def test_checklist_has_five_items() -> None:
    text = DOC.read_text(encoding="utf-8")
    # Procura bloco da seção "## Checklist para stage 02"
    start = text.find("## Checklist para stage 02")
    assert start >= 0
    section = text[start:text.find("\n## ", start + 1) if text.find("\n## ", start + 1) >= 0 else len(text)]
    bullets = [ln for ln in section.splitlines() if ln.strip().startswith("- [ ]")]
    assert len(bullets) >= 5, f"esperado >=5 checklist items, achei {len(bullets)}"


def test_references_companion_docs() -> None:
    """Deep modules deve mencionar ADR + design-it-twice (alinhamento de referências)."""
    text = DOC.read_text(encoding="utf-8")
    assert "adr-format.md" in text
    assert "design-it-twice.md" in text
