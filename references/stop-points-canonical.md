# Stop Points canônicos

> **Versão:** v3.0.0-beta1
> **Path resolution:** caminhos `scripts/` neste documento referem-se a `<SKILL_DIR>/scripts/`, onde `SKILL_DIR` está definido em L0 (`CLAUDE.md`).
> **Propósito:** lista canônica dos 12 stop points da skill `xp-icm-workflow` + thresholds calibrados por tier para itens 5/7/8 + template padronizado de menu A/B/C + protocolo de update do L1.

Resolução **Q5** do plan: lista fixa de 12 stops; itens 5, 7, 8 calibrados por tier conforme `templates/_config/profile-matrix.md` (chaves `stop_points_calibration.item_5/7/8`); demais 9 sempre `hard` em qualquer tier.

---

## 1. Lista canônica (12 itens)

| # | id | Descrição |
|---|---|---|
| 1 | `stack` | Stack tecnológica (linguagem, framework, runtime) |
| 2 | `db` | Banco de dados (engine, schema design) |
| 3 | `external_api` | API externa (paga? rate-limit? privacy?) |
| 4 | `new_dep` | Nova dependência (license? maintenance? size?) |
| 5 | `paid_service` | Serviço pago (custo recorrente?) — **calibrado por tier** |
| 6 | `irreversible` | Decisão irreversível (drop table, schema migration destructive) |
| 7 | `over_eng` | Over-engineering detectado (3+ camadas de abstração novas) — **calibrado por tier** |
| 8 | `pii` | PII/dados sensíveis (LGPD, ofuscação) — **calibrado por tier** |
| 9 | `prod_migration` | Migration de schema com dados em prod |
| 10 | `adr_drift` | Stack que difere do declarado em ADR existente |
| 11 | `workspace_corrupt` | Workspace ICM corrupted (L1/L2 inconsistentes — para e pede recovery) |
| 12 | `profile_mismatch` | Profile/tier inconsistente com escopo da task |

### 1.1 Detalhe por item

#### 1 — `stack`
Mudança ou primeira escolha de linguagem, framework ou runtime principal.

- **Sinais:**
  - Discovery propõe linguagem ainda não declarada em ADR.
  - Plan inclui novo runtime (Node, Python, Go) não-presente no projeto.
  - Migration de framework (Express → Fastify, Django → FastAPI).
  - Greenfield sem stack pré-fixada.
- **Trade-offs típicos:** maturidade do ecossistema vs preferência do time; perf vs DX; coesão arquitetural vs feature-fit.

#### 2 — `db`
Escolha de engine de banco ou redesign substantivo de schema.

- **Sinais:**
  - Primeira persistência do projeto.
  - Mudança de engine (Postgres → Mongo, SQLite → Postgres).
  - Schema redesign que renomeia/elimina tabelas usadas.
  - Nova classe de storage (cache, queue, OLAP).
- **Trade-offs típicos:** ACID vs flexibilidade; custo de op vs perf; portabilidade vs feature-fit do engine.

#### 3 — `external_api`
Integração com API de terceiro.

- **Sinais:**
  - Plan inclui chamada HTTP a serviço não-controlado.
  - API exige API key, OAuth, contrato de SLA.
  - Rate-limit não-trivial (<100 req/min).
  - Dados saindo da fronteira do projeto (privacy review).
- **Trade-offs típicos:** velocidade de entrega vs lock-in; SLA externo vs autonomia; compliance vs custo de implementar in-house.

#### 4 — `new_dep`
Adição de nova dependência runtime ou dev.

- **Sinais:**
  - `requirements.txt` / `package.json` ganha entry novo.
  - Pacote sem releases nos últimos 12 meses.
  - Licença não-permissiva (GPL, AGPL, custom).
  - Tamanho > 5 MB ou árvore transitiva > 50 pacotes.
- **Trade-offs típicos:** velocidade vs supply-chain risk; reuso vs lock-in; manutenção downstream.

#### 5 — `paid_service` (calibrado)
Serviço SaaS com custo recorrente.

- **Sinais:**
  - Plano pago obrigatório acima do free-tier.
  - Custo mensal estimado > threshold do tier (ver §2).
  - Vendor lock-in significativo (dados não-exportáveis).
  - Auto-scale com piso de custo.
- **Trade-offs típicos:** dev velocity vs OPEX recorrente; soberania vs conveniência; previsibilidade de custo vs flexibilidade.

#### 6 — `irreversible`
Operação que destrói dados ou histórico de forma não-recuperável.

- **Sinais:**
  - `DROP TABLE`, `TRUNCATE`, schema migration destructive (drop column com dados).
  - `git push --force` sobre branch compartilhada.
  - Rotação de credencial sem grace-window.
  - Hard-delete de registros sem soft-delete prévio.
- **Trade-offs típicos:** simplicidade vs reversibilidade; espaço/perf vs auditabilidade; agora vs janela de undo.

#### 7 — `over_eng` (calibrado)
Sinal de over-engineering em design.

- **Sinais:**
  - 3+ camadas novas de abstração para resolver 1 problema concreto.
  - Padrões enterprise (factories, mediators, brokers) sem necessidade demonstrada.
  - Generalização preventiva sem segundo caso de uso real.
  - Configurabilidade que não tem segundo consumidor.
- **Trade-offs típicos:** flexibilidade futura vs custo de leitura; YAGNI vs reuso antecipado.

#### 8 — `pii` (calibrado)
Manipulação de dados pessoais ou sensíveis.

- **Sinais:**
  - Schema inclui CPF, RG, e-mail, telefone, dados de saúde.
  - Logs potencialmente vazam PII em texto claro.
  - Compartilhamento entre serviços sem ofuscação/criptografia.
  - Retenção indefinida sem política declarada.
- **Trade-offs típicos:** UX vs compliance LGPD; debug vs minimização; perf vs criptografia.

#### 9 — `prod_migration`
Migration de schema executando contra dados de produção.

- **Sinais:**
  - Migration toca tabela com volume > 100k linhas.
  - DDL bloqueante em RDBMS (ALTER TABLE com rewrite).
  - Mudança de tipo/constraint que invalida linhas existentes.
  - Sem janela de manutenção pré-acordada.
- **Trade-offs típicos:** zero-downtime vs simplicidade; backfill incremental vs single shot; rollback plan vs forward-only.

#### 10 — `adr_drift`
Plan diverge de ADR existente.

- **Sinais:**
  - ADR aprovado declara stack X, plan propõe Y.
  - Decisão arquitetural toca componente com ADR vigente.
  - "Rationale" antigo do ADR ainda válido — mas plan ignora.
  - ADR não foi superseded formalmente.
- **Trade-offs típicos:** manter ADR (custo de cumprir) vs superseder (custo de re-justificar) vs convivência híbrida (custo de divergência).

#### 11 — `workspace_corrupt`
Inconsistência entre L1 (CONTEXT.md frontmatter) e estado real do filesystem.

- **Sinais:**
  - Pre-flight check detecta hash mismatch, outputs ausentes, commit_sha sumido (ver §Heurísticas em `references/state-machine-schema.md`).
  - L1 diz `IN_PROGRESS` mas sem commits em workspace há > 24h.
  - `waves.current=N` sem branches `wave-N/<task>` correspondentes.
- **Trade-offs típicos:** retomar via Recovery Wizard vs abandonar workspace vs spawn novo workspace.
- **Nota:** este stop point é especial — sempre dispara `hard` e propõe Recovery Wizard direto, não menu A/B/C livre.

#### 12 — `profile_mismatch`
Profile/tier escolhido no bootstrap não corresponde ao escopo real da task em curso.

- **Sinais:**
  - Tier `experimental` mas plan inclui dados de produção.
  - Profile `technical_article` mas task envolve código rodando em CI.
  - `ml_project / tool` mas plan exige peer-review formal.
  - Escopo cresceu além do declarado em L0.
- **Trade-offs típicos:** mudar profile/tier (regenera matriz, custo de re-validação) vs spawn novo workspace com profile correto vs reduzir escopo da task atual.

---

## 2. Thresholds calibrados por tier (itens 5, 7, 8)

Source: `templates/_config/profile-matrix.md` (chaves `stop_points_calibration.item_5`, `item_7`, `item_8`). Em caso de divergência, `<SKILL_DIR>/scripts/profile-merge.py` é a fonte da verdade operacional.

| Item | experimental | tool | development | production |
|---|---|---|---|---|
| 5 — `paid_service` | warning, R$ 50 | hard, R$ 200 | hard, R$ 500 | hard, R$ 1000 |
| 7 — `over_eng` | warning | warning | hard | hard |
| 8 — `pii` | warning | hard | hard | hard+DPO |

Demais 9 stops (1, 2, 3, 4, 6, 9, 10, 11, 12) sempre `hard` em qualquer tier.

### 2.1 Modos de severidade

| Modo | Comportamento |
|---|---|
| `warning` | Agente avisa em prosa no output da sessão, segue trabalho com nota; **não bloqueia**. Não atualiza `status` do L1. Append em `history` opcional como `event: stop_point_warning`. |
| `hard` | Agente para, escreve menu A/B/C (template §3), atualiza L1 `status: BLOCKED_STOP_POINT`, espera resposta humana. |
| `hard+DPO` | `hard` + recomendação explícita "envolver DPO/legal antes de seguir" no menu. Status idem. |

---

## 3. Template de menu A/B/C padronizado

Disparo: agente em qualquer estágio ao detectar stop point com modo `hard` ou `hard+DPO`.

```markdown
# 🛑 STOP POINT — <id> (<descrição curta>)

## Resumo
<1-2 parágrafos descrevendo o que foi detectado e por que disparou>

## Trade-offs
- A) <opção A — descrição>
- B) <opção B — descrição>
- C) <opção C — geralmente "manter como está / escalar humano">

## Reversibilidade
- A: <reversível? como? a que custo?>
- B: <reversível? como? a que custo?>
- C: <reversível>

## Recomendação do agente
<A/B/C> + justificativa em 1 parágrafo, citando trade-offs e contexto do projeto (tier, profile, lessons aplicáveis).

## Ação humano

Responda no chat:
- "A" / "B" / "C" para escolher
- Texto livre para outra opção / pedir mais info

Aguardando resposta. L1 atualizado: `status: BLOCKED_STOP_POINT`.
```

Em modo `hard+DPO` adiciona linha extra logo após a recomendação:

> **Atenção LGPD:** envolver DPO/legal antes de seguir. Decisão técnica não substitui validação jurídica.

---

## 4. Update do L1 ao disparar

Sessão DEVE executar atomicamente (1 commit):

1. Append em `history`:
   ```yaml
   - at: "<ISO 8601 UTC>"
     event: "stop_point_triggered"
     stop_point_id: "<id>"
     note: "<texto curto descrevendo gatilho>"
   ```
2. Set `status: BLOCKED_STOP_POINT`.
3. Set `last_action: "stop point <id> disparado"` + `last_action_at: <ISO>`.
4. Set `next_action: "aguardando resposta humana ao menu A/B/C"`.
5. Commit atômico (`workspace: stop_point <id> disparado`). Pre-commit hook valida atomicidade L1↔outputs.

Status enum e schema vêm de `references/state-machine-schema.md`.

---

## 5. Resposta humana — protocolo de retomada

Humano responde no chat com `A`, `B`, `C` ou texto livre. Sessão:

1. Lê resposta.
2. Append em `history`:
   ```yaml
   - at: "<ISO 8601 UTC>"
     event: "stop_point_resolved"
     stop_point_id: "<id>"
     resolution: "A" | "B" | "C" | "custom"
     note: "<resumo da decisão humana>"
   ```
3. Set `status: IN_PROGRESS`.
4. Atualiza `last_action`/`next_action` conforme escolha.
5. Continua trabalho conforme opção escolhida.
6. **Spawn de ADR:** se a escolha implica decisão arquitetural (típico em stops 1, 2, 3, 6, 10), spawnar `docs/decisions/NNNN-<slug>.md` — **apenas em fase 02 design**. Em outras fases, anotar no `decisions-pending.md` da fase 02 do próximo workspace ou registrar como tech debt.

---

## 6. Custom stop points (D3)

Override em `.icm-profile.local.yaml` campo `custom_stop_points` (schema completo em `templates/_config/profile-matrix.md`). Lista adicional projeto-específica. Cada item exige `id`, `description`, `threshold` (dict tier→modo).

Bootstrap (`<SKILL_DIR>/scripts/profile-merge.py`) valida schema e bootstrap inclui custom stops em `recon-report.md` para visibilidade. Sessões consultam tanto a lista canônica quanto `custom_stop_points` do profile efetivo.

---

## 7. Estágios onde stop points são esperados

Tabela de aplicabilidade típica. `n/a` significa que o estágio raramente dispara aquele stop pela natureza do trabalho.

| Estágio | Stops mais comuns |
|---|---|
| 00 recon | 11 (`workspace_corrupt`), 12 (`profile_mismatch`) |
| 01 discovery | 1 (`stack`), 3 (`external_api`), 5 (`paid_service`), 8 (`pii`) |
| 02 design | 1, 2 (`db`), 4 (`new_dep`), 5, 6 (`irreversible`), 7 (`over_eng`), 8, 10 (`adr_drift`) |
| 03 wave_planner | n/a (wave-planner é determinístico — gap-fill se aplicável) |
| 04 implementation_waves | 4, 6, 7, 9 (`prod_migration`), 10 |
| 05 verification | n/a |
| 06 review | 7, 8, 10 |
| 07 merge | 6, 9 |
| 08 feedback_intake | n/a (fase 08 é análise + decisão A/B/C de iteração; stops detectados aqui rolam pro próximo workspace via saída C) |

A tabela é orientativa. Qualquer estágio pode disparar qualquer stop se o sinal aparecer — não há whitelist enforçada.
