# 4-Block Contract Template + Vertical TDD Cycle

> **Version:** v3.9.0
> **Skill:** `xp-icm-workflow`
> **Purpose:** Defines the mandatory 4-block contract per task in `plan.md` (output of stage 02 design, consumed by stages 03 wave_planner and 04 implementation_waves) **and** the canonical vertical TDD cycle (tracer-first + 1 test → 1 impl → repeat) that every subagent executes per task. Replaces v3.0.0-beta5 (Akita 15-item drop in v3.9.0).

> **Origin decision:** F1 of plan `reescrever-a-skill-zazzy-wirth.md` (line 57) + §4.4 dev↔qa loop + §4.11 channel 3 (plan.md schema). v3.9.0: drop inline Akita; QA delegated to forensic+ extended (L2) + orthogonal critic (L3) per `references/critic-protocol.md`.

---

## 1. The 4 blocks — mandatory schema per task

Every task in `plan.md` (stage 02 design) **must** declare the 4 blocks below, in fixed order. Each block is 50-200 tokens; total task between 200-800 tokens.

```markdown
## Task <SLUG>: <Human title>

### WHAT
<Functional requirements — what this task delivers.
 Product language, not implementation language.
 2-5 bullets.>

### HOW
<Technical approach — which files, which functions, which pattern.
 May explicitly cite an ADR ("follow 0004-auth-strategy").
 3-7 bullets.>

### OUT OF SCOPE
<Anti-requirements. Out of scope. What NOT to do.
 Exists to prevent scope creep and over-engineering.
 2-5 bullets.>

### VALIDATION
<Measurable acceptance criteria + mandatory tests.
 Each bullet must map to ≥1 test name (forensic+ Check 5 validates).
 3-7 bullets.>
```

### Why 4 blocks (and not 3 or 5)

| Block | Without it... |
|---|---|
| WHAT | Subagent invents requirements; QA has no anchor to validate against |
| HOW | Architectural decisions diverge between parallel tasks in the same wave |
| OUT OF SCOPE | Silent scope creep; subagent adds things "while we're here..." |
| VALIDATION | Tests cover what the dev found interesting, not what matters |

---

## 2. Complete task schema in `plan.md`

In addition to the 4 blocks, each task declares metadata consumed by the lead in stage 04 (channel 3 of the doc-reading-protocol):

```markdown
## Task <SLUG>: <Title>

### WHAT / HOW / OUT OF SCOPE / VALIDATION
<see §1>

### Depends on
- <parent-task-slug> OR none (root task)

### Files touched
- src/path/file.ts
- tests/path/file.test.ts

### Estimated lines
~250    <!-- optional. forensic-plus.py Check 3 (scope creep) triggers when
            actual diff insertions > 3 × estimate. Plan author opts in for
            tasks where bounded scope matters. Absent → check skipped. -->

### Applicable ADRs
- docs/decisions/0001-stack.md
- docs/decisions/0004-auth-strategy.md

### Critical pre-marked lessons
- 0033 (log policy)

### Extra conventions
- (default xp-conventions.md is sufficient)

### Tech debt paydown
- none    OR    - 0017 (refactor extraction X)

### Requires_peer_review
- true | false   (true if critical path tier=production OR profile flag)

### Requires E2E update
- true | false   <!-- v3.10.0: wave-planner auto-emits when Files touched
                      matches user_facing_paths from profile-effective.yaml.
                      Subagent MUST add/update ≥1 file in e2e/
                      cypress/, playwright/, tests/e2e/. Forensic+ Check 8
                      audits. Override via `**E2E:** skip - <rationale>`
                      in the 4-block (audit Stage 05). -->
```

| Field | Who fills in | Who consumes |
|---|---|---|
| 4-block | Designer (stage 02) | Subagent (stage 04) |
| Depends on | Designer (stage 02) | Wave-planner (explicit DAG edge) |
| Files touched | Designer; refined by wave-planner | Lead (branch boundary); Wave-planner (validates ≥1 test file) |
| Estimated lines (optional) | Designer (stage 02) | forensic-plus.py (Check 3 scope creep) |
| Applicable ADRs | Designer | Subagent (read order); forensic+ Check 7 (import drift) |
| Critical lessons | Wave-planner (Q10 match) | Subagent (pre-RED audit) |
| Extra conventions | Designer (rare) | Subagent |
| Tech debt paydown | Designer | Subagent (declares in commit) |
| Requires_peer_review | Wave-planner (rule Q6) | Lead (decides to spawn QA-pair) |

**`Files touched` rule — test file required:** every task that touches functional code (`src/`, `app/`, `lib/`, etc.) must declare ≥1 corresponding test file (`tests/`, `*.test.*`, `*_test.*`, `spec/`, etc.). Wave-planner validates this rule in the DAG pre-flight; task without a test file = `BLOCKED_ERROR` before wave allocation. Exceptions: tasks declared as `doc-only` or `config-only` in `Extra conventions` are exempt from the rule.

---

## 3. Vertical TDD cycle — tracer-first + 1 test → 1 impl → repeat

Every subagent executes **strictly** vertical TDD. Anti-horizontal slicing. mattpocock-aligned.

### 3.1 Vertical principle

Vertical = **complete one feature unit end-to-end** (test + impl + verify) before starting the next. Horizontal = "write all the tests first, then implement" (prohibited).

### 3.2 Tracer-first

Before the first unit/integration test, the subagent writes **1 tracer test** — the E2E golden path of the entire task, minimum viable, expected to fail initially. The tracer guides the shape of the impl, does not cover edge cases.

| Profile | Typical tracer |
|---------|---------------|
| backend | HTTP request → DB assertion (e.g.: POST /users → user row exists) |
| frontend | render component → user interaction → DOM assertion |
| fullstack | browser action → API call → DB → response render |
| ml | input fixture → model call → output shape assertion |
| agent_ia | prompt fixture → tool sequence → final output match |

Tracer is committed red as the first commit of the task. Does not count as coverage — it is scaffold.

### 3.3 Loop per feature unit

After the tracer, the subagent iterates:

```
LOOP {
  RED      → write 1 test (1 acceptance bullet OR 1 edge case)
  GREEN    → minimal impl to make the test pass (do not add untested logic)
  CI scope → run tests + types + lint only on files touched (fast feedback)
  REFACTOR → optional; only if there is an obvious complexity reduction
}
```

**Each loop iteration = 1 commit.** Incremental commits form a verifiable TDD history in `git log`. Forensic+ Check 1 validates ≥2 assertions in the final test file.

### 3.4 Anti-horizontal slicing

❌ **Prohibited:**
- Writing all task tests at once (without impl in between)
- Implementing all of the impl at once (without tests in between)
- Skipping `RED` ("I already know it will work")
- Skipping `GREEN minimal` (writing speculative logic "for the next test")

Signals that trigger a stop:
- Diff > 100 LOC without a corresponding new test
- Test file with 5+ test names but empty impl files
- Impl file with complete classes and empty test file

Forensic+ Check 5 (acceptance ↔ test mapping) detects when tests do not correspond to acceptance criteria — structural anti-horizontal gating.

### 3.5 Iteration cap

- **Cap:** 3 attempts for the entire task (full loop cycle exhausted).
- Failure = forensic+ HARD or critic REJECT 3 rounds.
- When cap is reached → escalate to lead-resolution tier (3 buckets B1/B3/B4 — see `references/lead-resolution-protocol.md`).

### 3.6 Stop points within the cycle

If at any step the subagent detects a stop point (e.g.: new paid service not declared in an ADR), it:

- Pauses the cycle at the current state (without losing progress).
- Triggers menu A/B/C per `stop-points-canonical.md`.
- Signals the lead via Agent tool output.
- Waits for resolution; cycle resumes from the step where it paused.

### 3.7 Commit verify gate

Before declaring COMPLETE, subagent confirms:

```
git log --oneline <BASE>..HEAD  →  ≥1 commit visible
```

Zero commits = incomplete task report; returns to cycle. forensic+ structural check detects branch HEAD == BASE HEAD.

---

## 4. Integration with superpowers (200tok summaries)

Subagent in stage 04 has in the `_references/superpowers-summary/` folder (copied by bootstrap):

| Summary | Covers steps |
|---|---|
| `test-driven-development-200tok.md` | RED → GREEN → REFACTOR (vertical) |
| `verification-before-completion-200tok.md` | CI gate scope |
| `systematic-debugging-200tok.md` | support when GREEN stalls |

---

## 5. QA delegation — who ensures quality

Starting from v3.9.0, task QA is the responsibility of:

| Layer | Responsibility | Token cost |
|-------|------------------|------------|
| L1 writer (subagent) | Writes vertical tests, code passes CI scope | (writer model) |
| L2 forensic+ extended | 7 deterministic git-only checks | 0 |
| L3 orthogonal critic | Independent LLM (tier ceiling) evaluates diff | ~3-8k input |
| L4 wave gate | global suite green + cross-task coherence (production) | (CI infra) |
| Lead-resolution tier | Last resort when cap exhausted OR catastrophic | (lead model) |

Subagent does NOT write an inline QA checklist in the task report. Self-grading bias documented (ICLR 2024 Huang, arxiv 2510.11822, arxiv 2509.16533) — delegated to orthogonal layers.

Task report (COMPLETE step) is minimal:

```markdown
# Task <slug> — COMPLETE

## Summary
<1-3 sentences about the delivered scope>

## Modified files
- <list>

## Tests
- <test file>: <count> tests
- Coverage: <%>

## ADRs applied
- <list>
```

---

## 6. Concrete example — task `auth-middleware`

Fictional task that illustrates the complete schema (4-block + metadata; no Akita checklist).

### 6.1 Input from `plan.md` (stage 02 design)

```markdown
## Task auth-middleware: JWT validation middleware

### WHAT
- Express middleware that validates JWT in `Authorization: Bearer <token>` headers.
- Rejects 401 when token is missing, malformed, or expired.
- Attaches `req.user = { id, email, role }` when valid.
- Logs failures (without PII) at `warn` level.

### HOW
- Create `src/auth/middleware.ts` exporting `requireJwt()`.
- Use lib `jose` (already in ADR 0001-stack), never `jsonwebtoken`.
- Verify signature via `JWKS_URI` read from `process.env.JWKS_URI`.
- Pipeline order: `cors → requireJwt → rateLimit` (lesson 0017).
- Error: throw `AuthError`/`AuthExpiredError` classes caught in `errorHandler`.

### OUT OF SCOPE
- Decode JWT without verifying (lesson 0042).
- Implement refresh-token (scope of another task).
- Log token value or email (PII; lesson 0033).
- Cache results in memory (out-of-scope; pending ADR).
- Internal mock of jose or JWKS client (use boundary mock; see mocking-guidelines.md).

### VALIDATION
- Test `test_missing_header_returns_401`: missing header → 401 + body `{error: "missing_auth"}`.
- Test `test_malformed_jwt_returns_401`: malformed token → 401 + warn log without PII.
- Test `test_expired_jwt_returns_401`: expired token → 401 + body `{error: "expired"}`.
- Test `test_valid_token_attaches_user`: valid token → `next()` called + `req.user` populated.
- Test `test_pipeline_order_integration`: pipeline order (`cors` first, `rateLimit` after) — integration.
- Coverage ≥90% on `src/auth/middleware.ts`.

### Depends on
- project-setup
- add-user-model

### Files touched
- src/auth/middleware.ts
- src/auth/errors.ts
- tests/auth/middleware.test.ts
- tests/auth/middleware.integration.test.ts

### Estimated lines
~120

### Applicable ADRs
- docs/decisions/0001-stack.md
- docs/decisions/0004-auth-strategy.md

### Critical pre-marked lessons
- 0042 (never trust decoded JWT without verify)
- 0033 (log auth failures without PII)
- 0017 (middleware order: cors → auth → rate)

### Extra conventions
- (default xp-conventions.md is sufficient)

### Tech debt paydown
- none

### Requires_peer_review
- true (path /auth, tier=production)
```

### 6.2 Expected subagent output (`task-auth-middleware.md`, COMPLETE)

```markdown
# Task auth-middleware — COMPLETE

## Summary
JWT middleware implemented in `src/auth/middleware.ts` (47 LOC) +
error classes in `src/auth/errors.ts`. Vertical TDD: tracer + 5 tests +
2 integration. Coverage 94%.

## Modified files
- src/auth/middleware.ts (+47 LOC)
- src/auth/errors.ts (+22 LOC)
- tests/auth/middleware.test.ts (+158 LOC, 5 tests)
- tests/auth/middleware.integration.test.ts (+62 LOC, 2 tests)

## Tests
- tests/auth/middleware.test.ts: 5 tests
- tests/auth/middleware.integration.test.ts: 2 tests
- Coverage: 94%

## ADRs applied
- 0001-stack (jose lib)
- 0004-auth-strategy (JWKS verification)
```

QA is validated by layers L2 (forensic+) + L3 (critic) — see `references/critic-protocol.md` and `references/forensic-plus-protocol.md`.

---

## 7. Cross-references

| Doc | Related content |
|---|---|
| `references/doc-reading-protocol.md` | Channels 1/2/3 — who injects what into the subagent |
| `references/wave-planner-algorithm.md` | DAG, Q10 lesson match, Q6 peer-review trigger |
| `references/subagent-protocol.md` | Lead spawn, Agent tool output, plan approval |
| `references/stop-points-canonical.md` | 15 stop points + thresholds per tier |
| `references/forensic-plus-protocol.md` | L2 deterministic checks (7 in v3.9.0) |
| `references/critic-protocol.md` | L3 orthogonal LLM critic |
| `references/lead-resolution-protocol.md` | Buckets B1/B3/B4 when cap exhausted |
| `references/mocking-guidelines.md` | Mock only boundaries; never internals |
| `references/recovery-wizard.md` | Recovery if cycle stalls without COMPLETE |
| `_references/superpowers-summary/test-driven-development-200tok.md` | Vertical TDD summary |
| `_references/superpowers-summary/verification-before-completion-200tok.md` | CI gate summary |

---

## 8. AGENT-BRIEF compatibility

Starting from v3.3.0, every 4-block must be parseable by
`scripts/agent-brief-render.py` in stage 04. v3.9.0 adds model fields
in the header. Mapping:

| 4-block | AGENT-BRIEF section |
|---|---|
| **WHAT:** | `Summary:` (1st line) + `Desired behavior:` (body) |
| **HOW:** | `Key interfaces:` (no absolute paths / line numbers) |
| **OUT OF SCOPE:** | `Out of scope:` |
| **VALIDATION:** | `Acceptance criteria:` (testable list) |

Additionally, the task block in plan.md MUST have:
- `**Type:** AFK` or `**Type:** HITL` (see `task-types-hitl-afk.md`)
- `**Files touched:** path1, path2` (no line numbers)

v3.9.0 brief header:
```yaml
model_recommended_writer: <claude-haiku-4-5|claude-sonnet-4-6|claude-opus-4-7>
model_recommended_critic: <claude-haiku-4-5|claude-sonnet-4-6|claude-opus-4-7>
complexity_score: <int>
```

Canonical AGENT-BRIEF doc: `references/agent-brief-template.md`.
