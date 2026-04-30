# Stage 04 Wave Execution — Gaps Fix Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar 10 gaps de protocolo no stage 04 + 12 drifts cross-file + instalar drift prevention automatizado. Resultado: protocolo wave determinístico, repo livre de drift atual, futuras updates protegidas por test gate.

**Architecture:** Bump `v3.4.4 → v3.5.0`. 7 chunks, 30 tasks. Edits concentrados em L2 stage 04 + 3 novos docs canônicos em `references/` + `bootstrap.py` SKILL_VERSION + `validate_state.py` enum + drift detector test. Tests novos: `test_v3_5_0_wave_protocol.py` (14 tests presença) + `test_no_drift.py` (5 tests cross-file). Drift prevention permanente bloqueia future regressions automaticamente.

**Tech Stack:** Python 3.11+, pytest, Hypothesis, Markdown (templates Jinja-like com `{{PLACEHOLDER}}`).

**Workflow:** branch `feat/stage-04-gaps-fix-v3.5.0` a partir de `main`, commits por chunk, `bash tests/run.sh --no-bats` antes de merge, `git merge --ff-only`, branch deletada pós-merge.

**Versionamento:** v3.5.0 (minor bump — vários protocol additions, não-breaking pra workspaces v3.4.x existentes; recovery wizard ganha 1 detector novo).

---

## Gaps endereçados

### Wave protocol gaps (10 — Chunks 1-5)

| # | Gap | Chunk |
|---|-----|-------|
| 1 | CLAUDE.md skill root linha 24 stale ("no worktrees") | 1 |
| 2 | Branch creation ownership ambíguo (lead vs Agent harness) | 2 |
| 3 | Wave-reviewer isolation não especificado | 3 |
| 4 | Cap 3 voltas auto-QA accountability | 3 |
| 5 | Paralelismo Agent → merge sequencial sem sort buffer | 4 |
| 6 | Conflict resolution mid-wave sem protocolo | 4 |
| 7 | HITL granularidade task-level ausente | 3 |
| 8 | Cleanup `--force` decision não-determinística | 2 |
| 9 | CI global vermelho pós-merge sem rollback protocol | 4 |
| 10 | `.icm-main` worktree convention assume presença | 5 |

### Stale files audit (12 — Chunk 6)

| # | Arquivo | Drift | Severidade |
|---|---------|-------|------------|
| 11 | `scripts/bootstrap.py:32` | `SKILL_VERSION = "3.4.1"` | CRÍTICO |
| 12 | `scripts/validate_state.py:33-34` | enum sem `BLOCKED_HITL` | CRÍTICO |
| 13 | `references/state-machine-schema.md:61-62` | row `BLOCKED_HITL` ausente | CRÍTICO |
| 14 | `README.md:15` | "no worktrees" + "10 profiles" | ALTO |
| 15 | `references/design-system.md:1,3` | versão v3.4.4 | MÉDIO |
| 16 | `CLAUDE.md:90,101` | "10 profiles" pré-existente | MÉDIO |
| 17 | `SKILL.md:279` | "10 profiles" | MÉDIO |
| 18 | `scripts/profile-merge.py:3` + `tests/unit/test_profile_merge.py:30` | "10 profiles" | MÉDIO |
| 19 | `scripts/recovery-wizard.py` | sem `MISSING_PRE_WAVE_SHA` detector | MÉDIO |
| 20 | `references/task-types-hitl-afk.md` | sem task-level granularity | ALTO |
| 21 | `references/subagent-protocol.md` | duplica wave-execution-protocol | BAIXO |
| 22 | `references/example-run.md` + `smoke-manual-checklist.md` | sem v3.5.0 fields | BAIXO |

### Drift prevention (3 — Chunk 7)

| # | Solução | Leverage |
|---|---------|----------|
| 23 | `tests/unit/test_no_drift.py` — 4 detectores automáticos | ALTO |
| 24 | `validate_state.py` exporta `ALLOWED_STATUSES` const (single source) | MÉDIO |
| 25 | CLAUDE.md "Pre-merge drift audit (mandatory)" — process backup | BAIXO |

---

## File Structure

**Modify:**
- `CLAUDE.md` (skill root) — fix linha 24 + profile count + Pre-merge drift audit section + pointer wave-execution-protocol
- `README.md` — drift fix worktree + profile count
- `SKILL.md` — bump version + profile count
- `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` — passos 1, 2, 3, 4, 6, 7, 8, 9, 10, 11 reescritos; HITL task-level + sort buffer + status BLOCKED_HITL
- `references/changelog.md` — entrada v3.5.0
- `references/state-machine-schema.md` — BLOCKED_HITL row + profile count fix
- `references/design-system.md` — version bump
- `references/task-types-hitl-afk.md` — task-level granularity
- `references/subagent-protocol.md` — cross-ref dedup
- `references/example-run.md` — sync stage 04 v3.5.0 fields
- `references/smoke-manual-checklist.md` — v3.5.0 checks
- `scripts/bootstrap.py` — SKILL_VERSION 3.4.1 → 3.5.0 (CRÍTICO)
- `scripts/validate_state.py` — ALLOWED_STATUSES const + BLOCKED_HITL (CRÍTICO)
- `scripts/profile-merge.py` — docstring profile count
- `scripts/recovery-wizard.py` — MISSING_PRE_WAVE_SHA detector
- `tests/unit/test_profile_merge.py` — comment profile count
- `tests/unit/test_recovery_wizard.py` — case MISSING_PRE_WAVE_SHA

**Create:**
- `references/wave-execution-protocol.md` — doc canônico consolidado do ciclo wave
- `references/conflict-resolution-protocol.md` — protocolo conflict mid-wave
- `references/ci-rollback-protocol.md` — protocolo rollback CI global vermelho
- `tests/unit/test_v3_5_0_wave_protocol.py` — validações estruturais (14 tests)
- `tests/unit/test_no_drift.py` — drift detector permanente (5 tests)

**Negative scope (não tocar):**
- `scripts/migrate-v3.3-to-v3.4.py` — target específico, não bumpa pra 3.5.0
- `_KICKOFF-v3.4.0-finish.md` — arquivado, deixar
- `scripts/handoff.py`, `wave-planner-script.py` — sem mudança lógica necessária
- Tests legacy (`test_v3_4_*`, fixtures `"3.3.0"`) — whitelist explícito no drift test

---

## Chunk 1: Doc drift fix + version bump prep

### Task 1: Fix CLAUDE.md skill root linha "no worktrees"

**Files:**
- Modify: `CLAUDE.md:55-56` (linha "Stage 04 exception: ...")

- [ ] **Step 1: Read current line**

```bash
sed -n '54,58p' CLAUDE.md
```

Expected output contém: `Stage 04 exception: each wave = 1 lead session; subagents spawned via \`Agent\` tool (no worktrees), branch setup mandatory.`

- [ ] **Step 2: Replace stale line**

`old_string`:
```
Stage 04 exception: each wave = 1 lead session; subagents spawned via `Agent` tool (no worktrees), branch setup mandatory.
```

`new_string`:
```
Stage 04 exception: each wave = 1 lead session; subagentes spawnados via `Agent(isolation: "worktree")` (worktree efêmera por task, criada pelo harness), branch `wave-<NNN>-<N>/<task-slug>` derivada de `BASE_BRANCH`. Doc canônico: `references/wave-execution-protocol.md`.
```

- [ ] **Step 3: Verify edit**

```bash
grep -n "isolation: \"worktree\"" CLAUDE.md
```

Expected: 1 hit em CLAUDE.md root.

- [ ] **Step 4: Commit**

```bash
git checkout -b feat/stage-04-gaps-fix-v3.5.0
git add CLAUDE.md
git commit -m "docs(skill): fix CLAUDE.md root stage 04 line — drift v3.4.0+"
```

---

### Task 2: Version bump SKILL.md + changelog skeleton

**Files:**
- Modify: `SKILL.md:1-10` (frontmatter + linha 7)
- Modify: `references/changelog.md:1-10` (insert v3.5.0 header acima de v3.4.4)

- [ ] **Step 1: Read SKILL.md frontmatter**

```bash
sed -n '1,15p' SKILL.md
```

Capture current version line.

- [ ] **Step 2: Bump version SKILL.md**

`old_string`: `# xp-icm-workflow v3.4.4`
`new_string`: `# xp-icm-workflow v3.5.0`

Se houver `version:` em frontmatter YAML, atualizar também (mesma replace).

- [ ] **Step 3: Insert changelog skeleton**

Edit `references/changelog.md` — adicionar antes da linha `## v3.4.4`:

```markdown
## v3.5.0 — Stage 04 protocol gaps fix (2026-04-29)

### Why v3.5.0

10 gaps de protocolo identificados no stage 04 wave execution durante
revisão de execução real. Cada gap mascarava edge cases que produziam
estado inconsistente (worktrees órfãs, merge order não-determinístico,
conflict mid-wave sem fluxo de retomada, HITL granularidade insuficiente).

### Mudanças

(detalhes preenchidos na Task 14)

---

```

- [ ] **Step 4: Verify edits**

```bash
grep -c "v3.5.0" SKILL.md references/changelog.md
```

Expected: ≥2 hits total.

- [ ] **Step 5: Commit**

```bash
git add SKILL.md references/changelog.md
git commit -m "chore(skill): bump v3.4.4 → v3.5.0 + changelog skeleton"
```

---

## Chunk 2: Branch + cleanup determinism

### Task 3: Branch creation ownership — declarar lead-owned

**Files:**
- Modify: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` (passo 2 do Process)

**Decisão:** lead cria branch ANTES de spawn (`git branch <wave-branch> <BASE_BRANCH>`). Agent tool `isolation: "worktree"` faz `git worktree add` apontando pra essa branch já existente. Razão: se Agent falha pré-checkout, branch órfã é detectável + cleanable; harness criando branch sozinho deixa estado opaco.

- [ ] **Step 1: Read current passo 2**

```bash
sed -n '58,62p' templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl
```

- [ ] **Step 2: Reescrever passo 2 com ownership explícito**

`old_string`:
```
2. **Lead spawn subagentes via Agent tool:** para cada task da wave (até cap), cria branch `wave-{{WORKSPACE}}-<N>/<task-slug>` a partir de `{{BASE_BRANCH}}` e invoca subagente via Agent tool com o contexto da task.
```

`new_string`:
```
2. **Lead spawn subagentes via Agent tool:** para cada task da wave (até cap):
   1. Lead cria branch ANTES do spawn: `git branch wave-{{WORKSPACE_NUM}}-<N>/<task-slug> {{BASE_BRANCH}}`. Lead permanece em workspace branch (sem checkout). Branch órfã (caso Agent falhe pré-checkout) é detectável via `git branch --merged {{BASE_BRANCH}}` e limpa no passo 11.
   2. Lead invoca `Agent(isolation: "worktree", subagent_type: "general-purpose", description: "wave <N> task <slug>", prompt: <AGENT-BRIEF + canal-2>)`. Harness faz `git worktree add` apontando pra branch já existente — NÃO cria branch novo. Path do worktree retornado no Agent tool result; lead persiste em estrutura local pra cleanup posterior.
   3. Tasks paralelas: múltiplos `Agent` calls em UMA mensagem (multi tool-use). Tasks sequenciais (HITL ou dependentes): chamadas sequenciais.
```

- [ ] **Step 3: Verify**

```bash
grep -n "git branch wave-" templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl
```

Expected: ≥1 hit.

- [ ] **Step 4: Commit**

```bash
git add templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl
git commit -m "feat(stage-04): branch creation lead-owned — explicit pre-spawn"
```

---

### Task 4: Cleanup `--force` decision matrix

**Files:**
- Modify: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` (passo 11 — bloco `--force` decision)

**Decisão determinística:** `git worktree remove --force` permitido SOMENTE se `task-<slug>.md` tem `auto_qa_passed: true` registrado. Subagente garante working tree limpa antes de declarar COMPLETE; `--force` só serve pra paths com lock file órfão. Se task report não tem `auto_qa_passed: true` → `BLOCKED_ERROR`, humano inspeciona.

- [ ] **Step 1: Read current cleanup block**

```bash
sed -n '75,90p' templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl
```

- [ ] **Step 2: Replace ambiguous force decision**

`old_string`:
```
   Falha não-fatal: registrar warning em `wave-summary.md` (próximo passo). `git worktree remove` falha se working tree não-limpo → tentar `--force` apenas se Auto-QA Akita já passou (subagente garantiu commit limpo). `git branch -d` recusa se não-merged → não usar `-D` (forçar delete mascararia bugs do merge anterior).
```

`new_string`:
```
   **Decision matrix `--force`:**
   - `git worktree remove <path>` falha se working tree não-limpo → lead lê task report `output/wave-<N>/task-<slug>.md`:
     - `auto_qa_passed: true` no frontmatter → safe usar `git worktree remove --force <path>` (lock file órfão é a única causa restante).
     - `auto_qa_passed: false` ou ausente → NÃO força. Set `status: BLOCKED_ERROR`, registrar em `wave-summary.md`, humano inspeciona manualmente.
   - `git branch -d` recusa se não-merged → JAMAIS usar `-D`. Branch não-merged pós-merge step indica bug no merge sequencial; investigar antes.
   - Falha cleanup não-fatal (após force válido): registrar warning em `wave-summary.md` (próximo passo).
```

- [ ] **Step 3: Verify auto_qa_passed ref existe**

```bash
grep -rn "auto_qa_passed" templates/ references/ | head -5
```

Se zero hits, frontmatter `auto_qa_passed` precisa ser declarado em template de task report. Adicionar em `_references/runtime/4-block-contract-template.md` se ausente (opcional para esta task — registrar dependência).

- [ ] **Step 4: Commit**

```bash
git add templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl
git commit -m "feat(stage-04): cleanup --force decision matrix deterministic"
```

---

## Chunk 3: Subagent protocol additions

### Task 5: Wave-reviewer isolation spec

**Files:**
- Modify: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` (passo 8)

**Decisão:** wave-reviewer = `Agent(subagent_type: "general-purpose", isolation: <UNSET>)` — sem worktree. Reviewer NÃO precisa working tree de cada wave branch; lê código via `git show <branch>:<path>` ou `git diff <BASE_BRANCH>...<wave-branch>`. Roda mais rápido (sem worktree create), CWD = lead workspace.

- [ ] **Step 1: Read current passo 8**

```bash
sed -n '72,74p' templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl
```

- [ ] **Step 2: Reescrever passo 8 com isolation spec**

`old_string`:
```
8. **Wave-reviewer:** subagente revisa Auto-QA Akita de cada task report + verifica que `Files touched` reais batem com declarado no plan.md.
```

`new_string`:
```
8. **Wave-reviewer:** lead spawna `Agent(subagent_type: "general-purpose", description: "wave <N> review")` SEM `isolation: "worktree"` — reviewer roda em CWD do lead (workspace branch), lê código das wave branches via:
   - `git show wave-{{WORKSPACE_NUM}}-<N>/<task-slug>:<file-path>` para conteúdo final.
   - `git diff {{BASE_BRANCH}}...wave-{{WORKSPACE_NUM}}-<N>/<task-slug>` para diff completo.
   - `git log {{BASE_BRANCH}}..wave-{{WORKSPACE_NUM}}-<N>/<task-slug>` para commits da branch.

   Reviewer audita: (a) Auto-QA Akita 15-itens de cada `task-<slug>.md`; (b) `Files touched` reais (via `git diff --name-only`) batem com declarado em plan.md task; (c) acceptance criteria cumpridos. Retorna ao lead via Agent tool output: `approved: true|false`, `issues: [<list>]`. Issues → lead re-spawna subagente original (com `isolation: "worktree"`) para correção.
```

- [ ] **Step 3: Commit**

```bash
git add templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl
git commit -m "feat(stage-04): wave-reviewer isolation explicit — git show, no worktree"
```

---

### Task 6: Auto-QA Akita 3-voltas tracking

**Files:**
- Modify: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` (passo 4 sub-passo 6 + passo 6)

**Decisão:** subagente self-track em counter local + grava `qa_loops_used: <N>` no frontmatter do `task-<slug>.md`. Lead audita via wave-reviewer (passo 8) — se `qa_loops_used > 3` ou ausente em task COMPLETE, reviewer flagra. Não-mentível pois reviewer compara contra git log da wave branch (cada volta = ≥1 commit RED→GREEN→REFACTOR).

- [ ] **Step 1: Read passo 4.6**

```bash
sed -n '67,68p' templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl
```

- [ ] **Step 2: Replace passo 4.6**

`old_string`:
```
   6. Auto-QA Akita 15-itens — `❌` força volta ao passo 4 ou 3 (cap 3 voltas).
```

`new_string`:
```
   6. Auto-QA Akita 15-itens — `❌` força volta ao passo 4 ou 3. Cap 3 voltas; subagente incrementa counter local a cada volta e grava `qa_loops_used: <N>` no frontmatter de `task-<slug>.md`. Volta 4ª = aborta com `BLOCKED_ERROR`.
```

- [ ] **Step 3: Reescrever passo 6 (cap detection)**

`old_string`:
```
6. **Cap 3 voltas auto-QA:** subagente marca `status: BLOCKED_ERROR` no task-report e retorna ao lead via Agent tool; lead decide reduzir wave (ver subagent-protocol) ou escalar humano.
```

`new_string`:
```
6. **Cap 3 voltas auto-QA:** se `qa_loops_used` chegou a 3 e Auto-QA ainda `❌`, subagente:
   1. Marca `status: BLOCKED_ERROR` + `qa_loops_used: 3` + `auto_qa_passed: false` no frontmatter.
   2. Escreve `output/wave-<N>/task-<slug>-blocked.md` com último Auto-QA failed.
   3. Retorna ao lead via Agent tool output.

   Lead recebe → seta L1 `status: BLOCKED_ERROR` → wave-reviewer (passo 8) audita git log da wave branch contando commits RED/GREEN/REFACTOR; se `qa_loops_used` declarado < commits reais, flagra fraude. Lead decide: reduzir wave (subagent-protocol) ou escalar humano.
```

- [ ] **Step 4: Commit**

```bash
git add templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl
git commit -m "feat(stage-04): auto-QA 3-voltas tracking — qa_loops_used + audit"
```

---

### Task 7: HITL granularidade task-level

**Files:**
- Modify: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` (seção `## v3.3.0 references aplicáveis`, bloco HITL handling)

**Decisão:** task-level HITL flag (`type: HITL` em plan.md) isola a task em própria sub-wave (cap=1) já no wave-planner (existente). Em runtime stage 04: se task da wave tem `type: HITL`, lead NÃO spawna Agent — gera AGENT-BRIEF, exibe ao humano, marca `task-<slug>.md` com `status: AWAITING_HITL`. Outras tasks da mesma wave (não-HITL) prosseguem normal em paralelo. Wave fecha quando todas tasks COMPLETE (HITL incluído após humano resolver).

- [ ] **Step 1: Read current HITL block**

```bash
sed -n '293,297p' templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl
```

- [ ] **Step 2: Reescrever HITL handling com granularidade task-level**

`old_string`:
```
- **HITL handling:** se wave é `Type: HITL`, lead session NÃO spawna
  subagent. Gera AGENT-BRIEF, exibe ao humano, atualiza L1 para
  `status=COMPLETED_AWAITING_HUMAN, sub_stage=04_wave_N_hitl_pending`,
  SAIR. Próxima sessão (após humano resolver) retoma wave seguinte.
```

`new_string`:
```
- **HITL handling (task-level granularity):**
  - **Wave-level HITL** (todas tasks da wave têm `type: HITL`, ou
    wave-planner isolou tasks HITL em sub-wave cap=1): lead NÃO spawna
    Agent para nenhuma task. Gera AGENT-BRIEF de cada, exibe ao humano,
    atualiza L1 `status=COMPLETED_AWAITING_HUMAN,
    sub_stage=04_wave_N_hitl_pending`, SAIR. Próxima sessão (após humano
    resolver) lê task reports preenchidos pelo humano e prossegue.
  - **Task-level HITL** (wave mista — algumas tasks `type: HITL`, outras
    não): lead spawna Agents para tasks não-HITL EM PARALELO; para cada
    task HITL gera AGENT-BRIEF + escreve `output/wave-<N>/task-<slug>.md`
    com frontmatter `status: AWAITING_HITL` + brief inline. Lead aguarda
    Agents não-HITL retornarem. Após retorno: se ainda há tasks
    AWAITING_HITL, lead atualiza L1 `status=BLOCKED_HITL,
    sub_stage=04_wave_N_partial_hitl_pending`, SAIR. Próxima sessão
    valida que tasks HITL viraram `status: COMPLETE` (humano editou) e
    retoma passo 8 (wave-reviewer) com a wave inteira.
  - Status canônico novo: `BLOCKED_HITL` (distinto de `BLOCKED_ERROR` —
    não é falha, é espera externa).
```

- [ ] **Step 3: Adicionar BLOCKED_HITL em status canônicos do estágio**

`old_string`:
```
## Status canônicos disponíveis neste estágio

- `IN_PROGRESS` — wave em execução (lead orquestrando, subagentes trabalhando).
- `COMPLETED_AWAITING_HUMAN` — última wave concluída, aguardando humano aprovar transição para 05.
- `BLOCKED_STOP_POINT` — subagente disparou menu A/B/C; humano responde.
- `BLOCKED_ERROR` — merge conflict, CI global vermelho, ou cap 3 voltas auto-QA estourado em alguma task.
```

`new_string`:
```
## Status canônicos disponíveis neste estágio

- `IN_PROGRESS` — wave em execução (lead orquestrando, subagentes trabalhando).
- `COMPLETED_AWAITING_HUMAN` — última wave concluída, aguardando humano aprovar transição para 05.
- `BLOCKED_STOP_POINT` — subagente disparou menu A/B/C; humano responde.
- `BLOCKED_ERROR` — merge conflict, CI global vermelho, cap 3 voltas auto-QA estourado, ou cleanup --force unsafe.
- `BLOCKED_HITL` — wave mista com 1+ task `type: HITL` aguardando humano (não é falha; espera externa).
```

- [ ] **Step 4: Adicionar entrada no state-machine-schema (referência)**

```bash
grep -n "BLOCKED_HITL\|BLOCKED_ERROR" references/state-machine-schema.md | head -5
```

Se `BLOCKED_HITL` ausente: adicionar em `references/state-machine-schema.md` lista de status canônicos (mesma seção que `BLOCKED_ERROR`). Se schema não enumera: documentar em comentário e seguir.

- [ ] **Step 5: Commit**

```bash
git add templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl references/state-machine-schema.md
git commit -m "feat(stage-04): HITL task-level granularity + BLOCKED_HITL status"
```

---

## Chunk 4: Merge orchestration

### Task 8: Sort buffer protocol pré-merge

**Files:**
- Modify: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` (passo 7 + passo 9)

**Decisão:** lead aguarda TODOS Agent calls da wave retornarem (foreground). Resultados chegam ordem não-determinística. Antes do merge sequencial (passo 9), lead constrói lista ordenada por ordem de declaração no `plan.md` (não por timestamp de retorno). Sort key = índice da task no `plan.md > tasks[]` array.

- [ ] **Step 1: Read passo 7**

```bash
sed -n '71,72p' templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl
```

- [ ] **Step 2: Reescrever passo 7 incluindo sort buffer**

`old_string`:
```
7. **Lead recebe resultado de cada subagente via Agent tool:** lead aguarda retorno COMPLETE de cada subagente da wave. Resultados chegam diretamente pelo Agent tool output — sem polling de diretório.
```

`new_string`:
```
7. **Lead recebe resultado de cada subagente via Agent tool:** lead aguarda retorno COMPLETE de cada subagente da wave. Resultados chegam diretamente pelo Agent tool output — sem polling de diretório. Ordem de retorno é não-determinística (paralelismo). Lead bufferiza resultados em estrutura `{task_slug: agent_result}`. Antes do passo 9 (merge sequencial), lead ordena tasks por índice no `plan.md > tasks[]` da wave atual — merge order = plan order, NÃO retorno order. Auditável: `wave-summary.md` lista tasks na ordem do plan.
```

- [ ] **Step 3: Adicionar nota explícita no passo 9**

`old_string`:
```
9. **Merge sequencial:** lead faz merge de cada branch `wave-{{WORKSPACE}}-<N>/<task-slug>` em `{{BASE_BRANCH}}` na ordem do plan. Conflict de merge → `BLOCKED_ERROR`, humano resolve manualmente.
```

`new_string`:
```
9. **Merge sequencial:** lead faz merge de cada branch `wave-{{WORKSPACE_NUM}}-<N>/<task-slug>` em `{{BASE_BRANCH}}` usando ordem buferizada do passo 7 (= ordem do plan). Comando: `git checkout {{BASE_BRANCH}} && git merge --no-ff wave-{{WORKSPACE_NUM}}-<N>/<task-slug>` por task. `--no-ff` preserva grupo de commits da wave branch (auditável). Conflict de merge → ver `references/conflict-resolution-protocol.md`.
```

- [ ] **Step 4: Commit**

```bash
git add templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl
git commit -m "feat(stage-04): sort buffer pré-merge — plan order deterministic"
```

---

### Task 9: Conflict resolution mid-wave protocol

**Files:**
- Create: `references/conflict-resolution-protocol.md`
- Modify: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` (referência adicionada em passo 9 — feita na Task 8)

- [ ] **Step 1: Write conflict-resolution-protocol.md**

```markdown
# Conflict Resolution Protocol — Stage 04 Mid-Wave

> Doc canônico de resolução de conflict de merge durante stage 04 (wave merge sequencial). Referenciado por `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` passo 9.

## Quando dispara

Lead executa `git merge --no-ff wave-<NNN>-<N>/<task-slug>` em passo 9 → comando retorna non-zero com `CONFLICT (content): Merge conflict in <file>`. Lead permanece em `BASE_BRANCH` com working tree em estado de merge incompleto.

## Estado pré-resolução

- `HEAD` em `BASE_BRANCH` com merge in-flight (`.git/MERGE_HEAD` presente).
- Working tree contém arquivos com markers `<<<<<<<`, `=======`, `>>>>>>>`.
- Branches restantes da wave (não-mergeadas ainda): aguardam.
- L1 ainda em `IN_PROGRESS`; lead vai transitar pra `BLOCKED_ERROR`.

## Protocolo

### Fase 1: Lead pausa + sinaliza

1. Lead NÃO tenta resolver autonomamente (decisão deliberada — código de merge é alto risco).
2. Lead atualiza L1:
   - `status: BLOCKED_ERROR`
   - `error_type: merge_conflict`
   - `last_transition.note: "merge conflict wave <N> task <slug-conflitada>"`
   - `history` append: `{event: "merge_conflict", wave: <N>, task: <slug>, conflicted_files: [...]}`
3. Lead escreve `output/wave-<N>/merge-conflict-<slug>.md` documentando:
   - Branch conflitada.
   - Lista de arquivos em conflict (`git diff --name-only --diff-filter=U`).
   - Diff dos hunks conflitados.
   - Tasks restantes da wave NÃO mergeadas ainda.
4. Lead commit atômico:
   ```
   workspace <NNN>: BLOCKED merge conflict wave <N>
   ```
   (commit inclui L1 + merge-conflict-<slug>.md; NÃO inclui mudanças do working tree em conflict.)
5. Lead imprime prompt de resolução pro humano. AGUARDA na mesma sessão.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 BLOCKED_ERROR — merge conflict wave <N>

Branch conflitada: wave-<NNN>-<N>/<task-slug>
Files:
  - <path/to/file1>
  - <path/to/file2>

Working tree em estado de merge in-flight (.git/MERGE_HEAD presente).
Tasks restantes da wave (NÃO mergeadas): <lista>

Opções:
  A) Resolver manualmente nos arquivos + `git add` + `git commit` →
     responda "resolvido" pra retomar passo 9 nas tasks restantes.
  B) Abortar este merge: `git merge --abort` →
     responda "abort task" pra marcar a task como BLOCKED_ERROR e
     pular ela; lead segue pras restantes.
  C) Abortar wave inteira: responda "abort wave" → lead reverte
     todos merges desta wave (`git reset --hard <pre-wave-sha>`),
     marca workspace BLOCKED_ERROR, sai.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Fase 2: Resposta humana

#### "resolvido"

1. Lead valida: `git status --porcelain` retorna vazio para arquivos conflitados; `.git/MERGE_HEAD` ainda presente OU já commitado.
2. Se MERGE_HEAD ainda presente: humano esqueceu de commitar — lead executa `git commit --no-edit` (mensagem default do merge).
3. Lead atualiza L1: `status: IN_PROGRESS`, history append `{event: "conflict_resolved", task: <slug>}`.
4. Lead retoma passo 9 nas tasks restantes da wave (ordem do plan).

#### "abort task"

1. Lead executa `git merge --abort`.
2. Marca `output/wave-<N>/task-<slug>-blocked.md` com `reason: merge_conflict_aborted`.
3. Atualiza L1: `status: IN_PROGRESS`, history append `{event: "task_aborted_conflict", task: <slug>}`.
4. Lead pula task atual, segue passo 9 nas restantes.
5. Wave-summary.md final lista task como BLOCKED_ERROR não-resolvida; humano decide stage 05+.

#### "abort wave"

1. Lead captura `pre_wave_sha` de L1 history (gravado no início da wave).
2. Lead executa `git merge --abort` + `git reset --hard <pre_wave_sha>` em `BASE_BRANCH`.
3. Atualiza L1: `status: BLOCKED_ERROR`, `error_type: wave_aborted`.
4. Lead escreve `output/wave-<N>/wave-aborted.md` com SHAs originais + tasks que estavam pendentes.
5. Lead commit atômico + SAIR. Próxima sessão: humano decide refazer wave ou pular.

### Fase 3: Cleanup pós-resolução

- Tasks resolvidas/abortadas: cleanup normal (passo 11).
- Tasks com merge conflict abortado: branch permanece (não deletada via `git branch -d` pois não-merged); humano pode investigar depois.
- Wave-summary.md (passo 12) registra: `conflicts: [{task: <slug>, resolution: <resolved|aborted>}]`.

## Invariantes

- **Lead jamais resolve conflict autonomamente.** Sempre humano decide.
- **Reset --hard só com SHA explícito de pre-wave** (gravado em L1 history). Nunca `reset --hard HEAD~N`.
- **Branch wave conflict não é deletada** automaticamente (preserva evidência).
- **L1 status reflete realidade:** `BLOCKED_ERROR` durante espera, `IN_PROGRESS` após resolved/aborted.
```

Save to: `references/conflict-resolution-protocol.md`

- [ ] **Step 2: Verify file**

```bash
test -f references/conflict-resolution-protocol.md && wc -l references/conflict-resolution-protocol.md
```

Expected: arquivo existe, ~120 linhas.

- [ ] **Step 3: Commit**

```bash
git add references/conflict-resolution-protocol.md
git commit -m "feat(stage-04): conflict resolution protocol — 3 paths A/B/C"
```

---

### Task 10: CI global vermelho rollback protocol

**Files:**
- Create: `references/ci-rollback-protocol.md`
- Modify: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` (passo 10 — referenciar novo doc)

- [ ] **Step 1: Write ci-rollback-protocol.md**

```markdown
# CI Global Rollback Protocol — Stage 04 Post-Merge

> Doc canônico de rollback quando CI global falha após merge sequencial da wave (passo 10). Referenciado por `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`.

## Quando dispara

Lead completou passo 9 (merge sequencial) com sucesso. Passo 10 roda CI completo (`bash tests/run.sh` ou pipeline equivalente do projeto). Resultado: vermelho. Estado: `BASE_BRANCH` tem todos merges da wave aplicados; CI quebrou.

## Estado pré-rollback

- `BASE_BRANCH` HEAD = último merge da wave (commit verde local mas CI global red).
- L1: `IN_PROGRESS`, sub_stage `04_wave_<N>_in_progress`.
- Cleanup (passo 11) AINDA não executado — worktrees + branches da wave intactos.

## Protocolo

### Fase 1: Diagnose (não pula)

1. Lead invoca `references/diagnose-protocol.md` (build feedback loop → reproduce → hypothesise → fix). Tempo cap: 30min lead-side.
2. Resultado diagnose:
   - **Causa identificada + fix < 50 linhas:** lead aplica fix em `BASE_BRANCH` direto (commit `workspace <NNN>: ci-fix wave <N> <hypothesis>`). Volta passo 10. Loop max 3 vezes.
   - **Causa em task específica + fix > 50 linhas OU múltiplas tasks afetadas:** vai pra Fase 2 (rollback).
   - **Causa não identificada após cap:** vai pra Fase 2 (rollback).

### Fase 2: Rollback

1. Lead captura `pre_wave_sha` de L1 history.
2. Lead atualiza L1:
   - `status: BLOCKED_ERROR`
   - `error_type: ci_global_red`
   - `history` append: `{event: "ci_global_red", wave: <N>, diagnose_attempts: <N>, rolling_back: true}`
3. Lead executa `git reset --hard <pre_wave_sha>` em `BASE_BRANCH`. Mudança destrutiva — wave inteira revertida.
4. Lead PRESERVA wave branches (não deleta). Worktrees efêmeras: cleanup normal (sem `--force` se Auto-QA passou; ver decision matrix passo 11).
5. Lead escreve `output/wave-<N>/ci-rollback.md`:
   - SHAs antes/depois.
   - Diagnose attempts log.
   - Sintomas CI (logs).
   - Tasks da wave (todas afetadas).
6. Lead commit atômico:
   ```
   workspace <NNN>: ci rollback wave <N> — diagnose inconclusive
   ```
7. Lead imprime prompt de gate humano. AGUARDA.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 BLOCKED_ERROR — CI global red post-merge wave <N>

Diagnose: <causa-identificada-ou-inconclusive>
Diagnose attempts: <N>/3

BASE_BRANCH revertida pra <pre_wave_sha> (wave merges destruídos).
Wave branches PRESERVADAS para investigação:
  - wave-<NNN>-<N>/<slug-1>
  - wave-<NNN>-<N>/<slug-2>
  ...

Próximas opções:
  A) Refazer wave: responda "redo wave" → lead re-spawna subagentes
     com lições aprendidas no canal 2. Wave branches existentes
     deletadas; novas criadas.
  B) Refazer task específica: responda "redo task <slug>" → lead
     re-spawna só essa task; outras mantêm branches originais
     (re-merge sequencial após).
  C) Abandonar wave: responda "abandon" → marca workspace
     BLOCKED_ERROR permanente; humano decide stage 05+.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Fase 3: Resposta humana

#### "redo wave"

1. Lead deleta wave branches existentes: `git branch -D wave-<NNN>-<N>/<slug>` (force pois não-merged após reset).
2. Lead injeta no canal 2 da próxima rodada: lessons da `ci-rollback.md` (sintomas + causa identificada se houver).
3. Lead atualiza L1: `status: IN_PROGRESS`, history append `{event: "wave_redo", wave: <N>}`.
4. Volta ao passo 2 do Process (criar branches + spawn subagentes).

#### "redo task <slug>"

1. Lead identifica task pelo slug.
2. Lead deleta SÓ essa branch: `git branch -D wave-<NNN>-<N>/<slug>`. Outras wave branches permanecem.
3. Lead atualiza L1: `status: IN_PROGRESS`, history append `{event: "task_redo", task: <slug>}`.
4. Lead spawna SÓ um Agent pra essa task. Quando retorna COMPLETE, vai pro passo 9 — re-merge SEQUENCIAL de TODAS wave branches (incluindo as preservadas).
5. Volta passo 10 (CI gate global).

#### "abandon"

1. Lead atualiza L1: `status: BLOCKED_ERROR`, `error_type: wave_abandoned`. Sub_stage permanece `04_wave_<N>_in_progress`.
2. Wave branches permanecem (preserva evidência).
3. Lead commit atômico + SAIR.

## Invariantes

- **Reset --hard só com SHA explícito de `pre_wave_sha`.** Capturado em L1 history no início da wave (passo 1 do Process precisa gravar).
- **Wave branches preservadas durante BLOCKED_ERROR ci_global_red.** Cleanup só após resolução (redo wave / redo task / abandon).
- **Diagnose protocol é mandatório antes de rollback.** Não pular pra rollback direto — gasto barato vs custo de re-implementação.
- **L1 history rastreia todas tentativas:** `wave_started`, `ci_global_red`, `wave_redo`, etc.

## Dependência

Passo 1 do Process precisa gravar `pre_wave_sha: <BASE_BRANCH HEAD sha>` em L1 history evento `wave_started`. Sem isso, rollback é cego. Verificar/adicionar em template do passo 1 se ausente.
```

Save to: `references/ci-rollback-protocol.md`

- [ ] **Step 2: Update L2 passo 10 referenciar doc**

`old_string`:
```
10. **CI gate global:** roda CI completo do projeto após todos os merges. Verde → wave concluída.
```

`new_string`:
```
10. **CI gate global:** roda CI completo do projeto após todos os merges. Verde → wave concluída, segue passo 11. Vermelho → ver `references/ci-rollback-protocol.md` (diagnose protocol → rollback se inconclusive → gate humano A/B/C).
```

- [ ] **Step 3: Add pre_wave_sha capture em passo 1**

`old_string`:
```
1. **Lead pre-flight:** lê wave-plan.md; identifica wave atual via L1 `waves.current`. Sub_stage transita para `04_wave_<N>_in_progress`.
```

`new_string`:
```
1. **Lead pre-flight:** lê wave-plan.md; identifica wave atual via L1 `waves.current`. Sub_stage transita para `04_wave_<N>_in_progress`. Lead grava em L1 history evento `{event: "wave_started", wave: <N>, pre_wave_sha: <git rev-parse {{BASE_BRANCH}}>}` — usado por ci-rollback-protocol.md como ponto de reset.
```

- [ ] **Step 4: Commit**

```bash
git add references/ci-rollback-protocol.md templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl
git commit -m "feat(stage-04): CI rollback protocol — diagnose → rollback → gate A/B/C"
```

---

## Chunk 5: .icm-main robustness + tests + finalize

### Task 11: `.icm-main` worktree presence check + fallback

**Files:**
- Modify: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` (seção `## v3.3.0 references aplicáveis`, bloco "Subagent worktree (v3.4.0)")

**Decisão:** comando `cd .icm-main && git pull --ff-only` só executa se `.icm-main` existe E é worktree linkada (verifica via `git worktree list`). Caso contrário: skip silencioso + warning em wave-summary. `.icm-main` é convenção opcional setup pelo recovery wizard ou bootstrap em alguns workspaces — não universal.

- [ ] **Step 1: Read current `.icm-main` block**

```bash
sed -n '283,292p' templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl
```

- [ ] **Step 2: Replace com presence check**

`old_string`:
```
- **Subagent worktree (v3.4.0):** lead spawna subagentes via
  `Agent(isolation: "worktree")` para wave branches `wave-{{WORKSPACE_NUM}}-<N>/<task-slug>`
  derivadas de `{{BASE_BRANCH}}`. Tool cria worktree efêmera; subagente
  trabalha nela isolado da worktree principal (que continua em
  `workspace/{{WORKSPACE}}`). Lead permanece no `{{PROJECT_ROOT}}/`
  workspace branch durante toda a wave. Após subagente terminar, lead
  inspeciona resultado do worktree retornado e merge a wave branch em
  `{{BASE_BRANCH}}` conforme protocol da fase 04. Após merge:
  `cd {{PROJECT_ROOT}}/.icm-main && git pull --ff-only` para sincronizar
  worktree linkada com novo HEAD da base.
```

`new_string`:
```
- **Subagent worktree (v3.4.0):** lead spawna subagentes via
  `Agent(isolation: "worktree")` para wave branches `wave-{{WORKSPACE_NUM}}-<N>/<task-slug>`
  derivadas de `{{BASE_BRANCH}}`. Tool cria worktree efêmera; subagente
  trabalha nela isolado da worktree principal (que continua em
  `workspace/{{WORKSPACE}}`). Lead permanece no `{{PROJECT_ROOT}}/`
  workspace branch durante toda a wave. Após subagente terminar, lead
  inspeciona resultado do worktree retornado e merge a wave branch em
  `{{BASE_BRANCH}}` conforme protocol da fase 04.

  **Sync `.icm-main` (condicional v3.5.0):** após merge, lead checa se
  `{{PROJECT_ROOT}}/.icm-main` existe E é worktree linkada:
  ```bash
  if git worktree list --porcelain | grep -q "worktree {{PROJECT_ROOT}}/.icm-main"; then
      cd {{PROJECT_ROOT}}/.icm-main && git pull --ff-only
  fi
  ```
  Se ausente: skip silencioso (`.icm-main` é convenção opcional setup
  por recovery wizard / bootstrap em alguns workspaces). Falha do
  `pull --ff-only` (ex: divergence): warning não-fatal em
  `wave-summary.md`, lead segue.
```

- [ ] **Step 3: Commit**

```bash
git add templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl
git commit -m "feat(stage-04): .icm-main sync conditional — presence check"
```

---

### Task 12: Wave-execution-protocol consolidated doc

**Files:**
- Create: `references/wave-execution-protocol.md` (doc canônico consolidado, referenciado por L2 + CLAUDE.md root)

- [ ] **Step 1: Write wave-execution-protocol.md**

```markdown
# Wave Execution Protocol — Stage 04 (Canonical)

> Doc canônico do ciclo wave em stage 04. Consolida protocol disperso entre L2 template e references. Source of truth — outros docs apontam pra cá.

## Resumo (1 parágrafo)

Stage 04 = N waves sequenciais. Cada wave = 1 lead session. Lead spawna subagentes via `Agent(isolation: "worktree")`, um por task da wave (até cap por tier 2/3/5/5). Subagente trabalha em worktree efêmera isolada na branch `wave-<NNN>-<N>/<task-slug>`. Após COMPLETE de todos: wave-reviewer audita, lead merge sequencial em `BASE_BRANCH` (ordem do plan), CI global, cleanup, handoff. Mid-wave handoff automático; última wave gate humano.

## Atores

| Ator | Sessão | CWD | Branch | Função |
|------|--------|-----|--------|--------|
| Lead | 1 (toda a wave) | `{{PROJECT_ROOT}}` | `workspace/{{WORKSPACE}}` | Orquestra, gerencia state L1, faz merge |
| Subagente N | Spawnado pelo lead via Agent | Worktree efêmera | `wave-<NNN>-<N>/<task-slug>` | TDD 7 passos, escreve task report |
| Wave-reviewer | Spawnado pelo lead via Agent (sem worktree) | Lead CWD | `workspace/{{WORKSPACE}}` | Audita Auto-QA, files touched, acceptance |
| Humano | Async (gate inline) | — | — | Aprova última wave, resolve conflicts, responde stop points |

## Branches durante wave

```
main (= BASE_BRANCH)         ← estável, lead faz merge aqui
  └─ workspace/<NNN-slug>     ← lead trabalha (state files L1/L2, outputs)
       └─ wave-<NNN>-<N>/<slug-1>  ← subagente 1 (worktree efêmera)
       └─ wave-<NNN>-<N>/<slug-2>  ← subagente 2
       └─ ...
```

## Pipeline (12 passos)

1. **Pre-flight** — lead lê wave-plan.md, identifica wave atual, grava `pre_wave_sha` em L1 history.
2. **Spawn** — lead cria branches + invoca `Agent(isolation: "worktree")` paralelo (multi tool-use).
3. **Canal 2** — lead injeta ADR subset + lessons + design subset (se frontend) no prompt do Agent.
4. **TDD 7 passos** — subagente em worktree: RED → GREEN → CI 1ª → REFACTOR → CI 2ª → Auto-QA → COMPLETE.
5. **Stop points** — subagente detecta `new_dep`/`irreversible`/`over_eng`/`prod_migration`/`adr_drift` → menu A/B/C.
6. **Cap 3 voltas auto-QA** — `qa_loops_used` no task report; reviewer audita.
7. **Lead recebe** — Agent results bufferizados em `{task_slug: result}`; sort por plan order.
8. **Wave-reviewer** — Agent sem worktree, lê via `git show`/`git diff`; aprova ou flagra issues.
9. **Merge sequencial** — `git merge --no-ff` em `BASE_BRANCH`, ordem do plan; conflict → `conflict-resolution-protocol.md`.
10. **CI global** — verde → 11; vermelho → `ci-rollback-protocol.md`.
11. **Cleanup** — `git worktree remove` (decision matrix `--force`) + `git branch -d` (jamais `-D`); sync `.icm-main` condicional.
12. **Handoff** — mid-wave automático ou última wave gate humano (ver L2 § End of stage handoff).

## Status canônicos

- `IN_PROGRESS`
- `COMPLETED_AWAITING_HUMAN` (última wave)
- `BLOCKED_STOP_POINT`
- `BLOCKED_ERROR` (merge conflict, CI red, cap 3 voltas, cleanup unsafe)
- `BLOCKED_HITL` (wave mista, task HITL pendente)

## Cross-references

- Conflict de merge: `references/conflict-resolution-protocol.md`
- CI global vermelho: `references/ci-rollback-protocol.md`
- AGENT-BRIEF render: `references/agent-brief-template.md` + `scripts/agent-brief-render.py`
- Stop points: `references/stop-points-canonical.md`
- Diagnose: `references/diagnose-protocol.md`
- Handoff: `references/session-handoff-protocol.md`
- HITL: `references/task-types-hitl-afk.md`
- L2 stage 04 (instruções runtime): `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`

## Invariantes globais

- Lead sempre em `workspace/<NNN-slug>` durante wave inteira.
- Subagentes nunca leem outros workspaces.
- Branches wave nascem de `BASE_BRANCH`, NÃO de workspace branch.
- Merge sequencial usa ordem do plan, não ordem de retorno do Agent.
- `pre_wave_sha` capturado em L1 history pra rollback.
- Wave branches deletadas SÓ após merge bem-sucedido + CI verde + cleanup.
- Cleanup `--force` SÓ com `auto_qa_passed: true` no task report.
```

Save to: `references/wave-execution-protocol.md`

- [ ] **Step 2: Add cross-ref no L2 header**

`old_string` (logo após linha 24 — antes de "## Inputs"):
```
Execução paralela em waves. Lead session orquestra subagentes via Agent tool respeitando o cap por tier (2/3/5/5). Cada subagente trabalha numa task em branch isolada `wave-{{WORKSPACE}}-<N>/<task-slug>` (a partir de `{{BASE_BRANCH}}`), segue o ciclo TDD 7 passos, valida via auto-QA Akita 15-itens. Subagentes comunicam resultados diretamente ao lead via Agent tool output. Wave-reviewer audita ao fim. Lead faz merge sequencial em `{{BASE_BRANCH}}`. Uma sub_stage por wave: `04_wave_<N>_in_progress` → `04_wave_<N>_completed`. Repete até esgotar `wave-plan.md`.
```

`new_string`:
```
Execução paralela em waves. Lead session orquestra subagentes via Agent tool respeitando o cap por tier (2/3/5/5). Cada subagente trabalha numa task em branch isolada `wave-{{WORKSPACE}}-<N>/<task-slug>` (a partir de `{{BASE_BRANCH}}`), segue o ciclo TDD 7 passos, valida via auto-QA Akita 15-itens. Subagentes comunicam resultados diretamente ao lead via Agent tool output. Wave-reviewer audita ao fim. Lead faz merge sequencial em `{{BASE_BRANCH}}`. Uma sub_stage por wave: `04_wave_<N>_in_progress` → `04_wave_<N>_completed`. Repete até esgotar `wave-plan.md`.

**Doc canônico consolidado:** `references/wave-execution-protocol.md` (single source of truth do pipeline 12-passos).
```

- [ ] **Step 3: Commit**

```bash
git add references/wave-execution-protocol.md templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl
git commit -m "feat(stage-04): wave-execution-protocol canonical doc — single source of truth"
```

---

### Task 13: Tests v3.5.0

**Files:**
- Create: `tests/unit/test_v3_5_0_wave_protocol.py`

- [ ] **Step 1: Write test file**

```python
"""Tests v3.5.0 — stage 04 wave protocol gaps fix.

Cobertura:
- CLAUDE.md root drift fixed (linha "no worktrees" removida)
- L2 template tem branch creation lead-owned
- L2 tem decision matrix --force
- L2 tem wave-reviewer isolation spec
- L2 tem qa_loops_used tracking
- L2 tem BLOCKED_HITL status
- L2 tem sort buffer pre-merge
- conflict-resolution-protocol.md existe + 3 paths A/B/C
- ci-rollback-protocol.md existe + diagnose-first
- L2 tem .icm-main presence check
- wave-execution-protocol.md existe + 12 passos
- Changelog v3.5.0 entry presente
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
L2_PATH = REPO_ROOT / "templates" / "workspace" / "stages" / "04_implementation_waves" / "CONTEXT.md.tpl"
CLAUDE_ROOT = REPO_ROOT / "CLAUDE.md"
SKILL_MD = REPO_ROOT / "SKILL.md"
CHANGELOG = REPO_ROOT / "references" / "changelog.md"
CONFLICT_DOC = REPO_ROOT / "references" / "conflict-resolution-protocol.md"
ROLLBACK_DOC = REPO_ROOT / "references" / "ci-rollback-protocol.md"
WAVE_PROTOCOL_DOC = REPO_ROOT / "references" / "wave-execution-protocol.md"


@pytest.fixture(scope="module")
def l2_text():
    return L2_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def claude_root_text():
    return CLAUDE_ROOT.read_text(encoding="utf-8")


def test_claude_root_no_worktrees_line_removed(claude_root_text):
    """Gap 1: linha 'no worktrees' não deve mais existir."""
    assert "no worktrees" not in claude_root_text, \
        "CLAUDE.md root ainda tem linha stale 'no worktrees'"
    assert "isolation: \"worktree\"" in claude_root_text, \
        "CLAUDE.md root deve mencionar isolation: worktree"


def test_l2_branch_creation_lead_owned(l2_text):
    """Gap 2: passo 2 deve declarar lead cria branch antes do spawn."""
    assert "Lead cria branch ANTES do spawn" in l2_text or \
           "git branch wave-" in l2_text, \
           "L2 deve documentar branch creation lead-owned"


def test_l2_force_decision_matrix(l2_text):
    """Gap 8: passo 11 deve ter decision matrix --force."""
    assert "Decision matrix `--force`" in l2_text or \
           "auto_qa_passed: true" in l2_text, \
           "L2 deve ter decision matrix --force"
    assert "JAMAIS usar `-D`" in l2_text or \
           "não usar `-D`" in l2_text, \
           "L2 deve proibir -D em branch delete"


def test_l2_wave_reviewer_isolation_spec(l2_text):
    """Gap 3: passo 8 deve declarar reviewer SEM worktree."""
    assert "SEM `isolation: \"worktree\"`" in l2_text or \
           "git show wave-" in l2_text, \
           "L2 deve declarar wave-reviewer sem worktree (git show)"


def test_l2_qa_loops_tracking(l2_text):
    """Gap 4: subagente grava qa_loops_used no task report."""
    assert "qa_loops_used" in l2_text, \
        "L2 deve declarar qa_loops_used field"


def test_l2_blocked_hitl_status(l2_text):
    """Gap 7: BLOCKED_HITL status canônico presente."""
    assert "BLOCKED_HITL" in l2_text, \
        "L2 deve declarar status BLOCKED_HITL"
    assert "Task-level HITL" in l2_text or \
           "task-level granularity" in l2_text.lower(), \
           "L2 deve documentar HITL task-level"


def test_l2_sort_buffer(l2_text):
    """Gap 5: passo 7 declara sort por plan order pré-merge."""
    assert "ordem do plan" in l2_text and \
           ("bufferiza" in l2_text or "buferizada" in l2_text), \
           "L2 deve declarar sort buffer pré-merge"


def test_l2_pre_wave_sha(l2_text):
    """Gap 9 dependência: passo 1 grava pre_wave_sha."""
    assert "pre_wave_sha" in l2_text, \
        "L2 passo 1 deve gravar pre_wave_sha em L1 history"


def test_l2_icm_main_conditional(l2_text):
    """Gap 10: .icm-main sync condicional via presence check."""
    assert "git worktree list" in l2_text and \
           ".icm-main" in l2_text, \
           "L2 deve checar presença de .icm-main antes de pull"


def test_conflict_protocol_exists():
    """Gap 6: conflict-resolution-protocol.md existe + 3 paths."""
    assert CONFLICT_DOC.exists(), "conflict-resolution-protocol.md ausente"
    text = CONFLICT_DOC.read_text(encoding="utf-8")
    for path in ("resolvido", "abort task", "abort wave"):
        assert path in text, f"conflict protocol falta path '{path}'"
    assert "git merge --abort" in text
    assert "pre_wave_sha" in text or "reset --hard" in text


def test_ci_rollback_protocol_exists():
    """Gap 9: ci-rollback-protocol.md existe + diagnose-first + 3 opções."""
    assert ROLLBACK_DOC.exists(), "ci-rollback-protocol.md ausente"
    text = ROLLBACK_DOC.read_text(encoding="utf-8")
    assert "diagnose-protocol" in text or "diagnose" in text.lower(), \
        "rollback protocol deve referenciar diagnose-protocol"
    for opt in ("redo wave", "redo task", "abandon"):
        assert opt in text, f"rollback protocol falta opção '{opt}'"
    assert "pre_wave_sha" in text


def test_wave_execution_protocol_canonical_exists():
    """Task 12: wave-execution-protocol.md existe + 12 passos."""
    assert WAVE_PROTOCOL_DOC.exists(), "wave-execution-protocol.md ausente"
    text = WAVE_PROTOCOL_DOC.read_text(encoding="utf-8")
    assert "12 passos" in text or "12-passos" in text or \
           "## Pipeline" in text, \
           "wave-execution-protocol deve listar pipeline"
    for status in ("BLOCKED_HITL", "BLOCKED_ERROR", "IN_PROGRESS"):
        assert status in text, f"wave-execution-protocol falta status {status}"


def test_skill_version_v3_5_0():
    """Task 2: SKILL.md bumped para v3.5.0."""
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "v3.5.0" in text, "SKILL.md deve estar em v3.5.0"


def test_changelog_v3_5_0_entry():
    """Task 2/14: changelog tem entrada v3.5.0."""
    text = CHANGELOG.read_text(encoding="utf-8")
    assert "## v3.5.0" in text, "changelog deve ter ## v3.5.0"
    assert "Stage 04 protocol gaps fix" in text or \
           "wave protocol" in text.lower(), \
           "changelog v3.5.0 deve descrever escopo"
```

Save to: `tests/unit/test_v3_5_0_wave_protocol.py`

- [ ] **Step 2: Run tests — esperam falhar inicialmente se ordem dos commits trocar**

```bash
pytest tests/unit/test_v3_5_0_wave_protocol.py -v
```

Expected: todos passam (assumindo Tasks 1-12 já commitadas). Se algum falha, fix a task correspondente antes de prosseguir.

- [ ] **Step 3: Run full unit suite — guard regression**

```bash
bash tests/run.sh --no-bats
```

Expected: 548+ tests pass (baseline) + 14 novos = ~562. Zero regressions.

- [ ] **Step 4: Commit tests**

```bash
git add tests/unit/test_v3_5_0_wave_protocol.py
git commit -m "test: cobrir v3.5.0 wave protocol gaps fix"
```

---

### Task 14: Changelog v3.5.0 final + merge

**Files:**
- Modify: `references/changelog.md` (preencher detalhes da entrada v3.5.0)

- [ ] **Step 1: Replace skeleton com detalhes completos**

`old_string` (skeleton da Task 2):
```
## v3.5.0 — Stage 04 protocol gaps fix (2026-04-29)

### Why v3.5.0

10 gaps de protocolo identificados no stage 04 wave execution durante
revisão de execução real. Cada gap mascarava edge cases que produziam
estado inconsistente (worktrees órfãs, merge order não-determinístico,
conflict mid-wave sem fluxo de retomada, HITL granularidade insuficiente).

### Mudanças

(detalhes preenchidos na Task 14)

---

```

`new_string`:
```
## v3.5.0 — Stage 04 protocol gaps fix (2026-04-29)

### Why v3.5.0

10 gaps de protocolo identificados no stage 04 wave execution durante
revisão de execução real. Cada gap mascarava edge cases que produziam
estado inconsistente (worktrees órfãs, merge order não-determinístico,
conflict mid-wave sem fluxo de retomada, HITL granularidade insuficiente).

### Mudanças

**1. Doc drift fix (CLAUDE.md skill root):**
- Linha "no worktrees" removida; substituída por referência a
  `Agent(isolation: "worktree")` (alinhamento com v3.4.0+).

**2. Branch lifecycle determinismo (L2 stage 04):**
- Passo 2 explicita: lead cria branch ANTES do spawn (`git branch
  wave-<NNN>-<N>/<slug> <BASE_BRANCH>`), Agent harness faz worktree
  add em branch existente. Branch órfã detectável via `git branch
  --merged`.
- Passo 11 ganha decision matrix `--force` determinística:
  `auto_qa_passed: true` no task report → safe `--force`; senão
  BLOCKED_ERROR.

**3. Subagent protocol additions (L2 stage 04):**
- Passo 8 declara wave-reviewer SEM `isolation: "worktree"` — lê
  via `git show wave-<branch>:<file>` / `git diff <BASE>...<wave>`.
- Passo 4.6 + passo 6: subagente grava `qa_loops_used: <N>` no
  frontmatter de `task-<slug>.md`; reviewer audita contra git log
  da wave branch (anti-fraude).
- HITL handling reescrito com granularity task-level: wave mista
  spawna Agents pra tasks não-HITL em paralelo, tasks HITL
  registradas com `status: AWAITING_HITL`. Status novo:
  `BLOCKED_HITL` (distinto de `BLOCKED_ERROR`).

**4. Merge orchestration (L2 stage 04):**
- Passo 7 ganha sort buffer: `{task_slug: agent_result}` → ordena
  por índice em `plan.md > tasks[]` antes do passo 9. Merge order =
  plan order, não retorno order.
- Passo 1 grava `pre_wave_sha` em L1 history evento `wave_started`
  (usado por rollback).
- Novo doc `references/conflict-resolution-protocol.md`: lead pausa
  em `BLOCKED_ERROR`, escreve `merge-conflict-<slug>.md`, gate
  humano A/B/C (resolvido / abort task / abort wave). Lead JAMAIS
  resolve conflict autonomamente.
- Novo doc `references/ci-rollback-protocol.md`: passo 10 vermelho
  → diagnose-protocol obrigatório (cap 3 attempts, fix < 50 LOC) →
  rollback (`git reset --hard <pre_wave_sha>`) → gate humano A/B/C
  (redo wave / redo task / abandon). Wave branches preservadas
  durante BLOCKED_ERROR.

**5. `.icm-main` robustness (L2 stage 04):**
- Sync `cd .icm-main && git pull --ff-only` agora condicional:
  só executa se `git worktree list --porcelain | grep -q
  ".icm-main"` retorna match. Skip silencioso senão (`.icm-main` é
  convenção opcional setup pelo recovery wizard / bootstrap).

**6. Doc canônico consolidado:**
- Novo `references/wave-execution-protocol.md` consolida pipeline
  12-passos, atores, branches, status, cross-references.
  Single source of truth — outros docs apontam pra cá.

### Migrations / breaking changes

Não há breaking changes pra workspaces v3.4.x existentes:
- Status novo `BLOCKED_HITL` é additive (workspaces antigos não
  usam, mas validador aceita).
- `qa_loops_used` no task report é additive (workspaces antigos
  sem o field continuam válidos; reviewer trata ausente como N/A).
- `pre_wave_sha` em L1 history é additive (recovery wizard ganha
  detector novo `MISSING_PRE_WAVE_SHA` opcional para waves
  iniciadas pré-v3.5.0; auto-fix marca `pre_wave_sha: unknown`).

### Tests

- `tests/unit/test_v3_5_0_wave_protocol.py` — 14 tests cobrindo
  todos os gaps fechados (presença de seções em L2, existência
  dos novos docs, version bump, changelog entry).

### Plan

- `docs/plans/2026-04-29-stage-04-gaps-fix.md` — implementation
  plan completo (5 chunks, 14 tasks).

---

```

- [ ] **Step 2: Run all tests final**

```bash
bash tests/run.sh --no-bats
```

Expected: 562+ pass, zero fails.

- [ ] **Step 3: Commit changelog final**

```bash
git add references/changelog.md
git commit -m "docs(changelog): v3.5.0 entry full — stage 04 gaps fix"
```

(Merge para main movido para Task 30, último task pós-Chunks 6+7.)

---

## Chunk 6: Stale files audit (drift causado por v3.5.0 + drift pré-existente)

Auditoria descobriu 12 arquivos com info desatualizada. Crítico bloqueante: `bootstrap.py` SKILL_VERSION + `validate_state.py` enum + `state-machine-schema.md` BLOCKED_HITL row. Sem esses, workspaces v3.5.0 saem com versão errada e validator rejeita L1.

### Task 15: bootstrap.py SKILL_VERSION bump (CRÍTICO)

**Files:**
- Modify: `scripts/bootstrap.py:32`

`SKILL_VERSION` é a constante real injetada em `{{SKILL_VERSION}}` placeholder. Sem bump, workspaces novos saem com `icm_skill_version: "3.4.1"` no L0.

- [ ] **Step 1: Verify current value**

```bash
grep -n "^SKILL_VERSION" scripts/bootstrap.py
```

Expected: `32:SKILL_VERSION = "3.4.1"`

- [ ] **Step 2: Bump**

`old_string`: `SKILL_VERSION = "3.4.1"  # template prepends \`v\``
`new_string`: `SKILL_VERSION = "3.5.0"  # template prepends \`v\``

- [ ] **Step 3: Run bootstrap tests**

```bash
pytest tests/unit/test_bootstrap.py -v
```

Expected: passa. Se algum test hardcode `"3.4.1"` em assertion, fix com replace.

- [ ] **Step 4: Commit**

```bash
git add scripts/bootstrap.py
git commit -m "chore(bootstrap): SKILL_VERSION 3.4.1 → 3.5.0"
```

---

### Task 16: validate_state.py enum + state-machine-schema BLOCKED_HITL (CRÍTICO)

**Files:**
- Modify: `scripts/validate_state.py:33-34`
- Modify: `references/state-machine-schema.md:61-62`

Sem isso, L1 com `status: BLOCKED_HITL` é rejeitado pelo validator → workspaces v3.5.0 quebram em runtime.

- [ ] **Step 1: Read current enum**

```bash
sed -n '25,45p' scripts/validate_state.py
```

Capture estrutura exata da lista de allowed statuses.

- [ ] **Step 2: Add BLOCKED_HITL ao enum**

`old_string`:
```python
        "BLOCKED_STOP_POINT",
        "BLOCKED_ERROR",
```

`new_string`:
```python
        "BLOCKED_STOP_POINT",
        "BLOCKED_ERROR",
        "BLOCKED_HITL",
```

- [ ] **Step 3: Add row em state-machine-schema.md**

`old_string`:
```
| `BLOCKED_STOP_POINT` | menu A/B/C disparado | humano responde menu; `IN_PROGRESS` |
| `BLOCKED_ERROR` | falha runtime/CI/merge | humano resolve manualmente; `IN_PROGRESS` |
```

`new_string`:
```
| `BLOCKED_STOP_POINT` | menu A/B/C disparado | humano responde menu; `IN_PROGRESS` |
| `BLOCKED_ERROR` | falha runtime/CI/merge | humano resolve manualmente; `IN_PROGRESS` |
| `BLOCKED_HITL` | wave mista, task `type: HITL` aguarda humano (não-falha) | humano completa task report; `IN_PROGRESS` |
```

- [ ] **Step 4: Run validator tests**

```bash
pytest tests/unit/test_state_machine.py -v
```

Expected: passa.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_state.py references/state-machine-schema.md
git commit -m "feat(state): BLOCKED_HITL status — enum + schema"
```

---

### Task 17: README.md drift fix

**Files:**
- Modify: `README.md:15`

Linha 15 tem 2 problemas: "(paralelismo sem worktrees)" stale + "10 profiles × 4 tiers" stale (deveria ser 11 desde v3.4.4).

- [ ] **Step 1: Replace linha 15**

`old_string`:
```
Bootstrap one-shot que cria estrutura ICM (L0/L1/L2/L3) num projeto e SAI. A partir daí o filesystem governa o ciclo — sessões novas leem L0+L1+L2 do estágio atual e trabalham. 9 estágios (00 recon → 08 feedback intake), 10 profiles × 4 tiers calibrando rigor, subagentes via Agent Tool na fase 04 (paralelismo sem worktrees), Wave Planner determinístico + LLM review subagent, Recovery Wizard pra workspaces órfãos.
```

`new_string`:
```
Bootstrap one-shot que cria estrutura ICM (L0/L1/L2/L3) num projeto e SAI. A partir daí o filesystem governa o ciclo — sessões novas leem L0+L1+L2 do estágio atual e trabalham. 9 estágios (00 recon → 08 feedback intake), 11 profiles × 4 tiers calibrando rigor, subagentes via Agent Tool na fase 04 (paralelismo via `Agent(isolation: "worktree")` — worktree efêmera por task), Wave Planner determinístico + LLM review subagent, Recovery Wizard pra workspaces órfãos.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(readme): fix drift — 11 profiles + worktree isolation"
```

---

### Task 18: design-system.md version bump

**Files:**
- Modify: `references/design-system.md:1,3`

- [ ] **Step 1: Replace title**

`old_string`: `# Design System — DESIGN.md format (v3.4.4)`
`new_string`: `# Design System — DESIGN.md format (v3.5.0)`

- [ ] **Step 2: Replace version line**

`old_string`: `> **Versão:** v3.4.4`
`new_string`: `> **Versão:** v3.5.0`

- [ ] **Step 3: Commit**

```bash
git add references/design-system.md
git commit -m "docs(design-system): bump v3.4.4 → v3.5.0"
```

---

### Task 19: CLAUDE.md profile count + doc references

**Files:**
- Modify: `CLAUDE.md:90,101`

Drift pré-existente desde v3.4.4 (fullstack adicionado, docs nunca atualizados).

- [ ] **Step 1: Replace linha 90**

`old_string`: `- **profile-merge.py** — Merges 10 profiles × 4 tiers → deterministic effective hash (sha256)`
`new_string`: `- **profile-merge.py** — Merges 11 profiles × 4 tiers → deterministic effective hash (sha256)`

- [ ] **Step 2: Replace linha 101**

`old_string`:
```
10 profiles (e.g., `app_web_backend`, `ml_project`, `agent_ia`) × 4 tiers (`experimental`, `tool`, `development`, `production`). Config keys: `stages_skipped`, `tdd_required`, `security_gate`, `stop_points_calibration`. See `templates/_config/profile-matrix.md`.
```

`new_string`:
```
11 profiles (e.g., `app_web_backend`, `app_web_frontend`, `fullstack`, `ml_project`, `agent_ia`) × 4 tiers (`experimental`, `tool`, `development`, `production`). Config keys: `stages_skipped`, `tdd_required`, `security_gate`, `stop_points_calibration`. See `templates/_config/profile-matrix.md`.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): fix profile count drift 10 → 11 (fullstack)"
```

---

### Task 20: SKILL.md profile count

**Files:**
- Modify: `SKILL.md:279`

- [ ] **Step 1: Replace**

`old_string`: `| `templates/_config/profile-matrix.md` | Matriz canônica 10 profiles × 4 tiers |`
`new_string`: `| `templates/_config/profile-matrix.md` | Matriz canônica 11 profiles × 4 tiers |`

- [ ] **Step 2: Commit**

```bash
git add SKILL.md
git commit -m "docs(skill): fix profile count 10 → 11"
```

---

### Task 21: Scripts + tests profile count

**Files:**
- Modify: `scripts/profile-merge.py:3`
- Modify: `tests/unit/test_profile_merge.py:30`
- Modify: `references/state-machine-schema.md:26`

- [ ] **Step 1: profile-merge.py docstring**

`old_string`: `Cobre 10 profiles canonicos x 4 tiers, com regras de override seguro`
`new_string`: `Cobre 11 profiles canonicos x 4 tiers, com regras de override seguro`

- [ ] **Step 2: test_profile_merge.py comment**

`old_string`: `# 1. Cobertura completa: 10 profiles x 4 tiers`
`new_string`: `# 1. Cobertura completa: 11 profiles x 4 tiers`

- [ ] **Step 3: state-machine-schema.md table row**

`old_string`: `| `profile_base` | string | um de 10 profiles canônicos | Bootstrap |`
`new_string`: `| `profile_base` | string | um de 11 profiles canônicos | Bootstrap |`

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_profile_merge.py -v
```

Expected: passa.

- [ ] **Step 5: Commit**

```bash
git add scripts/profile-merge.py tests/unit/test_profile_merge.py references/state-machine-schema.md
git commit -m "chore: fix profile count drift 10 → 11 (scripts + tests + schema)"
```

---

### Task 22: recovery-wizard.py detector MISSING_PRE_WAVE_SHA

**Files:**
- Modify: `scripts/recovery-wizard.py`

Plan changelog declarou additive `MISSING_PRE_WAVE_SHA` mas Task original não implementou.

- [ ] **Step 1: Localize add_detector pattern**

```bash
grep -n "def detect_\|DETECTORS\b" scripts/recovery-wizard.py | head -10
```

Identificar padrão usado pra detectores existentes (`HASH_MISMATCH`, `MISSING_COMMIT`, etc.).

- [ ] **Step 2: Adicionar detector + auto-fix**

Adicionar função `detect_missing_pre_wave_sha(workspace_path)`:
- Lê L1 history.
- Filtra eventos `wave_started` em estágio 04.
- Para cada: checa se `pre_wave_sha` field presente.
- Se ausente E sub_stage começa com `04_wave_`: retorna inconsistência tipo `MISSING_PRE_WAVE_SHA`.
- Auto-fix: marca `pre_wave_sha: "unknown"` + warning em history note (não tenta inferir SHA — humano decide rollback).

Integrar em `DETECTORS` list/dict (ou padrão equivalente do script).

- [ ] **Step 3: Test**

Adicionar caso em `tests/unit/test_recovery_wizard.py`:
- Cria workspace v3.4.x simulado (sem `pre_wave_sha`).
- Roda wizard.
- Verifica detecção + auto-fix grava `unknown`.

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_recovery_wizard.py -v
```

- [ ] **Step 5: Commit**

```bash
git add scripts/recovery-wizard.py tests/unit/test_recovery_wizard.py
git commit -m "feat(recovery): MISSING_PRE_WAVE_SHA detector — v3.4.x → v3.5.0 migration"
```

---

### Task 23: task-types-hitl-afk.md atualizar pra task-level

**Files:**
- Modify: `references/task-types-hitl-afk.md`

- [ ] **Step 1: Read doc atual**

```bash
cat references/task-types-hitl-afk.md
```

Identificar seções que descrevem HITL handling em wave-level (a serem expandidas pra task-level).

- [ ] **Step 2: Adicionar seção "Task-level HITL granularity (v3.5.0)"**

Após seção que descreve HITL atual, inserir:

```markdown
## Task-level HITL granularity (v3.5.0)

Antes de v3.5.0: wave inteira pausava se 1+ task HITL (lead saía, próxima sessão retomava). Resultado: tasks não-HITL da mesma wave esperavam desnecessariamente.

A partir de v3.5.0:
- **Wave HITL pura** (todas tasks `type: HITL`, ou wave-planner isolou em sub-wave cap=1): comportamento legacy mantido. Lead não spawna Agent, gera AGENT-BRIEFs, sai com `BLOCKED_HITL`.
- **Wave mista** (tasks HITL + não-HITL): lead spawna Agents só pra não-HITL EM PARALELO. Tasks HITL: AGENT-BRIEF inline em `task-<slug>.md` + `status: AWAITING_HITL`. Lead aguarda Agents retornarem. Se ainda há `AWAITING_HITL`: L1 `status: BLOCKED_HITL`, sai. Próxima sessão valida tasks HITL viraram COMPLETE (humano editou) e retoma wave-reviewer.

### Status canônico associado

`BLOCKED_HITL` (distinto de `BLOCKED_ERROR` — não é falha, é espera externa). Listado em `references/state-machine-schema.md`.

### Cross-ref

- Pipeline detalhado: `references/wave-execution-protocol.md`
- L2 runtime: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` § HITL handling
```

- [ ] **Step 3: Commit**

```bash
git add references/task-types-hitl-afk.md
git commit -m "docs(hitl): task-level granularity v3.5.0 + BLOCKED_HITL"
```

---

### Task 24: subagent-protocol.md cross-ref dedup

**Files:**
- Modify: `references/subagent-protocol.md`

Doc canônico antigo de subagent handling pode ter conteúdo duplicado com `wave-execution-protocol.md` novo.

- [ ] **Step 1: Read doc**

```bash
cat references/subagent-protocol.md | head -100
```

Identificar seções que duplicam pipeline de wave (passo 1-12).

- [ ] **Step 2: Decision**

- Se duplica >50%: substituir seção duplicada por pointer único: `> Pipeline detalhado: ver references/wave-execution-protocol.md (canonical).`
- Se complementa: adicionar nota no topo: `> Para o pipeline 12-passos canônico: references/wave-execution-protocol.md. Este doc cobre detalhes específicos de subagent dispatch (cap por tier, subagent-driven-development pattern).`

- [ ] **Step 3: Commit**

```bash
git add references/subagent-protocol.md
git commit -m "docs(subagent-protocol): cross-ref wave-execution-protocol canonical"
```

---

### Task 25: example-run.md sync stage 04

**Files:**
- Modify: `references/example-run.md`

Walkthrough E2E. Stage 04 example provavelmente desatualizado (sem `pre_wave_sha`, sem `qa_loops_used`, sem sort buffer, sem BLOCKED_HITL paths).

- [ ] **Step 1: Read seção stage 04**

```bash
grep -n "04\|stage 04\|wave" references/example-run.md | head -20
```

- [ ] **Step 2: Atualizar fields no walkthrough**

Adicionar nos exemplos de L1 history events:
- `wave_started` event com `pre_wave_sha`.
- Task report frontmatter com `qa_loops_used: <N>` + `auto_qa_passed: true`.
- (Opcional) caminho com BLOCKED_HITL ilustrando wave mista.

- [ ] **Step 3: Commit**

```bash
git add references/example-run.md
git commit -m "docs(example-run): sync stage 04 com v3.5.0 fields"
```

---

### Task 26: smoke-manual-checklist.md add v3.5.0 checks

**Files:**
- Modify: `references/smoke-manual-checklist.md`

- [ ] **Step 1: Adicionar seção v3.5.0 checklist**

Append:

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add references/smoke-manual-checklist.md
git commit -m "docs(smoke): v3.5.0 wave protocol checks"
```

---

## Chunk 7: Drift prevention (automatizar audit)

Auditoria manual falha em sessões fresh. Sem test gate determinístico, drift sempre volta. T27-T29 instalam guardrails permanentes.

### Task 27: test_no_drift.py — 4 detectores

**Files:**
- Create: `tests/unit/test_no_drift.py`

Test pytest que falha se inconsistência detectada. Roda em `bash tests/run.sh --no-bats`. PR drift bloqueado automaticamente.

- [ ] **Step 1: Write test file**

```python
"""Drift detection — bloqueia inconsistências cross-file.

4 detectores:
A. Versão consistente (canonical = scripts/bootstrap.py SKILL_VERSION)
B. Profile count consistente (canonical = len(CANONICAL_PROFILES))
C. Status enum sync (state-machine-schema ↔ validate_state.py ↔ L2 templates)
D. Cross-ref resolves (markdown links em references/ + templates/)

Whitelist exceptions explícitas — nunca grep-and-update silencioso.
"""
import re
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ============================================================
# A. Version consistency
# ============================================================

VERSION_RE = re.compile(r"v(\d+\.\d+\.\d+)")

# Whitelist: arquivos que LEGITIMAMENTE mencionam versões antigas
# (changelog histórico, scripts de migração com target específico,
# kickoffs arquivados). Caminho relativo a REPO_ROOT.
VERSION_WHITELIST = {
    "references/changelog.md",            # registro histórico
    "scripts/migrate-v3.3-to-v3.4.py",    # target específico
    "_KICKOFF-v3.4.0-finish.md",          # arquivado
    "tests/unit/test_migrate_v3_3_to_v3_4.py",  # asserta migração
    "tests/unit/test_bootstrap.py",       # fixtures legacy
    "tests/unit/test_stop_points_render.py",  # fixtures legacy
    "docs/plans",                         # plans históricos
}

# Arquivos que DEVEM mencionar a versão canônica
VERSION_MUST_MATCH = [
    ("SKILL.md", r"# xp-icm-workflow v(\d+\.\d+\.\d+)"),
    ("references/design-system.md", r"format \(v(\d+\.\d+\.\d+)\)"),
]


def _canonical_version() -> str:
    bootstrap = _load_module("bootstrap", REPO_ROOT / "scripts" / "bootstrap.py")
    return bootstrap.SKILL_VERSION  # "3.5.0"


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


# ============================================================
# B. Profile count consistency
# ============================================================

PROFILE_COUNT_RE = re.compile(r"(\d+)\s+profiles\b")
PROFILE_COUNT_WHITELIST = {
    "references/changelog.md",  # registro histórico
    "docs/plans",
}


def _canonical_profile_count() -> int:
    pm = _load_module("profile_merge", REPO_ROOT / "scripts" / "profile-merge.py")
    return len(pm.CANONICAL_PROFILES)


def _is_whitelisted(rel_path: str, whitelist: set) -> bool:
    return any(rel_path == w or rel_path.startswith(w + "/") or rel_path.startswith(w + "\\")
               for w in whitelist)


def test_profile_count_consistency():
    """Toda menção a 'N profiles' deve bater com len(CANONICAL_PROFILES)."""
    canonical = _canonical_profile_count()
    violations = []
    for path in REPO_ROOT.rglob("*.md"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if _is_whitelisted(rel, PROFILE_COUNT_WHITELIST):
            continue
        text = path.read_text(encoding="utf-8")
        for match in PROFILE_COUNT_RE.finditer(text):
            n = int(match.group(1))
            if n != canonical:
                violations.append(f"{rel}: '{match.group(0)}' (canonical {canonical})")
    for path in REPO_ROOT.rglob("*.py"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if _is_whitelisted(rel, PROFILE_COUNT_WHITELIST):
            continue
        text = path.read_text(encoding="utf-8")
        for match in PROFILE_COUNT_RE.finditer(text):
            n = int(match.group(1))
            if n != canonical:
                violations.append(f"{rel}: '{match.group(0)}' (canonical {canonical})")
    assert not violations, "Profile count drift:\n  " + "\n  ".join(violations)


# ============================================================
# C. Status enum sync
# ============================================================

def _validator_statuses() -> set:
    """Lê statuses permitidos do validate_state.py via parsing AST simples."""
    text = (REPO_ROOT / "scripts" / "validate_state.py").read_text(encoding="utf-8")
    # Heuristic: linhas tipo `"BLOCKED_*"` ou `"IN_PROGRESS"` em lista
    return set(re.findall(r'"([A-Z_]+)"', text))


def _schema_statuses() -> set:
    """Extrai status canônicos de state-machine-schema.md."""
    text = (REPO_ROOT / "references" / "state-machine-schema.md").read_text(encoding="utf-8")
    # Heuristic: pattern `\| \`STATUS_NAME\``
    return set(re.findall(r"\|\s*`([A-Z_]+)`", text))


# Statuses canônicos (allow-list — guarda contra typos no validator/schema)
EXPECTED_STATUSES = {
    "IN_PROGRESS",
    "COMPLETED",
    "COMPLETED_AWAITING_HUMAN",
    "BLOCKED_STOP_POINT",
    "BLOCKED_ERROR",
    "BLOCKED_HITL",
}


def test_validator_has_expected_statuses():
    """validate_state.py enum cobre todos statuses canônicos."""
    validator = _validator_statuses()
    missing = EXPECTED_STATUSES - validator
    assert not missing, f"validate_state.py falta: {missing}"


def test_schema_doc_has_expected_statuses():
    """state-machine-schema.md table cobre todos statuses canônicos."""
    schema = _schema_statuses()
    missing = EXPECTED_STATUSES - schema
    assert not missing, f"state-machine-schema.md falta rows: {missing}"


# ============================================================
# D. Markdown cross-ref resolves
# ============================================================

MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
SCAN_DIRS = ["references", "templates", "docs"]


def test_markdown_cross_refs_resolve():
    """Links markdown relativos devem apontar pra arquivos existentes."""
    violations = []
    for sub in SCAN_DIRS:
        root = REPO_ROOT / sub
        if not root.exists():
            continue
        for md in list(root.rglob("*.md")) + list(root.rglob("*.tpl")):
            text = md.read_text(encoding="utf-8")
            for label, target in MD_LINK_RE.findall(text):
                # Ignore: URLs, anchors-only, mailto
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                # Ignore: placeholders {{...}}
                if "{{" in target:
                    continue
                # Strip anchor
                path_part = target.split("#", 1)[0]
                if not path_part:
                    continue
                resolved = (md.parent / path_part).resolve()
                # Try also from REPO_ROOT (for absolute-style refs)
                if not resolved.exists():
                    alt = (REPO_ROOT / path_part.lstrip("/")).resolve()
                    if alt.exists():
                        resolved = alt
                if not resolved.exists():
                    violations.append(f"{md.relative_to(REPO_ROOT).as_posix()}: broken link → {target}")
    # Soft assert: muitos links em templates podem ser placeholders runtime;
    # fail apenas se >0 quebrados em references/
    references_violations = [v for v in violations if v.startswith("references/")]
    assert not references_violations, \
        "Broken cross-refs em references/:\n  " + "\n  ".join(references_violations)
```

Save to: `tests/unit/test_no_drift.py`

- [ ] **Step 2: Run drift tests**

```bash
pytest tests/unit/test_no_drift.py -v
```

Expected: todos passam. Se algum falhar, indica drift residual não coberto pelas Tasks 1-26 — fix antes de prosseguir.

- [ ] **Step 3: Run full suite — ensure no regression**

```bash
bash tests/run.sh --no-bats
```

Expected: 562+ tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_no_drift.py
git commit -m "test(drift): no-drift detector — version + profile count + status enum + cross-refs"
```

---

### Task 28: validate_state.py exporta ALLOWED_STATUSES const

**Files:**
- Modify: `scripts/validate_state.py`

Currently statuses estão hardcoded em meio a função. Promover pra constante module-level facilita import + reuso pelo drift test.

- [ ] **Step 1: Read estrutura atual**

```bash
sed -n '20,50p' scripts/validate_state.py
```

- [ ] **Step 2: Refactor — extrair constante**

Substituir lista hardcoded por:

```python
ALLOWED_STATUSES = (
    "IN_PROGRESS",
    "COMPLETED",
    "COMPLETED_AWAITING_HUMAN",
    "BLOCKED_STOP_POINT",
    "BLOCKED_ERROR",
    "BLOCKED_HITL",
)
```

(No topo do módulo, após imports.) Função validadora referencia `ALLOWED_STATUSES`.

- [ ] **Step 3: Update test_no_drift.py para importar const**

`old_string` (em test_no_drift.py):
```python
def _validator_statuses() -> set:
    """Lê statuses permitidos do validate_state.py via parsing AST simples."""
    text = (REPO_ROOT / "scripts" / "validate_state.py").read_text(encoding="utf-8")
    # Heuristic: linhas tipo `"BLOCKED_*"` ou `"IN_PROGRESS"` em lista
    return set(re.findall(r'"([A-Z_]+)"', text))
```

`new_string`:
```python
def _validator_statuses() -> set:
    """Importa ALLOWED_STATUSES do validate_state.py (single source)."""
    vs = _load_module("validate_state", REPO_ROOT / "scripts" / "validate_state.py")
    return set(vs.ALLOWED_STATUSES)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_state_machine.py tests/unit/test_no_drift.py -v
```

Expected: passa.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_state.py tests/unit/test_no_drift.py
git commit -m "refactor(validator): export ALLOWED_STATUSES const — single source for drift test"
```

---

### Task 29: CLAUDE.md adicionar seção drift audit mandatory

**Files:**
- Modify: `CLAUDE.md` (skill root)

Process doc apoiando o test gate. Última linha de defesa — informa próxima sessão sobre obrigação.

- [ ] **Step 1: Read seção "Workflow de modificações"**

```bash
sed -n '1,60p' CLAUDE.md
```

- [ ] **Step 2: Adicionar seção após "Workflow de modificações"**

Insert after closing `}` ou final block do Workflow section:

```markdown
## Pre-merge drift audit (mandatory)

**Toda PR que toca `references/`, `templates/`, `scripts/`, `SKILL.md`, `CLAUDE.md`, `README.md` DEVE rodar:**

```bash
pytest tests/unit/test_no_drift.py -v
```

**Detectores ativos:**
- Versão consistente (canonical = `scripts/bootstrap.py:SKILL_VERSION`).
- Profile count (canonical = `len(CANONICAL_PROFILES)` em `profile-merge.py`).
- Status enum sync (validate_state.py ↔ state-machine-schema.md).
- Cross-refs resolvem (links markdown em `references/`).

**Se test falha:**
- NÃO mergear até fix.
- Adicionar entrada no whitelist do test (`VERSION_WHITELIST` / `PROFILE_COUNT_WHITELIST`) APENAS se a divergência é legítima (changelog histórico, kickoff arquivado, fixture legacy explícita).
- Caso contrário: fix o drift no arquivo que diverge.

**Por que automatizado:** repo é highly-coupled (versão em 5+ arquivos, profile count em 8+, status enum em 3+). Auditar manualmente em sessão fresh é não-confiável. Test gate bloqueia drift no commit, sem precisar lembrar.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): pre-merge drift audit mandatory + leverage automation"
```

---

### Task 30: Final tests + merge para main

**Files:** N/A (operação git).

- [ ] **Step 1: Run full suite final**

```bash
bash tests/run.sh --no-bats
```

Expected: 562+ tests pass (548 baseline + 14 v3.5.0 protocol + drift tests). Zero regressions.

- [ ] **Step 2: Run drift detector explicit**

```bash
pytest tests/unit/test_no_drift.py -v
```

Expected: 5/5 pass.

- [ ] **Step 3: Verify branch state**

```bash
git log --oneline main..HEAD | wc -l
```

Expected: ~30 commits (Tasks 1-29).

- [ ] **Step 4: Merge para main**

```bash
git checkout main
git merge --ff-only feat/stage-04-gaps-fix-v3.5.0
git branch -d feat/stage-04-gaps-fix-v3.5.0
```

Expected: fast-forward merge limpo. Branch deletada.

- [ ] **Step 5: Final verify**

```bash
git log --oneline -30
bash tests/run.sh --no-bats
```

Expected: ~30 commits novos visíveis em main, todos tests pass.

---

## Done criteria

- [ ] Tasks 1-30 todas com checkboxes ✅.
- [ ] `pytest tests/unit/test_v3_5_0_wave_protocol.py -v` 14/14 pass.
- [ ] `pytest tests/unit/test_no_drift.py -v` 5/5 pass.
- [ ] `bash tests/run.sh --no-bats` 562+ pass, zero regressions.
- [ ] `git log --oneline main..HEAD` vazio (tudo merged).
- [ ] Branch `feat/stage-04-gaps-fix-v3.5.0` deletada.
- [ ] `references/changelog.md` tem entrada v3.5.0 completa.
- [ ] Versão `v3.5.0` em SKILL.md + bootstrap.py + design-system.md.
- [ ] `BLOCKED_HITL` em validate_state.py + state-machine-schema.md + L2 stage 04.
- [ ] Profile count consistente em todos os arquivos não-whitelisted (11 profiles).

## Rollback (caso algo dê errado durante execução)

Cada chunk = 1+ commits independentes. Se chunk N falha:
1. `git log --oneline` localiza último commit OK.
2. `git reset --hard <sha-OK>` na branch feat (NÃO em main).
3. Re-tenta chunk com correção.

Se main já recebeu merge corrompido (improvável com `--ff-only`):
1. `git reflog` identifica HEAD pré-merge.
2. `git reset --hard HEAD@{N}` em main.
3. Investiga + retry branch.
