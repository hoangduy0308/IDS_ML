# Approach: IDS Multiclass Two-Stage Classification

**Date**: 2026-04-04
**Feature**: `ids-multiclass-two-stage-classification`
**Based on**:
- `history/ids-multiclass-two-stage-classification/discovery.md`
- `history/ids-multiclass-two-stage-classification/CONTEXT.md`

---

## 1. Gap Analysis

| Component | Have | Need | Gap Size |
|-----------|------|------|----------|
| Family-labeled training data | Binary frozen parquet with family metadata preserved | Deterministic derived family-view artifact and reports | Medium |
| Stage-2 model | None | Attack-only family classifier with unknown/abstain support | New |
| Direct multiclass comparison | None | Offline baseline that predicts `Benign` plus known attack families | New |
| Bundle contract | Binary-only manifest and runtime compatibility metadata | One promoted bundle that keeps binary fields primary and carries optional family-enrichment metadata | High |
| Runtime scoring | Binary `attack_score` / `is_alert` only | Two-stage scoring that adds family fields only on attack rows | Medium |
| Console/operator visibility | Alert payload persistence exists, table/detail do not surface family | Readable family/confidence/status visibility for operators | Medium |

---

## 2. Recommended Approach

Build this as a derived, additive two-stage lane. Keep the current frozen binary dataset and binary gate intact, derive a new family-view artifact from the existing clean parquet files, train a CatBoost family classifier only on attack rows, and calibrate it to return `unknown` when confidence is weak or the sample behaves like the OOD holdout families. For deployment, package stage 1 and stage 2 under one promoted bundle root and one activation record, while preserving the existing binary prediction fields as the primary contract and adding family fields as optional enrichment.

The crucial design choice is to avoid both extremes: do not retrain the whole system as direct multiclass for production, and do not deploy stage 2 as a separately wired runtime model with its own override surface. Instead, use the current binary classifier as the gate, keep one deployment contract, and treat family prediction as a second-stage enrichment that only activates when the binary decision is already `Attack`.

### Why This Approach

- It honors `D1`, `D2`, `D3`, and `D4` from `CONTEXT.md` directly: binary gate first, family stage second, unknown/abstain required, additive rollout only.
- It reuses the strongest local pattern already in the repo: deterministic parquet artifacts plus one bundle activation contract.
- It keeps the blast radius smaller than a direct production multiclass flip while still producing a real offline multiclass comparison for decision quality.
- It uses the existing OOD holdout policy as a feature, not a nuisance: `BruteForce` and `Recon` become the first proof surface for unknown-family behavior.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Dataset source for stage 2 | Derive from `artifacts/cic_iot_diad_2024_binary`, do not regenerate raw CSV preprocessing in the first iteration | Honors `D8` and avoids redefining the canonical binary artifact |
| Stage-2 target space | Closed-set families `DDoS`, `DoS`, `Mirai`, `Spoofing`, `Web-Based` | Honors `D5`, `D6`, `D7` and matches available supervised signal |
| Stage-2 model family | Start with CatBoost multiclass | Same tabular modeling family already wins the binary lane and minimizes new implementation risk |
| Unknown-family rule | Validation-calibrated abstention using top-1 probability plus runner-up margin, evaluated against ID test and OOD holdout | Better fit for severe imbalance than forced closed-set prediction |
| Production packaging | One promoted composite bundle root with primary binary contract plus optional family-enrichment metadata/artifacts | Applies the one-activation-contract learning while keeping binary outputs primary |
| Runtime rollout | Score stage 1 for every row; only if `is_alert` then run stage 2 and append family fields | Matches the user's requested two-tier design and limits unnecessary stage-2 scoring |
| Direct multiclass baseline | Keep offline only in phase 1 evidence | Honors `D10` without creating unnecessary deployment risk |

---

## 3. Alternatives Considered

### Option A: Replace production with direct multiclass immediately

- Description: retrain one classifier on `Benign + attack families` and replace the binary runtime contract.
- Why considered: conceptually simpler at inference time.
- Why rejected: it violates the additive rollout direction, expands the blast radius across bundle/runtime/console at once, and ignores the fact that the current artifact and production contract are explicitly binary.

### Option B: Deploy stage 2 as a separate independently selected model

- Description: keep the binary bundle as-is and add a second runtime knob for a family classifier.
- Why considered: low-touch for the current binary manifest.
- Why rejected: it recreates the exact split-contract risk that the model-bundle hardening lane already removed. Operators could silently mix incompatible stage-1 and stage-2 artifacts.

### Option C: Regenerate the whole dataset from raw CSVs in a new multiclass preprocessing lane first

- Description: create a brand-new raw-data preprocessing contract before any model experiments.
- Why considered: maximal flexibility for future family/scenario experiments.
- Why rejected: unnecessary for the first rollout because the frozen binary artifact already preserves the needed family metadata. It adds cost and risk before we have proved the two-stage family lane is worth shipping.

---

## 4. Risk Map

| Component | Risk Level | Reason | Verification Needed |
|-----------|------------|--------|---------------------|
| Derived family-view artifact | **MEDIUM** | New artifact/reporting lane, but built from an existing frozen dataset and existing patterns | Manifest/count consistency checks and reproducibility proof |
| Stage-2 family classifier + abstention | **HIGH** | New model behavior, heavy class imbalance, unknown-handling requirement | Validation spike on calibration strategy and acceptance metrics |
| Direct multiclass offline baseline | **LOW** | Offline-only comparison using the same derived data/report pattern | Scripted report generation |
| Composite bundle contract | **HIGH** | Contract boundary change touching deployment semantics and activation safety | Validation spike on manifest shape and fail-closed parsing |
| Runtime two-stage enrichment | **MEDIUM** | Touches inference and realtime emission paths, but follows additive field pattern | Replay proof and focused runtime tests |
| Console/operator visibility | **MEDIUM** | UI and possibly query-surface changes, but `payload_json` already carries extensible fields | Page rendering tests and payload compatibility checks |

### Risk Classification Reference

```text
Pattern in codebase?        -> YES = LOW base
External dependency?        -> YES = HIGH
Blast radius > 5 files?     -> YES = HIGH
Otherwise                   -> MEDIUM
```

### HIGH-Risk Summary (for khuym:validating skill)

- `Stage-2 family classifier + abstention`: prove a concrete unknown-family rule that balances in-distribution family recall against OOD rejection on `BruteForce` and `Recon`.
- `Composite bundle contract`: prove a manifest design that keeps one activation contract and fails closed when family artifacts or metadata are missing/corrupt.

---

## 5. Proposed File Structure

```text
ml_pipeline/
  data_prep/
    prepare_iot_diad_family_views.py          # Derive attack-only and direct-multiclass views from frozen binary parquet
  training/
    train_iot_diad_family_classifier.py       # Stage-2 family classifier + abstention calibration
    train_iot_diad_direct_multiclass.py       # Offline direct multiclass baseline for comparison
  packaging/
    package_two_stage_model.py                # Promote one composite two-stage bundle
ids/
  core/
    model_bundle.py                           # Extend contract parsing/validation for optional family metadata
  runtime/
    inference.py                              # Optional second-stage family scoring after binary alert gate
    realtime_pipeline.py                      # Emit additive family fields in JSONL alerts
  console/
    db.py                                     # Persist/query additive family fields as needed
    templates/
      alerts.html                             # Alert list visibility
      alert_detail.html                       # Detail visibility if not already present in payload views
scripts/
  prepare_iot_diad_family_views.py            # Thin wrapper
  train_iot_diad_family_classifier.py         # Thin wrapper
  train_iot_diad_direct_multiclass.py         # Thin wrapper
  package_two_stage_model.py                  # Thin wrapper
artifacts/
  cic_iot_diad_2024_family_views/             # New derived frozen artifact
  final_model/
    two_stage_catboost_family_v1/             # Composite promoted bundle
```

---

## 6. Dependency Order

```text
Layer 1: Derived family-view artifact + reports
Layer 2: Offline model evidence (stage 2 + direct multiclass baseline)
Layer 3: Composite bundle contract + packaging
Layer 4: Runtime enrichment
Layer 5: Console/operator visibility + docs/tests
```

### Parallelizable Groups

- Group A: `prepare_iot_diad_family_views.py` and initial report plumbing can land before runtime work.
- Group B: `train_iot_diad_family_classifier.py` and `train_iot_diad_direct_multiclass.py` can run in parallel once the derived artifact exists.
- Group C: bundle-contract work depends on Group B's chosen artifact shape, but can proceed in parallel with console UI investigation once the runtime field contract is known.

---

## 7. Institutional Learnings Applied

| Learning Source | Key Insight | How Applied |
|-----------------|-------------|-------------|
| `history/learnings/20260329-model-bundle-promotion-hardening.md` | Keep production selection on one activation contract | Chose one composite promoted bundle instead of independent binary and family runtime knobs |
| `history/learnings/20260331-repo-structure-wrapper-contracts.md` | Wrappers are executable contracts | Proposed dedicated thin wrappers for new ML tasks and called out smoke coverage as part of the lane |
| `history/learnings/20260331-repo-structure-wrapper-contracts.md` | Canonical code must stay independent from wrappers | All new logic is placed under `ml_pipeline/*` and `ids/*`; `scripts/*` are shims only |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | Durable runtime outputs must publish during runtime | Runtime enrichment is specified as additive JSONL fields emitted per alert, not deferred into batch summaries |
| `history/learnings/20260403-packaging-contract-proof.md` | Packaging proof must survive a scrubbed environment | Packaging phase includes wrapper/install proof expectations, not just in-tree success |

---

## 8. Open Questions for Validating

- [ ] Should the optional family-enrichment block fit inside bundle manifest version `2`, or is a version bump safer while preserving the primary binary inference fields?
- [ ] What exact acceptance targets define a shippable stage-2 classifier: macro-F1 on known families, OOD unknown recall, false-unknown rate on in-distribution attacks, or a weighted combination?
- [ ] Should the first UI slice surface family in alert detail only, or in both detail and the alerts table once runtime payload stability is proven?
