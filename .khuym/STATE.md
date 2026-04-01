STATUS: swarming-complete
FEATURE: ids-repo-installable-full-stack-packaging
SKILL: swarming
PHASE: reviewing-ready

EPIC:
- Replan epic: `ids_ml_new-urzq`
- Source review root: `ids_ml_new-axd0`

ARTIFACTS_WRITTEN:
- `history/ids-repo-installable-full-stack-packaging/discovery.md`
  - appended `Planning Addendum: Review-Followup Replan`
- `history/ids-repo-installable-full-stack-packaging/approach.md`
  - appended `Replan Addendum After Blocked Validation`

REPLANNED_BEAD_SET:
- `ids_ml_new-x1p9` install metadata + canonical entrypoint surface
- `ids_ml_new-d5ae` ML packaging topology + package defaults
- `ids_ml_new-qq0f` deploy/docs interpreter contract convergence
- `ids_ml_new-z0pb` runtime-scoped path-default boundary + runtime adopters
- `ids_ml_new-bt3x` explicit realtime inferencer/schema seam
- `ids_ml_new-m8h0` trust-boundary hardening + final installed bootstrap proof
- `ids_ml_new-zpih` proof-helper dedupe

REPLANNED_DEPENDENCY_SPINE:
- `ids_ml_new-x1p9 -> ids_ml_new-d5ae -> ids_ml_new-qq0f -> ids_ml_new-z0pb -> ids_ml_new-bt3x -> ids_ml_new-m8h0 -> ids_ml_new-zpih`

NOTES:
- The original validation blocker was structural, not architectural discovery.
- Replan added one explicit install-surface owner bead and moved final proof ownership explicitly onto `ids_ml_new-m8h0`.
- The replanned wave validated cleanly as a linear spine rooted at `ids_ml_new-x1p9`.
- During validation, `beads.db` was found malformed and rebuilt cleanly from a repaired `.beads/issues.jsonl`; `br sync --status` then returned `dirty_count=0`, `jsonl_newer=false`, `db_newer=false`.
- `br show ids_ml_new-x1p9` and `br show ids_ml_new-urzq` now resolve to the intended task/epic after the repair.
- Swarm completed after a final rescue pass on `ids_ml_new-zpih` in the main session because the rescue worker hit a usage cap before it could claim the last P3 bead.
- Final triage for `ids_ml_new-urzq` reports `open_count=0`, `actionable_count=0`, `in_progress_count=0`.

NEXT:
- Invoke `khuym:reviewing`.
