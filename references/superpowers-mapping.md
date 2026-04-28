# Superpowers Mapping — xp-icm-workflow v3.0.0-beta5

> **Versão:** v3.0.0-beta5
> **Skill:** `xp-icm-workflow`
> **Propósito:** documento canônico de como o `xp-icm-workflow` v3 **usa** as skills do plugin `superpowers`. Versão v3 inverte a relação v2.4: superpowers viram **referências sumarizadas**, não invocações no runtime. Skill formal só por escape hatch.

> **Decisão de origem:** §4.7 do plan `reescrever-a-skill-zazzy-wirth.md` + §4.10 (tabela de mudanças v2.4 → v3, linha "Skills superpowers").

---

## 1. Filosofia (mudança vs v2.4)

| Aspecto | v2.4 | v3.0.0-beta1 |
|---|---|---|
| Forma de uso | `Skill({skill: "superpowers:writing-plans"})` invocada no runtime | Sumário 200tok pré-copiado em `<workspace>/_references/superpowers-summary/` |
| Quem carrega | Orquestradora (skill sempre ativa durante o ciclo) | Bootstrap copia 1× no início; sessões leem como L3 estável |
| Custo de tokens por estágio | ~3k SKILL.md + referências on-demand | ~200tok do sumário (15× menos) |
| Atualização | Sempre carrega versão upstream atual | Snapshot copiado; sync manual via Wave 8 (futura) |
| Escape hatch | n/a (sempre invoca) | Sessão pode `Skill({skill:"superpowers:<X>"})` se complexidade exige; logado em L1 history |

**Por que mudou.** `xp-icm-workflow` v3 é parteira one-shot, não orquestradora. Filesystem governa o ciclo via L0/L1/L2. Skills carregadas dinamicamente conflitam com o princípio "sessão lê só o que está declarado em Inputs". Sumários 200tok cabem em L3 estável; cada estágio referencia 1-2 sumários no L2 §11. Skill formal continua disponível, mas é fallback consciente.

---

## 2. Mapeamento canônico estágio ↔ skill ↔ sumário

Tabela autoritativa. Espelho do mapeamento em `references/stage-templates.md` §11. Em caso de divergência, `stage-templates.md` é fonte da verdade (o L2 do estágio é quem determina o que a sessão lê).

| Estágio | Slug | Skill superpowers principal | Sumário 200tok |
|---|---|---|---|
| 00 | `recon` | `brainstorming` + `writing-plans` (light) | `brainstorming-200tok.md`, `writing-plans-200tok.md` |
| 01 | `discovery` | `brainstorming` | `brainstorming-200tok.md` |
| 02 | `design` | `writing-plans` | `writing-plans-200tok.md` |
| 03 | `wave_planner` | `dispatching-parallel-agents` | `dispatching-parallel-agents-200tok.md` |
| 04 | `implementation_waves` | `test-driven-development` + `subagent-driven-development` | `test-driven-development-200tok.md`, `subagent-driven-development-200tok.md` |
| 05 | `verification` | `verification-before-completion` | `verification-before-completion-200tok.md` |
| 06 | `review` | `requesting-code-review` + `receiving-code-review` | `requesting-code-review-200tok.md`, `receiving-code-review-200tok.md` |
| 07 | `merge` | `finishing-a-development-branch` | `finishing-a-development-branch-200tok.md` |
| 08 | `feedback_intake` | (nenhuma direta) | usa `references/feedback-intake-fase08.md` local |
| transversal | qualquer estágio com bug | `systematic-debugging` | `systematic-debugging-200tok.md` |

### 2.1 Skills auxiliares (não mapeadas a estágio fixo)

| Skill | Onde aparece | Sumário |
|---|---|---|
| `using-git-worktrees` | fora do ciclo ICM (substituído por Agent tool) | `using-git-worktrees-200tok.md` |
| `writing-skills` | fora do ciclo ICM (Guilherme criando/editando skills) | n/a — não copiado para workspace |

---

## 3. Os 10 sumários 200tok pré-copiados

Bootstrap copia em `{{PROJECT_ROOT}}/workspaces/{{WORKSPACE}}/_references/superpowers-summary/`. Origem dos templates: `C:\Users\guicr\.claude\skills\xp-icm-workflow\templates\_references\superpowers-summary\`.

| # | Arquivo | Cobre estágio(s) |
|---|---|---|
| 1 | `brainstorming-200tok.md` | 00, 01 |
| 2 | `writing-plans-200tok.md` | 00 (light), 02 |
| 3 | `dispatching-parallel-agents-200tok.md` | 03 |
| 4 | `test-driven-development-200tok.md` | 04 |
| 5 | `subagent-driven-development-200tok.md` | 04 |
| 6 | `verification-before-completion-200tok.md` | 04 (CI gates), 05 |
| 7 | `requesting-code-review-200tok.md` | 06 |
| 8 | `receiving-code-review-200tok.md` | 06 |
| 9 | `finishing-a-development-branch-200tok.md` | 07 |
| 10 | `systematic-debugging-200tok.md` | transversal — qualquer estágio com bug |
| 11 | `using-git-worktrees-200tok.md` | auxiliar (fora do ciclo ICM) |

> Notar: lista efetiva tem 11 arquivos. O plan §7 lista 10 explicitamente; o 11º (`using-git-worktrees`) permanece como auxiliar genérico de git, não mais exigido pelo protocolo de subagentes. Arquivos materializados em `templates/_references/superpowers-summary/` e copiados pelo bootstrap.

### 3.1 Schema obrigatório do sumário

Todo `<X>-200tok.md` tem header padronizado:

```markdown
---
source_skill: superpowers:<X>
source_version: <semver da skill upstream>
summarized_at: <ISO 8601 date>
target_tokens: 200
actual_tokens: <int>   # validado em CI ≤250
---

# <Skill X> — sumário 200tok

## Quando usar
<1 parágrafo>

## Passos canônicos
1. ...
2. ...

## Sinais de "invoque skill formal"
- <gatilho 1>
- <gatilho 2>
```

CI valida `actual_tokens ≤ 250` (margem de 25% sobre alvo).

---

## 4. Sincronização vs upstream

Sumários são **snapshots**. Quando a skill upstream muda no plugin `superpowers`, o sumário fica desatualizado. Mitigação:

1. **Header `source_version`:** todo sumário declara a versão da skill upstream da qual foi sumarizado.
2. **Wave 8 da reescrita (futura):** agente revisor lê diff entre `source_version` declarado e versão atual da skill upstream; gera task de update se houver mudança semântica relevante.
3. **Drift policy:** sumário com >2 versões de defasagem dispara warning no bootstrap (`scripts/check-runtime.sh` checa via metadados de `~/.claude/plugins/superpowers/`).

A skill `xp-icm-workflow` **não** sincroniza automaticamente — sync é decisão manual do mantenedor.

---

## 5. Escape hatch — invocação real da skill formal

Quando o sumário 200tok é **insuficiente** para a complexidade do que a sessão está fazendo, a sessão pode invocar a skill formal via `Skill({skill: "superpowers:<X>"})`. Casos típicos:

- Discovery (estágio 01) com domínio inédito — sumário de `brainstorming` não cobre nuance do problema.
- Bug na fase 04 que sumário de `systematic-debugging` não desbloqueia.
- Review (estágio 06) com feedback denso onde `receiving-code-review` cru ajuda mais do que sumário.

### 5.1 Protocolo obrigatório

Sessão que invoca skill formal **DEVE** registrar em L1 `history`:

```yaml
- at: "<ISO 8601 UTC>"
  event: "skill_escape_hatch"
  skill: "superpowers:<X>"
  stage: "<NN>"
  reason: "<1-2 frases sobre por que o sumário não bastou>"
  outcome: "resolved" | "escalated_to_human"
```

Sem o registro, escape hatch é silencioso e quebra audit. Pre-commit hook valida que commits de sessão com `skill_escape_hatch` no diff têm prefixo `workspace:` ou `feedback:`.

### 5.2 Rate limit informal

Se um workspace tem ≥3 `skill_escape_hatch` para a **mesma skill**, é sinal de que o sumário 200tok está mal calibrado. Disparar tarefa de revisão do sumário (Wave 8) ou escalar para mantenedor da skill `xp-icm-workflow`.

---

## 6. Resolução de conflito superpowers ↔ ICM

Quando uma instrução do sumário superpowers conflita com regra do ICM (L0/L1/L2 do workspace):

1. **L0/L1/L2 vencem.** Skill é layer 4 na priority order de `SKILL.md` §Instruction Priority.
2. **Sessão registra divergência** em comentário no output do estágio (não bloqueia).
3. **Se conflito é estrutural** (ex: skill diz "leia src/", L2 diz "não leia src/"), abrir tarefa de revisão do sumário — provável bug de tradução.

---

## 7. Manutenção dos sumários

Para criar/atualizar um sumário 200tok, ver `references/extending-skill.md` §"Adding a superpower summary". Resumo do fluxo:

1. Ler skill upstream em `~/.claude/plugins/superpowers/skills/<X>/SKILL.md`.
2. Sumarizar em ≤250 tokens com schema §3.1.
3. Atualizar `source_version` para versão atual.
4. Adicionar entry em `tests/unit/test_summary_format.py` (verifica schema + tokens).
5. Commit no skill repo (não no workspace de usuário).

---

## 8. Referências cruzadas

| Doc | Conteúdo |
|---|---|
| `references/stage-templates.md` §11 | Mapeamento estágio ↔ skill canônico (autoritativo) |
| `references/extending-skill.md` | Como adicionar/atualizar sumários |
| `references/changelog.md` | Histórico de versão do mapping |
| `references/v2.4-snapshot/superpowers-mapping.md` | Versão anterior (referência histórica) |
| `templates/_references/superpowers-summary/` | Templates dos 11 sumários |
| `SKILL.md` §Instruction Priority | Priority order completa (1-5) |
