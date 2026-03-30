---
date: 2026-03-30
feature: ids-flow-extractor-replacement
categories: [pattern, decision, failure]
severity: critical
tags: [extractor, contracts, deployment, testing, runtime]
---

# Learning: Keep The Model Boundary Harder Than The Legacy Shell

**Category:** decision
**Severity:** standard
**Tags:** [extractor, model, contracts]
**Applicable-when:** Replacing upstream tooling that feeds an already-hardened model or runtime contract

## What Happened

This feature started from a CICFlowMeter-like shell and packaging surface, but the safe execution path came from treating the 72 canonical runtime features as the real boundary and the historical `Cmd`, `_Flow.csv`, Java, and `jnetpcap` assumptions as negotiable compatibility seams. The planning, validation spikes, execution, and review follow-ups all held that line: semantic correctness into the active bundle stayed fixed while bridge, preflight, and service packaging were allowed to evolve in controlled ways.

## Root Cause / Key Insight

Legacy command shape is often only the outer shell of a system. The true source of truth here was the model-facing numeric feature contract and its validation path, not the packaging of the old extractor. Anchoring on the wrong boundary would have optimized for drop-in mimicry while still allowing silent semantic drift into inference.

## Recommendation for Future Work

When replacing infrastructure around an ML or runtime boundary, identify the deepest enforced contract first and optimize compatibility there. Treat command-line or file-format fidelity as secondary unless code and tests prove it is the real runtime invariant.

---

# Learning: Split Canonical Extraction From Compatibility Serialization With A Typed Seam

**Category:** pattern
**Severity:** standard
**Tags:** [extractor, serializer, typing]
**Applicable-when:** A semantic core must outlive one specific compatibility profile, transport, or output encoding

## What Happened

The replacement extractor originally computed flow semantics, mapped adapter aliases, shaped metadata, and wrote CSV rows in one module. Review follow-up work split the canonical extractor core into [`scripts/ids_offline_window_extractor.py`](F:\Work\IDS_ML_New\scripts\ids_offline_window_extractor.py) and a dedicated serializer layer in [`scripts/ids_offline_window_serializer.py`](F:\Work\IDS_ML_New\scripts\ids_offline_window_serializer.py), then tightened the seam with an explicit protocol and direct serializer tests.

## Root Cause / Key Insight

Semantic extraction and compatibility serialization change at different rates. When they are fused, every adapter/profile change becomes an extractor change and the boundary becomes hard to reason about. The split only really became stable once the seam was typed and directly tested, not just separated into two files.

## Recommendation for Future Work

Define a canonical internal model first, then add a typed serializer or compatibility layer on top. Remove dead helpers and `Any`-style scaffolding in the same refactor so the new seam does not drift back into implicit coupling.

---

# Learning: Pin Command Tokenization And Negative Paths With Executable Round-Trip Tests

**Category:** failure
**Severity:** critical
**Tags:** [systemd, shell, cli, tokenization, testing]
**Applicable-when:** Any feature passes multi-token commands or required startup flags through systemd, shell wrappers, or CLI parsers

## What Happened

The review-follow-up swarm fixed the live extractor dependency contract by preserving multi-token `extractor_command_prefix` end to end, but review found that the first test pass only checked object normalization and static unit-file text. The final clean review came only after adding tests that exercised argparse failure on missing required flags, verified service-unit tokenization through a shell-style split, and pinned negative parser behavior with real malformed-frame fixtures.

## Root Cause / Key Insight

Startup and transport bugs often live in tokenization layers, not in the config objects behind them. If tests stop at object construction or grep the shipped unit file as text, quoting, shell expansion, and required-argument failures can still break runtime startup without any regression signal.

## Recommendation for Future Work

Whenever a runtime contract crosses CLI, systemd, or shell boundaries, add executable round-trip tests for both success and failure paths. Do not treat static file assertions or config-object tests as sufficient coverage for tokenization-sensitive behavior.

---

# Learning: Guard Only The Exact Bad Case In Derived Metrics

**Category:** failure
**Severity:** standard
**Tags:** [metrics, semantics, testing]
**Applicable-when:** Derived rates or aggregates need protection against invalid or degenerate inputs

## What Happened

The offline extractor originally floored `rate_duration_seconds` to `1.0`, which silently undercounted rate-based features for valid sub-second flows. The bug was only discovered in review, then fixed by changing the logic to guard only the zero-duration case and by pinning sub-second behavior with dedicated regression tests and a refreshed golden fixture.

## Root Cause / Key Insight

The defensive guard was broader than the actual failure mode. A convenience floor protected the zero-duration edge case but also changed the semantics of nonzero short windows, which mattered directly at the model boundary.

## Recommendation for Future Work

Guard only the exact invalid case you intend to handle. For model-facing derived metrics, add explicit boundary tests for sub-second, zero, and near-threshold inputs instead of relying on broad fallback math.
