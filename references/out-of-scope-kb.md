# OUT-OF-SCOPE Knowledge Base

Adaptado de [mattpocock/skills/skills/engineering/triage/OUT-OF-SCOPE.md].

`<workspace>/_out-of-scope/` armazena registros persistentes de feature
requests rejeitadas. Dois propósitos:

1. **Memória institucional** — por que feature foi rejeitada, raciocínio
   preservado quando issue fecha.
2. **Deduplicação** — quando issue nova bate com rejeição prior, skill
   surfaces decisão prévia em vez de re-litigar.

## Estrutura

```
<workspace>/_out-of-scope/
├── README.md            (template explicando convenção)
├── dark-mode.md
├── plugin-system.md
└── graphql-api.md
```

**1 arquivo por conceito**, NÃO por issue. Múltiplas issues pedindo a mesma
coisa são agrupadas sob 1 arquivo.

## Formato

Estilo relaxed/readable — short design doc, não database entry.

```markdown
# Dark Mode

Este projeto não suporta dark mode ou theming.

## Por que está fora de escopo

Rendering pipeline assume single color palette em `ThemeConfig`. Suportar
multiple themes exigiria:
- Theme context provider wrapping component tree
- Per-component theme-aware style resolution
- Persistence layer para user theme preference

Mudança arquitetural significativa que não alinha com foco em content authoring.
Theming é concern downstream — embed/redistribute output.

```ts
interface ThemeConfig {
  colors: ColorPalette;  // single palette, build-time
  fonts: FontStack;
}
```

## Prior requests

- session 042 fase 08 — "Add dark mode support"
- session 087 fase 02 — "Night theme accessibility"
- session 134 fase 01 — "Dark theme option"
```

## Naming

- Short, descriptive kebab-case: `dark-mode.md`, `plugin-system.md`,
  `graphql-api.md`.
- Recognizable enough — pessoa browsing diretório entende o que foi rejeitado
  sem abrir arquivo.

## Razão deve ser substantiva

Não "we don't want this" mas **por quê**. Boas razões referenciam:

- Project scope/philosophy ("Foco em X; theming é concern downstream")
- Technical constraints ("Suportar isso exigiria Y, conflita com Z")
- Strategic decisions ("Escolhemos A em vez de B porque...")

Razão deve ser **durável**. Evite circumstance temporária ("muito ocupado
agora") — isso é deferral, não rejection real.

## Quando consultar `_out-of-scope/`

**Stage 02 (design):** se workspace tem `iteration > 0`, ler todos
`_out-of-scope/*.md`. Se design proposto bate com rejeição prévia, surface ao
humano:
> "Esta proposta é similar a `_out-of-scope/dark-mode.md` — rejeitamos antes
> porque [reason]. Ainda concorda?"

Humano pode:
- **Confirmar** — issue nova adicionada à "Prior requests", workspace
  prossegue sem incluir o item no design.
- **Reconsiderar** — arquivo deletado/atualizado, design prossegue normal.
- **Disagree** — issues relacionadas mas distintas, prosseguir.

**Stage 08 (feedback intake):** durante triage, antes de classificar feedback
novo, check matching com `_out-of-scope/` files.

## Quando escrever em `_out-of-scope/`

Apenas quando **enhancement** (não bug) é rejeitada como `wontfix`:

1. Maintainer/agent decide feature é fora de escopo.
2. Check se arquivo correspondente já existe.
3. Se sim: append nova entry em "Prior requests".
4. Se não: criar arquivo novo com concept name + decision + reason + first prior request.
5. Post mensagem no log explaining decisão + mencionando arquivo.
6. Workspace fecha com Saída A (close), L1 status=COMPLETED.

## Quando atualizar/remover

Se decisão muda (não está mais out-of-scope):
- Delete arquivo `_out-of-scope/<conceito>.md`.
- Skill não precisa reabrir issues antigas — são historical records.
- Issue nova que triggered reconsideração prossegue triage normal.

## Match de conceito (não keyword)

"Night theme" matches `dark-mode.md` porque concept similarity. Mecanismo:
agent lê todos arquivos da kb, compara semântica do feedback novo com cada
concept. Se match: surface ao humano.

Não é keyword matching estrito — não exige termos idênticos.
