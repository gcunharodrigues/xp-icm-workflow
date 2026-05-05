---
name: smoke-manual-checklist
purpose: Checklist de smoke tests manuais pré-release (plan §8.2)
gate: v3.0.0-beta5 → v3.0.0 promotion
required_projects: 3
---

# Smoke manual — pré-release v3.0.0-beta5

> Antes de promover `v3.0.0-beta5` para `v3.0.0`: rodar todos os 10 itens em ≥3 projetos reais distintos. Documentar resultado por projeto em `references/smoke-results-<projeto>-<YYYY-MM-DD>.md`.

## Critérios gerais (todos os itens)

- ✅ **PASS** se: comportamento conforme documentação + sem crash + sem corrupção FS/git.
- ❌ **FAIL** se: crash, escrita fora do escopo declarado, regressão de qualquer Wave anterior, perda de trabalho do humano.
- ⚠️ **WARN** se: comportamento correto mas UX confusa / mensagem ruim / passo extra inesperado. Anotar para Wave 8 (futuras melhorias).

## Os 13 itens

### 1. Greenfield real

`profile=app_web_backend tier=development project_root=<path-novo>`. Percorrer 00→07 em projeto pequeno (3-5 tasks).

**Verificar:**
- [ ] Bootstrap exit 0, 9 dirs criados, L0/L1 sem placeholders sobrando
- [ ] Cada estágio transiciona conforme L2 declara
- [ ] Pre-commit hook bloqueia tentativa de bypass
- [ ] Token spend total ≤ 60% da v2.4 mesma escala (se houver baseline)

### 2. Existing repo Aura ecosystem

Repo já com CLAUDE.md, ADRs em `docs/decisions/`, `docs/lessons.md`.

**Verificar:**
- [ ] Recon (estágio 00) detecta tipo `existing` corretamente
- [ ] ADRs vigentes aparecem no recon-report (índice apenas, sem ler corpo)
- [ ] Discovery (estágio 01) NÃO repete perguntas já respondidas em CLAUDE.md
- [ ] Lessons herdáveis citadas no recon-report

### 3. External repo

Clone read-only de skill qualquer (ex: `superpowers/skills/brainstorming`).

**Verificar:**
- [ ] Bootstrap não comita acidentalmente em master/main do upstream
- [ ] Branch atual = `workspace/NNN-<slug>`
- [ ] master/main do clone permanece com 1 commit (initial do upstream)
- [ ] Hook local instalado mas não propagado pra upstream

### 4. tier=production com 5 subagentes

Plan.md com ≥5 tasks paralelizáveis.

**Verificar:**
- [ ] Wave Planner constrói DAG correto (sem ciclo, deps respeitadas)
- [ ] 5 branches criadas em `wave-NNN-1/<task-slug>`
- [ ] Cada subagente em branch isolada `wave-NNN-1/<task-slug>`
- [ ] Sync barreira aguarda todos COMPLETE antes wave-reviewer
- [ ] Merge sequencial limpo OU conflito escalado para humano com mensagem clara
- [ ] CI gate global verde antes wave 2

### 5. Stop point real

Design (estágio 02) lista nova dependência paga (ex: SaaS Auth0 R$ 300/mês).

**Verificar:**
- [ ] Stop point `paid_service` dispara conforme calibração tier
- [ ] Menu A/B/C escrito com trade-offs + recomendação + reversibilidade
- [ ] L1 status vira `BLOCKED_STOP_POINT`, history append
- [ ] Humano responde "B", sessão retoma `IN_PROGRESS`
- [ ] history append `stop_point_resolved` com escolha

### 6. Override yaml com guard-rail

`.icm-profile.local.yaml` com `tdd_required: false` em `tier=production` (sem `confirm_unsafe`).

**Verificar:**
- [ ] Bootstrap recusa com `ProfileMergeError("override perigoso requer confirm_unsafe: true")`
- [ ] Adicionar `confirm_unsafe: true`, retry → bootstrap aceita
- [ ] L0 reflete `tdd_required: false` no profile-effective.yaml

### 7. Recovery Wizard

Forçar workspace órfão: matar sessão mid-fase 04 (kill processo durante wave-1 spawn).

**Verificar:**
- [ ] Próxima sessão pre-flight detecta inconsistência (R2.7)
- [ ] Recovery Wizard dispara automaticamente com 3 ações A/B/C
- [ ] Aplicar A (rebuild from history) → L1 reconstruído
- [ ] Sessão retoma do `stage_atual` correto sem perder trabalho

### 8. Feedback intake fase 08 — 3 saídas

Workspace COMPLETED → humano dispara fase 08 manualmente, 3 vezes (3 workspaces ou 1 com 3 iterations).

**Verificar:**
- [ ] **Saída A** (close): status → `COMPLETED`, sub_stage → `08_decided_A`, lessons append em `docs/lessons.md`
- [ ] **Saída B** (restart fase X): X ∈ {01..07} aceito (recusa 00 e 08), iteration++, outputs antigos movidos para `output-iteration-<N>/`, status → `IN_PROGRESS`, stage_atual → X
- [ ] **Saída C** (spawn novo): mensagem para humano com comando exato, sub_stage → `08_decided_C`, spawn_to set, sessão termina sem bootstrappar 043

### 9. Comparação custo $

Mesmo projeto canônico (3-5 tasks) executado em v2.4 e v3.0-beta1. Medir input + output tokens totais.

**Verificar:**
- [ ] v3 ≤ 60% de v2.4 (alvo plan §8.3)
- [ ] Ganho vem de: sumários 200tok vs invocação skill formal + sub_stage tracking + sessões enxutas
- [ ] Documentar números em `references/smoke-results-<projeto>.md`

### 10. Path absoluto (Windows / cross-drive)

Workspace em `D:\workspaces\NNN-<slug>\`, projeto em `C:\projects\X\`.

**Verificar:**
- [ ] L0 resolve `project_root: C:/projects/X/` corretamente
- [ ] Código escrito sai em `C:\projects\X\src\` (NUNCA dentro do workspace)
- [ ] Branches criadas em `C:\projects\X\` (formato `wave-NNN-N/<task-slug>`)
- [ ] Pre-commit hook valida prefixo `workspaces/NNN/` no workspace branch (não permite escrever em `src/`)

### 11. Test Infrastructure — profile-effective.yaml

`profile=app_web_backend tier=development`. Verificar geração de test_specs.

**Verificar:**
- [ ] `profile-effective.yaml` contém campo `test_specs` com sub-campos `test_types_required`, `coverage_threshold`, `http_integration`, `db_integration`
- [ ] `coverage_threshold` = 80 para tier=development (conforme tabela de defaults)
- [ ] `test_types_required` = `[unit, integration]` para profile `app_web_backend`
- [ ] Campo `test_specs` ausente em `.icm-profile.local.yaml` — não-overridável

### 12. Test Strategy no plan.md (stage 02)

Percorrer stage 02 em workspace real.

**Verificar:**
- [ ] Stage 02 produz seção `§Test Strategy` no plan.md (framework, pirâmide, threshold, path crítico)
- [ ] Toda task com arquivos em `src/` declara ≥1 arquivo de teste em `Files touched`
- [ ] Task sem arquivo de teste em `Files touched` para código funcional → Wave Planner dispara `BLOCKED_ERROR "test file missing for task <slug>"`
- [ ] Transition condition do stage 02 bloqueia se Test Strategy ausente

### 13. Test-recipe copiada no bootstrap

Bootstrap com qualquer profile (ex: `agent_ia`, `ml_project`).

**Verificar:**
- [ ] `workspace/_references/test-recipes/<profile>.md` existe após bootstrap
- [ ] Conteúdo da receita bate com `templates/_references/test-recipes/<profile>.md` da skill
- [ ] Stage 01 lista o arquivo na tabela Inputs (Input #12) como `condicional`
- [ ] Stage 05 passo 4.6 executa sample-check e reporta PASS/CONDITIONAL/FAIL

## Critérios de aceitação para promover beta1 → v3.0.0 (plan §8.3)

- ✅ Suite formal: ≥80% coverage críticos, ≥60% resto. CI verde 7 dias consecutivos.
- ✅ ≥3 projetos reais usaram v3.0.0-beta1 sem regressão grave (bug que destrói trabalho).
- ✅ Comparação $ documentada: v3 ≤ 60% v2.4 em ≥3 projetos.
- ✅ 10 itens deste checklist PASS em ≥3 projetos.
- ✅ Lessons coletadas em `docs/lessons.md` da própria skill (Wave 7 cria).

## Template de relatório por projeto

```markdown
# Smoke result — <projeto> — <YYYY-MM-DD>

| # | Item | Status | Notas |
|---|---|---|---|
| 1 | Greenfield real | ✅/❌/⚠️ | ... |
| 2 | Existing repo | ✅/❌/⚠️ | ... |
| 3 | External repo | ✅/❌/⚠️ | ... |
| 4 | 5 subagentes | ✅/❌/⚠️ | ... |
| 5 | Stop point real | ✅/❌/⚠️ | ... |
| 6 | Override guard-rail | ✅/❌/⚠️ | ... |
| 7 | Recovery Wizard | ✅/❌/⚠️ | ... |
| 8 | Feedback intake A/B/C | ✅/❌/⚠️ | ... |
| 9 | Custo $ vs v2.4 | ✅/❌/⚠️ | v3=Xtok / v2.4=Ytok = Z% |
| 10 | Path absoluto | ✅/❌/⚠️ | ... |
| 11 | test_specs no profile-effective | ✅/❌/⚠️ | ... |
| 12 | Test Strategy no plan.md | ✅/❌/⚠️ | ... |
| 13 | test-recipe copiada no bootstrap | ✅/❌/⚠️ | ... |

## Bugs descobertos
- ...

## UX warnings
- ...

## Lessons
- ...
```

---

## v3.3.0 — novos itens de smoke manual

Após bootstrap em `tier=development`, verificar:

- [ ] `<project_root>/CLAUDE.md` criado com região ICM (`<!-- ICM-START/END -->`)
- [ ] `<workspace>/_config/CONTEXT.md` (L3 ubiquitous language) presente, frontmatter `layer: L3, scope: ubiquitous_language`
- [ ] `<workspace>/_out-of-scope/README.md` presente
- [ ] `<workspace>/_references/runtime/agent-brief-template.md` presente
- [ ] `<workspace>/_references/runtime/context-format.md` presente
- [ ] `<workspace>/_references/runtime/adr-format.md` presente
- [ ] `<workspace>/_references/runtime/diagnose-protocol.md` presente
- [ ] `<workspace>/_references/runtime/triage-state-machine.md` presente
- [ ] `<workspace>/_references/runtime/out-of-scope-kb.md` presente
- [ ] `<workspace>/_references/runtime/design-it-twice.md` presente
- [ ] `<workspace>/_config/hitl-loop.template.sh` presente
- [ ] `docs/decisions/_template.md` presente

Em workspace branch:
- [ ] Editar `<project_root>/CLAUDE.md` e `git add CLAUDE.md` — pre-commit hook permite (G6 whitelist)
- [ ] Recovery wizard detecta `CLAUDE_MD_ROOT_STALE` quando L1.stage_atual diverge do bloco em CLAUDE.md root

Brownfield:
- [ ] Bootstrap em projeto com CLAUDE.md preexistente preserva conteúdo fora dos marcadores ICM byte-a-byte
- [ ] Sem marcadores: insere região ICM logo após primeiro `^# ` (título principal)

Multi-workspace:
- [ ] Bootstrap segundo workspace adiciona bloco preservando o primeiro

Saída A do último workspace:
- [ ] Região ICM substituída por mensagem "Nenhum workspace ICM ativo + rode /init"

## v3.5.0 — wave protocol checks

- [ ] L1 history grava `pre_wave_sha` em evento `wave_started` (passo 1 stage 04).
- [ ] Task report tem `qa_loops_used: <N>` + `auto_qa_passed: <bool>` no frontmatter.
- [ ] Wave-reviewer roda sem worktree (CWD = lead workspace; lê via `git show`).
- [ ] Sort buffer aplica plan order pré-merge (mesmo que Agents retornem fora de ordem).
- [ ] Conflict mid-wave: lead pausa em `BLOCKED_ERROR`, escreve `merge-conflict-<slug>.md`, gate humano A/B/C.
- [ ] CI global vermelho: diagnose-protocol primeiro, rollback com `pre_wave_sha`, gate A/B/C.
- [ ] Wave mista com 1 task HITL: tasks não-HITL completam em paralelo, status final `BLOCKED_HITL`.
- [ ] Cleanup `--force` apenas com `auto_qa_passed: true` no task report.
- [ ] `.icm-main` sync condicional (skip silencioso se ausente).
- [ ] Validator aceita `BLOCKED_HITL` em L1 status.

## v3.9.0 — layered dev↔QA loop checks

### Bootstrap
- [ ] Workspace tier=experimental: novo CONTEXT.md.tpl com L3 critic enabled (Haiku ceiling).
- [ ] Workspace tier=production: novo CONTEXT.md.tpl com L3 critic Opus.
- [ ] Bootstrap copia 3 docs novos pra `_references/runtime/` (critic-protocol, lead-resolution-protocol, mocking-guidelines).

### Pick-model
- [ ] `pick-model.py` task `complexity_score: 1` + tier=production → writer Haiku + critic Opus.
- [ ] `pick-model.py` task `complexity_score: 6` + tier=experimental → writer Haiku + critic Haiku (ceiling caps).
- [ ] `pick-model.py` task `complexity_score: 5` + tier=development → writer Opus + critic Opus.
- [ ] `agent-brief-render.py --tier production` injeta `model_recommended_writer/critic` + `complexity_score` no header.

### Lead-diagnose
- [ ] `lead-diagnose.py` round 1 fail + Jaccard < 0.7 → recommend `surgical_retry` (no trigger met).
- [ ] `lead-diagnose.py` round 2 fail + Jaccard ≥ 0.7 vs round 1 → recommend `escalate_to_lead, reason: convergence_trip`.
- [ ] `lead-diagnose.py` catastrophic signal (forensic_files_outside > 5) → recommend `escalate_to_lead, reason: catastrophic, bucket_hint: B3`.
- [ ] diagnose.md schema: trigger condition + Jaccard table + bucket recommend + surgical brief (when B1).

### Forensic+ extended
- [ ] `forensic-plus.py` Check 5 fixture (acceptance criterion sem test mapping) → HARD em production.
- [ ] `forensic-plus.py` Check 6 fixture (diff toca pattern NÃO QUERO `Mock interno de jose`) → HARD em dev/prod.
- [ ] `forensic-plus.py` Check 7 fixture (import lib proibida por ADR `## Forbidden imports`) → HARD em dev/prod.
- [ ] ADR sem section `## Forbidden imports` → check 7 silently skipped (backward compat).

### Lead-resolution tier
- [ ] B1 REWRITE_SPEC: lead reescreve task spec, 1 final spawn writer, output passa L2+L3 igual.
- [ ] B3 DIRECT_IMPL: lead escreve em branch `wave-<NNN>-<N>/<slug>-lead-resolved`, output passa L2+L3 igual (não auto-aprovado).
- [ ] B4 VOID_TASK: bloco `### VOIDED` em plan.md com rationale concreto, wave-planner --recalculate.
- [ ] L1 status `LEAD_RESOLUTION_IN_PROGRESS` durante bucket execution.
- [ ] Recovery wizard detecta `LEAD_RESOLUTION_STALE` se status > 24h sem progresso.

### Stage 05 audit
- [ ] Sub-step 5.5 audit lead resolutions detecta B1 loosen (FAIL), B3 critic concerns silenced (FAIL), B4 vague rationale (FAIL).
- [ ] B1/B3/B4 corretamente aplicados → audit PASS.
- [ ] FAIL → `BLOCKED_ERROR error_type: lead_resolution_audit_failed`.

### Migration
- [ ] migrate-workspace v3.8.0→v3.9.0 idempotente em smoke fixture.
- [ ] L0 frontmatter de workspace existente ganha `icm_skill_version: "3.9.0"` sem quebrar parse.
- [ ] Status enum atualizado (`LEAD_RESOLUTION_IN_PROGRESS` valid em validate_state.py).

### E2E
- [ ] Workspace lifecycle 04 wave com 2 tasks (1 forensicamente válida + 1 forçada B3 catastrophic).
- [ ] Lead resolve via B3 (escreve direto, passa L2+L3).
- [ ] Stage 05 audit aprova lead resolution.
- [ ] Handoff stage 04 → 05 verde.

## v3.10.0 — E2E coverage reinforcement checks

### Bootstrap
- [ ] Workspace tier=production profile=app_web_backend: novo CONTEXT.md.tpl com step 11b E2E suite gate.
- [ ] Bootstrap copia `e2e-coverage-protocol.md` pra `_references/runtime/`.

### Wave-planner detection
- [ ] Plan com task tocando `src/routes/checkout.ts` profile=app_web_backend → wave-plan.md mostra `yes (auto)` na coluna E2E required + annotation `> **E2E coverage required**`.
- [ ] Plan com task tocando `notebooks/eda.ipynb` profile=data_analysis → coluna E2E required = `no`, sem annotation.
- [ ] Profile fullstack pega paths frontend AND backend.

### Forensic+ Check 8
- [ ] Task com `Requires E2E update: true` no plan.md SEM file em `e2e/`/`cypress/`/`playwright/`/`tests/e2e/` no diff → HARD em tier dev/prod, SOFT em tier exp/tool.
- [ ] Task com `Requires E2E update: true` + e2e file presente → no violation.
- [ ] Task com `**E2E:** skip - rationale` → Check 8 silent skip.
- [ ] Task sem field `Requires E2E update` → Check 8 silent skip.

### Stage 04 wave gate L4
- [ ] tier production profile=backend + e2e_command declarado → step 11b roda E2E suite. Vermelho → BLOCKED_ERROR error_type=e2e_suite_failed → diagnose protocol.
- [ ] tier exp profile=backend sem e2e_command → step 11b skip silently (warning).
- [ ] profile=data_analysis (user_facing_paths vazio) → step 11b skip integral.

### Stage 05 audit (4.7)
- [ ] Suite e2e ausente em workspace tier dev/prod com user_facing_paths não-vazio → BLOCKED_ERROR error_type=e2e_suite_missing.
- [ ] Suite e2e > 7 dias com tasks user-facing entregues → BLOCKED_ERROR error_type=e2e_suite_stale.
- [ ] Task com `**E2E:** skip` sem rationale → BLOCKED_ERROR error_type=e2e_skip_unjustified.
- [ ] CI report e2e vermelho → FAIL.

### Recovery wizard
- [ ] Detector E2E_SUITE_STALE alerta workspace com suite > 7 dias + tasks user-facing recentes em wave-summary.

### Migration
- [ ] migrate-workspace v3.9.0→v3.10.0 idempotente em smoke fixture.
- [ ] L0 frontmatter de workspace existente ganha `icm_skill_version: "3.10.0"` sem quebrar parse.

### E2E (meta-test do reforço)
- [ ] Workspace lifecycle: criar plan com 2 tasks (1 user-facing forencic-flagged, 1 não); confirmar wave-plan.md mostra E2E annotation; designer adiciona `Requires E2E update: true`; subagente A esquece e2e file → Check 8 HARD; subagente B adiciona e2e/checkout.spec.ts → PASS; L4 wave gate roda suite; Stage 05 4.7 audita freshness verde.
