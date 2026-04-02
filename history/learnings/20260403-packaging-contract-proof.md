---
date: 2026-04-03
feature: ids-repo-installable-full-stack-packaging
categories: [pattern, decision, failure]
severity: critical
tags: [packaging, bootstrap, trust-boundary, wrappers, testing, review]
---

# Learning: Bind Privileged Bootstrap Execution To The Validated Interpreter Contract

**Category:** failure
**Severity:** critical
**Tags:** [bootstrap, trust-boundary, security]
**Applicable-when:** Any preflight step approves Python modules, scripts, or helpers that will later run with mutation authority.

## What Happened

The review-followup wave found that `ids/ops/same_host_stack.py` validated management-module trust during preflight and then later executed `python -m ...` under the ambient runtime environment. That meant approval happened under one interpreter/import contract while privileged execution happened under another. The final repair had to bind bootstrap execution to the same isolated interpreter/env/cwd contract and make degraded preflight fail closed before mutations.

## Root Cause / Key Insight

The original design treated validation and execution as separate phases and assumed the approval remained valid even when runtime resolution inputs changed. That assumption was false: if `cwd`, `PYTHONPATH`, `PYTHONHOME`, or similar inputs drift, the code that was validated is not necessarily the code that runs. Trust-boundary work only closes when approval and privileged execution share the same executable contract.

## Recommendation for Future Work

Always bind privileged module execution to the exact interpreter, environment, and working-directory contract that preflight validated. Never approve code under one resolution context and execute it later under another, and always add contamination tests that vary inherited `PYTHON*` state to prove the binding holds.

---

# Learning: Prove Editable Installs In A Scrubbed Environment That Cannot Fall Back To Warmed `__pycache__`

**Category:** failure
**Severity:** critical
**Tags:** [packaging, editable-install, verification]
**Applicable-when:** Closing any packaging, install-surface, or deploy-asset feature that claims a clean editable install is a supported contract.

## What Happened

Packaging looked healthy until a fresh install proof exposed that `ids.console.web` source was missing and previous success depended on warmed local `.pyc` state rather than real shipped source or package data. The defect only became visible after running a scrubbed install/lifecycle proof outside the already-warmed workspace assumptions. That late discovery caused extra review churn and forced source restoration before the lane could close.

## Root Cause / Key Insight

The verification surface was too warm and too in-tree. Tests proved behavior inside a checkout that still had cached bytecode and local source layout available, so they did not assert the actual installed artifact contract. Clean packaging proof must verify source/package-data presence, not just import success in a dirty developer tree.

## Recommendation for Future Work

Before closing packaging work, run a scrubbed editable-install proof that removes `__pycache__` assumptions and asserts every shipped import, template, and static asset exists as real source or package data. Treat passing inside a warmed repo as insufficient evidence of install correctness.

---

# Learning: Reuse One Validated Config Snapshot Across Preflight And Mutating Bootstrap

**Category:** pattern
**Severity:** standard
**Tags:** [config, bootstrap, testing]
**Applicable-when:** A bootstrap flow validates configuration first and then uses that configuration to mutate state or launch services.

## What Happened

The repaired bootstrap path in `ids/ops/same_host_stack.py` stopped reparsing operator config after preflight and instead carried one validated snapshot into the mutating bootstrap steps. That removed a config-drift seam where preflight could approve one configuration view while bootstrap executed against another. The follow-up tests now pin the fail-closed path instead of allowing hidden re-entry into config loading.

## Root Cause / Key Insight

Re-reading configuration after validation silently reopens time-of-check/time-of-use drift, especially when environment-backed settings or generated files are involved. A validated snapshot is not just cached data; it is part of the contract that the later execution is supposed to honor.

## Recommendation for Future Work

When preflight validates config for a later mutating phase, thread the validated snapshot forward and make that snapshot authoritative. Do not reparse the same config on the hot path unless the design explicitly requires revalidation and proves that behavior in tests.

---

# Learning: Treat Wrapper Seams As Explicit Contracts Or Intentionally Narrow Them

**Category:** decision
**Severity:** standard
**Tags:** [wrappers, compatibility, runtime]
**Applicable-when:** A migration keeps old `scripts/*` entrypoints or wrapper modules alive while canonical `ids/*` surfaces become the real product path.

## What Happened

The console-server follow-up had to repair both runtime reload behavior and wrapper compatibility expectations around `scripts/ids_operator_console_server.py`. Simply keeping names exported was not enough; the actual callable behavior and forwarded `uvicorn.run(...)` contract needed to be pinned in tests. The successful resolution was to choose the surviving facade intentionally and prove it directly.

## Root Cause / Key Insight

Wrappers drift when teams preserve labels but do not specify which CLI or import-time behaviors remain supported. That leaves a seam that looks compatible to humans while quietly changing at runtime. Migrations stay stable only when wrapper scope is explicit and test-enforced.

## Recommendation for Future Work

When preserving wrappers, decide exactly which CLI and programmatic surfaces remain supported and pin them with focused tests. If a wrapper contract is being narrowed, make that decision explicit and remove or stop advertising the dropped seam instead of letting it drift implicitly.

---

# Learning: Isolate Review Closure To The Owned Lane In A Shared Workspace

**Category:** decision
**Severity:** standard
**Tags:** [review, coordination, multi-agent]
**Applicable-when:** Multiple agents are landing adjacent changes and a fresh-eyes review runs against a shared moving worktree.

## What Happened

One fresh-eyes pass briefly picked up `ids.console.web` failures that belonged to a concurrent UI rebuild, not to the packaging/runtime repair lane under review. Once the review was re-scoped to the owned non-UI lane, the remaining findings were concrete and closeable. That kept the packaging conclusion from being blocked by unrelated parallel churn.

## Root Cause / Key Insight

Shared workspaces make unrelated failures look locally relevant unless the review first pins the owned file/test surface and distinguishes baseline failures from new lane-specific regressions. Without that discipline, review time gets spent reopening noise instead of closing the real contract.

## Recommendation for Future Work

When reviewing in a multi-agent repo, pin the owned lane first: files, tests, and contract surface. Record known concurrent-lane failures up front, then exclude them from blocker triage unless the seams are genuinely coupled.
