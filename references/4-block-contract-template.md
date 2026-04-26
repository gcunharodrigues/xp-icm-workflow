# 4-Block Contract Template + Ciclo TDD 7 Passos

> **Versão:** v3.0.0-beta1
> **Skill:** `xp-icm-workflow`
> **Propósito:** Define o contrato 4-block obrigatório por task no `plan.md` (output da fase 02 design, consumido pelas fases 03 wave_planner e 04 implementation_waves) **e** o ciclo TDD canônico de 7 passos que todo teammate executa por task. Inclui o auto-QA Akita (checklist 15-item) aplicado no passo 6 e o cap de 3 voltas que dispara escalonamento ao lead.

> **Decisão de origem:** F1 do plan `reescrever-a-skill-zazzy-wirth.md` (linha 57) + §4.4 dev↔qa loop + §4.11 canal 3 (plan.md schema).

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
 Lista clara, cada item verificável.
 3-7 bullets.>
```

### Por que 4 blocos (e não 3 ou 5)

| Bloco | Sem ele... |
|---|---|
| O QUE | Teammate inventa requisito; QA não tem âncora pra validar |
| COMO | Decisões arquiteturais divergem entre tasks paralelas da mesma wave |
| NÃO QUERO | Scope creep silencioso; teammate adiciona "enquanto está aqui..." |
| VALIDAÇÃO | Tests cobrem o que o dev achou interessante, não o que importa |

---

## 2. Schema completo de task no `plan.md`

Além dos 4 blocos, cada task declara metadados consumidos pelo lead da fase 04 (canal 3 do doc-reading-protocol):

```markdown
## Task <SLUG>: <Título>

### O QUE / COMO / NÃO QUERO / VALIDAÇÃO
<vide §1>

### Files touched
- src/path/file.ts
- tests/path/file.test.ts

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
| 4-block | Designer (fase 02) | Teammate (fase 04) |
| Files touched | Designer; refinado wave-planner | Lead (worktree boundary) |
| ADRs aplicáveis | Designer | Teammate (read order) |
| Lições críticas | Wave-planner (Q10 match) | Teammate (audit pré-RED) |
| Conventions extras | Designer (raro) | Teammate |
| Tech debt paydown | Designer | Teammate (declara em commit) |
| Requires_peer_review | Wave-planner (regra Q6) | Lead (decide spawn QA-pair) |

---

## 3. Ciclo TDD 7 passos — ordem canônica

Todo teammate executa **exatamente** esta sequência por task. CI gate roda 2x (passos 3 e 5) — princípio "verde antes do refactor, verde depois do refactor".

| Passo | Nome | Ação | Saída |
|---|---|---|---|
| 1 | RED | Escrever test que falha (cobre VALIDAÇÃO da task) | Test rodando vermelho |
| 2 | GREEN | Implementar mínimo pra test passar | Test verde |
| 3 | CI gate local (1ª) | `lint` + `type-check` + `tests` | Tudo verde |
| 4 | REFACTOR | Melhorar código mantendo tests verde | Código limpo, tests inalterados |
| 5 | CI gate local (2ª) | `lint` + `type-check` + `tests` | Garante que refactor não quebrou |
| 6 | Auto-QA Akita | Checklist 15-item (vide §5) | Todos ✅ ou volta passo 4/3 |
| 7 | COMPLETE | Escreve `task-<slug>.md` em `stages/04/output/wave-N/`, sinaliza COMPLETE | Lead detecta e procede |

### 3.1 Cap de iterações

- **Cap:** 3 voltas sem convergir (auto-QA falha 3× seguidas).
- Ao atingir cap:
  1. Teammate seta no próprio task report `status: BLOCKED_ERROR`.
  2. Sinaliza ao lead via mailbox: `stages/04/output/wave-N/mailbox/<task-slug>-blocked.md` (descreve item Akita que falha repetidamente + tentativas).
  3. Pausa e espera lead intervir (lead pode escalar humano).
- Cada `❌` no Akita conta como 1 ciclo (não cada item; a volta inteira).

### 3.2 Stop points dentro do ciclo

Se durante qualquer passo o teammate detecta um stop point (ex: novo paid service não declarado em ADR), ele:

- Pausa o ciclo no estado atual (sem perder progresso).
- Dispara menu A/B/C conforme `stop-points-canonical.md`.
- Sinaliza lead via mailbox.
- Espera resolução; ciclo retoma do passo onde parou.

---

## 4. Integração com superpowers (sumários 200tok)

Teammate na fase 04 tem na pasta `_references/superpowers-summary/` (criada na Wave 5 da skill):

| Sumário | Cobre passos |
|---|---|
| `test-driven-development-200tok.md` | 1, 2, 4 (RED → GREEN → REFACTOR) |
| `verification-before-completion-200tok.md` | 3, 5 (CI gates) |
| `systematic-debugging-200tok.md` | suporte quando passo 2 ou 5 trava |

---

## 5. Auto-QA Akita — checklist 15-item

Aplicado **no passo 6**. Teammate marca cada item ✅/❌. **Qualquer `❌` força volta** ao passo 4 (refactor) ou passo 3 (impl), e conta como 1 volta no cap de 3.

| # | Item | Foco |
|---|---|---|
| 1 | Tests cobrem golden path? | Cobertura |
| 2 | Tests cobrem edge cases relevantes (empty input, boundary, error)? | Cobertura |
| 3 | Tests não-flaky (sem `sleep` arbitrário, sem ordem implícita)? | Confiabilidade |
| 4 | Clean code re-ranqueado (Akita): nomes claros, fluxo linear, abstrações justificadas? | Estilo |
| 5 | Tipos explícitos em fronteiras (params, returns, exports)? | Estilo |
| 6 | Functions 4-20 linhas (excede só com justificativa)? | Estilo |
| 7 | Comentários quando há (explicam WHY não WHAT)? | Estilo |
| 8 | Sem código morto (funcs/imports/vars não usadas)? | Higiene |
| 9 | Sem comentários commented-out (código fantasma)? | Higiene |
| 10 | Imports organizados + nenhum import circular? | Higiene |
| 11 | Error handling explícito em boundaries (input do user, API externa)? | Robustez |
| 12 | Secrets/PII protegidos (não em logs, não em tests)? | Segurança |
| 13 | ADR compliance (segue stack/padrão declarado em `docs/decisions`)? | Aderência |
| 14 | Tech debt declarado (qualquer atalho/TODO commitado em `docs/tech_debt.md`)? | Aderência |
| 15 | Commit message segue convenção do repo (conventional commits, scope correto)? | Aderência |

### 5.1 Como teammate registra checklist no task report

No `task-<slug>.md` (passo 7 COMPLETE), seção dedicada:

```markdown
## Auto-QA Akita
- Ciclos: <N>
- Resultado final: ✅ all green | ❌ blocked at item <X>
- [✅] 1. Tests cobrem golden path? — evidência: `tests/auth/middleware.test.ts::test_rejects_invalid_token`
- [✅] 2. Tests cobrem edge cases? — evidência: `test_empty_authorization_header`, `test_malformed_jwt`
- [✅] 3. Tests não-flaky? — evidência: 50× `pytest -p no:randomly` sem flake
- [✅] 4. Clean code Akita? — evidência: 3 funcs ≤15 linhas, fluxo linear
... (15 linhas)
```

---

## 6. Exemplo concreto — task `auth-middleware`

Task fictícia que ilustra o schema completo (4-block + metadados + auto-QA registrado).

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

### VALIDAÇÃO
- Test: header ausente → 401 + body `{error: "missing_auth"}`.
- Test: token malformado → 401 + log warn sem PII.
- Test: token expirado → 401 + body `{error: "expired"}`.
- Test: token válido → `next()` chamado + `req.user` populado.
- Test: pipeline order (`cors` antes, `rateLimit` depois) — integration.
- Cobertura ≥90% em `src/auth/middleware.ts`.

### Files touched
- src/auth/middleware.ts
- src/auth/errors.ts
- tests/auth/middleware.test.ts
- tests/auth/middleware.integration.test.ts

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

### 6.2 Saída esperada do teammate (`task-auth-middleware.md`, passo 7)

```markdown
# Task auth-middleware — COMPLETE

## Resumo
Middleware JWT implementado em `src/auth/middleware.ts` (47 LOC) +
classes de erro em `src/auth/errors.ts`. 6 unit tests + 2 integration tests.
Cobertura 94%.

## Auto-QA Akita
- Ciclos: 2 (1ª volta falhou item 12; corrigido removendo `console.log(token)`)
- Resultado final: ✅ all green
- [✅] 1. Golden path? — `test_valid_token_attaches_user`
- [✅] 2. Edge cases? — `test_missing_header`, `test_malformed_jwt`, `test_expired`
- [✅] 3. Não-flaky? — 50 runs consecutivos verde
- [✅] 4. Akita re-rank? — funcs 8/12/15 LOC, nomes claros
- [✅] 5. Tipos? — `RequestHandler<...>` explícito
- [✅] 6. 4-20 linhas? — sim
- [✅] 7. Comentários WHY? — comentário em `verifyJwt` justifica `clockTolerance: 5`
- [✅] 8. Código morto? — nenhum
- [✅] 9. Comentários fantasma? — nenhum
- [✅] 10. Imports? — organizados, sem circulares
- [✅] 11. Error handling? — `AuthError`/`AuthExpiredError` em boundaries
- [✅] 12. Secrets/PII? — log usa `req.ip` + erro tipo, nunca token nem email
- [✅] 13. ADR compliance? — usa `jose` (0001), JWKS strategy (0004)
- [✅] 14. Tech debt? — nenhum atalho declarado
- [✅] 15. Commit msg? — `feat(auth): add JWT middleware (closes wave-1/task-auth-middleware)`
```

---

## 7. Referências cruzadas

| Doc | Conteúdo relacionado |
|---|---|
| `references/doc-reading-protocol.md` | Canais 1/2/3 — quem injeta o quê no teammate |
| `references/wave-planner-algorithm.md` | DAG, Q10 lesson match, Q6 peer-review trigger |
| `references/agent-team-protocol.md` | Lead spawn, mailbox, plan approval |
| `references/stop-points-canonical.md` | 12 stop points + thresholds por tier |
| `references/recovery-wizard.md` | Recuperação se ciclo trava no passo 7 sem COMPLETE |
| `_references/superpowers-summary/test-driven-development-200tok.md` | Sumário TDD (Wave 5) |
| `_references/superpowers-summary/verification-before-completion-200tok.md` | Sumário CI gate (Wave 5) |
