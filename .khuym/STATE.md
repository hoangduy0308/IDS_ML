STATUS: compounding-complete
FEATURE: repo-structure-rationalization
SKILL: compounding
SOURCE_EPIC: ids_ml_new-br4g
CLEANUP_EPIC: ids_ml_new-1w7v
FINAL_RESIDUAL_CLEANUP_EPIC: ids_ml_new-z8pp
OPEN_REVIEW_CLEANUP_BEADS: none
LATEST_REVIEW_RERUN: clean

REVIEW_RERUN_SUMMARY:
- No live P1 remains after manual validation of the wrapper surfaces.
- The rerun review still found P2/P3 work in four areas: ids.core boundary, docs lanes, console security hardening, and wrapper smoke coverage.
- A dedicated cleanup epic `ids_ml_new-1w7v` carried that follow-up work and is now closed.
- A final residual cleanup epic `ids_ml_new-z8pp` addressed the remaining neutral seam, restore authenticity, and docs/wrapper-smoke follow-ups and is now closed.
- A final fresh review pass after those cleanup waves found no new issues, and the full test suite passed on the current worktree.

SUMMARY:
- The original rerun blocker and first follow-up wave are complete.
- The second cleanup wave is complete and full-suite verification passed afterward.
- The final residual cleanup wave is complete and `python -m pytest tests -q` passed at HEAD `09877ad`.
- No open review or cleanup beads remain.
- Fresh review rerun result: clean.
- Latest full-suite verification on the current worktree: `337 passed`.

ACTIVE_WORKERS:
- none

LAST_COMPOUNDING_RUN:
- Date: 2026-03-31
- Learnings file: history/learnings/20260331-repo-structure-wrapper-contracts.md
- Critical promotions: 2
- Notes: refreshed existing feature learnings with boundary-normalization and path-containment rules after the final clean review rerun
