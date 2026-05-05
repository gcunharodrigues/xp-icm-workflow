# Preview Loop Protocol — build-iterate visual (v3.12.1)

> **Version:** v3.12.1 (preview loop introduced in v3.6.0; v3.7.0 migrated
> dev-server PID file → runtime-registry, see `runtime-cleanup-protocol.md`)
> **Skill:** `xp-icm-workflow`
> **Applies when:** effective profile has `preview_loop_enabled: True`
> (currently: `app_web_frontend` and `fullstack`).

## Philosophy

Frontend is NOT built mockup-first in a canvas tool (Figma/Penpot).
It is built **code-first**: agent generates UI with mock data, human inspects
in a real browser, gives verbal/visual feedback, agent iterates. Native hot-reload
from the dev server eliminates the need for an intermediate canvas.

## When NOT to use this protocol

- Pure backend (`app_web_backend` without embedded frontend).
- CLI tools, libraries, ML pipelines, pure IA agents.
- Experimental tier profile opting for ad-hoc iteration (override
  `preview_loop_enabled: false`).

## Canonical stack

| Component       | Default                                              | Override                  |
|-----------------|------------------------------------------------------|---------------------------|
| Build tool      | detected (Vite, Next.js, Astro, SvelteKit)           | profile override          |
| Hot reload      | native from the build tool                            | n/a                       |
| Mock data       | tier-based (see table below)                          | override in plan.md       |
| CDP browser     | Chrome with `--remote-debugging-port=9222`            | n/a                       |
| Preview pages   | `preview/` subfolder excluded from production build   | convention                |
| Verification    | `tsc --noEmit` each edit + lint/Playwright wave-end   | uniform                   |

## Mock data strategy (tier-based)

| Tier         | Strategy           | Implementation                                                            |
|--------------|--------------------|---------------------------------------------------------------------------|
| experimental | `fixtures`         | Static JSON files in `fixtures/`, imported directly in the component      |
| tool         | `fixtures`         | Same as experimental                                                      |
| development  | `msw_faker`        | MSW Service Worker + Faker.js + handlers in `mocks/handlers.ts`           |
| production   | `msw_faker_zod`    | MSW + Faker + Zod-validated schema in `mocks/schema.ts`                   |

### Why tier-based

- Experimental profile values speed over robustness. Fixture JSON =
  zero setup, edit and run.
- Production requires an explicit API contract (Zod schema becomes source for
  the real backend later).
- MSW intercepts real `fetch`/`axios` → component speaks HTTP from day 1,
  zero refactor when backend connects.

### Schema design (stage 02)

Stage 02 designs the mock data schema when tier ≥ development:

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

Stage 04 implements MSW handlers consuming the schema:

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

Decision 1: agent starts the dev server on entering stage 04, kills it on exit.
Each new session reboots from scratch.

- **Stage 04 entry hook:** detects package manager (npm/pnpm/yarn/bun)
  via lockfile, starts `<pm> run dev` in the background.
- **PID saved in** `.icm-main/.dev-server.pid` (worktree base branch
  v3.4.0). Future session reads the PID to detect an orphan.
- **Native hot-reload from the build tool** refreshes automatically after
  each edit. Agent does NOT manually trigger refresh.
- **Stage 04 exit hook:** reads PID, kills process (`kill <pid>` POSIX,
  `taskkill /PID <pid> /F` Windows), removes the PID file.
- **Recovery wizard type `DEV_SERVER_ORPHAN`:** PID file exists but
  process is dead. Plan A: delete PID, log warning, let the next
  stage 04 entry reboot clean.

### Commands per package manager

| PM   | Detector             | Start         |
|------|----------------------|---------------|
| npm  | `package-lock.json`  | `npm run dev` |
| pnpm | `pnpm-lock.yaml`     | `pnpm dev`    |
| yarn | `yarn.lock`          | `yarn dev`    |
| bun  | `bun.lockb`/`bun.lock` | `bun dev`   |

If multiple lockfiles are present: priority `bun > pnpm > yarn > npm`
(most recent/specific first). Recon (stage 00) reports this in
`recon-report.md`.

## CDP browser integration

Decision 4: agent reads the current URL + DOM in real time via Chrome DevTools
Protocol. Zero friction for the human (they just browse normally).

### Helper scripts

Lead in stage 04 prints a hyperlink to the helper:

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

`.icm-chrome-profile/` in the project CWD isolates the session (does not mix with
your main Chrome — separate extensions, cookies, logins).

### MCP integration

Agent connects via Playwright MCP in `connect_over_cdp` mode pointing
to `http://localhost:9222`. Relevant tools:

- `browser_navigate` — agent does NOT use this in CDP mode (human drives).
- `browser_snapshot` — accessibility tree of the active tab.
- `browser_evaluate` — `window.location.href`, `document.title`.
- `browser_console_messages` — captures app logs.

### Read scope

Hardcoded whitelist: agent only inspects tabs whose URL matches
`localhost:*` or `127.0.0.1:*`. Other tabs (Gmail, GitHub, etc.)
are ignored even when connected to the same Chrome.

### Fallback

CDP unavailable (Chrome closed, port occupied, helper failed) →
degrades gracefully:

1. Stage 02 keeps `output/routes.md` as a backup map (route → component
   → fixture).
2. Agent asks the human for the URL when ambiguous.
3. Recovery wizard `CDP_DISCONNECTED` detects `.icm-chrome-profile/`
   without a listener on :9222, suggests relaunching.

## Uniform verification

Decision 5: single policy, not tier-based.

- **Each Edit on a `.ts/.tsx/.vue/.svelte` file:** agent runs
  `tsc --noEmit` (~1s). Failure = task is NOT declared done, fix immediately.
- **Wave end:** full lint + Playwright headless sample-check
  (1 click per new component, validates render without crash).
- **On demand:** human says "test" / "ok validate" → agent runs full
  suite + relevant e2e.
- **Always:** Vite/Next shows compile errors on the human's screen
  directly via the native overlay. Human sees the breakage before the agent
  in many cases.

## Preview pages convention

Decision 6: components get a preview page instead of Storybook.

### Rationale

- Zero new dependencies (Storybook adds ~50 deps + config).
- Native hot-reload from the build tool (Storybook has its own slower HMR).
- Stack already familiar to the agent (Next/Vite already running).
- Extractable to real Storybook later without loss.

### Path convention

| Build tool   | Path                                          |
|--------------|-----------------------------------------------|
| Next.js (app router) | `app/preview/<component>/page.tsx`     |
| Next.js (pages router) | `pages/preview/<component>.tsx`      |
| Vite + React | `src/preview/<component>.tsx` + registered route |
| SvelteKit    | `src/routes/preview/<component>/+page.svelte`  |
| Astro        | `src/pages/preview/<component>.astro`           |

### Standard structure

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

Minimum coverage: 4 states (Default/Hover/Active/Disabled). Additional states
(Loading, Error, Empty) as applicable to the component.

### Production exclusion

`preview/` path excluded from the production build via env check:

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

## Feedback communication

Decision 3: agent accepts free-form combo, no forced standardization.

- Plain text: `"login button on the right, more space between cards"`
- Annotated screenshot: human pastes PNG from Snipping Tool / ShareX /
  Greenshot
- URL + description: `"on /dashboard the chart clips on the right"`
- DOM outerHTML: `"this <div class=\"card\">"`
- Any combination

Agent reads PNG via native vision (zero MCP). No screenshot tool standardization —
human uses whatever they prefer.

### Stop point `ambiguous_feedback`

When confidence is low (vague description, screenshot without clear annotation,
contradiction between text and visual):
- Agent does NOT speculate and make changes.
- Pauses, writes a menu A/B/C with candidate interpretations.
- Updates L1 `status: BLOCKED_STOP_POINT`.
- Waits for human to disambiguate.

### Kickoff priming stage 04

Lead in stage 04 prints to console on entry:

```
🎨 Preview loop active — workspace <NNN-slug>

Dev server: http://localhost:3000 (PID <pid>)
Chrome CDP: launch via scripts/launch-chrome-cdp.{bat,sh}
Preview pages: localhost:3000/preview/<component>

To give visual feedback, any combo works:
  - Text: "button on the right, more padding"
  - Annotated screenshot (Win+Shift+S Snipping or ShareX https://getsharex.com): paste PNG
  - URL: "/checkout, header is skewed"
  - HTML: paste outerHTML of the problematic element

If ambiguous, I ask before making changes (stop point ambiguous_feedback).
```

## Visual iteration

Decision 8: no cap, no audit in L1.

Iterates until human says `"ok done"` / `"approved"`. Trade-off declared:
speed > traceability. Long loops become the human's responsibility.

Stage 04 wave-summary mentions whether the wave closed in visual convergence
or still has pending refinement — auditable outside L1 formal.

## Design system cascade

Decision 9: cascade via DESIGN.md default; threshold 5 confirms.

Changes to a token (color, spacing, typography) flow through the cascade via
`DESIGN.md` → CSS vars:

1. Agent receives request (`"change primary to green"`).
2. Runs Grep `var(--color-primary)` or `{colors.primary}` in the codebase.
3. Counts affected files (= components that use the token).
4. **If ≤ 5 affected:** applies directly, records in commit message.
   ```
   workspace 042: cascade colors.primary green — 3 components affected
   ```
5. **If > 5 affected:** stop point `design_system_cascade`, menu:
   - **A) global cascade** — propagates to all via DESIGN.md token edit.
   - **B) limit scope** — only current component (local override;
     DESIGN.md remains the aspirational source recorded in
     `out-of-scope/<workspace>.md`).
   - **C) cancel** — reconsiders the change.

Threshold 5 is a heuristic, calibratable via
`_config/design-system-policy.yaml` (`design_cascade_threshold: <int>`).

## Multi-screen / navigational flow

Decision 10: CDP only reads the current URL by default; multi-screen replay on demand +
auto-detect keywords.

CDP live (decision 4) reads the current URL in real time. Sufficient for 90% of
cases (single-screen feedback).

### Multi-screen replay

When feedback involves a flow (e.g., `"checkout → payment → confirmation
has an issue at the transition"`):

- **Default:** agent does NOT activate replay automatically.
- **Auto-detect keywords:** if human feedback mentions `transition`,
  `flow`, `multi-step`, `navigation`, `fluxo`, agent suggests activating
  replay before making changes.
- **On human request:** `"I will show the flow"` → agent injects a temporary breadcrumb
  logger in `router.beforeEach` (Vue) / `useEffect` in root layout
  (Next/React) / `beforeNavigate` (Svelte).
- **Reads via CDP** `Runtime.consoleAPICalled`.
- **Reconstructs the sequence** of visited URLs + timing.
- **Replay disabled** at the end of the iteration (logger removed from code —
  commit `chore: remove temp breadcrumb logger`).

## Flow per ICM stage

| Stage | Action |
|-------|------|
| **00 recon** | Detects frontend stack (Next/Vite/Astro/SvelteKit). Reports in `recon-report.md`. Checks `package.json` for dev script. |
| **01 discovery** | Brand voice, tone, target audience. Captures inputs for DESIGN.md Overview (stage 02). |
| **02 design** | Creates/updates DESIGN.md (tokens). Designs mock data schema (Zod) if tier ≥ development. Plan.md includes flag `requires_design_system` + `requires_preview_page` per task. |
| **03 wave_planner** | Tasks with frontend files get propagated flags. Subagent cap respects tier. |
| **04 implementation_waves** | **Main loop.** Entry hook starts dev server, kickoff priming, helper CDP launch. Each subagent implements task + preview page + MSW handler (if applicable). Lead orchestrates human feedback via CDP. Hot-reload visual after each edit. On demand: full lint + Playwright sample. Exit hook kills dev server. |
| **05 verification** | Visual regression (production tier) compares screenshots vs baseline. Sample-check 3 components against DESIGN.md tokens. |
| **06 review** | `conventions` dimension audits adherence to tokens (no hardcoded values). Auditor reviews preview pages + MSW schema validity. |
| **07 merge** | Dev server + CDP profile dir cleaned. Changes to DESIGN.md merged along. |
| **08 feedback intake** | New iteration reads current DESIGN.md + route map before proposing visual changes. |

## Anti-patterns

### Mockup-first in an external canvas tool
Figma/Penpot trade-off detailed in `design-system.md`. If needed: optional profile
flag `figma_plugin_enabled` (not default, not documented in this protocol).

### Subagent without preview page
Stage 04 task with a reusable frontend component file WITHOUT
the corresponding `preview/<component>` = wave-reviewer flags it (issue:
"preview page missing").

### Inline mock data in the component
```tsx
// ❌ ANTI
const products = [{ id: 1, name: "test" }, { id: 2, name: "x" }];

// ✅ via fixture (experimental/tool)
import products from '@/fixtures/products.json';

// ✅ via MSW (development+) — component calls real fetch
const products = await fetch('/api/products').then(r => r.json());
```

### Hardcoded color/spacing when a token exists
Same rule as `design-system.md`. Reinforced in the preview loop: each edit
runs Grep against DESIGN.md tokens — literal match without ref → warning.

### Endless iteration without human closure
Decision 8 declares: human is responsible. But if the workspace finishes stage
04 without `wave-summary.md` mentioning visual convergence = wave-reviewer
flags it as non-blocking debt.

### Orphan dev server PID
Recovery wizard `DEV_SERVER_ORPHAN` detects this. Skill exit hook MUST
kill the process + delete the PID. Exiting without cleanup = next session enters
an ambiguous state.

## Recovery wizard new types

| Code                  | Detection                                                         | Plan A (preserve)                                |
|-----------------------|-------------------------------------------------------------------|--------------------------------------------------|
| `DEV_SERVER_ORPHAN`   | `.icm-main/.dev-server.pid` exists; process is dead               | delete PID file, log warning in history          |
| `CDP_DISCONNECTED`    | `.icm-chrome-profile/` exists; no Chrome listening on :9222        | suggest helper script relaunch (do not kill profile) |

Both `severity: warning` (does not block work — agent degrades
gracefully via fallbacks: route map + manual screenshot).

## Consolidated profile flags

```yaml
# profile-effective.yaml (generated by profile-merge.py)
preview_loop_enabled: true              # default true in frontend/fullstack
mock_data_strategy: msw_faker_zod       # tier-based: fixtures|msw_faker|msw_faker_zod
cdp_live_enabled: true                  # default true; opt-out via override
visual_iter_cap: null                   # decision 8: no cap
design_cascade_threshold: 5             # decision 9
preview_pages_path: preview/            # convention
```

## Cross-references

- `references/design-system.md` — DESIGN.md format Google Stitch spec
- `references/wave-execution-protocol.md` — 12-step pipeline stage 04
- `references/state-machine-schema.md` — L1 schema (new stop points)
- `scripts/recovery-wizard.py` — recovery types (DEV_SERVER_ORPHAN, CDP_DISCONNECTED)
- `templates/_config/profile-matrix.md` — `preview_loop_enabled`, `mock_data_strategy`
- [MSW docs](https://mswjs.io/) — Mock Service Worker
- [Faker.js docs](https://fakerjs.dev/) — fake data generation
- [Zod docs](https://zod.dev/) — schema validation
- [Playwright connect_over_cdp](https://playwright.dev/docs/api/class-browsertype) — CDP integration
- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/) — DOM/Runtime/Network domains
