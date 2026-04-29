# Triage State Machine — Fase 08 feedback intake

Adaptado de [mattpocock/skills/skills/engineering/triage/SKILL.md].

Stage 08 (feedback_intake) classifica feedback recebido em **(category, state)**
antes de inferir A/B/C. Mapping direto: classificação → saída.

## Categorias

- **bug** — algo está quebrado.
- **enhancement** — nova feature ou improvement.

Toda issue classificada carrega **exatamente 1 categoria**.

## Estados

- **needs-triage** — precisa avaliação. Estado inicial.
- **needs-info** — esperando reporter dar mais info. Volta a `needs-triage` após resposta.
- **ready-for-action** — fully specified, ready para ser actioned (B ou C).
- **wontfix** — não será actioned. Vai para `_out-of-scope/` se enhancement.

Toda issue triada carrega **exatamente 1 estado**.

## Transições válidas

```
unlabeled → needs-triage
needs-triage → needs-info
              → ready-for-action
              → wontfix
needs-info → needs-triage  (após reporter responder)
```

Maintainer pode override em qualquer momento — flag transitions unusuais e
ask antes de proceder.

## Mapping classificação → Saída A/B/C

| Categoria | Estado | Saída | Comportamento |
|---|---|---|---|
| **bug** | ready-for-action | **B** restart fase X | Mapeia stage do bug: testes/CI → 05, código → 04, design errado → 02, requisitos errados → 01, review missou → 06, merge → 07 |
| **enhancement** | ready-for-action (aceito) | **C** spawn novo workspace | Workspace novo com escopo da enhancement |
| **enhancement** | wontfix | **A** close + append `_out-of-scope/<conceito>.md` | Workspace fecha, decisão registrada |
| qualquer | needs-info | sessão pausa | Status `COMPLETED_AWAITING_HUMAN`; aguarda reporter |
| nada | tudo ok | **A** close | Workspace fecha sem ação |

## AGENT-BRIEF para Saída B e C

Cada item que vai para Saída B ou C **produz um AGENT-BRIEF**
(formato: `references/agent-brief-template.md`):

- **Saída B:** AGENT-BRIEF descreve o bug + fix esperado + acceptance criteria.
  Vai como input para próxima sessão da fase X reaberta.
- **Saída C:** AGENT-BRIEF descreve a enhancement + escopo do novo workspace.
  Sessão B (bootstrap) usa como kickoff.

## OUT-OF-SCOPE para wontfix

Enhancement rejeitado (wontfix) registra:

1. Cria/atualiza `<workspace>/_out-of-scope/<conceito-kebab>.md` com:
   - `# {Concept Name}`
   - **Decision:** out-of-scope
   - **Reason:** raciocínio durável (não temporário)
   - **Prior requests:** lista de issues/sessions que pediram

2. Próxima fase 02 (em iterações futuras) consulta `_out-of-scope/` e
   surfaces match ao humano antes de re-propor.

Ver `references/out-of-scope-kb.md` para format completo.

## Disclaimer obrigatório

Toda mensagem postada na issue/log durante triage começa com:

```
> *Esta classificação foi gerada por IA durante triage.*
```

## Fluxo completo Stage 08

```
1. Pre-flight: L1 declara stage_atual=08, sub_stage=08_in_progress
2. Coletar feedback (input livre + logs)
3. Triage classification:
   - Para cada item de feedback:
     a. Categoria = bug | enhancement | none
     b. Estado = ready-for-action | needs-info | wontfix
4. Se needs-info → status=COMPLETED_AWAITING_HUMAN, sair
5. Mapear classificação → saída (A | B | C)
6. Para B e C: gerar AGENT-BRIEF
7. Para wontfix: append em _out-of-scope/
8. Mini-confirm com humano: mostra decisão + brief, espera s/n/edit
9. Executar saída:
   - A: deactivate CLAUDE.md root + L1 status=COMPLETED + lessons append
   - B: move outputs antigos, L1 iteration++, gera _kickoff, update CLAUDE.md root
   - C: remove bloco do dono em CLAUDE.md root, imprime comando spawn
10. Commit atômico + sair
```

## Quick override

Maintainer humano pode dizer "marcar #42 como wontfix" — agent confirma
ação proposta + executa direto. Skip grilling.
