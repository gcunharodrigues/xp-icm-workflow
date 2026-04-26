<!--
Fixture com ciclo: alpha -> beta -> gamma -> alpha.
Wave Planner deve abortar com WavePlannerError("cycle detected: ...").
-->

## Task alpha: Alpha

### 4-block
O QUE / COMO / NAO QUERO / VALIDACAO

### Files touched
- src/alpha.ts

### Depends on
- gamma

## Task beta: Beta

### 4-block
O QUE / COMO / NAO QUERO / VALIDACAO

### Files touched
- src/beta.ts

### Depends on
- alpha

## Task gamma: Gamma

### 4-block
O QUE / COMO / NAO QUERO / VALIDACAO

### Files touched
- src/gamma.ts

### Depends on
- beta
