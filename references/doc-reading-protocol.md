# Doc Reading Protocol — Canais de documentação para o subagente

> Protocolo que define **como** um subagente (fase 04) recebe documentação: quais docs ler, em que ordem, e quem injeta cada qual.

## Os 3 canais

| Canal | Nome | Quem injeta | O quê | Onde |
|---|---|---|---|---|
| 1 | **L2 Inputs** | Estrutura do workspace (bootstrap + sessões) | `CONTEXT.md` do estágio + arquivos declarados na tabela `Inputs` | `stages/<NN>/CONTEXT.md` lista todos os inputs obrigatórios e condicionais |
| 2 | **Lead injeta** | Lead da wave (agente coordenador da fase 04) | Lições críticas pré-marcadas, contexto de task, ADRs relevantes, conventions extras | Injetado no `_kickoff.md` da wave e/ou na task do `plan.md` |
| 3 | **plan.md declara** | Designer (fase 02), refinado pelo wave-planner (fase 03) | Metadados por task: Files touched, ADRs aplicáveis, Lições críticas, Tech debt paydown, Requires_peer_review | Seção de metadados de cada task no `plan.md` |

## Regra de leitura

1. **Canal 1 é obrigatório.** Todo subagente lê L0 → L1 → L2 (seu estágio) → Inputs declarados. Sem exceção.
2. **Canal 2 é obrigatório quando presente.** Se `_kickoff.md` existe no estágio, o subagente lê antes de começar. O lead pode injetar contexto adicional via mensagem direta (apenas quando estritamente necessário).
3. **Canal 3 é task-specific.** Cada task no `plan.md` declara quais ADRs, lições e files o subagente deve consultar. O subagente lê **somente** os files declarados em `Files touched`, não a árvore inteira de `src/`.

## O que o subagente NÃO lê

- Outros workspaces em `workspaces/<outro>/`
- Outputs de estágios não listados em `Inputs`
- `src/` inteiro — somente `Files touched` da task
- L4 outputs de estágios futuros (que ainda não existem)

## Anti-patterns

- **Over-read:** ler `src/` inteiro em vez de `Files touched` declarados. Custo de token alto, contexto diluído.
- **Under-read:** pular L2 Inputs obrigatórios. Perde convenções, stop points, gates.
- **Canal 2 sem kickstart:** lead que não gera `_kickoff.md` deixa subagente sem contexto de wave. Cada wave deve ter kickoff.

## Cruzamento com outros protocolos

- **4-block-contract-template.md:** O schema de task no `plan.md` é o veículo do canal 3. Cada task carrega O QUE / COMO / NÃO QUERO / VALIDAÇÃO + metadados.
- **subagent-protocol.md:** O lead usa canais 1+2+3 para montar o contexto de cada subagente antes do spawn.
- **session-handoff-protocol.md:** O `_kickoff.md` é o artefato do canal 2 entre sessões (lead → próxima sessão).