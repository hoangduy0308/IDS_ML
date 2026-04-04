# Phase 1 Acceptance Summary: Known vs Unknown Families

## Current Decision

Phase 1 is far enough along to support a two-stage family path, but not a direct deployment decision. The evidence now says:

- Keep the binary `Attack`/`Benign` detector as the production gate.
- Treat stage 2 as a family enricher with explicit `unknown` abstention.
- Do not finalize any direct-multiclass deployment conclusion until `direct_multiclass_eval.json` lands back in the repo.

The current oracle and gated reports were generated from the derived family-view artifact with a bounded offline run (`max_train_rows=100000`, `iterations=100`) so the summary is evidence-backed but still offline-only.

## What Phase 1 Has Proven

- The derived family view is usable for offline family modeling.
- The oracle stage-2 family classifier works on the known-family splits and produces usable confidence signals.
- The stage-1 binary gate is not the bottleneck for known-family traffic: it lets through most in-distribution attack rows.
- The OOD probe families `BruteForce` and `Recon` still get mapped into known families with non-trivial confidence, so stage 2 needs explicit abstention rather than forced closed-set prediction.

Key observed numbers from the current offline run:

- Oracle family classifier val macro F1: `0.3483`
- Oracle family classifier test macro F1: `0.4037`
- Oracle family classifier test accuracy: `0.9176`
- Oracle OOD top-1 confidence mean: `0.5134`
- Oracle OOD runner-up margin mean: `0.2935`
- Gated stage-1 alert rate on val: `0.9781`
- Gated stage-1 alert rate on test: `0.9874`
- Gated stage-1 alert rate on OOD holdout: `0.4996`
- Gated `BruteForce` stage-1 alert rate: `0.3493`
- Gated `Recon` stage-1 alert rate: `0.5008`

Interpretation:

- `BruteForce` and `Recon` are still not safe to force into a known family.
- Stage 1 alone does not create the `unknown` behavior we need.
- Stage 2 must abstain on weak family evidence.

## What Remains Provisional

The direct multiclass comparison is still provisional because the repo does not yet contain `artifacts/modeling/cic_iot_diad_2024_family_views/direct_multiclass/reports/direct_multiclass_eval.json`.

What we do have is the Kaggle kernel contract in `artifacts/kaggle/kernels/direct_multiclass/README.md` and the companion kernel script. That contract confirms the intended output shape and location, but it is not evidence yet.

So, for now:

- The two-stage direction is evidence-backed.
- The direct multiclass baseline is contract-backed, not result-backed.
- Phase 2 should not depend on direct-baseline superiority until the Kaggle-produced report returns.

## Recommended Acceptance Rule

Use this rule for the current Phase 1 exit:

- `known family` means the row is already classified as `Attack` by stage 1 and stage 2 returns a family prediction only when both `top1_confidence` and `runner_up_margin` exceed validation-calibrated thresholds.
- `unknown` means anything else, including weak-confidence attack rows and OOD-like rows that do not clear both thresholds.

Practical recommendation:

- Start with a two-signal abstention gate calibrated on the oracle validation split.
- Keep the thresholds conservative enough that known-family recall stays near the current oracle level while OOD `BruteForce` / `Recon` assignment drops materially below the current pass-through observed under stage 1 alone.
- Do not hardcode the final threshold pair until the direct multiclass report returns and the comparison can be done on the same artifact lineage.

## HIGH-Risk Questions For Validating

- What exact `top1_confidence` and `runner_up_margin` thresholds should define `known`?
- Does the current report contract need a version bump before Phase 2 adds family enrichment metadata?
- Does the direct multiclass baseline change the recommendation, or does it just confirm the two-stage path?

## Phase 1 Exit Recommendation

Proceed to Phase 2 on the two-stage path, but only with the binary gate preserved and the family model allowed to abstain. The direct multiclass path remains comparison-only until its Kaggle report is imported and reviewed.
