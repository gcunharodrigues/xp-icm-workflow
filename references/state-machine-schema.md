# State Machine Schema (L1 — `<workspace>/CONTEXT.md`)

> **Path resolution:** caminhos `scripts/` neste documento referem-se a `<SKILL_DIR>/scripts/`, onde `SKILL_DIR` está definido em L0 (`CLAUDE.md`).

> Esquema canônico do `CONTEXT.md` raiz do workspace. Validado em pre-flight check de cada sessão. Property-based tested em `tests/unit/test_state_machine.py`.

## Formato do arquivo

`<workspace>/CONTEXT.md` é Markdown com **YAML frontmatter** seguido de seções narrativas. O frontmatter é a fonte de verdade do estado; o corpo é apenas para legibilidade humana.

```markdown
---
<frontmatter yaml>
---

# Workspace NNN — <slug>

(corpo opcional, narrativo)
```

## Frontmatter — campos obrigatórios

| Campo | Tipo | Valores / formato | Origem |
|---|---|---|---|
| `workspace` | string | `NNN-slug` (ex: `042-feat-auth`) | Bootstrap |
| `profile_base` | string | um de 11 profiles canônicos | Bootstrap |
| `profile_effective_hash` | string | sha256 hex (64 chars) | `<SKILL_DIR>/scripts/profile-merge.py` |
| `tier` | string | `experimental` \| `tool` \| `development` \| `production` | Bootstrap |
| `project_root` | string | path absoluto | Bootstrap (CWD ou `--project-root`) |
| `base_branch` | string | nome de branch git válido | Bootstrap (`git rev-parse --abbrev-ref HEAD`) |
| `workspace_branch` | string | `workspace/NNN-slug` | Bootstrap |
| `stage_atual` | string | `00` \| `01` \| ... \| `08` | Sessão atual |
| `sub_stage` | string | enum (ver §Sub-stage enum) | Sessão atual |
| `status` | string | enum (ver §Status canônicos) | Sessão atual |
| `iteration` | integer | ≥ 0, monotônico | `0` no bootstrap; `++` em fase 08 saída B |
| `history` | list | append-only (ver §History) | Toda transição append |
| `last_action` | string | descrição livre | Sessão atual |
| `last_action_at` | string | ISO 8601 timestamp | Sessão atual |
| `next_action` | string | descrição livre | Sessão atual |
| `last_transition` | object | `{from, to, at, commit_sha}` | Toda transição |

## Frontmatter — campos opcionais (nullable / omissíveis)

| Campo | Tipo | Quando presente | Default |
|---|---|---|---|
| `stages_skipped` | list of strings | sempre (bootstrap determina via profile/tier) | `[]` |
| `logs_root` | string \| null | sistema com logs externos (H3) | `null` |
| `waves` | object \| null | `stage_atual >= 04` (R2.8) | ausente antes de 04 |
| `llm_review_skipped_count` | integer | sempre que ≥1 skip ocorre | `0` |
| `spawn_from` | string | workspace foi gerado por fase 08 saída C | omisso |
| `spawn_to` | string | workspace gerou outro via fase 08 saída C | omisso |
| `custom_stop_points` | list | yaml override declarou (D3) | omisso |
| `revisit_after` | string | yaml override declarou (Q16) | omisso |

## Status canônicos (6 valores)

| Status | Quando | Próxima ação típica |
|---|---|---|
| `IN_PROGRESS` | sessão ativa trabalhando | continuar trabalho ou transicionar |
| `COMPLETED_AWAITING_HUMAN` | estágio concluído, gate humano pendente | humano aprova/rejeita; transition para próximo estágio |
| `BLOCKED_STOP_POINT` | menu A/B/C disparado | humano responde menu; `IN_PROGRESS` |
| `BLOCKED_ERROR` | falha runtime/CI/merge | humano resolve manualmente; `IN_PROGRESS` |
| `BLOCKED_HITL` | wave mista, task `type: HITL` aguarda humano (não-falha) | humano completa task report; `IN_PROGRESS` |
| `COMPLETED` | workspace inteiro fechado (fase 07 saída ou fase 08 A) | none — workspace arquivado |

**Variação especial:** `RESTARTING_AT_PHASE_X` (H1) é registrado em `history` como evento de `iteration++`, mas o `status` em si volta para `IN_PROGRESS` no estágio X com `iteration` incrementado.

## Sub-stage enum (R2.6)

Estados granulares dentro de cada estágio. Pre-flight valida enum.

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
| 08 Feedback Intake | `08_in_progress`, `08_decided_A`, `08_decided_B` †, `08_decided_C` |

**† `08_decided_B` é transitório:** aparece somente como evento em `history`, nunca persistido em `sub_stage`. A sessão transita diretamente de `08_in_progress` para `<XX>_in_progress` (stage de retorno). O enum existe para compatibilidade do schema, mas validate-state deve aceitar `08_decided_B` em history events sem exigir que ele apareça em `sub_stage`.

**Regra:** `sub_stage` SEMPRE começa com prefixo `<stage_atual>_`. Mismatch = inconsistência → Recovery Wizard.

## `history` — append-only

Lista de eventos. Ordem cronológica preservada. Cada item:

```yaml
- at: "2026-04-25T14:30:00Z"
  event: "stage_transition"  # ver §Event types abaixo
  from: "02_completed"        # opcional, depende do event
  to: "03_in_progress"        # opcional, depende do event
  commit_sha: "abc123def"     # opcional, se houve commit
  note: "stack approved by human"  # texto livre opcional
```

**Regra:** sessões NUNCA editam itens existentes; apenas append. Recovery Wizard pode prepend item `recovery_applied` documentando reconstrução.

### Event types canônicos

| Event | Descrição | Campos obrigatórios |
|---|---|---|
| `stage_transition` | Transição entre estágios/sub_stages | `from`, `to`, `commit_sha` |
| `stop_point_triggered` | Stop point disparado | `stop_point_id`, `from` |
| `stop_point_resolved` | Humano respondeu stop point | `stop_point_id`, `to` |
| `iteration_increment` | Saída B da fase 08: `iteration++` | `from`, `to`, `commit_sha` |
| `recovery_applied` | Recovery Wizard corrigiu inconsistência | `inconsistency_type`, `action` |
| `wave_completed` | Wave N da fase 04 finalizada | `wave`, `commit_sha` |
| `blocked_error` | Erro runtime bloqueou progresso | `error_type`, `message` |
| `workspace_bootstrapped` | Bootstrap inicial do workspace | `commit_sha` |
| `feedback_session_started` | Humano abriu sessão de feedback (fase 08) | `from` |

### `error_type` values (conhecidos, lista crescente — não enum)

Quando o evento `blocked_error` é appended a `history` (e `status: BLOCKED_ERROR`
é setado em paralelo), o campo `error_type` (free-form string) do evento é
populado com um dos valores abaixo. Lista evolui por versão; não há enforcement
automático. Schema do `last_transition` permanece `{from, to, at, commit_sha}`
sem `error_type` — este vive apenas no event row de `history`.

- `merge_conflict`
- `ci_red`
- `cap_exceeded`
- `cleanup_unsafe`
- `runtime_cleanup_failed`
- `forensic_max_retries`        <!-- v3.8.0 — cap MAX_FORENSIC_RETRIES esgotado -->
- `forensic_script_crash`       <!-- v3.8.0 — forensic-plus.py exit 1 -->
- `human_abort`

## `waves` — schema (presente só se `stage_atual >= 04`)

```yaml
waves:
  current: 2                     # int, wave em execução
  completed: [1]                 # list de int, waves já merged
  current_sub_wave: null         # str opcional, ex "2.a" se subdividida (E3)
  blocked_at_sub_wave: null      # str opcional, set se BLOCKED_ERROR mid-wave (E4)
  blocked_task: null             # str opcional, slug da task bloqueada
```

## `last_transition` — schema

```yaml
last_transition:
  from: "02_completed"
  to: "03_in_progress"
  at: "2026-04-25T14:30:00Z"
  commit_sha: "abc123def456"
```

**Regra:** `commit_sha` deve existir em `git log` da `workspace_branch`. Se não existe (force push ou branch reset) → Recovery Wizard inconsistência #4 (R2.7).

## Heurísticas de inconsistência (Recovery Wizard — R2.7)

Pre-flight de sessão NOVA dispara Recovery se qualquer uma:

1. `profile_effective_hash` não bate com hash recomputado de `<workspace>/_config/profile-effective.yaml`
2. Outputs declarados em `history` não existem no FS
3. `status: IN_PROGRESS` sem commit em `workspaces/NNN/*` nas últimas 24h
4. `last_transition.commit_sha` não existe em git history
5. `waves.current` declara wave N mas branches `wave-NNN-N/<task>` ausentes

Cada inconsistência tem mensagem específica + ação proposta em `references/recovery-wizard.md`.

## Exemplo completo (mid-wave 2)

```yaml
---
workspace: "042-feat-auth"
profile_base: "app_web_backend"
profile_effective_hash: "9f3a8b2c4d6e1f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a"
tier: "development"
project_root: "C:/Users/guicr/projects/aura-luz-api"
base_branch: "main"
workspace_branch: "workspace/042-feat-auth"
stage_atual: "04"
sub_stage: "04_wave_2_in_progress"
status: "IN_PROGRESS"
iteration: 0
logs_root: null
llm_review_skipped_count: 0
waves:
  current: 2
  completed: [1]
  current_sub_wave: null
  blocked_at_sub_wave: null
  blocked_task: null
last_action: "wave 2 spawned with 3 subagentes"
last_action_at: "2026-04-25T14:30:00Z"
next_action: "lead aguarda 3 COMPLETE; depois wave-reviewer + merge sequencial"
last_transition:
  from: "04_wave_1_completed"
  to: "04_wave_2_in_progress"
  at: "2026-04-25T14:30:00Z"
  commit_sha: "abc123def456"
history:
  - at: "2026-04-23T10:00:00Z"
    event: "stage_transition"
    from: "00_completed"
    to: "01_in_progress"
    commit_sha: "111aaa"
  - at: "2026-04-24T09:00:00Z"
    event: "stage_transition"
    from: "03_completed"
    to: "04_wave_1_in_progress"
    commit_sha: "222bbb"
  - at: "2026-04-24T18:00:00Z"
    event: "wave_completed"
    note: "wave 1 merged in base_branch, CI green"
    commit_sha: "333ccc"
  - at: "2026-04-25T14:30:00Z"
    event: "stage_transition"
    from: "04_wave_1_completed"
    to: "04_wave_2_in_progress"
    commit_sha: "abc123def456"
---

# Workspace 042 — feat-auth

Auth middleware para API Aura Luz. Tier development, 2 waves planejadas.
```

## Validação

`<SKILL_DIR>/scripts/validate-state.sh` chamado em pre-flight de cada sessão:

1. Parse YAML frontmatter (PyYAML strict load).
2. Valida campos obrigatórios presentes.
3. Valida enums (`tier`, `status`, `sub_stage` — prefixo bate `stage_atual`).
4. Valida `iteration >= 0` e monotônico vs `history`.
5. Valida `waves` ausente/null se `stage_atual < "04"`; presente se `>=`.
6. Valida `last_transition.commit_sha` existe em git history.
7. Recomputa `profile_effective_hash` e compara.
8. Roda heurísticas de Recovery (R2.7).

Falha em qualquer step → mensagem específica + abort OU Recovery Wizard.

## Property-based testing (`tests/unit/test_state_machine.py`)

Hypothesis gera estados aleatórios respeitando schema. Property invariantes:

- Toda transition válida preserva schema YAML.
- `iteration` é monotônico (nunca decresce).
- `history` é append-only (nunca shrink).
- `sub_stage` sempre prefixo de `stage_atual`.
- `waves` ausente sse `stage_atual < "04"`.
- Status ∈ enum canônico.
- `last_transition.from` é o `sub_stage` anterior, `last_transition.to` é o `sub_stage` atual.
