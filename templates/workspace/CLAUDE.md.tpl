---
layer: L0
workspace: "{{WORKSPACE}}"
profile: "{{PROFILE}}"
tier: "{{TIER}}"
project_root: "{{PROJECT_ROOT}}"
base_branch: "{{BASE_BRANCH}}"
workspace_branch: "workspace/{{WORKSPACE}}"
profile_effective_hash: "{{PROFILE_EFFECTIVE_HASH}}"
logs_root: {{LOGS_ROOT}}
created_at: "{{CREATED_AT}}"
icm_skill_version: "{{SKILL_VERSION}}"
---

# Workspace {{WORKSPACE}} — L0 (identidade)

## Propósito

L0 é a constituição imutável deste workspace. Todo agente em qualquer estágio lê este arquivo PRIMEIRO. Define identidade, paths absolutos e regras inegociáveis.

## Identidade

| Campo | Valor |
|---|---|
| Workspace | `{{WORKSPACE}}` |
| Profile | `{{PROFILE}}` |
| Tier | `{{TIER}}` |
| Project root | `{{PROJECT_ROOT}}` (path absoluto) |
| Base branch | `{{BASE_BRANCH}}` |
| Workspace branch | `workspace/{{WORKSPACE}}` |
| Logs root | `{{LOGS_ROOT}}` |
| Profile hash | `{{PROFILE_EFFECTIVE_HASH}}` |

## Paths absolutos (fonte de verdade)

| Recurso | Path | Branch real |
|---|---|---|
| Workspace root | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/` | workspace |
| L1 state | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md` | workspace |
| Estágios | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/<NN>_*/` | workspace |
| Config | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/` | workspace |
| Conventions | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/xp-conventions.md` | workspace |
| Ubiquitous Language (L3) | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/CONTEXT.md` | workspace |
| OUT-OF-SCOPE kb | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_out-of-scope/` | workspace |
| Runtime refs | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/` | workspace |
| Sumários superpowers | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/` | workspace |
| Skill dir | `{{SKILL_DIR}}` | (filesystem global) |
| Project CLAUDE.md | `{{PROJECT_ROOT}}/CLAUDE.md` (dashboard externo do estado; mantido por `handoff.py`) | workspace (migra pra base na saída A) |
| **Worktree base branch (`.icm-main/`)** | `{{PROJECT_ROOT}}/.icm-main/` | base (`{{BASE_BRANCH}}`) |
| ADRs do projeto | `{{PROJECT_ROOT}}/.icm-main/docs/decisions/` | base |
| Lessons do projeto | `{{PROJECT_ROOT}}/.icm-main/docs/lessons.md` | base |
| Tech debt | `{{PROJECT_ROOT}}/.icm-main/docs/tech_debt.md` | base |
| Código existente (read-only de leitura cross-branch) | `{{PROJECT_ROOT}}/.icm-main/src/`, `{{PROJECT_ROOT}}/.icm-main/tests/` etc. | base |

**Regra:** TODA referência a docs resolve absoluta a partir de `{{PROJECT_ROOT}}`. Scripts da skill resolvem absoluta a partir de `{{SKILL_DIR}}/scripts/`. NUNCA use `scripts/` relativo (assumir CWD errado). NUNCA use `../../` relativo. Vazamento de path = bug B2 do diagnóstico.

**Modelo worktree paralelo (v3.4.0):** quando branch checada em `{{PROJECT_ROOT}}` é `workspace/{{WORKSPACE}}`, paths como `{{PROJECT_ROOT}}/docs/decisions/` NÃO existem no working tree (workspace branch não tem `docs/`). Para ler/escrever esses paths, use o worktree linkado em `{{PROJECT_ROOT}}/.icm-main/` (sempre checado em `{{BASE_BRANCH}}`). Doc canônico: `_references/runtime/worktree-model.md`.

## Regras inegociáveis

### 1. Anti-bypass (B1)

NUNCA use `git commit --no-verify` neste workspace. O pre-commit hook valida atomicidade `outputs ↔ L1` e prefixos de commit. Se o hook bloqueia: investigue e corrija o conteúdo, não bypass o hook.

### 2. CWD do agente

Cada sessão começa lendo seu L2 (`stages/<NN>/CONTEXT.md`). O L2 declara o CWD esperado:

- Sessões 00–03, 05–08: CWD = `{{PROJECT_ROOT}}` (workspace branch checkout).
- Sessão 04 (lead): CWD = `{{PROJECT_ROOT}}` (workspace branch).
- Subagente em wave: CWD = `{{PROJECT_ROOT}}` (branch `wave-{{WORKSPACE_NUM}}-<N>/<task-slug>`).

### 3. Branches + worktree paralelo

Três tipos de branch ICM convivem via git worktree:

- `{{BASE_BRANCH}}` — código real do projeto + ADRs + lessons + tech_debt + dashboard `CLAUDE.md` em estado idle.
- `workspace/{{WORKSPACE}}` — só state files (`workspaces/{{WORKSPACE}}/*`) + dashboard `CLAUDE.md` ativo. NUNCA toca `src/`, `tests/`, `docs/decisions/`, `docs/lessons.md`, `docs/tech_debt.md`.
- `wave-{{WORKSPACE_NUM}}-<N>/<task-slug>` — código + tests da task. Criada de `{{BASE_BRANCH}}`. Lead merge em `{{BASE_BRANCH}}` ao fim da wave.

Worktree:

- `{{PROJECT_ROOT}}/` (worktree principal) — durante ciclo ICM, normalmente checada em `workspace/{{WORKSPACE}}`.
- `{{PROJECT_ROOT}}/.icm-main/` (worktree linkada) — sempre checada em `{{BASE_BRANCH}}`. Cria pelo bootstrap (`git worktree add .icm-main {{BASE_BRANCH}}`). Listada em `.gitignore` de todas as branches. Cleanup só em saída A do último workspace.
- Subagentes em fase 04 usam `Agent(isolation: "worktree")` — tool cria worktree efêmera por subagente em `wave-{{WORKSPACE_NUM}}-<N>/<task-slug>`.

Pre-commit hook do `{{PROJECT_ROOT}}/` rejeita commit em `workspace/*` que toca paths fora de `workspaces/*`, `workspaces/.index.md`, `.gitignore`, `CLAUDE.md` (dashboard). ADRs / lessons / tech_debt **não** estão no whitelist do hook — devem ser commitados via `cd .icm-main && git commit ...` (que opera na base branch automaticamente).

Doc canônico do modelo: `_references/runtime/worktree-model.md`.

### 4. Profile + Tier calibram rigor

Profile = `{{PROFILE}}`. Tier = `{{TIER}}`. Calibração canônica em `_config/profile-matrix.md`. Define:

- Estágios pulados.
- Cap de subagentes por wave (2/3/5/5 por tier).
- TDD obrigatório vs opcional.
- Security gate on/off.
- Stop points calibrados (5 serviço pago, 7 over-engineering, 8 PII).

Override local em `.icm-profile.local.yaml` (no `{{PROJECT_ROOT}}`). Hash recomputado em pre-flight.

### 5. Stop Points

12 stop points canônicos em `_config/stop-points.md`. Disparo: agente pausa, escreve menu A/B/C, atualiza L1 `status: BLOCKED_STOP_POINT`. Humano responde, sessão retoma.

### 6. ADRs

ADRs criados em fase 02 são L4 nascente; após commit em `{{BASE_BRANCH}}` viram L3 imutável. Edição de ADR existente = nova versão (`0001-stack-v2.md`) ou superseding (`0042-supersedes-0001.md`). Edição direta proibida em pre-commit hook.

Workflow canônico fase 02 (v3.4.0):

```
1. Write {{PROJECT_ROOT}}/.icm-main/docs/decisions/NNNN-<slug>.md
2. cd {{PROJECT_ROOT}}/.icm-main
3. git add docs/decisions/NNNN-*.md
4. git commit -m "docs(decisions): <slug> (workspace {{WORKSPACE}})"
5. cd {{PROJECT_ROOT}}
6. plan.md cita filename relativo a `.icm-main/docs/decisions/`
```

NUNCA tente `git add docs/decisions/...` direto da worktree principal em workspace branch — pre-commit hook rejeita.

### 7. Linguagem

Conteúdo em português. Identificadores de código, paths, comandos em inglês.

### 8. Cross-branch reads via `.icm-main/`

Sessões em qualquer estágio que precisem ler conteúdo da base branch
(ADRs vigentes, lessons herdadas, tech_debt acumulado, código existente
para diagnose) DEVEM ler de `{{PROJECT_ROOT}}/.icm-main/<path>`. Read tool
funciona direto — zero `git show base:<path>` necessário.

Antes da 1ª leitura cross-branch da sessão:

- Verificar `.icm-main/` existe em `{{PROJECT_ROOT}}` (presente desde
  bootstrap; ausente = recovery wizard).
- Sincronização opcional: se base branch avançou desde a última sessão,
  rodar `cd {{PROJECT_ROOT}}/.icm-main && git fetch && git pull --ff-only`
  (manualmente quando relevante; fase 07 lead executa após cada merge).

### 9. Superpowers via summary, não Skill tool

Skills `superpowers:*` (brainstorming, executing-plans, test-driven-development, debugging, etc.) NÃO devem ser invocadas via `Skill` tool durante o ciclo ICM.

- **Usar:** sumários em `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/` (200tok cada). Aplicar princípios inline.
- **Escape hatch:** invocação real só com aprovação humana explícita por turno (humano escreve "ok, dispara superpowers:X").
- **Por quê:** brainstorm/discovery vive em `stages/01_discovery/`. TDD/debug viram instruções dentro de cada L2. ICM governa o ciclo via filesystem; superpowers como skill paralela quebra atomicidade L1↔outputs e bypassa governance.
- **Bootstrap pendente sem args:** perguntar OU inferir profile/tier. NUNCA pular pra fluxo livre superpowers.

## Read order para qualquer agente

1. `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md` (este arquivo, L0)
2. `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md` (L1, state machine)
3. `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/<stage_atual>/CONTEXT.md` (L2, instruções do estágio)
4. `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/<stage_atual>/_kickoff.md` (L4-kickoff, handoff da sessão anterior — condicional, pode não existir em workspaces legados ou primeira sessão de stage)
5. Paths declarados na tabela `Inputs` do L2 (L3 + L4 específicos)

Layer Loading Protocol literal: a tabela `Inputs` do L2 é a fonte canônica do que ler. O `Read Order` é guia prático de sequência — pode agrupar itens relacionados ou reordenar para eficiência, mas cada item do Read Order deve mapear para um item em Inputs. Recusa ler qualquer path não listado em Inputs.

## Session header

Toda sessão imprime na primeira mensagem (R4.4):

```
Workspace {{WORKSPACE}} | Stage <NN> | Status <YY> | Profile {{PROFILE}}/{{TIER}} | Próximo: <next_action>
```
