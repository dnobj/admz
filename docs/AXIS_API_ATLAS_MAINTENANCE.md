# Axis API Atlas — maintenance has moved

The Axis API catalog/knowledge/capabilities are now maintained in the standalone
**`axis-api-atlas`** repository (the single source of truth — see
[ADR-0029](specification/decisions/0029-axis-api-atlas-as-maintained-reusable-asset.md)).
ADMZ consumes it as a dependency (`requirements.txt` → `axis-api-atlas`) and no
longer carries an in-tree copy.

- **Discover / update / verify the API + capability data** (with access to live
  Axis devices): see `MAINTAINING.md` in the `axis-api-atlas` repo and run that
  repo's `axis-atlas-refresh` tool. Changes land there, then ADMZ bumps the
  dependency version.
- **Why / how the swap works:** ADR-0027 (control families / collectors) and
  ADR-0029 (Atlas as a maintained, reusable asset) in `docs/specification/decisions/`.
