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
