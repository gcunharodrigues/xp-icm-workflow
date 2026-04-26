# xp-workflow ↔ xp-icm-workflow Integration

> **Versão:** v3.0.0-beta1
> **Skill:** `xp-icm-workflow`
> **Propósito:** doc canônico de como `xp-icm-workflow` (esta skill, parteira de workspaces ICM) se relaciona com `xp-workflow` (skill irmã no plugin, executora direta de tarefas). Define quando usar cada uma, hierarquia de invocação, conventions compartilhadas e fluxo de "lift" de uma para outra.

> **Decisão de origem:** §4.10 do plan + Q1 (skill = parteira), Q3 (sessões batched) + memória do projeto Aura (xp-workflow é skill cotidiana; xp-icm-workflow é só pra projetos formais).

---

## 1. Quando usar cada uma

### 1.1 `/xp-workflow` direto

Use quando a tarefa é **trivial ou cosmética** e não precisa de estrutura ICM:

- 1 arquivo, sem decisões arquiteturais.
- Bug fix simples (test reproduz, fix óbvio, regressão coberta).
- Refinamento de docstring, rename, refactor local.
- Ajuste de config, bump de dependência sem implicação de stack.
- Sessão única, ≤30min, ≤2k tok.

### 1.2 `/xp-icm-workflow`

Use quando há **estrutura, paralelismo ou decisões não-triviais**:

- Projeto novo (greenfield ou existente) com múltiplos estágios + revisão humana entre passos.
- Feature complexa (discovery → design → impl → review → merge).
- Implementação que se beneficia de paralelismo (Agent Teams na fase 04).
- Quer ver, editar e aprovar artefatos intermediários (L4 outputs por estágio).
- Decisões arquiteturais não-triviais que precisam de menu A/B/C + ADR formal.
- Tier `development` ou `production` com auditabilidade obrigatória.

### 1.3 Não use **nem** uma nem outra

- Pergunta conceitual ("como funciona X").
- Conversa exploratória sem ação concreta.
- Tarefa de pesquisa pura (cita fontes, não escreve código).

---

## 2. Comparativo lado-a-lado

| Dimensão | `xp-workflow` | `xp-icm-workflow` |
|---|---|---|
| Tipo | Executora direta | Bootstrap one-shot + filesystem-driven |
| Estágios formais | Phases 0-10 internas (no SKILL.md da skill) | 9 estágios materializados em pastas (`stages/00..08`) |
| Sessões típicas | 1 sessão única ponta a ponta | N sessões (1 por estágio ou batch) |
| State machine externa | n/a (skill é stateless por sessão) | L1 `<workspace>/CONTEXT.md` (yaml frontmatter + history append-only) |
| Paralelismo | n/a (sequencial single-agent) | Agent Teams na fase 04 (cap 2/3/5/5 por tier, git worktrees) |
| ADRs formais | Pode escrever em `docs/decisions/` se a tarefa pedir | Obrigatório quando estágio 02 dispara stop point arquitetural |
| Profile/Tier | Implícito (inferido pela tarefa) | Explícito em L0 (`profile: app_web_backend`, `tier: development`) — calibra rigor |
| Stop points | Sim (lista interna do `xp-workflow`) | Sim (12 canônicos em `references/stop-points-canonical.md`, calibrados por tier) |
| 4-block contract | Phase 1 internal | Obrigatório por task no `plan.md` (fase 02), consumido em fase 04 |
| Wave Planner determinístico | n/a | Sim (`scripts/wave-planner-script.py`) + LLM review subagent |
| Recovery Wizard | n/a | Sim (6 inconsistências detectadas em pre-flight) |
| Pre-commit hook | n/a | Instalado pelo bootstrap; valida atomicidade L1↔outputs |
| Git branches | Trabalha em `main` ou branch existente | Cria `workspace/NNN-slug` (state) + `wave-N/<task>` (código) |
| Feedback intake fase 08 | n/a | Sim — humano dispara após uso real, 3 saídas A/B/C |
| Token budget alvo (sessão) | 2-8k | 1-6k por estágio (mais agressivo) |

---

## 3. Hierarquia de invocação (priority order)

Definida em `SKILL.md` §Instruction Priority. Recap:

1. **User explicit instructions** (CLAUDE.md do projeto, AGENTS.md, mensagens diretas) — sempre vencem.
2. **L0/L1/L2 do workspace ICM** — instruções específicas do projeto/estágio em curso (só quando há workspace ICM ativo).
3. **`/xp-icm-workflow`** — só ativa no bootstrap one-shot.
4. **Skills especializadas** — `xp-workflow`, `superpowers:*` etc.
5. **Default system prompt** — perde para 1-4.

Implicações práticas:

- Sessão dentro de workspace ICM (L1 ativo): regras do L2 do estágio vencem qualquer skill especializada se houver conflito.
- Sessão sem workspace ICM: `xp-workflow` é a default para tarefas de código.
- Bootstrap do `xp-icm-workflow` roda 1× e sai; depois disso, é o filesystem que governa.

---

## 4. Conventions compartilhadas

### 4.1 `xp-conventions.md` (compartilhado entre as duas skills)

Define padrões neutros aplicáveis a qualquer profile:

- TDD obrigatório se `tier ∈ {development, production}`.
- Conventional Commits (`feat`, `fix`, `chore`, `refactor`, `docs`, `test`).
- Prefixos de commit por contexto (`workspace:`, `wave:`, `feedback:`, `intake:`).
- Files touched discipline: cada task declara seu footprint.
- LGPD/PII handling baseline.

**Estado atual (v3.0.0-beta1):** o arquivo `xp-conventions.md` ainda **não existe** como template separado. Wave 7 da reescrita da skill cria `templates/_config/xp-conventions.md.tpl` para ser copiado em `<workspace>/_config/xp-conventions.md` no bootstrap. Até lá, `xp-icm-workflow` referencia o conteúdo via `icm-conventions.md.tpl` parcial — verificar `templates/_config/` no bootstrap real.

### 4.2 `icm-conventions.md` (específica da skill ICM)

Convenções que só fazem sentido no ciclo ICM:

- L0 imutável após bootstrap (regenerar via `scripts/recovery-wizard.py` se precisar).
- L1 `history` append-only — nunca editar item existente.
- L4 outputs commitados (decisions.md, ADRs) são imutáveis; mudanças via novo ADR superseding.
- Sub_stage prefixo bate com `stage_atual` sempre.

---

## 5. Fluxo de "lift": de `xp-workflow` para `xp-icm-workflow`

Cenário típico: usuário começa com `/xp-workflow`, descobre que a tarefa cresceu (3+ tasks paralelas, decisões arquiteturais aparecendo, revisão entre passos seria bom). Pode "promover" para `/xp-icm-workflow`.

### 5.1 Sinais de que cabe promover

- Tarefa cresceu para 3+ arquivos com files-conflict potencial.
- Apareceu decisão de stack/db/dep que merece ADR formal.
- Usuário quer ver outputs intermediários antes de seguir.
- Tier subiu (de `tool` para `development`).
- Bug fix descobriu que precisa redesign (vai virar feature complexa).

### 5.2 Como promover (sessão nova)

A skill `xp-icm-workflow` é parteira **one-shot**; não pode ser invocada por dentro do `xp-workflow`. O usuário (ou agente) abre **sessão nova** e roda:

```
/xp-icm-workflow profile=<X> tier=<Y> project-root=<absolute-path> workspace-name=<slug>
```

Bootstrap cria estrutura ICM. Trabalho parcial feito no `xp-workflow` é tratado como **input do estágio 00 recon** — agente lê o branch atual, infere ADRs já implícitos, registra em `recon-report.md`.

### 5.3 Como **não** promover

- Não invocar `/xp-icm-workflow` dentro de uma sessão ativa do `xp-workflow` — quebra a separação one-shot.
- Não tentar "fundir" workspaces: workspace ICM novo nasce limpo, herda contexto via recon.
- Não rebatizar branches manualmente — bootstrap cria as próprias.

---

## 6. Convivência (mesmo projeto, ambas as skills)

Um mesmo `project_root` pode ter:

- `workspaces/042-feat-auth/` (ciclo ICM em andamento).
- `main` ou outras branches ativas onde `/xp-workflow` opera diretamente.
- Contas separadas: `workspace/042-feat-auth` toca SOMENTE state files; `main` (e seus descendentes) toca código.

**Regra de não-interferência:** sessão `xp-workflow` na `main` **não** lê `workspaces/NNN/` (não é input dela). Sessão `xp-icm-workflow` em workspace ativo respeita L2 §"Não Lê" (não toca `src/` fora dos worktrees da fase 04).

---

## 7. Mapeamento conceitual de phases (v3 ↔ v3)

Recap rápido — `xp-workflow` v3 tem phases 0-10 internas; `xp-icm-workflow` v3 tem 9 estágios externos materializados em pastas.

| Phase `xp-workflow` | Estágio `xp-icm-workflow` | Notas |
|---|---|---|
| 0 Reconnaissance | 00 recon | ICM materializa o output em `stages/00_recon/output/baseline.md` |
| 1 4-block communication | Embutido em fase 02 (plan.md schema) | 4-block-contract-template.md formaliza |
| 2 Division of responsibilities | Embutido no `SKILL.md` §Division | Tabela L0/L1/L2/L3/L4 cobre |
| 3 Bootstrap or continuation | One-shot bootstrap (esta skill) | Sai depois — filesystem governa |
| 4 TDD cycles | 04 implementation_waves (cada teammate roda os 7 passos) | Ver `4-block-contract-template.md` §3 |
| 5 Stop points | Em qualquer estágio com decisão | 12 canônicos em `stop-points-canonical.md` |
| 6 CI Gate | Passos 3 e 5 do TDD ciclo + 05 verification | Dupla verificação |
| 7 Pair check | Wave-reviewer (sempre) + peer-reviewer ad-hoc (path crítico) | Detalhes em `agent-team-protocol.md` §5, §10 |
| 8 Post-deploy | 08 feedback_intake (universal todos os tiers) | 3 saídas A/B/C |
| 9 Tech debt dashboard | `docs/tech_debt.md` mantido pela fase 04 | Sample-check em 05/06 |
| 10 Self-revision | **Dropada** | Skill ICM é starter, não runtime |

---

## 8. Documentos compartilhados entre as duas skills

| Documento | Path | Quem escreve | Quem lê |
|---|---|---|---|
| `docs/decisions/NNNN-slug.md` | `<project_root>/docs/decisions/` | fase 02 design (ICM) ou xp-workflow ad-hoc | qualquer estágio posterior; xp-workflow consulta |
| `docs/lessons.md` | `<project_root>/docs/lessons.md` | fase 08 saída A (ICM); xp-workflow ad-hoc | retomada de sessão; pré-cozinhada pelo lead na fase 04 |
| `docs/tech_debt.md` | `<project_root>/docs/tech_debt.md` | teammate em fase 04 declarando débito | fases 04, 05, 06 |
| `xp-conventions.md` | `<workspace>/_config/xp-conventions.md` (ICM) ou implicit (xp-workflow) | bootstrap copia template (Wave 7 pendente) | ambas as skills |

---

## 9. Referências cruzadas

| Doc | Conteúdo |
|---|---|
| `SKILL.md` §When to Use / §When NOT to Use | Critérios canônicos de seleção |
| `SKILL.md` §Instruction Priority | Hierarquia 1-5 completa |
| `references/stage-templates.md` | Mapeamento dos 9 estágios ICM |
| `references/superpowers-mapping.md` | Como ICM usa superpowers (sumários 200tok) |
| `references/v2.4-snapshot/xp-workflow-integration.md` | Versão v2.4 anterior (referência histórica) |
| Plugin `xp-workflow` SKILL.md | Phases 0-10 internas |
