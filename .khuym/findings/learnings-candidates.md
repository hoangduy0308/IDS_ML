## Candidate: derived-view-contracts-and-eval-proofing
Category: pattern
Tags: [ml, datasets, evaluation, contracts, fail-closed]
Summary: Derived dataset builders and evaluation reports must enforce label contracts at build time, reject unexpected or missing labels, and include negative-path proofs instead of relying on smoke success.
Evidence: Review findings on direct-multiclass label contract enforcement, derived-view boundary enforcement, OOD abstention smoke-only checks, direct baseline comparison proof gaps, and missing negative-path coverage.
Recommended title: YYYYMMDD-derived-view-contracts-and-eval-proofing.md

## Candidate: class-preserving-sampling
Category: failure
Tags: [ml, sampling, class-imbalance, training]
Summary: Any random subsampling step that can silently remove a declared class must either stratify explicitly or fail loudly before training proceeds.
Evidence: Review finding on `sample_train_split()` / `train_model()` deriving effective class support from the sampled subset only.
Recommended title: YYYYMMDD-class-preserving-sampling.md

## Candidate: root-contained-destructive-ops
Category: failure
Tags: [filesystem, path-resolution, containment, security, ml]
Summary: Caller-controlled paths used for delete, export, or dataset materialization must be normalized and proven to stay inside an approved root before any destructive filesystem action runs.
Evidence: Review findings on recursive cleanup of `--output-root` and trusting dataset/index paths without containment checks.
Recommended title: YYYYMMDD-root-contained-destructive-ops.md
