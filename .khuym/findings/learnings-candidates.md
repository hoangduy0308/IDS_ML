## Candidate: execute-full-stack-lifecycle-verification-before-declaring-success
Category: failure
Tags: bootstrap, restore, verification, smoke, readiness
Summary: Thin same-host stack orchestrators must execute the full promised verification contract after startup and after restore, including canonical status/smoke and optional non-gating edge checks, instead of returning success after service start or mutation alone.
Evidence: ids_ml_new-osr, ids_ml_new-a6d1
Recommended title: YYYYMMDD-execute-full-stack-lifecycle-verification-before-declaring-success.md

## Candidate: default-stack-diagnostics-to-degraded-and-redacted-output
Category: failure
Tags: diagnostics, redaction, secrets, readiness, cli
Summary: Canonical stack health and recovery surfaces should never emit raw tracebacks, secret-bearing argv, or sensitive notification details on expected failures; default output must stay machine-readable, degraded, and redacted, with deeper diagnostics gated behind explicit operator intent.
Evidence: ids_ml_new-8fhx, ids_ml_new-q26, ids_ml_new-27c
Recommended title: YYYYMMDD-default-stack-diagnostics-to-degraded-and-redacted-output.md

## Candidate: pin-negative-path-taxonomy-on-new-runtime-health-seams
Category: failure
Tags: live-sensor, runtime-health, test-coverage, failure-taxonomy
Summary: When a feature introduces a new read-only runtime-health seam, regression coverage must pin every emitted failure state and activation-resolution branch so downstream stack aggregation cannot drift while happy-path health stays green.
Evidence: ids_ml_new-r0g
Recommended title: YYYYMMDD-pin-negative-path-taxonomy-on-new-runtime-health-seams.md
