---
name: requesting-code-review-200tok
source_skill: superpowers:requesting-code-review
source_version: "5.0.0"
purpose: Lead pede review do output do teammate antes de aceitar merge — pega problemas cedo, antes que cascateiem.
---

# Requesting Code Review — sumario 200tok

## Quando aplicar
- No estagio 06 (review) do ICM, lead avalia output do teammate apos o 05 verde.
- Apos cada task em subagent-driven development; antes de merge para main.
- Opcional: quando travado (perspectiva fresca), antes de refactor grande.

## Como aplicar
1. Capturar SHAs: `BASE_SHA=$(git rev-parse HEAD~1)` e `HEAD_SHA=$(git rev-parse HEAD)`.
2. Carregar `references/4-block-contract-template.md` do teammate como spec do que deveria ter sido entregue.
3. Rodar reviewer (subagente ou self-review estruturado) cobrindo 7 dimensoes: corretude, testes, seguranca, performance, legibilidade, aderencia ao contrato, riscos.
4. Gravar `review-report.md` no workspace do estagio com:
   - Strengths (o que esta bom)
   - Issues classificados **P0** (bloqueia merge), **P1** (corrige antes de prosseguir), **P2** (importante mas nao bloqueia), **P3** (nota para depois)
   - Veredito: APROVADO / FIX-LOOP / REJEITADO
5. Se P0/P1 existem → disparar fix loop (teammate volta ao 04 com `review-report.md`).

## Sinais de sucesso
- `review-report.md` referencia commits especificos (SHA + linhas).
- Cada issue tem severidade, justificativa tecnica e fix sugerido.
- Veredito explicito; nao deixar ambiguidade sobre "esta pronto?".

## Escape hatch
Mudanca trivial (typo, doc-only) → review pode ser inline no commit message. Mas: se tocar codigo de producao, sempre passar pelo review formal — nao pular por "e simples".

Ver `references/agent-team-protocol.md` para handoff lead↔teammate.
