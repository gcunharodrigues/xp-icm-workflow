"""v3.7.0 — stage 08 template auto-invokes /init after exit A/C last active.

Smoke check of template `08_feedback_intake/CONTEXT.md.tpl`:
- Exit A step 5 uses `--exit-2-if-last-active`.
- Exit A step 6 instructs session to invoke `Skill(skill: "init")` if exit 2.
- Exit C step 5 uses `--exit-2-if-last-active`.
- Exit C step 6 same.
- Exit B never mentions /init (workspace remains active).
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
    """Splits template into 3 sub-strings for exits A/B/C."""
    markers = {
        "A": "### Exit A — Close",
        "B": "### Exit B — Restart stage X",
        "C": "### Exit C — Spawn new workspace",
    }
    a_start = content.find(markers["A"])
    b_start = content.find(markers["B"])
    c_start = content.find(markers["C"])
    c_end = content.find("Detalhes em", c_start) if c_start >= 0 else len(content)
    assert a_start >= 0 and b_start > a_start and c_start > b_start, (
        "A/B/C exit markers not found in expected order"
    )
    return {
        "A": content[a_start:b_start],
        "B": content[b_start:c_start],
        "C": content[c_start:c_end],
    }


def test_outcome_A_uses_exit_2_flag():
    """Exit A passes --exit-2-if-last-active in remove-block."""
    sec = _split_outcomes(_read())["A"]
    assert "--exit-2-if-last-active" in sec, (
        "exit A must pass --exit-2-if-last-active in remove-block"
    )


def test_outcome_A_invokes_skill_init_when_exit_2():
    """Exit A instructs invoking Skill(skill: 'init') when exit 2."""
    sec = _split_outcomes(_read())["A"]
    assert 'Skill(skill: "init")' in sec or "Skill(skill: 'init')" in sec, (
        "exit A must instruct invoking Skill init"
    )
    assert "exit code" in sec.lower() and "2" in sec
    assert "last active" in sec.lower() or "último ativo" in sec.lower() or "ultimo ativo" in sec.lower()


def test_outcome_C_uses_exit_2_flag():
    """Exit C passes --exit-2-if-last-active in remove-block."""
    sec = _split_outcomes(_read())["C"]
    assert "--exit-2-if-last-active" in sec


def test_outcome_C_invokes_skill_init_when_exit_2():
    """Exit C instructs invoking Skill(skill: 'init') when exit 2."""
    sec = _split_outcomes(_read())["C"]
    assert 'Skill(skill: "init")' in sec or "Skill(skill: 'init')" in sec
    assert "exit code" in sec.lower() and "2" in sec


def test_outcome_B_does_not_invoke_skill_init():
    """Exit B (restart) must NOT mention /init or Skill init."""
    sec = _split_outcomes(_read())["B"]
    assert "Skill(skill" not in sec, (
        "exit B (workspace remains active) must NOT invoke /init"
    )
    assert "/init" not in sec, "exit B must not mention /init"


def test_outcome_A_offers_icm_cleanup_menu():
    """v3.7.2 — exit A offers opt-in cleanup menu after /init."""
    sec = _split_outcomes(_read())["A"]
    assert "icm-cleanup.py" in sec, "saída A deve referenciar icm-cleanup.py"
    assert "[s]" in sec and "[n]" in sec and "[dry-run]" in sec, (
        "menu cleanup deve ter 3 opções: s/n/dry-run"
    )


def test_outcome_C_offers_icm_cleanup_menu():
    """v3.7.2 — exit C offers opt-in cleanup menu after /init."""
    sec = _split_outcomes(_read())["C"]
    assert "icm-cleanup.py" in sec
    assert "[s]" in sec and "[n]" in sec and "[dry-run]" in sec


def test_outcome_B_does_not_offer_cleanup():
    """Exit B (restart) must NOT offer cleanup — workspace remains active."""
    sec = _split_outcomes(_read())["B"]
    assert "icm-cleanup.py" not in sec, (
        "exit B must not invoke icm-cleanup.py (workspace remains active)"
    )
