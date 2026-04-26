# Session Handoff Protocol

> Canonical: **1 stage = 1 sessão**. Cada stage termina com handoff dual (verbal + arquivo persistido) e a sessão atual SAI. Próxima sessão começa fresh — context enxuto, cache miss aceito como custo.

## Por que 1-stage-1-sessão (supersede Q3 batched)

Observação empírica em uso real (beta1/beta2): sessões batched (design 00+01+02 numa só, closing 05+06+07 numa só) cresceram contexto além do alvo de 2-8k tokens por L2. Token spend total cresceu não-linear vs número de sub_stages.

Trade-off resolvido em favor de cache fresh:

| Opção | Token cost | Cache miss | Context pollution |
|---|---|---|---|
| Batched (Q3 v1) | menor (1 cache miss por batch) | 1 por batch | alta — sub_stages se acumulam |
| **1-stage-1-sessão (v2)** | 1 cache miss por stage = 8 misses no fluxo completo, mas cada sessão start ~2-3k tokens | 8 total | mínima — sessão fresh por stage |

User sinalizou que ganho em context fresh supera custo de cache miss. Decisão revisada: **A1 — TODOS stages 00→07 uniforme = 1 sessão cada**.

Stage 04 mantém versão wave-aware: 1 sessão lead por wave (status quo, decisão 2a). Sub-waves não disparam handoff explícito — lead persiste através das sub-waves dentro da mesma sessão.

## Anatomia de uma sessão de stage

```
┌─ INÍCIO ────────────────────────────────────────┐
│  1. Sessão nova abre em <project_root>          │
│  2. Lê L0 + L1 + L2 do stage_atual              │
│  3. Lê _kickoff.md (se gerado pela anterior)    │
│  4. Imprime header session (R4.4)               │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─ TRABALHO ──────────────────────────────────────┐
│  Executa instruções do L2                       │
│  Produz outputs em stages/<NN>/output/          │
│  Handles stop points / errors / gates           │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─ FIM (handoff) ─────────────────────────────────┐
│  1. L1 update: sub_stage=<NN>_completed,        │
│     status=COMPLETED_AWAITING_HUMAN, history    │
│     append, last_transition pra próximo stage   │
│  2. Render _kickoff.md no stage seguinte        │
│  3. Commit atômico (hooks validam)              │
│  4. Imprime KICKOFF block verbal pro user       │
│  5. Sessão SAI                                  │
└─────────────────────────────────────────────────┘
                      │
                      ▼
   ┌── User abre nova sessão Claude ──┐
   │   Cola prompt do KICKOFF block    │
   └───────────────────────────────────┘
                      │
                      ▼
                 (próximo stage)
```

## Schema `_kickoff.md` (L4-kickoff)

Arquivo gerado pela sessão atual no diretório do **próximo** stage:

```
<workspace>/stages/<NN+1>/_kickoff.md
```

Schema YAML frontmatter + corpo:

```markdown
---
layer: L4-kickoff
stage_target: "03"
stage_target_name: "wave_planner"
generated_by: "session ending stage 02"
generated_at: "2026-04-26T14:30:00Z"
generator_commit_sha: "abc123def"
prev_stage: "02"
prev_outputs:
  - path: "stages/02_design/output/plan.md"
    summary: "Plano com 8 tasks, 2 ADRs criados (0001 stack + 0004 auth)"
  - path: "stages/02_design/output/decisions.md"
    summary: "Index L4 dos ADRs"
prev_decisions_summary: |
  - Stack: Python 3.13 + FastAPI + Postgres
  - Auth: JWT com refresh tokens (ADR 0004)
pending_for_this_stage:
  - "Resolver ambiguidade: tasks user-model e user-routes tocam src/users/"
---

# Kickoff — Stage 03 wave_planner (workspace 042-feat-auth)

## Read order (paths absolutos)

1. `<project_root>/workspaces/042-feat-auth/CLAUDE.md`
2. `<project_root>/workspaces/042-feat-auth/CONTEXT.md`
3. `<project_root>/workspaces/042-feat-auth/stages/03_wave_planner/CONTEXT.md`
4. Este arquivo (`stages/03_wave_planner/_kickoff.md`)
5. Inputs declarados pelo L2 do stage 03

## Estado entregue pela sessão anterior

(prev_outputs + prev_decisions_summary do frontmatter renderizados em prosa)

## O que esta sessão deve fazer

(extraído do L2 do stage atual + pending_for_this_stage)
```

**Regra "no orphan files":** `_kickoff.md` é declarado nos `Inputs` do L2 do stage_target. Próxima sessão lê via leitor declarado.

## Handoff verbal (3C dual)

Final da sessão imprime no chat:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Stage 02 (design) COMPLETO — workspace 042-feat-auth

Workspace atualizado em commit abc123de:
  - L1: stage_atual=03, sub_stage=03_in_progress, status=IN_PROGRESS
  - Outputs: stages/02_design/output/plan.md (8 tasks)
              stages/02_design/output/decisions.md (2 ADRs)
  - Kickoff: stages/03_wave_planner/_kickoff.md gerado

🔄 KICKOFF próxima sessão — copy/paste:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Continuar workspace 042-feat-auth no estágio 03 (wave_planner).

Read order:
  workspaces/042-feat-auth/CLAUDE.md
  workspaces/042-feat-auth/CONTEXT.md
  workspaces/042-feat-auth/stages/03_wave_planner/CONTEXT.md
  workspaces/042-feat-auth/stages/03_wave_planner/_kickoff.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Para continuar: encerre esta sessão (Ctrl+D ou /exit) e abra
nova sessão Claude no project_root, depois cole o prompt acima.
```

Verbal + arquivo redundantes intencionais:
- Arquivo: persistente, lido pela próxima sessão automaticamente.
- Verbal: pro user copy-paste, não depender de Claude lembrar de ler kickoff.

## Stage 04 (waves) — exceção

Stage 04 = **1 sessão lead por wave**. Wave 1 termina, lead handoff pra próxima sessão de wave 2 (mesmo stage 04). Sub_stage vai de `04_wave_1_completed` pra `04_wave_2_in_progress`.

Após última wave: handoff normal pra stage 05.

## Stage 07 (merge) → 08 — transição automática

Stage 07 **NÃO é terminal**. Após merge confirmado, sessão transita imediatamente para stage 08 com `status: COMPLETED_AWAITING_HUMAN` e gera `_kickoff.md` em `stages/08_feedback_intake/`. Workspace fica vivo aguardando humano voltar com feedback livre após uso real do projeto (sem prazo).

L1 final do 07:
```
sub_stage = 07_completed → imediatamente → 08_in_progress
stage_atual = 08
status = COMPLETED_AWAITING_HUMAN
```

History append 2 eventos: `stage_transition 07_in_progress→07_completed` + `stage_transition 07_completed→08_in_progress`.

KICKOFF block 07→08 (sem menu A/B/C — sessão 08 inferirá pela intenção do feedback):

```
✅ Stage 07 (merge) COMPLETO — workspace 042-feat-auth

Workspace transitou pra stage 08 (feedback intake) em status
COMPLETED_AWAITING_HUMAN. Workspace fica vivo até você voltar
com feedback após uso real do projeto.

🔄 KICKOFF próxima sessão (DEPOIS de uso real, sem prazo):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Continuar workspace 042-feat-auth no estágio 08 (feedback_intake).

Read order:
  workspaces/042-feat-auth/CLAUDE.md
  workspaces/042-feat-auth/CONTEXT.md
  workspaces/042-feat-auth/stages/08_feedback_intake/CONTEXT.md
  workspaces/042-feat-auth/stages/08_feedback_intake/_kickoff.md

Cole o feedback livre — sessão 08 lê outputs, infere intenção
(bug fix → restart fase X, feature nova → spawn workspace,
tudo OK → close), confirma com você antes de executar.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Stage 08 (feedback intake) — terminal real

Workspace só fecha (`status: COMPLETED`) em uma das 3 saídas do stage 08, decididas pela **inferência de intenção do feedback livre** do humano (sem menu A/B/C explícito). Sessão 08 mapeia heurísticas do feedback → A/B/C, calcula confidence, mini-confirma com humano antes executar.

**Saídas:**

- **A — Close:** workspace `COMPLETED`. Lições registradas em `docs/lessons.md`. Sessão sai SEM gerar kickoff.
  - Sinais inferência: "tudo ok", "encerrar", "sem feedback", silêncio.

- **B — Restart fase X:** L1 `iteration++`, `stage_atual=X`, `sub_stage=X_in_progress`. Mapping bug→stage canônico (testes→05, código→04, design→02, etc.). GERA kickoff pra stage X. Imprime KICKOFF verbal.
  - Sinais inferência: "bug em X", "quebrou Y", "regressão", menção explícita a stage.

- **C — Spawn novo workspace:** L1 `status=COMPLETED`, `spawn_to=<slug-novo>`. Imprime instrução pro user invocar `/xp-icm-workflow project-root=<X> spawn_from=<NNN>` em sessão nova. NÃO gera kickoff (workspace novo = outro).
  - Sinais inferência: "pivotar", "novo projeto", "feature grande nova", mudança de profile/tier.

Heurísticas detalhadas no L2 do stage 08 (`stages/08_feedback_intake/CONTEXT.md` seção "Inferência de intenção"). Confidence < 0.6 → sessão pergunta clarificação curta antes inferir.

Mini-confirm template (1 menu único):

```
Entendi: <saída inferida em prosa, 1-2 frases>

[s] confirma e executa
[n] cancela, pergunta de novo
[edit] descreva o ajuste
```

L1 status final = `COMPLETED`. Branch workspace pode ser arquivada (vide R3.4).

## Stage 08 disparo

User volta abrindo nova sessão (cole prompt do KICKOFF block do stage 07). Não há comando especial — o protocolo "1 stage = 1 sessão" trata stage 08 igual aos outros, exceto que **a entrada é feedback livre** em vez de seguir L2 num fluxo determinístico.

Tempo entre 07→08: indefinido. Workspace fica em `COMPLETED_AWAITING_HUMAN` enquanto user usa o projeto na vida real.

## Anti-patterns

### Continuar stage além do escopo declarado

Sessão atual NÃO deve avançar pra próximo sub_stage / stage além do declarado. Mesmo que pareça "rápido fazer tudo numa só vez" — o ponto da regra é tokens enxutos. Se sentir tentação de avançar: pare, faça handoff, abra sessão nova.

### Pular handoff por "ser óbvio"

Stage trivial (ex: 01 discovery curto) ainda DEVE seguir protocolo. Senão handoff vira opcional e usuários esquecem em stages reais. Uniformidade > eficiência marginal.

### Kickoff verbal sem arquivo

Apenas imprimir verbal sem gerar `_kickoff.md` quebra rastreabilidade. Próxima sessão precisa do arquivo pra:
- Entender o que foi entregue (`prev_outputs`)
- Pendências marcadas pelo handoff (`pending_for_this_stage`)
- Read order absoluta (paths podem mudar entre sessões)

### Migrar workspaces beta1/beta2

Decisão **4B**: sem migração forçada. Workspaces criados antes do beta3 continuam em batched mode. Não tente converter — risk de quebrar atomicidade L1↔outputs. Esses workspaces terminam no batched original.

## Atomicidade do commit de handoff

Ao final do stage, commit DEVE incluir simultaneamente:

1. Outputs do stage atual (`stages/<NN>/output/*`)
2. L1 atualizado (`workspaces/<NNN>/CONTEXT.md`)
3. `_kickoff.md` do próximo stage (`stages/<NN+1>/_kickoff.md`)

Pre-commit hook valida atomicidade outputs↔L1 (já existe). Hook **NÃO** valida `_kickoff.md` automaticamente — convenção depende da sessão. Mas hook aceita kickoff porque está dentro de `workspaces/NNN/stages/`.

Mensagem do commit (regulada pelo commit-msg hook):

```
workspace 042: stage 02 completo + kickoff stage 03
```

## Validação

Pre-flight check da próxima sessão:

1. Lê L0 + L1.
2. Confirma `last_transition.to == "<NN+1>_in_progress"`.
3. Lê `stages/<NN+1>/_kickoff.md` se existir; warning se ausente (pode ter sido geração v1 ou bug — recovery wizard pode prepender entrada audit).
4. Continua com L2 do stage atual.

`scripts/handoff.py` (Wave 2/3 fix) implementa render + validação. Tests em `tests/unit/test_handoff.py`.
