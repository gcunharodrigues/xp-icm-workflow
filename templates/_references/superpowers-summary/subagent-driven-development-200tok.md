---
name: subagent-driven-development-200tok
source_skill: superpowers:subagent-driven-development
source_version: "5.0.0"
purpose: Executar plano com subagent fresco por tarefa e revisão em duas etapas (spec depois qualidade).
---

# Subagent-Driven Development — sumário 200tok

## Quando aplicar
- Há plano de implementação escrito, tarefas independentes, execução na mesma sessão.
- Casa com a fase 04 `implementation_waves` quando o Wave Planner liberou um agent team. Ver `references/agent-team-protocol.md` para regras locais (worktrees, isolamento, contratos 4-bloco).

## Princípio
Subagent novo por tarefa + revisão em duas etapas (spec compliance → qualidade de código) = alta qualidade, iteração rápida.

## Como aplicar
1. Leia o plano uma vez, extraia o texto completo de cada tarefa + contexto, crie TodoWrite.
2. Para cada tarefa:
   a. Despache **implementer subagent** com texto completo + contexto. Responda perguntas antes dele começar.
   b. Implementer faz TDD, testa, commita, self-review, retorna status (DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED).
   c. Despache **spec reviewer** — confirma que o código bate com a spec, sem faltar nem sobrar. Loop até OK.
   d. Despache **code quality reviewer** — só após spec OK. Loop até aprovado.
   e. Marque tarefa como completa.
3. Após todas as tarefas, despache **final reviewer** sobre a implementação inteira.

## Seleção de modelo
Use o modelo mais barato que aguenta o papel: mecânico → cheap; integração → standard; arquitetura/review → mais capaz.

## Sinais de sucesso
- Cada tarefa passou por spec review e quality review separados.
- Loops de revisão fecharam (sem "close enough").
- Nenhum subagent paralelo de implementação na mesma tarefa.

## Red flags
Pular review, rodar code quality antes do spec OK, fazer subagent ler o plano (passe texto completo), aceitar issues abertas para próxima tarefa.

## Escape hatch
Se complexidade exceder este sumário (coordenação multi-agent não trivial, conflitos de worktree, plano ambíguo) → invocar `superpowers:subagent-driven-development` formal.
