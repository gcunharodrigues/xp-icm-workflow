---
name: finishing-a-development-branch-200tok
source_skill: superpowers:finishing-a-development-branch
source_version: "5.0.0"
purpose: Decidir como integrar trabalho concluido — merge local, PR ou tag — apos verification e review verdes.
---

# Finishing a Development Branch — sumario 200tok

## Quando aplicar
- No estagio 07 (merge) do ICM, depois que 05 verification e 06 review estao APROVADOS.
- Quando implementacao completa, testes passam, e precisa decidir destino do branch.

## Como aplicar
1. **Verificar testes** uma vez mais no branch (nao confiar em run anterior). Falhou → parar, voltar ao 04.
2. **Determinar base** com `git merge-base HEAD main` (ou master).
3. **Apresentar menu** ao Guilherme — exatamente 3 opcoes ICM-aware:
   - **A) Merge direto local** — `git checkout <base> && git pull && git merge <feature>`, deletar branch.
   - **B) Push + abrir PR** — `git push -u origin <branch>` + `gh pr create` com summary 2-3 bullets e test plan; manter branch ate PR fechar.
   - **C) Tag-only (keep as-is)** — criar tag `icm/<estagio>/<slug>` no HEAD, manter branch para iteracao posterior.
4. **Executar escolha**, registrar SHA final e tag/PR no `merge-report.md` do estagio.
5. Deletar branch apenas em A; em B aguarda PR; em C preserva.

## Sinais de sucesso
- `merge-report.md` registra: opcao escolhida, SHA do merge/PR, tag (se houver).
- Testes verdes apos merge (run pos-integracao em A).
- Branch deletada **apenas** se merge confirmado.

## Red flags — PARAR
- Tests falhando → nunca prosseguir.
- Force-push sem pedido explicito.
- Descartar trabalho sem confirmacao tipada.
- Deletar branch em B ou C (perde estado).

## Escape hatch
Se Guilherme nao decide na hora → opcao C (tag-only) preserva tudo para sessao futura, sem necessidade de cleanup.