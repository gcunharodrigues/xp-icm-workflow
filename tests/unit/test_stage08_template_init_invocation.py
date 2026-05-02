"""v3.7.0 — stage 08 template auto-invoca /init pós saída A/C último ativo.

Smoke check do template `08_feedback_intake/CONTEXT.md.tpl`:
- Saída A step 5 usa `--exit-2-if-last-active`.
- Saída A step 6 instrui sessão invocar `Skill(skill: "init")` se exit 2.
- Saída C step 5 usa `--exit-2-if-last-active`.
- Saída C step 6 idem.
- Saída B nunca menciona /init (workspace continua ativo).
"""
from __future__ import annotations

from pathlib import Path

TEMPLATE_PATH = (
    Path(__file__).resolve().parents[2]
    / "templates" / "workspace" / "stages"
    / "08_feedback_intake" / "CONTEXT.md.tpl"
)


def _read() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _split_outcomes(content: str) -> dict[str, str]:
    """Quebra template em 3 sub-strings das saídas A/B/C."""
    markers = {
        "A": "### Saída A — Close",
        "B": "### Saída B — Restart phase X",
        "C": "### Saída C — Spawn novo workspace",
    }
    a_start = content.find(markers["A"])
    b_start = content.find(markers["B"])
    c_start = content.find(markers["C"])
    c_end = content.find("Detalhes em", c_start) if c_start >= 0 else len(content)
    assert a_start >= 0 and b_start > a_start and c_start > b_start, (
        "marcadores das saídas A/B/C não encontrados em ordem esperada"
    )
    return {
        "A": content[a_start:b_start],
        "B": content[b_start:c_start],
        "C": content[c_start:c_end],
    }


def test_outcome_A_uses_exit_2_flag():
    """Saída A passa --exit-2-if-last-active no remove-block."""
    sec = _split_outcomes(_read())["A"]
    assert "--exit-2-if-last-active" in sec, (
        "saída A deve passar --exit-2-if-last-active no remove-block"
    )


def test_outcome_A_invokes_skill_init_when_exit_2():
    """Saída A instrui invocar Skill(skill: 'init') quando exit 2."""
    sec = _split_outcomes(_read())["A"]
    assert 'Skill(skill: "init")' in sec or "Skill(skill: 'init')" in sec, (
        "saída A deve instruir invocar Skill init"
    )
    assert "exit code" in sec.lower() and "2" in sec
    assert "último ativo" in sec.lower() or "ultimo ativo" in sec.lower()


def test_outcome_C_uses_exit_2_flag():
    """Saída C passa --exit-2-if-last-active no remove-block."""
    sec = _split_outcomes(_read())["C"]
    assert "--exit-2-if-last-active" in sec


def test_outcome_C_invokes_skill_init_when_exit_2():
    """Saída C instrui invocar Skill(skill: 'init') quando exit 2."""
    sec = _split_outcomes(_read())["C"]
    assert 'Skill(skill: "init")' in sec or "Skill(skill: 'init')" in sec
    assert "exit code" in sec.lower() and "2" in sec


def test_outcome_B_does_not_invoke_skill_init():
    """Saída B (restart) NÃO menciona /init nem Skill init."""
    sec = _split_outcomes(_read())["B"]
    assert "Skill(skill" not in sec, (
        "saída B (workspace continua ativo) NÃO deve invocar /init"
    )
    assert "/init" not in sec, "saída B não deve mencionar /init"
