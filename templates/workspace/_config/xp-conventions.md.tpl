---
layer: L3
scope: conventions
workspace: "{{WORKSPACE}}"
profile: "{{PROFILE}}"
tier: "{{TIER}}"
---

# Conventions — {{WORKSPACE}}

Convenções de código e processo para este workspace. Derivadas do profile `{{PROFILE}}` / tier `{{TIER}}`.

**Linhagem:** regras de Clean Code e TDD vindas da skill `xp-workflow` v3 (Akita: "Clean Code pra Agentes de IA"). Este documento é a ponte — a skill ICM não invoca `xp-workflow` no runtime, mas suas convenções são materializadas aqui e no auto-QA Akita (15 itens, `references/4-block-contract-template.md` §5).

## Naming

- **Arquivos:** kebab-case (`user-model.ts`, `auth-routes.py`)
- **Diretórios:** kebab-case (`api-handlers/`, `data-pipelines/`)
- **Identificadores de código:** seguir convenção da linguagem (camelCase JS, snake_case Python)
- **Nomes grep-friendly:** `rg "<nome>"` deve retornar <5 hits não-relacionados. Se retornar mais, renomeie para ser mais específico.
- **Termos de domínio sem tradução boa:** permitidos em PT (`nota_fiscal`, `cnpj`, `cpf`, `cfop`, `icms`). Todo o resto em inglês.
- **ADRs:** `NNNN-slug.md` em `docs/decisions/`

## Funções & Arquivos (Clean Code gates)

- **Funções:** 4-20 linhas. Excede só com justificativa em comentário. Se >20, dividir.
- **Arquivos:** <300 linhas = ok. 300-500 = avisar. >500 = dividir obrigatoriamente.
- **Nesting:** máx 2 níveis. Preferir early return. If/else profundo = refatorar.
- **Duplicação:** zero tolerância. Se copiou, extrair. Cada duplicação é dívida técnica imediata.
- **DI via construtor/parâmetro.** Nunca global. Injeção explícita = testável.

## Tipos & Fronteiras

- **Tipos explícitos** em params, returns e exports. Sem `any`, sem `untyped` function.
- **Mensagens de erro** incluem valor ofensivo + forma esperada: `Expected UserDTO, got null` (não `Invalid input`).
- **Fronteiras** (input do user, API externa, banco): validação explícita e defensiva. Interior do módulo: confiar nos tipos.

## Imports & Structure

- Imports agrupados: stdlib → third-party → local
- Ordem: ordem alfabética dentro de cada grupo
- Path aliases: declarar em `tsconfig.json` / `pyproject.toml` conforme linguagem
- **Imports circulares:** zero. Se detectado, refatorar imediatamente.
- **Código morto:** zero. Funções, imports e variáveis não usadas = delete no refactor.

## Docstrings & Comentários

- **Docstrings em PT obrigatórias** em toda função pública. 4 elementos:
  1. O que faz (linguagem clara)
  2. Pra que serve (necessidade do projeto)
  3. Entradas e saídas (em termos práticos)
  4. Avisos de efeito colateral (grava no banco, chama API externa, apaga arquivo)
- **Comentários inline:** WHY, não WHAT. Exceção: referência técnica (RFC, issue, commit SHA).
- **Comentários com proveniência:** agente preserva comentários que escreveu. Não podar.
- **Comentários comentados-out (código fantasma):** zero. Delete ou git-blame.

## Formatting

- Linter: seguir default da linguagem (ESLint/Prettier para JS, Ruff/Black para Python)
- Max line length: 120 caracteres
- Indentação: 2 espaços (JS/TS), 4 espaços (Python)

## Git

- Commits em workspace branch: prefixo obrigatório `workspace {{WORKSPACE_NUM}}:` (validado por commit-msg hook). Formato: `workspace {{WORKSPACE_NUM}}: <descrição>` ou `workspace {{WORKSPACE_NUM}}: <type>: <descrição>` (type = feat/fix/refactor/test/docs/chore/perf/ci, opcional mas recomendado).
- Commits em wave branches (`wave-{{WORKSPACE}}-<N>/<task>`): Conventional Commits padrão sem prefix ICM. Formato: `<type>: <descrição>`. Exemplos: `feat: add JWT validation`, `test: unit tests for auth middleware`.
- Branches: `workspace/{{WORKSPACE}}` para state files, `wave-{{WORKSPACE}}-<N>/<task>` para código
- Nunca `--no-verify` no workspace branch

## Testing (calibrado por tier)

- **experimental:** TDD opcional
- **tool:** TDD recomendado
- **development:** TDD obrigatório
- **production:** TDD obrigatório + security gate

Ciclo canônico por task (7 passos): RED → GREEN → CI gate → REFACTOR → CI gate → Auto-QA Akita → COMPLETE. Detalhes em `references/4-block-contract-template.md` §3.

### Dirt Check (pós-cycle, passo 6 do Akita)

Após cada ciclo TDD, 3 perguntas obrigatórias:
1. Há duplicação introduzida neste cycle? Fatore agora.
2. Algum nome ficou genérico/grepável ruim? Renomeie agora.
3. Função passou de 20 linhas ou arquivo passou de 300? Divida agora.

## Security (calibrado por tier)

- **experimental:** sem gate
- **tool:** sem gate
- **development:** security gate on (item 8 PII)
- **production:** security gate on + DPO (item 8 hard+DPO)

### Secrets & PII

- Nunca commit de `.env`, credenciais, API keys, tokens.
- Sempre `.env.example` com placeholders.
- Leitura via env var only. Nunca hardcoded em código.
- Logs não contêm PII nem tokens. Loga tipo de erro + contexto anônimo, nunca valor.
- Se secret vazar: rotacionar imediatamente, documentar incidente em `docs/lessons.md`.

## Clean Code gates por linguagem (CI + pre-commit)

Aplicado conforme stack declarado em ADRs. Cada gate enforced por ferramenta, não por review manual.

| Gate | Python | TypeScript/JS | Outras |
|---|---|---|---|
| Formatter | `ruff format` / `black` | `prettier` | default da linguagem |
| Linter | `ruff` | `eslint` | linter canônico |
| Type check | `mypy --strict` | `tsc --strict` | nativo ou `--strict` equivalente |
| Complexity | `radon`, `xenon` | `eslint-plugin-sonarjs` | ferramenta equivalente |
| Duplicação | `pylint --duplicate-code` | `jscpd` | ferramenta equivalente |
| Size (func/file) | linter custom | `eslint max-lines` | linter custom |
| Security | `bandit`, `pip-audit` | `npm audit`, `semgrep` | ferramenta equivalente |
| Secrets | `gitleaks` | `gitleaks` | `gitleaks` |
| Coverage | `pytest-cov` | `vitest --coverage` | ferramenta equivalente |

**Tier calibra rigor:** gates obrigatórios em `development` e `production`. `tool` roda formatter + linter + secrets. `experimental` roda só formatter.

## Stop Points

Detalhados em `_config/stop-points.md` (renderizado pelo bootstrap com calibração por tier).

## Dependências de runtime

- **jq** — obrigatório para hook `context-check.sh` (anti-compact). Se ausente, o hook falha silenciosamente (nenhum alerta de contexto, mas a sessão continua). Instalar via gerenciador de pacotes do OS (`apt install jq`, `brew install jq`, `choco install jq`).