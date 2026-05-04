# E2E Coverage Protocol — Canonical (v3.10.0)

> **Versão:** v3.10.0
> **Skill:** `xp-icm-workflow`
> **Estágios consumidores:** `03_wave_planner` (auto-flag), `04_implementation_waves` (forensic+ Check 8 + L4 wave gate), `05_verification` (audit suite freshness)
> **Propósito:** documento canônico do reforço E2E v3.10.0. Define detecção de tasks user-facing, flag `requires_e2e_update` no schema 4-block, Check 8 forensic+ (user-journey coverage), L4 wave gate universal tier dev/prod, audit Stage 05 e2e suite freshness.

## Resumo (1 parágrafo)

ICM v3.9.0 garante L1+L2+L3+L4 layers de QA per task, mas E2E coverage ficava profile-conditional (só frontend/fullstack tier dev/prod no L4 wave gate). v3.10.0 reforça E2E em 4 frentes: (1) wave-planner detecta user-facing paths e auto-emite `requires_e2e_update: true` na task; (2) forensic+ Check 8 valida que task com flag tem ≥1 file em `e2e/`/`cypress/`/`playwright/`/`tests/e2e/` no diff; (3) L4 wave gate roda E2E suite **universal** em tier dev/prod (independe profile); (4) Stage 05 audita e2e suite existe + última run < 7 dias. Cobertura de **processo** (cross-module, cross-feature) deixa de ser delegado a CI projeto e passa a ser gate ICM.

## Por que reforço

ICM v3.9.0 gaps documentados:

| Gap | Risco |
|-----|-------|
| Tracer-first (stage 04 step 4.1) cobre task isolada, não regressão de feature antiga | Wave N quebra silenciosamente fluxo de wave 1 |
| L4 wave gate e2e só `frontend/fullstack` tier dev/prod | Backend tier dev sem e2e ICM-impose |
| Stage 05 confia em CI projeto rodar e2e — sem audit ICM | Suite e2e quebrada/stale passa despercebida |
| Tasks user-facing podem mergiar sem teste de processo | Coverage falsa |

v3.10.0 fecha gaps via 4 mudanças estruturais sem mudar layer model L1-L4.

## User-facing path detection

Wave-planner identifica tasks que tocam paths user-facing via lookup em `_config/profile-effective.yaml:user_facing_paths` (config'd per profile, defaults sensatos abaixo).

### Defaults per profile

| Profile | user_facing_paths default |
|---------|--------------------------|
| `app_web_backend` | `["routes/", "controllers/", "handlers/", "endpoints/", "api/", "graphql/"]` |
| `app_web_frontend` | `["pages/", "views/", "app/", "components/pages/", "src/routes/"]` |
| `fullstack` | union de backend + frontend |
| `cli_tool` | `["cmd/", "cli/", "commands/"]` |
| `agent_ia` | `["prompts/", "agents/", "tools/"]` |
| `framework_library` | `["api/", "exports/"]` (public surface) |
| `dashboard` | `["pages/", "views/", "dashboards/"]` |
| `data_analysis` | (vazio — typically notebook-based, e2e não-aplicável) |
| `ml_project` | `["pipelines/", "inference/"]` |
| `technical_article` | (vazio — doc-only) |
| `experiment` | (vazio — POC, e2e opt-in) |

### Wave-planner emit logic

Para cada task `t` no plan.md:
```
if any(declared_path matches user_facing_paths)
   for declared_path in t.files_touched:
   t.metadata['requires_e2e_update'] = True
   wave-plan.md inclui annotation
```

Override manual via plan.md task: `**E2E:** skip (rationale)` desabilita check (audit stage 05 exige rationale).

## 4-block schema extension

Tasks emitidas por wave-planner com flag ganham metadata field opcional:

```markdown
## Task <slug>: <título>

### O QUE / COMO / NÃO QUERO / VALIDAÇÃO
<vide 4-block-contract-template.md>

### Files touched
- src/routes/checkout.ts
- tests/checkout.test.ts

### Requires E2E update
- true   <!-- wave-planner emite quando files_touched matches user_facing_paths -->

### E2E paths expected (opcional)
- e2e/checkout-flow.spec.ts
- cypress/integration/checkout.cy.ts
```

Subagente lendo task com flag DEVE adicionar/atualizar ≥1 file em e2e directory (ver pattern detection abaixo).

## Forensic+ Check 8 — user-journey coverage

Adicionado a `references/forensic-plus-protocol.md` § 7 checks.

Trigger: task tem `Requires E2E update: true` no metadata (OR `**E2E:** skip` ausente).

Detection:
```python
e2e_dirs = ["e2e/", "cypress/", "playwright/", "tests/e2e/", "tests/integration/", "test/e2e/"]
e2e_files_in_diff = [f for f in diff if any(d in f for d in e2e_dirs)]
if requires_e2e_update and not e2e_files_in_diff:
    violation
```

Severity:

| Tier | Severity |
|------|----------|
| experimental | SOFT |
| tool | SOFT |
| development | HARD |
| production | HARD |

Skip cases:
- Task tem `**E2E:** skip` declarado (skip silently — rationale audit em Stage 05).
- Task `Conventions extras: doc-only` ou `config-only`.
- Task `type: HITL`.

Brief de re-spawn (HARD violation):
```
Task declarou `Requires E2E update: true` mas diff não toca e2e/cypress/playwright.
Adicione ≥1 test cobrindo fluxo end-to-end do path user-facing modificado.
Caminhos esperados: e2e/<feature>.spec.ts, cypress/integration/<feature>.cy.ts.
Se mudança não justifica e2e (refactor interno sem mudança de behavior),
adicione `**E2E:** skip - refactor interno, behavior preservado` ao 4-block.
```

## L4 wave gate — universal tier dev/prod

Stage 04 step 11 (L4 wave gate, antiga wave gate CI global) ganha sub-gate:

```
11a. CI global green (sempre — todos tiers).
11b. E2E suite green (tier dev/prod, todos profiles com user_facing_paths não-vazio).
11c. Cross-task coherence check (production AND ≥2 tasks shared file/API).
```

E2E command lookup em `_config/profile-effective.yaml:e2e_command` (defaults: `npm run test:e2e` / `pnpm test:e2e` / `pytest tests/e2e/` / etc).

Falha 11b → `BLOCKED_ERROR error_type: e2e_suite_failed` → diagnose protocol → rollback se inconclusive → gate humano A/B/C (mesma máquina de step 10 CI global hoje).

Skip 11b quando:
- Profile com `user_facing_paths: []` (data_analysis, technical_article, experiment).
- `e2e_command` ausente em profile-effective + tier exp/tool (warning, não BLOCKED).

## Stage 05 — audit e2e freshness

Sub-step novo `4.7 Audit E2E suite`:

1. Localiza e2e suite via `_config/profile-effective.yaml:e2e_suite_root` (default `e2e/` ou `cypress/` ou `tests/e2e/`).
2. Verifica suite existe e tem ≥1 spec file.
3. Verifica última modificação dos specs em git: `git log -1 --format=%ct -- <e2e_suite_root>`. Stale = > 7 dias E wave-summary mostra ≥1 task user-facing entregue na wave atual.
4. Audita CI report (passo 4) extraiu resultado e2e — verde OR amarelo (CONDITIONAL) aceito; vermelho = FAIL.

Falha:
- `e2e_suite_required: true` (tier dev/prod com user_facing_paths não-vazio) AND suite ausente → FAIL → `BLOCKED_ERROR error_type: e2e_suite_missing`.
- Suite stale + tasks user-facing entregues → FAIL → `BLOCKED_ERROR error_type: e2e_suite_stale`.
- Tasks com `**E2E:** skip` mas sem rationale → FAIL → `BLOCKED_ERROR error_type: e2e_skip_unjustified`.

## Recovery wizard — E2E_SUITE_STALE

Tipo novo em `references/recovery-wizard.md`:

| Detector | Trigger | Action |
|----------|---------|--------|
| `E2E_SUITE_STALE` | `_config/profile-effective.yaml:e2e_suite_required: true` AND `git log -1 --format=%ct -- <e2e_suite_root>` > 7 dias AND L1 history mostra ≥1 wave user-facing recente | Warning + sugere re-rodar suite OR adicionar task `update-e2e-coverage` em wave nova |

Auto-fix: nenhum (humano decide). Apenas alerta.

## profile-effective.yaml — schema additions

```yaml
# Existente (v3.9.0):
preview_loop:
  preview_loop_enabled: true
  ...

# Novo (v3.10.0):
e2e:
  e2e_suite_required: true | false   # default depende profile×tier
  e2e_suite_root: "e2e/" | "cypress/" | "tests/e2e/" | null
  e2e_command: "npm run test:e2e" | "pytest tests/e2e/" | null
  e2e_freshness_days: 7   # stale threshold
  user_facing_paths:
    - "routes/"
    - "controllers/"
    # ...
```

`profile-merge.py` injeta defaults sensatos per profile (vide tabela §User-facing path detection).

## AGENT-BRIEF — E2E section

Quando task tem `Requires E2E update: true`, brief render em `agent-brief-render.py` injeta seção:

```markdown
**E2E expected paths:**
- e2e/<feature-slug>.spec.ts
- cypress/integration/<feature-slug>.cy.ts

**E2E pattern guidance:**
- Tracer-first: 1 test cobrindo golden path end-to-end (user → app → DB → response).
- Anti-mock policy: e2e usa app real (sem msw/jest.mock). Boundary mocks aceitos só pra serviços externos pagos (Stripe, SendGrid).
- Coverage: ≥1 happy path + ≥1 edge case (error state, validation fail, auth fail).
```

## Stop point novo — `e2e_skip_request`

Adicionado a `references/stop-points-canonical.md`:

| ID | Trigger | Calibração tier | Menu |
|----|---------|-----------------|------|
| `e2e_skip_request` | Subagente argumenta task user-facing não precisa e2e (refactor cosmético, etc) | exp/tool: warning; dev/prod: hard | A: skip aceito (registra rationale em plan.md) / B: força e2e mesmo assim / C: split task (refactor + feature em waves separadas) |

## Edge cases

| EC | Scenario | Behavior |
|----|----------|----------|
| EC1 | Profile `user_facing_paths: []` (data_analysis) — task NÃO recebe flag | Check 8 skip; L4 e2e gate skip; Stage 05 audit skip |
| EC2 | Task user-facing + tier experimental — Check 8 SOFT, L4 skip | Warning em wave-summary; merge prossegue |
| EC3 | Task user-facing + Conventions extras: doc-only | Skip silently (doc não justifica e2e) |
| EC4 | E2E suite quebrada por flaky test (não relacionado à wave) | Falha L4 → diagnose-protocol identifica flaky → gate humano A/B/C |
| EC5 | Suite e2e roda > 10min (CI gate slow) | profile-effective `e2e_timeout_minutes: 15` permite override |
| EC6 | Multi-language repo (frontend TS + backend Go) | `user_facing_paths` cobre ambos prefixos; e2e_command pode ser shell script multi-step |
| EC7 | Wave 1 task 1 (scaffold) sem feature user-facing ainda | wave-planner não emite flag; primeiro tracer global vira task explícita "setup-e2e-suite" no plan |
| EC8 | Task com `**E2E:** skip` SEM rationale após `-` | Stage 05 audit `e2e_skip_unjustified` FAIL |

## Cross-references

- Forensic+ canonical: `references/forensic-plus-protocol.md` (Check 8 §)
- 4-block schema: `references/4-block-contract-template.md` (Requires E2E update field)
- Wave-planner algoritmo: `references/wave-planner-algorithm.md` (auto-flag detection)
- Stop points: `references/stop-points-canonical.md` (`e2e_skip_request`)
- Stage 04 runtime: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`
- Stage 05 runtime: `templates/workspace/stages/05_verification/CONTEXT.md.tpl`
- Recovery wizard: `references/recovery-wizard.md` (`E2E_SUITE_STALE`)
- State machine: `references/state-machine-schema.md` (error_types `e2e_suite_failed`, `e2e_suite_missing`, `e2e_suite_stale`, `e2e_skip_unjustified`)
- Mocking guidelines: `references/mocking-guidelines.md` (anti-mock policy em e2e — boundary mocks only)
