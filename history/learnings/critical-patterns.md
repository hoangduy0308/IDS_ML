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
