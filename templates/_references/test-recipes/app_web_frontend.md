# Test Recipe — app_web_frontend

> Test strategy reference for SPAs/SSR (React, Vue, Svelte, Next.js, SvelteKit).
> Read by the discovery session (stage 01) and used to fill §Test Strategy in plan.md (stage 02).

## Required test types

| Type | What it tests | When to use |
|---|---|---|
| **Unit** | Pure functions, hooks, utils, store transformations | All logic without DOM |
| **Component** | Render + component interaction with `@testing-library` | Every component with state/event |
| **E2E** | Full flow in a real browser (dev/production) | Critical user flows |
| **Visual regression** | Automatically compared screenshots (production) | Critical layout, design system |
| **A11y** | WCAG violations via axe (dev/production) | Every public component |

## Recommended frameworks

| Type | Framework | Note |
|---|---|---|
| Unit + Component | `vitest` + `@testing-library/react` (or vue/svelte) | Prefer RTL over Enzyme |
| E2E | `playwright` | Alternative: `cypress` |
| A11y | `@axe-core/playwright` or `jest-axe` | Run in E2E or component test |
| Visual regression | `playwright` screenshots | Alternative: Percy/Chromatic |
| API mock | `msw` (Mock Service Worker) | Intercept fetch without manual mock |

## Essential patterns

### Component test — render + interaction

```tsx
// Pattern: prefer semantic queries (getByRole, getByLabelText)
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

test("login form submits credentials", async () => {
  const user = userEvent.setup();
  const onSubmit = vi.fn();
  render(<LoginForm onSubmit={onSubmit} />);

  await user.type(screen.getByLabelText(/email/i), "test@example.com");
  await user.type(screen.getByLabelText(/password/i), "secret123");
  await user.click(screen.getByRole("button", { name: /sign in/i }));

  expect(onSubmit).toHaveBeenCalledWith({
    email: "test@example.com",
    password: "secret123",
  });
});
```

### API mock with MSW

```ts
// src/mocks/handlers.ts
import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("/api/users/:id", ({ params }) =>
    HttpResponse.json({ id: params.id, name: "Test User" })
  ),
];

// Configured in setupTests.ts — do not use manual fetch mock
```

### A11y check embedded in component test

```ts
import { axe, toHaveNoViolations } from "jest-axe";
expect.extend(toHaveNoViolations);

test("form has no a11y violations", async () => {
  const { container } = render(<LoginForm />);
  const results = await axe(container);
  expect(results).toHaveNoViolations();
});
```

### E2E with Playwright

```ts
// tests/e2e/login.spec.ts
test("user can login and see dashboard", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("user@example.com");
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL("/dashboard");
  await expect(page.getByRole("heading", { name: /welcome/i })).toBeVisible();
});
```

## File structure

```
src/
  components/
    LoginForm/
      LoginForm.tsx
      LoginForm.test.tsx     # co-located component + a11y tests
  hooks/
    useAuth/
      useAuth.ts
      useAuth.test.ts        # co-located hook tests
  utils/
    formatDate.ts
    formatDate.test.ts       # co-located unit tests
tests/
  e2e/
    login.spec.ts
    dashboard.spec.ts
  mocks/
    handlers.ts
    setup.ts
```

## Coverage configuration

```ts
// vitest.config.ts
export default {
  test: {
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.stories.*", "src/mocks/**", "tests/e2e/**"],
      thresholds: { lines: 80, branches: 80 },  // adjust per tier
    },
  },
};
```

## Anti-patterns

- Testing implementation (internal state details) instead of visible behavior.
- Using `getByTestId` when `getByRole` / `getByLabelText` exist — breaks accessibility if used as a crutch.
- Large HTML snapshots — use snapshots only for static design system components.
- Manual `fetch`/`axios` mock — use MSW which intercepts at the service-worker level.
- `waitFor` with `sleep` — use `findBy*` which waits automatically.

## Quick checklist (auto-QA Akita support)

- [ ] Each component with state/event has ≥1 component test with RTL
- [ ] A11y check runs on each public component
- [ ] Critical flows (login, checkout, form submit) have E2E (if tier ≥ development)
- [ ] No `getByTestId` where `getByRole`/`getByLabelText` works
- [ ] MSW configures API mocks (not manual fetch/axios)
- [ ] Coverage ≥ tier threshold (see `_config/profile-effective.yaml`)
