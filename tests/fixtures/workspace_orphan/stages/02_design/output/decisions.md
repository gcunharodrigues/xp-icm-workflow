# Design decisions — fixture orfa

Output presente no FS mas L1 esta `IN_PROGRESS` mid-design.
Ilustra atomicidade quebrada: o output existe mas a transicao
para `02_completed` nunca foi commitada.

## Decisao 1

Stack: FastAPI + Postgres.
