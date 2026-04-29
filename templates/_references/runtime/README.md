# templates/_references/runtime/ — convention note

Bootstrap (`scripts/bootstrap.py`) copia refs canônicos de
`<skill_root>/references/<file>.md` para `<workspace>/_references/runtime/<file>.md`
no scaffold. Lista de refs em `bootstrap._scaffold_workspace_dirs.runtime_refs`.

Este diretório existe **vazio** apenas como placeholder convencional. Não
adicione cópias aqui — fonte canônica é `<skill_root>/references/`.

Workspace pós-bootstrap é self-contained: sessões leem do
`<workspace>/_references/runtime/` (cópias) e nunca cruzam para `<skill_root>/references/`
(canonical). Bootstrap é o único bridge entre os dois.

Por que esse design:
1. Workspace portable — pode ser zipado e reaberto noutra máquina sem skill.
2. Skill pode evoluir sem quebrar workspaces antigos (cópia é frozen).
3. Sessões dentro do workspace têm read order determinístico.

Ver `<skill_root>/scripts/bootstrap.py` linha ~430 (lista `runtime_refs`).
