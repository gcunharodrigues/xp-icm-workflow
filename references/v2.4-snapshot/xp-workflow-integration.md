# xp-workflow Integration

Como o xp-icm-workflow integra com o /xp-workflow em cada fase.

---

## Mapeamento de Fases

| Fase xp-workflow | Onde executa no ICM | Notas |
|---|---|---|
| Phase 0: Reconnaissance | Estágio 01 (Discovery) ou retomada de sessão | O ICM já fornece contexto via Layers 0-2. O Reconnaissance do xp-workflow lê `CLAUDE.md`, `docs/`, git log. |
| Phase 1: 4-block communication | Dentro de cada estágio | O ICM usa 4-block na Phase 1 do workflow. O xp-workflow usa 4-block internamente no Estágio 03. |
| Phase 2: Division of responsibilities | Implícito no ICM | A tabela de responsabilidades do ICM já cobre isso. O xp-workflow não precisa repetir. |
| Phase 3: Bootstrap or continuation | Phase 0 do ICM (Bootstrap) | O ICM gera a estrutura de pastas. O xp-workflow gera `src/`, `tests/`, `docs/` no projeto pai. |
| Phase 4: TDD cycles | Estágio 03 (Implementation) | Executado pelo xp-workflow DENTRO de subagentes. A orquestradora delega toda implementação — nunca executa xp-workflow diretamente. Subagentes rodam TDD cycles internamente. |
| Phase 5: Stop points | Estágio 02 e 03 | O ICM herda os stop points do xp-workflow. No Estágio 02, são apresentados como menu antes da implementação. No Estágio 03, subagentes gerenciam stop points internamente. Se um stop point arquitetural é atingido, o subagent retorna à orquestradora. |
| Phase 6: CI Gate | Estágio 03 (dentro dos subagentes) e Estágio 04 (Verification) | Subagentes rodam CI Gate por commit internamente. A orquestradora lê o resultado no implementation-report. O ICM roda verification gate no Estágio 04. |
| Phase 7: Pair check | Estágio 03 (dentro dos subagentes) | Segundo agente revisa código dentro do subagent. O ICM adiciona o Estágio 05 (Code Review) como verificação adicional. |
| Phase 8: Post-deploy | Estágio 06 (Merge & Delivery) + projeto pai | O xp-workflow gerencia post-deploy. O ICM entrega o projeto. |
| Phase 9: Tech debt dashboard | Estágio 03 + docs/tech_debt.md | O xp-workflow atualiza tech_debt.md. O ICM rastreia como Layer 3. |
| Phase 10: Self-revision | Fora do workflow normal | Disparado pelo usuário ("revisa a skill"). Não é parte de um estágio específico. |

---

## Stop Points: Mapeamento Cruzado

Os stop points obrigatórios do xp-workflow são aplicados em dois lugares no ICM:

1. **Estágio 02 (Design & Planning):** Stack, dados, API, dependência, serviço pago, decisão difícil de reverter. Apresentados como menu ao humano ANTES de implementar.

2. **Estágio 03 (Implementation):** Subagentes gerenciam stop points internamente (via /xp-workflow). Se um stop point é atingido durante implementação, o subagent para e pergunta. Se a decisão é arquitetural (requer voltar ao Estágio 02), o subagent retorna à orquestradora com a justificativa.

---

## CI Gates: Mapeamento Cruzado

| Gate | Quando roda | Quem gerencia |
|---|---|---|
| Format, lint, type, security, secrets, dep audit | Por commit (Phase 6 do xp-workflow) | /xp-workflow |
| Verification gate (Estágio 04) | Antes de code review | xp-icm-workflow |
| Code review (Estágio 05) | Antes de merge | xp-icm-workflow |
| Merge gate (Estágio 06) | Antes de entregar | xp-icm-workflow |

---

## Profile Matrix e Business Impact Tier

O xp-workflow define 10 perfis e 4 tiers. O ICM usa isso em dois lugares:

1. **Phase 0 (Bootstrap):** O tipo de projeto e tier determinam qual template ICM usar.
2. **Estágio 03 (Implementation):** O xp-workflow herda o perfil e tier do workspace para calibrar rigor.

O mapeamento de template para perfil:

| Template ICM | Perfil xp-workflow | Tier típico |
|---|---|---|
| `website-static` | N/A (não é código pesado) | experimental ou tool |
| `app-fullstack` | `app_web_backend` + `app_web_frontend` | development → production |
| `api-service` | `app_web_backend` | development → production |
| `agent-ia` | `agent_ia` | tool ou production |
| `dashboard` | `dashboard` | tool |
| `article-tech` | `technical_article` | experimental |
| `generic` | Inferido do 4-block | Inferido do 4-block |

---

## Error Recovery: Coordenação

Quando algo falha, a origem determina quem gerencia:

| Origem do erro | Quem gerencia | Protocolo |
|---|---|---|
| Dentro do xp-workflow (Estágio 03, via subagent) | xp-workflow Phase Error Recovery (dentro do subagent) | Subagent resolve internamente. Se não resolver, retorna erro à orquestradora. |
| Erro do subagent que não consegue resolver | Orquestradora + systematic-debugging | Orquestradora invoca debug skill ou delega correção para novo subagent com escopo limitado. |
| Orquestração entre estágios | xp-icm-workflow + systematic-debugging | Orquestradora invoca debug skill |
| Erro arquitetural (decisão do Estágio 02 incorreta) | xp-icm-workflow | Atualiza ADR, retorna ao Estágio 02 ou 03 |
| Erro de contexto (arquivo faltando, formato inesperado) | xp-icm-workflow | Fallback: inferir estado de outputs existentes |

---

## Princípio de Delegação

A orquestradora NUNCA lê código-fonte diretamente. Toda implementação é delegada a subagentes que executam /xp-workflow internamente.

**O que a orquestradora lê (compacto):**
- `implementation-report.md` — resumo do que foi feito (não o código-fonte)
- `verification-report.md` — resultado da verificação (não inspeção manual de código)
- `review-report.md` — resultado do code review (não leitura direta de src/)
- `plan.md`, `decisions.md`, ADRs — artefatos de design (estes sim são lidos diretamente)

**O que os subagentes e skills especializadas leem (completo):**
- `src/`, `tests/` — código-fonte completo
- CI gates output — resultado detalhado de format, lint, type, security, secrets, dep audit
- Pair check output — resultado detalhado da revisão por segundo agente

**Por que isso importa:**
- Reduz drasticamente os tokens na janela de contexto da orquestradora (ICM principle: cada agente carrega SOMENTE o contexto que precisa)
- A orquestradora opera em nível de abstração de relatórios e decisões, não de linhas de código
- Os subagentes recebem contexto focado (apenas sua task + ADRs relevantes), alinhado com o princípio ICM de context scoping

---

## Documentos Compartilhados

| Documento | Caminho | Quem escreve | Quem lê |
|---|---|---|---|
| `docs/decisions/NNNN-slug.md` | Projeto pai (Layer 3 após criação) | Estágio 02 | Todos os estágios posteriores |
| `docs/tech_debt.md` | Projeto pai (Layer 3) | Estágio 03 (subagentes) | Estágios 03, 04, 05 |
| `docs/lessons.md` | Projeto pai (Layer 3) | Todos os estágios | Retomada de sessão |
| `_config/xp-conventions.md` | Workspace (Layer 3) | Phase 0 | Estágios 02, 03, 04, 05 |
| `_config/project-rules.md` | Workspace (Layer 3) | Phase 0 | Todos os estágios |
| `stages/XX/CONTEXT.md` | Workspace (Layer 2) | Phase 0 (cria) + Estágio XX (atualiza Estado) | Estágio XX |
| `stages/XX/output/*.md` | Workspace (Layer 4) | Estágio XX | Estágio XX+1 |
| `stages/03/output/reports/task-*.md` | Workspace (Layer 4) | Cada subagent paralelo | Orquestradora (consolida) — **não lê src/** |
| `stages/03/output/implementation-report.md` | Workspace (Layer 4) | Orquestradora ou subagent consolidator | Orquestradora (Estágios 04, 05) — **não lê src/** |

> **Nota sobre Princípio de Delegação:** A orquestradora lê `implementation-report.md`, não o código-fonte. Subagentes e skills especializadas (verification, code review) leem o código-fonte diretamente.