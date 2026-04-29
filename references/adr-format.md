# ADR Format — formato canônico (3-critérios gate)

Adaptado de [mattpocock/skills/skills/engineering/grill-with-docs/ADR-FORMAT.md].

ADRs vivem em `<project_root>/docs/decisions/` e usam numeração sequencial:
`0001-slug.md`, `0002-slug.md`, etc.

## Gate de 3 critérios

**Só crie ADR se TODOS os 3 são verdade:**

1. **Hard to reverse** — custo de mudar de ideia depois é meaningful.
2. **Surprising without context** — leitor futuro vai olhar o código e perguntar
   "por que diabos fizeram desse jeito?"
3. **Result of a real trade-off** — havia alternativas genuínas e você
   escolheu uma por razões específicas.

Se algum dos 3 falha, **NÃO crie ADR**. A decisão entra em `decisions.md` como
nota.

- Decisão fácil de reverter? Vai ser revertida sem ADR — skip.
- Não surpreende? Ninguém vai perguntar — skip.
- Sem alternativa real? Nada para registrar — skip.

## Template

```md
# {Short title of the decision}

{1-3 sentences: what's the context, what did we decide, and why.}
```

Esse é o template completo. Um ADR pode ser um único parágrafo. O valor está em
registrar **que** uma decisão foi tomada e **por quê** — não em preencher
sections.

## Sections opcionais

Inclua apenas quando agregam valor genuíno. Maioria dos ADRs não vai precisar.

- **Status** frontmatter (`proposed | accepted | deprecated | superseded by ADR-NNNN`) — útil quando decisões são revisitadas
- **Considered Options** — só quando alternativas rejeitadas merecem ser lembradas
- **Consequences** — só quando efeitos downstream não-óbvios precisam destaque

## Numeração

Scan `docs/decisions/` para o maior número existente, increment by one.

## O que qualifica como ADR

- **Architectural shape.** "Monorepo." "Write model é event-sourced, read model
  projetado em Postgres."
- **Integration patterns entre contexts.** "Ordering e Billing comunicam via
  domain events, não synchronous HTTP."
- **Tech choices que carregam lock-in.** Database, message bus, auth provider,
  deployment target. Não toda library — só as que tomariam quarter para trocar.
- **Boundary e scope decisions.** "Customer data é owned by Customer context;
  outros contexts referenciam por ID only." Os "no-s" explícitos valem tanto
  quanto os "yes-s".
- **Deliberate deviations da obvious path.** "SQL manual em vez de ORM porque X."
  Anything onde leitor razoável assumiria o oposto.
- **Constraints not visible in code.** "Não podemos usar AWS por compliance."
  "Response time deve ser <200ms por contrato com partner API."
- **Rejected alternatives quando rejection é non-obvious.** Considerou GraphQL e
  picked REST por razões sutis — registre, ou alguém vai sugerir GraphQL again
  em 6 meses.

## O que NÃO qualifica

- Pequenas decisões de estilo (tab vs space)
- Library escolhas pequenas (lodash vs ramda)
- Decisões fáceis de reverter (escolha de framework de log)
- Decisões óbvias (não havia alternativa real)
- Coisas auto-evidentes do código

## decisions.md vs ADRs individuais

- `<workspace>/stages/02_design/output/decisions.md` — **índice + notas curtas**
  de decisões que NÃO passam pelo gate (decisões pequenas, raciocínio breve).
- `<project_root>/docs/decisions/NNNN-slug.md` — ADRs individuais para
  decisões que passam o gate.

decisions.md tem seções: `## ADRs criados (links)` + `## Notas (decisões que
não viraram ADR)`.
