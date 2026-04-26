# Git hooks — pre-commit (xp-icm-workflow)

Hook bash POSIX que enforca isolamento entre workspace ICM e src do projeto pai. Distribuido como template em `templates/.git-hooks/pre-commit`. Instalado por workspace (Wave 2 entrega `scripts/git-hook-installer.sh`).

## Proposito

Workspace ICM produz tudo dentro de `workspaces/NNN-slug/`. Edicao de codigo-fonte real do projeto (pasta `src/`, `tests/`, etc.) acontece em estagio 04 via subagentes de implementacao, em branches separadas. O hook impede:

1. Que branch de workspace acidentalmente edite `src/` (fora do escopo).
2. Que commit em workspace branch nao siga convencao de mensagem (rastreabilidade R2.3).
3. Que outputs de estagio sejam commitados sem atualizar `CONTEXT.md` raiz (atomicidade L1<->outputs).

Sem o hook, falhas silenciosas: workspace branches "vazariam" mudancas em src/, history de CONTEXT.md ficaria desincronizado de outputs, mensagens de commit nao identificariam o workspace.

## Regras (resumo executavel)

### R1 — Skip em rebase/merge

Se `.git/rebase-merge/` ou `.git/rebase-apply/` existe -> hook retorna `exit 0` imediatamente. Razao: durante rebase, o git mexe em commits historicos que ja passaram pelo hook; revalidar quebraria o rebase.

### R2 — Branch nao-workspace passa livre

Regex: `^workspace/[0-9]{3}-`. Se branch atual nao casa -> `exit 0`. Razao: hook so se aplica a workspace branches; trabalho normal em `main`, `feat/*`, etc. nao e afetado.

### R3 — Reject src edits

Em workspace branch, todo staged file deve estar em:

- `workspaces/NNN-slug/...` (escopo do workspace), OU
- `docs/decisions/*.md` (ADRs sao L3 globais e podem ser tocados em qualquer estagio).

Qualquer outro caminho (`src/`, `tests/`, raiz) -> reject com:

```
ERROR: branch workspace/NNN-slug pode tocar APENAS workspaces/NNN-slug/* ou docs/decisions/*.md.
File offendor: <path>
Pra editar src/, faca checkout em base_branch primeiro.
NUNCA use --no-verify; corrija o conteudo.
```

**Valido:**
- `workspaces/042-feat-auth/CONTEXT.md`
- `workspaces/042-feat-auth/stages/02/output/plan.md`
- `docs/decisions/0042-auth-strategy.md`

**Invalido:**
- `src/auth/middleware.py`
- `tests/test_auth.py`
- `README.md` (raiz)

### R4 — Prefixo de mensagem (R2.3)

Linha 1 da mensagem deve casar:

```
^workspace [0-9]{3}: 
```

Exemplo valido: `workspace 042: discovery completa`.

Exemplo invalido: `feat: add auth` -> reject com sugestao de reescrita.

### R5 — Excecao ADR (R5.4)

Se algum staged file casa `docs/decisions/*.md` E mensagem de commit contem a substring literal `(workspace NNN ` (parenteses + numero do workspace + espaco), aceita mesmo sem prefix de R4.

Razao: ADRs as vezes nasceram em outro contexto e estao sendo refinados em workspace; a marca `(workspace NNN ...)` no corpo basta para rastreabilidade.

**Valido:** `docs(adr): record decision (workspace 042 design)`

**Invalido:** `docs(adr): record decision` -> reject (nem prefix nem marker).

### R6 — Atomicidade L1<->outputs

Se algum staged file casa `workspaces/NNN-slug/stages/<NN>/output/...` E `workspaces/NNN-slug/CONTEXT.md` NAO esta staged -> reject com:

```
ERROR: outputs do estagio <NN> staged sem update de CONTEXT.md.
Atomicidade L1<->outputs requerida. Stage CONTEXT.md tambem.
```

Razao: cada output novo precisa ter rastro em `history` e `last_transition` do `CONTEXT.md` raiz. Se o commit tem so o output mas nao o estado, sessoes futuras nao retomam corretamente.

## Padroes regex exatos (R6.4)

| Regra | Regex / Glob |
|---|---|
| Branch workspace | `^workspace/[0-9]{3}-` |
| Workspace ID extraction | `${branch#workspace/}` -> split em primeiro `-` |
| Mensagem prefix | `^workspace [0-9]{3}: ` |
| ADR file glob | `docs/decisions/*.md` |
| ADR mensagem marker | substring literal `(workspace NNN ` |
| Stage output glob | `workspaces/<NNN-slug>/stages/<NN>/output/*` |
| Rebase markers | `.git/rebase-merge/` ou `.git/rebase-apply/` |

## Como instalar

Wave 2 entregara `scripts/git-hook-installer.sh` que:

1. Copia `templates/.git-hooks/pre-commit` para `.git/hooks/pre-commit` do projeto pai.
2. Faz `chmod +x`.
3. Idempotente — se ja instalado, sobrescreve apos confirmar via diff.

Ate la, instalacao manual:

```bash
cp <skill-root>/templates/.git-hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## Bypass via `--no-verify` e anti-pattern

`git commit --no-verify` pula o hook. **Nao use.** Razoes:

- Quebra atomicidade L1<->outputs -> sessoes futuras nao retomam.
- Permite vazar src edits para workspace branches -> historico bagunca.
- Mensagens sem prefix -> rastreabilidade perdida.

Se o hook esta rejeitando algo que voce acredita ser legitimo:

1. Leia a mensagem de erro completa — sugere correcao especifica.
2. Se acredita que e bug do hook, abra issue no repositorio da skill em vez de bypassar.
3. ADR + commits cross-cutting tem excecao R5 documentada acima.

## Excecoes documentadas

| Cenario | Comportamento |
|---|---|
| Branches que nao casam `^workspace/NNN-` | Hook nao faz nada |
| Rebase em progresso | Hook nao faz nada |
| ADR (`docs/decisions/*.md`) | Liberado em qualquer workspace branch |
| ADR + msg com `(workspace NNN ` | Aceita sem prefix R4 |

## Testes

- `tests/integration/test_git_hooks.bats` — integration tests via bats. CI-only (Ubuntu runner). Cobertura:
  1. Branch nao-workspace passa
  2. Reject src edit
  3. Aceita workspace + msg correta + CONTEXT.md staged
  4. Reject msg sem prefix
  5. Aceita ADR sem prefix com `(workspace NNN `
  6. Reject outputs sem CONTEXT.md
  7. Skip durante rebase-merge
  8. Skip durante rebase-apply

Bats nao roda em Windows local; testes serao executados no CI (GitHub Actions Ubuntu) configurado em Wave 3.
