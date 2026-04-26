# Stage Templates — xp-icm-workflow

Templates prontos para arquivos-raiz do workspace e para `stages/XX_nome/CONTEXT.md`. Copiar, colar e adaptar no Phase 0 (Bootstrap, passo 0.4-0.6) ou quando adicionar estágios customizados.

Templates de estágio incluem as **sete seções obrigatórias**: Estado, Skill, Inputs, Process, Outputs, Verify, Review Gate.

Convenção de prefixo usada nas Inputs:
- `[L3:cfg]` — Layer 3, internalizar como restrição (receita/config)
- `[L4:in]` — Layer 4, processar como input (ingrediente)

---

## Template: `CLAUDE.md` raiz do workspace (Layer 0 — Identidade)

Gerado no Passo 0.4-0.6 do Bootstrap. Define identidade do workspace, stack, regras. Todo agente que entrar no workspace lê este arquivo PRIMEIRO.

```markdown
# Workspace: <nome-do-projeto>

## Identidade
- **Slug:** <kebab-case-sem-acentos>
- **Data de criação:** YYYY-MM-DD
- **Tipo de projeto:** <website / app / api / agent-ia / dashboard / article / outro>
- **Business impact tier:** <experimental / tool / development / production>
- **Stack:** <linguagem + framework + banco + runtime>

## Objetivo (1 parágrafo)
<Descrição em PT do que este projeto faz e para quem.>

## Estrutura de Pastas do Workspace
- `CLAUDE.md` — este arquivo (L0: identidade)
- `CONTEXT.md` — estado atual e roteamento (L1)
- `stages/XX_nome/` — pastas numeradas, 1 por estágio (L2 contrato + L3 refs + L4 outputs)
- `_config/` — convenções e regras estáveis (L3: FÁBRICA)
- `docs/` — decisões, lessons, tech_debt (vinculado ao projeto pai)

## Regras de Prioridade (para este workspace)
1. Instruções do usuário (CLAUDE.md projeto pai, AGENTS.md, mensagens diretas) — vencem.
2. `/xp-icm-workflow` — orquestração.
3. Skills especializadas (`/xp-workflow`, `superpowers:*`) — vencem no escopo delas.
4. Default system prompt — perde.

## Ordem de Leitura Obrigatória
Todo agente ao entrar neste workspace lê, nesta ordem:
1. Este arquivo (L0)
2. `CONTEXT.md` raiz (L1)
3. `stages/XX/CONTEXT.md` do estágio atual (L2)
4. SOMENTE os arquivos listados na Inputs table do estágio (L3 e L4)

Nunca pular esta ordem. Nunca ler arquivos fora da Inputs table.

## Regras Específicas deste Workspace
<Adicionar regras específicas do projeto se houver — ex: "conteúdo em PT-BR", "API usa FastAPI", "banco é SQLite".>
```

---

## Template: `CONTEXT.md` raiz do workspace (Layer 1 — Estado e Roteamento)

Gerado no Passo 0.4-0.6 do Bootstrap. **Atualizado ao final de cada estágio** via Stage Transition Checklist: append no histórico + atualizar campo `STAGE` para apontar ao PRÓXIMO estágio como `IN_PROGRESS` (ou `COMPLETED` se for o último). É o arquivo de estado que permite retomada de sessão.

```markdown
# Contexto do Workspace <slug>

## Estado Atual
- **STAGE:** 00_BOOTSTRAP
- **STATUS:** IN_PROGRESS
- **Atualizado em:** YYYY-MM-DD

## Histórico de Estágios Completados
<!-- Append 1 linha por estágio completado, com data, status e outputs -->
<!-- Formato: | YYYY-MM-DD | 01_discovery | COMPLETED | discovery.md | -->

| Data | Estágio | Status | Outputs |
|---|---|---|---|
| | | | |

## Roteamento
Fluxo configurado (dos templates ICM):
01_discovery → 02_design → 03_implementation → 04_verification → 05_review → 06_merge

## Retomada
Ao retomar este workspace em sessão futura:
1. Ler este arquivo primeiro para saber em qual estágio parou (ver `STAGE` acima).
2. Seguir o Layer Loading Protocol: L0 → L1 (este) → L2 → L3 → L4.
3. Ler SOMENTE os arquivos listados na Inputs table do estágio atual.

**Se este arquivo estiver corrompido ou sem STAGE:** inferir o estado pela existência de arquivos em `stages/XX/output/`. Último estágio com output completo = completado; próximo sem output = atual.
```

---

## Template: Estágio 01 (Discovery)

```markdown
# Estágio 01: Discovery

## Estado
- **STATUS:** IN_PROGRESS / COMPLETED
- **Data:** (preencher ao completar)
- **Outputs:** (preencher ao completar)

## Skill a Invocar
superpowers:brainstorming

## Inputs
- [L4:in] Nenhum — ideia veio do prompt inicial
- [L3:cfg] `_config/project-brief.md` — brief inicial (se houver)
- IGNORAR: outputs de estágios subsequentes, ADRs (não existem ainda)

## Process
1. Ler Layers 0→1→2 em ordem.
2. Carregar SOMENTE os inputs listados acima.
3. Invocar `Skill({skill: "superpowers:brainstorming"})`.
4. Explorar:
   - Público-alvo e necessidades
   - Requisitos funcionais (o que o sistema faz)
   - Requisitos não-funcionais (performance, segurança, escala)
   - Alternativas de solução (menu se houver tradeoffs)
   - MVP: IN vs OUT nesta primeira versão
   - Riscos e restrições
   - Métricas de sucesso
5. Sintetizar em markdown estruturado.

## Outputs
- `output/discovery.md` com:
  - Resumo executivo (3-5 frases)
  - Requisitos funcionais (lista)
  - Requisitos não-funcionais (lista)
  - Alternativas consideradas (se houver menu)
  - Definição de MVP (escopo desta entrega)
  - Riscos e mitigações
  - Métricas de validação

## Verify
- Consistência interna: requisitos funcionais cobrem o MVP definido.
- Alternativas consideradas são mutualmente exclusivas.
- Critério: cada requisito funcional do MVP aparece no resumo executivo.

## Review Gate
- Humano lê `output/discovery.md` e edita se necessário.
- Se humano faz edições recorrentes, sugerir atualizar `_config/project-brief.md` ou este `CONTEXT.md`.
- Aplicar Stage Transition Checklist antes de prosseguir.
```

---

## Template: Estágio 02 (Design & Planning)

```markdown
# Estágio 02: Design & Planning

## Estado
- **STATUS:** IN_PROGRESS / COMPLETED
- **Data:** (preencher ao completar)
- **Outputs:** (preencher ao completar)

## Skill a Invocar
superpowers:writing-plans

## Inputs
- [L4:in] `../01_discovery/output/discovery.md` — seção Requisitos MVP e Alternativas; IGNORAR seção Métricas
- [L3:cfg] `../../_config/xp-conventions.md` — restrição de estilo e convenções
- [L3:cfg] `../../docs/tech_debt.md` — padrões a evitar
- IGNORAR: ADRs de outros projetos, outputs de estágios 03+

## Process
1. Ler Layers 0→1→2 em ordem.
2. Carregar SOMENTE os inputs listados acima. L3 como restrição, L4 como input.
3. Invocar `Skill({skill: "superpowers:writing-plans"})`.
4. Criar plano detalhado com:
   - Decisões arquiteturais (menu se não-trivial)
   - Modelagem de dados (tabelas, schemas, collections)
   - Contratos de API (endpoints, request/response)
   - Divisão em steps/sub-tasks
   - Estimativa de steps
   - Stop points obrigatórios
5. Registrar decisões em formato ADR em `../../docs/decisions/NNNN-slug.md` (fonte da verdade).
6. Gerar `output/decisions.md` como **INDEX** (títulos e slugs; não duplicar conteúdo).

## Stop Points Obrigatórios
Parar e apresentar menu se houver:
- Mudança de stack/framework/banco
- Modelagem de dados nova
- API pública nova
- Nova dependência
- Novo serviço pago recorrente
- Decisão difícil de reverter

## Outputs
- `output/plan.md` — plano completo
- `output/decisions.md` — INDEX de decisões (títulos/slugs/status)
- `../../docs/decisions/NNNN-slug.md` — ADR formal (fonte da verdade)

## Verify
- Consistência entre `output/plan.md` e `../01_discovery/output/discovery.md`: cada requisito do MVP aparece no plano OU está explicitamente deferred.
- `output/decisions.md` referencia todos os ADRs criados.
- Critério: cada requisito funcional do discovery é coberto por pelo menos 1 step no plano.

## Review Gate
- Humano revisa o plano e as decisões.
- Se humano ajusta profundidade/formato do plano, atualizar este `CONTEXT.md` ou `_config/project-rules.md`.
- Aplicar Stage Transition Checklist antes de prosseguir.
```

---

## Template: Estágio 03 (Implementation)

```markdown
# Estágio 03: Implementation

## Estado
- **STATUS:** IN_PROGRESS / COMPLETED
- **Data:** (preencher ao completar)
- **Outputs:** (preencher ao completar)

## Skill (orquestradora)
superpowers:subagent-driven-development (SEMPRE — toda implementação é delegada)

## Skill (por subagent)
/xp-workflow

> **Princípio de Delegação:** A orquestradora NUNCA escreve código nem lê código-fonte diretamente. Toda implementação é delegada a subagentes que executam `/xp-workflow` internamente. A orquestradora lê SOMENTE os `output/reports/task-*.md` individuais (escritos por cada subagent) e/ou o `implementation-report.md` consolidado — L4 compacto. Isso mantém a janela de contexto enxuta e alinha com o princípio ICM de context scoping.

## Inputs (orquestradora lê SOMENTE estes — NÃO lê src/ ou tests/)
- [L4:in] `../02_design/output/plan.md` — preparar prompts de delegação
- [L4:in] `../02_design/output/decisions.md` — sumário para escopo dos subagentes
- [L3:cfg] `../../docs/decisions/` — SOMENTE ADRs listados no plan; IGNORAR demais
- [L3:cfg] `../../docs/tech_debt.md` — padrões a evitar
- [L3:cfg] `../../docs/lessons.md` — lições a aplicar
- [L3:cfg] `../../_config/xp-conventions.md` — convenções de código
- NÃO LER (orquestradora): `src/`, `tests/`, qualquer código-fonte
- IGNORAR: `../01_discovery/output/` (já consumido pelo Estágio 02)

## Process
1. Ler Layers 0→1→2 em ordem.
2. Carregar SOMENTE os inputs listados acima. L3 como restrição, L4 como input.
3. Analisar o plano para identificar tasks independentes vs dependentes.
4. Delegar CADA task para um subagent via `Skill({skill: "superpowers:subagent-driven-development"})`.
5. Cada subagent recebe SOMENTE (ver Protocolo de Delegação no SKILL.md principal):
   - Caminho relativo ao workspace
   - Seção relevante do plano e decisões
   - ADRs relevantes à sua task APENAS
   - Convenções e tech_debt
   - Regras explícitas de Stop Point
6. Subagentes executam `/xp-workflow` internamente (TDD, CI Gate, Pair Check). Cada subagent escreve em `output/reports/task-<slug>.md` (arquivo próprio, sem race).
7. Após todos os subagentes completarem: orquestradora lê **SOMENTE** os `output/reports/task-*.md` individuais e consolida em `output/implementation-report.md` (ou delega a um subagent "consolidator").
8. Se qualquer task-report indica falha: invocar `superpowers:systematic-debugging` ou delegar correção para novo subagent com escopo limitado.

## Outputs
- Código em `src/` do projeto pai (escrito pelos subagentes)
- Testes em `tests/` do projeto pai (escritos pelos subagentes)
- `output/reports/task-<slug>.md` — 1 arquivo por subagent (escrito pelos subagentes paralelos sem race)
- `output/implementation-report.md` — consolidação dos reports individuais (escrito pela orquestradora ou subagent "consolidator" após todos completarem)
- `../../docs/lessons.md` atualizado (pelos subagentes)
- `../../docs/tech_debt.md` atualizado se aplicável

## Verify
- Consistência entre `output/implementation-report.md` (consolidado) e `../02_design/output/plan.md`: cada step do plano foi implementado ou explicitamente deferred.
- Cada `output/reports/task-<slug>.md` indica CI Gate verde, sem secrets hardcoded.
- Critério: cobertura de testes atende ao plano, todos os CI gates passaram conforme reportado em todos os task-reports.
- **NÃO verificar inspecionando código-fonte** — confiar nos reports e nos CI gates dos subagentes.

## Review Gate
- Orquestradora lê SOMENTE os `reports/task-*.md` individuais e/ou `implementation-report.md` consolidado (nunca o código-fonte).
- Humano revisa o código diretamente no repositório (ou confia no CI + pair check dos subagentes).
- Se humano consistentemente corrige o mesmo padrão, sugerir atualizar `_config/xp-conventions.md` ou este `CONTEXT.md`.
- Aplicar Stage Transition Checklist antes de prosseguir.
```

---

## Template: Estágio 04 (Verification)

```markdown
# Estágio 04: Verification

## Estado
- **STATUS:** IN_PROGRESS / COMPLETED
- **Data:** (preencher ao completar)
- **Outputs:** (preencher ao completar)

## Skill a Invocar
superpowers:verification-before-completion

> **Princípio de Delegação aplicado:** Orquestradora lê `implementation-report.md` para saber O QUE foi feito, não COMO. Verificação técnica (inspeção de código, CI gates, testes) é responsabilidade do skill de verificação. Orquestradora compara report contra plano e ADRs.

## Inputs (orquestradora lê SOMENTE estes — NÃO lê src/ ou tests/)
- [L4:in] `../03_implementation/output/implementation-report.md` — verificar o que foi implementado
- [L4:in] `../02_design/output/plan.md` — comparar report contra plano
- [L3:cfg] `../../docs/decisions/` — SOMENTE ADRs referenciados no plano
- [L3:cfg] `../../_config/xp-conventions.md` — restrição de convenções
- NÃO LER (orquestradora): `src/`, `tests/`, código-fonte. Inspeção é feita pelo skill de verificação.
- IGNORAR: `../01_discovery/output/`

## Process
1. Ler Layers 0→1→2 em ordem.
2. Carregar SOMENTE os inputs listados acima.
3. Ler `../03_implementation/output/implementation-report.md`.
4. Ler `../02_design/output/plan.md` para saber o que deveria ter sido implementado.
5. Ler ADRs relevantes para verificar conformidade arquitetural.
6. Invocar `Skill({skill: "superpowers:verification-before-completion"})` — este skill lê o código-fonte diretamente.
7. Verificar:
   - O implementation-report cobre todos os itens do plano?
   - Os ADRs foram respeitados (conforme reportado)?
   - O 4-block de validação foi atendido?
   - CI Gate verde, sem secrets hardcoded (conforme reportado)

## Outputs
- `output/verification-report.md`
- Status: PASS / CONDITIONAL / FAIL

## Verify
- Cross-stage: cada requisito do `../01_discovery/output/discovery.md` é coberto pelo plano e reportado como implementado.
- `output/verification-report.md` não contradiz `../03_implementation/output/implementation-report.md`.
- Critério: zero P0 issues, CI verde, cobertura atende ao 4-block de validação.

## Review Gate
- Humano revisa relatório.
- Se FAIL: retornar ao Estágio 03.
- Se PASS/CONDITIONAL: prosseguir para Estágio 05.
- Se verificação encontrou padrão recorrente de falha, sugerir atualizar `stages/03_implementation/CONTEXT.md` ou `_config/xp-conventions.md`.
- Aplicar Stage Transition Checklist antes de prosseguir.
```

---

## Template: Estágio 05 (Code Review)

```markdown
# Estágio 05: Code Review

## Estado
- **STATUS:** IN_PROGRESS / COMPLETED
- **Data:** (preencher ao completar)
- **Outputs:** (preencher ao completar)

## Skill Principal
superpowers:requesting-code-review

## Skill (se feedback externo)
superpowers:receiving-code-review

> **Princípio de Delegação aplicado:** Orquestradora lê relatórios compactos (`implementation-report.md`, `verification-report.md`, `plan.md`), não código-fonte. O skill de code review lê o código internamente.

## Inputs (orquestradora lê SOMENTE estes — NÃO lê src/ ou tests/)
- [L4:in] `../03_implementation/output/implementation-report.md` — saber o que foi implementado
- [L4:in] `../04_verification/output/verification-report.md` — saber se passou nos gates
- [L4:in] `../02_design/output/plan.md` — comparar implementação contra plano
- [L4:in] `../02_design/output/decisions.md` — sumário de decisões
- [L3:cfg] `../../docs/decisions/` — SOMENTE ADRs referenciados no plano
- [L3:cfg] `../../docs/tech_debt.md` — identificar novos débitos
- NÃO LER (orquestradora): `src/`, `tests/`, código-fonte
- IGNORAR: `../01_discovery/output/`

## Process
1. Ler Layers 0→1→2 em ordem.
2. Carregar SOMENTE os inputs listados acima.
3. Ler implementation-report, verification-report, plan, decisions (L4).
4. Ler ADRs formais e tech_debt (L3).
5. Invocar `Skill({skill: "superpowers:requesting-code-review"})` — este skill lê o código-fonte diretamente.
6. Reviewer compara implementação contra:
   - Plano do Estágio 02
   - ADRs formais
   - Convenções do `/xp-workflow`
   - 4-block de validação
7. Dimensões: correctness, security, test quality, design, standards, readability, performance.
8. Se houver feedback externo: invocar `Skill({skill: "superpowers:receiving-code-review"})`.

## Outputs
- `output/review-report.md`
- Lista de ajustes (se houver)
- `../../docs/tech_debt.md` atualizado se novos débitos foram identificados

## Verify
- `output/review-report.md` cobre todas as 7 dimensões.
- Cada P0 issue é rastreável a um requisito no plano ou ADR.
- Critério: zero P0 blocking, P1 documentados em `tech_debt.md`.

## Review Gate
- Humano aprova ajustes ou decide ignorar.
- Se houver ajustes P0/P1: aplicar Fix Loop Protocol (ver SKILL.md principal).
- Se review identificou padrão sistêmico, sugerir atualizar `_config/xp-conventions.md` ou `stages/03_implementation/CONTEXT.md`.
- Aplicar Stage Transition Checklist antes de prosseguir.
```

---

## Template: Estágio 06 (Merge & Delivery)

```markdown
# Estágio 06: Merge & Delivery

## Estado
- **STATUS:** IN_PROGRESS / COMPLETED
- **Data:** (preencher ao completar)
- **Outputs:** (preencher ao completar)

## Skill a Invocar
superpowers:finishing-a-development-branch

## Inputs
- [L4:in] `../05_review/output/review-report.md` — considerar ajustes finais
- [L4:in] `../04_verification/output/verification-report.md` — confirmar status PASS
- IGNORAR: outputs de estágios 01-03. Para contexto arquitetural, ler SOMENTE ADRs relevantes.

## Process
1. Ler Layers 0→1→2 em ordem.
2. Carregar SOMENTE os inputs listados acima.
3. Confirmar status PASS no `verification-report.md` antes de prosseguir.
4. Considerar ajustes finais do `review-report.md`.
5. Invocar `Skill({skill: "superpowers:finishing-a-development-branch"})`.
6. Apresentar menu:
   - Opção A: Merge direto (se branch isolada, CI verde)
   - Opção B: Pull Request (se repo compartilhado)
   - Opção C: Tag de release (se production tier)
   - Opção D: Cleanup de branches temporárias
7. Executar escolha do humano.
8. Atualizar `docs/lessons.md` e `docs/tech_debt.md`.

## Outputs
- `output/delivery-report.md`
- Branch integrada ou PR criado

## Verify
- `../04_verification/output/verification-report.md` tem status PASS.
- `../05_review/output/review-report.md` não tem P0 pendentes.
- Critério: CI verde, P0 resolvidos, delivery-report completo.

## Review Gate
- Humano confirma satisfação.
- Marcar workspace como completo.
- Aplicar Stage Transition Checklist final.
```
