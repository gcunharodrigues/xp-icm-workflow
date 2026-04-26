---
name: verification-before-completion-200tok
source_skill: superpowers:verification-before-completion
source_version: "5.0.0"
purpose: Provar que trabalho esta completo com evidencia fresca antes de qualquer claim de sucesso.
---

# Verification Before Completion — sumario 200tok

## Quando aplicar
- Antes de qualquer claim de "pronto", "passa", "funciona", "corrigido".
- Antes de commit, PR, merge ou marcar tarefa como completa.
- No estagio 05 (verification) do ICM — gera `verification-report.md` no workspace do estagio.
- Ao receber relato de sucesso de subagente — verificar diff, nao confiar.

## Como aplicar
1. **IDENTIFICAR** comando que prova o claim (test suite, build, lint, smoke).
2. **RODAR** comando completo e fresco neste turno (nao reusar output anterior).
3. **LER** output inteiro: exit code, contagem de falhas, warnings.
4. **VERIFICAR** se output confirma o claim — se nao, reportar status real.
5. **REGISTRAR** evidencia em `verification-report.md` (comando + output + veredito).
6. Regression test exige ciclo TDD red-green: reverter fix, ver falhar, restaurar, ver passar.

## Sinais de sucesso
- `verification-report.md` cita comando exato e output literal (nao parafraseado).
- Exit code 0 confirmado para cada gate (test, build, lint).
- Requisitos do plano checados linha-a-linha, gaps explicitos quando existem.

## Red flags — PARAR
- Palavras "should", "probably", "seems to", "deve passar".
- Expressao de satisfacao ("Otimo!", "Perfeito!") sem ter rodado comando.
- Confiar em "agente reportou sucesso" sem checar diff/VCS.
- "Linter passou" usado como prova de build (linter nao compila).

## Escape hatch
Se gate nao tem comando automatizado (ex: revisao visual de UX) → documentar em `verification-report.md` o metodo manual usado e quem validou. Nunca pular o registro.
