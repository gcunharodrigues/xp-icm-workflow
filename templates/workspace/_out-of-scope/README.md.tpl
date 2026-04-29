# OUT-OF-SCOPE — workspace {{WORKSPACE}}

> Knowledge base de feature requests rejeitadas. 1 arquivo por conceito,
> NÃO por issue. Múltiplas requests para o mesmo conceito agrupadas.
>
> Formato canônico: `_references/runtime/out-of-scope-kb.md`.

## Convenção

```
_out-of-scope/
├── README.md            (este arquivo)
├── <conceito-1>.md
├── <conceito-2>.md
└── ...
```

Cada `<conceito>.md` contém:

```markdown
# {Concept Name}

Curta descrição do que é o conceito + decisão de não implementar.

## Por que está fora de escopo

Razão durável: project scope/philosophy, technical constraint, ou strategic
decision. Não razão temporária ("muito ocupado agora").

## Prior requests

- session NNN fase XX — "summary"
- session NNN fase XX — "summary"
```

## Quando consultar

- **Stage 02 (design):** se `iteration > 0`, ler todos arquivos antes de
  propor design. Surface match ao humano.
- **Stage 08 (feedback intake):** durante triage de feedback novo, check
  matching antes de classificar.

## Quando atualizar

- **wontfix de enhancement:** append em arquivo existente OU criar novo.
- **Reconsideração:** delete arquivo, issue prossegue triage normal.
