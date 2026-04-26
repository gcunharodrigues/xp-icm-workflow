---
name: brainstorming-200tok
source_skill: superpowers:brainstorming
source_version: "5.0.0"
purpose: Transformar ideia crua em design aprovado antes de qualquer implementacao.
---

# Brainstorming — sumario 200tok

## Quando aplicar
- Antes de criar feature, componente ou mudar comportamento — sempre, mesmo em projeto "simples".
- Quando spec ainda nao existe ou requisitos estao vagos.
- Hard-gate: NAO escrever codigo nem invocar skill de implementacao ate design aprovado.

## Como aplicar
1. Explorar contexto do projeto (arquivos, docs, commits recentes).
2. Se escopo cobre subsistemas independentes, decompor antes de detalhar.
3. Fazer perguntas de clarificacao **uma por vez**, multiple-choice quando possivel. Foco: proposito, restricoes, criterios de sucesso.
4. Propor 2-3 abordagens com trade-offs e recomendacao explicita.
5. Apresentar design em secoes (arquitetura, componentes, fluxo de dados, erros, testes), aprovacao incremental por secao.
6. Salvar spec em `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` e commitar.
7. Transicionar **apenas** para `writing-plans` (nunca direto para implementacao).

## Sinais de sucesso
- Design escrito tem unidades com fronteiras claras e interfaces bem definidas.
- Usuario aprovou cada secao; YAGNI aplicado (nada de feature especulativa).
- Spec commitado antes de qualquer linha de codigo.

## Escape hatch
Se design exige mockups visuais, multiplos subsistemas ou loop de revisao formal → invocar `superpowers:brainstorming` completo.
