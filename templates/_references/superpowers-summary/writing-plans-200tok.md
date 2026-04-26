---
name: writing-plans-200tok
source_skill: superpowers:writing-plans
source_version: "5.0.0"
purpose: Converter spec aprovado em plano de implementacao bite-sized executavel por agente sem contexto.
---

# Writing Plans — sumario 200tok

## Quando aplicar
- Depois de spec aprovado em brainstorming, antes de tocar codigo.
- Tarefa multi-step que sera executada por outro agente/sessao.
- Engenheiro alvo sabe codar mas nao conhece nosso codebase nem dominio.

## Como aplicar
1. Scope check: se spec cobre subsistemas independentes, sugerir quebrar em planos separados (1 plano = 1 software testavel).
2. Mapear file structure antes das tasks: cada arquivo com responsabilidade unica, fronteiras claras.
3. Estruturar header obrigatorio: Goal (1 frase), Architecture (2-3 frases), Tech Stack.
4. Decompor em tasks bite-sized (2-5 min cada): Write failing test → Run (espera FAIL) → Implementar minimo → Run (espera PASS) → Commit.
5. Cada task lista: arquivos exatos (Create/Modify com linhas/Test), codigo completo no plano (nao "adicionar validacao"), comandos exatos com output esperado.
6. Salvar em `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`.
7. Loop de review por chunks (≤1000 linhas) com plan-document-reviewer ate aprovado.

## Sinais de sucesso
- TDD, DRY, YAGNI respeitados; commits frequentes.
- Caminhos absolutos, comandos copy-paste, codigo embutido — zero ambiguidade.

## Escape hatch
Se plano excede 1 chunk ou exige review formal por subagente → invocar `superpowers:writing-plans` completo.
