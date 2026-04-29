# Task Types — HITL vs AFK

Adaptado de [mattpocock/skills/skills/engineering/to-issues/SKILL.md].

## Definições

**HITL (Human-In-The-Loop):** task que **exige interação humana** durante
execução. Subagent não pode terminar autonomamente.

Exemplos:
- Decisão arquitetural com trade-off não-óbvio (escolher entre 2 frameworks)
- Design review (mockup precisa aprovação)
- Manual UX/QA testing (clica botão, valida visual)
- Acesso a credentials/cofres
- Deploy production gate
- Aceite de stakeholder externo

**AFK (Away-From-Keyboard):** task que **um subagent pode completar
autonomamente** com o brief. Lead spawna via Agent tool, subagent executa
ciclo TDD 7 passos, retorna report.

Exemplos:
- Implementar endpoint REST com schema definido em plan.md
- Adicionar coluna em schema + migration
- Refactor de função interna preservando contrato
- Adicionar test coverage em módulo existente
- Fix bug com repro test claro

## Default

`AFK` é default. Mark as `HITL` apenas com **justificativa explícita** em
coluna do plan.md.

## Schema no plan.md

```markdown
### Task: implementar-jwt-refresh

**Type:** AFK
**Files touched:** src/auth/jwt.{ts,test.ts}, src/api/refresh.ts
**Depends on:** none

**O QUE:** ...
**COMO:** ...
**NÃO QUERO:** ...
**VALIDAÇÃO:** ...
```

```markdown
### Task: choose-orm

**Type:** HITL
**Reason:** Decisão arquitetural — Prisma vs Drizzle vs raw SQL. Lock-in
significativo, equipe deve aprovar.
**Files touched:** docs/decisions/0007-orm-choice.md
**Depends on:** none

**O QUE:** ...
```

## Wave planner consequence

- **AFK tasks:** agrupadas em waves topológicas respeitando cap por tier
  (experimental: 2, tool: 3, development: 5, production: 5).
- **HITL tasks:** cada uma vira **wave isolada com cap=1**. Lead session
  pausa ao chegar nessa wave, gera AGENT-BRIEF (mas NÃO spawna subagent),
  exibe ao humano e aguarda input. Status: `wave-N_hitl_pending`.

## Lead session na wave HITL

```
1. Detecta wave type=HITL
2. Gera AGENT-BRIEF a partir da task
3. Imprime ao humano:
   "Wave N (HITL): <task summary>
    Brief gerado em stages/04/output/wave-N/hitl-brief.md
    Ação requerida: <reason>
    Após resolver, retome a sessão e marque sub_stage=04_wave_N_completed."
4. Atualiza L1: status=COMPLETED_AWAITING_HUMAN, sub_stage=04_wave_N_hitl_pending
5. SAIR da sessão.
```

Próxima sessão (após humano resolver) retoma na wave seguinte.

## Critérios de classificação

**Marque HITL quando:**
- Decisão é hard to reverse + tem alternativas reais (corresponde ao gate ADR)
- Subagent não tem informação suficiente (precisa input externo)
- Aceite de stakeholder explícito requerido
- Manual testing precisa olhos humanos (UX, design)
- Credentials/secrets envolvidos

**Marque AFK quando:**
- Brief tem acceptance criteria testáveis
- Path técnico está claro (mesmo que múltiplos passos)
- Tests podem confirmar correctness automaticamente
- Sem dependências externas humanas
