"""Testes unitarios para wave-planner-script.py.

Cobertura:
  - Parse de plan.md (schema canonico)
  - Construcao do DAG (deps explicitas + file conflicts)
  - Topological sort em waves
  - Cap por tier/profile + sub-waves
  - Detecccao de ciclo
  - Slugs duplicados
  - Marcacao de ambiguidades
  - Geracao de wave-plan.md (frontmatter YAML + tabela)
  - Property-based via Hypothesis (invariantes do DAG)
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from hypothesis import HealthCheck, given, settings, strategies as st

# ----------------------------------------------------------------------------
# Boot do script como modulo (hifen no nome impede import direto)
# ----------------------------------------------------------------------------
SKILL_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = SKILL_ROOT / "scripts" / "wave-planner-script.py"
FIXTURES = SKILL_ROOT / "tests" / "fixtures"

_spec = importlib.util.spec_from_file_location("wave_planner_script", SCRIPT_PATH)
wave_planner_script = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["wave_planner_script"] = wave_planner_script
_spec.loader.exec_module(wave_planner_script)  # type: ignore[union-attr]

WavePlannerError = wave_planner_script.WavePlannerError
parse_plan = wave_planner_script.parse_plan
build_graph = wave_planner_script.build_graph
detect_cycle = wave_planner_script.detect_cycle
topological_waves = wave_planner_script.topological_waves
subdivide_waves = wave_planner_script.subdivide_waves
plan_waves = wave_planner_script.plan_waves
resolve_cap = wave_planner_script.resolve_cap
render_wave_plan = wave_planner_script.render_wave_plan
detect_ambiguities = wave_planner_script.detect_ambiguities
Task = wave_planner_script.Task


# ----------------------------------------------------------------------------
# 1. Parse plan.md
# ----------------------------------------------------------------------------

def test_parse_canonical_returns_8_tasks():
    tasks = parse_plan(FIXTURES / "plan_canonical_8tasks.md")
    assert len(tasks) == 8
    assert [t.slug for t in tasks] == [
        "auth-middleware", "user-model", "logger-setup",
        "auth-routes", "user-routes", "audit-log",
        "auth-routes-v2", "dashboard",
    ]


def test_parse_extracts_files_touched():
    tasks = parse_plan(FIXTURES / "plan_canonical_8tasks.md")
    by_slug = {t.slug: t for t in tasks}
    assert by_slug["auth-middleware"].files_touched == [
        "src/auth/middleware.ts",
        "tests/auth/middleware.test.ts",
    ]
    assert by_slug["logger-setup"].files_touched == ["src/utils/logger.ts"]


def test_parse_extracts_depends_on():
    tasks = parse_plan(FIXTURES / "plan_canonical_8tasks.md")
    by_slug = {t.slug: t for t in tasks}
    assert by_slug["auth-routes"].depends_on == ["auth-middleware", "user-model"]
    assert by_slug["dashboard"].depends_on == ["auth-routes", "audit-log"]
    # "none" and empty blocks should be empty lists
    assert by_slug["auth-middleware"].depends_on == []
    assert by_slug["user-model"].depends_on == []
    assert by_slug["logger-setup"].depends_on == []


def test_parse_filters_none_as_empty(tmp_path):
    """Dependency value 'none' should be treated as empty (no deps)."""
    plan = tmp_path / "plan.md"
    plan.write_text(
        "## Task t1:\n\n### Depends on\n- none\n\n### Files touched\n- src/a.py\n",
        encoding="utf-8",
    )
    tasks = parse_plan(plan)
    assert len(tasks) == 1
    assert tasks[0].depends_on == []


def test_parse_backward_compat_nenhum(tmp_path):
    """Legacy Portuguese 'nenhum' should still work as empty deps."""
    plan = tmp_path / "plan.md"
    plan.write_text(
        "## Task t1:\n\n### Depends on\n- nenhum\n\n### Files touched\n- src/a.py\n",
        encoding="utf-8",
    )
    tasks = parse_plan(plan)
    assert len(tasks) == 1
    assert tasks[0].depends_on == []


def test_parse_strips_parenthetical_from_dep(tmp_path):
    """Dependency with parenthetical note should have note stripped."""
    plan = tmp_path / "plan.md"
    plan.write_text(
        "## Task t1:\n\n### Depends on\n- config-module (needs api_key for integration)\n\n### Files touched\n- src/a.py\n",
        encoding="utf-8",
    )
    tasks = parse_plan(plan)
    assert len(tasks) == 1
    assert tasks[0].depends_on == ["config-module"]


def test_parse_duplicate_slugs_raises(tmp_path):
    bad = tmp_path / "plan.md"
    bad.write_text(
        "## Task foo: Foo\n\n### Files touched\n- a.ts\n\n### Depends on\n\n"
        "## Task foo: Foo II\n\n### Files touched\n- b.ts\n\n### Depends on\n",
        encoding="utf-8",
    )
    with pytest.raises(WavePlannerError, match="duplicate slug"):
        parse_plan(bad)


def test_parse_invalid_slug_raises(tmp_path):
    bad = tmp_path / "plan.md"
    # Slug com maiuscula nao e kebab-case valido
    bad.write_text(
        "## Task FooBar: Foo\n\n### Files touched\n- a.ts\n\n### Depends on\n",
        encoding="utf-8",
    )
    with pytest.raises(WavePlannerError):
        # Aceita: ou parser nao acha task (lista vazia => erro upstream),
        # ou parser rejeita explicitamente. Aqui exigimos rejeicao explicita
        # quando uma sequencia "## Task X:" aparece com slug invalido.
        parse_plan(bad)


def test_parse_empty_plan_raises(tmp_path):
    empty = tmp_path / "plan.md"
    empty.write_text("# Sem tasks aqui\n\nNada.", encoding="utf-8")
    with pytest.raises(WavePlannerError):
        parse_plan(empty)


def test_parse_rejects_h4_task_header(tmp_path):
    """LLM gera plan.md com `#### Task` (h4) ao invés de `## Task` (h2).
    Sem guard, parser retorna 'no tasks found' longe da causa.
    """
    bad = tmp_path / "plan.md"
    bad.write_text(
        "#### Task foo: Foo\n\n##### WHAT\n- x\n\n##### Files touched\n- a.ts\n",
        encoding="utf-8",
    )
    with pytest.raises(WavePlannerError, match="heading drift"):
        parse_plan(bad)


def test_parse_rejects_h5_subsection(tmp_path):
    """Task header h2 OK but subsections at h5 — also drift."""
    bad = tmp_path / "plan.md"
    bad.write_text(
        "## Task foo: Foo\n\n##### WHAT\n- x\n\n##### Files touched\n- a.ts\n",
        encoding="utf-8",
    )
    with pytest.raises(WavePlannerError, match="heading drift"):
        parse_plan(bad)


def test_parse_drift_message_actionable(tmp_path):
    """Error message must point to canonical schema + mechanical fix."""
    bad = tmp_path / "plan.md"
    bad.write_text("#### Task foo: Foo\n\n##### WHAT\n- x\n", encoding="utf-8")
    with pytest.raises(WavePlannerError) as excinfo:
        parse_plan(bad)
    msg = str(excinfo.value)
    assert "4-block-contract-template" in msg
    assert "## Task" in msg


# ----------------------------------------------------------------------------
# 2. resolve_cap (tier + profile override Q17)
# ----------------------------------------------------------------------------

def test_resolve_cap_experimental():
    assert resolve_cap(tier="experimental", profile="app_web_backend") == 2


def test_resolve_cap_tool():
    assert resolve_cap(tier="tool", profile="app_web_backend") == 3


def test_resolve_cap_development():
    assert resolve_cap(tier="development", profile="app_web_backend") == 5


def test_resolve_cap_production():
    assert resolve_cap(tier="production", profile="app_web_backend") == 5


def test_resolve_cap_framework_library_overrides_to_3():
    for tier in ("experimental", "tool", "development", "production"):
        # framework_library cap=3 mas nao excede o cap do tier (experimental=2)
        expected = min(3, {"experimental": 2, "tool": 3, "development": 5, "production": 5}[tier])
        assert resolve_cap(tier=tier, profile="framework_library") == expected


def test_resolve_cap_ml_project_overrides_to_3():
    assert resolve_cap(tier="development", profile="ml_project") == 3
    assert resolve_cap(tier="production", profile="ml_project") == 3


def test_resolve_cap_technical_article_is_5():
    assert resolve_cap(tier="development", profile="technical_article") == 5


def test_resolve_cap_invalid_tier_raises():
    with pytest.raises(WavePlannerError):
        resolve_cap(tier="bogus", profile="app_web_backend")


def test_resolve_cap_invalid_profile_raises():
    with pytest.raises(WavePlannerError):
        resolve_cap(tier="development", profile="bogus")


# ----------------------------------------------------------------------------
# 3. build_graph (deps + file conflicts)
# ----------------------------------------------------------------------------

def test_build_graph_explicit_deps():
    tasks = [
        Task(slug="a", files_touched=["x.ts"], depends_on=[]),
        Task(slug="b", files_touched=["y.ts"], depends_on=["a"]),
    ]
    edges = build_graph(tasks)
    assert ("a", "b") in edges


def test_build_graph_file_conflict_serializes_by_order():
    # Mesmo arquivo => aresta na ordem do plan
    tasks = [
        Task(slug="first", files_touched=["src/shared.ts"], depends_on=[]),
        Task(slug="second", files_touched=["src/shared.ts"], depends_on=[]),
    ]
    edges = build_graph(tasks)
    assert ("first", "second") in edges
    assert ("second", "first") not in edges


def test_build_graph_no_conflict_no_edge():
    tasks = [
        Task(slug="a", files_touched=["src/a.ts"], depends_on=[]),
        Task(slug="b", files_touched=["src/b.ts"], depends_on=[]),
    ]
    edges = build_graph(tasks)
    assert edges == set()


def test_build_graph_unknown_dep_raises():
    tasks = [
        Task(slug="a", files_touched=["x.ts"], depends_on=["does-not-exist"]),
    ]
    with pytest.raises(WavePlannerError, match="unknown"):
        build_graph(tasks)


# ----------------------------------------------------------------------------
# 4. detect_cycle
# ----------------------------------------------------------------------------

def test_detect_cycle_in_simple_two_node_loop():
    edges = {("a", "b"), ("b", "a")}
    nodes = ["a", "b"]
    with pytest.raises(WavePlannerError, match="cycle"):
        detect_cycle(nodes, edges)


def test_detect_cycle_in_three_node_loop():
    edges = {("a", "b"), ("b", "c"), ("c", "a")}
    nodes = ["a", "b", "c"]
    with pytest.raises(WavePlannerError, match="cycle"):
        detect_cycle(nodes, edges)


def test_detect_cycle_acyclic_passes():
    edges = {("a", "b"), ("b", "c"), ("a", "c")}
    nodes = ["a", "b", "c"]
    detect_cycle(nodes, edges)  # nao levanta


def test_cycle_in_plan_file_aborts():
    with pytest.raises(WavePlannerError, match="cycle"):
        plan_waves(
            plan_path=FIXTURES / "plan_with_cycle.md",
            tier="development",
            profile="app_web_backend",
        )


# ----------------------------------------------------------------------------
# 5. topological_waves + subdivide_waves
# ----------------------------------------------------------------------------

def test_topological_waves_no_deps_one_wave():
    tasks = [
        Task(slug="a", files_touched=["a.ts"], depends_on=[]),
        Task(slug="b", files_touched=["b.ts"], depends_on=[]),
    ]
    waves = topological_waves(tasks, edges=set())
    assert len(waves) == 1
    assert set(waves[0]) == {"a", "b"}


def test_topological_waves_chain():
    tasks = [
        Task(slug="a", files_touched=["a.ts"], depends_on=[]),
        Task(slug="b", files_touched=["b.ts"], depends_on=["a"]),
        Task(slug="c", files_touched=["c.ts"], depends_on=["b"]),
    ]
    edges = {("a", "b"), ("b", "c")}
    waves = topological_waves(tasks, edges=edges)
    assert waves == [["a"], ["b"], ["c"]]


def test_subdivide_respects_cap():
    waves = [["a", "b", "c", "d", "e", "f", "g"]]
    sub = subdivide_waves(waves, cap=3)
    assert sub == [
        [["a", "b", "c"], ["d", "e", "f"], ["g"]],
    ]


def test_subdivide_no_split_when_under_cap():
    waves = [["a", "b"]]
    sub = subdivide_waves(waves, cap=5)
    assert sub == [[["a", "b"]]]


# ----------------------------------------------------------------------------
# 6. plan_waves end-to-end com fixture canonica
# ----------------------------------------------------------------------------

def test_plan_waves_canonical_topology():
    result = plan_waves(
        plan_path=FIXTURES / "plan_canonical_8tasks.md",
        tier="development",
        profile="app_web_backend",
    )
    assert result["total_tasks"] == 8
    assert result["cap_subagents_per_wave"] == 5

    # Wave 1: tasks sem deps + sem file conflict que as ponha mais tarde.
    # auth-routes-v2 conflita com auth-routes => so vai depois de auth-routes
    # que esta na wave 2 (depende de auth-middleware + user-model).
    waves = result["waves"]  # lista de listas-de-listas: waves[i] = sub_waves
    flat_wave_1 = [t for sub in waves[0] for t in sub]
    assert "auth-middleware" in flat_wave_1
    assert "user-model" in flat_wave_1
    assert "logger-setup" in flat_wave_1
    # auth-routes-v2 nunca pode estar na wave 1 (file conflict com auth-routes)
    assert "auth-routes-v2" not in flat_wave_1


def test_plan_waves_canonical_dashboard_last():
    result = plan_waves(
        plan_path=FIXTURES / "plan_canonical_8tasks.md",
        tier="development",
        profile="app_web_backend",
    )
    waves = result["waves"]
    flat_last_wave = [t for sub in waves[-1] for t in sub]
    assert "dashboard" in flat_last_wave


def test_plan_waves_subdivides_when_cap_exceeded(tmp_path):
    # 7 tasks sem deps + cap=3 => sub-waves 3+3+1
    lines = []
    for i in range(7):
        lines.append(f"## Task task-{i}: Task {i}\n\n### Files touched\n- src/{i}.ts\n\n### Depends on\n\n")
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("".join(lines), encoding="utf-8")

    result = plan_waves(
        plan_path=plan_path,
        tier="tool",  # cap=3
        profile="cli_tool",
    )
    assert result["total_tasks"] == 7
    assert result["cap_subagents_per_wave"] == 3
    # Uma unica wave logica, mas tres sub-waves
    assert len(result["waves"]) == 1
    assert len(result["waves"][0]) == 3
    assert len(result["waves"][0][0]) == 3
    assert len(result["waves"][0][1]) == 3
    assert len(result["waves"][0][2]) == 1
    assert result["total_sub_waves"] == 3


# ----------------------------------------------------------------------------
# 7. detect_ambiguities
# ----------------------------------------------------------------------------

def test_ambiguity_detected_when_same_dir_different_files():
    tasks = [
        Task(slug="a", files_touched=["src/payments/charge.ts"], depends_on=[]),
        Task(slug="b", files_touched=["src/payments/refund.ts"], depends_on=[]),
    ]
    ambiguities = detect_ambiguities(tasks)
    assert len(ambiguities) >= 1
    # Mensagem deve referenciar pelo menos uma das tasks
    text = "\n".join(ambiguities)
    assert "a" in text and "b" in text


def test_no_ambiguity_when_no_dir_overlap():
    tasks = [
        Task(slug="a", files_touched=["src/a/x.ts"], depends_on=[]),
        Task(slug="b", files_touched=["src/b/y.ts"], depends_on=[]),
    ]
    assert detect_ambiguities(tasks) == []


def test_no_ambiguity_when_files_intersect_exactly():
    # Quando files_touched se sobrepoem exato, isso ja vira aresta no DAG
    # (file conflict). Nao deve ser ambiguidade.
    tasks = [
        Task(slug="a", files_touched=["src/x.ts"], depends_on=[]),
        Task(slug="b", files_touched=["src/x.ts"], depends_on=[]),
    ]
    assert detect_ambiguities(tasks) == []


def test_ambiguity_fixture():
    result = plan_waves(
        plan_path=FIXTURES / "plan_with_ambiguity.md",
        tier="development",
        profile="app_web_backend",
    )
    assert result["total_tasks"] == 2
    # Particiona normalmente (1 wave) mas registra ambiguidade
    assert len(result["ambiguities"]) >= 1


# ----------------------------------------------------------------------------
# 8. render_wave_plan (output Markdown)
# ----------------------------------------------------------------------------

def test_render_wave_plan_has_yaml_frontmatter():
    result = plan_waves(
        plan_path=FIXTURES / "plan_canonical_8tasks.md",
        tier="development",
        profile="app_web_backend",
    )
    rendered = render_wave_plan(result, plan_source="stages/02_design/output/plan.md", workspace="042-feat-auth")
    assert rendered.startswith("---\n")
    closing = rendered.index("\n---\n", 4)
    fm = yaml.safe_load(rendered[4:closing])
    assert fm["tier"] == "development"
    assert fm["profile"] == "app_web_backend"
    assert fm["cap_subagents_per_wave"] == 5
    assert fm["total_tasks"] == 8
    assert fm["llm_review"] == "PENDING"
    assert fm["llm_review_iterations"] == 0


def test_render_wave_plan_contains_task_table():
    result = plan_waves(
        plan_path=FIXTURES / "plan_canonical_8tasks.md",
        tier="development",
        profile="app_web_backend",
    )
    rendered = render_wave_plan(result, plan_source="plan.md", workspace="042-feat-auth")
    # Cabecalho de tabela em pelo menos uma wave
    assert "| Task slug |" in rendered
    # Branch usa workspace
    assert "wave-042-feat-auth" in rendered or "wave-042" in rendered
    # Todos os 8 slugs aparecem
    for slug in [
        "auth-middleware", "user-model", "logger-setup", "auth-routes",
        "user-routes", "audit-log", "auth-routes-v2", "dashboard",
    ]:
        assert slug in rendered


def test_render_wave_plan_includes_e2e_column(tmp_path):
    """v3.10.0: render_wave_plan inclui coluna E2E required? na task table."""
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(
        "## Task auth-mw: JWT middleware\n\n"
        "### Files touched\n- src/routes/auth.ts\n- tests/auth.test.ts\n\n"
        "### Depends on\n\n",
        encoding="utf-8",
    )
    result = plan_waves(plan_path=plan_path, tier="development", profile="app_web_backend")
    rendered = render_wave_plan(result, plan_source="plan.md", workspace="042-test")
    assert "E2E required?" in rendered
    # task em src/routes/ deve ser flagged yes
    assert "yes (auto)" in rendered
    # annotation block aparece
    assert "E2E coverage required" in rendered


def test_render_wave_plan_no_e2e_flag_for_data_analysis(tmp_path):
    """v3.10.0: profile data_analysis com user_facing_paths vazio → no flagged tasks."""
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(
        "## Task notebook-eda: Exploratory analysis\n\n"
        "### Files touched\n- notebooks/eda.ipynb\n- tests/eda.test.py\n\n"
        "### Depends on\n\n",
        encoding="utf-8",
    )
    result = plan_waves(plan_path=plan_path, tier="development", profile="data_analysis")
    rendered = render_wave_plan(result, plan_source="plan.md", workspace="042-test")
    # E2E column ainda aparece, mas sem yes
    assert "E2E required?" in rendered
    assert "yes (auto)" not in rendered
    # Annotation NÃO aparece (sem flagged)
    assert "E2E coverage required" not in rendered


def test_render_wave_plan_marks_subwaves_when_cap_exceeded(tmp_path):
    lines = []
    for i in range(7):
        lines.append(f"## Task task-{i}: Task {i}\n\n### Files touched\n- src/{i}.ts\n\n### Depends on\n\n")
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("".join(lines), encoding="utf-8")

    result = plan_waves(plan_path=plan_path, tier="tool", profile="cli_tool")
    rendered = render_wave_plan(result, plan_source="plan.md", workspace="099-test")
    # Sub-waves rotuladas
    assert "sub-wave 1.a" in rendered
    assert "sub-wave 1.b" in rendered
    assert "sub-wave 1.c" in rendered


# ----------------------------------------------------------------------------
# 9. CLI mode
# ----------------------------------------------------------------------------

def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_cli_canonical_writes_outputs(tmp_path):
    out_plan = tmp_path / "wave-plan.md"
    out_amb = tmp_path / "ambiguities-resolved.md"
    result = _run_cli(
        "--plan", str(FIXTURES / "plan_canonical_8tasks.md"),
        "--tier", "development",
        "--profile", "app_web_backend",
        "--workspace", "042-feat-auth",
        "--output", str(out_plan),
        "--ambiguities-output", str(out_amb),
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert out_plan.exists()
    assert out_amb.exists()
    # stdout contem contagem
    assert "total_tasks=8" in result.stdout
    assert "total_waves=" in result.stdout
    assert "total_sub_waves=" in result.stdout
    assert "ambiguities=" in result.stdout
    # wave-plan.md tem frontmatter + tabela
    body = out_plan.read_text(encoding="utf-8")
    assert body.startswith("---\n")
    assert "| Task slug |" in body


def test_cli_cycle_exits_nonzero(tmp_path):
    out_plan = tmp_path / "wave-plan.md"
    out_amb = tmp_path / "ambiguities-resolved.md"
    result = _run_cli(
        "--plan", str(FIXTURES / "plan_with_cycle.md"),
        "--tier", "development",
        "--profile", "app_web_backend",
        "--workspace", "042-feat-auth",
        "--output", str(out_plan),
        "--ambiguities-output", str(out_amb),
    )
    assert result.returncode == 1
    assert "cycle" in result.stderr.lower()


def test_cli_ambiguity_fixture_records_entries(tmp_path):
    out_plan = tmp_path / "wave-plan.md"
    out_amb = tmp_path / "ambiguities-resolved.md"
    result = _run_cli(
        "--plan", str(FIXTURES / "plan_with_ambiguity.md"),
        "--tier", "development",
        "--profile", "app_web_backend",
        "--workspace", "099-test",
        "--output", str(out_plan),
        "--ambiguities-output", str(out_amb),
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    body = out_amb.read_text(encoding="utf-8")
    assert "LLM" in body
    assert "ambiguities=" in result.stdout
    # Pelo menos 1 ambiguidade
    assert "ambiguities=0" not in result.stdout


# ----------------------------------------------------------------------------
# 10. Property-based (Hypothesis)
# ----------------------------------------------------------------------------

def _build_random_dag_tasks(num_tasks: int, edges_idx: list[tuple[int, int]]) -> list:
    """Constroi tasks com deps formando DAG (edge i->j so se i<j)."""
    tasks = []
    for i in range(num_tasks):
        deps = [f"t{a}" for (a, b) in edges_idx if b == i]
        tasks.append(Task(
            slug=f"t{i}",
            files_touched=[f"src/file_{i}.ts"],  # sem conflitos
            depends_on=deps,
        ))
    return tasks


@settings(max_examples=80, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    num_tasks=st.integers(min_value=1, max_value=12),
    edge_data=st.data(),
)
def test_property_total_tasks_preserved(num_tasks, edge_data):
    if num_tasks < 2:
        edges_idx: list[tuple[int, int]] = []
    else:
        edges_idx = edge_data.draw(st.lists(
            st.tuples(
                st.integers(min_value=0, max_value=num_tasks - 1),
                st.integers(min_value=0, max_value=num_tasks - 1),
            ).filter(lambda p: p[0] < p[1]),
            max_size=num_tasks * 2,
            unique=True,
        ))
    tasks = _build_random_dag_tasks(num_tasks, edges_idx)
    edges = build_graph(tasks)
    waves = topological_waves(tasks, edges=edges)
    cap = 5
    sub = subdivide_waves(waves, cap=cap)

    flat = [t for wave in sub for sw in wave for t in sw]
    assert len(flat) == num_tasks
    assert set(flat) == {t.slug for t in tasks}


@settings(max_examples=80, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    num_tasks=st.integers(min_value=1, max_value=12),
    edge_data=st.data(),
)
def test_property_no_dep_crosses_into_later_wave(num_tasks, edge_data):
    if num_tasks < 2:
        edges_idx: list[tuple[int, int]] = []
    else:
        edges_idx = edge_data.draw(st.lists(
            st.tuples(
                st.integers(min_value=0, max_value=num_tasks - 1),
                st.integers(min_value=0, max_value=num_tasks - 1),
            ).filter(lambda p: p[0] < p[1]),
            max_size=num_tasks * 2,
            unique=True,
        ))
    tasks = _build_random_dag_tasks(num_tasks, edges_idx)
    edges = build_graph(tasks)
    waves = topological_waves(tasks, edges=edges)

    # Mapa slug -> indice da wave
    wave_of = {}
    for idx, wave in enumerate(waves):
        for slug in wave:
            wave_of[slug] = idx

    # Para cada aresta (u, v), wave(v) > wave(u)
    for (u, v) in edges:
        assert wave_of[v] > wave_of[u], f"aresta {u}->{v} viola ordem ({wave_of[u]} -> {wave_of[v]})"


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    num_tasks=st.integers(min_value=1, max_value=15),
    cap=st.integers(min_value=1, max_value=5),
)
def test_property_no_subwave_exceeds_cap(num_tasks, cap):
    tasks = _build_random_dag_tasks(num_tasks, edges_idx=[])
    edges = build_graph(tasks)
    waves = topological_waves(tasks, edges=edges)
    sub = subdivide_waves(waves, cap=cap)

    for wave in sub:
        for sw in wave:
            assert len(sw) <= cap


# ============================================================================
# T2.6 — HITL/AFK classification (subdivide_waves com task_types)
# ============================================================================


def test_subdivide_hitl_isolated_in_own_subwave():
    """Tasks HITL viram sub-waves cap=1 mesmo com cap maior."""
    waves = [["a", "b", "c", "d"]]
    types = {"a": "AFK", "b": "HITL", "c": "AFK", "d": "HITL"}
    sub = subdivide_waves(waves, cap=5, task_types=types)
    flat = [s for sw in sub[0] for s in sw]
    # Todas tasks ainda presentes
    assert sorted(flat) == ["a", "b", "c", "d"]
    # HITL tasks ficam sozinhas em suas sub-waves
    hitl_subs = [sw for sw in sub[0] if sw == ["b"] or sw == ["d"]]
    assert len(hitl_subs) == 2


def test_subdivide_afk_grouped_under_cap():
    """AFK tasks agrupadas até cap; HITL ficam isoladas após."""
    waves = [["a", "b", "c", "d", "e"]]
    types = {"a": "AFK", "b": "AFK", "c": "AFK", "d": "HITL", "e": "AFK"}
    sub = subdivide_waves(waves, cap=2, task_types=types)
    # Esperado: [[a, b], [c, e], [d]]
    afk_subs = [sw for sw in sub[0] if "d" not in sw]
    hitl_subs = [sw for sw in sub[0] if "d" in sw]
    # AFK em sub-waves de tamanho <= 2
    for sw in afk_subs:
        assert len(sw) <= 2
    # HITL isolada em cap=1
    assert len(hitl_subs) == 1
    assert hitl_subs[0] == ["d"]


def test_subdivide_no_types_defaults_to_afk():
    """Sem task_types, comportamento idêntico ao default (todos AFK)."""
    waves = [["a", "b", "c"]]
    sub_with = subdivide_waves(waves, cap=2, task_types={})
    sub_without = subdivide_waves(waves, cap=2)
    assert sub_with == sub_without


def test_subdivide_all_hitl_each_isolated():
    """Wave inteira HITL → N sub-waves cap=1."""
    waves = [["a", "b", "c"]]
    types = {"a": "HITL", "b": "HITL", "c": "HITL"}
    sub = subdivide_waves(waves, cap=5, task_types=types)
    assert sub[0] == [["a"], ["b"], ["c"]]


def test_parse_plan_extracts_type_field(tmp_path):
    """Parser extrai `**Type:**` do bloco. Default AFK quando ausente."""
    plan = tmp_path / "plan.md"
    plan.write_text(
        "# plan\n\n"
        "## Task task-a:\n\n"
        "**Type:** HITL\n\n"
        "### Files touched\n\n"
        "- src/a.ts\n\n"
        "### Depends on\n\n"
        "- none\n\n"
        "## Task task-b:\n\n"
        "### Files touched\n\n"
        "- src/b.ts\n\n"
        "### Depends on\n\n"
        "- none\n",
        encoding="utf-8",
    )
    tasks = parse_plan(plan)
    by_slug = {t.slug: t for t in tasks}
    assert by_slug["task-a"].type == "HITL"
    assert by_slug["task-b"].type == "AFK"  # default


def test_render_wave_plan_emits_skip_cross_task_audit_for_one_task_wave(tmp_path):
    """1-task wave's section must carry `skip_cross_task_audit: true` annotation."""
    plan_md = (
        "## Task add-only:\n"
        "### Files touched\n"
        "- src/x.py\n"
        "- tests/test_x.py\n"
    )
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(plan_md, encoding="utf-8")
    result = plan_waves(plan_path=plan_path, tier="development", profile="app_web_backend")
    rendered = render_wave_plan(result, plan_source=str(plan_path), workspace="042-foo")

    assert "skip_cross_task_audit: true" in rendered

    plan_md2 = (
        "## Task add-a:\n### Files touched\n- src/a.py\n- tests/test_a.py\n\n"
        "## Task add-b:\n### Files touched\n- src/b.py\n- tests/test_b.py\n"
    )
    plan_path2 = tmp_path / "plan2.md"
    plan_path2.write_text(plan_md2, encoding="utf-8")
    result2 = plan_waves(plan_path=plan_path2, tier="development", profile="app_web_backend")
    rendered2 = render_wave_plan(result2, plan_source=str(plan_path2), workspace="042-foo")
    assert "skip_cross_task_audit" not in rendered2


def test_legacy_skip_wave_reviewer_alias_documented():
    """Forward-defensive: any consumer that emits the legacy `skip_wave_reviewer`
    string should still be parseable. v3.8.0 only writes the new name; this test
    pins the alias contract via doc inspection (the new doc must say the alias
    exists and will be removed in v3.9.0).
    """
    doc_path = SKILL_ROOT / "references" / "wave-planner-algorithm.md"
    doc = doc_path.read_text(encoding="utf-8")
    assert "skip_cross_task_audit" in doc
    assert "skip_wave_reviewer" in doc  # legacy alias mentioned
    assert "v3.9.0" in doc  # deprecation horizon
