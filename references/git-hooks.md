# Git hooks — pre-commit + commit-msg (xp-icm-workflow)

Dois hooks bash POSIX que enforcam isolamento entre workspace ICM e src do projeto pai. Distribuidos como templates em `templates/.git-hooks/{pre-commit,commit-msg}`. Instalados em conjunto pelo `scripts/git-hook-installer.sh` (Wave 2) ou pelo `bootstrap.py` (`_install_hooks`).

## Por que 2 hooks (split canonico)

Stages do git separam responsabilidades por timing:

| Stage | Quando roda | O que ve | O que valida (skill) |
|---|---|---|---|
| `pre-commit` | ANTES de `COMMIT_EDITMSG` ser persistido | Staged files apenas | File checks + atomicidade L1<->outputs |
| `commit-msg` | DEPOIS user fornecer msg, recebe path em `$1` | Msg atual no arquivo | Prefix da mensagem |

**Bug v1 (fixado):** versao inicial concentrava tudo em `pre-commit`, incluindo leitura de `.git/COMMIT_EDITMSG` para validar prefix. Mas `pre-commit` roda ANTES de git escrever a msg atual no arquivo — entao validava msg do commit ANTERIOR (ou empty no primeiro). Workaround temporario foi instalar hook depois dos commits do bootstrap, mas isso so protegia o bootstrap; commits futuros do user permaneciam validando msg stale. Fix: split em 2 stages canonicos.

**Anti-pattern:** NUNCA leia `COMMIT_EDITMSG` em `pre-commit`. Se precisa validar msg, use `commit-msg` que recebe path em `$1`.

## Pre-commit — file checks

### R1 — Skip em rebase/merge

Se `.git/rebase-merge/` ou `.git/rebase-apply/` existe -> `exit 0`. Razao: durante rebase, git mexe em commits historicos que ja passaram pelo hook; revalidar quebra rebase automatico do lead na fase 04.

### R2 — Branch nao-workspace passa livre

Regex: `^workspace/[0-9]{3}-`. Se branch atual nao casa -> `exit 0`. Trabalho em `main`, `feat/*`, `wave-NNN-N/*` nao e afetado.

### R3 — Reject src edits

Em workspace branch, todo staged file deve estar em:

- `workspaces/NNN-slug/...` (escopo do workspace), OU
- `docs/decisions/*.md` (ADRs sao L3 globais), OU
- `docs/lessons.md` (lições herdadas, stage 08 saída A), OU
- `docs/tech_debt.md` (débito técnico, stage 06 append P2/P3), OU
- `workspaces/.index.md` (registry de workspaces ativos/completados), OU
- `.gitignore` (atualizações de ignore pelo bootstrap).

Outros caminhos (`src/`, `tests/`, raiz) -> reject:

```
ERROR: branch workspace/NNN-slug pode tocar APENAS workspaces/NNN-slug/* ou arquivos whitelisted.
File offendor: <path>
```

**Valido:** `workspaces/042-feat-auth/CONTEXT.md`, `workspaces/042-feat-auth/stages/02/output/plan.md`, `docs/decisions/0042-auth-strategy.md`

**Invalido:** `src/auth/middleware.py`, `tests/test_auth.py`, `README.md` (raiz)

### R4 — Atomicidade L1<->outputs

Se algum staged file casa `workspaces/NNN-slug/stages/<NN>/output/...` E `workspaces/NNN-slug/CONTEXT.md` NAO esta staged -> reject:

```
ERROR: outputs do estagio <NN> staged sem update de CONTEXT.md.
Atomicidade L1<->outputs requerida.
```

Razao: cada output novo precisa rastro em `history` e `last_transition` do CONTEXT.md raiz. Output sem state = sessoes futuras nao retomam corretamente.

## Commit-msg — msg validation

### R5 — Skip nos casos triviais

- `$1` ausente ou arquivo inexistente -> `exit 0`.
- Branch nao-workspace -> `exit 0`.
- Rebase/merge em andamento -> `exit 0`.

### R6 — Prefixo de mensagem (R2.3)

Linha 1 da mensagem (ignorando linhas `#` de comentario do git) deve casar:

```
^workspace [0-9]{3}: 
```

Exemplo valido: `workspace 042: discovery completa`.

Exemplo invalido: `feat: add auth` -> reject com sugestao de reescrita.

### R7 — Excecao ADR (R5.4)

Se algum staged file casa `docs/decisions/*.md` E mensagem contem substring literal `(workspace NNN ` (parenteses + numero + espaco), aceita mesmo sem prefix R6.

Razao: ADRs as vezes nasceram em outro contexto e sao refinados em workspace; o marker `(workspace NNN ...)` no corpo basta para rastreabilidade.

**Valido:** `docs(adr): record decision (workspace 042 design)`

**Invalido:** `docs(adr): record decision` (nem prefix nem marker).

### R7.5 — Prefixos intake/feedback para stage 08 (R5.5)

Mensagens de commit no stage 08 podem usar prefixos `intake:` ou `feedback:` como alternativa ao prefix `workspace NNN:`. Estes prefixos sao especificos da fase de feedback intake onde o workspace ja esta em fase terminal e o contexto e diferente de stages anteriores.

**Valido:** `intake: stage 08 feedback coletado`, `feedback: close workspace`

**Invalido:** `intake:` sem mensagem (vazio apos dois-pontos).

## Padroes regex exatos (R6.4)

| Regra | Regex / Glob | Hook |
|---|---|---|
| Branch workspace | `^workspace/[0-9]{3}-` | ambos |
| Workspace ID extraction | `${branch#workspace/}` split em primeiro `-` | ambos |
| Mensagem prefix | `^workspace [0-9]{3}: ` | commit-msg |
| Intake/feedback prefix (stage 08) | `^(intake\|feedback): ` | commit-msg |
| ADR file glob | `docs/decisions/*.md` | ambos |
| Lessons file | `docs/lessons.md` | pre-commit |
| Tech debt file | `docs/tech_debt.md` | pre-commit |
| ADR mensagem marker | substring literal `(workspace NNN ` | commit-msg |
| Stage output glob | `workspaces/<NNN-slug>/stages/<NN>/output/*` | pre-commit |
| Workspace index | `workspaces/.index.md` | pre-commit |
| Gitignore | `.gitignore` | pre-commit |
| Rebase markers | `.git/rebase-merge/` ou `.git/rebase-apply/` | ambos |
| Wave branch detect | `^wave-[0-9]+-[0-9]+/` | commit-msg |
| Conventional Commit types | `^(feat\|fix\|refactor\|test\|docs\|chore\|perf\|ci\|build\|style\|revert)(\(.+\))?: .+` | commit-msg (R8 warning) |
| Comment lines (msg) | `^#` | commit-msg (strip antes parse) |

## Como instalar

`scripts/git-hook-installer.sh <project_root>` instala AMBOS hooks idempotentemente:

```bash
bash scripts/git-hook-installer.sh /caminho/do/projeto
```

Comportamento por hook:
- Ausente: copia template, `chmod +x`.
- Presente + igual: no-op.
- Presente + diff: backup `.bak.<UTC-ts>`, overwrite, `chmod +x`.

`bootstrap.py::_install_hooks(project_root, skill_root)` faz o mesmo via Python (chamado pelo `bootstrap.sh`/`bootstrap.py` ao final do bootstrap).

Manual:

```bash
cp <skill-root>/templates/.git-hooks/pre-commit .git/hooks/pre-commit
cp <skill-root>/templates/.git-hooks/commit-msg .git/hooks/commit-msg
chmod +x .git/hooks/pre-commit .git/hooks/commit-msg
```

## Wave branches (`wave-NNN-N/<task-slug>`)

### R8 — Wave branch Conventional Commit warning

Wave branches recebem **warning** (não bloqueio) via commit-msg hook R8 se a mensagem não segue Conventional Commits:

```
WARNING: wave branch detectada sem Conventional Commit.
Recomendação: use formato "<type>: <descrição>" (feat, fix, test, etc).
```

Regex: `^(feat|fix|refactor|test|docs|chore|perf|ci|build|style|revert)(\(.+\))?: .+`

Commits em wave branches usam **Conventional Commits padrão** sem prefix ICM:

- Formato: `<type>: <descrição>`
- Types: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`, `perf:`, `ci:`
- Exemplos: `feat: add JWT validation`, `test: unit tests for auth middleware`

Hooks ICM passam livremente em wave branches (R2/R5: branch não casa padrão workspace = exit 0). Isso é intencional — wave branches são escopo de código, não de state files. CI gate (lint, type-check, testes) substitui enforcement de hook.

**Anti-pattern:** NÃO comitar state files (CONTEXT.md, _kickoff.md) em wave branches. State files pertencem à workspace branch.

## Bypass via `--no-verify` e anti-pattern

`git commit --no-verify` pula AMBOS hooks. **Nao use.** Razoes:

- Quebra atomicidade L1<->outputs -> sessoes futuras nao retomam.
- Permite vazar src edits para workspace branches -> historico bagunca.
- Mensagens sem prefix -> rastreabilidade perdida.

Se hook rejeita algo que voce acredita ser legitimo:

1. Leia a mensagem de erro completa — sugere correcao especifica.
2. Se acredita que e bug do hook, abra issue em vez de bypass.
3. ADRs + commits cross-cutting tem excecao R7 documentada acima.

## Excecoes documentadas

| Cenario | Comportamento |
|---|---|
| Branches que nao casam `^workspace/NNN-` | Ambos hooks no-op |
| Rebase em progresso | Ambos hooks no-op |
| ADR (`docs/decisions/*.md`) | Liberado em workspace branch (pre-commit R3) |
| ADR + msg com `(workspace NNN ` | Aceita sem prefix R6 (commit-msg R7) |
| `commit-msg` chamado sem `$1` | exit 0 (deixa git tratar) |

## Testes

- `tests/integration/test_git_hooks.bats` — pre-commit (file checks). Cobre R1-R4.
- `tests/integration/test_commit_msg_hook.bats` — commit-msg (msg validation). Cobre R5-R7 + regression do bug v1 (msg ATUAL via `$1`, nao stale do anterior).

CI-only via Ubuntu runner; bats nao roda em Windows local. Wave 6 configura GitHub Actions com badge.

## Changelog

| Versao | Mudanca |
|---|---|
| v1 (Wave 2 inicial) | Hook unico `pre-commit` com file checks + msg validation. **Bug:** msg validation usava `.git/COMMIT_EDITMSG` que pre-commit le stale (msg do commit anterior). Workaround temporario: instalar hook depois dos commits do bootstrap. |
| v2 (Wave 2 fix) | Split em `pre-commit` (file checks) + `commit-msg` (msg validation). `commit-msg` recebe path em `$1` com msg atual, validacao correta. Regression test em `test_commit_msg_hook.bats`. |
