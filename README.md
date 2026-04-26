# xp-icm-workflow

Skill de orquestração de projetos. v3.0.0-beta1.

[![tests](https://github.com/<user>/xp-icm-workflow/actions/workflows/test-skill.yml/badge.svg)](https://github.com/<user>/xp-icm-workflow/actions)

## O que faz

Bootstrap one-shot que cria estrutura ICM (L0/L1/L2/L3) num projeto. Filesystem governa o ciclo a partir daí.

## Setup

```bash
pip install -r requirements.txt
bash scripts/check-runtime.sh
bash tests/run.sh
```

## Uso

```bash
# Em qualquer projeto:
/xp-icm-workflow profile=app_web_backend tier=development
```

Detalhes em `references/`.

## Documentos

- `SKILL.md` — entrada da skill.
- `references/state-machine-schema.md` — schema L1.
- `references/git-hooks.md` — hooks instalados no workspace.
- `references/changelog.md` — versões.
- `system-requirements.md` — runtime + permissions.

## Tests

```bash
bash tests/run.sh       # pytest + bats (se disponível)
```

CI: GitHub Actions Ubuntu (Wave 6).

## Versão

v3.0.0-beta1 — reescrita completa. v2.4 preservada em `references/v2.4-snapshot/`.
