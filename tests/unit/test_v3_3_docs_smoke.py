"""Smoke tests parsability of the 4 canonical docs v3.3.0+ (T2.5/T2.7/T2.8/T1.4).

Minimum coverage: file exists + expected minimal structure (sections,
keywords). NOT a property-based test — just a guard against deletion or
edits that destroy structure.

Documents covered:
  * references/adr-format.md (T1.4 — 3-criteria gate)
  * references/diagnose-protocol.md (T2.5 — 6 phases)
  * references/triage-state-machine.md (T2.7 — classification + transitions)
  * templates/workspace/_config/CONTEXT.md.tpl (T1.3 — ubiquitous language)
"""
from __future__ import annotations

from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[2]


# =========================================================================
# adr-format.md (T1.4)
# =========================================================================

class TestAdrFormat:
    @pytest.fixture
    def doc(self) -> str:
        return (SKILL_ROOT / "references" / "adr-format.md").read_text(encoding="utf-8")

    def test_doc_exists(self) -> None:
        assert (SKILL_ROOT / "references" / "adr-format.md").is_file()

    def test_mentions_3_criteria_gate(self, doc: str) -> None:
        # Doc deve descrever os 3 critérios de gate
        text_lower = doc.lower()
        assert "3-criteria" in text_lower or "3 crit" in text_lower  # "3-criteria gate" / "3 criterios"
        # Reversibilidade: doc usa "hard to reverse" / "reverter"
        assert "revert" in text_lower or "reverse" in text_lower
        assert "trade-off" in text_lower or "alternativa" in text_lower

    def test_has_required_sections(self, doc: str) -> None:
        # At least one main section
        assert "## " in doc


# =========================================================================
# diagnose-protocol.md (T2.5)
# =========================================================================

class TestDiagnoseProtocol:
    @pytest.fixture
    def doc(self) -> str:
        return (SKILL_ROOT / "references" / "diagnose-protocol.md").read_text(encoding="utf-8")

    def test_doc_exists(self) -> None:
        assert (SKILL_ROOT / "references" / "diagnose-protocol.md").is_file()

    def test_has_6_phases(self, doc: str) -> None:
        # Canonical diagnose doc has 6 phases (Phase 1-6 or Fase 1-6)
        # Accepts English or Portuguese
        text_lower = doc.lower()
        phase_count = max(
            sum(1 for i in range(1, 7) if f"phase {i}" in text_lower),
            sum(1 for i in range(1, 7) if f"fase {i}" in text_lower),
        )
        assert phase_count >= 6, f"expected 6 phases, found {phase_count}"

    def test_mentions_hitl_loop(self, doc: str) -> None:
        # Phase 1 item 10 mentions HITL loop
        assert "hitl" in doc.lower() or "human" in doc.lower()


# =========================================================================
# triage-state-machine.md (T2.7)
# =========================================================================

class TestTriageStateMachine:
    @pytest.fixture
    def doc(self) -> str:
        return (SKILL_ROOT / "references" / "triage-state-machine.md").read_text(encoding="utf-8")

    def test_doc_exists(self) -> None:
        assert (SKILL_ROOT / "references" / "triage-state-machine.md").is_file()

    def test_lists_canonical_states(self, doc: str) -> None:
        # State machine must list canonical states: triage, accepted, rejected, etc
        text_lower = doc.lower()
        # At least 2 canonical states must appear
        common_states = ["triage", "accept", "reject", "wontfix", "duplicate", "open"]
        found = sum(1 for s in common_states if s in text_lower)
        assert found >= 2, f"few states found: {found}"

    def test_describes_transitions(self, doc: str) -> None:
        # Doc must explain valid transitions
        assert "transi" in doc.lower() or "→" in doc or "->" in doc


# =========================================================================
# templates/workspace/_config/CONTEXT.md.tpl (T1.3 — ubiquitous language)
# =========================================================================

class TestUbiquitousLanguageTemplate:
    @pytest.fixture
    def doc(self) -> str:
        return (
            SKILL_ROOT / "templates" / "workspace" / "_config" / "CONTEXT.md.tpl"
        ).read_text(encoding="utf-8")

    def test_template_exists(self) -> None:
        assert (SKILL_ROOT / "templates" / "workspace" / "_config" / "CONTEXT.md.tpl").is_file()

    def test_has_frontmatter(self, doc: str) -> None:
        # L3 template starts with YAML frontmatter
        assert doc.startswith("---\n"), "template must start with frontmatter ---"
        # Frontmatter closed
        assert doc.count("---\n") >= 2

    def test_mentions_glossary_or_term(self, doc: str) -> None:
        # Ubiquitous language doc must mention glossary or terms
        text_lower = doc.lower()
        assert "glossário" in text_lower or "glossario" in text_lower or "termo" in text_lower or "term" in text_lower
