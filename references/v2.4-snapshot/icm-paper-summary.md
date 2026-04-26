# ICM Paper Summary (VanClief & McDermott, 2025)

**Paper:** "Interpretable Context Methodology: Folder Structure as Agent Architecture"
**arXiv:** 2603.16021v2
**Key takeaway:** Orquestração de agentes AI via estrutura de sistema de arquivos, sem framework.

---

## 5 Design Principles

### 1. One stage, one job
Cada estágio faz uma coisa e escreve output na sua pasta. Segue McIlroy (Unix: um programa, uma coisa bem feita) e Parnas (information hiding).

### 2. Plaintext as the interface
Estágios se comunicam por markdown e JSON. Nenhum formato binário. Qualquer ferramenta que lê texto pode participar. Qualquer humano com editor pode inspecionar/modificar.

### 3. Layered context loading
Agentes carregam SOMENTE o contexto que precisam. Previne o problema "lost in the middle" (Liu et al., 2024) — modelos degradam quando contexto irrelevante é carregado. Cada estágio recebe 2.000–8.000 tokens focados vs. 30.000–50.000 de abordagem monolítica.

### 4. Every output is an edit surface
O output de cada estágio é um arquivo que o humano pode abrir, ler, editar e salvar. Implementa mixed-initiative (Horvitz, 1999) e direct manipulation (Shneiderman, 1983).

### 5. Configure the factory, not the product
Workspace configurado uma vez. Cada run produz novo deliverable com mesma configuração. Layer 3 (referência) é a fábrica. Layer 4 (trabalho) é o produto. Editar Layer 3 melhora todas as runs. Editar Layer 4 melhora esta run.

---

## 5-Layer Context Hierarchy

| Layer | File | Role | Tokens | Loads always? |
|---|---|---|---|---|
| **0** | `CLAUDE.md` | "Where am I?" | ~800 | Yes |
| **1** | `CONTEXT.md` (root) | "Where do I go?" | ~300 | Yes |
| **2** | `stages/XX/CONTEXT.md` | "What do I do?" | ~500 | Only current stage |
| **3** | `references/`, `_config/`, `docs/decisions/` | "What rules apply?" | 500–2000 | Only listed in Inputs |
| **4** | `stages/XX/output/` | "What am I working with?" | Varies | Only listed in Inputs |

### Layer 3 vs Layer 4 — Key Operational Distinction

| Aspect | Layer 3 (Reference) | Layer 4 (Working) |
|---|---|---|
| Changes between runs? | **No** — configured once | **Yes** — produced each run |
| How the agent should process it | **Internalize as constraints**: follow these rules, use this style | **Process as input**: transform this content |
| When to edit? | When the rule needs to change for ALL future runs | When this run's output needs a tweak |
| Analogy | **The recipe** | **The ingredients** |
| Configured when? | Workspace setup (once) | Pipeline execution (each run) |

---

## Stage Contracts

Each stage CONTEXT.md has four sections:

1. **Inputs** — which files to load, with explicit scoping (which sections are relevant, which to ignore)
2. **Process** — what to do, in problem language
3. **Outputs** — what to produce and where to write
4. **Verify** (new) — which earlier stage outputs to check for consistency, and what criteria

### Example Inputs table:
```
## Inputs
- Layer 4: ../01_research/output/research-output.md — read "Key Findings" and "Data" sections; IGNORE "Methodology"
- Layer 3: ../../_config/voice.md — internalize as style constraint
- Layer 3: references/structure.md — internalize as format constraint
- IGNORE: ../../docs/decisions/ not listed below, ../03_production/ outputs
```

---

## Incremental Compilation (Selective Re-execution)

Key benefit: if stage 1 output is fine but stage 2 needs rework, re-run ONLY stage 2.

**Dependency rules:**
- Change in Layer 3 (`_config/`, `references/`, `docs/decisions/`) → invalidates ALL downstream stages
- Change in Layer 4 (`output/` of a stage) → invalidates only the consuming stage and subsequent ones
- Change in Layer 2 (`CONTEXT.md` of a stage) → invalidates only that stage and subsequent ones

---

## Edit-Source Principle

When output is wrong, there are two responses:
1. **Edit the output** — fixes this run (like patching a binary)
2. **Edit the source** — fixes all future runs (like fixing the compiler source code)

Recurring edits are diagnostic: if you always tighten the opening paragraph, the stage contract should say "keep the opening under 3 sentences."

---

## Where ICM Does NOT Work

- Real-time multi-agent collaboration (tight loops between agents)
- High-concurrency systems (many users hitting same pipeline)
- Workflows requiring complex branching logic based on AI decisions mid-pipeline

---

## Key References from Paper

- Liu et al. (2024) — "Lost in the Middle": LLMs perform worse with irrelevant context in long prompts
- Jiang et al. (2023) — Prompt compression achieves 20x token reduction with minimal loss
- Horvitz (1999) — Mixed-initiative systems: human control at natural breakpoints
- Shneiderman (2020) — Human-Centered AI: high control + high automation simultaneously
- Rudin (2019) — Stop explaining black boxes, build interpretable systems
- Wu, Terry & Cai (2022) — AI Chains: transparent multi-step LLM workflows