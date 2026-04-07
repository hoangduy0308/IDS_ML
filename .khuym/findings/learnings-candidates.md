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

## Candidate: canonical-family-view-builder
Category: failure
Tags: [console, alerts, ui, contracts, data-shape, architecture]
Summary: When alert-family semantics must appear on multiple operator surfaces, build the public family view exactly once and have detail, queue, and route surfaces consume that canonical shape instead of mixing pre-hydrated data with duplicated top-level fields.
Evidence: Review findings that the detail page depends on pre-hydrated `family` data, unknown detail drops `attack_family_margin` abstention context, benign rows preserve family fields despite the D8 no-label contract, the detail page is not wired to the canonical family-view builder, and the diff exposes both `alert['family']` and duplicated top-level family fields.
Recommended title: YYYYMMDD-canonical-family-view-builder.md

## Candidate: route-contract-tests-for-family-semantics
Category: failure
Tags: [testing, console, routes, contracts, family-semantics]
Summary: Route-level tests for alert-family operator surfaces must pin the real user-visible semantics for known, unknown, benign, and legacy cases, including explicit unknown confidence, preserved abstention margin, honest legacy-unavailable copy, and the absence of family labels on benign rows.
Evidence: Review findings that benign family semantics are not covered on the real route contract despite D8 and a dedicated benign branch, and that route assertions do not pin unknown confidence, known margin, or absence of family label for unknown.
Recommended title: YYYYMMDD-route-contract-tests-for-family-semantics.md
