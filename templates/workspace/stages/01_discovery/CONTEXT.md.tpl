---
layer: L2
stage: "01"
stage_name: "discovery"
sub_stage_enum:
  - "01_in_progress"
  - "01_completed"
applicable_stop_points:
  - "stack"
  - "external_api"
  - "paid_service"
  - "pii"
output_files:
  - "output/discovery.md"
next_stage: "02"
---

# Estágio 01 — discovery (L2)

Brainstorming guiado com o humano. Refina escopo via clarification iterativa, mapeia público, requisitos funcionais e não-funcionais, lista riscos, e propõe opções macro A/B/C de abordagem (sem ainda detalhar arquitetura — isso é estágio 02). Define MVP IN/OUT e métricas de sucesso. Saída alimenta o design (estágio 02) com escopo bem-delimitado.

## Inputs (lê SOMENTE estes, na ordem)

| # | Path | Layer | Obrigatório? |
|---|------|-------|--------------|
| 1 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md | L0 | sim |
| 2 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md | L1 | sim |
| 3 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/01_discovery/CONTEXT.md | L2 | sim |
| 4 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/00_recon/output/recon-report.md | L4 | sim |
| 5 | {{PROJECT_ROOT}}/docs/lessons.md | L3 | condicional: existe se herdou de fase 08 saída C ou iteração anterior |
| 6 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/profile-effective.yaml | L3 | sim |
| 7 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/stop-points.md | L3 | sim |
| 8 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/brainstorming-200tok.md | L3 | sim |
| 9 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/01_discovery/_kickoff.md | L4-kickoff | condicional: gerado pela sessão anterior. Ausente em workspaces beta1/beta2 (4B legacy) ou se for primeira sessão de stage. |
| 10 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/session-handoff-protocol.md | L3 | condicional: necessário no handoff final do estágio |
| 11 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/runtime/stop-points-canonical.md | L3 | condicional: catálogo canônico de IDs, complementar ao _config/stop-points.md de thresholds |

## Não Lê (negative constraint)

- {{PROJECT_ROOT}}/src/ e {{PROJECT_ROOT}}/tests/ — discovery NÃO inspeciona código-fonte. Se contexto de código for necessário, citar dependência no recon-report e revisitar 00.
- {{PROJECT_ROOT}}/docs/decisions/ — ADRs detalhados são consumidos no estágio 02. Aqui usa-se apenas o índice já listado em recon-report.md.
- Outputs de estágios 02+ — não existem ainda.
- {{PROJECT_ROOT}}/docs/tech_debt.md — escopo de tech debt aparece em design (02), não em discovery.

## Read order

1. L0 — {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md
2. L1 — {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md
3. L2 — este arquivo
4. {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/00_recon/output/recon-report.md (entrada principal)
5. {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/profile-effective.yaml
6. {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/stop-points.md
7. {{PROJECT_ROOT}}/docs/lessons.md (se existe)
8. Sumário superpowers brainstorming-200tok
9. session-handoff-protocol.md (handoff final do estágio)
10. stop-points-canonical.md (catálogo de IDs complementar ao _config/stop-points.md)
11. {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/01_discovery/_kickoff.md (se existe — handoff do estágio 00)

## Process

1. **Pre-flight:** validar todos os paths Inputs marcados `sim`; sub_stage `01_in_progress`. Se `recon-report.md` ausente → status `BLOCKED_ERROR` (recon precisa rodar antes).
2. **Consultar sumário 200tok brainstorming** para padronizar formato das perguntas (menu A/B/C com recomendação, perguntas de clarificação antes de assumir).
3. **Clarification iterativa com humano:** público-alvo, objetivo, requisitos funcionais (o que faz), requisitos não-funcionais (perf, segurança, escala), restrições técnicas/orçamentárias. Cada decisão não-trivial vira menu A/B/C com recomendação do agente.
4. **Detectar stop points durante clarificação:** se humano descreve integração com SaaS pago, troca de stack, API externa não-trivial, ou manipulação de PII → disparar stop point correspondente conforme calibração de tier em `_config/stop-points.md`.
5. **Mapear opções macro A/B/C** de abordagem (alta-nível, sem entrar em arquitetura detalhada). Justificar recomendação considerando profile/tier do L0.
6. **Definir MVP IN/OUT:** o que entra nesta entrega vs o que fica para depois. Lista explícita.
7. **Listar riscos** (técnicos, de escopo, de prazo) com mitigação proposta para cada.
8. **Definir métricas de sucesso** — como o humano vai saber que o MVP entregou valor.
9. **Escrever `output/discovery.md`** com seções fixas: Resumo executivo (3-5 frases); Público-alvo; Requisitos funcionais; Requisitos não-funcionais; Opções macro A/B/C + escolha; MVP IN/OUT; Riscos e mitigações; Métricas de sucesso; Stop points disparados (se houve).
10. **Atualizar L1:** sub_stage `01_completed`, status `COMPLETED_AWAITING_HUMAN`, append `history` evento `stage_transition`. Commit atômico.

## Outputs

- `output/discovery.md` — escopo refinado: público, requisitos, opções macro escolhidas, MVP IN/OUT, riscos, métricas. Documento que o humano edita diretamente se discordar.

## Sub_stage transitions

Enum válido: `01_in_progress`, `01_completed`.

Transição IN_PROGRESS → COMPLETED dispara quando:
- `output/discovery.md` existe com todas as seções fixas preenchidas.
- Stop points disparados durante a sessão estão resolvidos (status volta a `IN_PROGRESS` antes do completar).
- Humano aprovou via gate (status `COMPLETED_AWAITING_HUMAN` → humano responde "aprovado, prosseguir 02").

## Status canônicos disponíveis neste estágio

- `IN_PROGRESS` — clarificação ativa com humano.
- `COMPLETED_AWAITING_HUMAN` — discovery pronto, humano revisa/edita antes de transitar.
- `BLOCKED_STOP_POINT` — menu A/B/C aguardando resposta (stack, external_api, paid_service ou pii).
- `BLOCKED_ERROR` — recon-report ausente ou path Input obrigatório falhou.

## Stop points aplicáveis

Catálogo canônico em `references/stop-points-canonical.md`. IDs disparáveis no estágio 01 discovery:

- `stack` — humano descreve linguagem/framework/runtime ainda não declarado em ADR. Sempre `hard`.
- `external_api` — integração com API externa (paga? rate-limit? privacy?). Sempre `hard`.
- `paid_service` — SaaS recorrente; threshold calibrado por tier (warning R$50 experimental / hard R$200 tool / hard R$500 development / hard R$1000 production).
- `pii` — manipulação de dados pessoais ou sensíveis (LGPD); calibrado por tier (warning experimental / hard tool/development / hard+DPO production).

Disparo: agente pausa, escreve menu A/B/C no output, atualiza L1 `status: BLOCKED_STOP_POINT`. Humano responde, sessão retoma com `IN_PROGRESS`. Decisões não-arquiteturais ficam anotadas em discovery.md; arquiteturais propagam para 02 design (que pode spawnar ADR).

## Skill superpowers de referência

Sumário 200tok: `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/brainstorming-200tok.md`

Skill formal: `superpowers:brainstorming` (escape hatch — invocação real só se discovery exige exploração estruturada profunda além do sumário).

## Gates

- **Humano:** participa ativamente da clarificação; revisa e aprova `output/discovery.md`. Pode editar diretamente se discordar de algum item.
- **Automático (CI):** pre-commit hook valida atomicidade L1↔outputs e prefixo de commit `workspace/{{WORKSPACE}}`.
- **Aprovação para transitar:** humano explicitamente aprova ("prosseguir 02"); sub_stage vira `01_completed` no commit que registra a aprovação. Se stop point pendente → não transita.

## End of stage handoff (1-stage-1-sessão)

Ao concluir este estágio, sessão deve:

1. **Atualizar L1** (`<workspace>/CONTEXT.md`):
   - `sub_stage = 01_completed`
   - `status = COMPLETED_AWAITING_HUMAN` (ou `IN_PROGRESS` se transição automática pro próximo stage)
   - `last_transition.from = 01_completed`
   - `last_transition.to = 02_in_progress` (ou conforme `next_stage` do frontmatter)
   - `last_transition.at = <ISO 8601 UTC now>`
   - `history` append: `{at, event: "stage_transition", from, to, commit_sha, note}`

2. **Renderizar `_kickoff.md`** no stage seguinte:
   - Path: `<workspace>/stages/02_design/_kickoff.md`
   - Use `python {{SKILL_DIR}}/scripts/handoff.py render` ou função `render_kickoff` do `{{SKILL_DIR}}/scripts/handoff.py`
   - Frontmatter YAML L4-kickoff conforme schema em `references/session-handoff-protocol.md`
   - Corpo: prev_outputs com summary + prev_decisions + pending pra próximo stage

3. **Commit atômico** (pre-commit hook valida outputs↔L1; commit-msg valida prefix):
   ```
   workspace <NNN>: stage 01 completo + kickoff stage 02
   ```
   Files no commit: outputs do stage atual + L1 + `_kickoff.md` do próximo.

4. **Imprimir KICKOFF block verbal** pro user (copy-paste). Template (substitua placeholders):

   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ Stage 01 (discovery) COMPLETO — workspace <NNN-slug>

   Workspace atualizado em commit <sha>:
     - L1: stage_atual=02, sub_stage=02_in_progress
     - Outputs: <lista>
     - Kickoff: stages/02_design/_kickoff.md gerado

   🔄 KICKOFF próxima sessão — copy/paste:
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Continuar workspace <NNN-slug> no estágio 02 (design).

   Read order:
     workspaces/<NNN-slug>/CLAUDE.md
     workspaces/<NNN-slug>/CONTEXT.md
     workspaces/<NNN-slug>/stages/02_design/CONTEXT.md
     workspaces/<NNN-slug>/stages/02_design/_kickoff.md
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   Encerre esta sessão (Ctrl+D ou /exit) e abra nova sessão Claude
   no project_root, depois cole o prompt acima.
   ```

5. **SAIR** da sessão. NÃO continuar pro próximo stage na mesma sessão.

Detalhes em `<skill_root>/references/session-handoff-protocol.md`.
