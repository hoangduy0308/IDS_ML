# Critical Patterns

Promoted learnings from completed features. Read this file at the start of every
planning Phase 0 and every exploring Phase 0. These are the lessons that cost the
most to learn and save the most by knowing.

---

## [20260328] Never Use Copy-Based Fallbacks In Filesystem Rollback
**Category:** failure
**Feature:** ids-structured-record-adapter
**Tags:** [rollback, security, filesystem]

The adapter rollback path originally tried to recover from a failed `replace()` by copying the backup back into place. Review exposed that this is unsafe when the destination can be redirected through a symlink or junction, because a recovery step becomes an arbitrary overwrite primitive. Future work should keep rollback on atomic rename/replace only and fail closed if restore cannot be completed safely.

**Full entry:** history/learnings/20260328-adapter-rollback-contract.md

## [20260328] Validate Write Scope And High-Risk Spikes Before Swarming
**Category:** failure
**Feature:** ids-structured-record-adapter
**Tags:** [validation, swarming, bead-decomposition]

This feature's first validation pass failed because concurrent beads overlapped in file scope and HIGH-risk assumptions had not been spiked yet. Catching that before execution prevented a bad swarm start and forced the plan into a shape the workers could actually execute safely. Future validation passes should explicitly reject shared write scopes and missing spikes before approving execution.

**Full entry:** history/learnings/20260328-adapter-rollback-contract.md

## [20260328] Publish Durable Daemon Outputs During Runtime, Not Only At Shutdown
**Category:** failure
**Feature:** ids-live-host-based-ml-ids
**Tags:** [daemon, durability, restart]

The first live-sensor sink buffered outputs in memory and only made them durable on `close()`. Review exposed that this is unsafe for supervisor-managed services because a crash or restart can happen before graceful shutdown, leaving operators with a process that appeared active but had not actually published its evidence. Future daemon work should append durable alerts/quarantines during runtime and reserve shutdown for final snapshots only.

**Full entry:** history/learnings/20260328-live-sensor-runtime-contracts.md

## [20260328] Keep Service Entrypoints Wired To The Real App Factory
**Category:** failure
**Feature:** ids-operator-console-v1
**Tags:** [fastapi, runtime, deployment, review]

The operator console review found that the real dashboard and API routes existed in `web.py`, but the runnable service entrypoint still launched a bootstrap-only FastAPI app. That kind of split can make a feature look complete in implementation and route tests while production still serves a placeholder surface. Future service features should run exactly one canonical app factory and add a regression test that proves the entrypoint exposes a real feature route, not only `/healthz` or a stub root page.

**Full entry:** history/learnings/20260328-operator-console-runtime-wiring.md

## [20260328] Always Classify Child Process Exit In Supervisor-Managed Capture Loops
**Category:** failure
**Feature:** ids-live-host-based-ml-ids
**Tags:** [supervisor, process-lifecycle, fail-fast]

The live sensor originally treated the end of the capture notification stream as effectively clean completion. That was wrong: a dead or broken child can look like a quiet stream unless the parent inspects return code and stderr and decides whether the exit is recoverable or fatal. Future capture daemons should classify child exits explicitly and hand fatal cases to the supervisor restart path.

**Full entry:** history/learnings/20260328-live-sensor-runtime-contracts.md

## [20260328] Use Exact-Path Preflight Contracts For Linux Services
**Category:** pattern
**Feature:** ids-live-host-based-ml-ids
**Tags:** [systemd, preflight, deployment, security]

The service unit became safer only after runtime values were centralized and preflight checks validated exact helper-binary paths, native dependencies, NIC selection, and writable output roots before the daemon loop started. Bare `PATH` lookups and duplicated literals made the deployment contract too easy to drift. Future Linux services with host-level dependencies should use one config source and an explicit exact-path preflight step.

**Full entry:** history/learnings/20260328-live-sensor-runtime-contracts.md

## [20260329] Split Runtime Verification From Operator Mutation Paths
**Category:** pattern
**Feature:** ids-operator-console-production-hardening
**Tags:** [sqlite, bootstrap, migration, startup]

The operator console only became safely production-ready once normal startup stopped creating or mutating schema implicitly and shifted all shape-changing actions into explicit operator commands such as `migrate` and `bootstrap-admin`. For same-host services with local persistent state, mixing inspection and mutation inside the runtime path makes readiness impossible to reason about and hides broken upgrades until production. Future hardening work should keep runtime verify-only and move bootstrap/migration/recovery into explicit maintenance entrypoints.

**Full entry:** history/learnings/20260329-operator-console-production-hardening.md

## [20260329] Keep Production Model Selection On One Activation Contract
**Category:** pattern
**Feature:** ids-model-bundle-promotion-hardening
**Tags:** [model-bundle, compatibility, activation, deployment]

The IDS model lifecycle only became safe once production stopped accepting independent model/schema/threshold overrides and instead resolved one versioned bundle manifest through one host-local activation record. Split path inputs looked flexible but left a real drift seam where the runtime could score with one bundle while silently consuming schema or threshold from another. Future single-host ML deployments should keep production selection on one activation contract and fail closed if that contract cannot be verified.

**Full entry:** history/learnings/20260329-model-bundle-promotion-hardening.md

## [20260329] Execute The Full Stack Lifecycle Before Returning Success
**Category:** failure
**Feature:** ids-same-host-stack-runtime-hardening
**Tags:** [bootstrap, restore, verification, smoke]

Canonical stack commands are contracts, not convenience wrappers. If `bootstrap`, `recover`, or `post-restore-check` claims to complete a host lifecycle, it must execute the full advertised verification sequence before returning success, including post-start readiness/smoke and any documented non-gating seam checks. Future stack orchestration work should add tests that prove every documented phase actually runs.

**Full entry:** history/learnings/20260329-same-host-stack-runtime-hardening.md

## [20260329] Default Stack Diagnostics To Degraded And Redacted Output
**Category:** pattern
**Feature:** ids-same-host-stack-runtime-hardening
**Tags:** [diagnostics, redaction, secrets, cli]

Expected contract failures in stack-level health and operations commands should surface as structured degraded payloads, not raw tracebacks, and default output must stay secret-safe. Secret-bearing argv, sensitive notification metadata, and similar details should require explicit operator intent rather than appearing in routine health output. Future runtime CLIs should fail closed, emit machine-readable degraded state, and redact by default.

**Full entry:** history/learnings/20260329-same-host-stack-runtime-hardening.md

## [20260330] Use Live Bead State And Commit History To Rescue A Stalled Swarm
**Category:** failure
**Feature:** ids-operator-console-ui-redesign
**Tags:** [agent-coordination, swarming, recovery]

This UI redesign hit repeated worker startup/progress drift even though the validated graph, reservations, and repository state still allowed safe forward movement. The reliable rescue path was to stop trusting missing chat acknowledgments, release stale reservations, reset the bead state when necessary, and verify recovery from `br show`, real commits, and passing tests. Future swarms should time-box silent workers and recover from live execution state rather than waiting indefinitely on stuck status loops.

**Full entry:** history/learnings/20260330-agent-coordination-ui-redesign.md

## [20260330] Pin Multi-Token Runtime Contracts With End-To-End Tokenization Tests
**Category:** failure
**Feature:** ids-flow-extractor-replacement
**Tags:** [systemd, shell, cli, testing]

This feature's follow-up review found that preserving a multi-token extractor command prefix in code and service units was not enough; the real risk lived in the tokenization chain across systemd, shell expansion, and argparse. The issue only became truly closed after tests exercised both the success round-trip and the missing-argument failure path. Future host-service features should treat tokenization-sensitive startup flags as executable contracts and test them end to end.

**Full entry:** history/learnings/20260330-extractor-contract-hardening.md

## [20260331] Treat Compatibility Wrappers As Executable Contracts
**Category:** failure
**Feature:** repo-structure-rationalization
**Tags:** [wrappers, testing, compatibility, migration]

This refactor preserved `scripts/*` entrypoints during a large internal move, but review proved that wrapper stability is not real unless CI exercises those wrappers directly. Runtime, ops, and ML wrapper smoke coverage all had to be added after execution, costing a substantial review-fix wave. Future staged migrations should add wrapper-smoke coverage in the same bead that preserves an old entrypoint, not as a later review repair.

**Full entry:** history/learnings/20260331-repo-structure-wrapper-contracts.md

## [20260403] Bind Privileged Bootstrap Execution To The Validated Interpreter Contract
**Category:** failure
**Feature:** ids-repo-installable-full-stack-packaging
**Tags:** [bootstrap, trust-boundary, security]

This packaging follow-up only became safe once `ids/ops/same_host_stack.py` stopped validating trusted module origins under one import contract and executing them later under another. Preflight approval is meaningless if privileged bootstrap can still resolve code through a different interpreter, `cwd`, or inherited `PYTHON*` state. Future module-based bootstrap paths must run under the exact validated interpreter/env contract and ship contamination tests that prove approval and execution stay bound together.

**Full entry:** history/learnings/20260403-packaging-contract-proof.md

## [20260403] Prove Editable Installs In A Scrubbed Environment That Cannot Fall Back To Warmed `__pycache__`
**Category:** failure
**Feature:** ids-repo-installable-full-stack-packaging
**Tags:** [packaging, editable-install, verification]

This packaging lane looked healthy until a scrubbed install proof exposed that `ids.console.web` source presence was being masked by warmed local `.pyc` state. In-tree or already-warmed verification is not enough to prove an install contract because it can hide missing source files, templates, or package data. Future packaging work should always run a fresh editable-install proof that removes `__pycache__` dependence and asserts the real shipped module and asset payload exists.

**Full entry:** history/learnings/20260403-packaging-contract-proof.md

## [20260331] Keep Canonical Modules Independent From Compatibility Layers
**Category:** decision
**Feature:** repo-structure-rationalization
**Tags:** [architecture, core, imports, compatibility]

The new package tree only became real once canonical `ids/*` code stopped importing back through `scripts/*` and `ids.core` stopped carrying operational lifecycle behavior. If canonical modules depend on compatibility wrappers, the new structure is only cosmetic and boundary drift returns immediately. Future refactors should enforce one-way dependency flow (`scripts -> canonical`) and keep shared/core packages limited to true contract responsibilities.

**Full entry:** history/learnings/20260331-repo-structure-wrapper-contracts.md

## [20260331] Normalize Hostile Metadata At Contract Boundaries
**Category:** failure
**Feature:** repo-structure-rationalization
**Tags:** [error-handling, metadata, fail-closed, contracts]

This refactor only became review-clean after manifest, activation-record, and backup-metadata parsers stopped leaking raw `KeyError`, `ValueError`, and JSON parse exceptions. Boundary modules such as `ids/core/model_bundle.py`, `ids/core/model_bundle_activation.py`, and `ids/console/ops.py` need to translate hostile or malformed metadata into one domain-specific error type so runtime, CLI, and review logic all fail closed consistently. Future work should normalize malformed metadata at the boundary and add corrupted-input tests in the same bead.

**Full entry:** history/learnings/20260331-repo-structure-wrapper-contracts.md

## [20260331] Resolve Paths Then Prove Root Containment For Host-Level Operations
**Category:** failure
**Feature:** repo-structure-rationalization
**Tags:** [filesystem, path-resolution, containment, restore, security]

The same-host cleanup showed that `Path.resolve()` is not a security boundary. Host-level helpers and restore inventory logic were only safe after they rejected non-absolute inputs explicitly and proved that manifest-derived paths still lived under the selected backup root after normalization. Future ops/preflight/restore code should always separate path normalization from path authorization and enforce root containment before any filesystem action.

**Full entry:** history/learnings/20260331-repo-structure-wrapper-contracts.md

## [20260403] Always Escape User Data Before innerHTML Injection in Polling Renderers
**Category:** failure
**Feature:** ids-console-ui-pencil-rebuild
**Tags:** [security, xss, javascript, innerHTML, polling]

The Live Logs polling renderer in `console.js` injected `source_event_id` and `event_ts` raw into `innerHTML` on every poll cycle. Any DB-origin string containing `<`, `>`, or `&` becomes executable HTML. Jinja2's auto-escaping via `{{ }}` does not transfer to JS string concatenation — the two contexts have different escape contracts. Future JS polling/SSE renderers must add a minimal `esc()` helper (5 lines: replace `&`, `<`, `>`, `"`) and apply it to every non-constant field before `innerHTML` assignment. Add this to the reviewer checklist for any function that does `container.innerHTML = ...` with API data.

**Full entry:** history/learnings/20260403-console-ui-tdd-rebuild.md

## [20260403] Foundation-First Phase Structure Eliminates Base-Template Drift in Multi-Screen UI Rebuilds
**Category:** pattern
**Feature:** ids-console-ui-pencil-rebuild
**Tags:** [ui, jinja2, tdd, bead-decomposition, templates, css]

A 9-screen FastAPI/Jinja2 console was rebuilt cleanly in 3 phases by delivering the shared foundation first: CSS token layer + base template + auth + all routes as 501 stubs, all with passing tests. Subsequent phases implemented screens in order against a confirmed stable base. Workers never had to guess at template inheritance contracts or CSS variables mid-bead. Future full-page UI rewrites with shared base templates should make Phase 1 = foundation-only (no screen content), with explicit failing → passing tests for the shell before any screen work begins.

**Full entry:** history/learnings/20260403-console-ui-tdd-rebuild.md
