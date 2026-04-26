# Changelog — xp-icm-workflow

Histórico de versões da skill. A versão atual vive no frontmatter do `SKILL.md`.

---

## v2.4.0 — Refactor de concisão + correções adversariais

### Refactor estrutural (concisão sem perda)

- **SKILL.md reduzido de 1291 → ~600 linhas** sem perder hard-gates, princípios ou contratos.
- Templates de `CONTEXT.md` dos 6 estágios + templates de `CLAUDE.md` raiz e `CONTEXT.md` raiz movidos para `references/stage-templates.md`.
- Seção Extensibilidade movida para `references/extending-skill.md`.
- Histórico de versão movido para este arquivo (`references/changelog.md`).
- Novo `references/example-run.md` com exemplo de transição entre estágios.
- "Phase 1 — Execução por Estágios" compactada: protocolo de delegação e fix loop ficam no SKILL.md (load-bearing em runtime), detalhe de template fica em reference.
- Stage Transition Checklist declarado 1× em seção dedicada; estágios referenciam por nome em vez de duplicar.
- Princípio de Delegação com menção repetida somente onde o risco é real (Estágios 03/04/05).
- ICM Design Principles no SKILL.md ficam como 5 títulos + 1 frase cada; detalhe no reference `icm-paper-summary.md`.
- Convenção de prefixo `[L3:cfg]` / `[L4:in]` nos Inputs table — reduz prosa repetida sem perder distinção operacional restrição vs input.

### Correções adversariais round 1 (review por subagent)

- **Gap A (example-run)**: prompt do subagent no `example-run.md` agora inclui `decisions.md` — alinha com o Protocolo de Delegação do SKILL.md.
- **Gap B (contradição L1 vs L3)**: `docs/decisions/` agora é L3 consistente em todo SKILL.md (seção Edit-Source corrigida).
- **Gap C (race condition em reports paralelos)**: subagents paralelos escrevem em `output/reports/task-<slug>.md` (arquivos próprios). Orquestradora consolida depois em `implementation-report.md` — elimina race. Protocolo de Delegação, formato de output e example-run atualizados.
- **Gap D (Phase 0 não respeitava AGENTS.md)**: adicionado Passo 0.0 "Respeitar Instruction Priority" — lê `AGENTS.md` e `CLAUDE.md` do projeto pai ANTES de criar workspace.
- **Gap E (pasta `stages/XX/references/` nunca usada)**: removida da estrutura padrão. Agora opcional, criar apenas se houver material de referência específico do estágio.
- **Gap F (tensão ADRs L3 mas criados no run)**: adicionada seção "Ciclo de Vida dos ADRs" — esclarece nascimento no Estágio 02, promoção imediata a L3, edição via Edit-Source.
- **Gap G ("DELEGA, não executa" ambíguo)**: reformulado Orchestration Boundary — distingue invocação de skills (01-02) de delegação a subagents (03+), clarifica o que a orquestradora pode ler.

### Correções adversariais round 2 (cross-file review completa)

- **Gap S (template Estágio 03 desalinhado com correção Gap C)**: `references/stage-templates.md` atualizado — Template do Estágio 03 agora reflete a nova estrutura `reports/task-*.md` + consolidação em `implementation-report.md`. Outputs, Process passo 7 e Verify alinhados com SKILL.md.
- **Gap T (xp-workflow-integration tinha `docs/*` como L1)**: tabela "Documentos Compartilhados" corrigida — `docs/decisions/`, `docs/tech_debt.md`, `docs/lessons.md` agora são L3 consistente com Gap B. Tabela também inclui novos artefatos `reports/task-*.md`.
- **Gap U (superpowers-mapping regra 4 omitia reports paralelos)**: regra 4 agora lista `reports/task-*.md` individuais como artefato que orquestradora lê.
- **Gap Z (ambiguidade STAGE após transição)**: Stage Transition Checklist item 3 agora especifica que, após marcar estágio completado no histórico, o campo `STAGE` do `CONTEXT.md` raiz é atualizado para apontar ao PRÓXIMO estágio como `IN_PROGRESS`. Último estágio marca `STAGE: COMPLETED`. Example-run alinhado.

### Correções adversariais round 3 (detalhes finos cross-file)

- **Gap AB/AK (numeração do passo do Bootstrap)**: `stage-templates.md` referenciava "Passo 0.5" e "Passo 0.4" mas SKILL.md combinou em "Passo 0.4-0.6". Alinhado.
- **Gap AD (example-run descrevendo CONTEXT.md raiz errado pós-Z)**: Passo 2 do `example-run.md` agora reflete que ao entrar no Estágio 03 o campo `STAGE` já é `03_implementation, IN_PROGRESS` (não `02_design COMPLETED`).
- **Gap AE (review gate Estágio 03 omitia reports individuais)**: SKILL.md atualizado — review gate agora menciona leitura dos `reports/task-*.md` individuais E/OU consolidado.
- **Gap AF (superpowers-mapping listava lessons como input do subagent)**: corrigido — apenas orquestradora lê `lessons.md`; subagent recebe lições filtradas injetadas no prompt.
- **Gap AH (contagem errada de seções)**: SKILL.md e `stage-templates.md` diziam "seis seções" mas listavam 7 (Estado, Skill, Inputs, Process, Outputs, Verify, Review Gate). Corrigido para "sete seções".
- **Gap AJ (extending-skill item 4 omitia templates raiz)**: checklist agora inclui atualização de `CLAUDE.md` raiz e `CONTEXT.md` raiz quando a nova skill impactar identidade ou roteamento do workspace.
- **Gap AL (lessons.md fluxo não explícito)**: SKILL.md Processo do Estágio 03 passo 5 agora explicita que orquestradora lê `lessons.md`, extrai lições aplicáveis e injeta no prompt de delegação — subagent não lê o arquivo diretamente.
- **Gap AM (example-run anti-consistência ADR 0003)**: regras de contexto do prompt do subagent (a) agora dizem "NÃO ler ADRs 0001-0002"; ADR 0003 (stack) está resumido no `## Contexto do Workspace` do prompt — não duplicar leitura.

### Correções adversariais round 4 (subagent fresco)

- **Gap AN (numeração quebrada Estágio 03)**: "Processo da orquestradora" tinha passos 1-6 e depois "Após todos completarem" reiniciava em 6-8 — colisão. Agora sequencial 1-10, coerente.
- **Gap AO (regressão Gap C — quem escreve implementation-report)**: Texto "Formato de `implementation-report.md` (subagentes escrevem, orquestradora lê)" contradizia a arquitetura pós-Gap C. Corrigido: formato descreve `output/reports/task-<slug>.md` (cada subagent escreve o seu); consolidado é agregação feita pela orquestradora ou consolidator.
- **Gap AP (template Estágio 03 omitia reports paralelos)**: `stage-templates.md` Princípio de Delegação e Review Gate diziam "orquestradora lê SOMENTE implementation-report.md". Agora menciona reports individuais + consolidado consistente com SKILL.md e superpowers-mapping.
- **Gap AQ (example-run histórico sem ADRs)**: Stage Transition Checklist do exemplo agora inclui ADRs criados no Estágio 02 no histórico da transição.
- **Gap AR (typo schema→shema)**: 2 ocorrências de `0004-shema-habits.md` corrigidas para `0004-schema-habits.md`.
- **Gap AS (árvore docs/ em linha com vírgula)**: estrutura de pastas SKILL.md Passo 0.3 agora mostra `docs/` com 3 sub-itens em árvore (decisions/, lessons.md, tech_debt.md), classificados como L3.

Comportamento funcional equivalente a v2.3.0 + resolução de todas as ambiguidades, contradições e riscos estruturais detectados em 4 rounds de review adversarial (33 gaps corrigidos). Nenhum hard-gate removido.

---

## v2.3.0 — Hard Gates e Separação Rígida

- Stage Transition Protocol (5-item checklist hard gate entre estágios).
- Orchestration Boundary Rule (tabela por tipo de estágio + auto-correção).
- Fix Loop Protocol (review → delegate → review loop para P0/P1 issues).
- Review Gates 01-06 com checklist de transição explícito.
- Seção Estado obrigatória nos 6 templates de `CONTEXT.md`.

---

## v2.2.0 — Extensibilidade

- Seção Self-Improvement com checklist de 8 itens para atualizar quando nova skill é incorporada.
- Perguntas de classificação de nova skill.
- Formato de registro no changelog.

---

## v2.1.0 — Princípio de Delegação

- Orquestradora NUNCA lê código-fonte diretamente.
- Estágio 03 sempre delega para subagentes (não mais opcional).
- Templates de `CONTEXT.md` dos Estágios 03, 04 e 05 atualizados com "NÃO LER src/ ou tests/".
- Formato de `implementation-report.md` especificado.
- Error recovery atualizado para subagentes.
- Referências (`superpowers-mapping`, `xp-workflow-integration`) atualizadas para refletir delegação.

---

## v2.0.0 — Revisão baseada em auditoria contra o paper ICM

- Layer Loading Protocol com ordem obrigatória e scoping explícito.
- Distinção operacional Layer 3 vs Layer 4 (restrição vs input).
- Token budget e context pollution.
- Compilação incremental com re-execução seletiva.
- Seção Verify nos contratos de estágio.
- Princípio edit-source operacionalizado.
- Retomada de sessão lê Layer 2/3 do estágio atual.
- Context scoping para subagentes.
- Princípio "configure the factory".
- Workspace builder.
- 5 ICM design principles explícitos.

---

## v1.2.0 — Revisão final

- Paths relativos padronizados.
- Referências a `src/`, `tests/` corrigidas (não dentro de `stages/`).
- Atualização de `CONTEXT.md` raiz em todos os estágios.
- "Caminho absoluto" corrigido para "caminho relativo" nos subagentes.

---

## v1.1.0 — Correções pós-auditoria

- Arquivo de estado (`CONTEXT.md` raiz).
- Retomada de sessão.
- Propagação de ADRs formais.
- Contrato explícito de subagentes.
- Inputs completos nos templates.
- Error recovery distinto por origem.

---

## v1.0.0 — XP-ICM Workflow inicial

- Integração ICM + `/xp-workflow` + superpowers.
