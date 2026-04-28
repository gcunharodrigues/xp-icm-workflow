# Wave Planner Algorithm — Spec Canônico

> **Versão:** v3.0.0-beta5
> **Skill:** `xp-icm-workflow`
> **Estágio:** `03 wave_planner`
> **Path resolution:** caminhos `scripts/` neste documento referem-se a `<SKILL_DIR>/scripts/`, onde `SKILL_DIR` está definido em L0 (`CLAUDE.md`).
> **Propósito:** documento canônico do algoritmo Wave Planner. Formaliza o pipeline determinístico baseline (Sessão 2 do estágio 03, já implementado em `<SKILL_DIR>/scripts/wave-planner-script.py`) **+** o LLM review subagent (R2.4) que valida o DAG antes do gate humano.

> **Decisões de origem:** Q7 (DAG por footprint + branches isoladas), Q17 (cap por tier/profile), Q18 (LLM review SEMPRE), E3 (sub-waves), F2 (skip wave-reviewer 1-task), R2.4 (LLM review subagent via Task tool).

> **Status:** o pipeline determinístico está validado por `tests/unit/test_wave_planner_dag.py` (33 tests verde). LLM review subagent é wave 4 da reescrita; tests com mocks em `tests/mocks/llm_review_responses/`.

---

## 1. Inputs e outputs

| Camada | Entrada | Saída |
|---|---|---|
| Determinístico | `stages/02_design/output/plan.md` + `tier` + `profile` + `workspace_id` | `stages/03_wave_planner/output/wave-plan.md` (draft) + `ambiguities-resolved.md` |
| LLM review | wave-plan.md draft + plan.md + ambiguidades | wave-plan.md final + `llm_review_findings.md` |

CLI determinístico:

```bash
python <SKILL_DIR>/scripts/wave-planner-script.py \
  --plan stages/02_design/output/plan.md \
  --tier development \
  --profile app_web_backend \
  --workspace 042-feat-auth \
  --output stages/03_wave_planner/output/wave-plan.md
```

Stdout: `total_tasks=N total_waves=M total_sub_waves=K ambiguities=A`. Exit 0 ok; exit 1 erro (ciclo, schema, slug duplicado).

---

## 2. Schema task no plan.md

Cada task é parseada do `plan.md` conforme `references/4-block-contract-template.md`. Extrai:

| Campo | Origem no plan.md | Uso no Wave Planner |
|---|---|---|
| `slug` | header `## Task <slug>:` (kebab-case) | nó do DAG |
| `files_touched` | seção `### Files touched` | aresta por conflito; validação de test file obrigatório |
| `depends_on` | seção `### Depends on` (opcional) | aresta explícita |
| `peer_review` | `### Requires_peer_review` | metadata (não afeta DAG) |
| `adrs` | `### ADRs aplicáveis` | metadata |
| `conventions_extras` | `### Conventions extras` | metadata; `doc-only`/`config-only` isenta da regra de test file |

**Regras de parsing:**
- Slug duplicado → erro.
- Slug fora de kebab-case → erro.
- Dep apontando para slug inexistente → erro.
- **Regra de test file obrigatório:** toda task cujo `files_touched` contém arquivos em padrões de código (`src/`, `app/`, `lib/`, `pkg/`, extensões `.py`, `.ts`, `.js`, `.go`, `.rb`, `.rs`, `.java`, `.kt`, `.cs`) **deve** declarar ≥1 arquivo de teste correspondente (padrões reconhecidos: `tests/`, `test_*.py`, `*_test.py`, `*.test.ts`, `*.spec.ts`, `*.test.js`, `*.spec.js`, `spec/`, `__tests__/`). Violação → `BLOCKED_ERROR` com mensagem `test file missing for task <slug>`. Exceção: `Conventions extras` contém `doc-only` ou `config-only` → isenção automática.

---

## 3. Construção do DAG

Plan §4.3:

- **Nó:** uma task.
- **Aresta dirigida `(t1, t2)`** se:
  - `t2.depends_on` cita `t1` (dep explícita), **OU**
  - `files_touched(t1) ∩ files_touched(t2) ≠ ∅` E t1 aparece antes de t2 no `plan.md` (conflito serializa por ordem de aparição).

Conflito de footprint força tasks para waves diferentes — não viola ordem do humano.

---

## 4. Detecção de ciclos

DFS 3-cores (white/gray/black). Ao tocar nó GRAY na pilha → ciclo.

Mensagem: `cycle detected: t1 -> t2 -> t3 -> t1`. Exit 1.

---

## 5. Topological sort em waves (Kahn por níveis)

Nível N = nós com in-degree zero no grafo restante. Após emitir wave-N, remove arestas e recalcula. Empate dentro do nível resolve por ordem de aparição no `plan.md` (determinístico).

---

## 6. Cap por tier/profile

Cap efetivo = `min(TIER_CAP[tier], PROFILE_CAP_OVERRIDE[profile])`.

| Tier | Cap base |
|---|---|
| `experimental` | 2 |
| `tool` | 3 |
| `development` | 5 |
| `production` | 5 |

Profile overrides:

| Profile | Override |
|---|---|
| `framework_library` | 3 |
| `ml_project` | 3 |
| `technical_article` | 5 |

Exemplo: `tier=production` + `profile=ml_project` → cap = `min(5, 3) = 3`.

---

## 7. Subdivisão em sub-waves (E3)

Quando `len(wave-N) > cap`, subdivide em `wave-N.a, wave-N.b, ...`, cada uma com até `cap` tasks. Sub-wave `(k+1)` só inicia depois que `(k)` está merged em `base_branch` + CI green.

Schema `wave-plan.md` ganha campo `sub_wave_id` (letras a-z; fallback `x<idx>` se >26).

Branch naming: `wave-<workspace>-N.a/<task-slug>`, `wave-<workspace>-N.b/<task-slug>`, etc.

---

## 8. Detecção de ambiguidades de footprint

Heurística: pares de tasks que tocam o **mesmo diretório** mas **não compartilham arquivo exato** (dir-overlap sem file-overlap).

Exemplo: `task-a` toca `src/auth/middleware.ts`, `task-b` toca `src/auth/`. O determinístico **não** cria aresta (sem interseção exata) **mas** registra ambiguidade em `ambiguities-resolved.md` para o LLM review confirmar separação.

Determinístico aplica regra de fallback: serializa por ordem de aparição (mesma regra de file conflict). LLM review pode confirmar/contestar.

---

## 9. LLM review subagent (R2.4)

Após gerar `wave-plan.md` draft + `ambiguities-resolved.md`, o Wave Planner spawna subagent dedicado via Task tool com prompt fixo:

```
Você é um wave-planner-reviewer. Recebe o DAG draft + plan.md + ambiguities.

Tarefa: ler tasks + grafo + ambiguidades. Verificar se há:
1. Footprints ambíguos não resolvidos pelo determinístico
2. Deps implícitas não declaradas (ex: task B precisa do schema migrado por task A
   mas não declara dep)
3. Sub-waves que poderiam re-paralelizar (cap reduzido por engano)

Output JSON estruturado:
{
  "verdict": "APPROVE" | "PROPOSE_CHANGES",
  "issues": [
    {"type": "implicit_dep", "from": "task-a", "to": "task-b", "reason": "..."},
    {"type": "ambiguous_footprint", "tasks": ["task-x", "task-y"], "suggestion": "..."}
  ],
  "proposed_dag_changes": [...]   // só se PROPOSE_CHANGES
}
```

Wave Planner aplica o JSON:

- **APPROVE** → frontmatter `llm_review: APPROVE`, segue para gate humano.
- **PROPOSE_CHANGES** → aplica diff → re-roda determinístico → loop até `APPROVE` ou cap 2 ciclos (E2). 3ª iteração diverge → escala humano com diffs (`llm_review_iterations: 2 (max reached, human decided)`).

**Skip threshold:** waves com ≤2 tasks pulam LLM review (custo > benefício). Script `wave-planner-llm-review.py` incrementa counter `llm_review_skipped_count` em L1 quando skip ocorre (flag `--workspace-context <L1-CONTEXT.md>`).

**Mockable:** pytest mocka Task tool com fixtures JSON em `tests/mocks/llm_review_responses/` — CI roda sem custo de tokens.

---

## 10. Wave-reviewer skip exception (F2)

Wave com **1 task** pula o wave-reviewer agregado da fase 04 (sem cross-task coherence check possível). CI global da `base_branch` cobre o escape.

Schema `wave-plan.md` marca `skip_wave_reviewer: true` na wave aplicável. Lead da fase 04 lê esse flag e ajusta o protocolo.

---

## 11. Schema do wave-plan.md de saída

```yaml
---
generated_at: 2026-04-25T14:32:00Z
plan_source: stages/02_design/output/plan.md
profile: app_web_backend
tier: development
workspace: 042-feat-auth
cap_subagentes_per_wave: 5
total_tasks: 4
total_waves: 2
total_sub_waves: 2
ambiguities_count: 0
llm_review: APPROVE              # APPROVE | PROPOSE_CHANGES | SKIPPED
llm_review_iterations: 1
---

# Wave Plan

## Wave 1 (sub-wave 1.a) — 2 tasks paralelas

| Task slug | Files touched | Depends on | Branch |
|---|---|---|---|
| add-user-model | src/models/user.ts, tests/models/user.test.ts | - | wave-042-feat-auth-1/add-user-model |
| add-config-schema | src/config/schema.ts, tests/config.test.ts | - | wave-042-feat-auth-1/add-config-schema |

## Wave 2 (sub-wave 2.a) — 2 tasks paralelas

| Task slug | Files touched | Depends on | Branch |
|---|---|---|---|
| add-login-endpoint | src/api/login.ts, tests/api/login.test.ts | add-user-model | wave-042-feat-auth-2/add-login-endpoint |
| add-logout-endpoint | src/api/logout.ts, tests/api/logout.test.ts | add-user-model | wave-042-feat-auth-2/add-logout-endpoint |

## Audit

- Tasks com files conflict serializadas: nenhuma
- Nenhuma ambiguidade registrada.
```

---

## 12. Mid-wave cap reduce (D'')

Lead da fase 04 pode reduzir o cap **mid-wave** se observar drift:

- 3 ciclos travados sem convergência de algum subagente;
- idle waiting prolongado (saída do Agent tool sem progresso);
- orçamento de tokens crescendo desproporcional.

Ação: encerra wave parcial com `BLOCKED_ERROR` + snapshot pra humano. Detalhamento em `references/subagent-protocol.md` (sibling).

---

## 13. Validação automatizada

`tests/unit/test_wave_planner_dag.py` (33 tests verde):

- Cycle detection (cobre auto-loop, ciclo de 2/3/N nós).
- Topo sort correto (preserva ordem do plan.md em empates).
- Sub-wave split respeita cap.
- File conflict gera aresta na ordem certa.
- Detect ambiguities cobre dir-overlap sem file-overlap.
- Property-based via Hypothesis: todas as deps preservadas, nenhum cap excedido.

Wave 4 (LLM review) adiciona:

- `tests/unit/test_wave_planner_llm_review.py`: mocks Task tool com fixtures.
- `tests/integration/test_wave_planner_e2e.py`: pipeline determinístico + LLM review mocked → wave-plan.md final.
- Snapshot tests: `wave-plan.md` esperado vs gerado em `tests/fixtures/wave-plan-expected/`.

---

## 14. Exemplo concreto: 4-task plan.md fictício

Input `plan.md` resumido:

```markdown
## Task add-user-model
### Files touched
- src/models/user.ts
- tests/models/user.test.ts

## Task add-config-schema
### Files touched
- src/config/schema.ts

## Task add-login-endpoint
### Files touched
- src/api/login.ts
### Depends on
- add-user-model

## Task add-logout-endpoint
### Files touched
- src/api/logout.ts
### Depends on
- add-user-model
```

Pipeline (`tier=development`, `profile=app_web_backend`, cap=5):

1. **Parse:** 4 tasks.
2. **DAG:** arestas `(add-user-model, add-login-endpoint)`, `(add-user-model, add-logout-endpoint)`. Nenhum file conflict.
3. **Topo:** Wave 1 = `[add-user-model, add-config-schema]`. Wave 2 = `[add-login-endpoint, add-logout-endpoint]`.
4. **Sub-waves:** ambas waves ≤ cap → `1.a` e `2.a` (sem split).
5. **Ambiguidades:** nenhuma (dirs distintos).
6. **LLM review:** subagent retorna `APPROVE` (deps explícitas batem com semântica).
7. **Output:** wave-plan.md conforme §11.

Saída de stdout: `total_tasks=4 total_waves=2 total_sub_waves=2 ambiguities=0`.
