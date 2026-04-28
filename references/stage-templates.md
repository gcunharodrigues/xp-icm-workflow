# Stage Templates — Spec Canônico L2 (xp-icm-workflow v3.0.0-beta5)

> **Propósito:** define o **schema obrigatório** dos 9 templates L2 em `templates/workspace/stages/<NN>_<slug>/CONTEXT.md.tpl`. Cada L2 é um *contrato de estágio*: declara o que o agente lê, processa e escreve quando aquele estágio está ativo.

> **Status:** spec. L2 templates concretos em `templates/workspace/stages/*/CONTEXT.md.tpl`. Toda alteração de schema aqui obriga regenerar os 9 .tpl + atualizar `tests/unit/test_l2_templates.py`.

> **Não confundir:** este doc é spec do **template** L2. O `.tpl` resultante carrega placeholders `{{PROJECT_ROOT}}` e `{{WORKSPACE}}` que o bootstrap resolve. O resultado materializado em `<project_root>/workspaces/<NNN-slug>/stages/<NN>_<slug>/CONTEXT.md` é o L2 efetivo lido por sessões.

---

## Os 9 estágios

| NN | Nome (slug)              | Resumo 1 frase |
|----|--------------------------|----------------|
| 00 | `recon`                  | Reconnaissance do projeto/repositório: detecta stack, branch, ADRs e lessons existentes; gera baseline para os estágios seguintes. |
| 01 | `discovery`              | Brainstorming guiado: público, requisitos funcionais/não-funcionais, alternativas, MVP IN/OUT, riscos, métricas. |
| 02 | `design`                 | Plano arquitetural + ADRs formais; modelagem de dados, contratos de API, divisão em tasks com 4-block contract + Test Strategy global. |
| 03 | `wave_planner`           | Constrói DAG de tasks, agrupa em waves respeitando cap de subagentes e dependências; LLM review subagent assina o plano. |
| 04 | `implementation_waves`   | Execução paralela via subagentes em branches isoladas; lead orquestra spawn/saída do Agent tool/merge sequencial; uma sub-stage por wave. |
| 05 | `verification`           | Verificação técnica do que foi entregue: CI, cobertura vs threshold (test_specs), sample-check tipos de teste, conformidade ao plano e ADRs; PASS/CONDITIONAL/FAIL. |
| 06 | `review`                 | Code review nas 7 dimensões (correctness, security, tests, design, standards, readability, performance) + recebimento de feedback. |
| 07 | `merge`                  | Finaliza branch: merge direto, PR, tag de release ou cleanup; atualiza lessons/tech_debt; fecha o ciclo de entrega. |
| 08 | `feedback_intake`        | Pós-uso real: 3 saídas — A) close workspace, B) restart fase X (`iteration++`), C) spawn novo workspace herdando lessons+ADRs. |

---

## Schema obrigatório do L2 template

Todo `stages/<NN>_<slug>/CONTEXT.md.tpl` DEVE conter as 12 seções abaixo, **na ordem**. Test parser falha se faltar qualquer uma.

### 1. YAML frontmatter

```yaml
---
layer: L2
stage: "<NN>"                              # string "00".."08"
stage_name: "<slug>"                       # ∈ {recon, discovery, design, wave_planner, implementation_waves, verification, review, merge, feedback_intake}
sub_stage_enum:                            # lista canônica do estágio (ver §Sub_stage enum)
  - "<NN>_in_progress"
  - "<NN>_completed"
applicable_stop_points:                    # lista de IDs de stop-points-canonical.md aplicáveis aqui
  - "<sp_id>"
output_files:                              # paths relativos a stage dir
  - "output/<file>.md"
next_stage: "<MM>"                         # próximo estágio padrão; null se 08 ou se profile pula
---
```

**Campos obrigatórios:** `layer`, `stage`, `stage_name`, `sub_stage_enum`, `applicable_stop_points`, `output_files`, `next_stage`. Todos validados pelo parser de Round 2.

**Regra:** `stage_name` em snake_case sem prefixo numérico (o número está em `stage`). `sub_stage_enum` bate **exatamente** com `references/state-machine-schema.md` §Sub-stage enum.

### 2. Título + propósito (1 parágrafo)

```markdown
# Estágio {{STAGE_NN}} — {{STAGE_NAME}} (L2)

<1 parágrafo: o que este estágio entrega ao workspace, em linguagem direta. Sem floreio.>
```

### 3. Tabela `Inputs (lê SOMENTE estes, na ordem)`

Formato literal §4.11 do plan. Mínimo 3 linhas (L0, L1, L2 do estágio). Estágios subsequentes acrescentam outputs anteriores e ADRs/conventions.

```markdown
## Inputs (lê SOMENTE estes, na ordem)

| # | Path | Layer | Obrigatório? |
|---|------|-------|--------------|
| 1 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md | L0 | sim |
| 2 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md | L1 | sim |
| 3 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/<NN>_<slug>/CONTEXT.md | L2 | sim |
| 4 | <path estágio-específico>                         | L3/L4 | sim/condicional |
| ... | ...                                            | ...   | ... |
```

**Placeholders:** apenas `{{PROJECT_ROOT}}` e `{{WORKSPACE}}` (Jinja-style). Bootstrap resolve. Nunca usar `../../`.

**Marcação `condicional`:** linha cuja obrigatoriedade depende de profile/tier (ex.: `tech_debt.md` só se `tech_debt_tracking: true`). Coluna deve dizer `condicional: <regra>`.

### 4. Seção `Não Lê (negative constraint)`

Lista negativa explícita. Agente recusa ler diretórios/arquivos fora da Inputs e fora da pista declarada aqui.

```markdown
## Não Lê (negative constraint)

- {{PROJECT_ROOT}}/src/, {{PROJECT_ROOT}}/tests/   (exceções: <listadas>)
- ADRs não listados no plan.md desta wave
- Outputs de outros estágios além dos declarados em Inputs
- {{PROJECT_ROOT}}/docs/lessons.md (lições já vêm pré-injetadas pelo lead, se aplicável)
```

### 5. Read order

Numerado, preserva ordem da Inputs. Reforça Layer Loading Protocol.

```markdown
## Read order

1. L0 — identidade
2. L1 — state machine
3. L2 (este arquivo) — instruções do estágio
4..N. Demais paths da Inputs, na ordem da tabela
```

### 6. Process

Passos do estágio em formato numerado. Cada passo pequeno e verificável. Inclui:

- Verificação pre-flight (existência dos paths Inputs).
- Skill superpowers a invocar (ver §11).
- Decisões que disparam stop point.
- Ponto onde sub_stage transita para `<NN>_completed`.
- Atualização de L1 + commit atômico.

### 7. Outputs esperados

Paths **relativos a `stages/<NN>/output/`**. Igual ao campo `output_files` do frontmatter. Cada item descreve conteúdo mínimo (1 frase).

```markdown
## Outputs

- `output/<file>.md` — <descrição mínima do conteúdo>
- `output/reports/<...>` (se aplicável)
```

### 8. Sub_stage transitions

Lista enums válidos do estágio (puxados de `state-machine-schema.md`) + regra textual da transição IN_PROGRESS → COMPLETED.

```markdown
## Sub_stage transitions

Enum válido: <lista de sub_stage_enum do frontmatter>

Transição IN_PROGRESS → COMPLETED dispara quando:
- Todos os outputs declarados em §Outputs existem no FS.
- Verify (§6 Process passo X) passou.
- Humano aprovou (gate de §12) — quando aplicável.
```

Estágio 04 documenta sub_stages dinâmicos `04_wave_<N>_in_progress` / `04_wave_<N>_completed`. Estágio 08 documenta os 4 terminais `08_decided_A/B/C` além de `08_in_progress`.

### 9. Status que pode setar

Subset dos 5 canônicos de `references/state-machine-schema.md`.

```markdown
## Status canônicos disponíveis neste estágio

- `IN_PROGRESS` — trabalho ativo.
- `COMPLETED_AWAITING_HUMAN` — outputs prontos, aguarda gate humano.
- `BLOCKED_STOP_POINT` — menu A/B/C disparado (ver §10).
- `BLOCKED_ERROR` — runtime/CI/merge falhou.
- `COMPLETED` — APENAS estágio 07 (saída) ou 08 saída A.
```

Estágios 00–06 nunca setam `COMPLETED` (terminal de workspace). Estágios 03 e 06 podem omitir `BLOCKED_ERROR` se profile pula.

### 10. Stop points aplicáveis

Referência canônica a `references/stop-points-canonical.md` (escrito em paralelo). Lista IDs aplicáveis ao estágio.

```markdown
## Stop points aplicáveis

Catálogo canônico em `references/stop-points-canonical.md`. IDs disparáveis aqui:

- `sp_<id>` — <1 linha do que dispara>
- ...

Disparo: agente pausa, escreve menu A/B/C no output, atualiza L1 `status: BLOCKED_STOP_POINT`. Humano responde, sessão retoma com `IN_PROGRESS`.
```

Catálogo canônico em `references/stop-points-canonical.md` define os 12 IDs e thresholds por tier. L2 do estágio cita SOMENTE IDs canônicos. Mapeamento autoritativo:

| Estágio | Stop points aplicáveis (IDs canônicos) |
|---|---|
| 00 recon | `workspace_corrupt`, `profile_mismatch` |
| 01 discovery | `stack`, `external_api`, `paid_service`, `pii` |
| 02 design | `stack`, `db`, `new_dep`, `paid_service`, `irreversible`, `over_eng`, `pii`, `adr_drift` |
| 03 wave_planner | (nenhum — wave-planner é determinístico) |
| 04 implementation_waves | `new_dep`, `irreversible`, `over_eng`, `prod_migration`, `adr_drift` |
| 05 verification | (nenhum — falha CI é `BLOCKED_ERROR`, não stop point) |
| 06 review | `over_eng`, `pii`, `adr_drift` |
| 07 merge | `irreversible`, `prod_migration` |
| 08 feedback_intake | (nenhum — saídas A/B/C são decisão direta) |

### 11. Skill superpowers de referência

Aponta o sumário 200tok a consultar. Path absoluto via placeholder; arquivos serão criados na Wave 5 da skill — paths são contratos.

```markdown
## Skill superpowers de referência

Sumário 200tok: `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/<X>-200tok.md`

Skill formal: `superpowers:<nome>` (escape hatch — invocação real só se complexidade justifica).
```

#### Mapeamento estágio ↔ skill superpowers

| Estágio | Skill superpowers principal | Sumário 200tok |
|---|---|---|
| 00 recon | `brainstorming` + `writing-plans` (light) | `brainstorming-200tok.md` |
| 01 discovery | `brainstorming` | `brainstorming-200tok.md` |
| 02 design | `writing-plans` | `writing-plans-200tok.md` |
| 03 wave_planner | `dispatching-parallel-agents` | `dispatching-parallel-agents-200tok.md` |
| 04 implementation_waves | `test-driven-development` + `subagent-driven-development` | `test-driven-development-200tok.md`, `subagent-driven-development-200tok.md` |
| 05 verification | `verification-before-completion` | `verification-before-completion-200tok.md` |
| 06 review | `requesting-code-review` + `receiving-code-review` | `requesting-code-review-200tok.md` |
| 07 merge | `finishing-a-development-branch` | `finishing-a-development-branch-200tok.md` |
| 08 feedback_intake | (nenhuma direta) | usa `references/feedback-intake-fase08.md` local |

### 12. Gates

Declara explicitamente quem libera o estágio.

```markdown
## Gates

- **Humano:** <quando exige aprovação humana ou edição de output>
- **Automático (CI):** <linters, testes, hooks que precisam estar verdes>
- **Aprovação para transitar:** <regra exata para sub_stage IN_PROGRESS → COMPLETED>
```

Estágio 04 referencia gate composto: peer review subagent + wave-reviewer + merge verde.

---

## Sub_stage enum por estágio (canônico)

Réplica de `references/state-machine-schema.md` §Sub-stage enum. Frontmatter de cada L2 deve bater **exatamente** com a coluna correspondente.

| Estágio | Valores válidos |
|---|---|
| 00 Recon | `00_in_progress`, `00_completed` |
| 01 Discovery | `01_in_progress`, `01_completed` |
| 02 Design | `02_in_progress`, `02_completed` |
| 03 Wave Planner | `03_in_progress`, `03_completed` |
| 04 Implementation Waves | `04_wave_<N>_in_progress`, `04_wave_<N>_completed` (N inteiro positivo) |
| 05 Verification | `05_in_progress`, `05_completed` |
| 06 Review | `06_in_progress`, `06_completed` |
| 07 Merge | `07_in_progress`, `07_completed` |
| 08 Feedback Intake | `08_in_progress`, `08_decided_A`, `08_decided_B`, `08_decided_C` |

**Regra de prefixo:** `sub_stage` SEMPRE começa com prefixo `<stage>_`. Mismatch dispara Recovery Wizard inconsistência (ver `references/state-machine-schema.md` §R2.7).

---

## Estágios pulados por profile

Fonte: `templates/_config/profile-matrix.md`. Skill resolve `stages_skipped` no merge profile + tier + override e materializa SOMENTE os L2s não-pulados.

| Profile | `stages_skipped` |
|---|---|
| `experiment` | `["03", "05", "06", "08"]` (todos os tiers) |
| `technical_article` | `["03"]` (todos os tiers) |
| Demais 8 profiles | `[]` |

Override local em `.icm-profile.local.yaml` pode adicionar/remover (sujeito a `confirm_unsafe` para gates críticos). L1 declara `stages_skipped` final no `_config/profile-effective.yaml`; bootstrap NÃO cria pastas dos estágios pulados.

**Quando estágio é pulado:** L1 não pula transições — `next_stage` do L2 anterior aponta direto ao próximo estágio NÃO-pulado. Ex: em `experiment`, `next_stage` do estágio 02 design é `04` (pula 03).

---

## Validação automatizada (Round 2)

`tests/unit/test_l2_templates.py` parseia cada `templates/workspace/stages/<NN>_<slug>/CONTEXT.md.tpl` e valida:

1. **Frontmatter parseável** (PyYAML strict load) e contém os 7 campos obrigatórios.
2. **`sub_stage_enum`** bate exatamente com `references/state-machine-schema.md` §Sub-stage enum (exceção: estágio 04 valida regex `^04_wave_<int>_(in_progress|completed)$`).
3. **Placeholders Jinja**: somente `{{PROJECT_ROOT}}` e `{{WORKSPACE}}`. Qualquer outro placeholder (`{{...}}`) → falha. Verifica que ambos são substituíveis (re.findall encontra ≥1 ocorrência cada — exceto estágio 00 que pode não usar `WORKSPACE` em paths além dos default L0/L1/L2).
4. **Tabela Inputs presente** com cabeçalho exato `## Inputs (lê SOMENTE estes, na ordem)` e ≥3 linhas de dados (L0, L1, L2 mínimo) — parser conta linhas de tabela após o cabeçalho.
5. **Seção `## Não Lê (negative constraint)`** presente com ≥1 item.
6. **`output_files` do frontmatter** bate com paths citados na seção `## Outputs` (set equality).
7. **`applicable_stop_points`** ⊆ IDs declarados em `references/stop-points-canonical.md` (carrega catálogo, faz `issubset`).
8. **`next_stage`** ∈ {`"00".."08"`, `null`}; null exclusivo do estágio 08.
9. **Skill 200tok path** referenciado em §11 existe como string (arquivo real só na Wave 5 — teste só checa formato do path).

Falha em qualquer item → CI bloqueia merge da wave.

---

## Exemplo concreto — L2 estágio 02 design (placeholders resolvidos)

Workspace fictício: `042-feat-auth`, `project_root=/repo/aura-luz-api`, profile `app_web_backend`, tier `development`.

```markdown
---
layer: L2
stage: "02"
stage_name: "design"
sub_stage_enum:
  - "02_in_progress"
  - "02_completed"
applicable_stop_points:
  - "stack"
  - "db"
  - "new_dep"
  - "paid_service"
  - "irreversible"
  - "over_eng"
  - "pii"
  - "adr_drift"
output_files:
  - "output/plan.md"
  - "output/decisions.md"
next_stage: "03"
---

# Estágio 02 — design (L2)

Produz plano arquitetural executável + ADRs formais. Cada decisão não-trivial vira menu A/B/C. Saída alimenta o Wave Planner (estágio 03) com tasks contendo 4-block contract, files touched e ADRs aplicáveis.

## Inputs (lê SOMENTE estes, na ordem)

| # | Path | Layer | Obrigatório? |
|---|------|-------|--------------|
| 1 | /repo/aura-luz-api/workspaces/042-feat-auth/CLAUDE.md | L0 | sim |
| 2 | /repo/aura-luz-api/workspaces/042-feat-auth/CONTEXT.md | L1 | sim |
| 3 | /repo/aura-luz-api/workspaces/042-feat-auth/stages/02_design/CONTEXT.md | L2 | sim |
| 4 | /repo/aura-luz-api/workspaces/042-feat-auth/stages/01_discovery/output/discovery.md | L4 | sim |
| 5 | /repo/aura-luz-api/workspaces/042-feat-auth/stages/00_recon/output/baseline.md | L4 | sim |
| 6 | /repo/aura-luz-api/docs/decisions/ | L3 | condicional: ler ADRs já existentes referenciados em discovery.md |
| 7 | /repo/aura-luz-api/docs/tech_debt.md | L3 | condicional: tier ≠ experimental |
| 8 | /repo/aura-luz-api/workspaces/042-feat-auth/_config/xp-conventions.md | L3 | sim |
| 9 | /repo/aura-luz-api/workspaces/042-feat-auth/_config/stop-points.md | L3 | sim |
| 10 | /repo/aura-luz-api/workspaces/042-feat-auth/_references/superpowers-summary/writing-plans-200tok.md | L3 | sim |

## Não Lê (negative constraint)

- /repo/aura-luz-api/src/, /repo/aura-luz-api/tests/
- ADRs em /repo/aura-luz-api/docs/decisions/ NÃO referenciados em discovery.md
- Outputs de estágios 03+ (não existem ainda)
- /repo/aura-luz-api/docs/lessons.md (lead injetará lições relevantes na fase 04)

## Read order

1. L0 — /repo/aura-luz-api/workspaces/042-feat-auth/CLAUDE.md
2. L1 — /repo/aura-luz-api/workspaces/042-feat-auth/CONTEXT.md
3. L2 — este arquivo
4. discovery.md (entrada principal)
5. baseline.md (recon)
6. ADRs listados em discovery
7. tech_debt.md (se tier permitir)
8. xp-conventions.md, stop-points.md, sumário writing-plans

## Process

1. Pre-flight: validar todos os paths Inputs existem; sub_stage `02_in_progress`.
2. Ler em ordem; consultar sumário 200tok writing-plans.
3. Para cada decisão arquitetural não-trivial, montar menu A/B/C com recomendação.
4. Disparar stop point se: mudança de stack, modelagem nova, API pública nova, dependência nova, serviço pago, decisão irreversível, over-engineering detectado.
5. Escrever ADRs formais em /repo/aura-luz-api/docs/decisions/NNNN-<slug>.md (fonte da verdade).
6. Escrever output/plan.md: tasks com 4-block contract (O QUE / COMO / NÃO QUERO / VALIDAÇÃO), files touched, ADRs aplicáveis, requires_peer_review.
7. Escrever output/decisions.md: INDEX (título + slug + status) — não duplica ADR.
8. Verify: cada requisito do MVP do discovery aparece em ≥1 task do plan OU está deferred com justificativa.
9. Atualizar L1: sub_stage `02_completed`, status `COMPLETED_AWAITING_HUMAN`, append history. Commit atômico (pre-commit hook valida).

## Outputs

- `output/plan.md` — plano com tasks 4-block, DAG de dependências, files touched, ADRs aplicáveis por task.
- `output/decisions.md` — INDEX dos ADRs criados (título + slug + status).

## Sub_stage transitions

Enum válido: `02_in_progress`, `02_completed`.

Transição IN_PROGRESS → COMPLETED dispara quando:
- output/plan.md e output/decisions.md existem.
- Cada requisito MVP do discovery está coberto por ≥1 task ou explicitamente deferred.
- ADRs novos commitados em /repo/aura-luz-api/docs/decisions/.
- Humano aprovou via gate (status `COMPLETED_AWAITING_HUMAN` → humano responde).

## Status canônicos disponíveis neste estágio

- `IN_PROGRESS` — escrevendo plano/ADRs.
- `COMPLETED_AWAITING_HUMAN` — outputs prontos, humano revisa.
- `BLOCKED_STOP_POINT` — menu A/B/C aguardando resposta.
- `BLOCKED_ERROR` — pre-commit hook rejeitou ou path Input ausente.

## Stop points aplicáveis

Catálogo canônico em `references/stop-points-canonical.md`. IDs disparáveis no estágio 02 design:

- `stack` — troca de linguagem/framework/runtime vs ADR vigente.
- `db` — engine ou schema design novo.
- `new_dep` — npm/pip/cargo nova no manifesto (license/maintenance/size).
- `paid_service` — SaaS recorrente (calibrado por tier: warning R$50 / hard R$200/500/1000).
- `irreversible` — drop table, migração destrutiva.
- `over_eng` — 3+ camadas de abstração novas sem requisito (warning experimental/tool, hard development/production).
- `pii` — LGPD, dados sensíveis (warning experimental, hard tool/development, hard+DPO production).
- `adr_drift` — proposta diverge de ADR existente sem superseding declarado.

## Skill superpowers de referência

Sumário 200tok: `/repo/aura-luz-api/workspaces/042-feat-auth/_references/superpowers-summary/writing-plans-200tok.md`

Skill formal: `superpowers:writing-plans` (escape hatch).

## Gates

- **Humano:** revisa output/plan.md e ADRs; aprova ou requisita ajustes.
- **Automático (CI):** pre-commit hook valida atomicidade L1↔outputs e prefixo de commit `workspace/042-feat-auth`.
- **Aprovação para transitar:** humano explicitamente aprova (input em sessão); automaticamente vira `02_completed` no próximo commit.
```

---

## Fim do spec
