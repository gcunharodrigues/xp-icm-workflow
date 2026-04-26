---
name: test-driven-development-200tok
source_skill: superpowers:test-driven-development
source_version: "5.0.0"
purpose: Garantir que todo código de produção nasça de um teste que falhou primeiro.
---

# Test-Driven Development — sumário 200tok

## Quando aplicar
- Toda nova feature, bugfix, refactor ou mudança de comportamento.
- Sempre que houver código de produção a escrever.

## Lei de ferro
Sem teste falhando antes, sem código de produção. Escreveu código antes? Apaga e recomeça. "Manter como referência" é racionalização.

## Como aplicar
Use o ciclo TDD canônico já documentado neste workspace em `references/4-block-contract-template.md` (RED → GREEN → CI → REFACTOR → CI → Auto-QA Akita 15-item → COMPLETE).

Resumindo o essencial:

1. **RED** — escreva um teste mínimo, nome claro, um comportamento só, código real (sem mock se evitável).
2. **Verifique RED** — rode o teste e confirme que falha pelo motivo certo (feature ausente, não typo).
3. **GREEN** — escreva o mínimo de código que faz passar. Sem YAGNI, sem flags extras.
4. **Verifique GREEN** — teste passa, demais testes passam, output limpo.
5. **REFACTOR** — só após verde; remova duplicação, melhore nomes, mantenha verde.
6. **Próximo ciclo.**

## Sinais de sucesso
- Vi cada teste falhar antes da implementação.
- Falhou pelo motivo esperado.
- Código mínimo, sem features não pedidas.
- Output pristine, demais testes verdes.

## Red flags (parar e recomeçar)
"Testo depois", "já testei manualmente", "deletar é desperdício", "TDD é dogmático", "spirit not ritual" — todos significam: apague o código e refaça via TDD.

## Escape hatch
Se o caso for ambíguo (protótipo descartável, código gerado, config) ou complexidade exceder este sumário → invocar `superpowers:test-driven-development` formal. Para Auto-QA Akita 15-item, ver `references/4-block-contract-template.md` (não duplicar aqui).
