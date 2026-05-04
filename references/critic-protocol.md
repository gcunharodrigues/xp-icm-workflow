# Critic Protocol — Canonical (v3.9.0)

> **Versão:** v3.9.0
> **Skill:** `xp-icm-workflow`
> **Estágio consumidor:** `04_implementation_waves` (step 8c — L3 critic, sempre, todos tiers)
> **Propósito:** documento canônico do L3 LLM critic ortogonal — fresh-context, anti-sycophancy, triplet-output. Roda em todo task AFK depois de forensic+ extended pass (L2). Output binário APPROVE/REJECT consumido pelo lead-diagnose.

## Resumo (1 parágrafo)

L3 critic é uma 2ª opinião de modelo distinto (intra-Claude — Sonnet ↔ Opus mix), spawnado pelo lead via Agent tool com fresh context (zero memória da sessão writer). Roda **sempre**, em todos tiers, depois que forensic+ extended (L2) aprovou. Recebe brief enxuto: task spec (4-block) + diff completo + acceptance criteria. Output é uma decisão binária (APPROVE | REJECT) acompanhada de triplets `(claim, file:line, counterexample)` quando REJECT. Critic model = `TIER_CEILING[tier]` sempre. Token budget esperado ~3-8k input + 0.5-2k output por task; custo amortizado contra forensic+ deterministic gate (zero token).

## Por que crítico ortogonal

Self-grading do mesmo modelo writer sofre bias documentado:
- Huang et al. ICLR 2024 — sycophancy bias ~88% Claude Code autonomous (auto-aprovação)
- arxiv 2510.11822 — agreeableness assimétrica (modelos cedem mais quando challenged)
- arxiv 2509.16533 — sycophancy under rebuttal (88% flip rate Claude)

Forensic+ (L2) é deterministic regex git-only — imune a sycophancy mas só pega fraude estrutural (assertions count, files declared, scope creep, TODO). Não pega:
- Lógica errada com tests passando coincidentemente
- ADR violation por importar lib disfarçada
- Edge case ausente que coincide com test sem cobertura
- Refactor que muda contrato sem atualizar caller

L3 critic intra-Claude (writer = Sonnet, critic = Opus tier ceiling) cobre o gap semântico residual. Aceita ~5-10% family blindspot (mesma família) — stage 06 review humano + stage 08 feedback compensam downstream.

## Spawn — quem invoca

Lead da wave invoca via Agent tool:

```python
Agent(
    description="L3 critic ortogonal task <slug>",
    subagent_type="general-purpose",
    model="<critic_model_from_pick_model_py>",
    isolation="worktree",  # opcional; pode reusar worktree do writer só pra read
    prompt=render_critic_prompt(task_slug, wave_num),
)
```

Sem script Python wrapper — Agent tool é o scaffold. Prompt template canônico em `templates/critic-prompt.md` (renderizado com slug + wave + diff + spec).

## Anti-sycophancy prompt — princípios

Prompt do critic é **hardcoded** (não deriva de plan.md, não tem espaço pra writer "convencer"). Critic não vê histórico de retries, não vê argumentos do writer, não vê diagnose anterior. Apenas:

1. Task spec original (4-block + acceptance criteria + ADRs aplicáveis + lições)
2. Diff completo da task (`git diff BASE...wave-<NNN>-<N>/<slug> -- <files_touched>`)
3. Test results (output bruto do test runner, não summary)

Hardcoded clauses no prompt template:

```
Você é um auditor independente. Você não conhece o autor do código.
Seu papel é REJEITAR mudanças que não cumprem critérios de aceite ou
violam constraints documentados. APROVAR é o caminho excepcional;
REJEITAR é o default quando há dúvida.

NÃO peça esclarecimentos. NÃO ofereça alternativas construtivas.
NÃO assuma boa-fé do código. Cada claim seu deve apontar
file:line + counterexample concreto.

Se você não consegue identificar 3+ problemas, ainda assim revise
linha-por-linha cada arquivo modificado — provavelmente perdeu algo.

Output APENAS o triplet schema. Sem prefácio. Sem desculpas.
Sem "great work, but...". Direct critique only.
```

## Triplet output schema

Critic output é JSON estrito (parseable) — lead-diagnose.py consome e clusteriza para Jaccard.

```json
{
  "task_slug": "<slug>",
  "wave": <N>,
  "decision": "APPROVE" | "REJECT" | "ABSTAIN",
  "concerns": [
    {
      "claim": "<asserção curta 1-linha>",
      "evidence": "<file>:<line-start>[-<line-end>]",
      "counterexample": "<input/scenario que quebra a claim>",
      "severity": "BLOCKING" | "MAJOR" | "MINOR"
    }
  ],
  "model": "<claude-haiku-4-5|claude-sonnet-4-6|claude-opus-4-7>",
  "tokens_used": { "input": <int>, "output": <int> }
}
```

| Decision | Quando | Lead action |
|----------|--------|-------------|
| `APPROVE` | nenhum BLOCKING/MAJOR; só MINOR ou nenhum concern | task PASS, prossegue merge |
| `REJECT` | ≥1 BLOCKING ou ≥2 MAJOR | lead-diagnose.py → surgical retry OR escalate |
| `ABSTAIN` | critic não conseguiu avaliar (diff truncado, contexto insuficiente, infra fail) | lead trata como REJECT — força retry; se 2 ABSTAIN consecutivos → `BLOCKED_ERROR error_type: critic_abstain_loop` |

## Severity levels

| Severity | Critério | Exemplo |
|----------|----------|---------|
| BLOCKING | viola acceptance criterion explícito OR breaks contract OR security hole | "validate_token aceita assinatura inválida quando exp ausente" |
| MAJOR | edge case relevante não coberto OR ADR drift OR perf regressão >2× | "loop O(N²) em hot path declarado" |
| MINOR | style nit, comentário ausente, naming sub-ótimo | "func name `processData` ambíguo" |

Lead-diagnose só conta BLOCKING + MAJOR para Jaccard convergence trip. MINOR descartado (noise).

## Tier ceiling — sempre

Critic model = `TIER_CEILING[tier]` independente de complexity score do writer. Rationale: critic precisa de capability ≥ writer pra ser útil; downgrade do critic invalida o gate.

| Tier | Critic model |
|------|--------------|
| experimental | claude-haiku-4-5 |
| tool | claude-sonnet-4-6 |
| development | claude-opus-4-7 |
| production | claude-opus-4-7 |

`pick-model.py:pick_models(score, tier)` retorna `(writer, critic)` tupla; critic sempre = ceiling. Cap ceiling do writer.

## Quando NÃO roda L3

| Caso | Behavior |
|------|----------|
| Task `type: HITL` | skip (human resolve manualmente) |
| L2 forensic+ HARD violation | skip — diagnose direto (não desperdiça tokens em código rejeitado por gate barato) |
| Task `Conventions extras: doc-only` | skip (nada a auditar semanticamente em markdown) |
| Wave 1-task com `skip_cross_task_audit: true` | L3 ainda roda na task — flag afeta L4 cross-task only |
| Stage 04 sub_stage `04_wave_<N>_lead_resolution_in_progress` | skip durante lead bucket B3 retry; L3 roda 1× sobre output do lead |

## Edge cases

| EC | Scenario | Behavior |
|----|----------|----------|
| EC1 | Critic crash (Agent tool fail / quota exhausted) | lead retry 1× com mesmo prompt; 2ª falha → `BLOCKED_ERROR error_type: critic_unavailable` |
| EC2 | Critic JSON malformed | lead parser retorna parsing error; critic re-spawn 1×; 2ª falha → trata como ABSTAIN |
| EC3 | Critic diverge sobre interpretação de spec ambígua | é função do critic — REJECT é default. Surgical retry brief deve clarificar spec |
| EC4 | Diff > 200 LOC | critic ainda corre; prompt template paginate (50-LOC chunks) com summary header |
| EC5 | Critic concorda com writer (raro signal "all clear") | APPROVE legítimo; lead prossegue. Não é red flag se forensic+ passou |
| EC6 | Lead bucket B3 (DIRECT_IMPL) — critic do lead | mesmo critic protocol; lead writer code, critic ortogonal valida igual a subagente |
| EC7 | Tests passing mas critic identifica bug | REJECT prevalece — tests podem ser insuficientes. Triplet evidence + counterexample obriga adicionar test ao retry |

## Invocation — render_critic_prompt

Render via `templates/critic-prompt.md` com placeholders:

| Placeholder | Source |
|-------------|--------|
| `{{TASK_SLUG}}` | param do Agent call |
| `{{WAVE_NUM}}` | param |
| `{{TASK_4BLOCK}}` | parsed de plan.md |
| `{{ACCEPTANCE_CRITERIA}}` | bloco VALIDAÇÃO da task |
| `{{ADRS_APPLICABLE}}` | metadata `ADRs aplicáveis` |
| `{{DIFF_COMPLETE}}` | `git diff BASE...wave-<NNN>-<N>/<slug>` |
| `{{TEST_OUTPUT_RAW}}` | stdout do test runner (last run da task) |
| `{{TIER}}` | L1 frontmatter |

## Cross-references

- Lead-resolution canonical: `references/lead-resolution-protocol.md`
- Forensic+ canonical: `references/forensic-plus-protocol.md`
- Pipeline 12-passos: `references/wave-execution-protocol.md` step 8c
- Pick-model heurística: `scripts/pick-model.py`
- L2 runtime: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`
- State machine: `references/state-machine-schema.md` (`error_type: critic_unavailable|critic_abstain_loop`)
- Prompt template renderable: `templates/critic-prompt.md`
