---
name: xp-icm-workflow
description: Orquestra projetos completos usando ICM (Interpretable Context Methodology) para estrutura de workflow, xp-workflow para implementação de código com TDD/clean code, e skills do superpowers para etapas especializadas (brainstorm, planos, subagentes, verificação, review, merge).
type: flexible
---

# XP-ICM Workflow v2.4.0

Orquestração de projetos via pastas numeradas (ICM) + rigor técnico de código (xp-workflow) + skills especializadas do superpowers por estágio.

> **Tese central:** O workflow é a estrutura. O código é a execução. Cada um tem sua skill. A orquestradora apenas conecta os pontos.

> **Base teórica:** Implementa a Interpretable Context Methodology (ICM) de VanClief & McDermott (2025), que substitui orquestração por framework por estrutura de sistema de arquivos. Pastas numeradas representam estágios. Arquivos markdown carregam prompts e contexto. Ver `references/icm-paper-summary.md` para resumo acadêmico.

---

## Instruction Priority

1. **User explicit instructions** (CLAUDE.md do projeto, AGENTS.md, mensagens diretas) — sempre vencem.
2. **Esta skill (`/xp-icm-workflow`)** — sobrescreve comportamento default.
3. **Skills especializadas (`/xp-workflow`, `superpowers:*`)** — ativadas por estágio, regras internas vencem no escopo delas.
4. **Default system prompt** — perde para 1, 2 e 3.

---

## When to Use

- Projeto novo com múltiplos estágios e revisão humana entre passos.
- Feature complexa (envolve discovery, design, código, deploy).
- Usuário quer ver, editar e aprovar artefatos intermediários.
- Decisões arquiteturais não-triviais que precisam de menu de opções.
- Implementação envolve TDD, múltiplos arquivos, ou pode ser paralelizada.

## When NOT to Use

- Tarefa trivial de código (1 arquivo, sem decisões, sem testes novos).
- Bug fix simples (use `/xp-workflow` diretamente).
- Refinamento cosmético.
- Projeto já em produção que só precisa de ajuste rápido.

---

## Division of Responsibilities

| Quem | Decide / Faz |
|---|---|
| **Humano** | Negócio, escopo, aprovação entre estágios, escolha entre opções arquiteturais, edição de outputs intermediários |
| **xp-icm-workflow** (esta skill) | Orquestração: gerar workspace, escolher template, rotear estágios, decidir qual skill especializada invocar |
| **superpowers:brainstorming** | Discovery: requisitos, alternativas, MVP, restrições |
| **superpowers:writing-plans** | Design: plano detalhado, decisões |
| **superpowers:subagent-driven-development** | Delegação: toda implementação delegada a subagentes |
| **/xp-workflow** | Implementação por subagent: TDD, clean code, docstrings, CI gates, pair check |
| **superpowers:verification-before-completion** | Verificação antes de declarar pronto |
| **superpowers:requesting-code-review** | Review contra plano e padrões |
| **superpowers:receiving-code-review** | Processar feedback externo |
| **superpowers:finishing-a-development-branch** | Merge: integrar (merge, PR, cleanup) |
| **superpowers:systematic-debugging** | Debug quando estágio falha |
| **Automação** | Format, lint, type, security, secrets, dep audit, coverage (vem de `/xp-workflow`) |

---

## ICM Design Principles (5)

Resumo operacional. Detalhe acadêmico em `references/icm-paper-summary.md`.

1. **Um estágio, um trabalho.** Cada estágio faz uma coisa, escreve output na sua pasta. Nunca misturar responsabilidades.
2. **Texto plano como interface.** Estágios se comunicam por markdown e JSON. Humano pode abrir editor e modificar qualquer artefato.
3. **Carregamento em camadas.** Agentes carregam SOMENTE o contexto necessário ao estágio atual (Layer Loading Protocol).
4. **Todo output é superfície de edição.** Outputs intermediários são editáveis pelo humano antes do próximo estágio rodar.
5. **Configure a fábrica, não o produto.** Workspace configurado uma vez (Layer 3 = receita); cada run produz novo deliverable (Layer 4 = produto). Editar Layer 3 melhora todas as runs.

---

## Layer Loading Protocol

### As 5 Camadas

| Camada | Arquivo | Função | Tamanho típico | Carrega sempre? |
|---|---|---|---|---|
| **L0** | `CLAUDE.md` | Identidade workspace | ~800 tok | Sim |
| **L1** | `CONTEXT.md` raiz | Estado e roteamento | ~300 tok | Sim |
| **L2** | `stages/XX/CONTEXT.md` | Contrato do estágio | ~500 tok | Apenas estágio atual |
| **L3** | `references/`, `_config/`, `docs/decisions/` | Restrições | 500–2000 tok | Apenas listados na Inputs table |
| **L4** | `stages/XX/output/` | Trabalho | Varia | Apenas listados na Inputs table |

### Ordem de Leitura Obrigatória

Ao entrar em qualquer estágio: `L0 → L1 → L2 → L3 → L4`. Nunca pular ordem.

### Convenção `[L3:cfg]` vs `[L4:in]` na Inputs Table

Para evitar prosa repetida sobre a distinção operacional:

- `[L3:cfg]` — internalizar como **restrição** (siga estas regras, use este estilo). Não muda entre runs. Analogia: receita.
- `[L4:in]` — processar como **input** (transforme este conteúdo). Muda a cada run. Analogia: ingredientes.

Aplicar diferentemente NUNCA é opcional. Confundir os dois quebra o ICM.

### Ciclo de Vida dos ADRs (`docs/decisions/`)

ADRs são L3 (restrição) porque estágios downstream os consomem como regras. Mas são **criados durante o Estágio 02** (Design & Planning). Ciclo:

1. **Nascimento (Estágio 02):** ADR é produzido pelo estágio — comporta-se como output nascente.
2. **Promoção imediata para L3:** ao ser commitado, torna-se restrição para todos estágios downstream e runs futuras.
3. **Edição via Edit-Source:** ADR existente só muda via Error Recovery arquitetural (status `REVISADO`) ou via princípio Edit-Source, nunca silenciosamente.

Esta dupla natureza é intencional — evita duplicar o conteúdo entre L3 e L4 após criação.

### Token Budget e Context Scoping

Meta: 2.000–8.000 tokens por estágio (excluindo código produzido no Estágio 03). Abordagens monolíticas atingem 30.000–50.000, com degradação documentada por Liu et al. (2024) — "lost in the middle".

Regras:
- Inputs table lista 5 arquivos? Ler SOMENTE 5. Nunca "só mais um".
- Inputs lista "seção Decisão" de um ADR? Ler SOMENTE essa seção.
- Inputs lista 2 ADRs entre 8 disponíveis? Ler SOMENTE esses 2.
- Subagentes recebem contexto ainda mais restrito: L0 + L2 do escopo + inputs explícitos. Nada mais.

---

## Workflow Overview — Tabela Mestra

| # | Estágio | Skill principal | Input chave | Output chave | Review gate |
|---|---|---|---|---|---|
| 01 | Discovery | `superpowers:brainstorming` | Brief / prompt inicial | `discovery.md` | Humano aprova requisitos/MVP |
| 02 | Design & Planning | `superpowers:writing-plans` | `discovery.md` | `plan.md` + ADRs | Humano aprova plano e decisões |
| 03 | Implementation | `superpowers:subagent-driven-development` (orquestradora) + `/xp-workflow` (subagents) | `plan.md` + `decisions.md` | Código + `implementation-report.md` | Humano aprova após CI verde |
| 04 | Verification | `superpowers:verification-before-completion` | `implementation-report.md` + `plan.md` | `verification-report.md` | Humano aprova PASS |
| 05 | Code Review | `superpowers:requesting-code-review` | Reports + `plan.md` + ADRs | `review-report.md` | Humano aprova ajustes ou ignora |
| 06 | Merge & Delivery | `superpowers:finishing-a-development-branch` | `verification-report.md` + `review-report.md` | `delivery-report.md` + branch/PR | Humano confirma fim |

Falha ou output inesperado em qualquer estágio: invocar `superpowers:systematic-debugging` antes de prosseguir.

---

## Phase 0 — Bootstrap

Para gerar o workspace ICM no início de um projeto novo.

### 0.0 Respeitar Instruction Priority (ANTES de qualquer ação)

Antes de criar qualquer pasta ou arquivo:

- Se houver `AGENTS.md` na raiz do projeto pai: **ler primeiro** (Instruction Priority #1 do projeto vence).
- Se houver `CLAUDE.md` na raiz do projeto pai: ler primeiro.
- Regras do projeto pai sobre idioma, nomenclatura, stack, ou estrutura SOBRESCREVEM templates padrão ICM. Se conflito, aplicar regra do projeto pai e documentar em `_config/project-rules.md` do workspace.

### 0.1 Classificar (4-block do `/xp-workflow`)
- Tipo de projeto (website / app / api / agente_ia / dashboard / artigo / outro)
- Business impact tier (experimental / tool / development / production)
- Stack inferida ou confirmada
- Número estimado de estágios (padrão: 4-6)

### 0.2 Selecionar template ICM

| Template | Estágios | Uso |
|---|---|---|
| `website-static` | 01_brief → 02_wireframe → 03_frontend → 04_deploy → 05_seo | Sites, landing, blogs |
| `app-fullstack` | 01_discovery → 02_design → 03_api → 04_ui → 05_tests → 06_deploy | Apps web/mobile |
| `api-service` | 01_requirements → 02_contract → 03_implementation → 04_tests → 05_deploy | APIs REST/GraphQL |
| `agent-ia` | 01_discovery → 02_prompts → 03_tools → 04_integration → 05_tests | Agentes com LLM |
| `dashboard` | 01_data-sources → 02_models → 03_viz → 04_deploy | Dashboards/análise |
| `article-tech` | 01_research → 02_outline → 03_draft → 04_review → 05_publish | Artigos técnicos |
| `generic` | 01_discovery → 02_design → 03_implementation → 04_tests → 05_deploy | Fallback |

### 0.3 Gerar estrutura de pastas

`workspaces/NNN-slug/` (NNN = contador, slug = kebab-case):

```
workspaces/NNN-slug/
├── CLAUDE.md              # L0: identidade
├── CONTEXT.md             # L1: estado e roteamento
├── stages/
│   ├── 01_nome/
│   │   ├── CONTEXT.md     # L2: contrato
│   │   └── output/        # L4: artefatos da run
│   └── ...
├── _config/
│   ├── xp-conventions.md  # L3: convenções (FÁBRICA)
│   ├── project-rules.md   # L3: regras (FÁBRICA)
│   └── project-brief.md   # L3 (opcional): brief inicial
└── docs/                  # vinculado ao projeto pai
    ├── decisions/         # L3: ADRs formais (fonte da verdade)
    ├── lessons.md         # L3: lições acumuladas
    └── tech_debt.md       # L3: dívida técnica rastreada
```

> Configure-the-factory: arquivos em `_config/` (L3) e `docs/decisions/` (L3 após criação) são FÁBRICA — estáveis entre runs. Arquivos em `output/` (L4) são PRODUTO — mudam a cada run.

> **Pasta `stages/XX/references/` (opcional):** criar SOMENTE se o estágio tiver material de referência específico que não cabe em `_config/` (ex: exemplo de output anterior servindo como few-shot). Por padrão não criar — templates e regras globais moram em `_config/`.

### 0.4–0.6 Preencher CLAUDE.md, CONTEXT.md raiz e CONTEXT.md de cada estágio

Usar templates prontos em `references/stage-templates.md` (templates de `CLAUDE.md` raiz, `CONTEXT.md` raiz, e os 6 `CONTEXT.md` de estágio). Cada `stages/XX/CONTEXT.md` deve ter as 7 seções: Estado, Skill, Inputs, Process, Outputs, Verify, Review Gate.

### 0.7 Apresentar ao humano

"O workflow tem X estágios. Adicionar/remover/renomear algum? Posso iniciar o Estágio 1 ou quer revisar contratos?"

---

## Retomada de Sessão

1. Ler `workspaces/NNN-slug/CLAUDE.md` (L0).
2. Ler `workspaces/NNN-slug/CONTEXT.md` raiz (L1) — estado, histórico, roteamento.
3. Ler `stages/XX/CONTEXT.md` do estágio atual (L2).
4. Ler **SOMENTE** os arquivos listados na Inputs table do estágio (L3 e L4).
5. Se houver `AGENTS.md` na raiz do projeto: lê-lo antes de qualquer ação (Instruction Priority #1).
6. Se estágio anterior foi completado: ler seu `output/` como L4 input, conforme Inputs table.
7. Apresentar ao humano: "Workspace `NNN-slug` retomado no Estágio X. Continuar ou revisar contratos?"

> **Fallback se `CONTEXT.md` raiz corrompido:** inferir estado pela existência de arquivos `output/` nos estágios. Último estágio com output completo = completado; próximo sem output = atual.

---

## Stage Transition Protocol (HARD GATE)

Antes de avançar de um estágio para o próximo, completar **todos** os itens. Avançar sem completar quebra o ICM — sessões futuras não conseguem retomar e rastreabilidade se perde.

### Stage Transition Checklist (declarado 1× — referenciado por nome em cada estágio)

1. **Escrever outputs do estágio atual** — todos os artefatos em `stages/XX/output/`
2. **Atualizar `stages/XX/CONTEXT.md`** — seção Estado com `STATUS: COMPLETED`, data e lista de outputs
3. **Atualizar `CONTEXT.md` raiz** — append no histórico (data, `XX_nome`, `COMPLETED`, outputs). Em seguida, atualizar o campo `STAGE` para apontar para o PRÓXIMO estágio conforme Roteamento (`STAGE: YY_nome`, `STATUS: IN_PROGRESS`) — assim uma retomada de sessão imediata sabe onde continuar. Se é o último estágio, marcar `STAGE: COMPLETED`.
4. **Commitar** — outputs + CONTEXT.md atualizados (1 commit por transição, mensagem descreve a transição)
5. **Apresentar ao humano** — "Estágio XX completo. Outputs: [lista]. Aprovar para YY?"

**Somente após os 5 itens:** carregar próximo estágio (L0 → L1 → L2 do próximo).

### Violação

Se a orquestradora avança sem completar o checklist:
- Workflow quebrado — sessões futuras não podem retomar.
- Histórico incompleto — perde-se rastreabilidade.
- Princípio "plaintext as the interface" violado.

**Auto-correção:** ao descobrir transição incompleta, parar imediatamente, voltar e completar antes de prosseguir.

---

## Compilação Incremental (Re-execução Seletiva)

Benefício-chave do ICM: re-executar SOMENTE o estágio que precisa de retrabalho.

### Regras de dependência

- **L3 muda** (`_config/`, `references/`, `docs/decisions/`): invalida TODOS estágios downstream.
- **L4 muda** (`output/` de um estágio): invalida SOMENTE o estágio consumidor e subsequentes.
- **L2 muda** (`CONTEXT.md` do estágio): invalida SOMENTE aquele estágio e subsequentes.

### Quando humano edita output no review gate

Perguntar: "Esta edição é pontual (corrige esta run) ou sistêmica (corrige todas as runs futuras)?"
- **Pontual:** aceitar e prosseguir. Próximo estágio lê versão editada.
- **Sistêmica:** aplicar princípio Edit-Source (próxima seção).

---

## Princípio Edit-Source

Duas formas de corrigir output:
1. **Editar output (L4):** corrige esta run. Patching binary.
2. **Editar fonte (L2 ou L3):** corrige todas as runs futuras. Fixing compiler source.

Quando humano edita output no review gate, SEMPRE perguntar:

> "Edição pontual ou recorrente? Se você se encontra fazendo a mesma edição toda run, contrato ou referências devem ser atualizados para que futuras runs produzam o resultado certo automaticamente."

**Sinais de mudança de fonte:**
- Humano aperta o mesmo tipo de edição no mesmo estágio 3+ runs seguidas.
- Humano remove consistentemente um tipo de conteúdo que o agente sempre gera.
- Humano adiciona consistentemente um tipo de conteúdo que o agente nunca gera.

Quando identificado, atualizar:
- `stages/XX/CONTEXT.md` (L2) — se instrução do contrato é insuficiente.
- `references/` ou `_config/` (L3) — se regras de estilo/convenção são incompletas.
- `docs/decisions/` (L3) — se decisão arquitetural mudou.

Documentar em `docs/lessons.md`.

---

## Phase 1 — Execução por Estágios

Cada estágio segue este padrão. **Templates completos de `CONTEXT.md` em `references/stage-templates.md`.** Phase 1 abaixo cobre o que é load-bearing em runtime: skill, input/output chave, e — onde aplicável — protocolo de delegação detalhado.

### Estágio 01: Discovery

- **Skill:** `superpowers:brainstorming`
- **Input:** brief inicial (`_config/project-brief.md`) ou nada (ideia veio do prompt)
- **Output:** `output/discovery.md` (resumo, requisitos, alternativas, MVP, riscos, métricas)
- **Review gate:** humano aprova requisitos/MVP. Aplicar Stage Transition Checklist.

### Estágio 02: Design & Planning

- **Skill:** `superpowers:writing-plans`
- **Input:** `../01_discovery/output/discovery.md` ([L4:in]); `_config/xp-conventions.md`, `docs/tech_debt.md` ([L3:cfg])
- **Output:**
  - `output/plan.md` — plano completo
  - `output/decisions.md` — INDEX de decisões (títulos/slugs/status)
  - `../../docs/decisions/NNNN-slug.md` — ADR formal (fonte da verdade)
- **Stop points obrigatórios** (do `/xp-workflow`): stack/banco/framework, modelagem de dados, API pública, nova dependência, novo serviço pago, decisão difícil de reverter.
- **Regra de propagação:** `decisions.md` é índice; ADR formal em `docs/decisions/` é fonte da verdade. Estágios posteriores leem o ADR formal, não apenas o sumário.
- **Review gate:** humano aprova plano e decisões. Aplicar Stage Transition Checklist.

### Estágio 03: Implementation

- **Skill (orquestradora):** `superpowers:subagent-driven-development` (SEMPRE)
- **Skill (por subagent):** `/xp-workflow`

> **Princípio de Delegação:** Orquestradora NUNCA escreve código nem lê código-fonte. Toda implementação delegada a subagentes que executam `/xp-workflow` internamente. Orquestradora lê SOMENTE `implementation-report.md` (L4 compacto).

**Processo da orquestradora:**

1. Ler L0 → L1 → L2 (`stages/03_implementation/CONTEXT.md`).
2. Ler **SOMENTE** os Inputs listados (`plan.md`, `decisions.md`, ADRs no plan, `tech_debt.md`, `lessons.md`, `xp-conventions.md`).
3. **NÃO ler:** `src/`, `tests/`, código-fonte de qualquer tipo.
4. Analisar plano → identificar tasks independentes vs dependentes.
5. Extrair lições aplicáveis de `lessons.md` (a orquestradora lê; subagents não leem `lessons.md` diretamente — apenas recebem lições relevantes já filtradas no prompt de delegação).
6. Delegar **cada task** via `Skill({skill: "superpowers:subagent-driven-development"})`.

**Protocolo de Delegação — prompt do subagent contém SOMENTE:**

```
## Contexto do Workspace
- Caminho relativo: workspaces/NNN-slug/
- Perfil do projeto: [tipo/tier do CLAUDE.md]
- Stack: [do CLAUDE.md]

## Sua Task
[Descrição em PT, extraída do plano]

## Inputs (leia SOMENTE estes, na ordem)
1. workspaces/NNN-slug/CLAUDE.md
2. workspaces/NNN-slug/stages/03_implementation/CONTEXT.md
3. workspaces/NNN-slug/stages/02_design/output/plan.md (seção [especificar])
4. workspaces/NNN-slug/stages/02_design/output/decisions.md
5. [ADRs relevantes à sua task — SOMENTE os listados]
6. workspaces/NNN-slug/docs/tech_debt.md
7. workspaces/NNN-slug/_config/xp-conventions.md

## Regras de Stop Point
SE precisar de nova dependência, stack, API pública, ou serviço pago, PARE e retorne à orquestradora com justificativa.

## Regras de Contexto
- NÃO ler arquivos fora desta lista
- Seguir /xp-workflow (TDD, convenções, commits)
- Código em src/, testes em tests/ do projeto pai (NÃO dentro de stages/)
- Ao finalizar: escrever resumo em workspaces/NNN-slug/stages/03_implementation/output/reports/task-<slug>.md (arquivo próprio, para evitar race com outros subagents paralelos)

## Proibido
- NÃO ler outputs de estágios não relacionados
- NÃO ler ADRs não listados
- NÃO modificar arquivos fora do escopo
```

**Subagentes sequenciais vs paralelos:**
- Tasks **independentes** (ex: API users e API habits sem dependência) → paralelo.
- Tasks **dependentes** (ex: modelo de dados antes de API sobre o modelo) → sequencial; cada subagent recebe output do anterior.

**Evitar race em reports paralelos:** cada subagent escreve em arquivo próprio `output/reports/task-<slug>.md`. Nunca dois subagents gravam no mesmo arquivo simultaneamente. Após todos completarem, a orquestradora consolida em `output/implementation-report.md` lendo os arquivos individuais (ou um subagent dedicado "consolidator" pode fazer isso).

**Após todos completarem:**

7. Orquestradora lê **SOMENTE** os `output/reports/task-*.md` individuais — nunca código-fonte.
8. Orquestradora (ou subagent "consolidator" delegado) consolida os `reports/task-*.md` em `output/implementation-report.md`.
9. CI gates verde em todos os reports → review gate.
10. Falha em qualquer report → invocar `superpowers:systematic-debugging` ou delegar correção a novo subagent com escopo limitado.

**Formato de cada `output/reports/task-<slug>.md`** (cada subagent escreve o seu) — o `implementation-report.md` consolidado agrega os mesmos campos somando as tasks:

```markdown
# Task Report — <slug>

## Summary
[Breve resumo: 3-5 frases]

## Steps Completed
| Step | Descrição | Status | Arquivos |
|------|-----------|--------|----------|
| 1    | ...       | ✅/⚠️/❌ | `src/foo.py`, `tests/test_foo.py` |

## CI Gates
| Gate | Status | Notas |
|------|--------|-------|
| Format | ✅/❌ | ... |
| Lint | ✅/❌ | ... |
| Type | ✅/❌ | ... |
| Security | ✅/❌ | ... |
| Secrets | ✅/❌ | ... |
| Dep Audit | ✅/❌ | ... |
| Tests | ✅/❌ | ... |

## ADR Compliance
| ADR | Respeitado? | Notas |
|-----|-------------|-------|
| NNNN-slug | ✅/⚠️/❌ | ... |

## Tech Debt Introduced
[Nenhum / lista]

## Lessons Learned
[Para acrescentar a docs/lessons.md]

## Stop Points Hit
[Nenhum / lista]
```

**Review gate:** orquestradora lê SOMENTE os `reports/task-*.md` individuais e/ou `implementation-report.md` consolidado (nunca código-fonte). Humano revisa código diretamente no repositório (ou confia no CI + pair check). Aplicar Stage Transition Checklist.

### Estágio 04: Verification

- **Skill:** `superpowers:verification-before-completion`

> **Princípio de Delegação aplicado:** Orquestradora lê `implementation-report.md` para saber O QUE foi feito, não COMO. Inspeção técnica é responsabilidade do skill de verificação.

- **Input:** `implementation-report.md`, `plan.md` ([L4:in]); ADRs relevantes, conventions ([L3:cfg]). NÃO ler `src/` ou `tests/`.
- **Processo:** comparar implementation-report contra plano e ADRs. Skill de verificação lê código-fonte internamente.
- **Output:** `output/verification-report.md` com status `PASS` / `CONDITIONAL` / `FAIL`.
- **Review gate:** humano revisa relatório. FAIL → retorna ao Estágio 03. PASS/CONDITIONAL → Estágio 05. Aplicar Stage Transition Checklist.

### Estágio 05: Code Review

- **Skill principal:** `superpowers:requesting-code-review`
- **Skill (se feedback externo):** `superpowers:receiving-code-review`

> **Princípio de Delegação aplicado:** Orquestradora lê reports compactos. Skill de code review lê código-fonte internamente.

- **Input:** `implementation-report.md`, `verification-report.md`, `plan.md`, `decisions.md` ([L4:in]); ADRs, tech_debt ([L3:cfg]). NÃO ler `src/` ou `tests/`.
- **Processo:** comparar implementação contra plano, ADRs, convenções, 4-block de validação. Dimensões: correctness, security, test quality, design, standards, readability, performance.
- **Output:** `output/review-report.md` + lista de ajustes + tech_debt atualizado se houver novos débitos.
- **Review gate:** humano aprova ajustes ou ignora. Se P0/P1 → aplicar Fix Loop Protocol abaixo. Aplicar Stage Transition Checklist.

### Fix Loop Protocol (Estágio 05 → 03)

Quando code review encontra P0/P1:

1. Orquestradora lê **somente** `review-report.md` (L4).
2. Para cada P0/P1: despachar subagent implementer com:
   - Descrição exata do fix (do review-report)
   - Arquivo(s) afetado(s) (paths exatos)
   - Critério de aceitação
3. Após fix: despachar spec reviewer → code quality reviewer.
4. Orquestradora lê **somente** os reports — **nunca editar código**.
5. Repetir até todas P0/P1 resolvidas.
6. P2: documentar em `docs/tech_debt.md`, não exigir fix imediato.

### Estágio 06: Merge & Delivery

- **Skill:** `superpowers:finishing-a-development-branch`
- **Input:** `verification-report.md`, `review-report.md` ([L4:in]).
- **Processo:** confirmar PASS, considerar ajustes do review, apresentar menu (merge direto / PR / tag de release / cleanup), executar escolha do humano, atualizar `lessons.md` e `tech_debt.md`.
- **Output:** `output/delivery-report.md` + branch integrada ou PR criado.
- **Review gate:** humano confirma satisfação. Aplicar Stage Transition Checklist final.

---

## Error Recovery

**Skill:** `superpowers:systematic-debugging`

**Quando invocar:**
- Output de um estágio incompleto ou errado.
- CI Gate falha sem motivo óbvio.
- Review gate rejeita output.
- Transição entre estágios quebra (output não encontrado, formato inesperado).

**Processo:**

1. Parar workflow.
2. Classificar origem:
   - **Erro dentro do `/xp-workflow`** (Estágio 03): deixar `/xp-workflow` aplicar Phase Error Recovery interno (dentro do subagent). Aguardar diagnóstico.
   - **Erro de orquestração ou skill superpowers** (Estágios 01, 02, 04, 05, 06): invocar `superpowers:systematic-debugging`.
3. Erro **arquitetural** (decisão do Estágio 02 incorreta):
   - Atualizar ADR formal em `docs/decisions/NNNN-slug.md` com nova análise e status `REVISADO`.
   - Atualizar `output/decisions.md` (sumário).
   - Documentar em `docs/lessons.md`.
   - Aplicar **compilação incremental:** re-executar SOMENTE estágios afetados.
4. Auto-fix se seguro e dentro do escopo.
5. Se não conseguir, apresentar ao humano:
   - (a) corrigir abordagem e refazer estágio atual
   - (b) rollback para estágio anterior
   - (c) skip + replan a partir deste ponto

---

## Orchestration Boundary (HARD RULE)

A orquestradora **invoca skills especializadas e subagentes — nunca inspeciona código-fonte diretamente nem toma decisões que cabem ao humano**. Sem exceções por conveniência ou "pequenez".

Em 01-02 a orquestradora invoca skills (brainstorming, writing-plans) que escrevem artefatos markdown — a orquestradora pode ler esses outputs. Em 03 em diante, o artefato primário é código-fonte — apenas subagentes e skills especializadas (verification, code review) leem `src/`/`tests/` diretamente; a orquestradora lê somente reports compactos.

| Tipo de estágio | Orquestradora faz | Orquestradora NÃO faz |
|---|---|---|
| 01-02 (Design) | Invoca skill, lê outputs markdown (`discovery.md`, `plan.md`, `decisions.md`) | Editar código |
| 03 (Implementação) | Delega subagentes, lê `implementation-report.md` | Editar código, ler `src/`/`tests/` |
| 04-05 (Validação) | Invoca skill, lê reports compactos | Editar código, ler `src/`/`tests/` |
| 06 (Delivery) | Orquestra merge, lê reports | Editar código |

**Por que:** orquestradora editando código perde contexto limpo, revisão independente, separação de responsabilidades (viola ICM principle 1).

**Auto-correção** se perceber que está editando código:

1. Parar imediatamente.
2. Descrever fix necessário como prompt para subagent.
3. Despachar subagent implementer com a descrição.
4. Continuar fluxo normal de review.

---

## Cross-Cutting Rules

### Context Scoping
- Cada agente carrega SOMENTE o contexto listado na Inputs table do seu estágio.
- Subagentes recebem contexto ainda mais restrito: L0 + L2 do escopo + inputs explícitos.
- Ordem de leitura obrigatória: L0 → L1 → L2 → L3 → L4.
- L3 internalizada como restrição (`[L3:cfg]`). L4 processada como input (`[L4:in]`).

### Idioma e Nomenclatura
- Paths e identificadores: INGLÊS, lowercase, snake_case ou kebab-case.
- Conteúdo humano (docstrings, docs, reports): PORTUGUÊS.
- Commits: Conventional Commits em inglês.
- Nunca acento, cedilha ou espaço em nome de arquivo/pasta/função.

### Git
- Cada estágio que produz código tem commits pequenos.
- Nunca `--no-verify`.
- Mensagens em EN; corpo pode ter PT para decisões de negócio.
- Outputs de estágios são diffáveis e commitáveis. Commitar outputs após cada review gate aprovado.

### Secrets
- Nunca commitar `.env`, credenciais, API keys.
- Usar `.env.example` com placeholders.
- Leitura via env var only.

### Documentação
- `docs/lessons.md`: micro-retrospectiva ao final de cada sessão não-trivial.
- `docs/tech_debt.md`: atualizado quando dívida é identificada.
- `docs/decisions/NNNN-slug.md`: toda decisão arquitetural registrada.

---

## Workspace Builder (Meta-ICM)

ICM inclui padrão workspace-builder: workspace de 5 estágios cujo output é um novo workspace.

**Estrutura:**
1. Discovery: qual domínio e workflow?
2. Stage Mapping: onde estão os breakpoints naturais?
3. Scaffolding: criar estrutura de pastas com CONTEXT.md templates.
4. Questionnaire Design: que perguntas o workspace deve fazer?
5. Validation: pipeline roda end-to-end?

**Para usar:** quando template genérico não se aplica, criar workspace-builder customizado em `workspaces/NNN-slug-builder/`. Builder produz workspace final em `workspaces/NNN+1-slug/`.

---

## Local Profile Override

Se projeto tiver `.xp-profile.local.yaml` na raiz, respeitar overrides de `/xp-workflow` e `xp-icm-workflow`. Ver "Local profile override" no `/xp-workflow`.

---

## Extending the Skill

Quando uma nova skill é instalada no ecossistema ou usuário pede para incorporar nova capacidade ao workflow: ler `references/extending-skill.md` e seguir o checklist de 9 itens. Não tentar adicionar skill ao workflow sem esse checklist — referências dessincronizam silenciosamente.

---

## References

- `references/icm-paper-summary.md` — resumo do paper ICM (VanClief & McDermott, 2025)
- `references/xp-workflow-integration.md` — mapeamento de fases, stop points, CI gates entre `/xp-workflow` e ICM
- `references/superpowers-mapping.md` — tabela completa de qual superpowers usar em cada situação
- `references/stage-templates.md` — templates prontos de `CONTEXT.md` para os 6 estágios (copiar no Phase 0)
- `references/extending-skill.md` — checklist quando uma nova skill é incorporada ao ecossistema
- `references/example-run.md` — exemplo concreto de transição entre estágios (ancora mental)
- `references/changelog.md` — histórico completo de versões

---

## Version

v2.4.0 — atual. Histórico completo em `references/changelog.md`.
