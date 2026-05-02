# Acknowledgments

Esta skill é produto de adaptação e síntese de múltiplas fontes externas. Esta página centraliza atribuições devidas. Referências individuais seguem em cada doc adaptado em `references/`.

---

## Base teórica

### Interpretable Context Methodology (ICM)

> **VanClief, J. & McDermott, S. (2025).** "Interpretable Context Methodology: Folder Structure as Agent Architecture." arXiv:2603.16021v2.

Toda a arquitetura de 5 camadas (L0–L4), o princípio "1 estágio = 1 sessão", o modelo "filesystem-as-state" e a divisão estrutural em estágios numerados (`00_recon → 08_feedback_intake`) derivam diretamente do paper. Resumo local em [`references/icm-paper-summary.md`](references/icm-paper-summary.md).

Princípios fundadores citados pelos autores (atribuídos via paper):

- **McIlroy (Unix philosophy)** — "Make each program do one thing well." Inspira "1 stage, 1 job".
- **Parnas, D.L. (1972)** — Information hiding. Inspira camada L0/L1 imutável vs L4 mutável.
- **Liu et al. (2024)** — "Lost in the middle: How language models use long contexts." Justifica layered context loading (2-8k tokens por L2 vs 30-50k monolítico).
- **Horvitz, E. (1999)** — Mixed-initiative user interfaces. Inspira "every output is an edit surface".
- **Shneiderman, B. (1983)** — Direct manipulation. Idem.

---

## Patterns adotados de [mattpocock/skills](https://github.com/mattpocock/skills)

> Repositório: [github.com/mattpocock/skills](https://github.com/mattpocock/skills)
> Autor: Matt Pocock (@mattpocock)

Esta skill incorpora 9 patterns adaptados (v3.3.0, abril 2026). Cada arquivo adaptado declara fonte explícita no header.

| Pattern adotado | Doc local | Fonte original |
|---|---|---|
| ADR 3-criteria gate | [`references/adr-format.md`](references/adr-format.md) | `engineering/grill-with-docs/ADR-FORMAT.md` |
| AGENT-BRIEF template | [`references/agent-brief-template.md`](references/agent-brief-template.md) | `engineering/triage/AGENT-BRIEF.md` |
| Ubiquitous Language (CONTEXT format) | [`references/context-format.md`](references/context-format.md) | `engineering/grill-with-docs/CONTEXT-FORMAT.md` |
| Design It Twice / Interface Design | [`references/design-it-twice.md`](references/design-it-twice.md) | `engineering/improve-codebase-architecture/INTERFACE-DESIGN.md` |
| Diagnose 6-fase | [`references/diagnose-protocol.md`](references/diagnose-protocol.md) | `engineering/diagnose/SKILL.md` |
| OUT-OF-SCOPE knowledge base | [`references/out-of-scope-kb.md`](references/out-of-scope-kb.md) | `engineering/triage/OUT-OF-SCOPE.md` |
| HITL/AFK task types | [`references/task-types-hitl-afk.md`](references/task-types-hitl-afk.md) | `engineering/to-issues/SKILL.md` |
| Triage state machine | [`references/triage-state-machine.md`](references/triage-state-machine.md) | `engineering/triage/SKILL.md` |
| Deep modules + deletion test | [`references/deep-modules.md`](references/deep-modules.md) | `engineering/improve-codebase-architecture` |

**Adaptações:** patterns foram traduzidos pra PT-BR, integrados ao modelo de 9 estágios ICM, e calibrados pelos profiles × tiers da skill. Espírito original preservado; mecânica ajustada.

---

## Design System (frontend/fullstack profiles)

### [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md)

> Galeria de 69 exemplos de DESIGN.md tokens (cores, typography, spacing) usados como inspiração no stage 02 design quando o profile é `app_web_frontend` ou `fullstack`. Doc local: [`references/design-system.md`](references/design-system.md) seção §"Inspirar em exemplo".

### [Manavarya09/design-extract (designlang)](https://github.com/Manavarya09/design-extract)

> Ferramenta para extração de tokens design a partir de URL real. Documentado em [`references/design-system.md`](references/design-system.md) §"Extrair de URL externa" como opção `[c]` do menu de criação de DESIGN.md.

---

## Auto-QA "Akita" checklist (TDD subagent loop)

> **Inspirado nos blogposts de Fabio Akita** ([akitaonrails.com](https://www.akitaonrails.com/)).

Checklist 15-item aplicado no passo 6 do ciclo TDD canônico (cada subagente em fase 04). Doc: [`references/4-block-contract-template.md`](references/4-block-contract-template.md) §5.

Critérios consolidados de clean code, naming, abstrações justificadas, fluxo linear e auto-revisão pós-implementação derivam do corpo de trabalho de Fabio Akita publicado ao longo de duas décadas em [akitaonrails.com](https://www.akitaonrails.com/) (palestras, posts sobre Ruby on Rails, arquitetura, qualidade de código, code review e clean code aplicado em contexto brasileiro/multinacional).

A síntese específica de 15 itens nesta skill é adaptação operacional desses princípios para o ciclo TDD de subagentes ICM; espírito original e nomenclatura "Akita" preservados em homenagem à influência educacional.

---

## Ecossistema Claude Code

> [Claude Code](https://docs.claude.com/en/docs/claude-code) — CLI da Anthropic onde esta skill roda.
> [Anthropic Skills system](https://docs.claude.com/en/docs/agents/skills) — modelo de skills/SKILL.md adotado.

A skill consome ferramentas do harness Claude Code: `Read`, `Edit`, `Write`, `Glob`, `Grep`, `Bash`, `Agent` (subagentes via `Agent(isolation: "worktree")`), `Skill` (escape hatch para superpowers). Documentação dessas tools é da Anthropic.

---

## Tooling

- **Python ecosystem:** [pytest](https://pytest.org/), [Hypothesis](https://hypothesis.readthedocs.io/) (property-based testing), [PyYAML](https://pyyaml.org/), [coverage.py](https://coverage.readthedocs.io/).
- **bats** (Bash Automated Testing System): [bats-core](https://github.com/bats-core/bats-core) — usado em `tests/integration/` e `tests/e2e/` (CI-only).
- **Conventional Commits:** [conventionalcommits.org](https://www.conventionalcommits.org/) — convenção de mensagens git.
- **Semantic Versioning:** [semver.org](https://semver.org/) — esquema `MAJOR.MINOR.PATCH`.

---

## Como creditar mudanças

Se você adapta esta skill ou seus protocolos para outro projeto, mantenha a cadeia de atribuição:

1. Cite **esta skill** (`xp-icm-workflow`) + autor (@gcunharodrigues) + versão.
2. Cite **fontes upstream** desta skill quando aplicável (ex: se você reutiliza `triage-state-machine.md`, cite mattpocock/skills também).
3. Cite o **paper ICM** se você adota a metodologia de 5 camadas / 9 estágios.

Boa prática academica: declarar atribuições explícitas no `README.md` ou `ACKNOWLEDGMENTS.md` do projeto derivado.

---

## Reportar atribuição faltando

Se você identifica fonte externa não creditada nesta skill, abra issue em [github.com/gcunharodrigues/xp-icm-workflow/issues](https://github.com/gcunharodrigues/xp-icm-workflow/issues) com label `attribution-fix`. Inclua:

- Material desta skill que parece derivado.
- Fonte original (link, autor, data).
- Evidência da relação (similaridade textual, conceitual, estrutural).

Atribuições serão adicionadas em release patch.
