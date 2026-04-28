---
name: receiving-code-review-200tok
source_skill: superpowers:receiving-code-review
source_version: "5.0.0"
purpose: Subagente recebe feedback do reviewer com rigor tecnico, nao concordancia performativa.
---

# Receiving Code Review — sumario 200tok

## Quando aplicar
- Quando fix loop dispara: P0/P1 no `review-report.md` exige volta ao estagio 04.
- Ao receber qualquer review, especialmente se feedback parece confuso ou tecnicamente questionavel.
- Antes de implementar sugestao — verificar antes de mudar.

## Como aplicar
1. **LER** feedback inteiro sem reagir.
2. **ENTENDER** restate cada item em palavras proprias; se nao consegue, pedir clarificacao **antes** de implementar qualquer item (itens podem ser relacionados).
3. **VERIFICAR** contra realidade do codebase: o suggestion quebra algo? ha razao para impl atual? funciona em todas as plataformas?
4. **AVALIAR** YAGNI: grep por uso real antes de "implementar direito".
5. **RESPONDER** com reasoning tecnico ou pushback fundamentado — nunca "Voce esta absolutamente certo!", "Otimo ponto!", "Obrigado por pegar isso!".
6. **IMPLEMENTAR** um item por vez, testar cada, sem regressao.
7. Anotar fixes no proprio `review-report.md` (sub-secao "fixes aplicados") e re-rodar verification antes de devolver ao reviewer.

## Sinais de sucesso
- Cada item P0/P1 tem fix com commit SHA referenciado.
- Pushback (quando aplicavel) cita codigo/test que prova posicao.
- Zero linguagem performativa; codigo fala pelo trabalho.

## Red flags — PARAR
- "Voce esta certo!" ou qualquer gratidao antes de verificar.
- Implementar em batch sem testar entre items.
- Aceitar sugestao que quebra funcionalidade existente sem questionar.
- Conflito com decisao previa do Guilherme → pausar e perguntar.

## Escape hatch
Se nao consegue verificar (ex: precisa env especifico) → declarar limitacao no report, pedir direcao. Nunca implementar as cegas.
