# Contributing — xp-icm-workflow

Obrigado por contribuir. Este doc cobre fluxo de PR, regras de código, gates de drift e padrões de commit.

---

## Antes de começar

1. Leia [README.md](README.md) (visão geral) + [SKILL.md](SKILL.md) (entrada da skill).
2. Familiarize-se com [`references/example-run.md`](references/example-run.md) (E2E concreto).
3. Rode o suite local pra confirmar setup:
   ```bash
   pip install -r requirements.txt
   bash scripts/check-runtime.sh
   bash tests/run.sh --no-bats   # 782+ tests devem passar
   ```

Se algo quebra antes de você editar nada, abra issue antes de PR.

---

## Tipos de contribuição aceitos

- **Bug fix** com teste cobrindo regressão.
- **Feature** após discussão em issue (evita rework).
- **Docs** (typos, clarificações, exemplos novos).
- **Tests** adicionais (cobertura de edge cases, fuzzing, property-based via Hypothesis).
- **Refactor** se acompanhado de tests + sem mudança de comportamento.

**Não aceito sem discussão prévia:**

- Mudança de schema L0/L1 (impacta backward compat).
- Adição de novo profile ou tier (impacta matrix 11×4 → 12×4).
- Remoção de stop point canônico.
- Mudança de protocolo de saída fase 08.

Abra issue marcada `discussion-needed` antes de codar.

---

## Fluxo de PR

### 1. Fork + branch

```bash
git clone https://github.com/<seu-user>/xp-icm-workflow
cd xp-icm-workflow
git checkout main
git pull origin main
git checkout -b feat/<slug-curto>      # ou fix/<slug>, docs/<slug>, test/<slug>
```

Slug em kebab-case, ≤ 30 chars (ex: `feat/runtime-cleanup-docker`).

### 2. TDD obrigatório

Toda mudança em `scripts/` requer teste em `tests/unit/`. Pattern:

1. Escreva o teste primeiro (red).
2. Implemente até passar (green).
3. Refator se necessário (sem quebrar testes).

Tests usam pytest + Hypothesis (property-based em `tests/unit/test_*.py`). Bats em `tests/integration/` e `tests/e2e/` — CI-only, não roda em Win local.

### 3. Drift gate

Toda PR que toca **`references/`, `templates/`, `scripts/`, `SKILL.md`, `CLAUDE.md`, `README.md`** DEVE passar:

```bash
pytest tests/unit/test_no_drift.py -v
```

13 detectores ativos:

- Versão consistente em 4 arquivos canônicos (SKILL.md, README.md, design-system.md, preview-loop-protocol.md)
- Changelog tem entry pra versão atual
- Profile count consistente (canonical = `len(CANONICAL_PROFILES)`)
- Status enum sync (validate_state.py ↔ state-machine-schema.md)
- Cross-refs markdown resolvem em `references/`
- Templates `.sh` sem CRLF (Windows line ending quebra exec)
- Plan.md schema sync (parser regex ↔ template doc)

**Se test falha:**

- NÃO mergear até fix.
- Adicionar entrada no whitelist (`VERSION_WHITELIST`, `PROFILE_COUNT_WHITELIST`) APENAS se a divergência é legítima (changelog histórico, fixture legacy explícita).
- Caso contrário: fix o drift.

### 4. Bump de versão (se aplicável)

Mudanças que mudam comportamento da skill exigem bump em `scripts/bootstrap.py:SKILL_VERSION`. Toda mudança de versão requer sweep sincronizado em **5 arquivos**:

| # | Arquivo | O que atualizar |
|---|---|---|
| 1 | `scripts/bootstrap.py` | `SKILL_VERSION = "X.Y.Z"` |
| 2 | `SKILL.md` | header `# xp-icm-workflow vX.Y.Z` |
| 3 | `README.md` | badge `version-vX.Y.Z` + nova seção `## vX.Y.Z — <título>` |
| 4 | `references/design-system.md` | `format (vX.Y.Z)` + linha `> **Versão:** vX.Y.Z` |
| 5 | `references/preview-loop-protocol.md` | `build-iterate visual (vX.Y.Z)` + linha `> **Versão:** vX.Y.Z` |
| 6 | `references/changelog.md` | nova entry `## vX.Y.Z — <título> (YYYY-MM-DD)` no top com `### Mudanças` listando alterações concretas |

`pytest tests/unit/test_no_drift.py::test_version_consistency_canonical_files` valida 1-5. `test_changelog_has_entry_for_canonical_version` valida 6. Falha = merge bloqueado.

### 5. Conventional Commits

Subject ≤ 70 chars. Tipos aceitos:

- `feat:` nova funcionalidade
- `fix:` correção de bug
- `docs:` apenas documentação
- `test:` apenas testes
- `refactor:` refator sem mudança funcional
- `chore:` build, deps, ferramentas
- `perf:` performance

Body opcional explicando "porquê" (não "o quê" — diff já mostra).

Exemplo:

```
feat(runtime-registry): tracking de side-effects por workspace

Substitui PID file ad-hoc da v3.6.0 por JSON estruturado em
workspaces/<NNN>/_state/runtime-registry.json (gitignored).
Cross-platform PID liveness via os.kill (POSIX) / ctypes
OpenProcess (Windows).

Tests: 13 cobrindo CRUD, validação, purge, legacy, CLI.
```

### 6. Suite local antes de push

```bash
bash tests/run.sh --no-bats
```

Deve passar 782+ tests sem falha. Se passar local mas quebra em CI, é provável CRLF (Windows) — `git config --global core.autocrlf input`.

### 7. Abrir PR

PR contra `main` com descrição:

- **Motivação:** por que essa mudança? Issue relacionada?
- **Mudanças:** lista de arquivos tocados + comportamento novo.
- **Breaking changes:** se houver, sinalize claramente + migration path.
- **Tests:** quantos novos, o que cobrem.
- **Drift gate:** confirme que rodou `pytest tests/unit/test_no_drift.py`.

---

## Padrões de código

### Python

- **Type hints obrigatórios** em funções públicas (assinatura).
- **Docstrings** em funções públicas + classes (formato curto, 1-3 linhas).
- **Sem comentários óbvios** ("incrementa contador" no `i += 1`).
- **Imports** ordenados: stdlib → third-party → local.
- **PEP 8** + linha ≤ 100 chars (não-rígido pra strings).

### Markdown (templates + refs)

- **Português** pra prosa; identificadores de código, paths, comandos em **inglês**.
- **Headings:** `#` (h1) só no topo; `##` (h2) seções; `###` (h3) sub-seções; ≤ h4.
- **Code blocks** com language tag (` ```python`, ` ```bash`, ` ```yaml`).
- **Tables** pra dados tabulares (não bullets aninhados).
- **Cross-refs** markdown relativos: `[label](path/to/file.md)`. Drift detector valida.

### Templates `.tpl` (workspace bootstrap)

- Placeholders `{{NAME}}` em UPPER_SNAKE_CASE.
- Lista canônica em `bootstrap.py:_build_placeholders` — adicionar novo placeholder requer update do dict + tests `test_l2_templates.py::test_l2_template_no_unresolved_placeholders`.

### Shell `.sh` / `.bat`

- `.sh` POSIX strict (`set -euo pipefail`), shebang `#!/usr/bin/env bash`.
- LF line endings (CRLF quebra exec; drift detector valida).
- `.bat` apenas pra Windows-only helpers; cross-platform = Python.

---

## Bug reports

Issue template:

```markdown
**Versão da skill:** vX.Y.Z (cole de `bootstrap.py:SKILL_VERSION`)
**OS:** macOS 14.5 / Ubuntu 22.04 / Windows 10 Pro 19045
**Python:** 3.13.7

**Reprodução:**

1. Criei workspace via `/xp-icm-workflow profile=app_web_backend tier=development`
2. Cheguei na fase 04
3. Rodei `<comando>`
4. Recebi `<erro>`

**Esperado:** <comportamento esperado>
**Observado:** <comportamento real, com output relevante>

**Logs:**

- L1 frontmatter (`workspaces/NNN/CONTEXT.md` — primeiro bloco YAML):
  ```yaml
  ...
  ```
- _kickoff.md do stage onde quebrou (se relevante):
  ```
  ...
  ```

**Notas adicionais:** <qualquer contexto extra>
```

---

## Code of Conduct

Seja respeitoso. Critique código, não pessoas. PRs e issues que não seguem isso serão fechados.

---

## License

Contribuições serão licenciadas sob MIT (mesmo do projeto). Ao submeter PR você confirma que tem direito de licenciar o código sob MIT.
