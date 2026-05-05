# Preview Loop Protocol — build-iterate visual (v3.10.0)

> **Versão:** v3.10.0 (preview loop introduzido em v3.6.0; v3.7.0 migrou
> dev-server PID file → runtime-registry, ver `runtime-cleanup-protocol.md`)
> **Skill:** `xp-icm-workflow`
> **Aplica quando:** profile efetivo tem `preview_loop_enabled: True`
> (atualmente: `app_web_frontend` e `fullstack`).

## Filosofia

Frontend NÃO é construído via mockup-first em canvas tool (Figma/Penpot).
É construído **code-first**: agente gera UI com mock data, humano olha
em browser real, dá feedback verbal/visual, agente itera. Hot-reload
nativo do dev server elimina necessidade de canvas intermediário.

## Quando NÃO usar este protocol

- Backend puro (`app_web_backend` sem frontend embutido).
- CLI tools, libraries, ML pipelines, agents IA puros.
- Profile experimental tier que opta por iteração ad-hoc (override
  `preview_loop_enabled: false`).

## Stack canônico

| Componente      | Default                                              | Override                  |
|-----------------|------------------------------------------------------|---------------------------|
| Build tool      | detectado (Vite, Next.js, Astro, SvelteKit)          | profile override          |
| Hot reload      | nativo do build tool                                  | n/a                       |
| Mock data       | tier-based (ver tabela abaixo)                        | override em plan.md       |
| CDP browser     | Chrome com `--remote-debugging-port=9222`             | n/a                       |
| Preview pages   | `preview/` subpasta excluída do build production       | convenção                 |
| Verificação     | `tsc --noEmit` cada edit + lint/Playwright wave-end   | uniforme                  |

## Mock data strategy (tier-based)

| Tier         | Strategy           | Implementação                                                            |
|--------------|--------------------|--------------------------------------------------------------------------|
| experimental | `fixtures`         | JSON estáticos em `fixtures/`, import direto no componente               |
| tool         | `fixtures`         | mesmo experimental                                                       |
| development  | `msw_faker`        | MSW Service Worker + Faker.js + handlers em `mocks/handlers.ts`          |
| production   | `msw_faker_zod`    | MSW + Faker + schema Zod validado em `mocks/schema.ts`                   |

### Por que tier-based

- Profile experimental valoriza velocidade > robustez. Fixtures JSON =
  zero setup, edita e roda.
- Production exige contrato API explícito (Zod schema vira fonte pra
  backend real depois).
- MSW intercepta `fetch`/`axios` real → componente fala HTTP do dia 1,
  refactor zero quando backend liga.

### Schema design (stage 02)

Stage 02 designa schema mock data quando tier ≥ development:

```typescript
// mocks/schema.ts
import { z } from 'zod';

export const ProductSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1).max(120),
  price: z.number().positive(),
  // ...
});

export type Product = z.infer<typeof ProductSchema>;
```

Stage 04 implementa MSW handlers consumindo schema:

```typescript
// mocks/handlers.ts
import { http, HttpResponse } from 'msw';
import { faker } from '@faker-js/faker';
import { ProductSchema } from './schema';

export const handlers = [
  http.get('/api/products', () => {
    const products = Array.from({ length: 50 }, () => ({
      id: faker.string.uuid(),
      name: faker.commerce.productName(),
      price: parseFloat(faker.commerce.price()),
    }));
    return HttpResponse.json(products.map(p => ProductSchema.parse(p)));
  }),
];
```

## Dev server lifecycle

Decisão 1: agente starta dev server ao entrar stage 04, mata ao sair.
Cada nova sessão rebota do zero.

- **Stage 04 entry hook:** detecta package manager (npm/pnpm/yarn/bun)
  via lockfile, starta `<pm> run dev` em background.
- **PID salvo em** `.icm-main/.dev-server.pid` (worktree base branch
  v3.4.0). Sessão futura lê PID pra detectar orphan.
- **Hot-reload nativo do build tool** refresca automaticamente após
  cada edit. Agente NÃO mexe em refresh manual.
- **Stage 04 exit hook:** lê PID, mata processo (`kill <pid>` POSIX,
  `taskkill /PID <pid> /F` Windows), remove arquivo PID.
- **Recovery wizard tipo `DEV_SERVER_ORPHAN`:** PID file existe mas
  processo morto. Plan A: apaga PID, registra warning, deixa próximo
  stage 04 entry rebotar limpo.

### Comandos por package manager

| PM   | Detector             | Start         |
|------|----------------------|---------------|
| npm  | `package-lock.json`  | `npm run dev` |
| pnpm | `pnpm-lock.yaml`     | `pnpm dev`    |
| yarn | `yarn.lock`          | `yarn dev`    |
| bun  | `bun.lockb`/`bun.lock` | `bun dev`   |

Se múltiplos lockfiles presentes: prioridade `bun > pnpm > yarn > npm`
(ordem do mais recente/específico). Recon (stage 00) reporta em
`recon-report.md`.

## CDP browser integration

Decisão 4: agente lê URL + DOM atual real-time via Chrome DevTools
Protocol. Zero atrito pro humano (ele só navega normalmente).

### Helper scripts

Lead em fase 04 imprime hyperlink pro helper:

**Windows** — `templates/.claude/scripts/launch-chrome-cdp.bat`:
```batch
@echo off
set PROFILE_DIR=%CD%\.icm-chrome-profile
set CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" set CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe
"%CHROME%" --remote-debugging-port=9222 --user-data-dir="%PROFILE_DIR%" http://localhost:3000
```

**POSIX** — `templates/.claude/scripts/launch-chrome-cdp.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
PROFILE_DIR="$(pwd)/.icm-chrome-profile"
CHROME="${CHROME:-}"
if [ -z "$CHROME" ]; then
  for cand in google-chrome chromium chromium-browser \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; do
    if command -v "$cand" >/dev/null 2>&1 || [ -x "$cand" ]; then
      CHROME="$cand"; break
    fi
  done
fi
"$CHROME" --remote-debugging-port=9222 --user-data-dir="$PROFILE_DIR" http://localhost:3000 &
```

`.icm-chrome-profile/` em CWD do projeto isola sessão (não mistura com
seu Chrome principal — extensões, cookies, logins separados).

### MCP integration

Agente conecta via Playwright MCP modo `connect_over_cdp` apontando
pra `http://localhost:9222`. Tools relevantes:

- `browser_navigate` — agente NÃO usa em CDP mode (humano dirige).
- `browser_snapshot` — accessibility tree do tab ativo.
- `browser_evaluate` — `window.location.href`, `document.title`.
- `browser_console_messages` — captura logs do app.

### Scope de leitura

Whitelist hardcoded: agente só inspeciona abas com URL matching
`localhost:*` ou `127.0.0.1:*`. Outras abas (Gmail, GitHub, etc.)
ignoradas mesmo conectadas no mesmo Chrome.

### Fallback

CDP indisponível (Chrome fechado, porta ocupada, helper falhou) →
degrada gracefully:

1. Stage 02 mantém `output/routes.md` como backup map (rota → componente
   → fixture).
2. Agente pergunta URL ao humano quando ambíguo.
3. Recovery wizard `CDP_DISCONNECTED` detecta `.icm-chrome-profile/`
   sem listener em :9222, sugere relaunch.

## Verificação uniforme

Decisão 5: política única, não tier-based.

- **Cada Edit em arquivo `.ts/.tsx/.vue/.svelte`:** agente roda
  `tsc --noEmit` (~1s). Falha = NÃO declara task done, fix imediato.
- **Wave end:** lint completo + Playwright headless sample-check
  (1 click por componente novo, valida render sem crash).
- **Sob pedido:** humano fala "testa" / "ok valida" → agente roda full
  suite + e2e relevantes.
- **Sempre:** Vite/Next mostra erros de compile na tela do humano
  direto via overlay nativo. Humano vê quebra antes do agente em
  muitos casos.

## Preview pages convention

Decisão 6: componentes ganham preview page ao invés de Storybook.

### Rationale

- Zero deps novas (Storybook adiciona ~50 deps + config).
- Hot-reload nativo do build tool (Storybook tem próprio HMR mais lento).
- Stack já familiar pro agente (Next/Vite que está rodando).
- Extraível pra Storybook real depois sem perda.

### Convenção path

| Build tool   | Path                                          |
|--------------|-----------------------------------------------|
| Next.js (app router) | `app/preview/<component>/page.tsx`     |
| Next.js (pages router) | `pages/preview/<component>.tsx`      |
| Vite + React | `src/preview/<component>.tsx` + route registrada |
| SvelteKit    | `src/routes/preview/<component>/+page.svelte`  |
| Astro        | `src/pages/preview/<component>.astro`           |

### Estrutura padrão

```tsx
// app/preview/button/page.tsx
import { Button } from '@/components/Button';

export default function ButtonPreview() {
  return (
    <div className="grid gap-8 p-8">
      <section>
        <h2>Default</h2>
        <Button>Click me</Button>
      </section>
      <section>
        <h2>Hover (force via DevTools)</h2>
        <Button>Hover me</Button>
      </section>
      <section>
        <h2>Disabled</h2>
        <Button disabled>Disabled</Button>
      </section>
      <section>
        <h2>Loading</h2>
        <Button loading>Loading</Button>
      </section>
    </div>
  );
}
```

Cobertura mínima: 4 estados (Default/Hover/Active/Disabled). Estados
extras (Loading, Error, Empty) conforme aplicável ao componente.

### Production exclusion

Path `preview/` excluído do build production via env check:

**Next.js** — `middleware.ts`:
```typescript
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(req: NextRequest) {
  if (
    process.env.NODE_ENV === 'production' &&
    req.nextUrl.pathname.startsWith('/preview')
  ) {
    return NextResponse.rewrite(new URL('/404', req.url));
  }
  return NextResponse.next();
}
```

**Vite** — `vite.config.ts`:
```typescript
export default defineConfig(({ mode }) => ({
  build: {
    rollupOptions: {
      external: mode === 'production' ? [/.*\/preview\/.*/] : [],
    },
  },
}));
```

## Feedback comunicação

Decisão 3: agente aceita combo livre, sem padronização forçada.

- Texto puro: `"botão login direita, mais espaço entre cards"`
- Screenshot anotado: humano cola PNG de Snipping Tool / ShareX /
  Greenshot
- URL + descrição: `"no /dashboard o gráfico cortou direita"`
- DOM outerHTML: `"esse <div class=\"card\">"`
- Combo qualquer

Agente lê PNG via vision nativa (zero MCP). Sem padronização de tool
de screenshot — humano usa o que prefere.

### Stop point `feedback_ambiguous`

Quando confidence baixa (descrição vaga, screenshot sem anotação clara,
contradição entre texto e visual):
- Agente NÃO mexe especulando.
- Pausa, escreve menu A/B/C com interpretações candidatas.
- Atualiza L1 `status: BLOCKED_STOP_POINT`.
- Aguarda humano desambiguar.

### Kickoff priming stage 04

Lead em fase 04 imprime no console no entry:

```
🎨 Preview loop ativo — workspace <NNN-slug>

Dev server: http://localhost:3000 (PID <pid>)
Chrome CDP: launch via scripts/launch-chrome-cdp.{bat,sh}
Preview pages: localhost:3000/preview/<component>

Pra dar feedback visual, qualquer combo funciona:
  - Texto: "botão direita, mais padding"
  - Print anotado (Win+Shift+S Snipping ou ShareX https://getsharex.com): cola PNG
  - URL: "/checkout, header torto"
  - HTML: cola outerHTML do elemento problemático

Se ambíguo, eu pergunto antes de mexer (stop point feedback_ambiguous).
```

## Iteração visual

Decisão 8: sem cap, sem audit em L1.

Itera até humano falar `"ok pronto"` / `"aprovado"`. Trade-off declarado:
velocidade > rastreabilidade. Loops longos viram responsabilidade do
humano.

Wave-summary do stage 04 menciona se a wave fechou em convergência
visual ou ainda tem refinamento pendente — auditável fora de L1
formal.

## Design system cascade

Decisão 9: cascata via DESIGN.md default; threshold 5 confirma.

Mudanças em token (cor, spacing, typography) seguem cascata via
`DESIGN.md` → CSS vars:

1. Agente recebe pedido (`"muda primary pra verde"`).
2. Faz Grep `var(--color-primary)` ou `{colors.primary}` no codebase.
3. Conta arquivos afetados (= componentes que usam token).
4. **Se ≤ 5 afetados:** aplica direto, registra em commit message.
   ```
   workspace 042: cascade colors.primary verde — 3 components affected
   ```
5. **Se > 5 afetados:** stop point `design_system_cascade`, menu:
   - **A) cascata global** — propaga a todos via DESIGN.md token edit.
   - **B) limita escopo** — só componente atual (override local;
     DESIGN.md fica fonte aspiracional registrada em
     `out-of-scope/<workspace>.md`).
   - **C) cancela** — reconsidera mudança.

Threshold 5 é heurístico, calibrável via
`_config/design-system-policy.yaml` (`design_cascade_threshold: <int>`).

## Multi-tela / fluxo navegacional

Decisão 10: CDP só URL atual default; replay multi-tela sob pedido +
auto-detect keywords.

CDP live (decisão 4) lê URL atual em tempo real. Suficiente pra 90% dos
casos (feedback de tela única).

### Replay multi-tela

Quando feedback envolve fluxo (ex: `"checkout → pagamento → confirmação
tem problema na transição"`):

- **Default:** agente NÃO ativa replay automaticamente.
- **Auto-detect keywords:** se feedback humano menciona `transição`,
  `fluxo`, `multi-step`, `navegação`, `flow`, agente sugere ativar
  replay antes de mexer.
- **Sob pedido humano:** `"vou mostrar fluxo"` → agente injeta breadcrumb
  logger temporário em `router.beforeEach` (Vue) / `useEffect` em layout
  root (Next/React) / `beforeNavigate` (Svelte).
- **Lê via CDP** `Runtime.consoleAPICalled`.
- **Reconstrói sequência** de URLs visitadas + timing.
- **Replay desligado** ao fim da iteração (logger removido do código —
  commit `chore: remove temp breadcrumb logger`).

## Fluxo por stage ICM

| Stage | Ação |
|-------|------|
| **00 recon** | Detecta stack frontend (Next/Vite/Astro/SvelteKit). Reporta em `recon-report.md`. Verifica `package.json` por dev script. |
| **01 discovery** | Brand voice, tone, target audience. Captura inputs pra Overview do DESIGN.md (stage 02). |
| **02 design** | Cria/atualiza DESIGN.md (tokens). Designa schema mock data (Zod) se tier ≥ development. Plan.md inclui flag `requires_design_system` + `requires_preview_page` por task. |
| **03 wave_planner** | Tasks com files frontend ganham flags propagadas. Cap subagentes respeita tier. |
| **04 implementation_waves** | **Loop principal.** Entry hook starta dev server, kickoff priming, helper CDP launch. Cada subagente implementa task + preview page + MSW handler (se aplicável). Lead orquestra feedback humano via CDP. Hot-reload visual após cada edit. Sob pedido: full lint + Playwright sample. Exit hook mata dev server. |
| **05 verification** | Visual regression (production tier) compara screenshots vs baseline. Sample-check 3 componentes contra DESIGN.md tokens. |
| **06 review** | Dimensão `conventions` audita aderência aos tokens (não hardcoded values). Auditor revê preview pages + MSW schema validity. |
| **07 merge** | Dev server + CDP profile dir limpos. Mudanças em DESIGN.md merged junto. |
| **08 feedback intake** | Iteração nova lê DESIGN.md atual + route map antes de propor mudanças visuais. |

## Anti-patterns

### Mockup-first em canvas tool externa
Tradeoff Figma/Penpot detalhado em `design-system.md`. Se precisa: profile
flag opcional `figma_plugin_enabled` (não default, não documentado neste
protocol).

### Subagente sem preview page
Stage 04 task com file frontend de componente reusável SEM
`preview/<component>` correspondente = wave-reviewer flagra (issue:
"preview page ausente").

### Mock data inline no componente
```tsx
// ❌ ANTI
const products = [{ id: 1, name: "test" }, { id: 2, name: "x" }];

// ✅ via fixture (experimental/tool)
import products from '@/fixtures/products.json';

// ✅ via MSW (development+) — componente chama fetch real
const products = await fetch('/api/products').then(r => r.json());
```

### Hardcoded color/spacing quando token existe
Mesma regra de `design-system.md`. Reforço no preview loop: cada edit
roda Grep contra DESIGN.md tokens — match literal sem ref → warning.

### Iteração sem fim sem fechamento humano
Decisão 8 declara: humano responsável. Mas se workspace termina stage
04 sem `wave-summary.md` mencionando convergência visual = wave-reviewer
flagra como débito não-bloqueante.

### Dev server PID órfão
Recovery wizard `DEV_SERVER_ORPHAN` detecta. Skill exit hook DEVE
matar processo + apagar PID. Sair sem cleanup = próxima sessão entra
em estado ambíguo.

## Recovery wizard tipos novos

| Code                  | Detecção                                                          | Plan A (preserve)                                |
|-----------------------|-------------------------------------------------------------------|--------------------------------------------------|
| `DEV_SERVER_ORPHAN`   | `.icm-main/.dev-server.pid` existe; processo morto                | apaga PID file, registra warning history          |
| `CDP_DISCONNECTED`    | `.icm-chrome-profile/` existe; nenhum Chrome listening em :9222    | sugere helper script relaunch (não mata profile)  |

Ambos `severity: warning` (não bloqueia trabalho — agente degrada
gracefully via fallbacks: route map + screenshot manual).

## Profile flags consolidadas

```yaml
# profile-effective.yaml (gerado por profile-merge.py)
preview_loop_enabled: true              # default true em frontend/fullstack
mock_data_strategy: msw_faker_zod       # tier-based: fixtures|msw_faker|msw_faker_zod
cdp_live_enabled: true                  # default true; opt-out via override
visual_iter_cap: null                   # decisão 8: sem cap
design_cascade_threshold: 5             # decisão 9
preview_pages_path: preview/            # convenção
```

## Referências cruzadas

- `references/design-system.md` — DESIGN.md format Google Stitch spec
- `references/wave-execution-protocol.md` — pipeline 12-passos stage 04
- `references/state-machine-schema.md` — L1 schema (stop points novos)
- `scripts/recovery-wizard.py` — recovery types (DEV_SERVER_ORPHAN, CDP_DISCONNECTED)
- `templates/_config/profile-matrix.md` — `preview_loop_enabled`, `mock_data_strategy`
- [MSW docs](https://mswjs.io/) — Mock Service Worker
- [Faker.js docs](https://fakerjs.dev/) — fake data generation
- [Zod docs](https://zod.dev/) — schema validation
- [Playwright connect_over_cdp](https://playwright.dev/docs/api/class-browsertype) — CDP integration
- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/) — DOM/Runtime/Network domains
