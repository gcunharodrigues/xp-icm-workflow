"""Drift detection — bloqueia inconsistências cross-file.

7 detectores:
A. Versão consistente (canonical = scripts/bootstrap.py SKILL_VERSION)
B. Profile count consistente (canonical = len(CANONICAL_PROFILES))
C. Status enum sync (validate_state.py ALLOWED_STATUSES vs schema doc)
D. Status canônicos esperados presentes (allow-list anti-typo)
E. Cross-refs markdown resolvem em references/
F. Shell templates sem CRLF (CRLF no shebang quebra exec — kernel
   procura interpretador 'bash\\r' e falha com "No such file or directory")
H. Scripts source-of-truth version sync — `CURRENT_SKILL_VERSION = "X.Y.Z"`
   + última entry de `SUPPORTED_VERSIONS = (...)` em scripts/*.py devem
   bater canonical (regra v3.7.2: pega drift em scripts auxiliares como
   migrate-workspace.py que não estavam em VERSION_MUST_MATCH).

Whitelist exceptions explícitas — nunca grep-and-update silencioso.
"""
import importlib.util
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ============================================================
# A. Version consistency
# ============================================================

VERSION_RE = re.compile(r"v(\d+\.\d+\.\d+)")

# Whitelist: arquivos que LEGITIMAMENTE mencionam versões antigas
# (changelog histórico, scripts de migração com target específico,
# kickoffs arquivados). Caminho relativo a REPO_ROOT (posix-style).
VERSION_WHITELIST = {
    "references/changelog.md",
    "scripts/migrate-v3.3-to-v3.4.py",
    "_KICKOFF-v3.4.0-finish.md",
    "tests/unit/test_migrate_v3_3_to_v3_4.py",
    "tests/unit/test_bootstrap.py",
    "tests/unit/test_stop_points_render.py",
    "docs/plans",
    "references/v2.4-snapshot",
    "references/example-run.md",  # menciona v3.0.0-beta5 + v2.4 (histórico)
}

# Arquivos que DEVEM mencionar a versão canônica.
# Toda mudança em SKILL_VERSION exige bump em TODOS estes (regra v3.7.0).
VERSION_MUST_MATCH = [
    ("SKILL.md", r"# xp-icm-workflow v(\d+\.\d+\.\d+)"),
    ("README.md", r"version-v(\d+\.\d+\.\d+)"),
    ("references/design-system.md", r"format \(v(\d+\.\d+\.\d+)\)"),
    (
        "references/preview-loop-protocol.md",
        r"build-iterate visual \(v(\d+\.\d+\.\d+)\)",
    ),
    # v3.7.2: scripts canônicos de orquestração também devem bater
    (
        "scripts/migrate-workspace.py",
        r'CURRENT_SKILL_VERSION\s*=\s*"(\d+\.\d+\.\d+)"',
    ),
]


def _canonical_version() -> str:
    bootstrap = _load_module("bootstrap", REPO_ROOT / "scripts" / "bootstrap.py")
    return bootstrap.SKILL_VERSION


def test_version_consistency_canonical_files():
    """Arquivos canônicos devem refletir SKILL_VERSION."""
    canonical = _canonical_version()
    for rel_path, pattern in VERSION_MUST_MATCH:
        path = REPO_ROOT / rel_path
        text = path.read_text(encoding="utf-8")
        match = re.search(pattern, text)
        assert match is not None, f"{rel_path}: pattern '{pattern}' não encontrado"
        assert match.group(1) == canonical, \
            f"{rel_path}: versão {match.group(1)} ≠ canonical {canonical}"


def test_changelog_has_entry_for_canonical_version():
    """Toda SKILL_VERSION nova exige entry em references/changelog.md.

    Regra v3.7.0: bump SKILL_VERSION sem entry no changelog é drift.
    Pattern aceita "## vX.Y.Z" no início de linha (header de seção).
    """
    canonical = _canonical_version()
    changelog = (REPO_ROOT / "references" / "changelog.md").read_text(encoding="utf-8")
    pattern = re.compile(rf"^## v{re.escape(canonical)}\b", re.MULTILINE)
    assert pattern.search(changelog), (
        f"references/changelog.md não tem entry '## v{canonical}'. "
        f"Toda mudança de SKILL_VERSION exige changelog entry "
        f"(regra drift v3.7.0)."
    )


# ============================================================
# B. Profile count consistency
# ============================================================

# Regex captura claims canônicos sobre profile count total. Ignora menções
# context-specific tipo "os 3 profiles X/Y/Z" (subset).
# Match patterns: "N profiles × 4 tiers", "N profiles canônicos", "N profiles
# canonicos x 4 tiers", "N profiles (e.g.,", "Demais N profiles"
PROFILE_COUNT_RE = re.compile(
    r"(\d+)\s+profiles\b\s*(?:×|x\s+\d|canôn|canon|\(e\.g|\(incl)",
    re.IGNORECASE,
)
# Pattern adicional: "Demais N profiles" (= total - listed)
PROFILE_REMAINDER_RE = re.compile(r"Demais\s+(\d+)\s+profiles\b")

# Hardened (v3.7.0): pega formatos missados pelo PROFILE_COUNT_RE original.
# Cobre:
#   - "Profiles canônicos (N):" / "Profiles canonicos (N)"
#   - "(N × 4 = M combos)" / "(N x 4 = M combos)"
PROFILE_COUNT_PARENS_RE = re.compile(
    r"Profiles\s+can(?:ô|o)nicos\s*\((\d+)\)",
    re.IGNORECASE,
)
PROFILE_COMBO_RE = re.compile(
    r"\((\d+)\s*[×x]\s*(\d+)\s*=\s*(\d+)\s*combos?\)",
    re.IGNORECASE,
)

PROFILE_COUNT_WHITELIST = {
    "references/changelog.md",
    "docs/plans",
    "references/v2.4-snapshot",
}


def _canonical_profile_count() -> int:
    pm = _load_module("profile_merge", REPO_ROOT / "scripts" / "profile-merge.py")
    return len(pm.CANONICAL_PROFILES)


def _is_whitelisted(rel_path: str, whitelist: set) -> bool:
    return any(
        rel_path == w or rel_path.startswith(w + "/")
        for w in whitelist
    )


CANONICAL_TIERS_COUNT = 4  # CANONICAL_TIERS em profile-merge.py


def _check_profile_count_in_file(path: Path, canonical: int) -> list:
    """Retorna lista de violações no arquivo."""
    rel = path.relative_to(REPO_ROOT).as_posix()
    if _is_whitelisted(rel, PROFILE_COUNT_WHITELIST):
        return []
    text = path.read_text(encoding="utf-8")
    violations = []
    for match in PROFILE_COUNT_RE.finditer(text):
        n = int(match.group(1))
        if n != canonical:
            violations.append(f"{rel}: '{match.group(0)}' (canonical {canonical})")
    # "Demais N profiles" — remainder, espera-se total - explicit listed na mesma table
    # Heurística simples: se aparecer, deve ser pelo menos 1 a menos que canonical
    for match in PROFILE_REMAINDER_RE.finditer(text):
        n = int(match.group(1))
        if n >= canonical:
            violations.append(
                f"{rel}: '{match.group(0)}' >= canonical {canonical} (impossível)"
            )
    # Hardened v3.7.0: "Profiles canônicos (N):" format
    for match in PROFILE_COUNT_PARENS_RE.finditer(text):
        n = int(match.group(1))
        if n != canonical:
            violations.append(
                f"{rel}: '{match.group(0)}' (canonical {canonical})"
            )
    # Hardened v3.7.0: "(N × T = M combos)" format
    for match in PROFILE_COMBO_RE.finditer(text):
        n_profiles = int(match.group(1))
        n_tiers = int(match.group(2))
        n_combos = int(match.group(3))
        if n_profiles != canonical:
            violations.append(
                f"{rel}: '{match.group(0)}' profile count {n_profiles} ≠ "
                f"canonical {canonical}"
            )
        if n_tiers != CANONICAL_TIERS_COUNT:
            violations.append(
                f"{rel}: '{match.group(0)}' tier count {n_tiers} ≠ "
                f"canonical {CANONICAL_TIERS_COUNT}"
            )
        if n_combos != canonical * CANONICAL_TIERS_COUNT:
            violations.append(
                f"{rel}: '{match.group(0)}' combos {n_combos} ≠ "
                f"{canonical}×{CANONICAL_TIERS_COUNT}={canonical * CANONICAL_TIERS_COUNT}"
            )
    return violations


def test_profile_count_consistency():
    """Toda menção canônica a 'N profiles' deve bater com len(CANONICAL_PROFILES)."""
    canonical = _canonical_profile_count()
    violations = []
    for path in REPO_ROOT.rglob("*.md"):
        violations.extend(_check_profile_count_in_file(path, canonical))
    for path in REPO_ROOT.rglob("*.py"):
        violations.extend(_check_profile_count_in_file(path, canonical))
    assert not violations, "Profile count drift:\n  " + "\n  ".join(violations)


# ============================================================
# C. Status enum sync
# ============================================================

EXPECTED_STATUSES = {
    "IN_PROGRESS",
    "COMPLETED",
    "COMPLETED_AWAITING_HUMAN",
    "BLOCKED_STOP_POINT",
    "BLOCKED_ERROR",
    "BLOCKED_HITL",
}


def _validator_statuses() -> set:
    """Importa ALLOWED_STATUSES do validate_state.py (single source)."""
    vs = _load_module("validate_state", REPO_ROOT / "scripts" / "validate_state.py")
    return set(vs.ALLOWED_STATUSES)


def _schema_statuses() -> set:
    """Extrai status canônicos de state-machine-schema.md table rows."""
    text = (REPO_ROOT / "references" / "state-machine-schema.md").read_text(encoding="utf-8")
    # Pattern: linhas tipo `| \`STATUS_NAME\` | ...`
    return set(re.findall(r"^\|\s*`([A-Z_]+)`\s*\|", text, flags=re.MULTILINE))


def test_validator_has_expected_statuses():
    """validate_state.py ALLOWED_STATUSES cobre todos statuses canônicos."""
    validator = _validator_statuses()
    missing = EXPECTED_STATUSES - validator
    assert not missing, f"validate_state.py falta: {missing}"


def test_schema_doc_has_expected_statuses():
    """state-machine-schema.md table cobre todos statuses canônicos."""
    schema = _schema_statuses()
    missing = EXPECTED_STATUSES - schema
    assert not missing, f"state-machine-schema.md falta rows: {missing}"


def test_validator_schema_in_sync():
    """Validator ↔ schema: todo status no validator está no schema."""
    validator = _validator_statuses()
    schema = _schema_statuses()
    only_validator = validator - schema
    assert not only_validator, \
        f"validator tem statuses ausentes no schema: {only_validator}"


# ============================================================
# D. Markdown cross-ref resolves em references/
# ============================================================

MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


# ============================================================
# F. Shell templates sem CRLF
# ============================================================

# Templates whitelist (CRLF aceitável) — vazio por padrão. Adicionar entry
# APENAS se o arquivo NÃO é executado via shebang (ex: doc/example).
SHELL_CRLF_WHITELIST: set[str] = set()


def test_shell_templates_no_crlf():
    """Templates .sh em templates/ não devem ter CRLF.

    Bug: shutil.copy2 preserva bytes; CRLF do template cai no destino.
    Kernel exec do shebang procura literal 'bash\\r' → "No such file
    or directory". bootstrap.py normaliza na cópia, mas template-source
    com CRLF arrisca regressão se alguma cópia futura voltar a copy2.
    """
    templates_root = REPO_ROOT / "templates"
    if not templates_root.exists():
        pytest.skip("templates/ não existe")
    violations = []
    for sh in templates_root.rglob("*.sh"):
        rel = sh.relative_to(REPO_ROOT).as_posix()
        if rel in SHELL_CRLF_WHITELIST:
            continue
        raw = sh.read_bytes()
        if b"\r\n" in raw:
            violations.append(rel)
    assert not violations, (
        "Templates .sh com CRLF (use LF; rode `python -c \"import "
        "pathlib; [p.write_bytes(p.read_bytes().replace(b'\\r\\n',b'\\n')) "
        "for p in pathlib.Path('templates').rglob('*.sh')]\"`):\n  "
        + "\n  ".join(violations)
    )


def test_git_hook_templates_no_crlf():
    """Templates .git-hooks/ — git executa via shebang exec mesma classe."""
    hooks_root = REPO_ROOT / "templates" / ".git-hooks"
    if not hooks_root.exists():
        pytest.skip("templates/.git-hooks/ não existe")
    violations = []
    for hook in hooks_root.iterdir():
        if not hook.is_file():
            continue
        raw = hook.read_bytes()
        if b"\r\n" in raw:
            violations.append(hook.relative_to(REPO_ROOT).as_posix())
    assert not violations, (
        "Git hook templates com CRLF:\n  " + "\n  ".join(violations)
    )


# ============================================================
# G. Plan.md schema sync — parser regex ↔ template doc
# ============================================================
#
# Bug histórico: LLM (designer fase 02) gera plan.md com headings em
# h4/h5 ao invés de h2/h3 do schema canônico. Wave-planner em fase 03
# falha com "no tasks found" ou retorna lista vazia silenciosamente.
# Causa raiz frequente: schema do template alterado sem atualizar parser
# (ou vice-versa). Estes testes congelam o contrato.

def _wave_planner_module():
    """Importa wave-planner-script.py com registro em sys.modules ANTES
    de exec_module — exigência do @dataclass do Task pra resolver type
    annotations via lookup em sys.modules[cls.__module__].
    """
    import sys
    name = "wave_planner_script_drift"
    spec = importlib.util.spec_from_file_location(
        name, REPO_ROOT / "scripts" / "wave-planner-script.py",
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_4block_template_uses_canonical_heading_levels():
    """4-block-contract-template.md deve declarar schema com h2 (Task) e
    h3 (subseções). Mudança aqui sem ajustar parser quebra geração.
    """
    template = (REPO_ROOT / "references" / "4-block-contract-template.md").read_text(
        encoding="utf-8"
    )
    assert "## Task <SLUG>:" in template, \
        "4-block-contract-template.md falta '## Task <SLUG>:' (schema h2)"
    for section in ("### O QUE", "### COMO", "### NÃO QUERO", "### VALIDAÇÃO"):
        assert section in template, \
            f"4-block-contract-template.md falta '{section}' (h3)"
    for section in ("### Files touched", "### Depends on"):
        assert section in template, \
            f"4-block-contract-template.md falta '{section}' (h3)"


def test_parser_regex_matches_template_canonical_example():
    """SLUG_RE do parser deve casar header de exemplo concreto §6.1
    (`## Task auth-middleware: JWT validation middleware`). Drift entre
    parser e schema canônico = LLM segue template, parser rejeita.
    """
    module = _wave_planner_module()
    template = (REPO_ROOT / "references" / "4-block-contract-template.md").read_text(
        encoding="utf-8"
    )
    matches = module.SLUG_RE.findall(template)
    assert "auth-middleware" in matches, (
        f"parser SLUG_RE não casa exemplo do template (got {matches}). "
        "Schema canônico em references/4-block-contract-template.md §6.1."
    )


def test_parser_drift_detector_rejects_h4_task():
    """`_detect_heading_drift` deve abortar em '#### Task ...' (h4).
    Garante guard em parse_plan permanece ativo.
    """
    module = _wave_planner_module()
    bad = "#### Task foo: bar\n\n##### O QUE\n- x\n"
    with pytest.raises(module.WavePlannerError, match="heading drift"):
        module._detect_heading_drift(bad)


def test_parser_drift_detector_passes_canonical_h2():
    """Plan.md correto (h2 + h3) não deve disparar drift detector."""
    module = _wave_planner_module()
    good = (
        "## Task foo: Foo\n\n"
        "### O QUE\n- x\n\n"
        "### Files touched\n- src/foo.ts\n\n"
        "### Depends on\n\n"
    )
    module._detect_heading_drift(good)  # não levanta


# ============================================================
# H. Scripts source-of-truth version sync (v3.7.2)
# ============================================================
#
# Detecta scripts auxiliares que mantêm cópia local de SKILL_VERSION
# (ex: migrate-workspace.py CURRENT_SKILL_VERSION + SUPPORTED_VERSIONS
# tuple). VERSION_MUST_MATCH cobre arquivos canônicos com pattern fixo;
# este detector é genérico — varre scripts/**/*.py por dois padrões e
# valida == canonical.

SCRIPT_CURRENT_VERSION_RE = re.compile(
    r'CURRENT_SKILL_VERSION\s*=\s*"(\d+\.\d+\.\d+)"'
)
SCRIPT_SUPPORTED_LAST_RE = re.compile(
    r'SUPPORTED_VERSIONS[^=]*=\s*\((?P<body>[^)]*)\)',
    re.DOTALL,
)
SEMVER_RE = re.compile(r'"(\d+\.\d+\.\d+)"')


def _scripts_version_violations(canonical: str) -> list[str]:
    violations = []
    scripts_dir = REPO_ROOT / "scripts"
    if not scripts_dir.is_dir():
        return violations
    for py in scripts_dir.rglob("*.py"):
        rel = py.relative_to(REPO_ROOT).as_posix()
        # migrate-v3.3-to-v3.4.py é histórico (target fixo) — whitelist
        if rel == "scripts/migrate-v3.3-to-v3.4.py":
            continue
        text = py.read_text(encoding="utf-8")
        m = SCRIPT_CURRENT_VERSION_RE.search(text)
        if m and m.group(1) != canonical:
            violations.append(
                f"{rel}: CURRENT_SKILL_VERSION={m.group(1)} ≠ {canonical}"
            )
        m2 = SCRIPT_SUPPORTED_LAST_RE.search(text)
        if m2:
            versions = SEMVER_RE.findall(m2.group("body"))
            if versions and versions[-1] != canonical:
                violations.append(
                    f"{rel}: SUPPORTED_VERSIONS última entry "
                    f"{versions[-1]} ≠ {canonical}"
                )
    return violations


def test_scripts_skill_version_sync():
    """Scripts auxiliares (migrate-workspace.py etc) devem refletir SKILL_VERSION.

    Regra v3.7.2: caça drift em CURRENT_SKILL_VERSION e SUPPORTED_VERSIONS
    tuple por scripts/. Cobre futuros scripts que copiarem padrão sem
    estarem em VERSION_MUST_MATCH.
    """
    canonical = _canonical_version()
    violations = _scripts_version_violations(canonical)
    assert not violations, (
        "Scripts version drift:\n  " + "\n  ".join(violations)
    )


def test_markdown_cross_refs_resolve_in_references():
    """Links markdown relativos em references/ devem resolver."""
    violations = []
    root = REPO_ROOT / "references"
    if not root.exists():
        pytest.skip("references/ não existe")
    for md in root.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        for label, target in MD_LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            if "{{" in target:
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            # Resolução relativa ao MD; fallback REPO_ROOT
            resolved = (md.parent / path_part).resolve()
            if not resolved.exists():
                alt = (REPO_ROOT / path_part.lstrip("/")).resolve()
                if alt.exists():
                    resolved = alt
            if not resolved.exists():
                violations.append(
                    f"{md.relative_to(REPO_ROOT).as_posix()}: broken link → {target}"
                )
    assert not violations, \
        "Broken cross-refs em references/:\n  " + "\n  ".join(violations)


def test_wave_execution_protocol_has_forensic_substeps():
    """Pipeline canonical doc must reflect step 8 expansion."""
    path = REPO_ROOT / "references" / "wave-execution-protocol.md"
    text = path.read_text(encoding="utf-8")
    assert "**8a Forensic+**" in text
    assert "**8b Audit existente**" in text
    assert "**8c Forensic git log**" in text
    assert "**8d Decision**" in text
    assert "forensic-plus-protocol.md" in text


def test_l2_stage_04_mentions_max_forensic_retries():
    """L2 stage 04 template must reference the cap value (sourced from forensic-plus.py)."""
    l2_path = (
        REPO_ROOT
        / "templates"
        / "workspace"
        / "stages"
        / "04_implementation_waves"
        / "CONTEXT.md.tpl"
    )
    text = l2_path.read_text(encoding="utf-8")
    # The L2 template must mention the constant by name AND value to allow drift detection.
    assert "MAX_FORENSIC_RETRIES" in text
    assert "= 2" in text  # value embedded so reading the prompt is self-explanatory
