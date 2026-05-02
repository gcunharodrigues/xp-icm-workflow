# Design System — DESIGN.md format (v3.7.2)

> **Versão:** v3.7.2
> **Skill:** `xp-icm-workflow`
> **Aplica quando:** profile efetivo tem `design_system_required: True`
> (atualmente: `app_web_frontend` e `fullstack`).
> **Path canônico:** `<project_root>/.icm-main/DESIGN.md` (base branch,
> persistente cross-iteration via worktree v3.4.0).
> **Complementa:** `references/preview-loop-protocol.md` — DESIGN.md fornece
> tokens; preview loop fornece o ciclo build-iterate visual que consome esses
> tokens em telas reais com hot-reload.

## Por que DESIGN.md e não outro formato

ICM adota o formato **DESIGN.md** definido pela
[spec do Google Stitch](https://stitch.withgoogle.com/docs/design-md/overview/).
Razões:

1. **Plain markdown + YAML frontmatter** — LLM lê direto, sem tooling
   especial. Subagente em fase 04 lê via `Read tool`, zero ceremony.
2. **Spec aberta + comunidade** — 69 exemplos prontos em
   [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md)
   (airbnb, apple, claude, figma, framer, ferrari, etc.).
3. **File-based ≡ filosofia ICM** — vive ao lado dos ADRs em
   `<project_root>/.icm-main/`. Mesmo padrão de escrita (worktree-mediated
   commits em base branch).
4. **Schema converte trivialmente** pra `tokens.json` (W3C DTCG), Figma
   variables, Tailwind theme config, shadcn/ui theme.

## Estrutura canônica do arquivo

```markdown
---
version: alpha
name: <Brand name>
description: <opcional, 1-2 frases>

colors:
  primary: "#1A1C1E"
  secondary: "#6C7278"
  tertiary: "#B8422E"
  neutral: "#F7F5F2"
  # Estados semânticos opcionais:
  # surface, on-surface, error, on-error, etc.

typography:
  display-lg:
    fontFamily: <font>
    fontSize: <Dimension>
    fontWeight: <number>
    lineHeight: <Dimension|number>
    letterSpacing: <Dimension>
  headline-lg: { ... }
  body-md: { ... }
  label-sm: { ... }
  # Geralmente 9-15 níveis nomeados (display/headline/body/label/caption × sm/md/lg)

rounded:
  sm: 4px
  md: 8px
  lg: 16px
  full: 9999px

spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px

components:
  # Composite tokens com refs cross-token via {path.to.token}
  button:
    bg: "{colors.primary}"
    fg: "#ffffff"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
---

## Overview
<Brand personality, target audience, emotional response. Foundational
context pra agente fazer decisões high-level quando token específico
não cobre.>

## Colors
<Paleta + rationale por cor, mapeando palette description → semantic role>

## Typography
<Escala 9-15 níveis com role declarado por nível>

## Layout
<Grid system, breakpoints, container max-widths>

## Elevation & Depth
<Shadow scale, z-index layers>

## Shapes
<Border radius, shape language (sharp / rounded / pill / organic)>

## Components
<Anatomia por componente importante: button, input, card, modal, navbar, etc.>

## Do's and Don'ts
<Patterns to use vs anti-patterns to avoid>
```

Section order é canônica: omitir seção é OK; reordenar não é.

## 3-layer token architecture (princípio canônico)

Stage 02 designer estrutura tokens em três camadas hierárquicas:

```
Primitive (raw values) — colors.gray-900, colors.blue-600, spacing.16
       ↓
Semantic (purpose aliases) — colors.primary, colors.text-default, spacing.md
       ↓
Component (component-specific) — button.bg, card.padding, input.border
```

Exemplo CSS resultante:

```css
/* Primitive */
--color-blue-600: #2563EB;
--spacing-16: 16px;

/* Semantic — referencia primitive via {colors.blue-600} */
--color-primary: var(--color-blue-600);
--spacing-md: var(--spacing-16);

/* Component — referencia semantic */
--button-bg: var(--color-primary);
--button-padding: var(--spacing-md);
```

Token reference syntax DESIGN.md: `"{colors.primary}"`. Conversão pra
CSS variables, Tailwind config, ou Figma variables é determinística.

## Component spec table (template)

Stage 02 plan.md inclui spec por componente não-trivial usando este
template. Cobre 4 estados visuais + permite identificar gaps de design.

| Property | Default | Hover | Active | Disabled |
|----------|---------|-------|--------|----------|
| Background | `{colors.primary}` | `{colors.primary-dark}` | `{colors.primary-darker}` | `{colors.muted}` |
| Text | `#ffffff` | `#ffffff` | `#ffffff` | `{colors.muted-fg}` |
| Border | none | none | none | `{colors.muted-border}` |
| Shadow | `{elevation.sm}` | `{elevation.md}` | none | none |

Subagente em fase 04 valida que implementação cobre os 4 estados ao
escrever component tests.

## Fluxo por stage ICM

| Stage | Ação |
|---|---|
| **00 recon** | Detecta se DESIGN.md já existe em `.icm-main/`. Reporta presença/ausência em `recon-report.md`. Se existe: stage 02 atualiza incrementalmente. Se ausente: stage 02 cria do zero. |
| **01 discovery** | Brand voice, target audience, emotional tone emergem da clarificação humana. Não escreve DESIGN.md ainda — apenas captura inputs em `discovery.md` que stage 02 usará pra preencher seção `## Overview`. |
| **02 design** | **Stage onde DESIGN.md é criado/atualizado.** Process step novo (apenas profiles `app_web_frontend` + `fullstack`). Ver "Stage 02 process" abaixo. |
| **03 wave_planner** | Tasks com files frontend ganham flag `requires_design_system: true` no plan.md (consumido pelo lead em fase 04). |
| **04 implementation_waves** | Lead injeta DESIGN.md no canal 2 do prompt do subagente quando task tem flag `requires_design_system`. Subagente lê tokens + escreve código respeitando refs. |
| **05 verification** | `visual_regression` (production tier) audita aderência. Sample-check: 3 componentes implementados batem tokens declarados. |
| **06 review** | Dimensão `conventions` audita aderência aos tokens (não hardcoded values quando token existe). |
| **07 merge** | Mudanças em DESIGN.md vão junto no merge (commit em base via `.icm-main/`). |
| **08 feedback intake** | Iteration nova lê DESIGN.md atual antes de propor mudanças visuais. |

## Stage 02 process — criar/atualizar DESIGN.md

Após reading da seção `## Overview` desejada (de discovery.md) e tokens
existentes (se brownfield), stage 02 designer apresenta menu A/B/C ao
humano:

```
## Design System — escolha ponto de partida

A) **Criar do zero** — designer propõe tokens iniciais baseado em
   brand voice + audience capturados em discovery. Depois iteração
   humana refinará.

B) **Inspirar em exemplo** — escolha brand de referência da galeria
   awesome-design-md (airbnb, apple, claude, figma, framer, etc).
   Designer adapta tokens pra novo projeto preservando vibe.

C) **Extrair de URL existente** — humano fornece URL de site
   referência. Designer instrui rodar `npx designlang <url>`
   externamente e cola output base relevante. Designer adapta.

Aguardando resposta humana.
```

Após escolha:

1. Designer escreve/atualiza `<project_root>/.icm-main/DESIGN.md`
   seguindo schema canônico (YAML frontmatter + section order).
2. Commit em base branch via worktree:
   ```bash
   cd <project_root>/.icm-main
   git add DESIGN.md
   git commit -m "design: <slug-do-workspace> — design system v<N>"
   cd <project_root>
   ```
3. Plan.md cita componentes não-triviais com tabela component spec
   (Default/Hover/Active/Disabled) — refs aos tokens declarados em DESIGN.md.
4. Stage 02 wave_planner consumirá flag `requires_design_system: true`
   em tasks com files frontend.

## Stage 04 canal 2 — DESIGN.md no prompt do subagente

Lead em fase 04, ao spawnar subagente pra task frontend, injeta no canal 2:

```
## Design System (DESIGN.md fonte de verdade)

Ler ANTES de escrever código:
  Read <project_root>/.icm-main/DESIGN.md

Tokens disponíveis (seções relevantes pra essa task):
- colors.primary, colors.secondary, colors.tertiary
- typography.body-md, typography.label-sm
- spacing.md, spacing.lg
- components.button (se aplica)

Regra:
- NÃO hardcoded values quando token existe.
- Usar refs `{colors.primary}` ao invés de `#1A1C1E` literal.
- Para componentes novos, propor entry em `components` section da DESIGN.md
  via stop point `design_system_drift`.
```

Lead pré-cozinha — subagente NÃO lê DESIGN.md cru integralmente; recebe
subset relevante (tokens + components section relacionada à task).

## Galeria de referência

[VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md):
69 DESIGN.md prontos extraídos de sites populares. Stage 02 designer pode
sugerir como ponto de partida (Caso B do menu).

Brands disponíveis incluem: airbnb, airtable, apple, bmw, cal, claude,
clay, clickhouse, cohere, coinbase, composio, cursor, elevenlabs, expo,
ferrari, figma, framer, hashicorp, ibm, intercom, e mais.

## Tool externo opcional — designlang

Para Caso C (extrair de URL), humano roda externamente:

```bash
npx designlang <url>           # gera 17 files de output
npx designlang <url> --dark    # captura também dark mode
npx designlang <url> --depth 3 # crawl multi-page pra consistência
```

Output em `./design-extract-output/` inclui:
- `*-design-language.md` — markdown 19-section pronto pra LLM
- `*-design-tokens.json` — DTCG W3C format
- `*-tailwind.config.js`, `*-shadcn-theme.css`

Designer ICM lê o markdown gerado, extrai tokens relevantes, adapta pra
DESIGN.md do projeto. designlang **não é deps** da skill — é tool externa
opcional que humano roda quando útil.

Doc: https://github.com/Manavarya09/design-extract

## Escape hatch — ui-ux-pro-max-skill

Para casos onde ICM design needs profundidade extra além do DESIGN.md
spec, humano pode invocar a skill paralela `ui-ux-pro-max:ui-ux-pro-max`
manualmente. Cobre:

- 161 reasoning rules + 99 UX guidelines
- 67 UI styles (glassmorphism, claymorphism, minimalism, brutalism,
  neumorphism, bento grid, etc.)
- 161 color palettes + 57 font pairings
- 25 chart types
- 10 stacks (React, Next.js, Vue, Svelte, SwiftUI, RN, Flutter,
  Tailwind, shadcn/ui, HTML/CSS)

**Quando invocar:**

- Greenfield sem referência visual prévia (antes de stage 02 popular DESIGN.md)
- Slides/decks/banners — out-of-scope ICM, ui-ux-pro-max tem `slides`
  sub-skill com 8 CSVs de strategy
- Stuck em decisão de design no stage 02 — ICM menu A/B/C limitado;
  ui-ux-pro-max expande framework de decisão
- Brand exploration antes de bootstrar workspace

**Quando NÃO invocar:**

- Mid-stage 04 (implementação). Lead lendo 161 rules durante TDD = ruído.
  Subagentes recebem DESIGN.md (canônico do projeto) no canal 2, não
  ui-ux-pro-max.
- Refinamento de tokens já existentes em DESIGN.md — stage 02 ICM cuida.
- Stage 06 review — dimensão `conventions` da ICM já valida aderência.

**Boundary:** ICM governa o ciclo do projeto. ui-ux-pro-max é tool
consultivo paralelo. Invocação humana explícita ("ok, dispara
ui-ux-pro-max"), nunca auto-invocação dentro de stage ICM. Igual padrão
`superpowers:*` que ICM já adotou em v3.3.0.

## Conversão pra outras representações

DESIGN.md frontmatter converte determinísticamente:

| Destino | Conversão |
|---|---|
| W3C DTCG `tokens.json` | `colors`, `typography`, etc. → `$value`/`$type` schema |
| Figma variables | YAML keys → variables com mesmo nome |
| Tailwind `theme.extend` | `colors`, `spacing`, `borderRadius`, `fontFamily`, etc. |
| shadcn/ui CSS vars | `colors` → `--primary`, `--secondary`, etc. via `oklch()` ou hex |
| CSS custom properties | Direct mapping com `--<token-path>` |

Se projeto requer dual-source (DESIGN.md + tokens.json sincronizados),
documentar em ADR e escolher fonte primária. Recomendação: **DESIGN.md
é a fonte de verdade**; demais formatos são gerados.

## Anti-patterns

### Hardcoded values quando token existe

```diff
- background: #1A1C1E;
+ background: var(--color-primary);
```

Code review (stage 06) sinaliza. Subagente em fase 04 já é instruído
no canal 2.

### DESIGN.md fora-do-padrão

Section order, schema YAML keys, token reference syntax `{path.to.token}`
seguem spec Google rigidamente. Custom keys → fragmenta interop com
exemplos awesome-design-md e tools (Figma, Tailwind generators).

### Componentes só em código, não em DESIGN.md

Cada componente reusável merece entry na seção `## Components` da
DESIGN.md com anatomia + estados (Default/Hover/Active/Disabled). Sem
isso, onboarding de devs novos perde contexto.

### Designer alterando código direto

Stage 02 designer SÓ escreve em DESIGN.md (e plan.md). NÃO toca
`src/`, `tests/` — isso é fase 04. Pre-commit hook do workspace branch
rejeita.

## Build-iterate visual loop (v3.6.0)

DESIGN.md tokens cobrem fonte de verdade declarativa. Mas frontend NÃO é
construído via mockup-first em canvas externo (Figma/Penpot exigem trabalho
manual em GUI ou plano pago). Em vez disso, ICM v3.6.0 adota loop
**code-first**: agente gera UI com mock data, humano olha em browser real,
dá feedback verbal/visual/screenshot, agente itera via hot-reload.

Doc canônico: `references/preview-loop-protocol.md`. Cobre:

- Dev server lifecycle (start entry stage 04, kill exit).
- Mock data tier-based (fixtures → MSW+Faker → MSW+Faker+Zod).
- Chrome CDP live integration (`--remote-debugging-port=9222`).
- Verificação uniforme (`tsc` cada edit + lint/Playwright wave-end).
- Preview pages (`preview/<component>` ao invés de Storybook).
- Feedback combo livre (texto, screenshot anotado, URL, HTML).
- Iteração visual sem cap (humano fecha quando OK).
- Design system cascade threshold (≤5 cascata direto, >5 stop point).
- Multi-tela replay sob pedido + auto-detect keywords.
- Recovery wizard tipos `DEV_SERVER_ORPHAN` + `CDP_DISCONNECTED`.

DESIGN.md continua fonte canônica de tokens. Preview loop é o ciclo de
execução que consome esses tokens em telas reais. Os dois docs operam
juntos: design-system.md = O QUÊ; preview-loop-protocol.md = COMO ITERAR.

## Referências cruzadas

- [Spec DESIGN.md (Google Stitch)](https://stitch.withgoogle.com/docs/design-md/overview/)
- [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) — 69 exemplos
- [Manavarya09/design-extract (designlang)](https://github.com/Manavarya09/design-extract) — extração de URL
- [W3C Design Token JSON spec](https://www.designtokens.org/tr/2025.10/format/)
- `references/preview-loop-protocol.md` — ciclo build-iterate visual (v3.6.0)
- `references/worktree-model.md` — modelo de escritas em base branch via `.icm-main/`
- `templates/_config/profile-matrix.md` — `design_system_required` por profile
- `references/4-block-contract-template.md` — schema de tasks no plan.md
