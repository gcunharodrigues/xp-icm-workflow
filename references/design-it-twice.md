# Design It Twice — parallel interface design

Adaptado de [mattpocock/skills/skills/engineering/improve-codebase-architecture/INTERFACE-DESIGN.md].

Para módulos core em stage 02 (design), spawnar **3+ subagents em paralelo**
com constraints distintos. Comparar antes de commitar interface. Baseado em
"Design It Twice" (Ousterhout, *A Philosophy of Software Design*) — primeira
ideia raramente é a melhor.

## Quando aplicar

- Módulo marcado `core: true` no plan.md (decisão arquitetural meaningful)
- Interface terá múltiplos callers / public surface
- Lock-in alto (refactor depois custa quarter+)
- Não aplicável: módulos triviais, single-caller, glue code

## Processo

### 1. Frame the problem space

Antes de spawn, escreva user-facing explanation da problem space:
- Constraints que qualquer interface satisfaria
- Dependencies (categorize: in-process / local-substitutable / remote-owned / true-external)
- Code sketch ilustrativo (não proposal — só ground constraints)

Mostre ao user, depois proceed para Step 2 (user lê enquanto subagents trabalham).

### 2. Spawn 3+ subagents em paralelo

Use `Agent` tool com 3+ chamadas paralelas. Cada subagent tem **constraint
diferente** (briefs separados, mas todos referenciam CONTEXT.md + ADRs):

- **Agent 1:** "Minimize interface — 1-3 entry points max. Maximize leverage por entry point."
- **Agent 2:** "Maximize flexibility — support many use cases + extension."
- **Agent 3:** "Optimize common caller — default case trivial."
- **Agent 4 (se aplicável):** "Design around ports & adapters para cross-seam dependencies."

Cada subagent retorna:
1. Interface (types, methods, params + invariants, ordering, error modes)
2. Usage example mostrando como callers usam
3. O que implementação esconde behind seam
4. Dependency strategy + adapters
5. Trade-offs — onde leverage é alto, onde é thin

### 3. Present and compare

Apresenta designs sequencialmente para user absorver cada um. Compare em
prosa por:
- **Depth** — leverage no interface (deep = high leverage)
- **Locality** — onde change concentra
- **Seam placement** — onde behavior pode ser altered

Após comparação, dê **opinionated recommendation**: qual design é mais forte
e por quê. Se elements de designs diferentes combinam bem, propor hybrid.

User wants strong read, not menu.

## Output em stage 02

`stages/02_design/output/design-alternatives-<module>.md`:

```markdown
# Design Alternatives — <module name>

## Problem space
<constraints, dependencies, code sketch>

## Alternative 1 — Minimal interface
<interface, usage, hidden complexity, trade-offs>

## Alternative 2 — Maximum flexibility
<...>

## Alternative 3 — Optimize common caller
<...>

## Comparison
| Aspect | Alt 1 | Alt 2 | Alt 3 |
|---|---|---|---|
| Depth | high | medium | medium |
| Locality | tight | spread | tight |
| Seam | external | internal | external |

## Recommendation
<opinionated pick, ou hybrid proposal, com razões>
```

`decisions.md` lista a decisão final (com link). Pode virar ADR se passar
3-criteria gate (ver `references/adr-format.md`).

## Anti-padrões

- Spawnar 3 subagents com mesmo prompt — não vai produzir diversidade.
- Aplicar a TODO módulo — overhead. Reservar para core decisions.
- Usar como menu (escolha do user) — agent deve ter opinião.
- Pular Step 1 (problem space) — subagents trabalham com constraints diferentes do user.
