# System requirements — xp-icm-workflow

Runtime e setup necessários para rodar a skill e sua suite de testes.

## Runtime obrigatório

- **Python 3.11+** (testado em 3.13)
- **bash POSIX** — Linux/macOS nativo; Windows via Git for Windows / Git Bash
- **git 2.30+**
- **bats** — CI-only (instalado via `apt`); opcional em ambiente local

## Setup local

```bash
pip install -r requirements.txt
```

Para validar o ambiente antes de rodar a skill:

```bash
bash scripts/check-runtime.sh
```

## Permissions allowlist (R6.1)

Para reduzir prompts de permissão durante a execução da skill, adicione ao
`~/.claude/settings.json` (ou em `settings.local.json` no escopo do projeto):

```json
{
  "permissions": {
    "allow": [
      "Bash(python scripts/*)",
      "Bash(pytest *)",
      "Bash(git status *)",
      "Bash(git diff *)",
      "Bash(git log *)",
      "Bash(git branch *)",
      "Bash(git rev-parse *)",
      "Bash(git worktree *)",
      "Bash(git checkout *)",
      "Bash(git stash *)",
      "Bash(bash scripts/*)",
      "Bash(bash tests/run.sh)"
    ]
  }
}
```

Se o bootstrap detectar que essas permissions estão ausentes, ele imprime esse
snippet para o humano colar manualmente. A skill nunca edita `settings.json`
silenciosamente.

## Cross-platform notes (I2)

- **CI primary:** Ubuntu (GitHub Actions, Wave 6).
- **macOS:** smoke manual ocasional — comportamento idêntico ao Linux.
- **Windows:** Git Bash (vem com Git for Windows) executa scripts POSIX sem
  ajustes. Caminhos com backslash em fluxos de teste não são suportados — use
  forward slashes.

## Notas adicionais

- A skill roda **dentro** do Claude Code (Q1.1 / J1.1) — não há SDK Anthropic
  separado nas dependências.
- `bats` é detectado em runtime: ausência gera apenas warning, nunca falha.
- Override local de profile vai em `.icm-profile.local.yaml` (gitignored).
