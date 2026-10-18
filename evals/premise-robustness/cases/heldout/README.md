# Held-out set (not yet authored)

This directory will hold the held-out evaluation cases. Per PRD 5.5, the
held-out set is authored **in a separate pass from development** -- different
session, independently reviewed -- with scenario/template families disjoint
from `cases/dev/`. Prompts are frozen before held-out authoring begins.

Isolation rules:

1. Cases are listed in `manifest.json` with per-case content hashes.
2. `manifest.json` is committed; any change to a held-out case requires a
   manifest update, which is itself a reviewed change.
3. The runner refuses `--split heldout` while the manifest is a placeholder.
4. Dev runs structurally cannot see this directory (the runner only globs
   `cases/<split>/`).
5. Authors and coding agents working on development must not read these
   files -- the directory guard is a backstop, not the mechanism.

Until the manifest is frozen, `manifest.json` stays a placeholder and
held-out runs are refused.
