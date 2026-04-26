# Superpowers Skills Mapping

Tabela completa de qual skill do superpowers usar em cada situação dentro do xp-icm-workflow.

---

## Mapeamento por Estágio

| Estágio ICM | Skill do Superpowers | Quando invocar | Contexto a passar |
|---|---|---|---|
| 01 Discovery | `superpowers:brainstorming` | Sempre que o projeto é novo ou há ambiguidade no escopo | 4 blocos da Phase 1 + referências em `_config/` |
| 02 Design & Planning | `superpowers:writing-plans` | Após discovery aprovado, ou quando a tarefa veio com escopo claro | Discovery output + decisões pendentes |
| 03 Implementation | `superpowers:subagent-driven-development` | **Sempre** (toda implementação é delegada a subagentes) | Plano + convenções + ADRs relevantes (scoping restrito) |
| 03 Implementation | `/xp-workflow` (executado POR subagentes, não pela orquestradora) | Dentro de cada subagent no Estágio 03 | Plano (seção da task) + ADRs relevantes + tech_debt + conventions (escopo restrito à task). `docs/lessons.md` é lido pela orquestradora para extrair lições aplicáveis e injetar no prompt do subagent — subagents não leem `lessons.md` diretamente |
| 04 Verification | `superpowers:verification-before-completion` | Antes de declarar "pronto" | Implementation report + plano + ADRs (orquestradora lê reports, skill lê código-fonte) |
| 05 Code Review | `superpowers:requesting-code-review` | Após verification aprovada | Implementation report + verification report + plano + decisões + tech_debt (orquestradora lê reports, skill lê código-fonte) |
| 05 Code Review | `superpowers:receiving-code-review` | Se houver feedback externo | Feedback + contexto do review |
| 06 Merge & Delivery | `superpowers:finishing-a-development-branch` | Após review aprovado | Verification report + review report |

---

## Mapeamento por Situação Transversal

| Situação | Skill | Quando |
|---|---|---|
| Bug, teste falhando, output inesperado | `superpowers:systematic-debugging` | Quando um estágio falha ou produz output inesperado |
| Feature nova, componente novo, mudança de comportamento | `superpowers:brainstorming` | Antes de implementar qualquer feature não-trivial |
| Plano de implementação para tarefa multi-step | `superpowers:writing-plans` | Antes de escrever código |
| Múltiplas tasks independentes | `superpowers:subagent-driven-development` | **Sempre** no Estágio 03 (toda implementação é delegada). Fora do Estágio 03, quando o plano tem 2+ tasks sem dependência entre si |
| Código pronto, testes passando | `superpowers:verification-before-completion` | Antes de commit ou PR |
| Revisão de código antes de merge | `superpowers:requesting-code-review` | Após verificação |
| Recebendo feedback de review | `superpowers:receiving-code-review` | Quando feedback externo chega |
| Branch pronta para integrar | `superpowers:finishing-a-development-branch` | Quando tudo está aprovado |
| Criando nova skill | `superpowers:writing-skills` | Quando o usuário pede para criar/editar skills |
| Feature ou bugfix com TDD | `superpowers:test-driven-development` | Antes de escrever implementação |
| Trabalho em branch isolado | `superpowers:using-git-worktrees` | Quando precisa isolamento do workspace atual |

---

## Regras de Invocação

1. **Uma skill por vez por estágio.** Não invocar duas skills no mesmo estágio simultaneamente (exceto implementation com subagents). No Estágio 03, `subagent-driven-development` é SEMPRE invocado pela orquestradora, e `/xp-workflow` roda DENTRO dos subagentes.
2. **A orquestradora decide QUANDO carregar.** A skill especializada executa suas regras internas. Conflitos: skill especializada vence no seu escopo.
3. **Context scoping se aplica a skills também.** Quando invocar uma skill do superpowers, passar SOMENTE o contexto listado na Inputs table do estágio, não o workspace inteiro.
4. **Princípio de Delegação: a orquestradora NUNCA lê código-fonte diretamente.** Nos Estágios 03, 04 e 05, a orquestradora lê SOMENTE relatórios compactos (`reports/task-*.md` individuais dos subagents paralelos, `implementation-report.md` consolidado, `verification-report.md`, `review-report.md`, `plan.md`, `decisions.md`). O código-fonte é lido SOMENTE por skills especializadas internamente (verification, code review) ou por subagentes.
5. **Subagentes recebem contexto mais restrito que a orquestradora.** Ver seção "Context Scoping para Subagentes" e "Protocolo de Delegação" no SKILL.md principal.
6. **Nunca pular a ordem de leitura.** Layer 0 → 1 → 2 → 3 → 4, sempre.