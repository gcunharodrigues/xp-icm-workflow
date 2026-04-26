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

| Recurso | Path |
|---|---|
| Workspace root | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/` |
| L1 state | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md` |
| Estágios | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/<NN>_*/` |
| Config | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/` |
| Sumários superpowers | `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/` |
| ADRs do projeto | `{{PROJECT_ROOT}}/docs/decisions/` |
| Lessons do projeto | `{{PROJECT_ROOT}}/docs/lessons.md` |
| Tech debt | `{{PROJECT_ROOT}}/docs/tech_debt.md` |
| Worktrees fase 04 | `{{PROJECT_ROOT}}/.worktrees/workspace-{{WORKSPACE}}/wave-<N>/<task-slug>/` |

**Regra:** TODA referência a docs resolve absoluta a partir de `{{PROJECT_ROOT}}`. NUNCA use `../../` relativo. Vazamento de path = bug B2 do diagnóstico.

## Regras inegociáveis

### 1. Anti-bypass (B1)

NUNCA use `git commit --no-verify` neste workspace. O pre-commit hook valida atomicidade `outputs ↔ L1` e prefixos de commit. Se o hook bloqueia: investigue e corrija o conteúdo, não bypass o hook.

### 2. CWD do agente

Cada sessão começa lendo seu L2 (`stages/<NN>/CONTEXT.md`). O L2 declara o CWD esperado:

- Sessões 00–03, 05–08: CWD = `{{PROJECT_ROOT}}` (workspace branch checkout).
- Sessão 04 (lead): CWD = `{{PROJECT_ROOT}}` (workspace branch).
- Teammate em wave: CWD = `{{PROJECT_ROOT}}/.worktrees/workspace-{{WORKSPACE}}/wave-<N>/<task-slug>/` (branch `wave-{{WORKSPACE}}-<N>/<task-slug>`).

### 3. Branches

- `{{BASE_BRANCH}}` — código real do projeto.
- `workspace/{{WORKSPACE}}` — só state files (`workspaces/{{WORKSPACE}}/*`). NUNCA toca `src/`, `tests/`.
- `wave-{{WORKSPACE}}-<N>/<task-slug>` — código + tests da task. Criada de `{{BASE_BRANCH}}`. Lead rebase em `{{BASE_BRANCH}}` ao fim da wave.

Pre-commit hook rejeita commit em `workspace/*` que toca paths fora de `workspaces/*` (R3.3).

### 4. Profile + Tier calibram rigor

Profile = `{{PROFILE}}`. Tier = `{{TIER}}`. Calibração canônica em `_config/profile-matrix.md`. Define:

- Estágios pulados.
- Cap de teammates por wave (2/3/5/5 por tier).
- TDD obrigatório vs opcional.
- Security gate on/off.
- Stop points calibrados (5 serviço pago, 7 over-engineering, 8 PII).

Override local em `.icm-profile.local.yaml` (no `{{PROJECT_ROOT}}`). Hash recomputado em pre-flight.

### 5. Stop Points

12 stop points canônicos em `_config/stop-points.md`. Disparo: agente pausa, escreve menu A/B/C, atualiza L1 `status: BLOCKED_STOP_POINT`. Humano responde, sessão retoma.

### 6. ADRs

ADRs criados em fase 02 são L4 nascente; após commit em `{{BASE_BRANCH}}` viram L3 imutável. Edição de ADR existente = nova versão (`0001-stack-v2.md`) ou superseding (`0042-supersedes-0001.md`). Edição direta proibida em pre-commit hook.

### 7. Linguagem

Conteúdo em português. Identificadores de código, paths, comandos em inglês.

### 8. Superpowers via summary, não Skill tool

Skills `superpowers:*` (brainstorming, executing-plans, test-driven-development, debugging, etc.) NÃO devem ser invocadas via `Skill` tool durante o ciclo ICM.

- **Usar:** sumários em `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/` (200tok cada). Aplicar princípios inline.
- **Escape hatch:** invocação real só com aprovação humana explícita por turno (humano escreve "ok, dispara superpowers:X").
- **Por quê:** brainstorm/discovery vive em `stages/01_discovery/`. TDD/debug viram instruções dentro de cada L2. ICM governa o ciclo via filesystem; superpowers como skill paralela quebra atomicidade L1↔outputs e bypassa governance.
- **Bootstrap pendente sem args:** perguntar OU inferir profile/tier. NUNCA pular pra fluxo livre superpowers.

## Read order para qualquer agente

1. `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md` (este arquivo, L0)
2. `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md` (L1, state machine)
3. `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/<stage_atual>/CONTEXT.md` (L2, instruções do estágio)
4. Paths declarados na tabela `Inputs` do L2 (L3 + L4 específicos)

Layer Loading Protocol literal: lê só o listado em `Inputs`. Recusa ler mais.

## Session header

Toda sessão imprime na primeira mensagem (R4.4):

```
Workspace {{WORKSPACE}} | Stage <NN> | Status <YY> | Profile {{PROFILE}}/{{TIER}} | Próximo: <next_action>
```
