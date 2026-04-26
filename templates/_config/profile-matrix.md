# Matriz canônica de profiles × tiers

Esta é a **fonte humana** da matriz que `scripts/profile-merge.py` aplica no merge
profile + tier (+ override). O script tem cópia hardcoded por
performance/atomicidade — em caso de divergência, o script é a fonte da verdade
operacional; este documento existe para revisão e onboarding.

## Profiles canônicos (10)

| Profile             | Descrição curta                                              |
|---------------------|--------------------------------------------------------------|
| `app_web_backend`   | API/serviço backend HTTP (FastAPI, Django, Express…)         |
| `app_web_frontend`  | SPA/SSR navegador (Next.js, SvelteKit, Remix…)               |
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
| `cap_teammates_per_wave`    | 2                    | 3                     | 5                     | 5                           |
| `stop_points_calibration.item_5` (serviço pago)  | warning, R$ 50  | hard, R$ 200    | hard, R$ 500          | hard, R$ 1000               |
| `stop_points_calibration.item_7` (over-eng.)     | warning         | warning         | hard                  | hard                        |
| `stop_points_calibration.item_8` (PII/LGPD)      | warning         | hard            | hard                  | hard+DPO                    |
| `stages_skipped` (default)  | `[]`                 | `[]`                  | `[]`                  | `[]`                        |

## Profile-specific overrides (aplicados sobre defaults de tier)

### `experiment`

- `stages_skipped` = `["03", "05", "06", "08"]` em **todos** os tiers.
- Justificativa: spike descartável pula testes (03), arquitetura formal (05),
  documentação (06) e operacionalização (08).

### `technical_article`

- `stages_skipped` ⊇ `["03"]` (artigo não roda CI/automação de testes).
- `cap_teammates_per_wave` = 5 (artigo longo pode paralelizar revisão).

### `framework_library`

- `cap_teammates_per_wave` = 3 (framework requer coesão de design; cap menor).

### `ml_project`

- `cap_teammates_per_wave` = 3 (pipelines ML demandam continuidade de
  hiperparâmetros e dados; paralelismo alto fragmenta entendimento).

### `app_web_backend` e `app_web_frontend`

- `security_gate` = True em qualquer tier ≠ `experimental`. App web exposto à
  rede sempre passa por gate de segurança, mesmo em `tool`.

## Override local: `.icm-profile.local.yaml`

Schema completo:

```yaml
extends: app_web_backend         # obrigatório; ∈ profiles canônicos
tier: development                # obrigatório; ∈ tiers canônicos
overrides:                       # opcional; dict com chaves da matriz
  cap_teammates_per_wave: 3
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
- `cap_teammates_per_wave`
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
