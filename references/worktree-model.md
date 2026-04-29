# Worktree Model — Opção B (canônico v3.4.0)

> **Versão:** v3.4.0
> **Skill:** `xp-icm-workflow`
> **Substitui:** modelo cross-branch implícito da v3.3.x

## Problema (v3.3.x)

Workspace branch (`workspace/NNN-slug`) não tem `docs/`, `src/`, `tests/`
no working tree (esses paths vivem só em `base_branch`). Mas:

- L0 declara paths absolutos `<project_root>/docs/decisions/...` como
  fonte de verdade.
- L2 do estágio 02 lista `docs/decisions/` como Input.
- Read tool lê filesystem do working tree atual = workspace branch tree.
- Resultado: `Read docs/decisions/0001.md` em sessão de stage 02 retorna
  ENOENT mesmo se arquivo existe em main.

Workarounds frágeis:
- `git show main:docs/decisions/0001.md` via Bash (verbose, não-cacheable).
- `git checkout main -- docs/decisions/` (deixa untracked, conflito com
  pre-commit hook).
- Stash/checkout/commit/checkout/pop para criar ADRs em main mid-stage.

## Modelo canônico v3.4.0 — `.icm-main/` worktree paralelo

Bootstrap cria worktree linkada de `<BASE_BRANCH>` em
`<project_root>/.icm-main/`. Sempre presente, sempre checada na base
branch, sempre disponível para read **e** write cross-branch.

```
<project_root>/                       # worktree principal (workspace branch durante ciclo ICM)
├── .git/                             # repo (compartilhado entre worktrees)
├── .gitignore                        # contém .icm-main/
├── CLAUDE.md                         # workspace branch tree
├── workspaces/                       # workspace branch tree
│   ├── .index.md
│   └── 001-.../
└── .icm-main/                        # worktree linkada → base_branch (gitignored)
    ├── .git                          # arquivo (não dir) apontando pra repo
    ├── docs/
    │   ├── decisions/
    │   ├── lessons.md
    │   └── tech_debt.md
    ├── src/
    ├── tests/
    └── ...
```

Worktree é **filesystem real**: Read tool funciona; Edit/Write funciona;
git status/add/commit dentro de `.icm-main/` são commits em base_branch.

## Comandos canônicos

| Operação | Comando |
|---|---|
| Setup (bootstrap) | `git worktree add .icm-main <BASE_BRANCH>` |
| Listar worktrees | `git worktree list` |
| Atualizar `.icm-main` (pull main novo) | `cd .icm-main && git pull --ff-only` |
| Criar ADR | `Write .icm-main/docs/decisions/NNNN-slug.md` |
| Commitar ADR | `cd .icm-main && git add docs/decisions/NNNN-*.md && git commit -m "docs(decisions): ..."` |
| Ler ADR | `Read .icm-main/docs/decisions/NNNN-slug.md` |
| Ler código existente (stage 04+) | `Read .icm-main/src/...` |
| Remover (cleanup, raríssimo) | `git worktree remove .icm-main` |

## Regras de uso

### 1. Worktree é READ-ONLY conceitualmente do workspace branch

Sessões em workspace branch (estágios 00–08) operam no `<project_root>`
checkout (workspace branch). Para tocar em arquivos da base branch
(ADRs, lessons, tech_debt), agente DEVE usar `.icm-main/`:

- Editar `<project_root>/docs/decisions/...` direto **falha**: pre-commit
  hook rejeita workspace branch tocando paths fora de `workspaces/`.
- Editar `<project_root>/.icm-main/docs/decisions/...` **funciona**: é
  área da base branch, não do workspace.

### 2. Stage 02 design — ADRs canônicos via `.icm-main/`

Process step 6 do L2 stage 02 instrui:

```
Spawn ADR novo:
  1. Write .icm-main/docs/decisions/NNNN-<slug>.md (formato canônico)
  2. cd .icm-main
  3. git add docs/decisions/NNNN-*.md
  4. git commit -m "docs(decisions): <slug> (workspace <NNN>)"
  5. cd <project_root>
  6. plan.md cita filename (não inline)
```

Saída do passo 4 dá SHA do commit em base_branch. plan.md pode
referenciar `(commit <SHA>)` se útil.

### 3. Stage 04 implementation_waves — código via subagent worktrees

Lead permanece em workspace branch (no `<project_root>`). Subagentes via
Agent tool DEVEM usar `isolation: "worktree"` (parâmetro nativo do tool):

- Tool cria worktree efêmero `<project_root>/.icm-wave-001-N-<task>/`
  (ou similar) checkado em `wave-NNN-N/<task-slug>` derivada de
  base_branch.
- Subagente trabalha lá: read código existente em `.` (próprio worktree),
  read ADRs em `../.icm-main/docs/decisions/` (stage 04 brief inclui
  paths relativos — `agent-brief-render.py` resolve).
- Ao final do subagente, branch pushed; lead merge em base_branch via
  protocol da fase 04.

Tool com `isolation: worktree` cleanup automático se subagente não
modifica nada; branch + path retornados se modificou.

### 4. Read code de iteração anterior — stage 00 + 04+ casos

Stage 00 recon precisa scan ADRs vigentes + lessons + tech_debt vigente.
Worktree garante visibilidade:

- Stage 00 lê `.icm-main/docs/decisions/*.md` lista ADRs.
- Stage 04 subagente em wave branch lê seu próprio working tree (já tem
  `src/`, `docs/`).

### 5. CLAUDE.md root — exceção

`<project_root>/CLAUDE.md` é dashboard externo do estado, mantido por
`handoff.update_project_claude_md`. Vive no workspace branch durante
ciclo ICM ativo. Saída A do workspace migra para base_branch (ver
`session-handoff-protocol.md`).

Não vai em `.icm-main/CLAUDE.md` — esse arquivo nunca existe na base
branch enquanto workspace ativo.

### 6. Sincronização do `.icm-main/` quando wave merges

Após stage 07 mergiar wave branch em base_branch:

```
cd .icm-main
git pull --ff-only origin <BASE_BRANCH>   # ou git fetch + git merge --ff-only
```

Lead da fase 07 executa esse comando logo após o merge para que estágios
seguintes (08 ou outro workspace) vejam código atualizado em `.icm-main/`.

Recovery wizard valida fast-forwardability como check de saúde.

### 7. Multi-workspace coexistência

Se houver 2+ workspaces ativos no mesmo project_root (ex: `001-feat-a` +
`002-feat-b` em paralelo), `.icm-main/` é compartilhada entre os 2.
Cada workspace tem seu próprio working tree em `<project_root>` mas
trocar entre eles requer `git checkout workspace/<outro>` que força
mudança no `<project_root>` checkout — `.icm-main/` permanece intocada.

## Setup verificável (bootstrap)

`scripts/bootstrap.py` step `_setup_main_worktree(project_root, base_branch)`:

```python
def _setup_main_worktree(project_root: Path, base_branch: str) -> None:
    worktree_path = project_root / ".icm-main"
    if worktree_path.exists():
        return  # idempotente
    _run_git(
        ["worktree", "add", str(worktree_path), base_branch],
        cwd=project_root,
    )
```

Idempotente: roda 1× no bootstrap; chamadas subsequentes no-op.

`.gitignore` no project_root ganha entry `.icm-main/`. Aplicado em todas
branches via:

- main branch: gitignore versionado lista `.icm-main/`.
- workspace branch: mesma lista (workspaces herdam .gitignore via merge
  no bootstrap).

## Falhas comuns + recovery

### `.icm-main/` ausente

Sintoma: `Read .icm-main/docs/decisions/...` retorna ENOENT.

Causa: bootstrap antigo (pré-v3.4.0) ou worktree removida manualmente.

Recovery: `git worktree add .icm-main <BASE_BRANCH>`. Recovery wizard
detecta + sugere comando.

### Worktree corrupta (`.icm-main/.git` quebrado)

Sintoma: comandos git em `.icm-main/` falham.

Recovery: `git worktree repair` ou `git worktree remove .icm-main --force` +
recriar.

### Branch errada em `.icm-main/`

Sintoma: `cd .icm-main && git branch --show-current` retorna `wave-...`
em vez de `<BASE_BRANCH>`.

Causa: subagente checkou wrong branch dentro da worktree.

Recovery: `cd .icm-main && git checkout <BASE_BRANCH>`. Recovery wizard
detecta + sugere comando.

### Workspace branch tem `docs/`, `src/` orfãos

Sintoma: workspaces antigos (pré-v3.4.0) tinham `docs/lessons.md`,
`docs/tech_debt.md` no workspace branch tree.

Causa: bootstrap antigo criava esses paths no workspace branch.

Recovery: migration script (em `scripts/migrate-v3.3-to-v3.4.py` —
NotImplemented; documentar como manual) remove esses paths do workspace
branch e copia conteúdo pra base_branch (`.icm-main/`).

## Por que não outras opções

| Opção | Pro | Contra |
|---|---|---|
| **A** — só em main, agente lê via `git show main:` | sem disco extra; sem worktree | verbose; não cacheia bem; difícil pra Read tool; hooks SessionStart-side fragmentados |
| **B** — `.icm-main/` worktree paralelo (escolhida) | Read/Write/Bash funcionam direto; commits cross-branch trivialmente atomicos; multi-workspace sharing | duplica disco do projeto; bootstrap precisa criar |
| **C** — single-branch (workspace + código convivem) | sem cross-branch | perde isolamento; hooks de atomicidade difíceis; saída A vira squash merge gigante |
| **D** — copy-on-session via SessionStart hook | sem worktree visível | hook setup machine-specific; não atomicidade write-back; gitignore complexo |

Opção B vence por: (1) zero ambiguidade de path; (2) ferramentas
existentes (`Read`, `Edit`, `Write`, `Bash`) funcionam sem mudança;
(3) commits cross-branch via `cd .icm-main && git commit` são ZERO-FRAGE
(uma única transação por commit, não 2 commits + stash).

## Compatibilidade backward

Workspaces criados em v3.3.x sem `.icm-main/`:

1. Migration manual: `cd <project_root> && git worktree add .icm-main <BASE_BRANCH>`.
2. Adicionar `.icm-main/` ao `.gitignore` na workspace branch + commit (workspace branch).
3. Adicionar `.icm-main/` ao `.gitignore` na base_branch + commit (via worktree).
4. L0 do workspace antigo permanece com paths v3.3.x; agente em v3.4.0 entende ambos formatos via fallback documented em recovery-wizard.

## Referências cruzadas

- `templates/workspace/CLAUDE.md.tpl` — L0 template com paths `.icm-main/`.
- `templates/workspace/stages/02_design/CONTEXT.md.tpl` — process step 6 atualizado.
- `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` — subagent worktree usage.
- `templates/.git-hooks/pre-commit` — whitelist tightened (sem docs/decisions/lessons/tech_debt).
- `scripts/bootstrap.py` — `_setup_main_worktree` step.
- `scripts/recovery-wizard.py` — branch + worktree validation.
- `references/git-hooks.md` — pre-commit + commit-msg + opcional SessionStart.
- `references/changelog.md` — entry v3.4.0.
