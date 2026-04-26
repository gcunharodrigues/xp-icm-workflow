<!--
Fixture canonica para Wave Planner DAG.

Expected output (development tier, app_web_backend profile, cap=5):

Topologia esperada:
  Wave 1: auth-middleware, user-model, logger-setup            (3 tasks, sem deps)
  Wave 2: auth-routes, user-routes, audit-log                  (3 tasks)
           - auth-routes depends_on auth-middleware + user-model
           - user-routes depends_on user-model
           - audit-log depends_on logger-setup
  Wave 3: auth-routes-v2, dashboard                            (2 tasks)
           - auth-routes-v2: file-conflict com auth-routes (mesmo arquivo
             src/auth/routes.ts) -> serializado para wave 3.
           - dashboard depends_on auth-routes + audit-log

  total_tasks=8 total_waves=3 total_sub_waves=3 ambiguities>=1

Cap=5 com no maximo 3 tasks por wave -> nenhuma sub-wave dividida.

Notas:
  - Ambiguidades sao detectadas (pares de tasks no mesmo dir sem intersecao
    exata em files_touched, ex.: src/auth/middleware.ts vs src/auth/routes.ts).
    Particionamento nao muda; LLM revisa depois.
  - Conflitos de arquivo serializados: auth-routes <-> auth-routes-v2
    (ambos tocam src/auth/routes.ts).
-->

## Task auth-middleware: Auth Middleware

### 4-block
O QUE / COMO / NAO QUERO / VALIDACAO

### Files touched
- src/auth/middleware.ts
- tests/auth/middleware.test.ts

### Depends on
- nenhum

### ADRs aplicaveis
- docs/decisions/0001-stack.md

### Licoes criticas pre-marcadas
- 0033

### Tech debt paydown
- nenhum

### Requires_peer_review
- false

## Task user-model: User Model

### 4-block
O QUE / COMO / NAO QUERO / VALIDACAO

### Files touched
- src/models/user.ts
- tests/models/user.test.ts

### Depends on
- nenhum

### ADRs aplicaveis

### Licoes criticas pre-marcadas

### Tech debt paydown
- nenhum

### Requires_peer_review
- false

## Task logger-setup: Logger Setup

### 4-block
O QUE / COMO / NAO QUERO / VALIDACAO

### Files touched
- src/utils/logger.ts

### Depends on

### ADRs aplicaveis

### Licoes criticas pre-marcadas

### Tech debt paydown

### Requires_peer_review
- false

## Task auth-routes: Auth Routes

### 4-block
O QUE / COMO / NAO QUERO / VALIDACAO

### Files touched
- src/auth/routes.ts
- tests/auth/routes.test.ts

### Depends on
- auth-middleware
- user-model

### ADRs aplicaveis

### Licoes criticas pre-marcadas

### Tech debt paydown

### Requires_peer_review
- true

## Task user-routes: User Routes

### 4-block
O QUE / COMO / NAO QUERO / VALIDACAO

### Files touched
- src/users/routes.ts
- tests/users/routes.test.ts

### Depends on
- user-model

### ADRs aplicaveis

### Licoes criticas pre-marcadas

### Tech debt paydown

### Requires_peer_review
- false

## Task audit-log: Audit Log

### 4-block
O QUE / COMO / NAO QUERO / VALIDACAO

### Files touched
- src/audit/log.ts

### Depends on
- logger-setup

### ADRs aplicaveis

### Licoes criticas pre-marcadas

### Tech debt paydown

### Requires_peer_review
- false

## Task auth-routes-v2: Auth Routes V2

### 4-block
O QUE / COMO / NAO QUERO / VALIDACAO

### Files touched
- src/auth/routes.ts

### Depends on
- nenhum

### ADRs aplicaveis

### Licoes criticas pre-marcadas

### Tech debt paydown

### Requires_peer_review
- false

## Task dashboard: Dashboard

### 4-block
O QUE / COMO / NAO QUERO / VALIDACAO

### Files touched
- src/dashboard/index.ts

### Depends on
- auth-routes
- audit-log

### ADRs aplicaveis

### Licoes criticas pre-marcadas

### Tech debt paydown

### Requires_peer_review
- true
