# Deep modules + deletion test (architecture review — stage 02)

> Doc canônico para review de arquitetura no stage 02 (design). Princípios
> inspirados em [mattpocock/skills/engineering/improve-codebase-architecture]
> e John Ousterhout, *A Philosophy of Software Design*.
>
> Use durante stage 02 quando design envolve módulos novos ou refactor de
> módulos existentes. Não obrigatório para bug fix puro.

## Conceito — Deep modules

**Deep module:** interface pequena, implementação rica.

```
+-----------+
|  API      |   <- pequena (poucos métodos, contratos claros)
+-----------+
| Implem    |
| ricamente |   <- complexidade aqui (validação, cache, retry, fallback)
| oculta    |
+-----------+
```

**Shallow module:** interface grande, implementação fina (passa-tudo).

| Aspecto | Deep | Shallow |
|---|---|---|
| Métodos públicos | 1-5 | 10+ |
| Tipos exportados | 1-2 (input/output) | muitos (estado interno vazado) |
| Contrato | "faça X" | "configure A, B, C, depois faça X" |
| Custo cognitivo p/ caller | baixo | alto |

Princípio: **complexidade tem que ir pra algum lugar**. Em deep modules,
fica oculta atrás da API; o caller paga preço pequeno. Em shallow modules,
a complexidade vaza para todos os callers.

## Os 3 critérios para classificar um módulo

| Critério | Pergunta | Sinal verde | Sinal vermelho |
|---|---|---|---|
| **Interface mínima** | Quantos métodos públicos? Quantos parâmetros por método? | ≤5 métodos, ≤4 params | 10+ métodos, params explodidos |
| **Information hiding** | Caller precisa conhecer detalhes internos pra usar corretamente? | Não — caller passa input, recebe output | Sim — caller precisa configurar estado, ordem de chamadas |
| **Single responsibility** | Módulo faz **uma** coisa? | Sim — nome do módulo descreve em 5 palavras | Não — nome usa "and"/"or" ou termina em "Util"/"Helper" |

Falha em qualquer critério → módulo é shallow ou multi-responsibility.

## Deletion test (heurística complementar)

> "Se eu deletasse este módulo, qual o blast radius? Se a resposta é
> '~3 callers atualizam imports', o módulo é deep. Se a resposta é
> 'metade do app quebra', o módulo é shallow."

Aplicar mentalmente em cada módulo novo do design:

1. Conte callers do módulo (`grep -r "from <module>"`).
2. Estime quanto cada caller depende de comportamento interno (não só
   da assinatura pública).
3. Se >30% dos callers precisam adaptar lógica em vez de só renomear
   imports → módulo está vazando estado/contrato → revise.

## Checklist para stage 02

Para cada módulo novo introduzido pelo design (`docs/decisions/NNNN.md`
ou `stages/02_design/output/plan.md`):

- [ ] **Interface mínima:** API pública listada explicitamente. ≤5 métodos.
- [ ] **Information hiding:** docstring da API menciona apenas input/output;
      detalhes internos (cache layer, retry policy, etc) NÃO aparecem na API.
- [ ] **Single responsibility:** nome do módulo descreve a responsabilidade
      em uma frase sem conjunções.
- [ ] **Deletion test:** estimativa de blast radius < 30% dos callers
      precisarem adaptar lógica (vs renomear imports).
- [ ] **Alternative considered:** ADR (`docs/decisions/NNNN.md`) menciona ao
      menos 1 alternativa que foi rejeitada (alinhado com Design It Twice).

Se ≥2 itens falham: voltar à prancheta antes de prosseguir para stage 03.

## Exemplos curtos

### Deep — `RetryableHTTPClient`

```python
# API pública: 1 método. Cache, backoff, jitter, circuit breaker invisíveis.
class RetryableHTTPClient:
    async def request(self, method: str, url: str, *, body: bytes | None = None) -> Response:
        ...
```

Caller só passa method/url. Não precisa saber sobre policies internas.

### Shallow — `HTTPClientUtil`

```python
# API pública: 8 métodos. Caller orquestra tudo.
class HTTPClientUtil:
    def configure_retry(self, max_attempts: int, backoff_ms: int) -> None: ...
    def configure_circuit_breaker(self, threshold: int) -> None: ...
    def configure_cache(self, ttl: int, max_size: int) -> None: ...
    def request(self, ...) -> Response: ...
    def parse_response(self, raw: bytes) -> dict: ...   # já deveria estar dentro
    def log_request(self, ...) -> None: ...             # cross-cutting, vaza
    def get_metrics(self) -> dict: ...                  # outro módulo
    ...
```

Caller precisa configurar tudo, ordem importa, estado vaza. Refactorar.

## Quando pular este check

- Bug fix puro (não introduz módulo novo).
- Módulo trivial single-function (ex: `slugify(s: str) -> str` solo num arquivo).
- Refactor de renomeação ou movimentação sem mudança de API.

## Integração com outros docs

- `references/adr-format.md` — gate dos 3 critérios para ADRs (escala diferente,
  mas espírito aliado: forçar trade-off explícito).
- `references/design-it-twice.md` — exigência de explorar 2 designs paralelos
  para módulos core. Deep modules emerge naturalmente do exercício.
- `templates/workspace/stages/02_design/CONTEXT.md.tpl` — checklist deste doc
  é executado durante design.

## Referências externas

- John Ousterhout, *A Philosophy of Software Design*, capítulos 4 (Modules
  Should Be Deep) e 5 (Information Hiding).
- mattpocock/skills/engineering/improve-codebase-architecture — fonte de
  inspiração do "deletion test" como heurística operacional.
