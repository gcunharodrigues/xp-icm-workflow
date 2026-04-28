# Test Recipe — app_web_frontend

> Referência de estratégia de teste para SPAs/SSR (React, Vue, Svelte, Next.js, SvelteKit).
> Lido pela sessão de discovery (stage 01) e usado para preencher §Test Strategy no plan.md (stage 02).

## Tipos de teste obrigatórios

| Tipo | O que testa | Quando usar |
|---|---|---|
| **Unit** | Funções puras, hooks, utils, store transformations | Toda lógica sem DOM |
| **Component** | Render + interação de componentes com `@testing-library` | Todo componente com estado/evento |
| **E2E** | Fluxo completo no browser real (dev/production) | Fluxos críticos de usuário |
| **Visual regression** | Screenshots comparadas automaticamente (production) | Layout crítico, design system |
| **A11y** | Violations WCAG via axe (dev/production) | Todo componente público |

## Frameworks recomendados

| Tipo | Framework | Observação |
|---|---|---|
| Unit + Component | `vitest` + `@testing-library/react` (ou vue/svelte) | Preferir RTL sobre Enzyme |
| E2E | `playwright` | Alternativa: `cypress` |
| A11y | `@axe-core/playwright` ou `jest-axe` | Executar em E2E ou component test |
| Visual regression | `playwright` screenshots | Alternativa: Percy/Chromatic |
| API mock | `msw` (Mock Service Worker) | Intercept fetch sem mock manual |

## Padrões essenciais

### Component test — render + interação

```tsx
// Padrão: preferir queries semânticas (getByRole, getByLabelText)
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

test("login form submits credentials", async () => {
  const user = userEvent.setup();
  const onSubmit = vi.fn();
  render(<LoginForm onSubmit={onSubmit} />);

  await user.type(screen.getByLabelText(/email/i), "test@example.com");
  await user.type(screen.getByLabelText(/senha/i), "secret123");
  await user.click(screen.getByRole("button", { name: /entrar/i }));

  expect(onSubmit).toHaveBeenCalledWith({
    email: "test@example.com",
    password: "secret123",
  });
});
```

### Mock de API com MSW

```ts
// src/mocks/handlers.ts
import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("/api/users/:id", ({ params }) =>
    HttpResponse.json({ id: params.id, name: "Test User" })
  ),
];

// Configurado em setupTests.ts — não usar fetch mock manual
```

### A11y check embutido no component test

```ts
import { axe, toHaveNoViolations } from "jest-axe";
expect.extend(toHaveNoViolations);

test("form has no a11y violations", async () => {
  const { container } = render(<LoginForm />);
  const results = await axe(container);
  expect(results).toHaveNoViolations();
});
```

### E2E com Playwright

```ts
// tests/e2e/login.spec.ts
test("user can login and see dashboard", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("user@example.com");
  await page.getByLabel("Senha").fill("password123");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page).toHaveURL("/dashboard");
  await expect(page.getByRole("heading", { name: /bem-vindo/i })).toBeVisible();
});
```

## Estrutura de arquivos

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
      thresholds: { lines: 80, branches: 80 },  // ajustar por tier
    },
  },
};
```

## Anti-patterns

- Testar implementação (detalhes de estado interno) em vez de comportamento visível.
- Usar `getByTestId` quando `getByRole` / `getByLabelText` existem — quebre acessibilidade se usar testids como crutch.
- Snapshots de HTML grandes — use snapshots apenas para componentes de design system estáticos.
- Mock manual de `fetch`/`axios` — use MSW que intercepta no service-worker level.
- `waitFor` com `sleep` — use `findBy*` que espera automaticamente.

## Checklist rápido (auto-QA Akita suporte)

- [ ] Cada componente com estado/evento tem ≥1 component test com RTL
- [ ] A11y check roda em cada componente público
- [ ] Fluxos críticos (login, checkout, form submit) têm E2E (se tier ≥ development)
- [ ] Sem `getByTestId` onde `getByRole`/`getByLabelText` funciona
- [ ] MSW configura mocks de API (não fetch/axios manual)
- [ ] Coverage ≥ threshold do tier (ver `_config/profile-effective.yaml`)
