"""Property-based + unit tests do schema L1 (CONTEXT.md raiz).

Cobertura:

- Properties (Hypothesis):
  * iteration_monotonic — count(history events 'iteration_increment') == iteration
  * sub_stage prefix — sub_stage.startswith(stage_atual + '_')
  * waves_nullable — stage<04 sem waves; stage>=04 com waves
  * history_append_only — simulacao de transicoes nao encolhe history
  * status_enum — status sempre em VALID_STATUSES
  * last_transition.to == sub_stage

- Tests deterministicos:
  * frontmatter valido passa
  * cada campo obrigatorio ausente levanta StateValidationError
  * enum invalido (tier, status) levanta
  * sub_stage prefix mismatch levanta
  * waves presente em stage 02 levanta
  * waves ausente em stage 04 levanta
  * iteration negativo levanta
  * iteration desbatido com history levanta
  * sub_stage 04 fora do padrao levanta
  * sub_stage fora do enum simples levanta
  * last_transition sem campo obrigatorio levanta
  * history nao-lista levanta
  * history item sem 'at' ou 'event' levanta
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

# Adicionar scripts/ ao path para import
SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from validate_state import (  # type: ignore[import-not-found]  # noqa: E402
    StateValidationError,
    SUB_STAGE_04_PATTERN,
    SIMPLE_SUB_STAGE_ENUMS,
    VALID_STAGES,
    VALID_STATUSES,
    VALID_TIERS,
    parse_frontmatter,
    validate_state,
)


# Strategies -------------------------------------------------------------------

ISO_TIMESTAMPS = st.sampled_from(
    [
        "2026-04-25T14:30:00Z",
        "2026-01-01T00:00:00Z",
        "2025-12-31T23:59:59Z",
    ]
)

COMMIT_SHAS = st.text(
    alphabet="0123456789abcdef", min_size=7, max_size=40
)

VALID_TIER_STRATEGY = st.sampled_from(sorted(VALID_TIERS))
VALID_STATUS_STRATEGY = st.sampled_from(sorted(VALID_STATUSES))
VALID_STAGE_STRATEGY = st.sampled_from(sorted(VALID_STAGES))


def _sub_stage_for(stage: str, wave_n: int = 1) -> str:
    """Retorna um sub_stage valido para o stage dado."""
    if stage == "04":
        return f"04_wave_{wave_n}_in_progress"
    enum = SIMPLE_SUB_STAGE_ENUMS[stage]
    return sorted(enum)[0]


def _make_valid_state(
    *,
    stage: str = "02",
    iteration: int = 0,
    extra_history: list[dict] | None = None,
    status: str = "IN_PROGRESS",
    tier: str = "development",
) -> dict:
    """Constroi um estado L1 valido para testes."""
    sub_stage = _sub_stage_for(stage)
    history: list[dict] = list(extra_history or [])
    state = {
        "workspace": "042-feat-auth",
        "profile_base": "app_web_backend",
        "profile_effective_hash": "a" * 64,
        "tier": tier,
        "project_root": "/tmp/proj",
        "base_branch": "main",
        "workspace_branch": "workspace/042-feat-auth",
        "stage_atual": stage,
        "sub_stage": sub_stage,
        "status": status,
        "iteration": iteration,
        "history": history,
        "last_action": "test",
        "last_action_at": "2026-04-25T14:30:00Z",
        "next_action": "next",
        "last_transition": {
            "from": "01_completed",
            "to": sub_stage,
            "at": "2026-04-25T14:30:00Z",
            "commit_sha": "abc123def",
        },
    }
    if stage >= "04":
        state["waves"] = {"current": 1, "completed": []}
    return state


# Properties — Hypothesis ------------------------------------------------------

@given(
    iteration=st.integers(min_value=0, max_value=10),
    other_events=st.lists(
        st.sampled_from(
            ["stage_transition", "wave_completed", "stop_point_triggered"]
        ),
        min_size=0,
        max_size=5,
    ),
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_invariant_iteration_monotonic(
    iteration: int, other_events: list[str]
) -> None:
    """iteration deve == count(history events 'iteration_increment')."""
    history: list[dict] = []
    for ev in other_events:
        history.append({"at": "2026-04-25T14:30:00Z", "event": ev})
    for _ in range(iteration):
        history.append(
            {"at": "2026-04-25T14:30:00Z", "event": "iteration_increment"}
        )
    state = _make_valid_state(iteration=iteration, extra_history=history)
    validate_state(state)  # nao deve levantar


@given(stage=VALID_STAGE_STRATEGY)
@settings(max_examples=20)
def test_invariant_sub_stage_prefix_stage(stage: str) -> None:
    """sub_stage deve sempre comecar com '<stage_atual>_'."""
    state = _make_valid_state(stage=stage)
    assert state["sub_stage"].startswith(f"{stage}_")
    validate_state(state)


@given(stage=VALID_STAGE_STRATEGY)
@settings(max_examples=20)
def test_invariant_waves_nullable(stage: str) -> None:
    """stage<04 sem waves; stage>=04 com waves."""
    state = _make_valid_state(stage=stage)
    if stage >= "04":
        assert "waves" in state and state["waves"] is not None
        assert "current" in state["waves"]
        assert "completed" in state["waves"]
    else:
        assert "waves" not in state or state["waves"] is None
    validate_state(state)


@given(
    n_transitions=st.integers(min_value=1, max_value=5),
)
@settings(max_examples=20)
def test_invariant_history_append_only(n_transitions: int) -> None:
    """Simulacao de N transicoes — history cresce, nao encolhe."""
    history: list[dict] = []
    prev_len = 0
    for i in range(n_transitions):
        history.append(
            {
                "at": "2026-04-25T14:30:00Z",
                "event": "stage_transition",
                "from": "01_in_progress",
                "to": "01_completed",
            }
        )
        assert len(history) == prev_len + 1, "history nunca shrinks"
        prev_len = len(history)
    state = _make_valid_state(extra_history=history)
    validate_state(state)


@given(status=VALID_STATUS_STRATEGY)
@settings(max_examples=10)
def test_invariant_status_enum(status: str) -> None:
    """status sempre em VALID_STATUSES."""
    assert status in VALID_STATUSES
    state = _make_valid_state(status=status)
    validate_state(state)


@given(stage=VALID_STAGE_STRATEGY)
@settings(max_examples=20)
def test_invariant_last_transition_to_matches_sub_stage(stage: str) -> None:
    """last_transition.to deve == sub_stage atual."""
    state = _make_valid_state(stage=stage)
    assert state["last_transition"]["to"] == state["sub_stage"]


# Tests deterministicos --------------------------------------------------------

class TestValidStates:
    def test_valid_minimal_stage_02_passes(self) -> None:
        state = _make_valid_state(stage="02")
        validate_state(state)

    def test_valid_stage_04_with_waves_passes(self) -> None:
        state = _make_valid_state(stage="04")
        validate_state(state)

    def test_valid_stage_07_with_waves_passes(self) -> None:
        state = _make_valid_state(stage="07")
        validate_state(state)

    def test_valid_iteration_with_matching_history(self) -> None:
        history = [
            {"at": "2026-04-25T14:30:00Z", "event": "iteration_increment"},
            {"at": "2026-04-25T14:31:00Z", "event": "iteration_increment"},
        ]
        state = _make_valid_state(iteration=2, extra_history=history)
        validate_state(state)


class TestMissingFields:
    @pytest.mark.parametrize(
        "field",
        [
            "workspace",
            "profile_base",
            "profile_effective_hash",
            "tier",
            "project_root",
            "base_branch",
            "workspace_branch",
            "stage_atual",
            "sub_stage",
            "status",
            "iteration",
            "history",
            "last_action",
            "last_action_at",
            "next_action",
            "last_transition",
        ],
    )
    def test_missing_required_field_raises(self, field: str) -> None:
        state = _make_valid_state()
        del state[field]
        with pytest.raises(StateValidationError, match=field):
            validate_state(state)


class TestInvalidEnums:
    def test_invalid_tier_raises(self) -> None:
        state = _make_valid_state()
        state["tier"] = "bogus"
        with pytest.raises(StateValidationError, match="tier"):
            validate_state(state)

    def test_invalid_status_raises(self) -> None:
        state = _make_valid_state()
        state["status"] = "RUNNING"
        with pytest.raises(StateValidationError, match="status"):
            validate_state(state)

    def test_invalid_stage_atual_raises(self) -> None:
        state = _make_valid_state()
        state["stage_atual"] = "99"
        with pytest.raises(StateValidationError, match="stage_atual"):
            validate_state(state)


class TestSubStage:
    def test_sub_stage_prefix_mismatch_raises(self) -> None:
        state = _make_valid_state(stage="02")
        state["sub_stage"] = "03_in_progress"
        # last_transition.to ainda aponta pro velho — mas a falha vem antes
        with pytest.raises(StateValidationError, match="sub_stage"):
            validate_state(state)

    def test_sub_stage_04_invalid_pattern_raises(self) -> None:
        state = _make_valid_state(stage="04")
        state["sub_stage"] = "04_wave_in_progress"  # falta numero
        state["last_transition"]["to"] = state["sub_stage"]
        with pytest.raises(StateValidationError, match="04_wave"):
            validate_state(state)

    def test_sub_stage_simple_enum_invalid_raises(self) -> None:
        state = _make_valid_state(stage="02")
        state["sub_stage"] = "02_running"  # nao esta no enum
        state["last_transition"]["to"] = state["sub_stage"]
        with pytest.raises(StateValidationError, match="sub_stage"):
            validate_state(state)

    def test_sub_stage_08_decided_a_passes(self) -> None:
        state = _make_valid_state(stage="08")
        state["sub_stage"] = "08_decided_A"
        state["last_transition"]["to"] = "08_decided_A"
        validate_state(state)


class TestWaves:
    def test_waves_present_in_stage_02_raises(self) -> None:
        state = _make_valid_state(stage="02")
        state["waves"] = {"current": 1, "completed": []}
        with pytest.raises(StateValidationError, match="waves"):
            validate_state(state)

    def test_waves_absent_in_stage_04_raises(self) -> None:
        state = _make_valid_state(stage="04")
        del state["waves"]
        with pytest.raises(StateValidationError, match="waves"):
            validate_state(state)

    def test_waves_null_in_stage_04_raises(self) -> None:
        state = _make_valid_state(stage="04")
        state["waves"] = None
        with pytest.raises(StateValidationError, match="waves"):
            validate_state(state)

    def test_waves_null_in_stage_02_passes(self) -> None:
        state = _make_valid_state(stage="02")
        state["waves"] = None
        validate_state(state)

    def test_waves_missing_current_raises(self) -> None:
        state = _make_valid_state(stage="04")
        state["waves"] = {"completed": []}
        with pytest.raises(StateValidationError, match="current"):
            validate_state(state)

    def test_waves_missing_completed_raises(self) -> None:
        state = _make_valid_state(stage="04")
        state["waves"] = {"current": 1}
        with pytest.raises(StateValidationError, match="completed"):
            validate_state(state)


class TestIteration:
    def test_negative_iteration_raises(self) -> None:
        state = _make_valid_state(iteration=-1)
        with pytest.raises(StateValidationError, match="iteration"):
            validate_state(state)

    def test_iteration_mismatch_history_raises(self) -> None:
        # iteration=2 mas zero eventos iteration_increment em history
        state = _make_valid_state(iteration=2, extra_history=[])
        with pytest.raises(StateValidationError, match="iteration"):
            validate_state(state)

    def test_iteration_non_int_raises(self) -> None:
        state = _make_valid_state()
        state["iteration"] = "1"
        with pytest.raises(StateValidationError, match="iteration"):
            validate_state(state)

    def test_iteration_bool_raises(self) -> None:
        state = _make_valid_state()
        state["iteration"] = True  # bool e subclasse de int em Py
        with pytest.raises(StateValidationError, match="iteration"):
            validate_state(state)


class TestLastTransition:
    @pytest.mark.parametrize("key", ["from", "to", "at", "commit_sha"])
    def test_last_transition_missing_key_raises(self, key: str) -> None:
        state = _make_valid_state()
        del state["last_transition"][key]
        with pytest.raises(StateValidationError, match="last_transition"):
            validate_state(state)

    def test_last_transition_not_mapping_raises(self) -> None:
        state = _make_valid_state()
        state["last_transition"] = "abc123"
        with pytest.raises(StateValidationError, match="last_transition"):
            validate_state(state)


class TestHistory:
    def test_history_not_list_raises(self) -> None:
        state = _make_valid_state()
        state["history"] = "not a list"
        with pytest.raises(StateValidationError, match="history"):
            validate_state(state)

    def test_history_item_missing_at_raises(self) -> None:
        state = _make_valid_state(
            extra_history=[{"event": "stage_transition"}]
        )
        with pytest.raises(StateValidationError, match="at"):
            validate_state(state)

    def test_history_item_missing_event_raises(self) -> None:
        state = _make_valid_state(
            extra_history=[{"at": "2026-04-25T14:30:00Z"}]
        )
        with pytest.raises(StateValidationError, match="event"):
            validate_state(state)

    def test_history_item_not_mapping_raises(self) -> None:
        state = _make_valid_state(extra_history=["not a dict"])  # type: ignore
        with pytest.raises(StateValidationError, match="history"):
            validate_state(state)


# Frontmatter parsing ---------------------------------------------------------

class TestParseFrontmatter:
    def test_valid_frontmatter_parses(self) -> None:
        content = (
            "---\n"
            "workspace: \"042\"\n"
            "tier: development\n"
            "---\n\n"
            "# corpo\n"
        )
        data = parse_frontmatter(content)
        assert data["workspace"] == "042"
        assert data["tier"] == "development"

    def test_no_frontmatter_raises(self) -> None:
        with pytest.raises(StateValidationError, match="frontmatter"):
            parse_frontmatter("# Just markdown\nNo frontmatter\n")

    def test_invalid_yaml_raises(self) -> None:
        with pytest.raises(StateValidationError, match="YAML"):
            parse_frontmatter("---\nkey: value: bad\n---\n")

    def test_non_mapping_root_raises(self) -> None:
        with pytest.raises(StateValidationError, match="mapping"):
            parse_frontmatter("---\n- item1\n- item2\n---\n")


# Workspace integration -------------------------------------------------------

class TestValidateWorkspace:
    def test_valid_workspace_passes(self, tmp_path: Path) -> None:
        from validate_state import validate_workspace  # type: ignore[import-not-found]

        ctx = tmp_path / "CONTEXT.md"
        ctx.write_text(
            "---\n"
            "workspace: \"042-feat-auth\"\n"
            "profile_base: app_web_backend\n"
            f"profile_effective_hash: \"{'a' * 64}\"\n"
            "tier: development\n"
            "project_root: /tmp/proj\n"
            "base_branch: main\n"
            "workspace_branch: workspace/042-feat-auth\n"
            "stage_atual: \"02\"\n"
            "sub_stage: 02_in_progress\n"
            "status: IN_PROGRESS\n"
            "iteration: 0\n"
            "history: []\n"
            "last_action: test\n"
            "last_action_at: 2026-04-25T14:30:00Z\n"
            "next_action: next\n"
            "last_transition:\n"
            "  from: 01_completed\n"
            "  to: 02_in_progress\n"
            "  at: 2026-04-25T14:30:00Z\n"
            "  commit_sha: abc123\n"
            "---\n",
            encoding="utf-8",
        )
        validate_workspace(tmp_path)

    def test_missing_context_md_raises(self, tmp_path: Path) -> None:
        from validate_state import validate_workspace  # type: ignore[import-not-found]

        with pytest.raises(StateValidationError, match="CONTEXT.md"):
            validate_workspace(tmp_path)
