# Conflict Resolution Protocol — Stage 04 Mid-Wave

> Doc canônico de resolução de conflict de merge durante stage 04 (wave merge sequencial). Referenciado por `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` passo 9.

## Quando dispara

Lead executa `git merge --no-ff wave-<NNN>-<N>/<task-slug>` em passo 9 → comando retorna non-zero com `CONFLICT (content): Merge conflict in <file>`. Lead permanece em `BASE_BRANCH` com working tree em estado de merge incompleto.

## Estado pré-resolução

- `HEAD` em `BASE_BRANCH` com merge in-flight (`.git/MERGE_HEAD` presente).
- Working tree contém arquivos com markers `<<<<<<<`, `=======`, `>>>>>>>`.
- Branches restantes da wave (não-mergeadas ainda): aguardam.
- L1 ainda em `IN_PROGRESS`; lead vai transitar pra `BLOCKED_ERROR`.

## Protocolo

### Fase 1: Lead pausa + sinaliza

1. Lead NÃO tenta resolver autonomamente (decisão deliberada — código de merge é alto risco).
2. Lead atualiza L1:
   - `status: BLOCKED_ERROR`
   - `error_type: merge_conflict`
   - `last_transition.note: "merge conflict wave <N> task <slug-conflitada>"`
   - `history` append: `{event: "merge_conflict", wave: <N>, task: <slug>, conflicted_files: [...]}`
3. Lead escreve `output/wave-<N>/merge-conflict-<slug>.md` documentando:
   - Branch conflitada.
   - Lista de arquivos em conflict (`git diff --name-only --diff-filter=U`).
   - Diff dos hunks conflitados.
   - Tasks restantes da wave NÃO mergeadas ainda.
4. Lead commit atômico:
   ```
   workspace <NNN>: BLOCKED merge conflict wave <N>
   ```
   (commit inclui L1 + merge-conflict-<slug>.md; NÃO inclui mudanças do working tree em conflict.)
5. Lead imprime prompt de resolução pro humano. AGUARDA na mesma sessão.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 BLOCKED_ERROR — merge conflict wave <N>

Branch conflitada: wave-<NNN>-<N>/<task-slug>
Files:
  - <path/to/file1>
  - <path/to/file2>

Working tree em estado de merge in-flight (.git/MERGE_HEAD presente).
Tasks restantes da wave (NÃO mergeadas): <lista>

Opções:
  A) Resolver manualmente nos arquivos + `git add` + `git commit` →
     responda "resolvido" pra retomar passo 9 nas tasks restantes.
  B) Abortar este merge: `git merge --abort` →
     responda "abort task" pra marcar a task como BLOCKED_ERROR e
     pular ela; lead segue pras restantes.
  C) Abortar wave inteira: responda "abort wave" → lead reverte
     todos merges desta wave (`git reset --hard <pre-wave-sha>`),
     marca workspace BLOCKED_ERROR, sai.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Fase 2: Resposta humana

#### "resolvido"

1. Lead valida: `git status --porcelain` retorna vazio para arquivos conflitados; `.git/MERGE_HEAD` ainda presente OU já commitado.
2. Se MERGE_HEAD ainda presente: humano esqueceu de commitar — lead executa `git commit --no-edit` (mensagem default do merge).
3. Lead atualiza L1: `status: IN_PROGRESS`, history append `{event: "conflict_resolved", task: <slug>}`.
4. Lead retoma passo 9 nas tasks restantes da wave (ordem do plan).

#### "abort task"

1. Lead executa `git merge --abort`.
2. Marca `output/wave-<N>/task-<slug>-blocked.md` com `reason: merge_conflict_aborted`.
3. Atualiza L1: `status: IN_PROGRESS`, history append `{event: "task_aborted_conflict", task: <slug>}`.
4. Lead pula task atual, segue passo 9 nas restantes.
5. Wave-summary.md final lista task como BLOCKED_ERROR não-resolvida; humano decide stage 05+.

#### "abort wave"

1. Lead captura `pre_wave_sha` de L1 history (gravado no início da wave).
2. Lead executa `git merge --abort` + `git reset --hard <pre_wave_sha>` em `BASE_BRANCH`.
3. Atualiza L1: `status: BLOCKED_ERROR`, `error_type: wave_aborted`.
4. Lead escreve `output/wave-<N>/wave-aborted.md` com SHAs originais + tasks que estavam pendentes.
5. Lead commit atômico + SAIR. Próxima sessão: humano decide refazer wave ou pular.

### Fase 3: Cleanup pós-resolução

- Tasks resolvidas/abortadas: cleanup normal (passo 11).
- Tasks com merge conflict abortado: branch permanece (não deletada via `git branch -d` pois não-merged); humano pode investigar depois.
- Wave-summary.md (passo 12) registra: `conflicts: [{task: <slug>, resolution: <resolved|aborted>}]`.

## Invariantes

- **Lead jamais resolve conflict autonomamente.** Sempre humano decide.
- **Reset --hard só com SHA explícito de pre-wave** (gravado em L1 history). Nunca `reset --hard HEAD~N`.
- **Branch wave conflict não é deletada** automaticamente (preserva evidência).
- **L1 status reflete realidade:** `BLOCKED_ERROR` durante espera, `IN_PROGRESS` após resolved/aborted.
