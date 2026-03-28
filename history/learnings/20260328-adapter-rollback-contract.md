---
date: 2026-03-28
feature: ids-structured-record-adapter
categories: [pattern, decision, failure]
severity: critical
tags: [adapter, rollback, testing, validation, security]
---

# Learning: Treat Multi-Output Publish And Rollback As One Contract

**Category:** pattern
**Severity:** standard
**Tags:** [rollback, file-mode, testing]
**Applicable-when:** A tool writes more than one durable output and can fail after one sink has already been staged or promoted

## What Happened

The adapter writes both adapted output and adapter quarantine output in file mode. Early review cycles exposed that handling those sinks as independent writes left room for partial publishes, asymmetric rerun states, and cleanup gaps when one promotion failed after the other sink had already moved. The final shape only stabilized after staged temp files, atomic promotion, asymmetric-state tests, and byte-fidelity assertions were treated as one combined contract.

## Root Cause / Key Insight

The failure surface was not in one file or one assertion. It lived in the interaction between adapted output, quarantine output, temp artifacts, backup artifacts, and rerun state. Narrow single-file checks missed exactly the class of bug that mattered most: partial recovery where one sink looked correct and the other did not.

## Recommendation for Future Work

When a feature publishes multiple outputs, stage all sinks first, promote them transactionally, and test rollback as one matrix that verifies surviving outputs, backup preservation, and temp cleanup together.

---

# Learning: Never Use Copy-Based Fallbacks In Filesystem Rollback

**Category:** failure
**Severity:** critical
**Tags:** [rollback, security, filesystem]
**Applicable-when:** Recovery code restores files after a failed rename or replace operation, especially on user-controlled or externally supplied output paths

## What Happened

The adapter rollback path originally tried to recover from a failed `Path.replace()` by copying the backup file back into the destination path. Review found that this was unsafe because a symlink or junction could redirect the target and turn a recovery step into an arbitrary overwrite. The fix pass removed the fallback and kept restore behavior on the atomic rename/replace path only.

## Root Cause / Key Insight

The implementation treated “best effort restore” as safer than surfacing an error. On real filesystems that assumption is wrong. Once path indirection is possible, a copy-based fallback is not a recovery convenience, it is a separate write primitive with a broader and less trustworthy target surface.

## Recommendation for Future Work

Never add copy-or-unlink fallbacks to rollback code that restores named output paths. Use atomic rename/replace only, and if restore fails, fail closed and preserve enough artifact state for diagnosis instead of copying data into the destination.

---

# Learning: Build Adapter Test Expectations From The Output Contract, Not The Source Payload

**Category:** decision
**Severity:** standard
**Tags:** [adapter, testing, contract]
**Applicable-when:** A test needs an expected record for a mapper or adapter that normalizes upstream inputs into a stricter downstream schema

## What Happened

One review rerun caught that the rollback test oracle had drifted into calling the adapter itself, which made the test self-referential. A later micro-fix replaced that with an explicit expected-record builder that only includes same-name features, aliased features, metadata aliases, controlled extras, and `adapter_profile`, staying inside the D7 boundary.

## Root Cause / Key Insight

Both “copy the whole source record” and “call the implementation under test” blur the boundary the adapter is supposed to enforce. Contract-focused expected-value builders are more verbose, but they are the only reliable way to catch pass-through leaks and mapping drift without mirroring the production code.

## Recommendation for Future Work

When writing adapter or mapper tests, construct expectations from the intended output contract only. Do not clone the full source payload, and do not derive expected values by calling the implementation under test.

---

# Learning: Validation Must Check Concurrent Write Scope And High-Risk Spikes Before Swarming

**Category:** failure
**Severity:** critical
**Tags:** [validation, swarming, bead-decomposition]
**Applicable-when:** Planning or validating any feature that will be executed by multiple workers or has HIGH-risk beads

## What Happened

Validation iteration 1 for this feature failed because concurrent beads overlapped in file scope and the highest-risk areas did not yet have spike beads. That issue was caught before execution started, dependencies were fixed, and two spike beads were added. Later review loops were still long, but they were long inside a valid execution graph rather than collapsing at the starting line.

## Root Cause / Key Insight

The original plan was structurally incomplete for parallel execution. Without explicit write-scope isolation and early spikes for the riskiest assumptions, the swarm would have started with ambiguous ownership and unknowns still sitting in the critical path.

## Recommendation for Future Work

Before approving execution, verify that concurrent beads have disjoint write scopes and require spikes for every HIGH-risk item. Do not let swarming start until both conditions are true in the live bead graph.
