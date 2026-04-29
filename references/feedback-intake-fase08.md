# Feedback Intake — Fase 08

> **Versão:** v3.0.0-beta5 · Define a fase 08 (feedback intake universal). Disparo manual humano após uso real do output do workspace. Três saídas: A close, B restart fase X, C spawn novo workspace.

---

## Propósito

Fase 08 é o **gate de iteração universal** do ciclo ICM. Não é monitoring, não é cron, não é Grafana. É uma sessão deliberada que o humano dispara quando já usou o output do workspace por tempo suficiente pra ter dados (logs, dor real, lição) e quer decidir: fechar, refazer um pedaço, ou escalar pra novo workspace.

Resolução do plan: Q12 (universal todos tiers), H1 (saída B só fases 01-07), H2 (saída C UX cola comando em sessão nova).

---

## Quando rodar fase 08

- **Sempre opcional, nunca automático.** Humano dispara explicitamente após uso real do output do workspace — semanas, meses depois do `COMPLETED` da fase 07.
- **Universal.** Qualquer tier (`experimental` → `production`). O plan dropou a restrição "só production". A diferença por tier é só calibração interna (peso de cada saída, profundidade da análise de logs).
- **Não-cron, não-agendada.** Disparo: humano abre nova sessão Claude Code no project_root e diz "rodar fase 08 do workspace 042".

### Estágios pulados por profile

A `profile-matrix.md` declara `stages_skipped` por profile. `experiment` lista `"08"` (e tipicamente `"03"`, `"05"`, `"06"`). Outros profiles rodam 08 quando humano dispara.

---

## Pré-condição

Workspace deve estar em `status: COMPLETED_AWAITING_HUMAN` (fase 07 já concluída, aguardando humano) ou `status: COMPLETED` (fase 08 anterior decidiu A/C e workspace reaberto).

Se status indefinido ou inconsistente → Stop point 11 (`workspace_corrupt`) → Recovery Wizard.

Se status ∈ {`IN_PROGRESS`, `BLOCKED_*`} → sessão recusa fase 08 com mensagem: "workspace ainda não foi concluído (fase 07). Termine o ciclo principal antes de rodar feedback intake."

Se status = `COMPLETED_AWAITING_HUMAN` → válido, prosseguir (transição automática de 07).

---

## O que a sessão fase 08 faz

### Pre-flight

Lê:

- L0 (`<workspace>/CLAUDE.md`) — paths absolutos, profile, tier, `logs_root`.
- L1 (`<workspace>/CONTEXT.md`) — confirma `status: COMPLETED`, lê `iteration` atual e `history`.
- L2 (`<workspace>/stages/08_feedback_intake/CONTEXT.md`) — instruções específicas do estágio.
- Outputs anteriores: `stages/01..07/output/*` — sample-check de existência (audit).

Validações automáticas:

1. `status == "COMPLETED"`.
2. Outputs 01-07 existem (sample-check de pelo menos 1 arquivo por estágio que rodou — respeitando `stages_skipped` do profile).
3. `sub_stage` atual ∈ {`08_in_progress`, `08_decided_A`, `08_decided_B`, `08_decided_C`} ou ausente (primeiro disparo).

Falha em qualquer validação → abort com mensagem específica + ação proposta.

### Coleta de inputs

**1. Logs do sistema** (se `logs_root` declarado em L0 e diferente de `null`)

Sample dos últimos 30 dias de `<logs_root>`. Se `logs_root: null` (greenfield/texto/skill), pula esta etapa. Se path não existe ou está vazio, anota "logs vazios/inacessíveis" no report e segue.

**2. Feedback humano estruturado**

Sessão pergunta humano em formato 4-block:

```
## O QUE FUNCIONOU

(o que entregou valor de verdade)

## O QUE NÃO FUNCIONOU

(o que falhou, atritou, desperdiçou tempo)

## QUAL DOR PERSISTE

(o que ainda dói após este workspace)

## QUE LIÇÃO TIRAR

(insight pra capturar em docs/lessons.md)
```

Humano responde inline na sessão. Sessão valida que cada bloco tem ao menos 1 frase substantiva (não vazio nem placeholder).

**3. Análise top-N error patterns**

Agrupa logs + feedback em **≤5 padrões** com `frequencia` (count ou estimativa) + `impacto` (low/medium/high/critical) + `evidencia` (linhas log ou trecho do feedback). Se logs vazios e feedback curto, pode haver 0-2 padrões; aceita.

### Output

Sessão escreve `<workspace>/stages/08_feedback_intake/output/intake-report.md`:

```markdown
# Intake Report — Workspace NNN, iteration M

## Logs sample
(últimos 30 dias de <logs_root>, ou "n/a" se null)

## Feedback humano
### O QUE FUNCIONOU
...
### O QUE NÃO FUNCIONOU
...
### QUAL DOR PERSISTE
...
### QUE LIÇÃO TIRAR
...

## Top-N patterns
| # | Padrao | Frequencia | Impacto | Evidencia |
|---|---|---|---|---|
| 1 | ... | ... | ... | ... |

## Recomendacao
Saida sugerida: A | B (fase X) | C
Justificativa: ...
```

Pre-commit hook valida prefixo de commit `intake:` ou `feedback:`.

---

## As 3 saídas A/B/C

Após `intake-report.md` escrito, sessão dispara menu A/B/C com a recomendação destacada. Humano escolhe (pode discordar da recomendação). Sessão executa transição correspondente.

### Saída A — Close workspace

**Quando:** ferramenta funciona, lições já capturadas, sem ação adicional.

**Sessão executa:**

1. Append em `history`: `event: stage_transition`, `from: 08_in_progress`, `to: 08_decided_A`, `note: "<motivo curto>"`, `at: <ISO>`, `commit_sha: <a preencher pós-commit>`.
2. Set `sub_stage: 08_decided_A`.
3. Set `status: COMPLETED`.
4. Append lições novas (extraídas do bloco "QUE LIÇÃO TIRAR" do intake-report) em `<project_root>/docs/lessons.md` respeitando frontmatter strict (id, date, tags, severity).
5. Commit atômico (pre-commit hook valida atomicidade L1↔outputs↔lessons).
6. Mensagem humano: "Workspace NNN fechado. M lições adicionadas em docs/lessons.md."

**Exemplo concreto — saída A:**

Mensagem ao humano:
```
Workspace 042 fechado com decisao A (close).

3 licoes adicionadas em docs/lessons.md:
  #017 critical — race em rebase de wave grande
  #018 medium — peer review on-demand pegou bug em path critico
  #019 low — wave-reviewer com 1 task adiciona ruido (skip futuro)

Sub_stage final: 08_decided_A. Status: COMPLETED.
```

Diff YAML em L1:
```yaml
# antes
sub_stage: "07_completed"
status: "COMPLETED"
last_action: "fase 07 merged em main, CI green"

# depois
sub_stage: "08_decided_A"
status: "COMPLETED"
last_action: "fase 08 saida A — close workspace"
last_action_at: "2026-04-25T16:00:00Z"
next_action: "n/a — workspace arquivado"
last_transition:
  from: "08_in_progress"
  to: "08_decided_A"
  at: "2026-04-25T16:00:00Z"
  commit_sha: "f1e2d3c4b5a6"
history:
  # ... entradas anteriores preservadas
  - at: "2026-04-25T15:30:00Z"
    event: "stage_transition"
    from: "07_completed"
    to: "08_in_progress"
    commit_sha: "a1b2c3d4"
  - at: "2026-04-25T16:00:00Z"
    event: "stage_transition"
    from: "08_in_progress"
    to: "08_decided_A"
    commit_sha: "f1e2d3c4b5a6"
    note: "ferramenta funciona, 3 licoes capturadas"
```

---

### Saída B — Restart fase X (iteration++)

**Quando:** descoberta nova exige redesenho parcial. Workspace volta a fase X com lições do intake aplicadas.

**Constraint H1:** X ∈ {`01`, `02`, `03`, `04`, `05`, `06`, `07`}. Restart NÃO permitido para:

- `00` (recon — pra mudar `project_root` ou tipo do projeto, use saída C).
- `08` (atual — não faz sentido restart no próprio gate).

Validação no L2 da fase 08: humano que escolher B precisa declarar X válido; sessão recusa X ∉ {01..07}.

**Sessão executa:**

1. Append em `history`: `event: iteration_increment`, `from: 08_in_progress`, `to: <XX>_in_progress`, `iteration_new: <N+1>`, `note: "restart phase X — <motivo>"`, `at: <ISO>`.
2. Move outputs antigos: `stages/<XX>/output/` → `stages/<XX>/output-iteration-<N>/` (N = iteration ANTES do incremento). Outputs preservados pra audit. Schema interno idêntico ao `output/`.
3. Set `iteration: N+1`.
4. Set `stage_atual: <XX>`.
5. Set `sub_stage: <XX>_in_progress`.
6. Set `status: IN_PROGRESS` (sai de `COMPLETED`).
7. Set `last_action: "restart fase <XX> iteration N+1"`.
8. Set `next_action: "rodar fase <XX> com licoes do intake-report"`.
9. Commit atômico.
10. Mensagem humano: instrução pra abrir nova sessão.
11. Sessão sai. Próxima sessão lê L1 e retoma fase XX naturalmente.

**Exemplo concreto — saída B (restart fase 03):**

Mensagem ao humano:
```
Workspace 042 voltou a fase 03 (wave planner), iteration 2.

Outputs antigos preservados em:
  stages/03/output-iteration-1/
  (wave-plan.md, ambiguities-resolved.md, llm_review_findings.md)

Outputs novos da iteration 2 vao em stages/03/output/ (limpo).

Abra nova sessao no project_root para retomar.
A sessao vai ler L1, ver stage_atual=03 + iteration=2,
e pegar as licoes do intake-report ao construir novo wave-plan.
```

Diff YAML em L1:
```yaml
# antes
stage_atual: "08"
sub_stage: "08_in_progress"
status: "COMPLETED"
iteration: 1

# depois
stage_atual: "03"
sub_stage: "03_in_progress"
status: "IN_PROGRESS"
iteration: 2
last_action: "restart fase 03 iteration 2"
last_action_at: "2026-04-25T16:00:00Z"
next_action: "rodar fase 03 com licoes do intake-report (wave 1 teve race em rebase, redesenhar DAG)"
last_transition:
  from: "08_in_progress"
  to: "03_in_progress"
  at: "2026-04-25T16:00:00Z"
  commit_sha: "9a8b7c6d5e4f"
history:
  # ... entradas anteriores preservadas
  - at: "2026-04-25T16:00:00Z"
    event: "iteration_increment"
    from: "08_in_progress"
    to: "03_in_progress"
    iteration_new: 2
    note: "restart phase 03 — DAG da wave 1 causou race em rebase, redesenhar"
    commit_sha: "9a8b7c6d5e4f"
```

Filesystem move:
```
stages/03/output/wave-plan.md            → stages/03/output-iteration-1/wave-plan.md
stages/03/output/ambiguities-resolved.md → stages/03/output-iteration-1/ambiguities-resolved.md
stages/03/output/llm_review_findings.md  → stages/03/output-iteration-1/llm_review_findings.md
stages/03/output/                        → (vazio, pronto pra iteration 2)
```

---

### Saída C — Spawn novo workspace (herda lessons + ADRs)

**Quando:** feedback indica precisar de novo escopo (reescrita maior, evolução com escopo distinto, ou troca de `project_root`). Workspace 042 segue fechado; cria 043 herdando contexto.

**UX H2:** sessão fase 08 NÃO bootstrappa o 043 automaticamente. Humano abre nova sessão e cola o comando explícito. Isso preserva a separação "skill é parteira one-shot, sai".

**Sessão executa:**

1. Append em `history`: `event: stage_transition`, `from: 08_in_progress`, `to: 08_decided_C`, `spawn_to: <slug-novo>`, `note: "spawn novo workspace — <motivo>"`, `at: <ISO>`.
2. Set `sub_stage: 08_decided_C`.
3. Set `status: COMPLETED`.
4. Set `spawn_to: <slug-novo-workspace>` (humano sugere durante a sessão; default `043-<slug>` baseado em escopo do feedback).
5. Commit atômico.
6. Mensagem humano explícita com comando pra colar em nova sessão.

**Bootstrap do 043 (acontece em sessão SEPARADA, não nesta):**

- Lê `<project_root>/workspaces/042/CONTEXT.md` via `spawn_from=042` arg.
- Herda `profile_base`, `tier`, `project_root` (humano confirma cada um — pode mudar).
- L1 do 043 recebe `spawn_from: 042`.
- recon-report inicial do 043 inclui seção "Herdado de 042: ADRs aplicáveis, lições críticas, escopo motivador do spawn".
- L1 do 042 já tinha `spawn_to: 043` set; agora é referência cruzada confirmada.

**Exemplo concreto — saída C:**

Mensagem ao humano:
```
Workspace 042 fechado com decisao SPAWN.

L1 do 042 atualizado: spawn_to=043-feat-auth-v2, status=COMPLETED.

Para criar 043 herdando contexto:

  1. Abra nova sessao Claude Code no mesmo project_root:
     C:/Users/guicr/projects/aura-luz-api

  2. Cole o comando:
     /xp-icm-workflow project-root=C:/Users/guicr/projects/aura-luz-api spawn_from=042

  3. Bootstrap vai:
     - Ler CONTEXT.md de 042
     - Propor profile=app_web_backend e tier=development (do 042); voce confirma
     - Criar 043 com spawn_from=042 em recon-report
     - Listar ADRs herdados (0001-stack, 0003-auth-strategy) pra voce confirmar quais aplicam
     - Listar licoes critical de 042 pra contexto inicial

Esta sessao termina aqui.
```

Diff YAML em L1:
```yaml
# antes
sub_stage: "08_in_progress"
status: "COMPLETED"
last_action: "fase 08 coletou feedback + intake-report escrito"

# depois
sub_stage: "08_decided_C"
status: "COMPLETED"
spawn_to: "043-feat-auth-v2"
last_action: "fase 08 saida C — spawn novo workspace 043"
last_action_at: "2026-04-25T16:00:00Z"
next_action: "humano abre nova sessao + /xp-icm-workflow spawn_from=042"
last_transition:
  from: "08_in_progress"
  to: "08_decided_C"
  at: "2026-04-25T16:00:00Z"
  commit_sha: "5e4d3c2b1a09"
history:
  # ... entradas anteriores preservadas
  - at: "2026-04-25T16:00:00Z"
    event: "stage_transition"
    from: "08_in_progress"
    to: "08_decided_C"
    commit_sha: "5e4d3c2b1a09"
    spawn_to: "043-feat-auth-v2"
    note: "spawn novo workspace — auth precisa OAuth2 PKCE, escopo nao cabe em restart"
```

---

## Sub_stage enum fase 08 (recap state-machine-schema.md)

| Sub_stage | Significado | Status correspondente |
|---|---|---|
| `08_in_progress` | sessão coletando logs + feedback + escrevendo intake-report | `IN_PROGRESS` |
| `08_decided_A` | humano escolheu A (close) | `COMPLETED` |
| `08_decided_B` | humano escolheu B (restart fase X) | volta a `IN_PROGRESS` no estágio X |
| `08_decided_C` | humano escolheu C (spawn) | `COMPLETED` + `spawn_to` set |

---

## Outputs preservados de iterations (saída B)

Na saída B, outputs antigos vão pra `stages/<XX>/output-iteration-<N>/` — **não deletados**. Audit trail completo da evolução do workspace.

Schema:
- `output-iteration-<N>/` é diretório.
- Estrutura interna idêntica à `output/` (mesmos nomes de arquivo).
- Nova iteration escreve em `stages/<XX>/output/` limpo.
- Iterations anteriores (`output-iteration-1/`, `output-iteration-2/`, ...) coexistem.

Pre-commit hook valida que `output-iteration-<N>/` é apenas criado em commits com prefixo `intake:` ou `feedback:`.

---

## Constraints

- **Fase 08 NÃO faz código novo.** Apenas analisa + decide + transiciona estado. Qualquer código novo é responsabilidade de iteration nova (saída B) ou novo workspace (saída C).
- **Pre-commit hook valida transição** como qualquer outra (atomicidade L1 ↔ outputs/lessons, prefixo `feedback:` ou `intake:`).
- **Stop points raros mas possíveis:** item 11 `workspace_corrupt` se `intake-report.md` não escreve (disco cheio, permissão), ou se humano interrompe a sessão antes de decidir A/B/C (status fica `IN_PROGRESS` em `08_in_progress`; próxima sessão retoma).
- **Lições novas só em saída A.** Saídas B e C reaproveitam lições naturalmente (B via intake-report do iteration N+1; C via herança em recon-report do 043). Saída A é o único caminho de append explícito em `docs/lessons.md`.

---

## v3.3.0 — Triage classification (precede A/B/C)

ANTES da inferência A/B/C, classificar feedback em **(category, state)**:

| Categoria | Estado | Saída |
|---|---|---|
| bug | ready-for-action | **B** restart fase X |
| enhancement | ready-for-action | **C** spawn novo workspace |
| enhancement | wontfix | **A** close + append `_out-of-scope/` |
| qualquer | needs-info | pausa (status=COMPLETED_AWAITING_HUMAN) |
| nada | tudo OK | **A** close |

Cada item classificado como B ou C **gera AGENT-BRIEF** (formato:
`agent-brief-template.md`) que vira input para próxima sessão / spawn.

Enhancement rejeitado (wontfix) registra em
`<workspace>/_out-of-scope/<conceito>.md` (formato: `out-of-scope-kb.md`).

CLAUDE.md root atualizado por handoff.py em todas as 3 saídas (ver
`session-handoff-protocol.md` §"Saídas A/B/C e CLAUDE.md root").

Doc canônico: `references/triage-state-machine.md`.
