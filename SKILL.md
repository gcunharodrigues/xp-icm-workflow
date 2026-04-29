---
name: xp-icm-workflow
description: Bootstrap one-shot ICM (Interpretable Context Methodology) que cria estrutura L0/L1/L2/L3 + branch git + hooks num projeto e sai; sessões subsequentes leem L1+L2 do stage corrente. Suporta 9 estágios (00 recon → 08 feedback intake), 10 profiles × 4 tiers, subagents via Agent Tool fase 04, Wave Planner determinístico, Recovery Wizard, AGENT-BRIEF protocol, ubiquitous language layer, ADR 3-criteria gate, diagnose protocol, triage state machine, OUT-OF-SCOPE knowledge base. Use when starting workspace ICM novo, projeto multi-estágio com revisão humana entre passos, feature complexa que requer discovery+design+implementação+review+merge, ou implementação que precisa paralelismo via subagents. Skip when tarefa trivial (1 arquivo), bug fix simples, refinamento cosmético, ou continuar workspace existente (sessão fresh lê L1+L2 sozinha — não re-invocar).
type: rigid
---

# xp-icm-workflow v3.4.3

> **Skill é parteira, não orquestradora.** Bootstrap one-shot cria a estrutura. Filesystem governa o ciclo. **1 stage = 1 sessão**: cada estágio termina com handoff dual (verbal + arquivo `_kickoff.md`) e a sessão sai. Próxima sessão começa fresh.

> **Base teórica:** Interpretable Context Methodology (VanClief & McDermott, 2025) — substitui orquestração por framework por estrutura de sistema de arquivos. Pastas numeradas representam estágios; arquivos markdown carregam prompts e contexto. Ver `references/icm-paper-summary.md`.

---

## Instruction Priority

1. **User explicit instructions** (CLAUDE.md do projeto, AGENTS.md, mensagens diretas) — sempre vencem.
2. **L0/L1/L2 do workspace** — instruções específicas do projeto/estágio em curso.
3. **Esta skill (`/xp-icm-workflow`)** — só ativa no bootstrap one-shot.
4. **Skills especializadas (superpowers:*)** — sumarizadas em L3 do workspace; invocação real só por escape hatch.
5. **Default system prompt** — perde para 1-4.

---

## When to Use

Invoque `/xp-icm-workflow` para **iniciar** um workspace novo. Casos típicos:

- Projeto novo (greenfield ou existente) com múltiplos estágios + revisão humana entre passos.
- Feature complexa (discovery → design → implementação → review → merge).
- Implementação que se beneficia de paralelismo (subagentes via Agent Tool na fase 04).
- Quer ver, editar e aprovar artefatos intermediários (L4 outputs por estágio).
- Decisões arquiteturais não-triviais que precisam de menu A/B/C.

## When NOT to Use

- Tarefa trivial de código (1 arquivo, sem decisões, sem testes novos) — use `/xp-workflow` direto.
- Bug fix simples — use `/xp-workflow` direto.
- Refinamento cosmético.
- Continuar workspace existente — abra sessão nova; ela lê L1+L2 e procede sozinha. NÃO re-invoque a skill.

---

## What this skill does (one-shot bootstrap)

```
INPUT  →  Skill invocada com profile + tier + project_root
OUTPUT →  Workspace pronto: estrutura de pastas + L0/L1 preenchidos +
          templates de L2 dos 9 estágios + sumários superpowers + git
          branch criada + pre-commit hook instalado + commit inicial
EXIT   →  Skill SAI. Sessão nova retoma via L1+L2.
```

A skill **não persiste** durante o ciclo. Não é orquestradora. Não invoca outras skills no runtime do projeto. É um *project starter* curto.

**Anti-superpowers (regra inegociável):** durante o bootstrap, NUNCA invoque `Skill` tool com `superpowers:*` (brainstorming, executing-plans, writing-plans, test-driven-development, debugging, requesting-code-review, etc.). Discovery/brainstorm pertencem ao `stages/00_recon/` → `stages/01_discovery/` do workspace. TDD/debug viram instruções inline em cada L2. Sumários (200tok cada) ficam em `workspaces/NNN-slug/_references/superpowers-summary/` como referência. Escape hatch: invocação real só com aprovação humana explícita por turno.

---

## Intent inference (prompt sem args)

User pode invocar `/xp-icm-workflow` com **descrição livre** em vez de args (ex: "criar skill que extrai design system de URL"). Protocolo:

1. **NÃO disparar `superpowers:*`** (vide regra acima). Discovery vive no workspace.
2. **Inferir profile/tier do prompt** (heurísticas):

   | Sinal no prompt | Profile inferido |
   |---|---|
   | "skill", "agente", "subagent", "LLM tool" | `agent_ia` |
   | "lib", "SDK", "framework", "package" | `framework_library` |
   | "CLI", "comando", "ferramenta linha de comando" | `cli_tool` |
   | "página web", "componente React/Vue", "UI" | `app_web_frontend` |
   | "API", "backend", "endpoint", "microservice" | `app_web_backend` |
   | "dashboard", "BI", "analytics" | `dashboard` |
   | "EDA", "notebook", "análise de dados" | `data_analysis` |
   | "treinar modelo", "ML pipeline", "fine-tune" | `ml_project` |
   | "artigo", "paper", "post técnico" | `technical_article` |
   | "POC", "spike", "experimento descartável" | `experiment` |

   **Tier default:** `development`. Ajustar pra `experimental` se for POC/spike, `production` se app já em produção, `tool` se uso interno desktop.

3. **Confirmar com humano** menu curto:

   ```
   Inferido: profile=<X> tier=<Y> workspace-name=<slug>
   [a] confirma   [b] corrige   [c] cancela
   ```

   Aceita OU corrige. Pendências de discovery (Qs abertas) devem ficar pra próxima sessão; **NÃO** entre em diálogo Q&A pré-bootstrap (isso é território do `01_discovery`).

4. **Executar bootstrap** com args confirmados (`bash scripts/bootstrap.sh --profile X --tier Y --workspace-name slug`).

5. **Escrever seed inicial** pra próxima sessão em `workspaces/NNN-slug/stages/00_recon/_seed.md`:

   ```markdown
   ---
   layer: L4-seed
   stage: 00_recon
   created_by: bootstrap
   created_at: <ISO8601>
   ---

   # Seed — input pré-recon

   ## Intenção do user (literal)
   <prompt original do user, citado>

   ## Inferência feita no bootstrap
   - Profile: <X>  Why: <heurística>
   - Tier: <Y>  Why: <heurística>

   ## Decisões/contexto já capturados (se houver)
   - <Q1, Q2, ... feitas no diálogo de bootstrap, com escolhas e tradeoffs>

   ## Recursos externos referenciados
   - <repos, URLs, papers citados pelo user, com summary curto se já fetchados>

   ## Pendências pra 00_recon
   - <Qs ainda sem resposta — ex: output format, dependências>
   ```

   Esse arquivo é input declarado no `Inputs` do `stages/00_recon/CONTEXT.md` (L2). Próxima sessão lê e parte dele em vez de zero.

6. **Commit do seed** atomicamente com bootstrap (pre-commit hook valida prefixo `workspace NNN: bootstrap seed`).

7. **SAIR.** Resumo final inclui: workspace path, branch, próximos passos, e linha **"Seed pré-recon em stages/00_recon/_seed.md"**.

**Quando NÃO inferir:** se o prompt é ambíguo ou o user quer escolher manualmente (sinais: "ajuda escolher", "quais opções", "explica diferenças"), pular passo 2 e ir direto pro menu interativo do `bootstrap.sh` (passo 3 com tabela completa).

---

## Division of Responsibilities

| Quem | Decide / Faz |
|---|---|
| **Humano** | Negócio, escopo, profile/tier inicial, aprovação entre estágios, edição de outputs intermediários, recovery decisions |
| **Skill `/xp-icm-workflow`** | One-shot: cria estrutura ICM + git branch + hook + commit inicial. Sai. |
| **L0** (`workspaces/NNN/CLAUDE.md`) | Identidade imutável: paths absolutos, profile/tier, regras inegociáveis |
| **L1** (`workspaces/NNN/CONTEXT.md`) | State machine única: stage_atual, sub_stage, status, history append-only |
| **L2** (`workspaces/NNN/stages/<NN>/CONTEXT.md`) | Instruções do estágio: read order, outputs esperados, gates |
| **L3** (estável) | Conventions, profile-matrix, stop-points canônicos, sumários superpowers |
| **L4** (outputs nascentes) | discovery.md, plan.md, ADRs, wave-plan.md, reports |

---

## CLI

```bash
/xp-icm-workflow profile=<X> tier=<Y> [project-root=<path>] [workspace-name=<slug>] [logs-root=<path>] [override=<yaml>]
```

**Args resolution (Q9 + L1):**

1. **CLI args** vencem tudo (Q9-A''').
2. **`.icm-profile.local.yaml`** detectado em project_root: prompt humano "usar este?".
3. **Pergunta interativa** menu PT (Q9-A') se faltar.

**Profiles canônicos (10):** `app_web_backend`, `app_web_frontend`, `dashboard`, `data_analysis`, `ml_project`, `agent_ia`, `cli_tool`, `framework_library`, `technical_article`, `experiment`.

**Tiers (4):** `experimental`, `tool`, `development`, `production`.

Detalhes da matriz em `templates/_config/profile-matrix.md` (10 × 4 = 40 combos).

---

## What gets created

```
<project_root>/
├── .git/
│   └── hooks/
│       └── pre-commit              [hook instalado, R2.3+R3.3+R3.10+R5.4]
├── .gitignore                      [updated: .icm-profile.local.yaml]
├── workspaces/
│   ├── .index.md                   [registry de workspaces ativos/completados]
│   └── NNN-slug/                   [workspace root]
│       ├── CLAUDE.md               [L0 — identidade imutável]
│       ├── CONTEXT.md              [L1 — state machine única]
│       ├── stages/
│       │   ├── 00_recon/           [L2 templates — Wave 3 da skill popula]
│       │   ├── 01_discovery/
│       │   ├── 02_design/
│       │   ├── 03_wave_planner/
│       │   ├── 04_implementation_waves/
│       │   ├── 05_verification/
│       │   ├── 06_review/
│       │   ├── 07_merge/
│       │   └── 08_feedback_intake/
│       ├── _config/
│       │   ├── profile-effective.yaml  [profile base + override + hash]
│       │   └── profile-matrix.md       [referência humana 10×4]
│       └── _references/
│           ├── runtime/                [protocolos: subagent, wave-planner, recovery, etc.]
│           └── superpowers-summary/    [10 sumários 200tok cada]
```

**Branches criadas:**

- `<base_branch>` — código real do projeto (geralmente `main`).
- `workspace/NNN-slug` — APENAS state files (`workspaces/NNN-slug/*` + `docs/decisions/*` via exceção). NUNCA toca `src/`.
- `wave-NNN-N/<task-slug>` — código + tests da task. Criada de `<base_branch>`. Lead faz merge em `<base_branch>` ao fim da wave.

---

## After bootstrap — 1 stage = 1 sessão (canonical)

A skill **sai**. Próximos passos seguem protocolo **1-stage-1-sessão** (supersede Q3 batched do plan v1; vide `references/session-handoff-protocol.md`):

1. **User abre sessão nova** Claude no project_root.
2. Sessão lê automaticamente:
   - `workspaces/NNN-slug/CLAUDE.md` (L0, identidade)
   - `workspaces/NNN-slug/CONTEXT.md` (L1, state machine)
   - `workspaces/NNN-slug/stages/<stage_atual>/CONTEXT.md` (L2, instruções do estágio)
   - `workspaces/NNN-slug/stages/<stage_atual>/_kickoff.md` se gerado pela sessão anterior
3. Sessão executa o estágio conforme L2.
4. **Fim do stage:** sessão atualiza L1, gera `_kickoff.md` no próximo stage, commita atomicamente, imprime KICKOFF block verbal pro user, **SAI**.
5. User abre nova sessão, cola prompt do KICKOFF, repete o ciclo.

**Trade-off aceito:** cada stage paga 1 cache miss (~2-3k tokens warm-up) em troca de context fresh + token spend total não-linear menor. Empírico: batched B+D do beta1/beta2 cresceu contexto além do alvo de 2-8k por L2; 1-stage-1-sessão fica dentro.

**Stage 04 exceção (decisão 2a):** cada wave = 1 sessão lead (sub-waves dentro da mesma sessão). Lead gera kickoff entre waves no mesmo stage 04 ou pra stage 05 ao final.

**Stage 07 → 08 transição automática:** após merge confirmado, sessão transita imediatamente pra stage 08 com `status: COMPLETED_AWAITING_HUMAN`. Workspace fica vivo aguardando humano voltar com feedback livre após uso real (sem prazo). Gera kickoff pra 08.

**Stage 08 terminal real (saídas inferidas pela intenção do feedback):** humano cola feedback livre na sessão 08 (sem menu A/B/C cru); sessão **infere** A/B/C autonomamente via heurísticas e mini-confirma antes executar.
- **A close** → workspace `COMPLETED` + lições em `docs/lessons.md` (sinais: "tudo ok", silêncio).
- **B restart fase X** → `iteration++`, kickoff pro stage X (mapping: bug em testes → 05, código → 04, design → 02, etc.).
- **C spawn** → workspace fecha + instrução pro user invocar `/xp-icm-workflow spawn_from=<NNN>` em sessão nova (sinais: "pivotar", "novo projeto").

**Migração beta1/beta2 (decisão 4B):** workspaces existentes em batched mode continuam batched; sem conversão forçada. Apenas workspaces criados via `/xp-icm-workflow` pós-beta3 usam 1-stage-1-sessão.

**Recovery:** se sessão crashar mid-estágio → próxima sessão dispara `scripts/recovery-wizard.py` automaticamente via pre-flight check do L2. Detecta 6 tipos de inconsistência (R2.7) e propõe ações.

**Stop points:** 12 stop points canônicos em `_config/stop-points.md` calibrados por tier. Disparo: agente pausa, escreve menu A/B/C, atualiza L1 `status: BLOCKED_STOP_POINT`. Humano responde, sessão retoma.

**Subagentes (fase 04):** waves de paralelismo via Agent tool. Cap por tier (2/3/5/5). Wave Planner determinístico + LLM review subagent. Detalhes em `_references/runtime/subagent-protocol.md`.

**Feedback intake (fase 08):** disparada manualmente pelo humano após uso real. 3 saídas: A) close workspace; B) restart fase X (iteration++); C) spawn novo workspace herdando lessons+ADRs.

---

## Pre-flight runtime check

Bootstrap roda `scripts/check-runtime.sh` antes de qualquer ação. Aborta limpo se runtime falha:

- Python 3.11+ (testado em 3.13)
- PyYAML
- pytest (pra rodar testes da skill localmente)
- git 2.30+
- bash POSIX (Linux/macOS nativo; Windows via Git Bash)
- bats (opcional local; CI rodará via apt no Ubuntu runner)

Permissions allowlist sugerida em `system-requirements.md`.

---

## Anti-patterns (não use)

- `git commit --no-verify` no workspace — pre-commit hook valida atomicidade L1↔outputs e prefixos. Bypass quebra audit. Investigue e corrija conteúdo, NÃO bypass o hook.
- Re-invocar `/xp-icm-workflow` em workspace existente — só pra criar novos. Para retomar, abra sessão nova; ela lê L1.
- Editar L1 (`CONTEXT.md`) manualmente sem entender o schema — use `scripts/recovery-wizard.py` se precisar reconstruir.
- Editar L4 outputs commitados (decisions.md, ADRs) sem nova versão ou superseding — vide `_config/xp-conventions.md`.
- **Invocar `superpowers:*` skills durante bootstrap** (brainstorming, writing-plans, executing-plans, test-driven-development, debugging, etc.). Brainstorm vive em `stages/01_discovery/`. TDD/debug viram instruções dentro de cada L2. Sumários em `_references/superpowers-summary/` (200tok cada) servem como referência. Bypass via Skill tool quebra atomicidade L1↔outputs.
- **Diálogo Q&A pré-bootstrap em vez de bootstrappar.** Quando user invoca a skill com descrição livre, infira profile/tier (vide "Intent inference"), confirme com menu curto, bootstrappe, e mande pendências pro `_seed.md` do `00_recon`. NÃO conduzir discovery completa antes de criar workspace.

---

## References

| Doc | Conteúdo |
|---|---|
| `references/state-machine-schema.md` | Schema completo L1 (yaml frontmatter + history append-only) |
| `references/session-handoff-protocol.md` | **1 stage = 1 sessão**: handoff dual, schema `_kickoff.md`, anti-patterns |
| `references/git-hooks.md` | Pre-commit + commit-msg hooks: regras, padrões regex, anti-bypass |
| `references/recovery-wizard.md` | 6 inconsistências detectadas + ações A/B/C |
| `references/changelog.md` | Versões da skill |
| `references/v2.4-snapshot/` | Snapshot da v2.4 anterior (pra referência histórica) |
| `system-requirements.md` | Runtime + permissions allowlist |
| `templates/_config/profile-matrix.md` | Matriz canônica 10 profiles × 4 tiers |
| `templates/workspace/CLAUDE.md.tpl` | Template L0 com placeholders |
| `templates/workspace/CONTEXT.md.tpl` | Template L1 com placeholders |

**Referências de algoritmo:**

- `references/wave-planner-algorithm.md` — DAG construction, sub-waves, LLM review subagent
- `references/subagent-protocol.md` — spawn via Agent tool, plan approval, mid-wave reduce
- `references/stop-points-canonical.md` — 12 stop points + thresholds por tier
- `references/4-block-contract-template.md` — O QUE / COMO / NÃO QUERO / VALIDAÇÃO
- `references/feedback-intake-fase08.md` — 3 saídas A/B/C
- `references/profile-matrix.md` — calibração por profile/tier (estágios pulados, etc.) — cópia em `templates/_config/profile-matrix.md`

**Referências de testes:**

- `tests/run.sh` — orquestrador (pytest + bats)
- `tests/unit/` — unit + property-based via Hypothesis
- `tests/integration/` — bats integration (CI-only)
- `tests/e2e/` — bats e2e (CI-only)
- `.github/workflows/test-skill.yml` — CI GitHub Actions (Wave 6)
