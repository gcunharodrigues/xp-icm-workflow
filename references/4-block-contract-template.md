# 4-Block Contract Template + Vertical TDD Cycle

> **Versão:** v3.9.0
> **Skill:** `xp-icm-workflow`
> **Propósito:** Define o contrato 4-block obrigatório por task no `plan.md` (output da fase 02 design, consumido pelas fases 03 wave_planner e 04 implementation_waves) **e** o ciclo TDD vertical canônico (tracer-first + 1 test → 1 impl → repeat) que todo subagente executa por task. Substitui v3.0.0-beta5 (Akita 15-item drop em v3.9.0).

> **Decisão de origem:** F1 do plan `reescrever-a-skill-zazzy-wirth.md` (linha 57) + §4.4 dev↔qa loop + §4.11 canal 3 (plan.md schema). v3.9.0: drop Akita inline; QA delegado a forensic+ extended (L2) + critic ortogonal (L3) per `references/critic-protocol.md`.

---

## 1. Os 4 blocos — schema obrigatório por task

Toda task no `plan.md` (fase 02 design) **deve** declarar os 4 blocos abaixo, na ordem fixa. Cada bloco fica entre 50-200 tokens; total da task entre 200-800 tokens.

```markdown
## Task <SLUG>: <Título humano>

### O QUE
<Requisitos funcionais — o que esta task entrega.
 Linguagem de produto, não de implementação.
 2-5 bullets.>

### COMO
<Abordagem técnica — quais arquivos, quais funções, qual padrão.
 Pode citar ADR explicitamente ("seguir 0004-auth-strategy").
 3-7 bullets.>

### NÃO QUERO
<Anti-requisitos. Fora de escopo. O que NÃO fazer.
 Existe pra evitar scope creep e over-engineering.
 2-5 bullets.>

### VALIDAÇÃO
<Critérios de aceite mensuráveis + tests obrigatórios.
 Cada bullet deve mapear ≥1 test name (forensic+ Check 5 valida).
 3-7 bullets.>
```

### Por que 4 blocos (e não 3 ou 5)

| Bloco | Sem ele... |
|---|---|
| O QUE | Subagente inventa requisito; QA não tem âncora pra validar |
| COMO | Decisões arquiteturais divergem entre tasks paralelas da mesma wave |
| NÃO QUERO | Scope creep silencioso; subagente adiciona "enquanto está aqui..." |
| VALIDAÇÃO | Tests cobrem o que o dev achou interessante, não o que importa |

---

## 2. Schema completo de task no `plan.md`

Além dos 4 blocos, cada task declara metadados consumidos pelo lead da fase 04 (canal 3 do doc-reading-protocol):

```markdown
## Task <SLUG>: <Título>

### O QUE / COMO / NÃO QUERO / VALIDAÇÃO
<vide §1>

### Depends on
- <slug-de-task-pai> OR nenhum (task raiz)

### Files touched
- src/path/file.ts
- tests/path/file.test.ts

### Estimated lines
~250    <!-- optional. forensic-plus.py Check 3 (scope creep) triggers when
            actual diff insertions > 3 × estimate. Plan author opts in for
            tasks where bounded scope matters. Absent → check skipped. -->

### ADRs aplicáveis
- docs/decisions/0001-stack.md
- docs/decisions/0004-auth-strategy.md

### Lições críticas pré-marcadas
- 0033 (log policy)

### Conventions extras
- (default xp-conventions.md basta)

### Tech debt paydown
- nenhum    OR    - 0017 (refactor extração X)

### Requires_peer_review
- true | false   (true se path crítico tier=production OR profile flag)
```

| Campo | Quem preenche | Quem consome |
|---|---|---|
| 4-block | Designer (fase 02) | Subagente (fase 04) |
| Depends on | Designer (fase 02) | Wave-planner (DAG aresta explícita) |
| Files touched | Designer; refinado wave-planner | Lead (boundary da branch); Wave-planner (valida ≥1 arquivo de teste) |
| Estimated lines (opcional) | Designer (fase 02) | forensic-plus.py (Check 3 scope creep) |
| ADRs aplicáveis | Designer | Subagente (read order); forensic+ Check 7 (import drift) |
| Lições críticas | Wave-planner (Q10 match) | Subagente (audit pré-RED) |
| Conventions extras | Designer (raro) | Subagente |
| Tech debt paydown | Designer | Subagente (declara em commit) |
| Requires_peer_review | Wave-planner (regra Q6) | Lead (decide spawn QA-pair) |

**Regra `Files touched` — test file obrigatório:** toda task que toca código funcional (`src/`, `app/`, `lib/`, etc.) deve declarar ≥1 arquivo de teste correspondente (`tests/`, `*.test.*`, `*_test.*`, `spec/`, etc.). Wave-planner valida esta regra no pré-voo do DAG; task sem arquivo de teste = `BLOCKED_ERROR` antes de alocar wave. Exceções: tasks declaradas como `doc-only` ou `config-only` em `Conventions extras` são isentas da regra.

---

## 3. Vertical TDD cycle — tracer-first + 1 test → 1 impl → repeat

Todo subagente executa **estritamente** vertical TDD. Anti-horizontal slicing. mattpocock-aligned.

### 3.1 Princípio vertical

Vertical = **completar uma feature unit end-to-end** (test + impl + verify) antes de iniciar a próxima. Horizontal = "escrevo todos os tests primeiro, depois implemento" (proibido).

### 3.2 Tracer-first

Antes do primeiro test unit/integration, subagente escreve **1 tracer test** — E2E golden path da task inteira, mínimo viável, espera-se que falhe inicialmente. Tracer guia a forma da impl, não cobre edge cases.

| Profile | Tracer típico |
|---------|---------------|
| backend | HTTP request → DB assertion (ex: POST /users → user row exists) |
| frontend | render component → user interaction → DOM assertion |
| fullstack | browser action → API call → DB → response render |
| ml | input fixture → model call → output shape assertion |
| agent_ia | prompt fixture → tool sequence → final output match |

Tracer é commitado vermelho como primeiro commit da task. Não conta como cobertura — é scaffold.

### 3.3 Loop por feature unit

Após tracer, subagente itera:

```
LOOP {
  RED      → write 1 test (1 acceptance bullet OR 1 edge case)
  GREEN    → minimal impl pra test passar (não adicione lógica não-testada)
  CI scope → run tests + types + lint só nos files touched (fast feedback)
  REFACTOR → opcional; só se redução de complexity óbvia
}
```

**Cada iteração do loop = 1 commit.** Commits incrementais formam a história TDD verificable em `git log`. Forensic+ Check 1 valida ≥2 asserções no test file final.

### 3.4 Anti-horizontal slicing

❌ **Proibido:**
- Escrever todos os tests da task de uma vez (sem impl entre)
- Implementar todo o impl de uma vez (sem tests entre)
- Pular `RED` ("já sei que vai funcionar")
- Pular `GREEN minimal` (escrever lógica especulativa "pra próximo test")

Sinais que disparam stop:
- Diff > 100 LOC sem novo test correspondente
- Test file com 5+ test names mas impl files vazios
- Impl file com classes completas e tests file vazio

Forensic+ Check 5 (acceptance ↔ test mapping) detecta quando tests não correspondem aos critérios de aceite — gating estrutural anti-horizontal.

### 3.5 Cap de iterações

- **Cap:** 3 attempts da task inteira (cycle inteiro do loop esgotado).
- Falha = forensic+ HARD ou critic REJECT 3 rounds.
- Ao atingir cap → escala lead-resolution tier (3 buckets B1/B3/B4 — ver `references/lead-resolution-protocol.md`).

### 3.6 Stop points dentro do ciclo

Se durante qualquer passo o subagente detecta um stop point (ex: novo paid service não declarado em ADR), ele:

- Pausa o ciclo no estado atual (sem perder progresso).
- Dispara menu A/B/C conforme `stop-points-canonical.md`.
- Sinaliza lead via saída do Agent tool.
- Espera resolução; ciclo retoma do passo onde parou.

### 3.7 Commit verify gate

Antes de declarar COMPLETE, subagente confirma:

```
git log --oneline <BASE>..HEAD  →  ≥1 commit visible
```

Zero commits = task report incomplete; volta ao cycle. forensic+ check estrutural detecta branch HEAD == BASE HEAD.

---

## 4. Integração com superpowers (sumários 200tok)

Subagente na fase 04 tem na pasta `_references/superpowers-summary/` (copiada pelo bootstrap):

| Sumário | Cobre passos |
|---|---|
| `test-driven-development-200tok.md` | RED → GREEN → REFACTOR (vertical) |
| `verification-before-completion-200tok.md` | CI gate scope |
| `systematic-debugging-200tok.md` | suporte quando GREEN trava |

---

## 5. QA delegation — quem garante qualidade

A partir de v3.9.0, QA da task é responsabilidade de:

| Layer | Responsabilidade | Token cost |
|-------|------------------|------------|
| L1 writer (subagente) | Escreve tests vertical, código passa CI scope | (writer model) |
| L2 forensic+ extended | 7 deterministic checks git-only | 0 |
| L3 critic ortogonal | LLM independente (tier ceiling) avalia diff | ~3-8k input |
| L4 wave gate | suite global green + cross-task coherence (production) | (CI infra) |
| Lead-resolution tier | Último recurso quando cap esgota OR catastrophic | (lead model) |

Subagente NÃO escreve checklist QA inline no task report. Self-grading bias documentado (ICLR 2024 Huang, arxiv 2510.11822, arxiv 2509.16533) — delegado a layers ortogonais.

Task report (passo COMPLETE) é minimalista:

```markdown
# Task <slug> — COMPLETE

## Resumo
<1-3 sentences sobre escopo entregue>

## Files modificados
- <list>

## Tests
- <test file>: <count> tests
- Coverage: <%>

## ADRs aplicados
- <list>
```

---

## 6. Exemplo concreto — task `auth-middleware`

Task fictícia que ilustra o schema completo (4-block + metadados; sem checklist Akita).

### 6.1 Entrada do `plan.md` (fase 02 design)

```markdown
## Task auth-middleware: JWT validation middleware

### O QUE
- Middleware Express que valida JWT em headers `Authorization: Bearer <token>`.
- Rejeita 401 quando token ausente, malformado ou expirado.
- Anexa `req.user = { id, email, role }` quando válido.
- Loga falhas (sem PII) com nível `warn`.

### COMO
- Criar `src/auth/middleware.ts` exportando `requireJwt()`.
- Usar lib `jose` (já em ADR 0001-stack), nunca `jsonwebtoken`.
- Verificar assinatura via `JWKS_URI` lido de `process.env.JWKS_URI`.
- Order pipeline: `cors → requireJwt → rateLimit` (lição 0017).
- Erro: throw classes `AuthError`/`AuthExpiredError` capturadas em `errorHandler`.

### NÃO QUERO
- Decodar JWT sem verificar (lição 0042).
- Implementar refresh-token (escopo de outra task).
- Logar valor do token nem email (PII; lição 0033).
- Cachear resultados em memória (out-of-scope; ADR pendente).
- Mock interno de jose nem JWKS client (use boundary mock; ver mocking-guidelines.md).

### VALIDAÇÃO
- Test `test_missing_header_returns_401`: header ausente → 401 + body `{error: "missing_auth"}`.
- Test `test_malformed_jwt_returns_401`: token malformado → 401 + log warn sem PII.
- Test `test_expired_jwt_returns_401`: token expirado → 401 + body `{error: "expired"}`.
- Test `test_valid_token_attaches_user`: token válido → `next()` chamado + `req.user` populado.
- Test `test_pipeline_order_integration`: pipeline order (`cors` antes, `rateLimit` depois) — integration.
- Cobertura ≥90% em `src/auth/middleware.ts`.

### Depends on
- project-setup
- add-user-model

### Files touched
- src/auth/middleware.ts
- src/auth/errors.ts
- tests/auth/middleware.test.ts
- tests/auth/middleware.integration.test.ts

### Estimated lines
~120

### ADRs aplicáveis
- docs/decisions/0001-stack.md
- docs/decisions/0004-auth-strategy.md

### Lições críticas pré-marcadas
- 0042 (never trust decoded JWT without verify)
- 0033 (log auth failures sem PII)
- 0017 (middleware order: cors → auth → rate)

### Conventions extras
- (default xp-conventions.md basta)

### Tech debt paydown
- nenhum

### Requires_peer_review
- true (path /auth, tier=production)
```

### 6.2 Saída esperada do subagente (`task-auth-middleware.md`, COMPLETE)

```markdown
# Task auth-middleware — COMPLETE

## Resumo
Middleware JWT implementado em `src/auth/middleware.ts` (47 LOC) +
classes de erro em `src/auth/errors.ts`. Vertical TDD: tracer + 5 tests +
2 integration. Cobertura 94%.

## Files modificados
- src/auth/middleware.ts (+47 LOC)
- src/auth/errors.ts (+22 LOC)
- tests/auth/middleware.test.ts (+158 LOC, 5 tests)
- tests/auth/middleware.integration.test.ts (+62 LOC, 2 tests)

## Tests
- tests/auth/middleware.test.ts: 5 tests
- tests/auth/middleware.integration.test.ts: 2 tests
- Coverage: 94%

## ADRs aplicados
- 0001-stack (jose lib)
- 0004-auth-strategy (JWKS verification)
```

QA é validado pelos layers L2 (forensic+) + L3 (critic) — ver `references/critic-protocol.md` e `references/forensic-plus-protocol.md`.

---

## 7. Referências cruzadas

| Doc | Conteúdo relacionado |
|---|---|
| `references/doc-reading-protocol.md` | Canais 1/2/3 — quem injeta o quê no subagente |
| `references/wave-planner-algorithm.md` | DAG, Q10 lesson match, Q6 peer-review trigger |
| `references/subagent-protocol.md` | Lead spawn, saída do Agent tool, plan approval |
| `references/stop-points-canonical.md` | 12 stop points + thresholds por tier |
| `references/forensic-plus-protocol.md` | L2 deterministic checks (7 in v3.9.0) |
| `references/critic-protocol.md` | L3 LLM critic ortogonal |
| `references/lead-resolution-protocol.md` | Buckets B1/B3/B4 quando cap esgota |
| `references/mocking-guidelines.md` | Mock só boundaries; nunca internals |
| `references/recovery-wizard.md` | Recuperação se ciclo trava sem COMPLETE |
| `_references/superpowers-summary/test-driven-development-200tok.md` | Sumário TDD vertical |
| `_references/superpowers-summary/verification-before-completion-200tok.md` | Sumário CI gate |

---

## 8. AGENT-BRIEF compatibility

A partir de v3.3.0, todo 4-block deve ser parseável pelo
`scripts/agent-brief-render.py` em fase 04. v3.9.0 adiciona model fields
no header. Mapping:

| 4-block | AGENT-BRIEF section |
|---|---|
| **O QUE:** | `Summary:` (1ª linha) + `Desired behavior:` (corpo) |
| **COMO:** | `Key interfaces:` (sem paths absolutos / line numbers) |
| **NÃO QUERO:** | `Out of scope:` |
| **VALIDAÇÃO:** | `Acceptance criteria:` (lista testável) |

Adicionalmente, o bloco da task no plan.md DEVE ter:
- `**Type:** AFK` ou `**Type:** HITL` (ver `task-types-hitl-afk.md`)
- `**Files touched:** path1, path2` (sem line numbers)

v3.9.0 brief header:
```yaml
model_recommended_writer: <claude-haiku-4-5|claude-sonnet-4-6|claude-opus-4-7>
model_recommended_critic: <claude-haiku-4-5|claude-sonnet-4-6|claude-opus-4-7>
complexity_score: <int>
```

Doc canônico do AGENT-BRIEF: `references/agent-brief-template.md`.
