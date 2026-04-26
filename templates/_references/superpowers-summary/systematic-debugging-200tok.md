---
name: systematic-debugging-200tok
source_skill: superpowers:systematic-debugging
source_version: "5.0.0"
purpose: Achar causa-raiz antes de qualquer fix; método científico em quatro fases.
---

# Systematic Debugging — sumário 200tok

## Quando aplicar
- Qualquer bug, teste falhando, comportamento inesperado, falha de build, problema de integração.
- **Especialmente** sob pressão de tempo, quando "um fix rápido" parece óbvio, ou após múltiplas tentativas falhas.

## Lei de ferro
Sem investigação de causa-raiz, sem fix. Sintoma corrigido sem causa entendida = falha.

## Como aplicar (4 fases, em ordem)

1. **Causa-raiz**
   - Leia mensagens de erro e stack traces inteiros.
   - Reproduza consistentemente; se não reproduz, junte mais dados, não chute.
   - Cheque mudanças recentes (git diff, deps novas, config).
   - Em sistemas multi-componente: instrumente cada fronteira (log entrada/saída/env) antes de propor fix. Identifique qual camada quebra.
   - Trace o dado para trás até a origem do valor ruim. Conserte na fonte, não no sintoma.

2. **Padrão**
   - Ache exemplo funcionando similar no codebase.
   - Compare por completo (sem skim) com referência. Liste cada diferença.
   - Mapeie dependências/assumptions.

3. **Hipótese**
   - Formule uma hipótese específica por escrito ("X é causa porque Y").
   - Teste com a menor mudança possível, uma variável por vez.
   - Funcionou? Fase 4. Não? Nova hipótese — não empilhe fixes.

4. **Implementação**
   - Crie teste falhando que reproduz (use TDD).
   - Um único fix endereçando a causa-raiz. Sem "while I'm here".
   - Verifique: teste passa, nada mais quebrou.
   - **3+ fixes falharam? Pare e questione a arquitetura** com o humano — não tente o 4º.

## Sinais de sucesso
Causa explicável em uma frase, teste reproduzindo o bug, fix mínimo, demais testes verdes.

## Red flags
"Quick fix por agora", "provavelmente é X", múltiplas mudanças simultâneas, pular o teste, "mais uma tentativa" após 2 falhas.

## Escape hatch
Se o caso exigir backward tracing profundo, defense-in-depth multi-camada, ou condition-based waiting → invocar `superpowers:systematic-debugging` formal (traz `root-cause-tracing.md`, `defense-in-depth.md`, `condition-based-waiting.md`).
