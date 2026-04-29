# CONTEXT.md (Ubiquitous Language) — formato canônico

Adaptado de [mattpocock/skills/skills/engineering/grill-with-docs/CONTEXT-FORMAT.md].

## Estrutura

```markdown
---
layer: L3
scope: ubiquitous_language
workspace: "{{WORKSPACE}}"
---

# Ubiquitous Language — workspace {{WORKSPACE}}

## Language

**Order**:
A request from a Customer to fulfill goods/services.
_Avoid_: Purchase, transaction

**Invoice**:
A request for payment sent to a customer after delivery.
_Avoid_: Bill, payment request

**Customer**:
A person or organization that places orders.
_Avoid_: Client, buyer, account

## Relationships

- An **Order** produces one or more **Invoices**
- An **Invoice** belongs to exactly one **Customer**

## Example dialogue

> **Dev:** "When a **Customer** places an **Order**, do we create the **Invoice** immediately?"
> **Domain expert:** "No — an **Invoice** is only generated once a **Fulfillment** is confirmed."

## Flagged ambiguities

- "account" was used to mean both **Customer** and **User** — resolved: these are distinct concepts.
```

## Regras

- **Be opinionated.** Quando múltiplas palavras existem para o mesmo conceito,
  pick the best one e liste outras como aliases para evitar.
- **Flag conflicts explicitly.** Se um termo é usado ambiguamente, call it out
  em "Flagged ambiguities" com resolução clara.
- **Keep definitions tight.** One sentence max. Define what it IS, not what it does.
- **Show relationships.** Use bold term names e expresse cardinalidade quando óbvio.
- **Only include domain-specific terms.** Conceitos gerais de programação
  (timeouts, error types, utility patterns) NÃO pertencem aqui mesmo que o
  projeto use extensivamente. Antes de adicionar um termo, pergunte: é um
  conceito único deste contexto, ou um conceito genérico de programação?
  Apenas o primeiro pertence.
- **Group terms under subheadings** quando clusters naturais emergem.
- **Write an example dialogue.** Conversa entre dev e domain expert que
  demonstra como os termos interagem naturalmente e clarifica boundaries
  entre conceitos relacionados.

## Quando atualizar

- **Stage 01 (discovery):** sessão é grilling session. Cada termo resolvido
  → atualiza `<workspace>/_config/CONTEXT.md` **inline** (não batchear no fim).
- **Stage 02+ (design, waves, etc):** consomem o glossário ao escrever
  outputs. Se um novo termo emerge ou se um termo existente é refinado,
  atualizar inline e referenciar no commit message.
- **Stage 04 subagent context-injection:** lead injeta o `_config/CONTEXT.md`
  como L3 obrigatório. Subagent usa vocabulário ao escrever código + tests.

## Single-context vs multi-context

**Single context (maioria dos workspaces):** um único `<workspace>/_config/CONTEXT.md`.

**Multiple contexts (workspace cobre múltiplos bounded contexts distintos):**
um `_config/CONTEXT-MAP.md` lista os contexts e onde vivem. Cada subpath tem
seu próprio `CONTEXT.md`. Inferir a estrutura — se workspace é coeso, single
context; senão, criar map.

## Anti-padrões

- Listar termos genéricos (`http`, `cache`, `event-loop`) — não são domínio.
- Definições longas e prolixas — uma sentença basta.
- Múltiplas palavras para o mesmo conceito sem resolver qual é canônica.
- Atualização batched no fim do stage — perde contexto da resolução.
