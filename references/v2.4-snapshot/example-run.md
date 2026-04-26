# Example Run — Transição Estágio 02 → 03

Exemplo concreto de uma transição entre estágios. Mostra o que a orquestradora lê, o que escreve, e como invoca subagent. Use como ancora mental ao executar transições reais.

---

## Cenário

Workspace: `workspaces/003-tracker-habitos/`
Estágio anterior (02 Design & Planning) acabou de produzir:

- `stages/02_design/output/plan.md` — plano com 4 tasks: (a) modelo de dados, (b) API CRUD habits, (c) API CRUD checkins, (d) frontend lista
- `stages/02_design/output/decisions.md` — INDEX com 2 ADRs
- `docs/decisions/0003-stack-fastapi-sqlite.md` — ADR formal stack
- `docs/decisions/0004-schema-habits.md` — ADR formal schema

Humano aprovou plano. Próximo: Estágio 03 (Implementation).

---

## Passo 1 — Orquestradora aplica Stage Transition Checklist do Estágio 02

Antes de carregar Estágio 03, completar:

```
[x] Outputs de 02 escritos em stages/02_design/output/
[x] stages/02_design/CONTEXT.md atualizado (STATUS: COMPLETED, data, outputs)
[x] CONTEXT.md raiz: append histórico (2026-04-24 | 02_design | COMPLETED | plan.md, decisions.md, + ADRs 0003, 0004 em docs/decisions/)
    e atualizar STAGE: 03_implementation, STATUS: IN_PROGRESS (aponta para próximo)
[x] Commit: "chore(workspace): completa estagio 02 design (003-tracker-habitos)"
[x] Apresentado ao humano: "Estágio 02 completo. Outputs: plan.md, decisions.md, 2 ADRs. Aprovar para 03?"
```

Humano aprovou. Prosseguir.

---

## Passo 2 — Carregar Estágio 03

Ordem obrigatória:

1. `workspaces/003-tracker-habitos/CLAUDE.md` (Layer 0 — identidade)
2. `workspaces/003-tracker-habitos/CONTEXT.md` (Layer 1 — estado atual: `STAGE: 03_implementation, STATUS: IN_PROGRESS`; histórico mostra 02_design COMPLETED)
3. `workspaces/003-tracker-habitos/stages/03_implementation/CONTEXT.md` (Layer 2 — contrato)

Layer 2 lista Inputs (do template):

- [L4:in] `../02_design/output/plan.md`
- [L4:in] `../02_design/output/decisions.md`
- [L3:cfg] `../../docs/decisions/` — SOMENTE ADRs no plan
- [L3:cfg] `../../docs/tech_debt.md`
- [L3:cfg] `../../docs/lessons.md`
- [L3:cfg] `../../_config/xp-conventions.md`

Orquestradora lê SOMENTE estes. **Não lê** `src/`, `tests/`, ADRs não listados.

---

## Passo 3 — Analisar plan.md e identificar tasks paralelizáveis

Plano tem 4 tasks. Análise de dependências:

| Task | Depende de | Paralelizável com |
|---|---|---|
| (a) modelo de dados | — | — |
| (b) API CRUD habits | (a) | (c) depois de (a) |
| (c) API CRUD checkins | (a) | (b) depois de (a) |
| (d) frontend lista | (b) | — |

Resultado: 1 subagent sequencial pra (a), depois 2 subagents paralelos pra (b) e (c), depois 1 subagent pra (d).

---

## Passo 4 — Despachar subagent (a) com prompt restrito

Orquestradora monta prompt usando o Protocolo de Delegação (ver SKILL.md principal):

```
## Contexto do Workspace
- Caminho relativo: workspaces/003-tracker-habitos/
- Perfil: app_web_backend
- Tier: development
- Stack: FastAPI + SQLite (ADR 0003)

## Sua Task
Implementar modelo de dados para habits e checkins, conforme schema definido no ADR 0004. Criar SQLAlchemy models, Pydantic schemas, e migration inicial.

## Inputs (leia SOMENTE estes, na ordem listada)
1. workspaces/003-tracker-habitos/CLAUDE.md
2. workspaces/003-tracker-habitos/stages/03_implementation/CONTEXT.md
3. workspaces/003-tracker-habitos/stages/02_design/output/plan.md (seção Modelo de Dados)
4. workspaces/003-tracker-habitos/stages/02_design/output/decisions.md (sumário INDEX)
5. workspaces/003-tracker-habitos/docs/decisions/0004-schema-habits.md
6. workspaces/003-tracker-habitos/docs/tech_debt.md
7. workspaces/003-tracker-habitos/_config/xp-conventions.md

## Regras de Stop Point
SE precisar de nova dependência, mudar stack, criar API pública, ou usar serviço pago → PARE e retorne à orquestradora.

## Regras de Contexto
- NÃO ler arquivos fora desta lista
- NÃO ler ADRs 0001-0002 (não relacionados à sua task). Stack (ADR 0003) já está resumida no Contexto do Workspace acima — não ler o arquivo completo
- NÃO ler outputs de Estágio 01 (já consumido)
- Seguir /xp-workflow (TDD, convenções, commits)
- Código em src/, testes em tests/ do projeto pai (NÃO dentro de stages/)
- Ao finalizar: escrever resumo em workspaces/003-tracker-habitos/stages/03_implementation/output/reports/task-a-modelo-de-dados.md (arquivo próprio, sem conflito com outros subagents paralelos)
```

---

## Passo 5 — Após subagent (a) completar

Orquestradora lê **SOMENTE** `stages/03_implementation/output/reports/task-a-modelo-de-dados.md`. Não abre `src/models/habits.py`. Não roda testes manualmente.

Se report indica:
- CI Gates verde ✅ → despachar (b) e (c) em paralelo (cada um escreve em seu próprio `output/reports/task-<slug>.md`)
- Algum gate vermelho ❌ → invocar `superpowers:systematic-debugging` ou re-delegar correção

---

## Passo 6 — Após todas tasks completas

Orquestradora lê os reports individuais `output/reports/task-*.md` e consolida em `output/implementation-report.md` (ou delega a um subagent "consolidator"). Em seguida, aplica Stage Transition Checklist do Estágio 03:

```
[x] Reports individuais em stages/03_implementation/output/reports/task-*.md
[x] Implementation-report consolidado em stages/03_implementation/output/implementation-report.md
[x] Código em src/, testes em tests/ (escritos pelos subagentes)
[x] stages/03_implementation/CONTEXT.md atualizado
[x] CONTEXT.md raiz atualizado
[x] Commit
[x] Apresentado ao humano: "Estágio 03 completo. CI verde, 4 tasks ✅. Aprovar para 04?"
```

---

## Anti-padrões observados (aplicar Princípio de Delegação)

- ❌ Orquestradora abre `src/models/habits.py` "só pra dar uma olhada" → viola Princípio de Delegação
- ❌ Orquestradora monta prompt do subagent listando "leia o workspace inteiro" → viola context scoping
- ❌ Orquestradora pula checklist de transição porque "tá tudo OK" → quebra retomada de sessão futura
- ❌ Orquestradora despacha (b) sem esperar (a) terminar → quebra ordem de dependência

Ao detectar self → parar, voltar, corrigir antes de prosseguir.
