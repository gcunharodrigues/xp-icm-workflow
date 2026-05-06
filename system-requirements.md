# System requirements — xp-icm-workflow

Runtime and setup needed to run the skill and its test suite.

## Required runtime

- **Python 3.11+** (tested on 3.13)
- **POSIX bash** — Linux/macOS native; Windows via Git for Windows / Git Bash
- **git 2.30+**
- **jq** — JSON processing in `context-check.sh` hook (context threshold detection)
- **bats** — CI-only (installed via `apt`); optional in local environment

## Local setup

```bash
pip install -r requirements.txt
```

To validate the environment before running the skill:

```bash
bash scripts/check-runtime.sh
```

## Permissions allowlist (R6.1)

To reduce permission prompts during skill execution, add to
`~/.claude/settings.json` (or `settings.local.json` in project scope):

```json
{
  "permissions": {
    "allow": [
      "Bash(git:*)",
      "Bash(python:*)",
      "Bash(pip:*)",
      "Bash(pytest:*)",
      "Bash(npm:*)",
      "Bash(pnpm:*)",
      "Bash(yarn:*)",
      "Bash(bun:*)",
      "Bash(ruff:*)",
      "Bash(tsc:*)",
      "Bash(npx:*)",
      "Read",
      "Edit",
      "Write",
      "Glob",
      "Grep",
      "WebFetch",
      "WebSearch",
      "Skill(*)"
    ]
  }
}
```

If bootstrap detects these permissions are missing, it prints the
recommended block in the session output — copy and paste into `settings.local.json`.

## Bats CI-only

`tests/run.sh` auto-detects bats: `bats: command not found` generates a warning
but the exit code is 0 (skip, not fail). Run with `--no-bats` for local:

```bash
bash tests/run.sh --no-bats
```

## `context-check.sh` hook

Claude Code `PostToolUse` hook that detects when session context
reaches >=70% and emits a mandatory handoff alert. Requires `jq` on PATH.
Installed by bootstrap at workspace creation time.

Does NOT block the session — the alert is informational. The ICM protocol
requires the agent to stop work and perform a handoff when the alert fires.

`jq` must be on PATH. The hook silently fails if `jq` is not available
(does not block the session, just does not emit alerts).

## macOS extra installs

```bash
brew install jq coreutils
```

## CI dependencies

```yaml
# GitHub Actions example (Ubuntu 22.04)
- name: Install deps
  run: |
    sudo apt-get update
    sudo apt-get install -y bats jq
    pip install -r requirements.txt
```

`bats` is detected at runtime: absence generates only a warning, never a failure.

## Pre-commit hooks

The skill installs git hooks in `<project>/.git/hooks/` on bootstrap:
- `pre-commit` — validates atomicity (L1 `outputs` ↔ declared `output_files`)
- `commit-msg` — enforces commit prefix `workspace NNN: ` on workspace branch

Both validated by `test_no_drift.py`.
