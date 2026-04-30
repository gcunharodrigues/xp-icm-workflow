# AGENT-BRIEF Template — formato canônico

Adaptado de [mattpocock/skills/skills/engineering/triage/AGENT-BRIEF.md].

## Princípios

### 1. Durability over precision
Subagent pode rodar minutos ou dias depois do brief escrito. Codebase pode mudar.
Brief deve permanecer útil mesmo com renames/refactors.
- **Faça:** descrever interfaces, types, contratos comportamentais.
- **Não faça:** referenciar paths absolutos, line numbers, estrutura interna corrente.

### 2. Behavioral, not procedural
Descreva **o que** o sistema deve fazer, não **como** implementar.
- **Bom:** "When `/triage` runs com no args, mostra summary de issues needing attention"
- **Ruim:** "Add switch statement on line 42 of handler.ts"

### 3. Complete acceptance criteria
Subagent precisa saber quando terminou. Critérios concretos, testáveis,
independentemente verificáveis.
- **Bom:** "`gh issue list --label needs-triage` returns issues que passaram inicial classification"
- **Ruim:** "Triage should work correctly"

### 4. Explicit scope boundaries
Diga explicitamente o que está fora de escopo. Previne gold-plating e
assumptions sobre features adjacentes.

## Template

```markdown
## Agent Brief

**Category:** bug / enhancement
**Summary:** one-line description of what needs to happen

**Current behavior:**
What happens now. Bugs: broken behavior. Enhancements: status quo.

**Desired behavior:**
What should happen after agent's work is complete. Be specific about edge
cases and error conditions.

**Key interfaces:**
- `TypeName` — what needs to change and why
- `functionName()` return type — what it currently returns vs what it should return
- Config shape — any new configuration options needed

**Acceptance criteria:**
- [ ] Specific, testable criterion 1
- [ ] Specific, testable criterion 2
- [ ] Specific, testable criterion 3
- [ ] `git log --oneline main..HEAD` ≥1 commit (branch persiste o trabalho — não retornar Status COMPLETE com zero commits).

**Out of scope:**
- Thing that should NOT be changed or addressed in this issue
- Adjacent feature that might seem related but is separate
```

## Mapping para 4-block do plan.md

O 4-block existente do plan.md (`O QUE / COMO / NÃO QUERO / VALIDAÇÃO`)
mapeia para AGENT-BRIEF da seguinte forma:

| 4-block | AGENT-BRIEF |
|---|---|
| **O QUE** | Summary + Current/Desired behavior |
| **COMO** | Key interfaces (não procedimental) |
| **NÃO QUERO** | Out of scope |
| **VALIDAÇÃO** | Acceptance criteria |

Stage 02 (design) escreve plan.md no formato 4-block. Stage 04 (lead session)
gera AGENT-BRIEF a partir da seção da task no plan.md via
`scripts/agent-brief-render.py`.

## Antes de retornar summary ao lead

Subagent (AFK) DEVE verificar antes de declarar Status COMPLETE no task report:

- [ ] `git log --oneline main..HEAD` mostra ≥1 commit (≠ zero).
- [ ] working tree clean OR remaining files explicitamente declarados.
- [ ] task report escrito em path absoluto.

Origem: incidente sessao-recorrencia (workspace 001 wave 6) — subagent terminou
TDD 7 passos sem `git commit`, branch HEAD = main HEAD, working tree dirty.
Lead recovery teve que salvar trabalho manualmente. Gate explícito previne
recorrência.

## Anti-padrões

- **File paths absolutos** (`src/triage/handler.ts:42`) — vão stale.
- **Line numbers** — mesma razão.
- **Vagueness** ("the triage thing is broken", "fix it") — agent não sabe o que fazer.
- **Sem acceptance criteria** — agent não sabe quando terminou.
- **Sem scope boundary** — agent gold-plata ou modifica features adjacentes.
- **Procedimental** ("open file X, line Y, change Z") — quebra ao primeiro refactor.
- **Async pytest desnecessário**: `Bash run_in_background=true + Monitor` pra pytest <5min é overkill; use Bash síncrono. Reserve async pra builds/dev-servers longos.
