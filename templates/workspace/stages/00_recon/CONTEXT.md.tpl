---
layer: L2
stage: "00"
stage_name: "recon"
sub_stage_enum:
  - "00_in_progress"
  - "00_completed"
applicable_stop_points:
  - "workspace_corrupt"
  - "profile_mismatch"
output_files:
  - "output/recon-report.md"
next_stage: "01"
---

# Estágio 00 — recon (L2)

Reconnaissance inicial do projeto. Detecta tipo de workspace (greenfield, existing, external_repo), valida coerência entre profile/tier declarados e estado real do repositório, lista ADRs vigentes e lessons herdáveis. Saída alimenta o discovery (estágio 01) com baseline factual — sem inventar contexto que não está no FS.

## Inputs (lê SOMENTE estes, na ordem)

| # | Path | Layer | Obrigatório? |
|---|------|-------|--------------|
| 1 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md | L0 | sim |
| 2 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md | L1 | sim |
| 3 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/stages/00_recon/CONTEXT.md | L2 | sim |
| 4 | {{PROJECT_ROOT}}/.icm-profile.local.yaml | L3 | condicional: existe se humano declarou override local |
| 5 | {{PROJECT_ROOT}}/.git/config | L3 | sim (read-only — checa base_branch + remotes) |
| 6 | {{PROJECT_ROOT}}/docs/lessons.md | L3 | condicional: existe se workspace foi spawn de fase 08 saída C ou herda de iteração anterior |
| 7 | {{PROJECT_ROOT}}/docs/decisions/ | L3 | condicional: lista índice de ADRs existentes (sem ler conteúdo de cada um) |
| 8 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/profile-effective.yaml | L3 | sim |
| 9 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/brainstorming-200tok.md | L3 | sim |
| 10 | {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/writing-plans-200tok.md | L3 | sim |

## Não Lê (negative constraint)

- {{PROJECT_ROOT}}/src/ e {{PROJECT_ROOT}}/tests/ — estágio 00 NÃO inspeciona código-fonte; só metadata de repositório.
- Conteúdo individual de ADRs em {{PROJECT_ROOT}}/docs/decisions/*.md — apenas o índice (filenames). Leitura detalhada acontece no estágio 02.
- Outputs de estágios 01+ — não existem ainda.
- Workspaces irmãos em {{PROJECT_ROOT}}/workspaces/<outro>/ — escopo deste workspace é {{WORKSPACE}}.

## Read order

1. L0 — {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CLAUDE.md (identidade)
2. L1 — {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/CONTEXT.md (state machine)
3. L2 — este arquivo (instruções do estágio)
4. {{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_config/profile-effective.yaml (profile + tier resolvidos)
5. {{PROJECT_ROOT}}/.icm-profile.local.yaml (se existe)
6. {{PROJECT_ROOT}}/.git/config (base_branch + remotes)
7. {{PROJECT_ROOT}}/docs/decisions/ (índice de ADRs — listing only)
8. {{PROJECT_ROOT}}/docs/lessons.md (se existe; herança de fase 08 saída C ou iteração anterior)
9. Sumários superpowers (brainstorming + writing-plans 200tok)

## Process

1. **Pre-flight:** validar que todos os paths Inputs marcados `sim` existem; sub_stage `00_in_progress`. Se path obrigatório ausente → status `BLOCKED_ERROR`.
2. **Detectar tipo de workspace:** classifica em `greenfield` (sem `src/` populado, sem ADRs), `existing` (repositório com código + ADRs prévios) ou `external_repo` (clone read-only que vai gerar workspace de leitura/análise). Decisão baseada em listing de `{{PROJECT_ROOT}}/src/` (apenas existência), `{{PROJECT_ROOT}}/docs/decisions/` (count de arquivos) e `git remote -v`.
3. **Validar coerência profile×tier vs estado real:** comparar `profile_base` e `tier` do L0/L1 contra realidade do FS. Sinais de mismatch — ex: tier `experimental` num repo com tag de release; profile `cli_tool` num repo com app web — disparam stop point `profile_mismatch`.
4. **Validar integridade do workspace:** rodar heurísticas de `references/state-machine-schema.md` §R2.7 (hash mismatch, history inconsistente, commit_sha sumido). Qualquer falha → stop point `workspace_corrupt` propondo Recovery Wizard.
5. **Listar ADRs vigentes:** glob `{{PROJECT_ROOT}}/docs/decisions/*.md` → registrar filename + título (primeira linha) sem ler corpo. Lista alimentará o estágio 02.
6. **Registrar herança (se `spawn_from`):** se L1 declara `spawn_from: <workspace>`, ler `{{PROJECT_ROOT}}/docs/lessons.md` e citar lições herdáveis aplicáveis em `recon-report.md`. Se ausente, anotar "sem herança".
7. **Consultar sumários superpowers** (brainstorming + writing-plans 200tok) para enquadrar o estilo do report — direto, factual, sem invenção.
8. **Escrever `output/recon-report.md`** com seções fixas: Tipo de workspace; Profile×tier check; ADRs vigentes (índice); Lessons herdáveis; Stop points pré-disparados (se houver); Próximos passos sugeridos para 01_discovery.
9. **Atualizar L1:** sub_stage `00_completed`, status `COMPLETED_AWAITING_HUMAN`, append `history` evento `stage_transition`. Commit atômico (pre-commit hook valida atomicidade L1↔outputs).

## Outputs

- `output/recon-report.md` — relatório de reconnaissance: tipo de workspace, validação profile/tier, índice de ADRs, lessons herdáveis, stops pré-disparados, próximos passos para 01.

## Sub_stage transitions

Enum válido: `00_in_progress`, `00_completed`.

Transição IN_PROGRESS → COMPLETED dispara quando:
- `output/recon-report.md` existe no FS.
- Validação profile×tier rodou (resultado documentado no report).
- Heurísticas de integridade rodaram (resultado documentado no report).
- Humano aprovou via gate (status `COMPLETED_AWAITING_HUMAN` → humano responde "prosseguir").

## Status canônicos disponíveis neste estágio

- `IN_PROGRESS` — recon ativo, lendo metadata do repositório.
- `COMPLETED_AWAITING_HUMAN` — recon-report pronto, humano revisa antes de transitar para 01.
- `BLOCKED_STOP_POINT` — `workspace_corrupt` ou `profile_mismatch` disparou; menu A/B/C aguardando resposta.
- `BLOCKED_ERROR` — path Input obrigatório ausente, hook rejeitou commit, ou git config inválido.

## Stop points aplicáveis

Catálogo canônico em `references/stop-points-canonical.md`. IDs disparáveis no estágio 00 recon:

- `workspace_corrupt` — inconsistência entre L1 frontmatter e estado real do FS (hash mismatch, outputs ausentes em history, commit_sha sumido). Sempre `hard`. Menu propõe Recovery Wizard como opção A.
- `profile_mismatch` — profile/tier declarados em L0/L1 não correspondem ao escopo real do projeto detectado pelo recon. Sempre `hard`. Menu propõe: A) ajustar profile/tier, B) spawn novo workspace, C) reduzir escopo.

Disparo: agente pausa, escreve menu A/B/C no output, atualiza L1 `status: BLOCKED_STOP_POINT`. Humano responde, sessão retoma com `IN_PROGRESS`.

## Skill superpowers de referência

Sumários 200tok (consulta obrigatória, skill formal só se complexidade justifica):

- `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/brainstorming-200tok.md`
- `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/writing-plans-200tok.md`

Skills formais (escape hatch): `superpowers:brainstorming`, `superpowers:writing-plans`.

## Gates

- **Humano:** revisa `output/recon-report.md`. Confirma "este recon-report está correto? prosseguir 01?" antes de transitar.
- **Automático (CI):** pre-commit hook valida atomicidade L1↔outputs e prefixo de commit `workspace/{{WORKSPACE}}`.
- **Aprovação para transitar:** humano explicitamente aprova; sub_stage vira `00_completed` no commit que registra a aprovação.
