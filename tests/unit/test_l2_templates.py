"""Tests dos 9 L2 templates (`templates/workspace/stages/<NN>_<slug>/CONTEXT.md.tpl`).

Valida schema canônico definido em `references/stage-templates.md`:
  - frontmatter parseável + campos obrigatórios
  - sub_stage_enum bate com state-machine-schema.md
  - applicable_stop_points subset de IDs canônicos
  - tabela Inputs presente com L0/L1/L2 mínimos
  - seção Não Lê presente
  - output_files frontmatter == paths citados em Outputs
  - next_stage válido
  - placeholders permitidos apenas
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STAGES_DIR = REPO_ROOT / "templates" / "workspace" / "stages"
REFERENCES_DIR = REPO_ROOT / "references"

# IDs canônicos do plan §4.9 / references/stop-points-canonical.md
CANONICAL_STOP_POINT_IDS = {
    "stack", "db", "external_api", "new_dep", "paid_service",
    "irreversible", "over_eng", "pii", "prod_migration", "adr_drift",
    "workspace_corrupt", "profile_mismatch",
    # v3.6.0 preview loop
    "feedback_ambiguous", "design_system_cascade",
}

# Sub_stage enum canônico do state-machine-schema.md §Sub-stage enum
CANONICAL_SUB_STAGE = {
    "00": {"00_in_progress", "00_completed"},
    "01": {"01_in_progress", "01_completed"},
    "02": {"02_in_progress", "02_completed"},
    "03": {"03_in_progress", "03_completed"},
    # 04 usa regex pattern (sub_stage_pattern key); validado separadamente
    "05": {"05_in_progress", "05_completed"},
    "06": {"06_in_progress", "06_completed"},
    "07": {"07_in_progress", "07_completed"},
    "08": {"08_in_progress", "08_decided_A", "08_decided_B", "08_decided_C"},
}

ALLOWED_PLACEHOLDERS = {
    # bootstrap.py canonical set
    "WORKSPACE", "WORKSPACE_NUM", "PROFILE", "TIER", "PROJECT_ROOT", "BASE_BRANCH",
    "LOGS_ROOT", "PROFILE_EFFECTIVE_HASH", "CREATED_AT", "SKILL_VERSION",
    "BOOTSTRAP_COMMIT_SHA",
    # extras úteis em L2 templates (skill-resolved no bootstrap)
    "SKILL_DIR",
}

REQUIRED_FRONTMATTER_FIELDS = {
    "layer", "stage", "stage_name", "sub_stage_enum",
    "applicable_stop_points", "output_files", "next_stage",
}

STAGE_SLUGS = {
    "00": "recon",
    "01": "discovery",
    "02": "design",
    "03": "wave_planner",
    "04": "implementation_waves",
    "05": "verification",
    "06": "review",
    "07": "merge",
    "08": "feedback_intake",
}

# Stages cujo applicable_stop_points DEVE ser vazio (determinísticos / sem decisão)
EMPTY_STOP_POINTS_STAGES = {"03", "05", "08"}


def parse_l2_template(path: Path) -> tuple[dict, str]:
    """Parse `.tpl` L2 → (frontmatter dict, body str). Levanta se malformado."""
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        raise ValueError(f"{path}: missing frontmatter delimiter")
    parts = content.split("---\n", 2)
    if len(parts) < 3:
        raise ValueError(f"{path}: malformed frontmatter")
    frontmatter = yaml.safe_load(parts[1])
    body = parts[2]
    return frontmatter, body


def template_path(stage: str) -> Path:
    return STAGES_DIR / f"{stage}_{STAGE_SLUGS[stage]}" / "CONTEXT.md.tpl"


def extract_used_placeholders(body: str) -> set[str]:
    """Extrai nomes de placeholders Jinja `{{NOME}}` usados no body + frontmatter raw."""
    return set(re.findall(r"\{\{\s*([A-Z_][A-Z0-9_]*)\s*\}\}", body))


def extract_outputs_section_paths(body: str) -> list[str]:
    """Extrai paths citados em `## Outputs` (linhas com backticks ou bullets)."""
    match = re.search(r"## Outputs\s*\n(.+?)(?=\n## |\Z)", body, re.DOTALL)
    if not match:
        return []
    section = match.group(1)
    paths = re.findall(r"`(output/[^`]+)`", section)
    return paths


# ---- Per-stage parametrized tests ----------------------------------------

@pytest.mark.parametrize("stage", list(STAGE_SLUGS.keys()))
def test_l2_template_exists(stage: str):
    path = template_path(stage)
    assert path.exists(), f"L2 template ausente: {path}"


@pytest.mark.parametrize("stage", list(STAGE_SLUGS.keys()))
def test_l2_frontmatter_parses(stage: str):
    fm, _ = parse_l2_template(template_path(stage))
    assert isinstance(fm, dict)


@pytest.mark.parametrize("stage", list(STAGE_SLUGS.keys()))
def test_l2_frontmatter_required_fields(stage: str):
    fm, _ = parse_l2_template(template_path(stage))
    missing = REQUIRED_FRONTMATTER_FIELDS - set(fm.keys())
    assert not missing, f"stage {stage}: campos faltando {missing}"


@pytest.mark.parametrize("stage", list(STAGE_SLUGS.keys()))
def test_l2_layer_is_l2(stage: str):
    fm, _ = parse_l2_template(template_path(stage))
    assert fm["layer"] == "L2"


@pytest.mark.parametrize("stage", list(STAGE_SLUGS.keys()))
def test_l2_stage_id_matches_directory(stage: str):
    fm, _ = parse_l2_template(template_path(stage))
    assert fm["stage"] == stage
    assert fm["stage_name"] == STAGE_SLUGS[stage]


@pytest.mark.parametrize("stage", [s for s in STAGE_SLUGS if s != "04"])
def test_l2_sub_stage_enum_matches_canonical(stage: str):
    fm, _ = parse_l2_template(template_path(stage))
    declared = set(fm["sub_stage_enum"])
    expected = CANONICAL_SUB_STAGE[stage]
    assert declared == expected, f"stage {stage}: enum {declared} != canonical {expected}"


def test_l2_04_sub_stage_pattern_is_valid_regex():
    fm, _ = parse_l2_template(template_path("04"))
    pattern = fm.get("sub_stage_pattern")
    assert pattern, "stage 04 deve declarar sub_stage_pattern"
    # regex compila
    compiled = re.compile(pattern)
    # casa exemplos válidos
    assert compiled.match("04_wave_1_in_progress")
    assert compiled.match("04_wave_42_completed")
    # rejeita inválidos
    assert not compiled.match("04_in_progress")
    assert not compiled.match("04_wave_a_completed")


@pytest.mark.parametrize("stage", list(STAGE_SLUGS.keys()))
def test_l2_applicable_stop_points_subset_of_canonical(stage: str):
    fm, _ = parse_l2_template(template_path(stage))
    declared = set(fm["applicable_stop_points"])
    invalid = declared - CANONICAL_STOP_POINT_IDS
    assert not invalid, f"stage {stage}: stop points não-canônicos {invalid}"


@pytest.mark.parametrize("stage", sorted(EMPTY_STOP_POINTS_STAGES))
def test_l2_empty_stop_points_for_deterministic_stages(stage: str):
    fm, _ = parse_l2_template(template_path(stage))
    assert fm["applicable_stop_points"] == [], (
        f"stage {stage}: deve ter applicable_stop_points vazio (determinístico/sem decisão)"
    )


@pytest.mark.parametrize("stage", list(STAGE_SLUGS.keys()))
def test_l2_inputs_table_has_l0_l1_l2(stage: str):
    _, body = parse_l2_template(template_path(stage))
    assert "## Inputs" in body, f"stage {stage}: seção Inputs ausente"
    # checa que há ≥3 linhas com L0, L1, L2 marcados
    assert "| L0 |" in body, f"stage {stage}: linha L0 ausente em Inputs"
    assert "| L1 |" in body, f"stage {stage}: linha L1 ausente em Inputs"
    assert "| L2 |" in body, f"stage {stage}: linha L2 ausente em Inputs"


@pytest.mark.parametrize("stage", list(STAGE_SLUGS.keys()))
def test_l2_nao_le_section_present(stage: str):
    _, body = parse_l2_template(template_path(stage))
    assert "## Não Lê" in body, f"stage {stage}: seção 'Não Lê' ausente"


@pytest.mark.parametrize("stage", list(STAGE_SLUGS.keys()))
def test_l2_output_files_match_outputs_section(stage: str):
    fm, body = parse_l2_template(template_path(stage))
    declared = set(fm["output_files"])
    cited = set(extract_outputs_section_paths(body))
    # output_files mandatórios presentes no body (subset relação — body pode citar mais detalhes)
    missing_in_body = {p for p in declared if not p.endswith("(opcional)") and "(opcional)" not in p}
    missing_in_body = {p for p in missing_in_body if p not in cited}
    # opcionais permitidos não estarem no body se claramente marcados
    if missing_in_body:
        # tolera se output_files contém path que aparece no body sem backticks
        plain_text = body
        truly_missing = {p for p in missing_in_body if p not in plain_text}
        assert not truly_missing, (
            f"stage {stage}: output_files {truly_missing} declarado mas não citado em body"
        )


@pytest.mark.parametrize(
    "stage,expected_next",
    [
        ("00", "01"),
        ("01", "02"),
        ("02", "03"),
        ("03", "04"),
        ("04", "05"),
        ("05", "06"),
        ("06", "07"),
        ("07", "08"),
        ("08", None),
    ],
)
def test_l2_next_stage_valid(stage: str, expected_next):
    fm, _ = parse_l2_template(template_path(stage))
    assert fm["next_stage"] == expected_next, (
        f"stage {stage}: next_stage {fm['next_stage']!r} != esperado {expected_next!r}"
    )


@pytest.mark.parametrize("stage", list(STAGE_SLUGS.keys()))
def test_l2_placeholders_only_allowed(stage: str):
    path = template_path(stage)
    raw = path.read_text(encoding="utf-8")
    used = extract_used_placeholders(raw)
    invalid = used - ALLOWED_PLACEHOLDERS
    assert not invalid, f"stage {stage}: placeholders não-permitidos {invalid}"


@pytest.mark.parametrize("stage", list(STAGE_SLUGS.keys()))
def test_l2_uses_project_root_and_workspace_placeholders(stage: str):
    path = template_path(stage)
    raw = path.read_text(encoding="utf-8")
    used = extract_used_placeholders(raw)
    assert "PROJECT_ROOT" in used, f"stage {stage}: PROJECT_ROOT não usado"
    assert "WORKSPACE" in used, f"stage {stage}: WORKSPACE não usado"


# ---- Cross-stage invariants ----------------------------------------------

def test_all_9_stages_present():
    for stage in STAGE_SLUGS:
        assert template_path(stage).exists(), f"stage {stage}: template ausente"


def test_no_path_relative_in_inputs():
    """Nenhum L2 deve usar `../../` ou paths relativos."""
    for stage in STAGE_SLUGS:
        body = template_path(stage).read_text(encoding="utf-8")
        assert "../" not in body, f"stage {stage}: path relativo `../` detectado"


def test_canonical_stop_points_doc_exists():
    """Test guard: doc canônico existe (parser carrega catálogo dele em runtime)."""
    canonical = REFERENCES_DIR / "stop-points-canonical.md"
    assert canonical.exists()


def test_state_machine_schema_doc_exists():
    """Test guard: schema doc existe (sub_stage enum vem dali)."""
    schema = REFERENCES_DIR / "state-machine-schema.md"
    assert schema.exists()
