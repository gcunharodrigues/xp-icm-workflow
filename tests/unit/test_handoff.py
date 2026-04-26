"""Unit tests do protocolo de session handoff (1 stage = 1 sessao).

Cobertura:

- render_kickoff substitui todos placeholders e raise se sobra `{{X}}`.
- render_kickoff handles empty prev_outputs / pending (yaml `[]`).
- render_kickoff handles multiline prev_decisions_summary com indent YAML literal block.
- write_kickoff cria dir, retorna Path correto, idempotente.
- extract_kickoff_metadata parse YAML frontmatter; raise em yaml malformado.
- validate_kickoff_present True/False por presenca do arquivo.
- STAGE_TARGET_DIR mapping correto pros 9 stages.
- Snapshot test contra fixture `kickoff_canonical.expected.md` (Q20).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Adicionar scripts/ ao path para import
SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from handoff import (  # type: ignore[import-not-found]  # noqa: E402
    HandoffData,
    HandoffError,
    PrevOutput,
    STAGE_DIR_BY_ID,
    extract_kickoff_metadata,
    render_kickoff,
    stage_target_dir,
    validate_kickoff_present,
    write_kickoff,
)


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
TEMPLATE_PATH = (
    Path(__file__).resolve().parents[2]
    / "templates"
    / "workspace"
    / "stages"
    / "_kickoff.md.tpl"
)


def _canonical_data() -> HandoffData:
    """Fixture de HandoffData usada no snapshot e em varios testes."""
    return HandoffData(
        workspace="042-feat-auth",
        project_root="/home/dev/aura-luz-api",
        prev_stage="02",
        prev_stage_name="design",
        stage_target="03",
        stage_target_name="wave_planner",
        stage_target_dir="03_wave_planner",
        generated_at="2026-04-26T14:30:00Z",
        generator_commit_sha="abc123def",
        prev_outputs=(
            PrevOutput(
                path="stages/02_design/output/plan.md",
                summary="Plano com 8 tasks, 2 ADRs criados (0001 stack + 0004 auth)",
            ),
            PrevOutput(
                path="stages/02_design/output/decisions.md",
                summary="Index L4 dos ADRs",
            ),
        ),
        prev_decisions_summary=(
            "- Stack: Python 3.13 + FastAPI + Postgres\n"
            "- Auth: JWT com refresh tokens (ADR 0004)"
        ),
        pending_for_this_stage=(
            "Resolver ambiguidade: tasks user-model e user-routes tocam src/users/",
        ),
        prev_state_prose=(
            "Sessao anterior fechou design com 8 tasks plan + 2 ADRs.\n"
            "Outputs em stages/02_design/output/."
        ),
        next_tasks_prose=(
            "Particionar 8 tasks em waves respeitando DAG.\n"
            "Resolver ambiguidades pendentes antes de freezar plan."
        ),
    )


# ---------------------------------------------------------------------------
# STAGE_DIR_BY_ID mapping
# ---------------------------------------------------------------------------

class TestStageDirMapping:
    def test_all_nine_stages_mapped(self) -> None:
        expected = {
            "00": "00_recon",
            "01": "01_discovery",
            "02": "02_design",
            "03": "03_wave_planner",
            "04": "04_implementation_waves",
            "05": "05_verification",
            "06": "06_review",
            "07": "07_merge",
            "08": "08_feedback_intake",
        }
        assert STAGE_DIR_BY_ID == expected

    def test_stage_target_dir_helper(self) -> None:
        assert stage_target_dir("03", "wave_planner") == "03_wave_planner"
        assert stage_target_dir("00", "recon") == "00_recon"
        assert stage_target_dir("08", "feedback_intake") == "08_feedback_intake"

    def test_stage_target_dir_invalid_id_raises(self) -> None:
        with pytest.raises(HandoffError):
            stage_target_dir("99", "nonsense")

    def test_stage_target_dir_name_mismatch_raises(self) -> None:
        # nome nao bate o canonico do stage_id
        with pytest.raises(HandoffError):
            stage_target_dir("03", "wrong_name")


# ---------------------------------------------------------------------------
# render_kickoff
# ---------------------------------------------------------------------------

class TestRenderKickoff:
    def test_substitutes_all_placeholders(self) -> None:
        data = _canonical_data()
        out = render_kickoff(TEMPLATE_PATH, data)
        # nenhum {{X}} nao-resolvido sobra
        assert "{{" not in out, f"placeholders nao resolvidos: {out}"
        assert "}}" not in out

    def test_includes_workspace_and_stage_target(self) -> None:
        data = _canonical_data()
        out = render_kickoff(TEMPLATE_PATH, data)
        assert "042-feat-auth" in out
        assert "03_wave_planner" in out
        assert "wave_planner" in out
        assert "stage_target: \"03\"" in out

    def test_includes_prev_outputs_yaml(self) -> None:
        data = _canonical_data()
        out = render_kickoff(TEMPLATE_PATH, data)
        assert "stages/02_design/output/plan.md" in out
        assert "stages/02_design/output/decisions.md" in out

    def test_empty_prev_outputs_renders_yaml_empty_list(self) -> None:
        base = _canonical_data()
        data = HandoffData(**{**base.__dict__, "prev_outputs": ()})
        out = render_kickoff(TEMPLATE_PATH, data)
        assert "prev_outputs: []" in out

    def test_empty_pending_renders_yaml_empty_list(self) -> None:
        base = _canonical_data()
        data = HandoffData(**{**base.__dict__, "pending_for_this_stage": ()})
        out = render_kickoff(TEMPLATE_PATH, data)
        assert "pending_for_this_stage: []" in out

    def test_multiline_decisions_summary_indented(self) -> None:
        """Multiline string deve respeitar indent (2 espacos) do YAML literal block."""
        data = _canonical_data()
        out = render_kickoff(TEMPLATE_PATH, data)
        # prev_decisions_summary: |
        #   - Stack: ...
        #   - Auth: ...
        assert "prev_decisions_summary: |\n" in out
        assert "  - Stack: Python 3.13 + FastAPI + Postgres\n" in out
        assert "  - Auth: JWT com refresh tokens (ADR 0004)\n" in out

    def test_raises_on_unresolved_placeholder(self, tmp_path: Path) -> None:
        """Template com placeholder fora da spec -> erro."""
        bad_tpl = tmp_path / "bad.md.tpl"
        bad_tpl.write_text("Header {{UNKNOWN_KEY}} body\n", encoding="utf-8")
        with pytest.raises(HandoffError):
            render_kickoff(bad_tpl, _canonical_data())

    def test_raises_on_missing_template(self, tmp_path: Path) -> None:
        with pytest.raises(HandoffError):
            render_kickoff(tmp_path / "nope.tpl", _canonical_data())

    def test_path_with_absolute_workspace_branch(self) -> None:
        """project_root absoluto resolve corretamente nas read orders."""
        data = _canonical_data()
        out = render_kickoff(TEMPLATE_PATH, data)
        assert "/home/dev/aura-luz-api/workspaces/042-feat-auth/CLAUDE.md" in out
        assert (
            "/home/dev/aura-luz-api/workspaces/042-feat-auth/"
            "stages/03_wave_planner/CONTEXT.md"
        ) in out

    def test_snapshot_against_fixture(self) -> None:
        """Snapshot canonico — output total bate fixture."""
        fixture = FIXTURES_DIR / "kickoff_canonical.expected.md"
        expected = fixture.read_text(encoding="utf-8")
        actual = render_kickoff(TEMPLATE_PATH, _canonical_data())
        assert actual == expected, (
            "Render diverge da fixture. Se mudou template intencionalmente, "
            f"atualize {fixture.name}.\nDIFF preview:\n"
            f"--- expected\n{expected[:500]}\n+++ actual\n{actual[:500]}"
        )


# ---------------------------------------------------------------------------
# write_kickoff
# ---------------------------------------------------------------------------

class TestWriteKickoff:
    def test_creates_dir_if_absent(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspaces" / "042-feat-auth"
        ws.mkdir(parents=True)
        # nao existe stages/03_wave_planner ainda
        out_path = write_kickoff(ws, _canonical_data(), template_path=TEMPLATE_PATH)
        assert out_path.exists()
        assert out_path.name == "_kickoff.md"
        assert out_path.parent.name == "03_wave_planner"

    def test_returns_absolute_path(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspaces" / "042-feat-auth"
        ws.mkdir(parents=True)
        out_path = write_kickoff(ws, _canonical_data(), template_path=TEMPLATE_PATH)
        assert out_path.is_absolute()
        assert out_path == ws / "stages" / "03_wave_planner" / "_kickoff.md"

    def test_idempotent_overwrite(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspaces" / "042-feat-auth"
        ws.mkdir(parents=True)
        first = write_kickoff(ws, _canonical_data(), template_path=TEMPLATE_PATH)
        content_first = first.read_text(encoding="utf-8")
        second = write_kickoff(ws, _canonical_data(), template_path=TEMPLATE_PATH)
        content_second = second.read_text(encoding="utf-8")
        assert first == second
        assert content_first == content_second


# ---------------------------------------------------------------------------
# extract_kickoff_metadata
# ---------------------------------------------------------------------------

class TestExtractMetadata:
    def test_parses_valid_frontmatter(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspaces" / "042-feat-auth"
        ws.mkdir(parents=True)
        out_path = write_kickoff(ws, _canonical_data(), template_path=TEMPLATE_PATH)
        meta = extract_kickoff_metadata(out_path)
        assert meta["layer"] == "L4-kickoff"
        assert meta["stage_target"] == "03"
        assert meta["stage_target_name"] == "wave_planner"
        assert meta["prev_stage"] == "02"
        assert meta["generator_commit_sha"] == "abc123def"
        assert isinstance(meta["prev_outputs"], list)
        assert len(meta["prev_outputs"]) == 2
        assert meta["prev_outputs"][0]["path"] == "stages/02_design/output/plan.md"
        assert isinstance(meta["pending_for_this_stage"], list)
        assert len(meta["pending_for_this_stage"]) == 1

    def test_raises_on_malformed_yaml(self, tmp_path: Path) -> None:
        bad = tmp_path / "_kickoff.md"
        bad.write_text(
            "---\nthis: is: broken: yaml\n---\n# body\n",
            encoding="utf-8",
        )
        with pytest.raises(HandoffError):
            extract_kickoff_metadata(bad)

    def test_raises_on_missing_frontmatter(self, tmp_path: Path) -> None:
        no_fm = tmp_path / "_kickoff.md"
        no_fm.write_text("# nada de frontmatter\n", encoding="utf-8")
        with pytest.raises(HandoffError):
            extract_kickoff_metadata(no_fm)

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(HandoffError):
            extract_kickoff_metadata(tmp_path / "ghost.md")


# ---------------------------------------------------------------------------
# validate_kickoff_present
# ---------------------------------------------------------------------------

class TestValidateKickoffPresent:
    def test_true_if_kickoff_exists(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspaces" / "042-feat-auth"
        ws.mkdir(parents=True)
        write_kickoff(ws, _canonical_data(), template_path=TEMPLATE_PATH)
        assert validate_kickoff_present(ws, "03") is True

    def test_false_if_kickoff_missing(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspaces" / "042-feat-auth"
        (ws / "stages" / "03_wave_planner").mkdir(parents=True)
        assert validate_kickoff_present(ws, "03") is False

    def test_false_if_stage_dir_missing(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspaces" / "042-feat-auth"
        ws.mkdir(parents=True)
        assert validate_kickoff_present(ws, "03") is False

    def test_invalid_stage_id_raises(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspaces" / "042-feat-auth"
        ws.mkdir(parents=True)
        with pytest.raises(HandoffError):
            validate_kickoff_present(ws, "99")
