# Spike Findings: ids_ml_new-i7oa.3

**Date**: 2026-04-04
**Feature**: ids-console-telegram-settings-and-deploy-readiness
**Phase**: Phase 4 - Review closure and release-proof hardening
**Question**: Can Phase 4 safely repair `ops/build_release.sh` by switching to a tracked or allowlisted export surface within the existing tarball plus `install.sh` model from D4, without introducing a broader packaging redesign?

## Verdict

YES

## Why

- The ship blocker lives at the export boundary, not in the tarball plus `install.sh` model itself.
- A tracked or explicit allowlisted export surface prevents ignored and untracked local files from shipping by construction instead of growing a brittle manual exclude list.
- The phase already contains the right proof surface to verify this contract, so no extra phase is needed.

## Constraints To Carry Into Execution

- Keep the existing tarball plus `install.sh` flow from D4.
- Treat `wheelhouse/` as the only acceptable generated post-export artifact layered onto the staged release surface.
- Add archive-level proof that ignored or untracked local files are absent from the produced bundle.

## Execution Implication

- `ids_ml_new-i7oa.1` remains the correct implementation bead as long as it stays focused on the safe export surface and its regression proof.

