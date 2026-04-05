---
date: 2026-04-05
feature: ids-multiclass-two-stage-runtime-contract
categories: [failure, decision, pattern]
severity: critical
tags: [runtime, composite-bundle, review, testing, validation, fail-closed]
---

# Learning: Realtime Composite Contract Tests Must Exercise A Real Composite Inferencer

**Category:** failure
**Severity:** critical
**Tags:** [testing, runtime, composite-bundle, realtime, review]
**Applicable-when:** Adding enrichment or second-stage scoring to a runtime path where the later stage can require a strict superset of the first-stage feature columns

## What Happened

The first runtime review pass found that `ids/runtime/realtime_pipeline.py` built its micro-batch frame from stage-1 aligned columns only. That looked fine under the existing unit test because the test used a dummy inferencer that never tried to align a real stage-2 feature schema. In production, though, the composite runtime path uses `IDSInferencer`, which aligns stage 2 against its own feature file and fails if stage-2-only columns are absent.

The result was a real mismatch between test evidence and production behavior. A composite bundle whose stage-2 schema added even one source-only feature would pass the suite and still fail at runtime when realtime flushing invoked the actual inferencer.

The fix was not just changing the implementation to preserve both `source_record` and canonical stage-1 aligned fields in the realtime frame. The important part was replacing the fake composite inferencer test with a real `IDSInferencer` wired to a real composite bundle fixture whose stage-2 feature schema was a strict superset. Only then did the test prove the contract that production actually depends on.

## Root Cause / Key Insight

For multi-stage runtime contracts, a dummy inferencer can prove output shape while completely missing feature-alignment seams. If the real runtime behavior depends on loading feature files and aligning columns, then the regression test must use the real inferencer and a realistic composite manifest. Otherwise the test is only proving a mock protocol, not the production contract.

## Recommendation for Future Work

When review or execution touches any runtime path that feeds a composite or staged model:

1. Build at least one regression test around the real inferencer/config loader, not only a fake scorer.
2. Make the test fixture's later-stage schema a strict superset of stage 1 whenever that is a supported contract.
3. Treat "passes with dummy inferencer" as insufficient evidence for feature-alignment safety.
4. If the runtime batch frame is rebuilt from validated records, preserve both canonical aligned fields and any source fields needed by later stages unless the contract explicitly forbids them.

Reference implementation: `tests/runtime/test_ids_realtime_pipeline.py::test_run_pipeline_stream_file_mode_emits_family_enrichment_for_composite_bundle` after commit `107f9e3`.

---

# Learning: Manifest Safety Flags Must Assert Semantic Falsehood, Not Only Boolean Shape

**Category:** failure
**Severity:** critical
**Tags:** [validation, manifests, safety-flags, fail-closed, model-bundle]
**Applicable-when:** A manifest or config contract uses boolean capability flags to prohibit unsafe override seams

## What Happened

The composite bundle validator originally checked that the six override-control flags in the inference contract were booleans. Review caught that this was weaker than the intended contract: a manifest could set one of those flags to `true`, still satisfy the type check, and reopen an external override seam that the design explicitly banned.

That meant the manifest was structurally valid while semantically unsafe. The issue only became closed after validation changed from "is this field a bool?" to "this field must exist, be a bool, and be false," and tests were added to mutate each flag to `true` and prove the bundle is rejected.

## Root Cause / Key Insight

Safety booleans are not ordinary typed metadata. They encode a security or compatibility invariant. Type validation alone is not enough; the validator must assert the exact allowed value. Otherwise the codebase has a manifest that is syntactically valid and operationally forbidden at the same time.

## Recommendation for Future Work

For any manifest field whose purpose is "this unsafe thing must never be allowed":

1. Validate both type and required value in one helper.
2. Add one regression test per flag that flips the value to the forbidden state.
3. Use error messages that describe the reopened seam plainly so review and operators can understand the failure.
4. Treat a naked `_require_bool()` on a safety flag as suspicious during review.

Reference implementation: `_require_false_bool()` in `ids/core/model_bundle.py` and `test_load_model_bundle_manifest_rejects_composite_external_override_flags()` in `tests/core/test_ids_model_bundle.py` after commit `284d74c`.

---

# Learning: Additive Enrichment Was The Right Runtime Rollout Shape

**Category:** decision
**Severity:** standard
**Tags:** [runtime, compatibility, rollout, multiclass]
**Applicable-when:** Extending an existing production scoring contract with richer semantics while current consumers still depend on the old primary fields

## What Happened

This feature kept the binary runtime contract as the primary contract and added family fields (`attack_family`, confidence, margin, and `family_status`) as enrichment only when a composite bundle is active. Review and the later review-fix wave reinforced that this was the right rollout shape: the implementation could harden bundle validation and realtime propagation without forcing a migration of every existing consumer.

## Recommendation for Future Work

When a stable runtime contract already has active consumers, prefer additive enrichment over replacement unless the old contract is proven insufficient. That keeps review focused on correctness and fail-closed behavior rather than mixing semantic expansion with consumer migration.

---

# Summary

| # | Title | Category | Severity |
|---|-------|----------|----------|
| 1 | Realtime Composite Contract Tests Must Exercise A Real Composite Inferencer | failure | critical |
| 2 | Manifest Safety Flags Must Assert Semantic Falsehood, Not Only Boolean Shape | failure | critical |
| 3 | Additive Enrichment Was The Right Runtime Rollout Shape | decision | standard |

Two findings were promoted to `history/learnings/critical-patterns.md` (#1 and #2).
