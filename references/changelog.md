# Changelog — xp-icm-workflow

Histórico de versões da skill. A versão atual vive no frontmatter do `SKILL.md`.

---

## v3.10.0 — E2E coverage reinforcement (2026-05-04)

### Mudanças

- **NEW:** `references/e2e-coverage-protocol.md` — doc canônico do reforço E2E. 4 frentes: (1) wave-planner detecta user-facing paths e auto-emite annotation, (2) forensic+ Check 8 valida task com `Requires E2E update: true` tem ≥1 file em e2e/cypress/playwright, (3) L4 wave gate roda E2E suite universal tier dev/prod (independe profile), (4) Stage 05 audit suite freshness < 7 dias.
- **EXTENDED:** `scripts/forensic-plus.py` +Check 8 user-journey coverage (HARD dev/prod, SOFT exp/tool). Plan parser extrai `Requires E2E update` field + detect `**E2E:** skip - <rationale>` override. JSON schema bump `e2e_coverage_missing` (backward-compat).
- **EXTENDED:** `scripts/wave-planner-script.py` +`USER_FACING_PATHS_BY_PROFILE` constant (defaults 11 profiles) + helper `_task_requires_e2e()`. render_wave_plan inclui coluna `E2E required?` na task table + annotation `> **E2E coverage required**` quando ≥1 task flagged.
- **EXTENDED:** `scripts/recovery-wizard.py` +`CODE_E2E_SUITE_STALE` em CANONICAL_ORDER (alerta quando suite > 7 dias sem update + tasks user-facing entregues).
- **EXTENDED:** `scripts/migrate-workspace.py` +entry `migrate_3_9_0_to_3_10_0` (bump-only, backward-compat). SUPPORTED_VERSIONS += "3.10.0".
- **EXTENDED:** `references/forensic-plus-protocol.md` Check 8 spec + tier×severity matrix expandida 8 checks. v3.9.0 → v3.10.0.
- **EXTENDED:** `references/4-block-contract-template.md` schema +`### Requires E2E update` field opcional (auto-emit por wave-planner; subagente DEVE adicionar e2e files; override `**E2E:** skip - <rationale>`).
- **EXTENDED:** `references/state-machine-schema.md` error_types adicionais: `e2e_suite_failed`, `e2e_suite_missing`, `e2e_suite_stale`, `e2e_skip_unjustified`.
- **EXTENDED:** `templates/.../04_implementation_waves/CONTEXT.md.tpl` step 11 expandido em 11a/11b/11c (CI universal / E2E suite tier dev/prod / cross-task coherence). Inputs +e2e-coverage-protocol.md.
- **EXTENDED:** `templates/.../05_verification/CONTEXT.md.tpl` step 4.7 NEW (audit E2E suite existe + freshness + skip rationale). BLOCKED_ERROR causa list +e2e_suite_*. Inputs +e2e-coverage-protocol.md.
- **BUMP:** SKILL_VERSION 3.9.0 → 3.10.0 (`scripts/bootstrap.py`); 5 canonical files synced (SKILL.md, README.md badge + section, design-system.md, preview-loop-protocol.md, bootstrap.py runtime_refs +e2e-coverage-protocol.md).

### Notas

E2E coverage gap docs em ICM v3.9.0: tracer-first cobre task isolada (não regressão); wave gate L4 e2e profile-conditional (só frontend/fullstack); Stage 05 confiava em CI projeto sem audit. v3.10.0 fecha gaps via 4 frentes complementares — wave-planner advisory (annotation), forensic+ enforcement (Check 8 HARD), wave gate universal (step 11b), stage 05 audit (4.7).

Nível 3 (mutation testing oracle, preview-loop suite completa wave-end) deferido pra v3.11.0+.

---

## v3.9.0 — Layered dev↔QA loop + lead-resolution tier (2026-05-04)

### Mudanças

- **NEW:** `references/critic-protocol.md` — L3 LLM critic ortogonal canonical. Fresh context, anti-sycophancy hardcoded, triplet output (claim, evidence, counterexample, severity), decision APPROVE/REJECT/ABSTAIN. Critic model = `TIER_CEILING[tier]` sempre. Cobre gap semântico do forensic+ (lógica errada, ADR drift disfarçado, edge cases ausentes).
- **NEW:** `references/lead-resolution-protocol.md` — buckets B1 REWRITE_SPEC / B3 DIRECT_IMPL / B4 VOID_TASK. Trigger conditions T1 (cap 3 retries) / T2 (Jaccard ≥ 0.7 convergence trip) / T3 (catastrophic detector universal). Cap 1 attempt per bucket. Stage 05 audit trail.
- **NEW:** `references/mocking-guidelines.md` — mattpocock alignment. Mock só boundaries (HTTP/DB/time/randomness/env); nunca internals. Per-profile guidance + tier-aware enforcement via forensic+ Check 6.
- **NEW:** `scripts/lead-diagnose.py` — Jaccard cluster + catastrophic detector (tests broken outside scope, build globally broken, scope creep > 5×) + bucket recommendation + surgical brief render. Output diagnose.md schema.
- **NEW:** `scripts/pick-model.py` — heurística determinística. compute_score (estimated_lines, hot_paths, security_sensitive, public_api_change, algorithm_heavy, doc_only/config_only/css_only, tier) + tier ceiling cap. Writer/critic split.
- **NEW:** `templates/critic-prompt.md` — renderable prompt template para Agent tool (anti-sycophancy + triplet schema).
- **EXTENDED:** `scripts/forensic-plus.py` — +Checks 5/6/7 (acceptance↔test mapping, NÃO QUERO violations, ADR import drift). JSON schema bump backward-compat (campos novos opcionais).
- **EXTENDED:** `scripts/agent-brief-render.py` — `--tier` flag opcional integra `pick-model.py`; brief header ganha `model_recommended_writer/critic` + `complexity_score`.
- **EXTENDED:** `scripts/migrate-workspace.py` — entry `migrate_3_8_0_to_3_9_0` (bump-only, backward-compat). SUPPORTED_VERSIONS += "3.9.0".
- **EXTENDED:** `scripts/recovery-wizard.py` — tipo novo `LEAD_RESOLUTION_STALE` (workspace em LEAD_RESOLUTION_IN_PROGRESS sem progresso > 24h).
- **EXTENDED:** `scripts/validate_state.py:VALID_STATUSES` += `LEAD_RESOLUTION_IN_PROGRESS` (additive, schema mantido).
- **REWRITE:** `references/4-block-contract-template.md` — § 3 vertical TDD + tracer-first + anti-horizontal slicing seção dedicada. § 5 Akita 15-itens DELETED. § 6 exemplo `auth-middleware` atualizado sem Akita output. v3.0.0-beta5 → v3.9.0.
- **REWRITE:** `references/forensic-plus-protocol.md` — 7 checks (4 originais + 3 novos), tier×severity matriz consolidada. v3.8.0 → v3.9.0.
- **EXTENDED:** `references/state-machine-schema.md` — status `LEAD_RESOLUTION_IN_PROGRESS` (additive, 7º status canônico). error_types adicionais: `lead_resolution_audit_failed`, `lead_resolution_all_buckets_failed`, `lead_decision_missing`, `critic_unavailable`, `critic_abstain_loop`.
- **REWRITE:** `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` — flow novo (TDD vertical → L2 forensic+ → L3 critic always → diagnose → retry/lead-bucket). Drop refs Akita. Step 8 expanded em 8a-8e. Step 9 novo (lead-resolution). Inputs +4 docs (critic, lead-resolution, forensic-plus, mocking-guidelines).
- **EXTENDED:** `templates/workspace/stages/05_verification/CONTEXT.md.tpl` — sub-step 5.5 audit lead resolutions (B1 tighten / B3 critic concerns endereçados / B4 rationale concreto). FAIL → `BLOCKED_ERROR error_type: lead_resolution_audit_failed`.
- **DROP:** Akita 15-itens inline removed do task report subagente. QA delegado a layers ortogonais (L2 forensic+ extended + L3 critic). Self-grading bias documentado (Huang ICLR 2024, arxiv 2510.11822, arxiv 2509.16533).
- **BUMP:** SKILL_VERSION 3.8.0 → 3.9.0 (`scripts/bootstrap.py`); 5 canonical files synced (SKILL.md, README.md badge + section, design-system.md, preview-loop-protocol.md, bootstrap.py runtime_refs +3 docs novos).

### Notas

Self-grading drop é mudança de filosofia, não de capacidade. Forensic+ Checks 4/6/7 + critic L3 cobrem dimensões de qualidade que Akita pretendia auditar (clean code, secrets/PII, ADR compliance), com gate ortogonal imune a sycophancy. `akita-derive.py` post-hoc opcional pra telemetria — deferred até stage 08 reportar gap.

Cross-family critic (E2 abandonado) e mutation testing oracle (R2) seguem out-of-scope. Compensação via stage 06 review humano + stage 08 feedback intake.

---

## v3.8.0 — Forensic+ wave reviewer (2026-05-03)

### Mudanças

- **NEW:** `scripts/forensic-plus.py` — auditoria estrutural per task no step 8 wave-reviewer (4 checks git-only).
- **NEW:** `references/forensic-plus-protocol.md` — doc canônico.
- **NEW:** schema `task-<slug>.md` frontmatter ganha `forensic_violations`, `forensic_passed`, `forensic_max_severity`, `forensic_respawn_count` (opcionais, backward compat).
- **NEW:** `wave-summary.md` ganha seção `## Forensic+ summary`.
- **NEW:** `plan.md` task aceita `### Estimated lines` opcional (Check 3 scope creep).
- **CHANGE:** step 8 do pipeline 12-passos expandido em 8a/8b/8c/8d (`references/wave-execution-protocol.md` + L2 stage 04 template).
- **CHANGE:** flag wave-plan.md `skip_wave_reviewer` renomeado pra `skip_cross_task_audit`. Backward-compat alias mantido em v3.8.0; removido em v3.9.0.
- **CHANGE:** `state-machine-schema.md` documenta novos `error_type: forensic_max_retries|forensic_script_crash` (sem enum change).
- **DEPS:** sem novas dependências runtime. PyYAML já presente em `requirements.txt`.
- **TESTS:** +20 unit (`test_forensic_plus.py`), +6 snapshot fixtures, +4 drift detectors, +1 bats e2e.

### Migração

`migrate_3_7_2_to_3_8_0` é bump-only — workspaces existentes são compatíveis sem mutação destrutiva. Campos novos no task-md frontmatter têm parser default tolerante a ausência.

### Rationale

Self-grading do subagente (Auto-QA Akita 15-itens) sofre de bias documentado (Huang et al. ICLR 2024, Self-Correction Benchmark 2025). Forensic+ adiciona auditoria externa estrutural sem importar prompt-only re-grade caro. Aproveita strength único do ICM (forensic git-log audit) ampliando cobertura de 1 vetor (qa_loops_used vs commits) pra 4 vetores de fraude estrutural.

---

## v3.7.2 — Saída A/C último ativo: auto-/init + cleanup ICM opt-in (2026-05-01)

### Why v3.7.2

Sessão real ICM (workspace 002 spawn de 001 via saída C) revelou 4 gaps:

1. Sem instrução pra rodar `/init` ao fim do stage 8 — região idle citava
   "rode /init" mas não era ação executada na sessão.
2. `.index.md` ficava stale com workspace fechado listado como `active`.
   SessionStart hook lia índice e detectava 001 fechado como ativo.
3. `.claude/settings.local.json` acumulava entries de hooks por workspace
   (bootstrap append, saída A/C nunca removia).
4. `.icm-main/` worktree + workspace branch + subagent worktrees órfãs
   permaneciam pós-saída A/C, humano via raiz em workspace branch tree
   "duplicada" da `.icm-main/`.

### Mudanças

**Stage 08 saída A/C último workspace ativo:**

- **Auto-`/init` invocation** — `handoff.py remove-block --exit-2-if-last-active`
  retorna exit 2 quando deactivate disparou. Stage 08 template captura e
  invoca `Skill(skill: "init")` na MESMA sessão antes de SAIR. Saída B
  intocada. Multi-workspace com remanescentes ativos pula (proibido).
- **Cleanup ICM opt-in** — `scripts/icm-cleanup.py` novo: pre-checks
  (uncommitted abort, --force bypass), remove subagent worktrees órfãs,
  remove `.icm-main/` worktree, checkout main, deleta workspace branch,
  prune. Menu `[s/n/dry-run]` no template stage 08 invoca o script.
  Doc: `references/icm-cleanup-protocol.md`.
- **`.index.md` cleanup** — `handoff.py:_update_index_status` reescreve
  linha do workspace `active` → `COMPLETED`. Chamado em `remove_workspace_block`.
- **`settings.local.json` hooks unregister** — `handoff.py:_unregister_workspace_hooks`
  remove entries do workspace fechado. Preserva hooks não-ICM.
- **SessionStart hook prefere L1** — `icm-session-check.sh` agora itera
  `workspaces/*/CONTEXT.md` frontmatter status ao invés de `.index.md`.

**Recovery wizard:**

- Novo detector `STALE_ICM_MAIN_AFTER_CLOSE` (16ª na CANONICAL_ORDER):
  dispara quando workspace COMPLETED + `.icm-main/` presente + zero outros
  workspaces ativos. Plan A registra warning sugerindo `icm-cleanup.py`
  (destrutivo, não auto-executa). Helper `_count_active_workspaces`.

### Tests

41 tests novos: `test_handoff_remove_block_exit_code.py` (5),
`test_stage08_template_init_invocation.py` (8),
`test_close_cleanup_v3_7_1.py` (10), `test_icm_cleanup.py` (10),
`test_recovery_stale_icm_main.py` (8). Suite: 823 passed (era 782),
sem regressão.

### Doc

- `references/icm-cleanup-protocol.md` (novo) — D1-D5 decisions, algoritmo,
  edge cases, idempotência.
- `references/project-root-claude-md.md` — auto-`/init` trigger.
- `templates/workspace/stages/08_feedback_intake/CONTEXT.md.tpl` — saídas
  A/C steps reescritos.

### v3.7.1 (intermediária, mergeada em 3.7.2)

`.index.md` + settings.local.json hooks fixes implementados em commit
separado (`ed838ce`) mas versão pulada — agrupado em v3.7.2.

### Post-release drift fix (2026-05-01)

`scripts/migrate-workspace.py` ficou em `CURRENT_SKILL_VERSION = "3.7.0"`
após bump 3.7.0→3.7.2 do bootstrap — `test_no_drift.py` original cobria
só 4 arquivos canônicos (SKILL.md, README.md, design-system.md,
preview-loop-protocol.md), não scripts auxiliares.

Fixes:

- `scripts/migrate-workspace.py`: `CURRENT_SKILL_VERSION` 3.7.0 → 3.7.2,
  `SUPPORTED_VERSIONS` add `"3.7.2"`, novo `migrate_3_7_0_to_3_7_2`
  (bump-only — v3.7.1 colapsada em 3.7.2 sem schema change), dispatcher
  entry `"3.7.0->3.7.2"`, docstring + CLI example bumped.
- `tests/unit/test_migrate_workspace.py`: 6 tests novos cobrem step novo,
  cadeia full 3.3.0→canonical, sync com `bootstrap.SKILL_VERSION`.
- `tests/unit/test_no_drift.py`: detector H novo `test_scripts_skill_version_sync`
  varre `scripts/**/*.py` por `CURRENT_SKILL_VERSION` + última entry de
  `SUPPORTED_VERSIONS` tuple, valida == canonical. Whitelist only para
  `migrate-v3.3-to-v3.4.py` (target histórico fixo). `VERSION_MUST_MATCH`
  ganha entry cirúrgica pra `migrate-workspace.py`.
- `CLAUDE.md` raiz: regra "bump SKILL_VERSION" estendida pra incluir
  `scripts/migrate-workspace.py` na lista de arquivos sincronizados.

Suite: 831 passed (era 823), 0 regressão.

---

## v3.7.0 — Runtime cleanup + spawn-pending + handoff fixes (2026-05-01)

### Why v3.7.0

20 gaps identificados durante uso real do workspace 001-001-saas-psicologo-mvp
(transição saída C → 002). Categorias: side-effects órfãos (uvicorn, vite,
docker, background tasks), working tree consistency (.icm-main dirt,
gitignore incompleto, wave branch sweep, TD append durante intake),
skill bugs cosmetic (handoff.py "Saída A" hardcoded em ambos A/C, profile-matrix
version drift), UX/runbook (comando spawn longo, checklist runtime ausente,
mini-menu não-strict), edge cases (mid-flow crash recovery, lessons gap C/B,
restart B baseline dirty).

v3.7.0 fecha 10 mudanças concretas:

### Mudanças

**1. Drift detector hardened (`tests/unit/test_no_drift.py`):**
- `PROFILE_COUNT_PARENS_RE` pega "Profiles canônicos (N):" format.
- `PROFILE_COMBO_RE` valida "(N × T = M combos)" tripla consistência.
- SKILL.md L158/L162 sweep: 10→11 profiles, 40→44 combos, +fullstack.

**2. handoff.py outcome-aware idle render (`scripts/handoff.py`):**
- `_render_icm_idle(closed_at, *, outcome={A,C}, spawn_to=None)` — branch
  por outcome em vez de hardcoded "Saída A".
- `remove_workspace_block` + `deactivate_project_claude_md` propagam
  outcome+spawn_to via kwargs com defaults backward-compat.
- CLI `remove-block` + `deactivate-project-md` ganham `--outcome`+`--spawn-to`.
- Validação: outcome=C requer spawn_to; outcome ∉ {A,C} raise.

**3. Runtime registry novo (`scripts/runtime-registry.py`):**
- CRUD em `workspaces/<NNN>/_state/runtime-registry.json` (gitignored).
- Kinds: dev_server, background_task, docker_container, subagent_worktree.
- `_is_pid_alive` cross-platform (POSIX `os.kill`, Windows `ctypes`
  `OpenProcess`+`GetExitCodeProcess`).
- `purge_dead` remove entries com PID morto.
- `detect_legacy_pid_files`: identifica `.icm-main/.dev-server.pid` v3.6.0
  pra migração graceful.
- CLI: register, list, unregister, purge-dead, detect-legacy.

**4. Runtime status checklist (`scripts/runtime-status.py`):**
- 6 categorias: dev_servers, background_tasks, docker, wave_branches,
  working_tree, untracked.
- `check_all` agrega; CLI suporta `--check <category>`, `--format json|text`,
  `--exit-code` (gating).
- Falhas graceful: docker daemon down/git ausente → assumed clean.

**5. Migrate workspace orquestrador (`scripts/migrate-workspace.py`):**
- Floor v3.3.0 (beta1/beta2 unsupported).
- Encadeia v3.3 → v3.4 → v3.5 → v3.6 → v3.7.
- Trigger híbrido: COMPLETED/AWAITING auto-prompt; IN_PROGRESS warning-only.
- Backup automático em `<pr>/.icm-migration-backup/<ts>/<ws>/`.
- Idempotente. Step v3.6→v3.7 substantive: bump L0 + cria `_state/` +
  migra `.icm-main/.dev-server.pid` → registry (se PID alive).

**6. Bootstrap.py — spawn-pending + spawn-from + gitignore extend:**
- `detect_spawn_pending` parse + valida schema 9 campos.
- `resolve_spawn_source` consolida arquivo + CLI arg (sources: file, arg,
  conflict, none). Conflict marca file_value/arg_value pra menu humano.
- `consume_spawn_pending` unlink pós-bootstrap successful (idempotente).
- CLI `--spawn-from <slug>` (dest=spawn_from, fallback explícito).
- GITIGNORE_LINES extended: `.icm/spawn-pending.json`, `workspaces/*/_state/`,
  `**/coverage/`, `**/coverage.json`, `**/tsconfig.tsbuildinfo`, `**/.vite/`.

**7. Recovery wizard novo tipo `RUNTIME_REGISTRY_STALE` (v3.7.0):**
- 14º entry em CANONICAL_ORDER.
- Detecta entries com PID morto em registry; sugere `purge-dead` (humano
  confirma, sem auto-purga).
- `_pid_alive_for_registry` wrapper testável.

**8. Pre-commit hook block `_state/` paths:**
- Reject staged paths `workspaces/*/_state/*` (privacy: PID/port leak em
  PRs públicos). Mensagem orienta diretório local-only gitignored.

**9. L2 stage 08 substantive update:**
- `applicable_stop_points: ["runtime_cleanup_failed"]` (era `[]`).
- §"Runtime Cleanup Checklist" antes de §Process — 6 categorias, strict
  universal todos tiers, comando `runtime-status.py` documented.
- Process step 0 obrigatório (rodar checklist).
- Saída A step 3: TD append durante intake (opcional, só se feedback cita
  débito explícito) + step 6: handoff.py remove-block --outcome A.
- Saída C step 3: render `.icm/spawn-pending.json` schema completo
  (spawn_from, intake_report_*, agent_brief structured 4 campos +
  notes_livre, proposed_*, intake_commit_sha, created_at) + step 5:
  remove-block --outcome C --spawn-to.

**10. L2 stage 04 entry/exit hook → registry calls:**
- Entry: `runtime-registry.py list --kind dev_server`, register na start.
- Exit: list + kill processo + unregister entries.
- Legacy v3.6.0 PID file path documented com migration via
  `migrate-workspace.py`.

### Refs novas

- `references/runtime-cleanup-protocol.md` (~150 LOC) — protocolo canônico
  6 categorias × cleanup default × override humano + per-OS quirks +
  recovery se cleanup falha mid-saída.
- `references/spawn-handoff-protocol.md` — schema spawn-pending.json +
  cross-branch read pattern via git show + bootstrap detection flow +
  edge cases (clone, colisão slug, multi-pendentes).

### Refs atualizadas

- `references/feedback-intake-fase08.md` — §"Runtime cleanup obrigatório
  pré-saída (v3.7+)" com 9 steps explícitos.
- `references/stop-points-canonical.md` — 14 → 15 itens, #15
  `runtime_cleanup_failed` (sinais, trade-offs, calibração strict
  universal, menu A/B/C específico).

### Templates

- `workspace/CLAUDE.md.tpl` R10 nova: runtime side-effects são
  responsabilidade humana. Skill detecta + imprime checklist + aguarda
  confirmação per categoria. Nunca mata processo automaticamente.
- `_config/stop-points.md` 12 → 13 itens; #13 `runtime_cleanup_failed`
  com menu A/B/C específico.

### Backward compat

- Workspaces v3.6.0 in-flight: rodar `migrate-workspace.py --workspace-root <ws>`
  pra migrar PID file → registry. Idempotente.
- Workspaces v3.3 → v3.6: encadeia migrations no orquestrador.
- Workspaces beta1/beta2 (pre-v3.3.0): unsupported. Migration manual.

### Decisões consolidadas (12)

| # | Tópico | Resolução |
|---|---|---|
| 1 | TD append fase 08 | (b) flexibilizar — saída A/B append opcional |
| 2 | Cross-platform tooling | (b) Python puro `runtime-status.py`. Drop Makefile |
| 3 | Drift profile count | (c) sweep + endurecer detector |
| 4 | Tier override checklist | (a) strict universal |
| 5 | Spawn handoff | (c) `.icm/spawn-pending.json` + `--spawn-from` arg fallback |
| 6 | Registry path + migração | (c×y) `_state/` workspace-scoped + migrate dev-server graceful |
| 7 | Pre-commit `_state/` | (a) block staged paths |
| 8 | Migration trigger | (d) híbrido COMPLETED auto-prompt; IN_PROGRESS warning |
| 9 | Migration floor | (b) v3.3.0 |
| 10 | Cleanup failure | (b) stop point #13 (#15 em references/) |
| 11 | agent_brief schema | (c+d) estruturado 4 blocos + git show cross-branch |
| 12 | Stage 04 entry hook | (c) helper docs + custom dev server fallback |

### Tests

49 tests novos (handoff outcome 7, runtime-registry 13, bootstrap spawn-pending
14, recovery RUNTIME_REGISTRY_STALE 4, runtime-status 8, migrate-workspace 15).
Total: 781 → 781+ tests verde, zero regressão.

---

## v3.6.0 — Preview loop (build-iterate visual) (2026-04-30)

### Why v3.6.0

Frontend ICM até v3.5.0 cobria DESIGN.md tokens (Google Stitch) mas
faltava ciclo build-iterate visual. Humano pedia "mostra como vai
ficar" e ICM não tinha resposta integrada além de "spawn subagente
implementa". Sem hot-reload coordenado, sem feedback loop visual,
sem mock data automático, sem CDP integration.

v3.6.0 fecha a lacuna: profile `app_web_frontend` + `fullstack`
ganham preview loop opt-in-by-default que orquestra dev server,
mock data tier-based, Chrome CDP live, preview pages, verificação
uniforme, feedback combo livre, design system cascade, e replay
multi-tela. Doc canônico: `references/preview-loop-protocol.md`.

### Mudanças

**1. Doc canônico novo (`references/preview-loop-protocol.md`):**
- 10 decisões consolidadas (dev server lifecycle, mock data
  tier-based, feedback combo, CDP live, verificação uniforme,
  preview pages, screenshot livre, sem cap iter, design cascade
  threshold 5, multi-tela sob pedido).
- Cobre stack canônico, comandos por package manager, helper
  scripts, scope de leitura CDP, fallback gracioso.
- Anti-patterns + recovery wizard tipos novos documentados.

**2. Helper scripts CDP (`templates/.claude/scripts/`):**
- `launch-chrome-cdp.bat` (Windows): lança Chrome com
  `--remote-debugging-port=9222 --user-data-dir=.icm-chrome-profile`.
- `launch-chrome-cdp.sh` (POSIX): mesma função, autodetecta
  Chrome/Chromium em macOS/Linux.

**3. Profile flags (`profile-merge.py` + `profile-matrix.md`):**
- Função nova `_preview_loop_config(profile, tier)` emite bloco
  `preview_loop` em `profile-effective.yaml`:
  - `preview_loop_enabled: true`
  - `mock_data_strategy` tier-based (`fixtures` | `msw_faker` | `msw_faker_zod`)
  - `cdp_live_enabled: true`
  - `visual_iter_cap: null`
  - `design_cascade_threshold: 5`
  - `preview_pages_path: preview/`
- Aplica APENAS em `app_web_frontend` + `fullstack`.

**4. Stage 02 design template — step 7.6:**
- Preview Loop schema mock data + preview pages flag.
- Tier ≥ development: designer escreve schema Zod em plan.md.
- Tasks com componente reusável ganham `requires_preview_page: true`.
- Routes map `output/routes.md` populado pra fallback CDP.
- Wireframe ASCII opcional pra layout não-trivial.

**5. Stage 04 implementation template — entry/exit hooks + sub-steps:**
- Entry hook: detect package manager via lockfile, start dev server
  em background, salvar PID em `.icm-main/.dev-server.pid`,
  imprimir kickoff priming.
- Verificação tier-aware reescrita: `tsc` cada Edit, lint+Playwright
  wave-end, full sob pedido.
- Stop points novos `feedback_ambiguous` + `design_system_cascade`.
- Exit hook: matar PID, apagar PID file, preservar `.icm-chrome-profile/`.

**6. Recovery wizard tipos novos (`scripts/recovery-wizard.py`):**
- `DEV_SERVER_ORPHAN`: PID file existe + processo morto. Plan A:
  apaga PID file + log, registra warning. Cross-platform (POSIX
  via `os.kill(pid, 0)`, Windows via `ctypes.OpenProcess`).
- `CDP_DISCONNECTED`: `.icm-chrome-profile/` existe + Chrome não
  listening em :9222. Plan A: warning, sugere helper relaunch
  (não mata profile dir).
- Helpers `_is_pid_alive(pid)` + `_is_port_listening(host, port)`
  adicionados (sem deps externas).

**7. Bootstrap (`scripts/bootstrap.py`):**
- `SKILL_VERSION = "3.6.0"`.
- `.icm-chrome-profile/` adicionado a `GITIGNORE_LINES`.
- Função nova `detect_package_manager(project_root)` retorna
  `(pm, dev_cmd)` baseado em lockfile (prioridade
  `bun > pnpm > yarn > npm`).

**8. Cross-refs:**
- `references/design-system.md` v3.6.0 → seção "Build-iterate visual
  loop" + cross-ref ao novo doc.
- `templates/_config/profile-matrix.md` → tabela de flags preview loop
  na seção `app_web_frontend` e `fullstack`.

---

## v3.5.0 — Stage 04 protocol gaps fix (2026-04-29)

### Why v3.5.0

10 gaps de protocolo identificados no stage 04 wave execution durante
revisão de execução real. Cada gap mascarava edge cases que produziam
estado inconsistente (worktrees órfãs, merge order não-determinístico,
conflict mid-wave sem fluxo de retomada, HITL granularidade insuficiente).
Adicionalmente: 12 arquivos com drift cross-file e introdução de drift
prevention test gate.

### Mudanças

**1. Doc drift fix (CLAUDE.md skill root + README.md):**
- Linha "no worktrees" removida; substituída por referência a
  `Agent(isolation: "worktree")` (alinhamento com v3.4.0+).
- README.md "10 profiles" → "11 profiles" (drift pré-existente desde v3.4.4).

**2. Branch lifecycle determinismo (L2 stage 04):**
- Passo 2 explicita: lead cria branch ANTES do spawn (`git branch
  wave-<NNN>-<N>/<slug> <BASE_BRANCH>`), Agent harness faz worktree
  add em branch existente. Branch órfã detectável via `git branch
  --merged`.
- Passo 11 ganha decision matrix `--force` determinística:
  `auto_qa_passed: true` no task report → safe `--force`; senão
  BLOCKED_ERROR.

**3. Subagent protocol additions (L2 stage 04):**
- Passo 8 declara wave-reviewer SEM `isolation: "worktree"` — lê
  via `git show wave-<branch>:<file>` / `git diff <BASE>...<wave>`.
- Passo 4.6 + passo 6: subagente grava `qa_loops_used: <N>` no
  frontmatter de `task-<slug>.md`; reviewer audita contra git log
  da wave branch (anti-fraude).
- HITL handling reescrito com granularity task-level: wave mista
  spawna Agents pra tasks não-HITL em paralelo, tasks HITL
  registradas com `status: AWAITING_HITL`. Status novo:
  `BLOCKED_HITL` (distinto de `BLOCKED_ERROR`).

**4. Merge orchestration (L2 stage 04):**
- Passo 7 ganha sort buffer: `{task_slug: agent_result}` → ordena
  por índice em `plan.md > tasks[]` antes do passo 9. Merge order =
  plan order, não retorno order.
- Passo 1 grava `pre_wave_sha` em L1 history evento `wave_started`
  (usado por rollback).
- Novo doc `references/conflict-resolution-protocol.md`: lead pausa
  em `BLOCKED_ERROR`, escreve `merge-conflict-<slug>.md`, gate
  humano A/B/C (resolvido / abort task / abort wave). Lead JAMAIS
  resolve conflict autonomamente.
- Novo doc `references/ci-rollback-protocol.md`: passo 10 vermelho
  → diagnose-protocol obrigatório (cap 3 attempts, fix < 50 LOC) →
  rollback (`git reset --hard <pre_wave_sha>`) → gate humano A/B/C
  (redo wave / redo task / abandon). Wave branches preservadas
  durante BLOCKED_ERROR.

**5. `.icm-main` robustness (L2 stage 04):**
- Sync `cd .icm-main && git pull --ff-only` agora condicional:
  só executa se `git worktree list --porcelain | grep -q
  ".icm-main"` retorna match. Skip silencioso senão (`.icm-main` é
  convenção opcional setup pelo recovery wizard / bootstrap).

**6. Doc canônico consolidado:**
- Novo `references/wave-execution-protocol.md` consolida pipeline
  12-passos, atores, branches, status, cross-references.
  Single source of truth — outros docs apontam pra cá.

**7. Stale files audit (Chunk 6):**
- `scripts/bootstrap.py` SKILL_VERSION 3.4.1 → 3.5.0 (CRÍTICO —
  versão real injetada em workspaces novos).
- `scripts/validate_state.py` ALLOWED_STATUSES const + BLOCKED_HITL
  no enum.
- `references/state-machine-schema.md` row BLOCKED_HITL.
- `references/design-system.md` v3.4.4 → v3.5.0.
- CLAUDE.md + SKILL.md + profile-merge.py + test_profile_merge.py:
  10 → 11 profiles (drift pré-existente).
- `scripts/recovery-wizard.py` detector novo `MISSING_PRE_WAVE_SHA`
  + auto-fix marca `unknown` para waves pré-v3.5.0.
- `references/task-types-hitl-afk.md`: seção task-level granularity
  + status BLOCKED_HITL.
- `references/subagent-protocol.md`: cross-ref pra
  wave-execution-protocol.md (anti-duplicação).
- `references/example-run.md`: walkthrough sync com fields
  `pre_wave_sha` / `qa_loops_used`.
- `references/smoke-manual-checklist.md`: 10 checks v3.5.0.

**8. Drift prevention permanente (Chunk 7):**
- Novo `tests/unit/test_no_drift.py` (5 detectores):
  - Versão consistente (canonical = `bootstrap.py:SKILL_VERSION`).
  - Profile count (canonical = `len(CANONICAL_PROFILES)`).
  - Status enum sync (validate_state.py ↔ schema.md).
  - Cross-refs markdown resolvem em `references/`.
- `validate_state.py` exporta `ALLOWED_STATUSES` const module-level
  → single source pra drift test.
- CLAUDE.md ganha seção "Pre-merge drift audit (mandatory)" — test
  gate bloqueia drift no commit, sem precisar lembrar.

### Migrations / breaking changes

Não há breaking changes pra workspaces v3.4.x existentes:
- Status novo `BLOCKED_HITL` é additive (workspaces antigos não
  usam, mas validador aceita).
- `qa_loops_used` no task report é additive (workspaces antigos
  sem o field continuam válidos; reviewer trata ausente como N/A).
- `pre_wave_sha` em L1 history é additive (recovery wizard ganha
  detector novo `MISSING_PRE_WAVE_SHA` opcional para waves
  iniciadas pré-v3.5.0; auto-fix marca `pre_wave_sha: unknown`).

### Tests

- `tests/unit/test_v3_5_0_wave_protocol.py` — 14 tests cobrindo
  todos os gaps fechados (presença de seções em L2, existência
  dos novos docs, version bump, changelog entry).
- `tests/unit/test_no_drift.py` — 5 tests cobrindo drift detection
  permanente. Bloqueia regressão automaticamente.

### Plan

- `docs/plans/2026-04-29-stage-04-gaps-fix.md` — implementation
  plan completo (7 chunks, 30 tasks).

---

## v3.4.4 — Profile fullstack + Design system (DESIGN.md format) (2026-04-29)

### Why v3.4.4

Dois adds em uma versão:

1. **Profile `fullstack`** — projetos onde backend + frontend coexistem
   no mesmo repo (Next.js com API routes, Remix + Prisma, T3 stack,
   Django + React colocated). `app_web_backend` deixava metade dos
   gates frontend desligados (component testing, e2e, a11y, visual
   regression); `app_web_frontend` deixava metade dos gates backend
   (http_integration, db_integration). Resultado: bugs UI escapavam
   audit em projetos fullstack reais.
2. **Design system L3** — stage 02 design pra profiles
   `app_web_frontend` e `fullstack` agora cria/atualiza
   `<project_root>/.icm-main/DESIGN.md` (formato Google Stitch spec)
   como fonte de verdade do visual. Subagentes em fase 04 ganham
   subset relevante via canal 2.

### Mudanças

**1. Profile `fullstack` (11º profile canônico):**
- `scripts/profile-merge.py`: `CANONICAL_PROFILES` adiciona
  `"fullstack"`. `_test_specs` novo branch retornando superset
  backend + frontend (`test_types_required: [unit, integration,
  component, e2e]`, `http_integration`, `db_integration`,
  `component_testing`, `e2e_required`, `visual_regression` (prod),
  `a11y_testing` (dev+prod), `design_system_required: True`).
- `_apply_profile_rules`: `fullstack` ganha `security_gate: True`
  em qualquer tier ≠ `experimental` (igual app_web_backend e
  app_web_frontend).
- `templates/_config/profile-matrix.md`: tabelas atualizadas pra
  refletir 11 profiles + nova linha de overrides combinando
  app_web_backend, app_web_frontend, fullstack.

**2. Design system L3 + DESIGN.md format:**
- Novo `references/design-system.md` (~290 linhas) adotando spec
  DESIGN.md do Google Stitch como formato canônico:
  - Schema YAML frontmatter: `colors`, `typography`, `rounded`,
    `spacing`, `components` + token reference syntax `{path.to.token}`
  - Section order: Overview → Colors → Typography → Layout →
    Elevation & Depth → Shapes → Components → Do's and Don'ts
  - 3-layer token architecture (primitive → semantic → component)
  - Component spec table template (Default/Hover/Active/Disabled)
  - Fluxo por stage ICM 00-08 mapeado
  - Stage 02 menu A/B/C: criar do zero / inspirar awesome-design-md /
    extrair de URL via designlang externamente
  - Galeria referência: VoltAgent/awesome-design-md (69 brands)
  - Tool externa opcional: Manavarya09/design-extract (designlang)
  - Escape hatch: ui-ux-pro-max-skill com boundary explícita
- L0 (`templates/workspace/CLAUDE.md.tpl`): adiciona path
  `<project_root>/.icm-main/DESIGN.md` em "Paths absolutos"
- L2 stage 02 (`02_design/CONTEXT.md.tpl`):
  - Inputs ganha 2 rows (design-system.md doc + DESIGN.md brownfield)
  - Process step 7.5 NOVO condicional ao profile
- L2 stage 04 (`04_implementation_waves/CONTEXT.md.tpl`):
  - Process step 3 (canal 2 inject) ganha cláusula condicional
    pra tasks com flag `requires_design_system: true`
- Bootstrap (`scripts/bootstrap.py`): `runtime_refs` tuple adiciona
  `"design-system.md"` (copiado pro `_references/runtime/` no workspace)

### Compatibilidade

Workspaces v3.4.x existentes não-fullstack continuam funcionando
(retrocompatível). Workspace antigo querendo migrar pra fullstack:
edit L0 + recompute hash via `profile-merge.py --profile fullstack`.

Profile `app_web_frontend` ganha `design_system_required: True`
retroativamente — workspaces antigos sem DESIGN.md continuam OK
(stage 02 detecta ausência e oferece menu A/B/C ao retomar).

### Testes

18 tests novos:
- `tests/unit/test_profile_merge.py`: classe `TestFullstackProfile`
  com 7 tests (test types superset, dimensões backend+frontend,
  visual_regression só prod, design_system_required pros 2 profiles,
  ausência em outros, hash distinto)
- `tests/unit/test_design_system_doc.py`: 11 smoke tests pro doc
  canônico

Suite total: 649 tests verde. Coverage 76% mantido.

---

## v3.4.3 — Wave worktree cleanup (2026-04-29)

### Why v3.4.3

Bug observado em uso real: após cada wave de fase 04, worktrees efêmeras
criadas pelos subagentes (Agent tool com `isolation: "worktree"`)
ficavam orfãs em `<project_root>/.icm-wave-*` (ou path retornado pelo
tool), e branches `wave-<NNN>-<N>/<task-slug>` poluíam `git branch`
listing. Lead nunca executava cleanup pós-merge.

### Mudanças

**1. L2 stage 04: novo passo 11 cleanup pós-merge:**
- Após merge sequencial + CI gate global verde, lead executa:
  ```bash
  git worktree remove <path-do-worktree>     # paths capturados dos Agent tool results
  git branch -d wave-<NNN>-<N>/<task-slug>   # safe pq merged --no-ff
  ```
- Fallback robusto se path foi perdido: `git worktree list --porcelain`
  filtrado por branch pattern.
- Falha não-fatal — registra warning em `wave-summary.md`, prossegue.
- `git branch -d` recusa não-merged (intencional). Não usar `-D`.

**2. Recovery Wizard: novo tipo `WAVE_WORKTREE_ORPHAN`:**
- Detect: `git worktree list` mostra worktrees com branch pattern
  `wave-<NNN>-` (NNN=workspace num) AND branch já merged em base_branch.
- Plan A (auto-cleanup): `git worktree remove <path>` + `git branch -d`.
  Cleanup safe pq detecção filtrou por já-merged.
- Skip orfas com branch não-merged (sinal de wave incompleta — atenção
  humana, não auto-cleanup).
- Helpers novos: `_list_worktrees`, `_is_branch_merged`.

**3. Docs atualizados:**
- `references/worktree-model.md` seção 3 (cleanup obrigatório).
- `references/subagent-protocol.md` seção 5.1 (Cleanup pós-merge).
- `references/recovery-wizard.md` (novo tipo).

### Compatibilidade

Workspaces v3.4.0/v3.4.1/v3.4.2 com worktrees orfãs acumuladas: rodar
Recovery Wizard manualmente quando aparecer. Plan A auto-cleanup remove
tudo de uma vez. Novos workspaces criados via v3.4.3 nascem com
cleanup automático no protocol da fase 04.

### Testes

8 tests novos em `tests/unit/test_v3_4_3_wave_cleanup.py`. Suite total
627 tests verde.

---

## v3.4.2 — Gate inline + tech debt drain (2026-04-29)

### Why v3.4.2

Bug-fix patch corrigindo loop de fim-de-stage observado em uso real
(workspace 001-001-saas-psicologo-mvp): sessão imprimia kickoff +
saía SEM aguardar gate humano; nova sessão detectava status pendente,
pedia aprovação, e re-imprimia o kickoff — confuso. Plus 2 itens de
tech debt acumulados.

### Mudanças

**1. Gate inline antes do kickoff em todos stages (bug fix principal):**
- L2 templates de stages 01-07 atualizados pra split End of stage handoff
  em duas fases dentro da MESMA sessão.
- Fase 1 WORK_DONE: update L1 (sub_stage=NN_completed,
  status=COMPLETED_AWAITING_HUMAN), commit atômico 1/2 (outputs + L1,
  SEM kickoff), imprime prompt de gate, AGUARDA humano.
- Fase 2 GATE_APPROVED (após "aprovado"): update L1
  (stage_atual=NN+1, sub_stage=NN+1_in_progress, status=IN_PROGRESS),
  render kickoff, commit atômico 2/2, imprime KICKOFF block, SAIR.
- Stage 04: gate só na transição última-wave→05 (mid-wave continua auto).
- Stage 06: gate só no caso A (sem P0/P1). Loopback ao 04 é auto.
- Stage 07: gate aprova merge-report; após aprovação, auto-transita
  07→08 com status=COMPLETED_AWAITING_HUMAN (workspace fica vivo
  aguardando feedback do mundo real, sem segundo gate).
- Doc canônico: `references/session-handoff-protocol.md` (diagrama
  atualizado seção "Anatomia de uma sessão").

**2. Recovery Wizard: novo tipo `KICKOFF_WITHOUT_GATE`:**
- Detecta workspaces buggy (criados antes da v3.4.2) com kickoff de
  stage NN+1 presente enquanto L1 indica `stage_atual=NN,
  status=COMPLETED_AWAITING_HUMAN`.
- Ação: oferece humano (a) aprovar gate retroativo (mantém kickoff,
  transita L1) ou (b) deletar kickoff e voltar ao trabalho do stage NN.

**3. Tech debt: `agent-brief-render.py` regex desatualizado:**
- Regex buscava `### Task: <slug>` (H3) + `**O QUE:**` (bold marker).
- Schema canônico (`references/4-block-contract-template.md`) é
  `## Task <SLUG>:` (H2) + `### O QUE` (H3).
- Mismatch fazia leads renderizarem briefs manualmente em fase 04.
- Fix: regex atualizado pra schema canônico H2/H3.

**4. Tech debt: bootstrap auto-merge `settings.local.json` no project_root:**
- Antes: bootstrap renderizava só `.example`; humano copiava manualmente
  pra ativar PostToolUse hook do `context-check.sh`.
- Inconsistência: workspace scope (`workspaces/<NNN>/.claude/settings.local.json`)
  já era auto-criado com merge idempotente, mas project_root scope não.
- Fix: bootstrap agora faz merge idempotente em
  `<project_root>/.claude/settings.local.json` (preserva customizações
  do user + adiciona/atualiza apenas a entrada ICM identificável por
  `command` contendo `context-check.sh`). Mantém `.example` por
  documentação.

### Compatibilidade

Workspaces v3.4.0/v3.4.1 já em curso: rodar Recovery Wizard manualmente
quando aparecer sintoma do bug (kickoff já gerado mas gate não aprovado).
Novos workspaces criados via v3.4.2 nascem com gate-inline.

---

## v3.4.1 — Backlog (migration, handoff saída A, Tier 3) (2026-04-29)

### Why v3.4.1

Patch sequência da v3.4.0 que finaliza items adiados do KICKOFF
(deferred 4+5) e drena Tier 3 backlog herdado da v3.3.0.

### Mudanças

**1. Migration script v3.3 → v3.4 (deferred 4):**
- Novo `scripts/migrate-v3.3-to-v3.4.py`. Detecta workspaces v3.3.x via
  `icm_skill_version` no L0, cria `.icm-main/` worktree, garante
  `docs/decisions/.keep` na base branch, atualiza `.gitignore`, bump
  `icm_skill_version` para 3.4.0. CLI: `--project-root <path>
  [--workspace <NNN-slug>] [--update-paths] [--dry-run]`.
- Idempotente: rerodar não causa dano. Workspaces v3.4.x são skip.
- 24 unit tests em `tests/unit/test_migrate_v3_3_to_v3_4.py`.

**2. Handoff saída A migra CLAUDE.md root (deferred 5):**
- `handoff.py:deactivate_project_claude_md` agora persiste o CLAUDE.md
  idle também na base branch via `.icm-main/CLAUDE.md` + commit.
- Sem isso, o CLAUDE.md root sumiria quando workspace branch fosse
  deletada após arquivamento.
- Idempotente: re-execução com mesmo conteúdo não gera commit extra.
- Doc canônico: `references/project-root-claude-md.md` (seção "Owner
  transition na saída A").
- 4 unit tests em `tests/unit/test_handoff_saida_a_v3_4_1.py`.

**3. Tier 3 backlog drenado:**
- **Deep modules + deletion test** (`references/deep-modules.md`):
  doc canônico de architecture review para stage 02. 5-item checklist:
  interface mínima, information hiding, single responsibility, deletion
  test, alternativa em ADR. Adicionado a `runtime_refs` do bootstrap +
  L2 stage 02. Smoke test em `tests/unit/test_deep_modules_doc.py`.
- **Git guardrails hook** (`templates/.claude/hooks/block-dangerous-git.sh`):
  PreToolUse hook que bloqueia push --force, reset --hard, clean -fd,
  branch -D, checkout/restore `.`. Instalado APENAS em workspaces
  tier=production (condicional em `bootstrap.py`).
- **PreToolUse anti-/init** (`templates/.claude/hooks/block-init-during-icm.sh`):
  bloqueia invocação de `/init` enquanto workspace ICM ativo. Mitigação
  G14. Instalado em todos os workspaces.
- **Zoom-out workflow stage 00**: section structured em
  `templates/workspace/stages/00_recon/CONTEXT.md.tpl` guiando agente
  ao encontrar módulo desconhecido (Grep callers → caller raiz → anotar
  glossário → não documentar agora → limite 3 níveis).

**4. Tests opcionais drenados:**
- `test_v3_3_docs_smoke.py` (12 tests): parsability + estrutura mínima
  de `adr-format.md`, `diagnose-protocol.md`, `triage-state-machine.md`,
  e `templates/workspace/_config/CONTEXT.md.tpl` (T1.3).
- `test_deep_modules_doc.py` (4 tests).

### Backlog para v3.5+

- Smoke test manual end-to-end em projeto real (greenfield/brownfield/
  multi-workspace) — checklist em `references/smoke-manual-checklist.md`,
  exige projeto real fora do escopo de unit tests.
- `tests/integration/test_pre_commit_whitelist.bats` (CI Ubuntu only).

---

## v3.4.0 — Cross-branch worktree model `.icm-main/` (2026-04-29)

### Why v3.4.0

Workspaces ICM v3.3.x sofriam de **path invisibility** entre branches:
o workspace branch (`workspace/NNN-slug`) não tinha `docs/decisions/`,
`docs/lessons.md`, `docs/tech_debt.md`, `src/`, `tests/` no working tree
porque esses paths viviam apenas em `base_branch`. L0/L2 declaravam paths
absolutos `<project_root>/docs/decisions/...` mas Read tool retornava
ENOENT em sessões workspace branch.

Workarounds frágeis (stash/checkout/commit/checkout/pop, `git show base:`,
checkout temp em main) violavam atomicidade L1↔outputs e sujavam history.

v3.4.0 introduz **worktree linkada permanente** `<project_root>/.icm-main/`
(checada em base_branch desde o bootstrap; gitignored em todas branches).
Sessões em qualquer estágio leem cross-branch via Read tool direto;
escritas cross-branch (ADRs, lessons, tech_debt) commitam via
`cd .icm-main && git commit ...` em transação única na base branch.

Doc canônico: `references/worktree-model.md`.

### Mudanças

**Worktree model (canônico):**
- `references/worktree-model.md` (NOVO) — fonte canônica do modelo Opção B; estrutura, comandos, regras de uso, falhas + recovery, comparação com opções A/C/D.

**Bootstrap:**
- `scripts/bootstrap.py` — `SKILL_VERSION` 3.3.0 → 3.4.0; `GITIGNORE_LINES` ganha `.icm-main/`; novas funções `_ensure_base_branch_docs(project_root)` (cria `docs/decisions/`, `docs/lessons.md`, `docs/tech_debt.md` na base branch) e `_setup_main_worktree(project_root, base_branch)` (cria worktree linkada via `git worktree add`); fluxo principal chama as duas ANTES de criar workspace branch; `_scaffold_workspace_dirs` não cria mais `docs/*` no project root (movido para `_ensure_base_branch_docs`).

**Templates L0/L2:**
- `templates/workspace/CLAUDE.md.tpl` — paths absolutos ganham coluna "Branch real"; nova entry "Worktree base branch (`.icm-main/`)" lista ADRs/lessons/tech_debt/src/tests sob esse prefix; §3 Branches reescrito para documentar worktree paralelo; §6 ADRs ganha workflow canônico via `cd .icm-main && git commit`; §8 nova "Cross-branch reads via `.icm-main/`" (numeração superpowers vai pra §9).
- `templates/workspace/stages/00_recon/CONTEXT.md.tpl` — paths `docs/`, `src/` migrados para `.icm-main/...`; pre-flight valida worktree existe.
- `templates/workspace/stages/01_discovery/CONTEXT.md.tpl` — paths migrados para `.icm-main/...`.
- `templates/workspace/stages/02_design/CONTEXT.md.tpl` — paths migrados; process step 6 "Spawn ADRs novos" reescrito com workflow `cd .icm-main && git commit`; nova seção "Worktree paralelo".
- `templates/workspace/stages/03_wave_planner/CONTEXT.md.tpl` — paths migrados.
- `templates/workspace/stages/04_implementation_waves/CONTEXT.md.tpl` — paths migrados; nova seção subagent worktree (`Agent(isolation: "worktree")`); lead sincroniza `.icm-main/` via `git pull --ff-only` após merge.
- `templates/workspace/stages/05_verification/CONTEXT.md.tpl` — paths migrados.
- `templates/workspace/stages/06_review/CONTEXT.md.tpl` — paths migrados; tech_debt update via `cd .icm-main`.
- `templates/workspace/stages/07_merge/CONTEXT.md.tpl` — paths migrados.
- `templates/workspace/stages/08_feedback_intake/CONTEXT.md.tpl` — paths migrados; lessons append via `cd .icm-main`.

**Hooks:**
- `templates/.git-hooks/pre-commit` — whitelist tightened: removidos `docs/decisions/*.md`, `docs/lessons.md`, `docs/tech_debt.md` (devem ir via `.icm-main/`); mantém `workspaces/.index.md`, `.gitignore`, `CLAUDE.md`; nova rule rejeita paths em `.icm-main/*` (worktree paths não devem ser tracked pelo workspace branch — gitignore deve cobrir).
- `templates/.claude/hooks/icm-session-check.sh` (NOVO) — SessionStart hook valida (1) branch atual = workspace branch ativo; (2) `.icm-main/` worktree existe; (3) worktree em base_branch correta. Imprime warning visível, não bloqueia.
- `templates/project_root/.claude/settings.local.json.example` (NOVO) — exemplo de settings local com SessionStart + PostToolUse hooks apontando pros scripts no workspace.

**Recovery:**
- `scripts/recovery-wizard.py` — 3 novos códigos: `WORKTREE_MISSING` (critical, sugere `git worktree add .icm-main <BASE_BRANCH>`); `WORKTREE_WRONG_BRANCH` (warning, sugere `git checkout`); `WRONG_BRANCH_CHECKOUT` (warning, branch principal != workspace branch durante workspace ativo).

**Migration v3.3.x → v3.4.0:**
- Workspaces existentes pré-v3.4.0 continuam funcionando, mas sessões em workspace branch falham ao tentar `Read docs/decisions/...` (paths legados). Migration manual: (1) `git worktree add .icm-main <BASE_BRANCH>` no project_root; (2) adicionar `.icm-main/` ao `.gitignore` em todas branches; (3) opcional — atualizar L0/L2 paths para usar `.icm-main/` prefix. Recovery wizard detecta e sinaliza.

---

## v3.3.0 — Tier 1 + Tier 2 patterns adopted from mattpocock/skills (2026-04-29)

### Why v3.3.0

Análise comparativa do repo `mattpocock/skills` identificou 13 padrões aplicáveis. Esta release adota 8 deles (Tier 1 + Tier 2 + dependência), endereçando 6 gaps de UX/qualidade no skill atual. Os outros 5 ficam como future work (Tier 3).

### Mudanças

**T1.1 — `<project_root>/CLAUDE.md` + handoff dinâmico:**
- `templates/project_root/CLAUDE.md.tpl` (NOVO) — template com marcadores `<!-- ICM-START/END -->` delimitando região exclusiva da skill.
- `scripts/handoff.py` — `WorkspaceBlock` dataclass; `update_project_claude_md`, `remove_workspace_block`, `deactivate_project_claude_md`, `list_active_workspace_ids`. Round-trip JSON via comentários `<!-- ICM-DATA:... -->`. Atomic write tmp+fsync+rename (G15). CLI subcommands.
- `scripts/bootstrap.py` — `_render_project_claude_md` chamado durante bootstrap; CLAUDE.md root incluído no staging.
- `scripts/recovery-wizard.py` — codes `CLAUDE_MD_ROOT_STALE`/`CLAUDE_MD_ROOT_MISSING` (G5); plan A regenera bloco a partir do L1.
- `templates/.git-hooks/pre-commit` — whitelist CLAUDE.md root (G6).
- `references/project-root-claude-md.md` (NOVO) — doc canônico cobrindo G1-G17 (brownfield, multi-workspace, /init contract, atomicidade, concorrência).
- `references/session-handoff-protocol.md` — §verbal block simplificado (remove KICKOFF copy-paste; CLAUDE.md root cobre read order).
- `tests/unit/test_project_root_claude_md.py` (NOVO) — 17 tests cobrindo greenfield, brownfield (com/sem marcadores), multi-workspace, idempotência, atomic write, round-trip JSON.

**T1.2 — AGENT-BRIEF template:**
- `references/agent-brief-template.md` (NOVO) — formato canônico (durability over precision, behavioral not procedural, complete acceptance criteria, explicit scope boundaries). Mapping pra 4-block do plan.md.
- `scripts/agent-brief-render.py` (NOVO) — extrai task do plan.md, parse 4-block, renderiza AGENT-BRIEF. CLI; warn de anti-patterns (paths absolutos, line numbers).
- `tests/unit/test_agent_brief_render.py` (NOVO) — 10 tests.

**T1.3 — CONTEXT.md ubiquitous language layer:**
- `templates/workspace/_config/CONTEXT.md.tpl` (NOVO) — glossário de domínio (L3), vazio no bootstrap, populado em stage 01.
- `references/context-format.md` (NOVO) — formato Term/Definition/Avoid/Relationships/Example dialogue/Flagged ambiguities.
- `scripts/bootstrap.py` — render do `_config/CONTEXT.md` durante scaffold.

**T1.4 — ADR 3-critérios gate:**
- `references/adr-format.md` (NOVO) — gate (hard to reverse + surprising without context + real trade-off); template minimal; sections opcionais.
- `templates/workspace/docs/decisions/_template.md` (NOVO) — template para ADR individual.

**T2.5 — Diagnose 6-fase:**
- `references/diagnose-protocol.md` (NOVO) — 6 fases (build feedback loop → reproduce → hypothesise → instrument → fix+regression test → cleanup+post-mortem). Hipóteses 3-5 ranked falsifiable. Tag logs `[DEBUG-xxxx]`.
- `templates/workspace/_config/hitl-loop.template.sh` (NOVO) — template HITL bash loop pra Phase 1 item 10.

**T2.6 — HITL/AFK classification:**
- `references/task-types-hitl-afk.md` (NOVO) — definição HITL vs AFK + critérios de classificação. AFK é default. HITL exige justificativa.

**T2.7 — Triage state machine:**
- `references/triage-state-machine.md` (NOVO) — categorias (bug/enhancement) + estados (needs-triage / needs-info / ready-for-action / wontfix). Mapping → Saída A/B/C. AGENT-BRIEF gerado para B e C.

**T2.8 — OUT-OF-SCOPE kb:**
- `templates/workspace/_out-of-scope/README.md.tpl` (NOVO) — convenção do diretório. 1 arquivo por conceito rejeitado.
- `references/out-of-scope-kb.md` (NOVO) — quando criar (enhancement rejeitado), quando consultar (stage 02 iter>0, stage 08 triage). Format completo.
- `scripts/bootstrap.py` — cria `_out-of-scope/` no scaffold + render do README.

**Bootstrap.py geral:**
- 8 novos refs canônicos adicionados à lista `runtime_refs` (copiados pra `<workspace>/_references/runtime/`).
- `SKILL_VERSION = "3.3.0"`.

### Out-of-scope desta release (Tier 3 — future work)

- Deep modules + deletion test em stage 02
- Design It Twice (3 interfaces paralelas) em stage 02
- Git guardrails hook (production tier)
- Zoom-out instruction explícita em stage 00
- SKILL.md description tightening (write-a-skill format)

### Tests

- 538 tests passing (+10 vs v3.2.0). Coverage mantida.
- Novos: `test_project_root_claude_md.py` (17), `test_agent_brief_render.py` (10).

### Refs

- Plan: `<plans>/primeiro-fa-a-um-plano-sunny-glade.md` (gaps G1-G17 endereçados via adversarial review)
- Source patterns: github.com/mattpocock/skills (engineering/triage, engineering/diagnose, engineering/grill-with-docs, engineering/tdd, engineering/to-issues)

---

## v3.2.0 — Test infrastructure: test_specs, test-recipes, TDD evidências (2026-04-28)

### Why v3.2.0

Auditoria identificou 7 lacunas na infraestrutura de testes da skill: ausência de distinção por tipo de teste no plan.md, nenhum planejamento de testes no stage 02, stage 05 excluindo `tests/` completamente, profile-matrix sem `test_specs`, itens 1-3 do Akita sem evidência mandatória, sem receitas de teste por profile, e stage 01 sem captura de contexto de teste existente.

### Mudanças

- **`scripts/profile-merge.py`:** função `_test_specs(profile, tier)` nova — deriva `test_specs` para os 10 profiles cobrindo `test_types_required`, `coverage_threshold` (calibrado por tier), `http_integration`, `db_integration`, `component_testing`, `eval_strategy`, `eval_threshold` e similares. Campo integrado em `merge_profile()` — não-overridável via `.icm-profile.local.yaml`.
- **`templates/_config/profile-matrix.md`:** row `test_specs.coverage_threshold` na tabela de defaults (0 / 60 / 80 / 90 por tier). Nova seção "test_specs por profile" documenta valores canônicos dos 10 profiles.
- **`templates/_references/test-recipes/` (10 NOVOS arquivos):** receitas de teste por profile — `app_web_backend`, `app_web_frontend`, `agent_ia`, `ml_project`, `cli_tool`, `framework_library`, `dashboard`, `data_analysis`, `experiment`, `technical_article`. Frameworks, padrões, anti-patterns e checklist rápido por profile.
- **`scripts/bootstrap.py`:** copia `_references/test-recipes/<profile>.md` para workspace durante bootstrap.
- **`templates/workspace/stages/01_discovery/CONTEXT.md.tpl`:** Input #12 test-recipe (condicional). Novo passo 9 "Levantar Test Context" — captura suite existente, framework, coverage policy, eval strategy; saída em `§Test Context` do discovery.md.
- **`templates/workspace/stages/02_design/CONTEXT.md.tpl`:** Novo passo 8 obrigatório "Definir Test Strategy global do workspace". Transition condition: `plan.md` deve conter `§Test Strategy` + toda task de código deve declarar ≥1 arquivo de teste em `Files touched`.
- **`references/wave-planner-algorithm.md`:** §2 "Regra de test file obrigatório" — tasks com arquivos de código (`src/`, `.py`, `.ts`, etc.) devem declarar ≥1 arquivo de teste; violação = `BLOCKED_ERROR "test file missing for task <slug>"`; exceção para `doc-only`/`config-only`.
- **`references/4-block-contract-template.md`:** regra em `Files touched` obriga ≥1 arquivo de teste por task de código. Itens 1-3 do Akita agora exigem evidência mandatória: nome do arquivo de teste + nome do test case; cobertura ≥ threshold; execução 3× consecutiva.
- **`templates/workspace/stages/05_verification/CONTEXT.md.tpl`:** Passo 4.5 — auditoria `coverage report` vs `test_specs.coverage_threshold` (PASS/CONDITIONAL/FAIL por tier). Passo 4.6 — sample-check 3 tasks aleatórias do wave-plan verificando tipos de teste no FS. Constraint `Não Lê` relaxada: leitura parcial de `tests/` via `git ls-files` + coverage report.

### Tests

Suite existente mantida. Regra de test file do Wave Planner coberta por `test_wave_planner_dag.py`. `_test_specs()` é pura — testável por unit test direto.

---

## v3.1.0 — Agent Teams → subagentes (2026-04-27)

### Why v3.1.0

Substituição completa do modelo Agent Teams (baseado em git worktrees + mailbox custom) pelo modelo de subagentes nativos do Claude Code (Agent tool). O novo modelo elimina a complexidade de worktrees, mailbox e rebase sequencial, usando branches isoladas e merges em vez de rebases. Simplifica a orquestração da fase 04 e reduz superfície de erro.

### Mudanças

- **`references/subagent-protocol.md` (NOVO):** protocolo canônico de subagentes substitui `agent-team-protocol.md`. Usa Agent tool nativo em vez de git worktrees + mailbox. Sem sync barrier manual — o lead aguarda retorno direto de cada subagente.
- **`references/agent-team-protocol.md` (DEPRECATED):** removido do fluxo ativo. Preservado em `references/v2.4-snapshot/` para referência histórica.
- **`references/file-flow-diagram.md` (DEPRECATED):** removido do fluxo ativo. Diagrama original referia-se ao modelo de worktrees/mailbox.

### Terminologia atualizada em todos os references ativos

- "Agent Team" / "agent team" / "Agent Teams" → "subagente" / "subagentes" / "subagente" (conforme contexto em PT-BR)
- "teammate" / "teammates" → "subagente" / "subagentes"
- "worktree" / "git worktree" → "branch isolada" / "branches isoladas" (contexto de isolamento de task)
- "mailbox" / "mailbox custom" → "saída do Agent tool" (contexto de sinalização entre lead e subagente)
- "rebase" (sequencial de wave) → "merge" (o workflow agora usa merge em vez de rebase)
- "agent-team-protocol.md" (referência) → "subagent-protocol.md"

### Arquivos atualizados

- `references/session-handoff-protocol.md`
- `references/4-block-contract-template.md`
- `references/stage-templates.md`
- `references/xp-workflow-integration.md`
- `references/wave-planner-algorithm.md`
- `references/stop-points-canonical.md`
- `references/state-machine-schema.md`
- `references/recovery-wizard.md`
- `references/superpowers-mapping.md`
- `references/doc-reading-protocol.md`
- `references/smoke-manual-checklist.md`
- `references/example-run.md`
- `references/changelog.md` (este arquivo)

### Semântica preservada

- Arquivos em `references/v2.4-snapshot/` não foram alterados (snapshot histórico imutável).
- Entradas históricas do changelog (v2.4 e anteriores) permanecem com a terminologia original "Agent Teams" / "worktrees" — são registros históricos.
- `using-git-worktrees` permanece como skill auxiliar no mapeamento de superpowers (a skill ainda existe no plugin superpowers, mas o protocolo ICM não a exige mais).

---

## v3.0.0-beta5 — Git governance overhaul + subagent protocol (2026-04-28)

### Why beta5

Auditoria de git revelou 7 problemas: subagentes sem checkout explícito de branch, lead ficando em base_branch após merge, context-check.sh crashando sob Agent calls paralelos, conflito ICM prefix vs Conventional Commits, wave branches sem nenhum hook, bootstrap parcial sem recovery, e chmod silencioso no Windows.

### Mudanças

- **`references/subagent-protocol.md`:** §2.4 branch setup obrigatório no prompt do subagente (`git checkout -b` + validação). §5 merge sequencial agora faz stash pré-flight, retorna pra workspace branch após cada merge, unstash ao final.
- **`templates/.claude/hooks/context-check.sh`:** reescrito. Removido `set -e` (causava crash em pipes vazios). Lock atômico via `mkdir` (elimina race condition com 4+ Agent calls paralelos). Cada comando de parse com `|| fallback`. jq check explícito. Guard contra git mid-operation.
- **`references/git-hooks.md`:** R8 — commit-msg emite warning em wave branches sem Conventional Commit. Nova seção "Wave branches" documentando separação workspace prefix vs conventional.
- **`templates/.git-hooks/commit-msg`:** R8 implementado — detecta `^wave-[0-9]+-[0-9]+/` e valida Conventional Commit types (não bloqueia, apenas avisa).
- **`references/recovery-wizard.md`:** 6ª inconsistência `BOOTSTRAP_PARTIAL` (scaffold commitado sem hooks). Ação A: instalar hooks. Ação B: rollback + re-bootstrap. Ordem canônica atualizada.
- **`templates/workspace/_config/xp-conventions.md.tpl`:** resolvido conflito workspace prefix vs Conventional Commits. Workspace branches = `workspace NNN: <desc>`. Wave branches = `<type>: <desc>`.
- **`scripts/bootstrap.py`:** chmod warning em POSIX (não mais `pass` silencioso). Em Windows aceita silencioso (comportamento esperado).
- **`SKILL.md`:** header bump beta4 → beta5.

### Tests

Suite existente mantida. Novas regras de hook (R8) cobertas por `test_commit_msg_hook.bats` em CI. Bootstrap chmod testado em `test_bootstrap.py`.

---

## v3.0.0-beta4 — 07→08 transição automática + 08 inferência de intenção (2026-04-26)

### Why beta4

User identificou bug semântico no beta3: stage 07 fechava workspace como `COMPLETED` sem transição automática pra stage 08, deixando feedback intake como ato manual desconectado do fluxo principal. Stage 08 ficava órfão; humano precisava lembrar de disparar manualmente. Decisão revisada:

- Stage 07 **não é terminal**. Transita imediatamente pra 08 após merge confirmado.
- Stage 08 = terminal real. Workspace fica em `COMPLETED_AWAITING_HUMAN` aguardando humano voltar com feedback livre após uso real do projeto (sem prazo).
- Stage 08 **infere intenção** do feedback livre (sem menu A/B/C cru). Mini-confirm antes executar.

### Mudanças

- **`templates/workspace/stages/07_merge/CONTEXT.md.tpl`:**
  - `next_stage: null` → `next_stage: "08"`.
  - Process passo 7 atualizado: transita 07_completed → imediatamente 08_in_progress + status COMPLETED_AWAITING_HUMAN.
  - Process passo 8 NOVO: render `_kickoff.md` em `stages/08_feedback_intake/`.
  - End-of-stage handoff substituído: KICKOFF block 07→08 sem menu A/B/C, instruções "abra nova sessão DEPOIS de uso real, cole feedback livre".

- **`templates/workspace/stages/08_feedback_intake/CONTEXT.md.tpl`:**
  - Pre-flight ajustado: aceita `status: COMPLETED_AWAITING_HUMAN` com `sub_stage: 08_in_progress` (transição automática vinda de 07).
  - Process passo 4 substituído: "feedback livre do humano" em vez de "4 blocos guiados".
  - Process passo 5 NOVO: **inferência de intenção** com heurísticas mapping → A/B/C + confidence score + clarificação se < 0.6.
  - Process passo 6 NOVO: mini-confirm `[s/n/edit]` em vez de menu A/B/C cru.
  - Seção "Inferência de intenção (heurísticas canônicas)" NOVA: mapping bug→stage X, sinais por saída, confidence, mini-confirm template.

- **`references/session-handoff-protocol.md`:** seção "Stage 07 terminal" reescrita pra "Stage 07 → 08 transição automática". Nova seção "Stage 08 terminal real" cobrindo saídas A/B/C inferidas. Stage 08 disparo: nova sessão normal (sem comando especial).

- **`SKILL.md`:** header bump beta3 → beta4. Seção "After bootstrap" atualizada: stage 07 → 08 automático; stage 08 saídas inferidas.

### Tests

527 passed mantido (templates não têm tests diretos; mudanças semânticas não afetam handoff.py / state machine schema).

### Migração

Workspaces beta3 já criados que estão em status COMPLETED após 07: nenhuma ação automática necessária. Se user quiser disparar feedback intake, basta editar L1 manualmente: `stage_atual=08`, `sub_stage=08_in_progress`, `status=COMPLETED_AWAITING_HUMAN`. Workspaces beta1/beta2 continuam legacy batched (decisão 4B).

---

## v3.0.0-beta3 — 1-stage-1-sessão + handoff dual (2026-04-26)

### Why beta3

Beta1/beta2 usavam sessões batched (Q3 do plan v1: design 00+01+02 numa só, closing 05+06+07 numa só). Em uso real, contexto cresceu além do alvo de 2-8k por L2. Token spend total não-linear vs número de sub_stages na batch.

User sinalizou ganho empírico em **context fresh** > custo de cache miss. Decisão revisada: **1 stage = 1 sessão** (decisão A1, supersede Q3-A do plan v1). Cada stage paga 1 cache miss (~2-3k tokens warm-up) em troca de context enxuto + token spend total menor.

### Mudanças

- **`references/session-handoff-protocol.md` (NOVO):** doc canonical do protocolo "1 stage = 1 sessão". Schema `_kickoff.md` (L4-kickoff layer), atomicidade do commit handoff, anti-patterns. Stage 04 mantém wave-aware (1 sessão lead por wave; sub-waves dentro da mesma sessão). Stage 07 terminal (não gera kickoff). Stage 08 saídas A/B/C.
- **`templates/workspace/stages/_kickoff.md.tpl` (NOVO):** template kickoff genérico com placeholders.
- **`scripts/handoff.py` (NOVO):** `render_kickoff`, `write_kickoff`, `extract_kickoff_metadata`, `validate_kickoff_present`. CLI mode pra debug. 25 unit tests + snapshot fixture.
- **9 L2 templates atualizados:** cada `templates/workspace/stages/<NN>_<name>/CONTEXT.md.tpl` ganhou linha `_kickoff.md` na tabela Inputs (condicional) + nova seção "End of stage handoff" com checklist + KICKOFF block verbal pro user. Stages 04, 07, 08 com customizações específicas. +541 linhas total.
- **`SKILL.md`:** seção "After bootstrap" reescrita com protocolo 1-stage-1-sessão. Trade-off cache miss vs context fresh documentado.

### Migração beta1/beta2 (decisão 4B)

**Sem migração forçada.** Workspaces criados antes do beta3 continuam em batched mode (legacy). Apenas workspaces criados pós-beta3 usam 1-stage-1-sessão.

### Tests

527 passed (+25 novos). Coverage 82%. Bats CI-only.

---

## v3.0.0-beta2 — Hook fix + intent inference + anti-superpowers (2026-04-26)

### Why beta2

Beta1 carregava bug crítico no pre-commit hook: lia `.git/COMMIT_EDITMSG` em pre-commit stage, mas git só persiste msg DEPOIS do hook passar. Hook validava msg do commit ANTERIOR (ou empty no primeiro). Workaround temporário (instalar hook depois dos commits do bootstrap) só protegia o bootstrap; commits futuros do user permaneciam validando msg stale.

### Mudanças

- **fix(hooks) — `0afcba7`:** split em 2 stages canônicos. `pre-commit` mantém file checks + atomicidade L1↔outputs. `commit-msg` (NOVO) recebe path em `$1` com msg atual; valida prefix + exceção ADR. Installer + bootstrap atualizados. Regression test garante msg ATUAL via `$1`.
- **feat(skill) — `77348b7`:** SKILL.md "Intent inference" com heurísticas profile/tier (10 mappings) + menu confirm + seed inicial em `stages/01_discovery/_seed.md`. Anti-superpowers rule (inegociável) refletida no L0 (rule 8).

### Tests

502 passed. Coverage 83%.

---

## v3.0.0-beta1 — Reescrita completa (2026-04-26)

> Filesystem é o programa. Skill é parteira, não orquestradora.

### Resumo

Reescrita end-to-end em 7 waves. Skill v2.4 (orquestradora persistente, 1 main + N subagents, 6 estágios) substituída por arquitetura ICM v3 (parteira one-shot + filesystem governa ciclo + 9 estágios + Agent Teams + Wave Planner LLM review + Recovery Wizard). v2.4 preservada em `references/v2.4-snapshot/` (snapshot histórico imutável).

### Why v3

**Problemas estruturais detectados em v2.4:**

- **B1**: Path absoluto vazado (orquestradora perdia CWD em fronteiras de subagent → escrevia em diretório errado).
- **B2**: Paths relativos `../../` confundiam subagents.
- **B3**: Stop points em subagent sem protocolo de retorno bem definido.
- **B6**: Sync barreira frouxa em fase de implementação paralela.
- **V3**: Skills superpowers invocadas dentro de cada estágio carregavam ~2-5k tok cada, inflando contexto.
- **Conflito de regras**: subagent rodando `/xp-workflow` dentro de estágio 03 batia com protocolo ICM.

**Decisões norteadoras:**

1. Filesystem é o programa, skill é só bootstrap.
2. Uma fase = uma sessão nova (cache prompt 5min Anthropic).
3. Skills superpowers viram referências (sumários 200tok), não invocações.
4. 4-block contract obrigatório por task.
5. Profile + Tier no L0 calibram rigor (10 profiles × 4 tiers = 40 combos).
6. Mandatory stop points + menu A/B/C padronizado em todo estágio com decisão.
7. Dev↔QA loop formal via auto-QA Akita 15-item.
8. Waves de paralelismo só onde for safe (DAG por file footprint).
9. Git worktrees por teammate (race mitigation física).
10. Reconnaissance Phase antes de tudo.
11. Feedback intake universal fase 08 (não só production).
12. Self-revision DROPADA — skill é parteira, não runtime evolutivo.

### Breaking Changes

- **CLI**: `/xp-icm-workflow` agora exige `profile=` e `tier=` (com fallback interativo). Sem default `app_web_backend`+`development`.
- **Estrutura de pastas**: 9 estágios (00 recon → 08 feedback intake) substituem os 6 da v2.4 (00 bootstrap → 06 merge). Numeração e nomes mudaram.
- **Branches**: agora 3 tipos — `<base_branch>` (código), `workspace/NNN-slug` (state-only), `wave-NNN-N/<task-slug>` (código wave). v2.4 só tinha 1.
- **State machine L1**: yaml frontmatter strict (PyYAML safe_load) com `sub_stage` enum específico por estágio. Schema validado em pre-flight.
- **Pre-commit hook**: instalado por padrão. Bloqueia bypass `--no-verify` e valida atomicidade L1↔outputs + prefixos.
- **Skills superpowers**: NÃO invocadas em runtime. Substituídas por sumários 200tok pré-copiados em `<workspace>/_references/superpowers-summary/`. Escape hatch via `Skill()` exige registro `event: skill_escape_hatch` em L1 history.
- **ADRs**: ciclo de vida formalizado — nascem em estágio 02, vão pra `<project_root>/docs/decisions/`, edição direta proibida (use superseding ADR).
- **Self-revision**: removida. v2.4 tinha Phase 7 (self-revision conversational); v3 dropa.

### What's New (Waves 1-6)

| Wave | Entregue |
|---|---|
| 1 — Foundations | Schema state-machine L1 com sub_stage enum por estágio; 4 scripts deterministic (profile-merge, lessons-match, wave-planner-script, validate_state); pre-commit hook bash POSIX com 6 regras; templates L0/L1; profile-matrix 10×4; pyproject.toml com workaround pytest-playwright. |
| 2 — Bootstrap + Recovery | SKILL.md reescrita (parteira one-shot); bootstrap.sh + bootstrap.py com greenfield/existing/external_repo; recovery-wizard.py detectando 6 inconsistências R2.7+R4.5 com 3 ações A/B/C; git-hook-installer.sh idempotente. |
| 3 — Stage Templates + L2 | 9 L2 templates (00..08) com schema canônico (frontmatter + Inputs + Não Lê + sub_stage enum + applicable_stop_points); 4 references (stage-templates, stop-points-canonical 12 itens, 4-block-contract + ciclo TDD 7 passos + Akita 15-item, feedback-intake-fase08 com 3 saídas A/B/C); workspace stop-points.md resolvido por tier. |
| 4 — Agent Teams + Wave Planner LLM | references/wave-planner-algorithm.md (DAG + LLM review subagent R2.4); references/subagent-protocol.md (spawn via Agent tool + mid-wave reduce); scripts/wave-planner-llm-review.py com modo mock (`--mock-response`), prod (`--llm-response`) e prompt (exit 2). |
| 5 — Superpowers summaries | 10 sumários 200tok em `templates/_references/superpowers-summary/` (brainstorming, writing-plans, dispatching-parallel-agents, TDD, subagent-DD, verification, requesting-review, receiving-review, finishing-branch, debugging); references/superpowers-mapping.md, xp-workflow-integration.md, example-run.md reescritas; bootstrap.py copia summaries + 7 runtime refs pra workspace. |
| 6 — CI + Smoke | `.github/workflows/test-skill.yml` (Ubuntu Python 3.13 + bats); tests/run.sh com flags `--ci` e `--no-bats`; README badges; references/smoke-manual-checklist.md (10 itens canônicos pré-release). |

### Suite stats finais

- **502 tests verde** (100% Python 3.13 Windows + Linux CI).
- **Coverage 83%** total. Scripts puros 87-96%. Bootstrap 49% (orchestration cobre via bats e2e). Recovery 73%.
- **Bats CI-only**: integration (test_git_hooks, test_bootstrap, test_worktrees) + e2e (recovery_orphan, greenfield_full, existing_repo, external_repo).
- **Hypothesis property-based**: state-machine + wave-planner DAG (preserva deps, sub_waves respeitam cap).
- **Mocks LLM**: 3 fixtures em `tests/mocks/llm_review_responses/` (approve_clean, propose_implicit_dep, invalid_verdict).

### Migration Guide v2.4 → v3

**Workspaces v2.4 existentes**: NÃO migram automaticamente. Estratégia recomendada:

1. Workspace v2.4 termina ciclo atual (chega a `STAGE: COMPLETED`).
2. Para nova feature: bootstrappar workspace v3 do zero com `/xp-icm-workflow profile=X tier=Y`.
3. Lessons coletadas em `docs/lessons.md` migram automaticamente (formato compatível).
4. ADRs em `docs/decisions/` migram automaticamente (mesmo formato).
5. v2.4 snapshot preservado em `references/v2.4-snapshot/` para arqueologia.

**CLI mapping**:

| v2.4 | v3 |
|---|---|
| `/xp-icm-workflow` (sem args) | `/xp-icm-workflow profile=<X> tier=<Y>` (obrigatório) |
| `STAGE: 03_implementation` | `stage_atual: "04"` + `sub_stage: "04_wave_<N>_in_progress"` |
| Subagent spawn ad-hoc | Agent Team na fase 04 (lead + N teammates em git worktrees) |
| Skills superpowers invocadas inline | Sumários 200tok pré-copiados (escape hatch via L1 history) |

**Conventions stáveis** (não mudaram entre v2.4 e v3):

- Layer Loading Protocol (L0 → L1 → L2 → L3 → L4).
- ADR formato (Context / Decision / Consequences / Status).
- Edit-source principle.
- Português Brasil pra conteúdo, inglês pra identificadores.

### Critérios de promoção v3.0.0-beta1 → v3.0.0

Documentados em `references/smoke-manual-checklist.md`:

- ✅ Suite formal: ≥80% coverage críticos, ≥60% resto. CI verde 7 dias consecutivos.
- ✅ ≥3 projetos reais usaram v3.0.0-beta1 sem regressão grave.
- ✅ Comparação $: v3 ≤ 60% v2.4 em ≥3 projetos.
- ✅ 10 itens smoke checklist PASS em ≥3 projetos.
- ✅ Lessons coletadas em `docs/lessons.md` da própria skill (futura wave 8 manutenção).

---

## v2.4.0 — Refactor de concisão + correções adversariais

### Refactor estrutural (concisão sem perda)

- **SKILL.md reduzido de 1291 → ~600 linhas** sem perder hard-gates, princípios ou contratos.
- Templates de `CONTEXT.md` dos 6 estágios + templates de `CLAUDE.md` raiz e `CONTEXT.md` raiz movidos para `references/stage-templates.md`.
- Seção Extensibilidade movida para `references/extending-skill.md`.
- Histórico de versão movido para este arquivo (`references/changelog.md`).
- Novo `references/example-run.md` com exemplo de transição entre estágios.
- "Phase 1 — Execução por Estágios" compactada: protocolo de delegação e fix loop ficam no SKILL.md (load-bearing em runtime), detalhe de template fica em reference.
- Stage Transition Checklist declarado 1× em seção dedicada; estágios referenciam por nome em vez de duplicar.
- Princípio de Delegação com menção repetida somente onde o risco é real (Estágios 03/04/05).
- ICM Design Principles no SKILL.md ficam como 5 títulos + 1 frase cada; detalhe no reference `icm-paper-summary.md`.
- Convenção de prefixo `[L3:cfg]` / `[L4:in]` nos Inputs table — reduz prosa repetida sem perder distinção operacional restrição vs input.

### Correções adversariais round 1 (review por subagent)

- **Gap A (example-run)**: prompt do subagent no `example-run.md` agora inclui `decisions.md` — alinha com o Protocolo de Delegação do SKILL.md.
- **Gap B (contradição L1 vs L3)**: `docs/decisions/` agora é L3 consistente em todo SKILL.md (seção Edit-Source corrigida).
- **Gap C (race condition em reports paralelos)**: subagents paralelos escrevem em `output/reports/task-<slug>.md` (arquivos próprios). Orquestradora consolida depois em `implementation-report.md` — elimina race. Protocolo de Delegação, formato de output e example-run atualizados.
- **Gap D (Phase 0 não respeitava AGENTS.md)**: adicionado Passo 0.0 "Respeitar Instruction Priority" — lê `AGENTS.md` e `CLAUDE.md` do projeto pai ANTES de criar workspace.
- **Gap E (pasta `stages/XX/references/` nunca usada)**: removida da estrutura padrão. Agora opcional, criar apenas se houver material de referência específico do estágio.
- **Gap F (tensão ADRs L3 mas criados no run)**: adicionada seção "Ciclo de Vida dos ADRs" — esclarece nascimento no Estágio 02, promoção imediata a L3, edição via Edit-Source.
- **Gap G ("DELEGA, não executa" ambíguo)**: reformulado Orchestration Boundary — distingue invocação de skills (01-02) de delegação a subagents (03+), clarifica o que a orquestradora pode ler.

### Correções adversariais round 2 (cross-file review completa)

- **Gap S (template Estágio 03 desalinhado com correção Gap C)**: `references/stage-templates.md` atualizado — Template do Estágio 03 agora reflete a nova estrutura `reports/task-*.md` + consolidação em `implementation-report.md`. Outputs, Process passo 7 e Verify alinhados com SKILL.md.
- **Gap T (xp-workflow-integration tinha `docs/*` como L1)**: tabela "Documentos Compartilhados" corrigida — `docs/decisions/`, `docs/tech_debt.md`, `docs/lessons.md` agora são L3 consistente com Gap B. Tabela também inclui novos artefatos `reports/task-*.md`.
- **Gap U (superpowers-mapping regra 4 omitia reports paralelos)**: regra 4 agora lista `reports/task-*.md` individuais como artefato que orquestradora lê.
- **Gap Z (ambiguidade STAGE após transição)**: Stage Transition Checklist item 3 agora especifica que, após marcar estágio completado no histórico, o campo `STAGE` do `CONTEXT.md` raiz é atualizado para apontar ao PRÓXIMO estágio como `IN_PROGRESS`. Último estágio marca `STAGE: COMPLETED`. Example-run alinhado.

### Correções adversariais round 3 (detalhes finos cross-file)

- **Gap AB/AK (numeração do passo do Bootstrap)**: `stage-templates.md` referenciava "Passo 0.5" e "Passo 0.4" mas SKILL.md combinou em "Passo 0.4-0.6". Alinhado.
- **Gap AD (example-run descrevendo CONTEXT.md raiz errado pós-Z)**: Passo 2 do `example-run.md` agora reflete que ao entrar no Estágio 03 o campo `STAGE` já é `03_implementation, IN_PROGRESS` (não `02_design COMPLETED`).
- **Gap AE (review gate Estágio 03 omitia reports individuais)**: SKILL.md atualizado — review gate agora menciona leitura dos `reports/task-*.md` individuais E/OU consolidado.
- **Gap AF (superpowers-mapping listava lessons como input do subagent)**: corrigido — apenas orquestradora lê `lessons.md`; subagent recebe lições filtradas injetadas no prompt.
- **Gap AH (contagem errada de seções)**: SKILL.md e `stage-templates.md` diziam "seis seções" mas listavam 7 (Estado, Skill, Inputs, Process, Outputs, Verify, Review Gate). Corrigido para "sete seções".
- **Gap AJ (extending-skill item 4 omitia templates raiz)**: checklist agora inclui atualização de `CLAUDE.md` raiz e `CONTEXT.md` raiz quando a nova skill impactar identidade ou roteamento do workspace.
- **Gap AL (lessons.md fluxo não explícito)**: SKILL.md Processo do Estágio 03 passo 5 agora explicita que orquestradora lê `lessons.md`, extrai lições aplicáveis e injeta no prompt de delegação — subagent não lê o arquivo diretamente.
- **Gap AM (example-run anti-consistência ADR 0003)**: regras de contexto do prompt do subagent (a) agora dizem "NÃO ler ADRs 0001-0002"; ADR 0003 (stack) está resumido no `## Contexto do Workspace` do prompt — não duplicar leitura.

### Correções adversariais round 4 (subagent fresco)

- **Gap AN (numeração quebrada Estágio 03)**: "Processo da orquestradora" tinha passos 1-6 e depois "Após todos completarem" reiniciava em 6-8 — colisão. Agora sequencial 1-10, coerente.
- **Gap AO (regressão Gap C — quem escreve implementation-report)**: Texto "Formato de `implementation-report.md` (subagentes escrevem, orquestradora lê)" contradizia a arquitetura pós-Gap C. Corrigido: formato descreve `output/reports/task-<slug>.md` (cada subagent escreve o seu); consolidado é agregação feita pela orquestradora ou consolidator.
- **Gap AP (template Estágio 03 omitia reports paralelos)**: `stage-templates.md` Princípio de Delegação e Review Gate diziam "orquestradora lê SOMENTE implementation-report.md". Agora menciona reports individuais + consolidado consistente com SKILL.md e superpowers-mapping.
- **Gap AQ (example-run histórico sem ADRs)**: Stage Transition Checklist do exemplo agora inclui ADRs criados no Estágio 02 no histórico da transição.
- **Gap AR (typo schema→shema)**: 2 ocorrências de `0004-shema-habits.md` corrigidas para `0004-schema-habits.md`.
- **Gap AS (árvore docs/ em linha com vírgula)**: estrutura de pastas SKILL.md Passo 0.3 agora mostra `docs/` com 3 sub-itens em árvore (decisions/, lessons.md, tech_debt.md), classificados como L3.

Comportamento funcional equivalente a v2.3.0 + resolução de todas as ambiguidades, contradições e riscos estruturais detectados em 4 rounds de review adversarial (33 gaps corrigidos). Nenhum hard-gate removido.

---

## v2.3.0 — Hard Gates e Separação Rígida

- Stage Transition Protocol (5-item checklist hard gate entre estágios).
- Orchestration Boundary Rule (tabela por tipo de estágio + auto-correção).
- Fix Loop Protocol (review → delegate → review loop para P0/P1 issues).
- Review Gates 01-06 com checklist de transição explícito.
- Seção Estado obrigatória nos 6 templates de `CONTEXT.md`.

---

## v2.2.0 — Extensibilidade

- Seção Self-Improvement com checklist de 8 itens para atualizar quando nova skill é incorporada.
- Perguntas de classificação de nova skill.
- Formato de registro no changelog.

---

## v2.1.0 — Princípio de Delegação

- Orquestradora NUNCA lê código-fonte diretamente.
- Estágio 03 sempre delega para subagentes (não mais opcional).
- Templates de `CONTEXT.md` dos Estágios 03, 04 e 05 atualizados com "NÃO LER src/ ou tests/".
- Formato de `implementation-report.md` especificado.
- Error recovery atualizado para subagentes.
- Referências (`superpowers-mapping`, `xp-workflow-integration`) atualizadas para refletir delegação.

---

## v2.0.0 — Revisão baseada em auditoria contra o paper ICM

- Layer Loading Protocol com ordem obrigatória e scoping explícito.
- Distinção operacional Layer 3 vs Layer 4 (restrição vs input).
- Token budget e context pollution.
- Compilação incremental com re-execução seletiva.
- Seção Verify nos contratos de estágio.
- Princípio edit-source operacionalizado.
- Retomada de sessão lê Layer 2/3 do estágio atual.
- Context scoping para subagentes.
- Princípio "configure the factory".
- Workspace builder.
- 5 ICM design principles explícitos.

---

## v1.2.0 — Revisão final

- Paths relativos padronizados.
- Referências a `src/`, `tests/` corrigidas (não dentro de `stages/`).
- Atualização de `CONTEXT.md` raiz em todos os estágios.
- "Caminho absoluto" corrigido para "caminho relativo" nos subagentes.

---

## v1.1.0 — Correções pós-auditoria

- Arquivo de estado (`CONTEXT.md` raiz).
- Retomada de sessão.
- Propagação de ADRs formais.
- Contrato explícito de subagentes.
- Inputs completos nos templates.
- Error recovery distinto por origem.

---

## v1.0.0 — XP-ICM Workflow inicial

- Integração ICM + `/xp-workflow` + superpowers.
