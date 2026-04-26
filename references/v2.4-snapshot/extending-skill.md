# Extending the Skill — xp-icm-workflow

Checklist para quando uma **nova skill** é instalada no ecossistema ou o usuário pede para incorporar uma nova capacidade ao workflow.

Aplicar o princípio edit-source à própria skill: se você continua atualizando os mesmos arquivos manualmente toda vez que algo muda, crie mecanismo que garanta consistência automática.

---

## Quando ler este arquivo

Carregar sob demanda quando:

1. Uma nova skill é instalada (ex: `superpowers:ui-ux-design`, `superpowers:data-pipeline`).
2. Usuário pede "incorporar [capacidade] ao workflow".
3. Orquestradora detecta skill invocada que não aparece no mapeamento.
4. Skill existente muda de nome ou escopo.

---

## Perguntas de classificação (responder primeiro)

Antes de atualizar arquivos:

1. **Esta skill afeta qual estágio?** → Define qual seção do `SKILL.md` e qual template de `CONTEXT.md` atualizar.
2. **Substitui ou complementa skill existente?** → Substitui: remover a antiga. Complementa: adicionar como auxiliar.
3. **Orquestradora precisa ler o output diretamente ou delegar?** → Markdown compacto (`discovery.md`, `plan.md`): orquestradora pode ler. Código-fonte (`src/`, `tests/`): delegar a subagentes/skills especializadas.
4. **Skill introduz novo tipo de artefato?** → Se sim, adicionar na Inputs table dos estágios que o consomem. Exemplo: wireframes (Estágio 02) são input para Estágio 03.
5. **Skill requer novo estágio?** → Etapa distinta com review gate próprio → criar estágio. Atividade dentro de estágio existente → adicionar como auxiliar.

---

## Checklist de Extensibilidade

Para cada nova skill ou mudança, atualizar **todos** os itens relevantes:

| # | Arquivo | O que atualizar | Exemplo |
|---|---|---|---|
| 1 | `SKILL.md` — Division of Responsibilities | Adicionar skill na tabela com Quem e Decide/Faz | `superpowers:ui-ux-design` → "Design: wireframes, protótipos, guias de estilo" |
| 2 | `SKILL.md` — Workflow Overview (tabela mestra) | Se cria novo estágio, adicionar no fluxo. Se complementa, adicionar como auxiliar. | Estágio 02.5: "UI/UX Design" com skill `ui-ux-design`, ou Estágio 03 com skill auxiliar |
| 3 | `SKILL.md` — Estágio específico (Phase 1 enxuta) | Atualizar skill, input chave, output chave e gate do estágio afetado | Se UI/UX afeta Estágio 02: adicionar wireframes como output |
| 4 | `references/stage-templates.md` | Atualizar template do estágio afetado com nova skill, inputs e outputs. Se a nova skill impactar identidade ou roteamento do workspace, atualizar também os templates de `CLAUDE.md` raiz e `CONTEXT.md` raiz nesse mesmo arquivo. | Adicionar `output/wireframes.md` nos outputs do Estágio 02; se skill adiciona novo campo (ex: design system name) ao workspace, atualizar template de `CLAUDE.md` raiz |
| 5 | `references/superpowers-mapping.md` | Adicionar linha na tabela "Mapeamento por Estágio" e/ou "Situação Transversal" | `02 Design & Planning` → `superpowers:ui-ux-design` |
| 6 | `references/xp-workflow-integration.md` | Se afeta fases do `/xp-workflow`, mapear. Se não afeta, marcar N/A. | Phase 1 do xp-workflow agora inclui UI/UX |
| 7 | `references/icm-paper-summary.md` | **NÃO atualizar** — resumo do paper, não da skill | N/A |
| 8 | `SKILL.md` — Protocolo de Delegação (se aplicável) | Se skill lê código-fonte ou produz artefatos que orquestradora consumiria, definir se lê direto ou via report | `ui-ux-design` produz wireframes (markdown) — orquestradora pode ler, não precisa de delegação |
| 9 | `references/changelog.md` | Registrar extensão como nova versão menor | v2.X.0 — Extensão: [skill]. Estágio(s): [...]. Arquivos: [...] |

---

## Formato de registro no changelog

```
## v2.X.0 — Extensão: [nome da skill]
- Estágio(s) afetado(s): [lista]
- Arquivos atualizados: [lista]
- Motivo da adição: [1 frase]
- Orquestradora lê output diretamente? [sim/não + motivo]
```

---

## Red flags

Sinais de que a extensão está sendo feita mal:

- Nova skill aparece em `SKILL.md` mas não em `references/superpowers-mapping.md` (mapeamento dessincronizado).
- Template de estágio no `references/stage-templates.md` diz "invocar X skill" mas o X não está listado em Division of Responsibilities.
- Orquestradora adicionou leitura direta de `src/` — viola Princípio de Delegação.
- Stop points do `/xp-workflow` não foram considerados quando novo tipo de artefato foi introduzido.
- Changelog não registrou a extensão — sessões futuras ficam sem rastreabilidade.

Ao detectar qualquer red flag: parar, corrigir, só depois prosseguir.
