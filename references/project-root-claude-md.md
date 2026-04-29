# `<project_root>/CLAUDE.md` — Contrato canônico

> Doc canônico do arquivo `CLAUDE.md` na raiz do projeto, gerenciado pela skill
> `xp-icm-workflow`. Cobre: contrato com `/init`, brownfield, multi-workspace,
> atomicidade, recovery, versionamento.

## Propósito

`<project_root>/CLAUDE.md` é o **dashboard externo** do estado dos workspaces ICM
ativos. Claude Code carrega esse arquivo automaticamente em qualquer sessão
fresh aberta no project root, eliminando a necessidade de copy/paste manual de
prompts KICKOFF entre sessões.

## Estrutura — duas regiões

```
# CLAUDE.md — <project_name>

This file provides guidance ...

<!-- ICM-START -->
## Active ICM Workspaces
<bloco por workspace ativo>
...
<!-- ICM-END -->

<conteúdo livre — preenchido por /init ou pelo usuário>
```

- **Região ICM** (entre `<!-- ICM-START -->` e `<!-- ICM-END -->`) — exclusiva
  da skill. Bootstrap insere; handoff atualiza; recovery wizard regenera.
- **Região codebase** (fora dos marcadores) — livre. Bootstrap nunca toca.
  Pode ser preenchida por `/init` futuro ou manualmente.

## Quando é escrito

| Evento | Função | Comportamento |
|---|---|---|
| Bootstrap de workspace novo | `bootstrap.py:_render_project_claude_md` | Adiciona bloco do novo workspace à região ICM. Brownfield: preserva resto byte-a-byte. |
| Handoff de transição de stage | `handoff.py:update_project_claude_md` | Atualiza só o bloco do workspace dono da transição. Demais blocos intactos. |
| Saída A (close), Saída C (spawn) | `handoff.py:remove_workspace_block` | Remove o bloco do workspace que finalizou. Se zero workspaces ativos restam, `deactivate_project_claude_md` substitui região por mensagem "nenhum ativo". |
| Recovery wizard | `recovery-wizard.py` (Plan A) | Regenera bloco a partir do L1 quando detecta `CLAUDE_MD_ROOT_STALE` ou `CLAUDE_MD_ROOT_MISSING`. |

## Algoritmo de inserção idempotente (brownfield)

1. **Arquivo não existe:** criar a partir de
   `templates/project_root/CLAUDE.md.tpl` com a região ICM completa.
2. **Arquivo existe COM marcadores:** substituir conteúdo apenas entre
   `<!-- ICM-START -->` e `<!-- ICM-END -->`. Bytes fora dos marcadores
   preservados intactos.
3. **Arquivo existe SEM marcadores (brownfield):** localizar primeiro `^# `
   (título principal). Inserir região ICM logo após o título e linhas em branco
   imediatas. Demais conteúdo preservado.

## Multi-workspace (G3)

Mais de um workspace pode estar ativo simultaneamente
(`status != COMPLETED`). A região ICM lista um bloco por workspace. Ordem:
crescente por workspace ID.

Exemplo:

```markdown
<!-- ICM-START -->
## Active ICM Workspaces

> ...

### Workspace `042-feat-auth` · profile=app_web_backend · tier=development
- Stage atual: `03` (03_wave_planner) ...
- Read order: workspaces/042-feat-auth/CLAUDE.md → ...

---

### Workspace `043-payment-gateway` · profile=app_web_backend · tier=production
- Stage atual: `06` (06_review) ...
- Read order: workspaces/043-payment-gateway/CLAUDE.md → ...

---

**Skill:** ... · **Recovery:** ...
<!-- ICM-END -->
```

## Saídas da fase 08 e CLAUDE.md root

| Saída | Função | Estado pós-saída |
|---|---|---|
| **A** (close) | `remove_workspace_block(workspace)` | Bloco do workspace removido. Se era o último: região ICM substituída por "nenhum ativo + rode /init". |
| **B** (restart fase X, iteration++) | `update_project_claude_md(workspace, stage_target=X, iteration=N+1, ...)` | Bloco atualizado mostrando nova fase e iteration. |
| **C** (spawn novo workspace) | `remove_workspace_block(workspace)` na sessão A; bootstrap em sessão B adiciona bloco novo | Bloco do workspace dono removido. Sessão B (separada) bootstrappa novo workspace e adiciona seu bloco. |

## Contrato com `/init` (G4)

`/init` do Claude Code regenera CLAUDE.md a partir do código do projeto. **Não
conhece os marcadores ICM por padrão.**

**Regra durante workspace ativo:** **NÃO invoque `/init`**. Warning explícito
fica na própria região ICM. Razão: `/init` pode sobrescrever a região ICM,
quebrando signaling.

**Após Saída A do último workspace ativo:** região ICM é substituída por
mensagem "nenhum ativo + rode /init". A partir desse ponto, rodar `/init` é
seguro — preencherá a região codebase com informações do código construído.

**Regra para `/init` consciente da skill (futuro):** uma versão futura do
`/init` pode procurar pelos marcadores e preservá-los. Marcadores são
sentinelas estáveis para qualquer ferramenta que queira respeitar a região.

**Tier 3 (future work):** PreToolUse hook que bloqueia invocação de `/init`
durante workspace ativo. Fora do escopo da v3.1.0.

## Atomicidade (G15)

Todas as escritas em `<project_root>/CLAUDE.md` usam padrão write-tmp + fsync +
rename:

```python
tmp = claude_md.with_suffix(".md.tmp")
tmp.write_text(content, encoding="utf-8")
fd = os.open(str(tmp), os.O_RDONLY)
os.fsync(fd)
os.close(fd)
tmp.replace(claude_md)
```

Crash mid-write não corrompe o arquivo original — `tmp.replace` é atômico em
POSIX e Windows (NTFS).

## Concorrência (G12)

Duas sessões abertas no mesmo project_root simultaneamente podem disparar
`handoff.py` concorrente. Mitigação:

- Workspace branch isola: cada sessão atua em sua workspace branch.
- Commit atômico do git previne escrita simultânea no mesmo arquivo.
- Em caso de conflito, segunda escrita falha com erro git → sessão aborta com
  `BLOCKED_ERROR`.
- Recovery wizard (`CLAUDE_MD_ROOT_STALE`) detecta e regenera.

## Versionamento (G13)

`CLAUDE.md` no project root é versionado em **workspace branch** (não na
main) durante o ciclo de cada workspace. A whitelist do
`templates/.git-hooks/pre-commit` libera o arquivo (R3.3 expandida em G6).

Após Saída A, opções para preservar o `CLAUDE.md` em main:

1. Merge workspace branch → main (preserva CLAUDE.md atual).
2. Rodar `/init` em main para regenerar a região codebase a partir do código
   atual (a região ICM já estará vazia — "nenhum ativo").

A divergência entre workspace branch (CLAUDE.md atualizado) e main (CLAUDE.md
desatualizado ou ausente) é **intencional** e segura — workspace branch é
layer de state efêmero por design ICM.

## Encoding (G11)

A região ICM gerada pela skill é em **PT-BR** (consistente com restante do
skill). A região codebase fora dos marcadores é livre — qualquer idioma. Sem
mistura forçada.

## Recovery (G5)

Inconsistências entre L1 e CLAUDE.md root são detectadas pelo recovery wizard:

- `CLAUDE_MD_ROOT_STALE` — `<project_root>/CLAUDE.md` mostra `stage_atual`
  diferente do `L1.stage_atual` para algum workspace ativo. Causa típica:
  sessão crash sem chamar handoff.
- `CLAUDE_MD_ROOT_MISSING` — workspace tem `L1.status=IN_PROGRESS` mas não
  aparece como bloco na região ICM do CLAUDE.md root.

Recovery (Plan A): regenerar a região ICM completa a partir do `.index.md` +
L1 de todos workspaces ativos.

## Templating (G17)

O template `templates/project_root/CLAUDE.md.tpl` é usado **apenas pelo
bootstrap inicial** quando o arquivo não existe. Updates subsequentes (handoff,
recovery) escrevem markdown direto via funções helper, sem usar `{{}}`
placeholders. Isso evita confusão entre templating de boostrap e regeneração
runtime.
