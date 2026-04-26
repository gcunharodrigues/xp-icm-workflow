---
name: dispatching-parallel-agents-200tok
source_skill: superpowers:dispatching-parallel-agents
source_version: "5.0.0"
purpose: Despachar agentes concorrentes quando ha 2+ tarefas independentes sem estado compartilhado.
---

# Dispatching Parallel Agents — sumario 200tok

## Quando aplicar
- 2+ falhas/tarefas em dominios independentes (arquivos, subsistemas, bugs distintos).
- Cada problema entendivel sem contexto dos outros.
- Sem estado compartilhado — agentes nao editam mesmos arquivos nem competem por recursos.

## Quando NAO usar
- Falhas relacionadas (consertar uma pode consertar as outras) — investigar junto.
- Debug exploratorio sem dominio claro.
- Refactor que toca codigo compartilhado.

## Como aplicar
1. Identificar dominios independentes — agrupar por "o que esta quebrado".
2. Para cada dominio, montar prompt com: **escopo especifico** (1 arquivo/subsistema), **objetivo claro** (criterio de sucesso), **constraints** (ex.: "nao alterar codigo de producao"), **output esperado** (resumo do root cause + mudancas).
3. Despachar em paralelo na mesma mensagem (multiplos Task calls simultaneos).
4. Integrar: ler cada resumo, verificar conflitos, rodar suite completa, spot-check.

## Sinais de sucesso
- Agentes retornam sumarios independentes sem editar mesmos arquivos.
- Suite completa verde apos integracao; zero conflitos.
- Tempo total ≈ tempo do agente mais lento (nao soma).

## Erros comuns
- Prompt vago ("conserte tudo") → escopo perdido.
- Sem constraints → agente refatora alem do necessario.
- Sem output especificado → impossivel verificar.

## Escape hatch
Se dominios revelam-se acoplados ou exigem orquestracao → invocar `superpowers:dispatching-parallel-agents` completo.
