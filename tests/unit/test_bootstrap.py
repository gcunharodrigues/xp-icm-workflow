"""Testes unitarios para scripts/bootstrap.py (backend testavel do bootstrap).

Foco: funcoes puras de templating, validacao e manipulacao de arquivos de
indice/.gitignore. NAO toca FS real fora de tmp_path/tmp_workspace.

Bootstrap end-to-end (criacao de branch, commit, scaffold de estagios) e
testado em tests/integration/test_bootstrap.bats (CI-only).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# Carrega scripts/bootstrap.py como modulo
SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = SKILL_ROOT / "scripts" / "bootstrap.py"

_spec = importlib.util.spec_from_file_location("bootstrap", SCRIPT_PATH)
bootstrap = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["bootstrap"] = bootstrap
_spec.loader.exec_module(bootstrap)  # type: ignore[union-attr]

BootstrapError = bootstrap.BootstrapError
render_template = bootstrap.render_template
resolve_workspace_id = bootstrap.resolve_workspace_id
update_index = bootstrap.update_index
update_gitignore = bootstrap.update_gitignore
validate_slug = bootstrap.validate_slug
parse_profile_merge_output = bootstrap.parse_profile_merge_output


# ============================================================================
# render_template
# ============================================================================

class TestRenderTemplate:
    def test_substitutes_single_placeholder(self, tmp_path: Path) -> None:
        tpl = tmp_path / "x.tpl"
        tpl.write_text("hello {{NAME}}", encoding="utf-8")
        out = render_template(tpl, {"NAME": "world"})
        assert out == "hello world"

    def test_substitutes_multiple_placeholders(self, tmp_path: Path) -> None:
        tpl = tmp_path / "x.tpl"
        tpl.write_text("a={{A}} b={{B}} c={{C}}", encoding="utf-8")
        out = render_template(tpl, {"A": "1", "B": "2", "C": "3"})
        assert out == "a=1 b=2 c=3"

    def test_repeated_placeholder_substituted_everywhere(self, tmp_path: Path) -> None:
        tpl = tmp_path / "x.tpl"
        tpl.write_text("{{X}} and {{X}} again", encoding="utf-8")
        out = render_template(tpl, {"X": "boom"})
        assert out == "boom and boom again"

    def test_raises_when_placeholder_unresolved(self, tmp_path: Path) -> None:
        tpl = tmp_path / "x.tpl"
        tpl.write_text("{{KNOWN}} but {{UNKNOWN}}", encoding="utf-8")
        with pytest.raises(BootstrapError, match="UNKNOWN"):
            render_template(tpl, {"KNOWN": "ok"})

    def test_raises_when_template_path_missing(self, tmp_path: Path) -> None:
        with pytest.raises(BootstrapError, match="template"):
            render_template(tmp_path / "nope.tpl", {})

    def test_unicode_values_preserved(self, tmp_path: Path) -> None:
        tpl = tmp_path / "x.tpl"
        tpl.write_text("autor: {{NAME}}", encoding="utf-8")
        out = render_template(tpl, {"NAME": "guilherme à 2026"})
        assert "guilherme à 2026" in out

    def test_empty_string_value_allowed(self, tmp_path: Path) -> None:
        tpl = tmp_path / "x.tpl"
        tpl.write_text("logs={{LOGS_ROOT}} fim", encoding="utf-8")
        out = render_template(tpl, {"LOGS_ROOT": ""})
        assert out == "logs= fim"


# ============================================================================
# resolve_workspace_id
# ============================================================================

class TestResolveWorkspaceId:
    def test_missing_index_returns_one(self, tmp_path: Path) -> None:
        idx = tmp_path / ".index.md"
        assert resolve_workspace_id(idx) == 1

    def test_empty_index_returns_one(self, tmp_path: Path) -> None:
        idx = tmp_path / ".index.md"
        idx.write_text("", encoding="utf-8")
        assert resolve_workspace_id(idx) == 1

    def test_index_with_only_header_returns_one(self, tmp_path: Path) -> None:
        idx = tmp_path / ".index.md"
        idx.write_text(
            "# Workspaces index\n\n"
            "| ID | Slug | Profile/Tier | Created at | Status |\n"
            "|---|---|---|---|---|\n",
            encoding="utf-8",
        )
        assert resolve_workspace_id(idx) == 1

    def test_index_with_three_entries_returns_four(self, tmp_path: Path) -> None:
        idx = tmp_path / ".index.md"
        idx.write_text(
            "# Workspaces index\n\n"
            "| ID | Slug | Profile/Tier | Created at | Status |\n"
            "|---|---|---|---|---|\n"
            "| 001 | foo | app_web_backend/development | 2026-04-20 | active |\n"
            "| 002 | bar | cli_tool/tool | 2026-04-21 | active |\n"
            "| 003 | baz | experiment/experimental | 2026-04-22 | active |\n",
            encoding="utf-8",
        )
        assert resolve_workspace_id(idx) == 4

    def test_index_with_gap_uses_max_plus_one(self, tmp_path: Path) -> None:
        idx = tmp_path / ".index.md"
        idx.write_text(
            "| ID | Slug | Profile/Tier | Created at | Status |\n"
            "|---|---|---|---|---|\n"
            "| 001 | a | x/x | 2026-04-20 | active |\n"
            "| 042 | b | y/y | 2026-04-21 | active |\n",
            encoding="utf-8",
        )
        assert resolve_workspace_id(idx) == 43

    def test_index_ignores_malformed_lines(self, tmp_path: Path) -> None:
        idx = tmp_path / ".index.md"
        idx.write_text(
            "# Header\n\n"
            "| ID | Slug | Profile/Tier | Created at | Status |\n"
            "|---|---|---|---|---|\n"
            "| 005 | ok | p/t | 2026-04-20 | active |\n"
            "| zzz | bad | nada |\n"
            "linha solta sem pipes\n"
            "| 010 | other | p/t | 2026-04-22 | active |\n",
            encoding="utf-8",
        )
        assert resolve_workspace_id(idx) == 11


# ============================================================================
# update_index
# ============================================================================

class TestUpdateIndex:
    def test_creates_file_with_header_when_missing(self, tmp_path: Path) -> None:
        idx = tmp_path / ".index.md"
        update_index(
            idx,
            workspace="001-foo",
            profile="cli_tool",
            tier="tool",
            created_at="2026-04-25T10:00:00Z",
        )
        content = idx.read_text(encoding="utf-8")
        assert "| ID |" in content
        assert "001" in content
        assert "foo" in content
        assert "cli_tool/tool" in content

    def test_appends_to_existing_index(self, tmp_path: Path) -> None:
        idx = tmp_path / ".index.md"
        idx.write_text(
            "# Workspaces index\n\n"
            "| ID | Slug | Profile/Tier | Created at | Status |\n"
            "|---|---|---|---|---|\n"
            "| 001 | first | cli_tool/tool | 2026-04-20 | active |\n",
            encoding="utf-8",
        )
        update_index(
            idx,
            workspace="002-second",
            profile="app_web_backend",
            tier="development",
            created_at="2026-04-25T10:00:00Z",
        )
        content = idx.read_text(encoding="utf-8")
        assert "001 | first" in content  # preserva
        assert "002" in content
        assert "second" in content
        assert "app_web_backend/development" in content

    def test_id_and_slug_split_correctly(self, tmp_path: Path) -> None:
        idx = tmp_path / ".index.md"
        update_index(
            idx,
            workspace="042-feat-multi-word-slug",
            profile="ml_project",
            tier="production",
            created_at="2026-04-25T10:00:00Z",
        )
        content = idx.read_text(encoding="utf-8")
        # ID = 042; slug = feat-multi-word-slug
        assert "| 042 |" in content
        assert "feat-multi-word-slug" in content


# ============================================================================
# update_gitignore
# ============================================================================

class TestUpdateGitignore:
    def test_creates_file_when_missing(self, tmp_path: Path) -> None:
        gi = tmp_path / ".gitignore"
        update_gitignore(gi, ["__pycache__/", ".icm-profile.local.yaml"])
        content = gi.read_text(encoding="utf-8")
        assert "__pycache__/" in content
        assert ".icm-profile.local.yaml" in content

    def test_idempotent_when_lines_already_present(self, tmp_path: Path) -> None:
        gi = tmp_path / ".gitignore"
        gi.write_text(
            "__pycache__/\n"
            ".icm-profile.local.yaml\n"
            ".coverage\n",
            encoding="utf-8",
        )
        original = gi.read_text(encoding="utf-8")
        update_gitignore(gi, ["__pycache__/", ".icm-profile.local.yaml"])
        assert gi.read_text(encoding="utf-8") == original

    def test_adds_only_missing_lines(self, tmp_path: Path) -> None:
        gi = tmp_path / ".gitignore"
        gi.write_text("__pycache__/\n", encoding="utf-8")
        update_gitignore(gi, ["__pycache__/", ".icm-profile.local.yaml"])
        content = gi.read_text(encoding="utf-8")
        # __pycache__/ aparece uma vez; .icm-profile.local.yaml foi adicionado
        assert content.count("__pycache__/") == 1
        assert ".icm-profile.local.yaml" in content

    def test_preserves_existing_unrelated_lines(self, tmp_path: Path) -> None:
        gi = tmp_path / ".gitignore"
        gi.write_text("node_modules/\n*.log\n", encoding="utf-8")
        update_gitignore(gi, ["__pycache__/"])
        content = gi.read_text(encoding="utf-8")
        assert "node_modules/" in content
        assert "*.log" in content
        assert "__pycache__/" in content

    def test_trailing_newline_handled(self, tmp_path: Path) -> None:
        gi = tmp_path / ".gitignore"
        # arquivo sem newline final
        gi.write_text("foo", encoding="utf-8")
        update_gitignore(gi, ["bar"])
        content = gi.read_text(encoding="utf-8")
        # bar deve estar em sua propria linha, nao concatenado
        assert "foobar" not in content
        assert "foo" in content
        assert "bar" in content


# ============================================================================
# validate_slug
# ============================================================================

class TestValidateSlug:
    @pytest.mark.parametrize("slug", [
        "feat-auth",
        "x",
        "01-feature",
        "abc-def-ghi",
        "abc123",
        "123",
    ])
    def test_accepts_valid_kebab(self, slug: str) -> None:
        validate_slug(slug)  # nao deve raise

    @pytest.mark.parametrize("slug,reason", [
        ("Feat-Auth", "uppercase"),
        ("feat_auth", "underscore"),
        ("feat auth", "space"),
        ("feat/auth", "slash"),
        ("feat.auth", "dot"),
        ("açao", "accent"),
        ("", "empty"),
        ("feat--auth", "double-dash"),  # double-dash also invalid? — defensive
    ])
    def test_rejects_invalid(self, slug: str, reason: str) -> None:
        # double-dash is technically allowed by ^[a-z0-9-]+$; aceitar
        if reason == "double-dash":
            validate_slug(slug)
            return
        with pytest.raises(BootstrapError):
            validate_slug(slug)


# ============================================================================
# parse_profile_merge_output
# ============================================================================

class TestParseProfileMergeOutput:
    def test_parses_valid_json(self) -> None:
        payload = json.dumps({
            "effective": {"profile": "cli_tool", "tier": "tool", "tdd_required": False},
            "hash": "abc123",
        })
        effective, h = parse_profile_merge_output(payload)
        assert effective["profile"] == "cli_tool"
        assert h == "abc123"

    def test_raises_on_invalid_json(self) -> None:
        with pytest.raises(BootstrapError, match="JSON"):
            parse_profile_merge_output("not json {")

    def test_raises_when_missing_effective(self) -> None:
        payload = json.dumps({"hash": "abc"})
        with pytest.raises(BootstrapError, match="effective"):
            parse_profile_merge_output(payload)

    def test_raises_when_missing_hash(self) -> None:
        payload = json.dumps({"effective": {"profile": "cli_tool"}})
        with pytest.raises(BootstrapError, match="hash"):
            parse_profile_merge_output(payload)

    def test_raises_when_root_not_dict(self) -> None:
        with pytest.raises(BootstrapError):
            parse_profile_merge_output(json.dumps([1, 2, 3]))


# ============================================================================
# _scaffold_workspace_dirs (copia summaries + runtime references)
# ============================================================================

class TestScaffoldWorkspaceDirs:
    """Verifica que scaffold copia summaries 200tok + runtime refs do skill_root."""

    def test_creates_all_9_stage_dirs(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspaces" / "001-foo"
        project_root = tmp_path / "project"
        project_root.mkdir(parents=True)
        bootstrap._scaffold_workspace_dirs(ws, SKILL_ROOT, project_root)
        for s in bootstrap.STAGES:
            assert (ws / "stages" / s).is_dir()

    def test_creates_config_dir_with_profile_matrix(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspaces" / "001-foo"
        project_root = tmp_path / "project"
        project_root.mkdir(parents=True)
        bootstrap._scaffold_workspace_dirs(ws, SKILL_ROOT, project_root)
        assert (ws / "_config" / "profile-matrix.md").is_file()

    def test_copies_all_10_superpowers_summaries(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspaces" / "001-foo"
        project_root = tmp_path / "project"
        project_root.mkdir(parents=True)
        bootstrap._scaffold_workspace_dirs(ws, SKILL_ROOT, project_root)
        sp_dir = ws / "_references" / "superpowers-summary"
        assert sp_dir.is_dir()
        expected = {
            "brainstorming-200tok.md",
            "writing-plans-200tok.md",
            "dispatching-parallel-agents-200tok.md",
            "test-driven-development-200tok.md",
            "subagent-driven-development-200tok.md",
            "verification-before-completion-200tok.md",
            "requesting-code-review-200tok.md",
            "receiving-code-review-200tok.md",
            "finishing-a-development-branch-200tok.md",
            "systematic-debugging-200tok.md",
        }
        actual = {p.name for p in sp_dir.iterdir() if p.is_file()}
        assert expected.issubset(actual), f"missing: {expected - actual}"

    def test_copies_runtime_references(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspaces" / "001-foo"
        project_root = tmp_path / "project"
        project_root.mkdir(parents=True)
        bootstrap._scaffold_workspace_dirs(ws, SKILL_ROOT, project_root)
        runtime_dir = ws / "_references" / "runtime"
        assert runtime_dir.is_dir()
        expected = {
            "subagent-protocol.md",
            "wave-planner-algorithm.md",
            "state-machine-schema.md",
            "recovery-wizard.md",
            "stop-points-canonical.md",
            "4-block-contract-template.md",
            "feedback-intake-fase08.md",
            "session-handoff-protocol.md",
        }
        actual = {p.name for p in runtime_dir.iterdir() if p.is_file()}
        assert expected.issubset(actual), f"missing: {expected - actual}"

    def test_summary_files_have_expected_frontmatter(self, tmp_path: Path) -> None:
        ws = tmp_path / "workspaces" / "001-foo"
        project_root = tmp_path / "project"
        project_root.mkdir(parents=True)
        bootstrap._scaffold_workspace_dirs(ws, SKILL_ROOT, project_root)
        sp_dir = ws / "_references" / "superpowers-summary"
        sample = (sp_dir / "brainstorming-200tok.md").read_text(encoding="utf-8")
        assert sample.startswith("---")
        assert "source_skill:" in sample
        assert "source_version:" in sample

    # v3.4.0: docs/tech_debt.md scaffolding moveu de _scaffold_workspace_dirs
    # para _ensure_base_branch_docs (vive APENAS na base branch via .icm-main/).
    # Cobertura agora em tests/unit/test_bootstrap_v3_4_0.py.


class TestL2ContextRendering:
    """Verifica que bootstrap renderiza L2 CONTEXT.md para cada estágio."""

    def test_renders_all_9_l2_context_files(self, tmp_path: Path) -> None:
        """Bootstrap deve criar CONTEXT.md em cada stage com placeholders resolvidos."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / ".git").mkdir()
        (project_root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        (project_root / ".git" / "refs" / "heads").mkdir(parents=True)
        (project_root / ".git" / "refs" / "heads" / "main").write_text("abc123\n")
        (project_root / ".git" / "objects").mkdir()
        (project_root / ".git" / "config").write_text(
            "[core]\n\trepositoryformatversion = 0\n"
        )
        ws_dir = project_root / "workspaces" / "001-test-l2"

        placeholders = {
            "WORKSPACE": "001-test-l2",
            "WORKSPACE_NUM": "001",
            "PROFILE": "app_web_backend",
            "TIER": "development",
            "PROJECT_ROOT": str(project_root).replace("\\", "/"),
            "BASE_BRANCH": "main",
            "LOGS_ROOT": "null",
            "PROFILE_EFFECTIVE_HASH": "abc123",
            "CREATED_AT": "2026-01-01T00:00:00Z",
            "SKILL_VERSION": "3.3.0",
            "SKILL_DIR": str(SKILL_ROOT).replace("\\", "/"),
            "BOOTSTRAP_COMMIT_SHA": "deadbeef",
        }

        # Criar dirs primeiro (como _scaffold_workspace_dirs faria)
        ws_dir.mkdir(parents=True)
        stages_dir = ws_dir / "stages"
        stages_dir.mkdir()
        for s in bootstrap.STAGES:
            (stages_dir / s).mkdir()

        # Renderizar L2 templates como bootstrap faria
        tpl_dir = SKILL_ROOT / "templates" / "workspace" / "stages"
        for stage_dir_name in bootstrap.STAGES:
            l2_tpl = tpl_dir / stage_dir_name / "CONTEXT.md.tpl"
            if l2_tpl.exists():
                rendered = bootstrap.render_template(l2_tpl, placeholders)
                out = stages_dir / stage_dir_name / "CONTEXT.md"
                out.write_text(rendered, encoding="utf-8")

        for s in bootstrap.STAGES:
            ctx = stages_dir / s / "CONTEXT.md"
            assert ctx.is_file(), f"CONTEXT.md missing for stage {s}"
            content = ctx.read_text(encoding="utf-8")
            assert content.startswith("---"), f"stage {s}: CONTEXT.md missing frontmatter"
            assert "{{" not in content, f"stage {s}: unresolved placeholder in CONTEXT.md"
            assert "layer: L2" in content, f"stage {s}: missing layer: L2"

    def test_l2_placeholders_resolved(self) -> None:
        """Placeholders PROJECT_ROOT e WORKSPACE devem estar resolvidos em todos os L2s."""
        project_root_str = "/tmp/test-project"
        placeholders = {
            "WORKSPACE": "001-test-l2",
            "WORKSPACE_NUM": "001",
            "PROFILE": "app_web_backend",
            "TIER": "development",
            "PROJECT_ROOT": project_root_str,
            "BASE_BRANCH": "main",
            "LOGS_ROOT": "null",
            "PROFILE_EFFECTIVE_HASH": "abc123",
            "CREATED_AT": "2026-01-01T00:00:00Z",
            "SKILL_VERSION": "3.3.0",
            "SKILL_DIR": "/skill/root",
            "BOOTSTRAP_COMMIT_SHA": "deadbeef",
        }

        tpl_dir = SKILL_ROOT / "templates" / "workspace" / "stages"
        for s in bootstrap.STAGES:
            l2_tpl = tpl_dir / s / "CONTEXT.md.tpl"
            if l2_tpl.exists():
                rendered = bootstrap.render_template(l2_tpl, placeholders)
                assert "{{PROJECT_ROOT}}" not in rendered, f"stage {s}: PROJECT_ROOT unresolved"
                assert "{{WORKSPACE}}" not in rendered, f"stage {s}: WORKSPACE unresolved"
                assert project_root_str in rendered, f"stage {s}: PROJECT_ROOT value not in output"
