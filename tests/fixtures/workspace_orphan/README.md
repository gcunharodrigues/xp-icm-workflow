# Fixture: workspace_orphan

Workspace orfa com inconsistencias L1 deliberadas. Usada por
`tests/e2e/recovery_orphan.bats` e `tests/unit/test_recovery_wizard.py`.

Cada teste copia a fixture pra `tmp_path` antes de modificar — nunca
mute esses arquivos no lugar.

## Inconsistencias ilustradas

| Code | Como ilustrada |
|---|---|
| `HASH_MISMATCH` | `profile_effective_hash` em CONTEXT.md = `00...00` (64 zeros), mas `_config/profile-effective.yaml` tem conteudo real -> sha256 != zeros |
| `MISSING_OUTPUT` | `history[1].note` referencia `stages/02_design/output/ghost.md` ausente. Apenas `decisions.md` existe no FS |
| `STALE_IN_PROGRESS` | `status=IN_PROGRESS`, `last_action_at=2026-04-20T10:00:00Z`. Se `now >= 2026-04-22T00:00:00Z` -> stale |
| `MISSING_COMMIT` | `last_transition.commit_sha=deadbeef...` nao existe em qualquer git history real |

## Inconsistencias NAO ilustradas pela fixture

- `BRANCH_MISSING` — exige repo git real. Testado programaticamente.

## Estrutura

```
workspace_orphan/
├── CONTEXT.md                                # L1 com 4 inconsistencias
├── README.md                                 # este arquivo
├── _config/
│   └── profile-effective.yaml                # conteudo real (hash != zeros)
└── stages/
    └── 02_design/
        └── output/
            └── decisions.md                  # output presente apesar de IN_PROGRESS
```
