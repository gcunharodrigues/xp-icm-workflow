# Lead Resolution Protocol — Canonical (v3.9.0)

> **Versão:** v3.9.0
> **Skill:** `xp-icm-workflow`
> **Estágio consumidor:** `04_implementation_waves` (step 9 — lead-resolution tier)
> **Propósito:** documento canônico do lead-resolution tier — 3 buckets (B1 REWRITE_SPEC, B3 DIRECT_IMPL, B4 VOID_TASK) acionados quando per-task loop esgota cap (3 retries) OR convergence trip OR catastrophic detected. Lead = último recurso "muito ruim".

## Resumo (1 parágrafo)

Per-task loop padrão (writer subagente → L2 forensic+ → L3 critic → diagnose) tem cap 3 retries. Quando esgota OR converge sem fix OR catastrophic detected, controle escala ao **lead da wave**. Lead lê `output/wave-N/task-<slug>-diagnose.md` (renderizado por `scripts/lead-diagnose.py`) que recomenda bucket. Lead pode override. 3 buckets disponíveis: **B1 REWRITE_SPEC** (lead reescreve task spec mais rigorosa, 1 final spawn writer), **B3 DIRECT_IMPL** (lead escreve código direto — passa L2+L3 igual), **B4 VOID_TASK** (declara task void com rationale + plan update + wave-plan recalculate). 1 attempt por bucket. Falha → `BLOCKED_ERROR`.

## Trigger conditions

Per-task loop entra em lead-resolution tier quando **qualquer** das 3 condições ativa:

| # | Condição | Detecção | Bucket hint diagnose |
|---|----------|----------|----------------------|
| T1 | Cap 3 retries esgotado | `task_attempts >= 3` and último critic = REJECT | B1 (default) |
| T2 | Convergence trip | Jaccard(concerns_round_N, concerns_round_N-1) ≥ 0.7 (BLOCKING+MAJOR set) | B1 (spec ambígua) ou B3 (override) |
| T3 | Catastrophic detected | `lead-diagnose.py` pre-check: tests broken outside scope OR build globally broken OR scope creep > 5× OR repo CI red | B3 (default), B4 (override) |

Detecção é deterministic em `scripts/lead-diagnose.py`. Lead **não** decide trigger — script renderiza diagnose.md com condition + hint, lead apenas escolhe bucket (aceita hint OR override).

## Buckets

### B1 — REWRITE_SPEC

**Acionamento:** spec original ambígua/insuficiente; loop converge porque writer não tem âncora clara.

**Lead action:**
1. Lê critic concerns (triplets) acumulados nos rounds 1-3 da task.
2. Identifica padrão: critério de aceite ambíguo? ADR conflict não declarado? Edge case implícito?
3. Reescreve task no plan.md com:
   - VALIDAÇÃO bullets mais específicos (test names obrigatórios)
   - NÃO QUERO bullets adicionais cobrindo armadilhas observadas
   - COMO bullets prescritivos (path/lib/pattern obrigatório)
   - `Estimated lines` recalibrado se foi underestimate
4. Commit plan update na branch da wave.
5. Spawn 1 final writer com novo brief (mesmo modelo do round 3 OR upgrade ceiling se tier permite).
6. Output passa L2 forensic+ + L3 critic igual a writer normal. APPROVE → merge. REJECT → escalate B4 (sem retry adicional).

**Não fazer:**
- Lead **não** escreve código em B1.
- Lead **não** dá hints inline ao writer (anti-sycophancy preservado).

### B3 — DIRECT_IMPL

**Acionamento:** lead avalia que writer não vai convergir mesmo com spec melhor (catastrophic OR multi-arquivo coordenação fina OR algoritmo subtle); ou T3 trigger.

**Lead action:**
1. Lê critic concerns + diagnose.md.
2. Lead escreve código direto (mesmo cycle TDD vertical: tracer-first → 1 test → 1 impl → repeat).
3. Output **NÃO é auto-aprovado** — passa L2 forensic+ + L3 critic igual.
4. APPROVE → merge. REJECT → escalate B4.

**Constraints:**
- Lead opera sob mesmo `pick-model.py` ceiling do tier (não pode rodar Opus em tier=experimental).
- Lead commit em branch dedicada `wave-<NNN>-<N>/<slug>-lead-resolved` (sufixo `-lead-resolved` distingue audit).
- L1 frontmatter ganha `last_action: "wave_<N> task_<slug> bucket_B3 in_progress"`.

### B4 — VOID_TASK

**Acionamento:** task é unmergeable (B1+B3 falharam OR catastrophic + ADR conflict real OR scope inválido descoberto durante implementation).

**Lead action:**
1. Lê critic concerns + diagnose.md.
2. Identifica rationale concreto (citar ADR conflict OR scope mismatch OR upstream blocker).
3. Reescreve task no plan.md com bloco novo:

```markdown
### VOIDED — wave <N> attempt <date>
- Reason: <ADR conflict | scope invalid | upstream blocker | other>
- Evidence: <file:line OR critic concern OR external constraint>
- Action proposed: <new task slug OR defer to v.NEXT OR remove from scope>
```

4. Commit plan update.
5. Trigger `wave-planner-script.py --recalculate` para re-derivar DAG sem task voided.
6. Wave continua com tasks restantes.
7. L1 history append: `event: task_voided, slug: <slug>, bucket: B4, reason: <text>`.

## Cap por bucket

**Hard cap: 1 attempt per bucket per task.**

| Sequence | Behavior |
|----------|----------|
| B1 fail | escalate B3 |
| B3 fail | escalate B4 |
| B4 declared | task voided — terminal, sem retry |
| B1 → B3 → B4 todos exhausted | `BLOCKED_ERROR error_type: lead_resolution_all_buckets_failed` |

Lead pode pular buckets (skip B1 → start B3 direto se diagnose recomenda). Não pode revisitar bucket usado (B3 → B1 inválido — lead já tem todo contexto necessário; revisitar = loop infinito).

## diagnose.md schema

`scripts/lead-diagnose.py` renderiza `output/wave-N/task-<slug>-diagnose.md` cada vez que trigger condition ativa:

```markdown
# Diagnose — task <slug> (wave <N>)

## Trigger
- condition: <T1_cap_exhausted | T2_convergence_trip | T3_catastrophic>
- detected_at: <ISO 8601>
- attempts_so_far: <int>

## Critic concerns clustered (rounds 1-N)
| Round | BLOCKING | MAJOR | Jaccard vs prev |
|-------|----------|-------|-----------------|
| 1 | <count> | <count> | n/a |
| 2 | <count> | <count> | <0.0-1.0> |
| 3 | <count> | <count> | <0.0-1.0> |

## Recurring claims (Jaccard ≥ 0.5 across rounds)
- <claim text> — appeared rounds: <list>, evidence: <files>

## Catastrophic signals (if T3)
- <signal name>: <evidence>

## Bucket recommendation
- bucket: <B1 | B3 | B4>
- rationale: <1-3 lines>

## Surgical brief (if B1)
<concise brief: top-3 concerns + acceptance delta vs original spec>
```

Lead pode override bucket — registra escolha em `output/wave-N/task-<slug>-lead-decision.md`:

```markdown
# Lead decision — task <slug>

- diagnose_recommended: <B1|B3|B4>
- lead_chose: <B1|B3|B4>
- rationale: <why override OR why accept>
- bucket_attempt_started_at: <ISO 8601>
```

## Audit trail (consumido stage 05)

Wave-summary.md ganha seção dedicada:

```markdown
## Lead resolutions

| Task | Trigger | Bucket recommended | Bucket chosen | Result |
|------|---------|--------------------|---------------|--------|
| <slug> | T2 convergence | B1 | B1 | merged |
| <slug2> | T3 catastrophic | B3 | B3 | escalated B4 |
| <slug3> | T1 cap exhausted | B1 | B3 | merged |
```

Stage 05 audit (sub-step "audit lead resolutions") lê tabela e aplica meta-checks:

| Bucket | Meta-check | Fail action |
|--------|------------|-------------|
| B1 | spec rewrite tighten OR loosen contraints? Loosen sem evidence = fail | `BLOCKED_ERROR error_type: lead_resolution_audit_failed` |
| B3 | lead diff é coherente com critic concerns? Lead resolveu issue real OR só silenciou critic? | `BLOCKED_ERROR error_type: lead_resolution_audit_failed` |
| B4 | rationale cita ADR conflict real OR upstream blocker concreto? Vague reason = fail | `BLOCKED_ERROR error_type: lead_resolution_audit_failed` |

Audit é deterministic regex + estrutura (zero LLM cost).

## L1 frontmatter durante lead-resolution

Status novo: `LEAD_RESOLUTION_IN_PROGRESS`.

```yaml
status: LEAD_RESOLUTION_IN_PROGRESS
sub_stage: "04_wave_<N>_in_progress"  # mantém wave; resolution é sub-state
last_action: "wave <N> task <slug> bucket <B1|B3|B4> in_progress"
```

History event quando bucket starts:
```yaml
- at: <ISO 8601>
  event: lead_resolution_started
  slug: <task-slug>
  bucket: <B1|B3|B4>
  trigger: <T1|T2|T3>
```

## Catastrophic detector — signals

Pre-check em `scripts/lead-diagnose.py` antes de Jaccard:

| Signal | Trigger condition | Bucket hint |
|--------|-------------------|-------------|
| Tests broken outside task scope | `git diff --name-only` exibe test files NÃO declarados em `files_touched` E suite global red | B3 |
| Build globally broken | `_config/profile-effective.yaml:build_command` exit ≠ 0 | B3 |
| Massive scope creep | forensic+ Check 2: `files_outside_declared > 5` | B3 default, B4 override |
| Repo CI completely red | `git log` mostra commits que rebentaram >50% tests da suite global | B3 |

Catastrophic detected → bypass cap 3, escalate lead immediately (sem retry surgical, sem aguardar Jaccard).

## Edge cases

| EC | Scenario | Behavior |
|----|----------|----------|
| EC1 | Wave-planner DAG inválido após B4 (task voided era depended_by) | wave-planner re-deriva DAG; tasks dependentes tratadas como `BLOCKED_HITL` aguardando humano OR cascade B4 |
| EC2 | Lead resolution task → critic ABSTAIN | conta como REJECT, lead escala próximo bucket |
| EC3 | B3 lead writer crash (Agent tool fail) | retry 1×; 2ª falha → escalate B4 mandatory |
| EC4 | B1 spec rewrite reduce VALIDAÇÃO criteria | stage 05 audit detecta loosen → `BLOCKED_ERROR` |
| EC5 | B4 sem rationale concreto (lead apressado) | stage 05 audit detecta vague reason → `BLOCKED_ERROR` |
| EC6 | Concurrent lead-resolution (wave tem 2+ tasks em buckets) | OK — sequencial por task; wave reviewer espera todas resolverem antes do merge |
| EC7 | Lead chose bucket diferente do recommend mas não escreveu lead-decision.md | wave-reviewer detecta missing lead-decision.md → `BLOCKED_ERROR error_type: lead_decision_missing` |

## Cross-references

- Critic protocol: `references/critic-protocol.md`
- Forensic+ protocol: `references/forensic-plus-protocol.md`
- Pipeline 12-passos: `references/wave-execution-protocol.md` step 9
- Diagnose script: `scripts/lead-diagnose.py`
- Pick model: `scripts/pick-model.py`
- L2 runtime: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`
- L2 stage 05 audit: `templates/workspace/stages/05_verification/CONTEXT.md.tpl`
- State machine: `references/state-machine-schema.md` (status `LEAD_RESOLUTION_IN_PROGRESS`; error_types `lead_resolution_audit_failed`, `lead_resolution_all_buckets_failed`, `lead_decision_missing`)
- Recovery wizard: `references/recovery-wizard.md` (tipo `LEAD_RESOLUTION_STALE`)
