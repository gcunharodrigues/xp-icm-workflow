# Matriz canônica de profiles × tiers

Esta é a **fonte humana** da matriz que `scripts/profile-merge.py` aplica no merge
profile + tier (+ override). O script tem cópia hardcoded por
performance/atomicidade — em caso de divergência, o script é a fonte da verdade
operacional; este documento existe para revisão e onboarding.

## Profiles canônicos (11)

| Profile             | Descrição curta                                              |
|---------------------|--------------------------------------------------------------|
| `app_web_backend`   | API/serviço backend HTTP (FastAPI, Django, Express…)         |
| `app_web_frontend`  | SPA/SSR navegador (Next.js, SvelteKit, Remix…)               |
| `fullstack`         | Backend + frontend coexistem mesmo repo (Next.js+API routes, T3, Remix+Prisma, Django+React colocated). Pra monorepo apps/web+apps/api separados, prefira 2 workspaces. |
| `dashboard`         | Painel analítico (Streamlit, Dash, Looker, Superset…)        |
| `data_analysis`     | Análise pontual, notebook orientado a relatório              |
| `ml_project`        | Pipeline ML completo (treino, eval, serving)                 |
| `agent_ia`          | Agente LLM/orquestrador com tools (skills, MCP, scripts)     |
| `cli_tool`          | Ferramenta de linha de comando standalone                    |
| `framework_library` | Biblioteca/framework reutilizável (publicado em registry)    |
| `technical_article` | Artigo técnico longo com código embutido                     |
| `experiment`        | Spike/POC descartável ou bench rápido                        |

## Tiers canônicos (4)

| Tier            | Quando usar                                                            |
|-----------------|------------------------------------------------------------------------|
| `experimental`  | Spike/POC; código provavelmente descartável                            |
| `tool`          | Ferramenta interna de uso recorrente, mas não crítica                  |
| `development`   | Sistema em construção que entrará em uso real                          |
| `production`    | Sistema em produção com usuários reais e/ou dados sensíveis            |

## Defaults por tier (sem profile override)

| Chave                       | experimental         | tool                  | development           | production                  |
|-----------------------------|----------------------|-----------------------|-----------------------|-----------------------------|
| `tdd_required`              | False (optional)     | False (recommended)   | True (required)       | True (required)             |
| `security_gate`             | False                | False                 | True (on)             | True (on+LGPD)              |
| `tech_debt_tracking`        | False                | True                  | True                  | True                        |
| `peer_review_required`      | False                | False                 | False                 | True                        |
| `cap_subagents_per_wave`    | 2                    | 3                     | 5                     | 5                           |
| `stop_points_calibration.item_5` (serviço pago)  | warning, R$ 50  | hard, R$ 200    | hard, R$ 500          | hard, R$ 1000               |
| `stop_points_calibration.item_7` (over-eng.)     | warning         | warning         | hard                  | hard                        |
| `stop_points_calibration.item_8` (PII/LGPD)      | warning         | hard            | hard                  | hard+DPO                    |
| `stages_skipped` (default)  | `[]`                 | `[]`                  | `[]`                  | `[]`                        |
| `test_specs.coverage_threshold` | 0 (sem mínimo)  | 60                    | 80                    | 90                          |

## test_specs por profile

Campo `test_specs` é calculado por `scripts/profile-merge.py` com base em profile + tier.
**Não está na lista de `overrides` permitidos** — é derivado, não configurável via `.icm-profile.local.yaml`.

### Estrutura de `test_specs`

```yaml
test_specs:
  test_types_required: []         # lista: unit, integration, e2e, component, eval, pipeline, model_eval
  coverage_threshold: 0           # int % (linhas/branches); 0 = sem mínimo
  test_location: "tests/"         # convenção de localização de arquivos de teste
  http_integration: false         # backend: deve testar endpoints HTTP reais
  db_integration: false           # backend: deve testar contra DB real/test
  component_testing: false        # frontend: deve usar component testing (RTL/etc)
  e2e_required: false             # frontend: E2E obrigatório
  visual_regression: false        # frontend: visual regression (prod only)
  a11y_testing: false             # frontend: acessibilidade (axe)
  eval_strategy: null             # agent_ia: "golden_output_similarity" | null
  eval_threshold: null            # agent_ia: float 0-1 | null
  deterministic_tools_only: false # agent_ia: apenas tool calls são unit-testáveis
  pipeline_testing: false         # ml_project: testa pipeline de dados
  model_regression: false         # ml_project: regressão de performance de modelo
```

### test_specs por profile (valores canônicos)

| Profile | test_types_required | Notas |
|---|---|---|
| `app_web_backend` | `[unit, integration]` | `http_integration: True`, `db_integration: True` |
| `app_web_frontend` | `[unit, component, e2e]` | `component_testing: True`, `e2e_required: True` (dev+prod), `visual_regression: True` (prod), `a11y_testing: True` (dev+prod), `test_location: src/` (co-located), `design_system_required: True` |
| `fullstack` | `[unit, integration, component, e2e]` | Superset backend+frontend: `http_integration: True`, `db_integration: True`, `component_testing: True`, `e2e_required: True` (dev+prod), `visual_regression: True` (prod), `a11y_testing: True` (dev+prod), `design_system_required: True`, `test_location: tests/` |
| `dashboard` | `[unit, integration]` | `http_integration: True`, semelhante a backend |
| `data_analysis` | `[unit]` | Notebooks: testar funções de transformação; sem integration obrigatória |
| `ml_project` | `[unit, pipeline, model_eval]` | `pipeline_testing: True`, `model_regression: True` (dev+prod) |
| `agent_ia` | `[unit_tools, integration_prompt, eval]` | `eval_strategy: golden_output_similarity`, `deterministic_tools_only: True`, `eval_threshold: 0.85` (dev+prod) |
| `cli_tool` | `[unit, integration]` | integration = subprocess testing, stdin/stdout capture |
| `framework_library` | `[unit, integration]` | coverage_threshold +10% (libs exigem cobertura maior por serem reusadas) |
| `technical_article` | `[unit]` (se houver código) | Artigo sem código executável: `test_types_required: []` |
| `experiment` | `[]` | Sem requisitos de teste — spike descartável |

## Profile-specific overrides (aplicados sobre defaults de tier)

### `experiment`

- `stages_skipped` = `["03", "05", "06", "08"]` em **todos** os tiers.
- Justificativa: spike descartável pula testes (03), arquitetura formal (05),
  documentação (06) e operacionalização (08).

### `technical_article`

- `stages_skipped = ["03"]` (artigo não roda CI/automação de testes; tier `experimental` herda `["03", "05", "06", "08"]` com `03` já incluso — deduplicado automaticamente por `profile-merge.py`).
- `cap_subagents_per_wave` = 5 (artigo longo pode paralelizar revisão).

### `framework_library`

- `cap_subagents_per_wave` = 3 (framework requer coesão de design; cap menor).

### `ml_project`

- `cap_subagents_per_wave` = 3 (pipelines ML demandam continuidade de
  hiperparâmetros e dados; paralelismo alto fragmenta entendimento).

### `app_web_backend`, `app_web_frontend` e `fullstack`

- `security_gate` = True em qualquer tier ≠ `experimental`. App web exposto à
  rede sempre passa por gate de segurança, mesmo em `tool`.

### `app_web_frontend` e `fullstack`

- `design_system_required` = True (todos os tiers). Stage 02 design cria/atualiza
  `<project_root>/.icm-main/DESIGN.md` (formato Google Stitch DESIGN.md spec).
  Doc canônico: `references/design-system.md`. Subagentes em fase 04 ganham
  DESIGN.md no canal 2 quando task tem files frontend.
- **Preview loop config (v3.6.0):** flags adicionais derivadas pelo
  `profile-merge.py`, alimentam o ciclo build-iterate visual descrito em
  `references/preview-loop-protocol.md`:

  | Chave                       | Valor por tier                                                                                       |
  |-----------------------------|------------------------------------------------------------------------------------------------------|
  | `preview_loop_enabled`      | `True` em todos os tiers                                                                              |
  | `mock_data_strategy`        | experimental → `fixtures` · tool → `fixtures` · development → `msw_faker` · production → `msw_faker_zod` |
  | `cdp_live_enabled`          | `True` em todos os tiers (opt-out via override `cdp_live_enabled: false`)                              |
  | `visual_iter_cap`           | `null` em todos os tiers (sem cap — humano fecha quando OK)                                            |
  | `design_cascade_threshold`  | `5` em todos os tiers (calibrável via override)                                                       |
  | `preview_pages_path`        | `preview/` (convenção, não-configurável)                                                              |

  Defaults aplicáveis: dev server starta entry stage 04 + mata exit
  (`scripts/bootstrap.py` detecta package manager via lockfile);
  Chrome CDP via `templates/.claude/scripts/launch-chrome-cdp.{bat,sh}`;
  preview pages em `preview/<component>/page.tsx` excluídos do build
  production. Recovery wizard cobre `DEV_SERVER_ORPHAN` + `CDP_DISCONNECTED`.

## Override local: `.icm-profile.local.yaml`

Schema completo:

```yaml
extends: app_web_backend         # obrigatório; ∈ profiles canônicos
tier: development                # obrigatório; ∈ tiers canônicos
overrides:                       # opcional; dict com chaves da matriz
  cap_subagents_per_wave: 3
  stages_skipped: ["08"]
custom_stop_points:              # opcional; D3 — stops adicionais ao projeto
  - id: custom_1
    description: "checagem específica do projeto"
    threshold:
      experimental: warning
      development: hard
revisit_after: "2026-08-01"      # opcional; ISO 8601 (Q16 A')
confirm_unsafe: false            # default false; true necessário pra desligar gates críticos (Q16 A'')
```

### Chaves de `overrides` permitidas

Apenas as 7 chaves canônicas da matriz:

- `stages_skipped`
- `tdd_required`
- `security_gate`
- `tech_debt_tracking`
- `peer_review_required`
- `cap_subagents_per_wave`
- `stop_points_calibration`

Qualquer outra chave em `overrides` → erro de validação.

### Guard-rail: `confirm_unsafe`

Override que **desliga** (de True → False) qualquer um destes três gates exige
`confirm_unsafe: true` no arquivo:

- `tdd_required`
- `security_gate`
- `peer_review_required`

Sem `confirm_unsafe: true` → `ProfileMergeError("override perigoso requer confirm_unsafe: true")`.

Ligar gates (False → True) é sempre seguro e não exige confirmação.

### `custom_stop_points` (D3)

Lista opcional de stop points adicionais ao projeto. Cada item exige:

- `id` — string não-vazia.
- `description` — string não-vazia.
- `threshold` — dict não-vazio cujas chaves ∈ tiers canônicos e cujos valores
  representam o modo (`warning` / `hard` / etc.) por tier.

### `revisit_after` (Q16 A')

ISO 8601 estrito: `YYYY-MM-DD` ou `YYYY-MM-DDTHH:MM:SS`. Outros formatos
(`agosto/2026`, `2026-08`, etc.) → erro.

## Hash determinístico

`scripts/profile-merge.py` calcula SHA256 hex (64 chars) do profile efetivo
serializado em YAML com `sort_keys=True`, `default_flow_style=False`,
`allow_unicode=True`. Mesmo input → mesmo hash sempre. Útil para gravar o estado
do projeto e detectar drift do `.icm-profile.local.yaml`.
