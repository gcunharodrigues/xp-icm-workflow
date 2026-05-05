# Doc Reading Protocol — Documentation channels for the subagent

> Protocol defining **how** a subagent (stage 04) receives documentation: which docs to read, in what order, and who injects each one.

## The 3 channels

| Channel | Name | Who injects | What | Where |
|---|---|---|---|---|
| 1 | **L2 Inputs** | Workspace structure (bootstrap + sessions) | The stage's `CONTEXT.md` + files declared in the `Inputs` table | `stages/<NN>/CONTEXT.md` lists all mandatory and conditional inputs |
| 2 | **Lead injects** | Wave lead (stage 04 coordinating agent) | Pre-marked critical lessons, task context, relevant ADRs, extra conventions | Injected into the wave's `_kickoff.md` and/or the task in `plan.md` |
| 3 | **plan.md declares** | Designer (stage 02), refined by wave-planner (stage 03) | Per-task metadata: Files touched, ADRs aplicáveis, Critical lessons, Tech debt paydown, Requires_peer_review | Metadata section of each task in `plan.md` |

## Reading rule

1. **Channel 1 is mandatory.** Every subagent reads L0 → L1 → L2 (its stage) → declared Inputs. No exception.
2. **Channel 2 is mandatory when present.** If `_kickoff.md` exists in the stage, the subagent reads it before starting. The lead may inject additional context via direct message (only when strictly necessary).
3. **Channel 3 is task-specific.** Each task in `plan.md` declares which ADRs, lessons, and files the subagent must consult. The subagent reads **only** the files declared in `Files touched`, not the entire `src/` tree.

## What the subagent does NOT read

- Other workspaces in `workspaces/<other>/`
- Outputs from stages not listed in `Inputs`
- The entire `src/` tree — only `Files touched` from the task
- L4 outputs from future stages (which do not yet exist)

## Anti-patterns

- **Over-read:** reading the entire `src/` instead of the declared `Files touched`. High token cost, diluted context.
- **Under-read:** skipping mandatory L2 Inputs. Misses conventions, stop points, gates.
- **Channel 2 without kickstart:** a lead that does not generate `_kickoff.md` leaves the subagent without wave context. Every wave must have a kickoff.

## Cross-reference with other protocols

- **4-block-contract-template.md:** The task schema in `plan.md` is the vehicle for channel 3. Each task carries O QUE / COMO / NÃO QUERO / VALIDAÇÃO + metadata.
- **subagent-protocol.md:** The lead uses channels 1+2+3 to assemble each subagent's context before spawn.
- **session-handoff-protocol.md:** The `_kickoff.md` is the channel 2 artifact between sessions (lead → next session).
