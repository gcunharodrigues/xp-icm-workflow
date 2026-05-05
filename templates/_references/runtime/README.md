# templates/_references/runtime/ — convention note

Bootstrap (`scripts/bootstrap.py`) copies canonical refs from
`<skill_root>/references/<file>.md` to `<workspace>/_references/runtime/<file>.md`
during scaffold. Ref list in `bootstrap._scaffold_workspace_dirs.runtime_refs`.

This directory exists **empty** as a conventional placeholder only. Do not
add copies here — the canonical source is `<skill_root>/references/`.

Post-bootstrap workspace is self-contained: sessions read from
`<workspace>/_references/runtime/` (copies) and never cross into `<skill_root>/references/`
(canonical). Bootstrap is the only bridge between the two.

Why this design:
1. Portable workspace — can be zipped and reopened on another machine without the skill.
2. Skill can evolve without breaking old workspaces (copy is frozen).
3. Sessions inside the workspace have a deterministic read order.

See `<skill_root>/scripts/bootstrap.py` line ~430 (list `runtime_refs`).
