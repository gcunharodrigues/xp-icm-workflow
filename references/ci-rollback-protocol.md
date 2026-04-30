# CI Global Rollback Protocol — Stage 04 Post-Merge

> Doc canônico de rollback quando CI global falha após merge sequencial da wave (passo 10). Referenciado por `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl`.

## Quando dispara

Lead completou passo 9 (merge sequencial) com sucesso. Passo 10 roda CI completo (`bash tests/run.sh` ou pipeline equivalente do projeto). Resultado: vermelho. Estado: `BASE_BRANCH` tem todos merges da wave aplicados; CI quebrou.

## Estado pré-rollback

- `BASE_BRANCH` HEAD = último merge da wave (commit verde local mas CI global red).
- L1: `IN_PROGRESS`, sub_stage `04_wave_<N>_in_progress`.
- Cleanup (passo 11) AINDA não executado — worktrees + branches da wave intactos.

## Protocolo

### Fase 1: Diagnose (não pula)

1. Lead invoca `references/diagnose-protocol.md` (build feedback loop → reproduce → hypothesise → fix). Tempo cap: 30min lead-side.
2. Resultado diagnose:
   - **Causa identificada + fix < 50 linhas:** lead aplica fix em `BASE_BRANCH` direto (commit `workspace <NNN>: ci-fix wave <N> <hypothesis>`). Volta passo 10. Loop max 3 vezes.
   - **Causa em task específica + fix > 50 linhas OU múltiplas tasks afetadas:** vai pra Fase 2 (rollback).
   - **Causa não identificada após cap:** vai pra Fase 2 (rollback).

### Fase 2: Rollback

1. Lead captura `pre_wave_sha` de L1 history.
2. Lead atualiza L1:
   - `status: BLOCKED_ERROR`
   - `error_type: ci_global_red`
   - `history` append: `{event: "ci_global_red", wave: <N>, diagnose_attempts: <N>, rolling_back: true}`
3. Lead executa `git reset --hard <pre_wave_sha>` em `BASE_BRANCH`. Mudança destrutiva — wave inteira revertida.
4. Lead PRESERVA wave branches (não deleta). Worktrees efêmeras: cleanup normal (sem `--force` se Auto-QA passou; ver decision matrix passo 11).
5. Lead escreve `output/wave-<N>/ci-rollback.md`:
   - SHAs antes/depois.
   - Diagnose attempts log.
   - Sintomas CI (logs).
   - Tasks da wave (todas afetadas).
6. Lead commit atômico:
   ```
   workspace <NNN>: ci rollback wave <N> — diagnose inconclusive
   ```
7. Lead imprime prompt de gate humano. AGUARDA.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 BLOCKED_ERROR — CI global red post-merge wave <N>

Diagnose: <causa-identificada-ou-inconclusive>
Diagnose attempts: <N>/3

BASE_BRANCH revertida pra <pre_wave_sha> (wave merges destruídos).
Wave branches PRESERVADAS para investigação:
  - wave-<NNN>-<N>/<slug-1>
  - wave-<NNN>-<N>/<slug-2>
  ...

Próximas opções:
  A) Refazer wave: responda "redo wave" → lead re-spawna subagentes
     com lições aprendidas no canal 2. Wave branches existentes
     deletadas; novas criadas.
  B) Refazer task específica: responda "redo task <slug>" → lead
     re-spawna só essa task; outras mantêm branches originais
     (re-merge sequencial após).
  C) Abandonar wave: responda "abandon" → marca workspace
     BLOCKED_ERROR permanente; humano decide stage 05+.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Fase 3: Resposta humana

#### "redo wave"

1. Lead deleta wave branches existentes: `git branch -D wave-<NNN>-<N>/<slug>` (force pois não-merged após reset).
2. Lead injeta no canal 2 da próxima rodada: lessons da `ci-rollback.md` (sintomas + causa identificada se houver).
3. Lead atualiza L1: `status: IN_PROGRESS`, history append `{event: "wave_redo", wave: <N>}`.
4. Volta ao passo 2 do Process (criar branches + spawn subagentes).

#### "redo task <slug>"

1. Lead identifica task pelo slug.
2. Lead deleta SÓ essa branch: `git branch -D wave-<NNN>-<N>/<slug>`. Outras wave branches permanecem.
3. Lead atualiza L1: `status: IN_PROGRESS`, history append `{event: "task_redo", task: <slug>}`.
4. Lead spawna SÓ um Agent pra essa task. Quando retorna COMPLETE, vai pro passo 9 — re-merge SEQUENCIAL de TODAS wave branches (incluindo as preservadas).
5. Volta passo 10 (CI gate global).

#### "abandon"

1. Lead atualiza L1: `status: BLOCKED_ERROR`, `error_type: wave_abandoned`. Sub_stage permanece `04_wave_<N>_in_progress`.
2. Wave branches permanecem (preserva evidência).
3. Lead commit atômico + SAIR.

## Invariantes

- **Reset --hard só com SHA explícito de `pre_wave_sha`.** Capturado em L1 history no início da wave (passo 1 do Process precisa gravar).
- **Wave branches preservadas durante BLOCKED_ERROR ci_global_red.** Cleanup só após resolução (redo wave / redo task / abandon).
- **Diagnose protocol é mandatório antes de rollback.** Não pular pra rollback direto — gasto barato vs custo de re-implementação.
- **L1 history rastreia todas tentativas:** `wave_started`, `ci_global_red`, `wave_redo`, etc.

## Dependência

Passo 1 do Process precisa gravar `pre_wave_sha: <BASE_BRANCH HEAD sha>` em L1 history evento `wave_started`. Sem isso, rollback é cego. Verificar/adicionar em template do passo 1 se ausente.
