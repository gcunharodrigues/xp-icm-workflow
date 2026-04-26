<!--
Fixture com ambiguidade: duas tasks tocam arquivos diferentes dentro do
mesmo diretorio (src/payments/), sem sobreposicao exata em files_touched.

Comportamento esperado da fase deterministica:
  - Particiona normalmente (nao serializa, pois nao ha intersecao exata).
  - Registra entrada em ambiguities-resolved.md indicando que LLM deve confirmar.
  - total_tasks=2 total_waves=1 ambiguities>=1.
-->

## Task payments-charge: Payments Charge

### 4-block
O QUE / COMO / NAO QUERO / VALIDACAO

### Files touched
- src/payments/charge.ts

### Depends on
- nenhum

## Task payments-refund: Payments Refund

### 4-block
O QUE / COMO / NAO QUERO / VALIDACAO

### Files touched
- src/payments/refund.ts

### Depends on
- nenhum
