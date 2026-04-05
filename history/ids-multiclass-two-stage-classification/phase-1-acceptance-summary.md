# Phase 1 Acceptance Summary: Known vs Unknown Families

## Current Decision

Phase 1 is far enough along to support a two-stage family path, but not a direct deployment decision. The evidence now says:

- Keep the binary `Attack`/`Benign` detector as the production gate.
- Treat stage 2 as a family enricher with explicit `unknown` abstention.
- Treat the imported direct-multiclass Kaggle run as a comparison baseline, not as a deployment candidate.

The current oracle and gated reports were generated from the derived family-view artifact with a bounded offline run (`max_train_rows=100000`, `iterations=100`). The direct baseline now also has a Kaggle-produced report imported into the repo, and the stage-2 family classifier has a full-data Kaggle run imported as the current best checkpoint.

## What Phase 1 Has Proven

- The derived family view is usable for offline family modeling.
- The oracle stage-2 family classifier works on the known-family splits and produces usable confidence signals.
- The stage-1 binary gate is not the bottleneck for known-family traffic: it lets through most in-distribution attack rows.
- The OOD probe families `BruteForce` and `Recon` still get mapped into known families with non-trivial confidence, so stage 2 needs explicit abstention rather than forced closed-set prediction.

Key observed numbers from the bounded offline run:

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

Imported Kaggle direct-multiclass comparison (`max_train_rows=999184`, `iterations=300`, `devices=0:1`):

- Direct multiclass test accuracy: `0.9601`
- Direct multiclass test weighted F1: `0.9688`
- Direct multiclass test macro F1: `0.5008`
- Direct multiclass test `DoS` F1: `0.9916`
- Direct multiclass test `DDoS` F1: `0.9238`
- Direct multiclass test `Benign` F1: `0.6069`
- Direct multiclass test `Mirai` F1: `0.3468`
- Direct multiclass test `Spoofing` F1: `0.1247`
- Direct multiclass test `Web-Based` F1: `0.0113`
- Direct multiclass OOD top-1 confidence mean: `0.5609`
- Direct multiclass OOD runner-up margin mean: `0.3526`
- Direct multiclass OOD rows forced into known/Benign classes: `444422 / 444422`

Imported Kaggle full-data stage-2 family checkpoint selected as current best (`max_train_rows=18457115`, `iterations=500`, `class_weight_exponent=0.5`, `devices=0`):

- Stage-2 family test accuracy: `0.9775`
- Stage-2 family test weighted F1: `0.9804`
- Stage-2 family test macro F1: `0.5376`
- Stage-2 family test `DDoS` F1: `0.9338`
- Stage-2 family test `DoS` F1: `0.9935`
- Stage-2 family test `Mirai` F1: `0.4488`
- Stage-2 family test `Spoofing` F1: `0.2955`
- Stage-2 family test `Web-Based` F1: `0.0162`
- Stage-2 family OOD top-1 confidence mean: `0.5589`
- Stage-2 family OOD runner-up margin mean: `0.3097`
- Stage-2 family OOD predicted `Web-Based` rows: `20260 / 444422`

One additional sweep (`iterations=700`, same exponent `0.5`) was also run on Kaggle. It improved macro F1 only marginally (`0.5379`) while slightly worsening `Web-Based`, slightly worsening OOD concentration into `Web-Based`, and slightly increasing OOD confidence. So the `iterations=500`, `class_weight_exponent=0.5` checkpoint remains the preferred stage-2 candidate.

Interpretation:

- `BruteForce` and `Recon` are still not safe to force into a known family.
- Stage 1 alone does not create the `unknown` behavior we need.
- Stage 2 must abstain on weak family evidence.
- The direct multiclass baseline still looks strong only on aggregate metrics dominated by `DoS`; it remains weak on minority families and still forces OOD traffic into closed-set labels.
- The full-data stage-2 family run materially improves `Mirai` and `Spoofing` over the direct baseline while sharply reducing OOD spill into `Web-Based`, but it still does not make `Web-Based` itself reliable enough for forced closed-set runtime use.

## Direct Baseline Verdict

The direct multiclass comparison is no longer provisional because the repo now contains `artifacts/modeling/cic_iot_diad_2024_family_views/direct_multiclass/reports/direct_multiclass_eval.json`.

What the imported Kaggle report says:

- The direct baseline is competitive on `DoS` / `DDoS` and on overall weighted metrics.
- It is not competitive enough on minority families such as `Mirai`, `Spoofing`, and especially `Web-Based`.
- It still has no trustworthy `unknown` behavior for `BruteForce` / `Recon`; every OOD row is forced into a known class or `Benign`.

So, now:

- The two-stage direction is evidence-backed.
- The direct multiclass baseline is also evidence-backed, but only as a comparison baseline.
- Phase 2 still should not replace the binary gate with a direct multiclass model.

## Recommended Acceptance Rule

Use this rule for the current Phase 1 exit:

- `known family` means the row is already classified as `Attack` by stage 1 and stage 2 returns a family prediction only when both `top1_confidence` and `runner_up_margin` exceed validation-calibrated thresholds.
- `unknown` means anything else, including weak-confidence attack rows and OOD-like rows that do not clear both thresholds.

Practical recommendation:

- Start with a two-signal abstention gate calibrated on the oracle validation split.
- Keep the thresholds conservative enough that known-family recall stays near the current oracle level while OOD `BruteForce` / `Recon` assignment drops materially below the current pass-through observed under stage 1 alone.
- Do not hardcode the final threshold pair until the selected full-data stage-2 checkpoint is calibrated against raw validation and OOD outputs.

## HIGH-Risk Questions For Validating

- What exact `top1_confidence` and `runner_up_margin` thresholds should define `known` on the selected full-data stage-2 family checkpoint?
- Does the current report contract need a version bump before Phase 2 adds family enrichment metadata?
- Does `Web-Based` stay too weak to expose as a first-class runtime family before additional data or hierarchy changes?

## Phase 1 Exit Recommendation

Proceed to Phase 2 on the two-stage path, but only with the binary gate preserved and the family model allowed to abstain. The direct multiclass path remains comparison-only even after the imported Kaggle result. The full-data stage-2 checkpoint is now strong enough to use as the Phase 2 starting model artifact, but threshold calibration and runtime contract work still need to happen before deployment.
