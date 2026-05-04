# Forensic+ Protocol — Canonical (v3.8.0)

> **Versão:** v3.8.0
> **Skill:** `xp-icm-workflow`
> **Estágio consumidor:** `04_implementation_waves` (step 8a)
> **Propósito:** documento canônico do Forensic+ — auditoria estrutural anti-fraude por task na wave-reviewer. Descreve os 4 checks, matriz tier×severidade, ações HARD/SOFT, cap de re-spawn, edge cases, e schema JSON do `scripts/forensic-plus.py`.

## Resumo (1 parágrafo)

Forensic+ é um audit determinístico, git-only, executado pelo wave-reviewer (step 8a do pipeline 12-passos) por cada task AFK da wave. Roda 4 checks: (1) test file com ≥2 asserções, (2) files fora de `files_touched` declarado, (3) scope creep > 3× plan estimate, (4) TODO/FIXME/HACK adicionados. Cada violation tem severidade tier-aware (HARD/SOFT). HARD bloqueia merge e força re-spawn (cap `MAX_FORENSIC_RETRIES = 2`); SOFT acumula em `wave-summary.md`. Tasks `type: HITL` são skipped. Output via `scripts/forensic-plus.py` em JSON estruturado, parsed pelo reviewer Agent.

## Os 4 checks

### Check 1 — Test file com ≥2 asserções

Garante que test files declarados em `files_touched` contêm ≥2 tokens reconhecidos como asserções (count-based, não filtragem semântica). Skip quando task tem `Conventions extras: doc-only` ou `config-only`.

Comando: `git show wave-<NNN>-<N>/<slug>:<test-file>` por test file.

Linguagem-aware regex (extensão → padrão):

| Ext | Padrão | Threshold |
|-----|--------|-----------|
| `.py` | `\bassert\b\|pytest\.raises\|self\.assert\w+` | ≥ 2 |
| `.ts/.tsx/.js/.jsx` | `\b(expect\|assert\|should\|it\(\|test\()\b` | ≥ 2 |
| `.go` | `\bt\.\(Errorf\|Fatal\|Run\)\b` | ≥ 2 |
| `.rb` | `\b(expect\|assert\|should)\b` | ≥ 2 |
| `.rs` | `\bassert(_eq\|_ne)?!\b` | ≥ 2 |
| `.java/.kt` | `\b(assert\|@Test\|assertEquals)` | ≥ 2 |
| `.cs` | `\b(Assert\.\|\[Test\]\|\[Fact\]\|\[Theory\])` | ≥ 2 |

Severity: **HARD** em todo tier.

### Check 2 — Files fora de `files_touched` declarado

Compara nome de arquivos do diff (`git diff --name-only BASE...wave`) contra declarado em plan.md task. Diferença set (atual − declarado) é violation, exceto se filename está na allowlist global de lockfiles/caches.

Allowlist tier-agnóstica: `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`, `Cargo.lock`, `Gemfile.lock`, `poetry.lock`, `go.sum`, `.prettierrc.cache`, `.eslintcache`.

Severity:

| Tier | Severity |
|------|----------|
| experimental/tool | SOFT |
| development/production | HARD |

### Check 3 — Scope creep > 3× plan estimate

Lê `### Estimated lines` opcional do plan.md task (ver `references/4-block-contract-template.md`). Compara com `git diff --shortstat` insertions count. Trigger se `insertions > 3 × estimate`. Se campo ausente, skip silently (backward compat).

Severity:

| Tier | Severity |
|------|----------|
| experimental/tool/development | SOFT |
| production | HARD |

### Check 4 — TODO/FIXME/HACK adicionados

Conta linhas começando `+` (não `+++`) que match `(TODO|FIXME|HACK|XXX)` em arquivos de código (`.py .ts .tsx .js .jsx .go .rb .rs .java .kt .cs`). Ignora linhas removidas (`-`) e contexto.

Severity:

| Tier | Severity |
|------|----------|
| experimental/tool/development | SOFT |
| production | HARD |

## Tier × violation matrix consolidada

| Check | exp | tool | dev | prod |
|-------|-----|------|-----|------|
| Test asserções | HARD | HARD | HARD | HARD |
| Files fora declared | SOFT | SOFT | HARD | HARD |
| Scope creep 3× | SOFT | SOFT | SOFT | HARD |
| TODO/FIXME/HACK | SOFT | SOFT | SOFT | HARD |

## Action HARD vs SOFT

- **HARD em ≥1 check** → reviewer emit `approved_pending_ci: false`, lead re-spawn subagente original.
- **Apenas SOFT** → reviewer emit `approved_pending_ci: true`, violations gravam em `wave-summary.md`, merge prossegue.
- **Nenhum** → padrão approved.

## Re-spawn cap + brief prescritivo

Cap: `MAX_FORENSIC_RETRIES = 2` (hardcoded em `scripts/forensic-plus.py`, drift-checked). Tier-agnostic.

| Tentativa | Resultado | Action |
|-----------|-----------|--------|
| 1ª original | HARD | re-spawn round 1 |
| 2ª (round 1) | HARD | re-spawn round 2 |
| 3ª (round 2) | HARD | `BLOCKED_ERROR error_type: forensic_max_retries`, escala humano |
| Qualquer | SOFT only | merge prossegue |
| Qualquer | NONE | merge prossegue |

Brief de re-spawn injeta no AGENT-BRIEF do subagente:

| Violation | Texto injetado |
|-----------|----------------|
| `test_assertions_too_few` | "Test file `<path>` tem `<N>` asserções. Adicione ≥2 asserções não-triviais cobrindo edge cases + happy path." |
| `files_outside_declared` | "Você tocou `<path>` não declarado em files_touched. Reverta ou escreva `output/wave-<N>/task-<slug>-blocked.md` pra escalar (sem novo stop point — usa BLOCKED handoff existente)." |
| `scope_creep` | "Diff `<X>` linhas vs estimate `<Y>`. Reduza ou divida. Se scope real é maior, escalar via stop point `over_eng`." |
| `todo_added` | "TODOs adicionados: `<list>`. Remova ou converta em issues." |

## Edge cases

| EC | Scenario | Behavior |
|----|----------|----------|
| EC1 | `forensic-plus.py` crash (git missing branch / plan malformed) | Script exit 1 + stderr. Reviewer emit `forensic_passed: null, forensic_error: <stderr>`. Lead → `BLOCKED_ERROR error_type: forensic_script_crash`. Escala humano. |
| EC2 | JSON parse fail | Treat as EC1. |
| EC3 | Re-spawn introduz nova HARD diferente | Conta como retry. Cap 2 ainda aplica. Anti-gaming. |
| EC4 | Wave HITL + AFK | Roda só em AFK. HITL → `forensic_passed: null`. |
| EC5 | Wave 1-task | Forensic+ roda. Akita-tipo cross-task skipped (`skip_cross_task_audit: true`). |
| EC6 | TODO obfuscation (`T0D0`, `F1XME`) | Out of scope. |
| EC7 | Lockfile vulnerabilities | Allowlist ignora. Stage 05 / security_gate cobre. |

## CI global step 10 interaction

Inalterado. `approved_pending_ci: true` é semântica (decisão final pendente CI). Step 10 vermelho → `references/ci-rollback-protocol.md` existente. Forensic+ não dispara rollback automático.

## JSON schema do `scripts/forensic-plus.py`

**Input (CLI):**

```bash
python scripts/forensic-plus.py \
    --workspace-num <NNN> \
    --wave <N> \
    --task-slug <slug> \
    --base-branch <BASE> \
    --plan <path-to-plan.md> \
    --tier <experimental|tool|development|production> \
    --output json
```

**Output (stdout JSON):**

```json
{
  "task_slug": "<slug>",
  "violations": [
    {
      "check": "<test_assertions_too_few|files_outside_declared|scope_creep|todo_added>",
      "severity": "<HARD|SOFT>",
      "evidence": "<human-readable explanation>"
    }
  ],
  "forensic_passed": true | false | null,
  "max_severity": "HARD" | "SOFT" | "NONE" | null,
  "skipped_reason": "task type=HITL"   // present only if HITL
}
```

**Exit codes:**
- `0` — script ran successfully (regardless of violations).
- `1` — script crash (git missing, plan malformed). Stderr formatted.

## Cross-references

- Pipeline 12-passos consumidor: `references/wave-execution-protocol.md` step 8a-8d.
- Schema task plan.md: `references/4-block-contract-template.md` (`### Estimated lines`).
- L2 runtime: `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`.
- State machine: `references/state-machine-schema.md` (`error_type: forensic_max_retries|forensic_script_crash`).
- Stop points (tabela: este audit não é stop point, é audit pós-COMPLETE): `references/stop-points-canonical.md`.
- Conflict / CI rollback: `references/conflict-resolution-protocol.md`, `references/ci-rollback-protocol.md`.
