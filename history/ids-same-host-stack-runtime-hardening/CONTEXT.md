# IDS Same-Host Stack Runtime Hardening — Context

**Feature slug:** ids-same-host-stack-runtime-hardening
**Date:** 2026-03-29
**Exploring session:** complete
**Scope:** Deep

---

## Feature Boundary

This feature delivers one explicit same-host Linux deployment and operations contract that wires model bundle activation, live sensor runtime, operator console runtime, notification worker runtime, and the optional reverse-proxy seam into one bootstrapable, deployable, smokeable, recoverable system without expanding into multi-host control-plane or new product capabilities.

**Domain type(s):** RUN | CALL | READ | ORGANIZE

---

## Locked Decisions

These are fixed. Planning must implement them exactly. No creative reinterpretation.

### Stack Shape
- **D1** Ship one thin stack-level canonical orchestrator for same-host bootstrap, preflight, smoke/status, and recovery/post-restore verification.
  *Rationale: The missing gap is the stack-level story, not another component runtime. A thin orchestrator gives one canonical host contract while preserving the existing service contracts underneath it.*

- **D2** The thin stack orchestrator must delegate to the existing service-specific commands and units instead of re-owning their logic.
  *Rationale: Mutation and runtime ownership must stay explicit per failure domain. The new layer coordinates; it does not become a control-plane.*

- **D3** Existing service-specific ownership stays unchanged:
  *Rationale: This preserves clear boundaries and avoids smearing responsibilities across the stack layer.*
  - model bundle activation and rollback remain owned by `scripts/ids_model_bundle_manage.py`
  - live sensing remains owned by `deploy/systemd/ids-live-sensor.service` and `scripts/ids_live_sensor.py`
  - operator console schema/bootstrap/backup/restore/smoke remain owned by `scripts/ids_operator_console_manage.py`
  - notification runtime remains owned by `deploy/systemd/ids-operator-console-notify.service` plus `scripts/ids_operator_console_manage.py notify-*`

### Health, Smoke, And Failure Domains
- **D4** Stack-level `status` and `smoke` must be canonical at the new stack layer, but they must report component results per failure domain instead of collapsing everything into one opaque verdict.
  *Rationale: The user explicitly wants `EXISTS / SUBSTANTIVE / WIRED` at the whole-system boundary while keeping failure domains clear.*

- **D5** Top-level stack healthy requires:
  *Rationale: The system should be considered operational only when the real same-host data and operator runtimes are ready, while still treating optional/edge seams honestly.*
  - active bundle contract resolves and is runtime-ready
  - live sensor runtime contract is healthy
  - operator console runtime contract is healthy
  - notification worker is healthy when notifications are configured/enabled on the host
  - notification worker is explicit `disabled` and non-blocking when notifications are intentionally not configured
  - reverse proxy is never a top-level readiness gate

- **D6** Reverse proxy is a supported, documented, production-facing dependency for operator visibility, but it remains a non-gating edge seam.
  *Rationale: Proxy failure must degrade operator access, not erase the distinction between internal runtime health and external edge reachability.*

- **D7** Stack reporting must keep these failure domains separate and named explicitly:
  *Rationale: The feature must not blur ownership or make one service look like an implicit side effect of another.*
  - model activation contract
  - live sensor data path
  - operator visibility path
  - outbound notification path
  - reverse proxy edge seam

- **D8** Operator-console visibility of the active model bundle remains read-only and summary-backed; the stack layer must not create a second source of truth for live bundle state.
  *Rationale: The console already reads active-bundle metadata from ingested sensor summaries, and promotion/rollback remain outside the web UI.*

### Bootstrap And Preflight
- **D9** Fresh-host bootstrap order is fixed:
  *Rationale: The host needs one reproducible order that turns separate hardened components into one recoverable system contract.*
  1. prepare host layout, env files, and secret files
  2. install/verify candidate model bundle and activate it through `ids_model_bundle_manage.py`
  3. initialize operator console state through `migrate --allow-bootstrap` and `bootstrap-admin`
  4. run stack-level preflight
  5. start `ids-operator-console.service`
  6. start `ids-live-sensor.service`
  7. start `ids-operator-console-notify.service` only when notifications are enabled
  8. run stack-level smoke/status
  9. run reverse-proxy seam smoke when a proxy is configured for the host

- **D10** Stack-level preflight must be one canonical command at the stack layer and must compose, not duplicate, the existing per-service preflight and status contracts.
  *Rationale: The stack needs one deploy gate, but the repo already has exact-path preflight and verify-only startup patterns that should stay authoritative.*

- **D11** Stack preflight must verify host layout and configuration seams explicitly across `/opt`, `/var/lib`, `/var/log`, env files, and secret-file references instead of relying on undocumented assumptions.
  *Rationale: The user wants a deployable same-host system contract, not an implicit pile of per-service defaults.*

### Recovery And Restore
- **D12** Restart and recovery remain supervisor-first: each runtime is restarted and diagnosed in its own failure domain, while the stack layer provides the canonical recovery ordering and verification path.
  *Rationale: systemd owns runtime restarts; the new feature should add an operational contract, not replace the supervisor.*

- **D13** Backup/restore for stack readiness must cover at minimum:
  *Rationale: These are the host-local state elements that determine whether the stack can come back in a meaningful same-host production shape.*
  - `/var/lib/ids-live-sensor/active_bundle.json`
  - the bundle directories referenced by the activation record
  - `/var/lib/ids-operator-console/operator_console.db`
  - operator backup manifests and secret references required to restore the console correctly

- **D14** Live sensor JSONL outputs and logs are operator evidence and should be preserved when practical, but they are not the primary mutation state required to restore scoring readiness.
  *Rationale: The stack should restore the runtime contract first; forensic artifacts remain important but should not be conflated with the core activation/database state needed for readiness.*

- **D15** Post-restore verification must be a first-class stack contract: after restore, the system is not considered recovered until the active bundle re-validates, the console smoke path passes, notification status/redrive is checked when enabled, and bundle visibility is re-established through restored or freshly ingested sensor summaries.
  *Rationale: Restore without post-restore proof is exactly the kind of partial integration drift this feature is meant to eliminate.*

### Scope Boundary
- **D16** This feature stays strictly same-host and integration-focused.
  *Rationale: The user explicitly framed this as finishing system integration, not adding a new platform layer.*
  - no multi-host fleet or control-plane work
  - no webhook/SIEM/email/IPS/auto-response expansion
  - no UI/UX feature expansion

### Agent's Discretion
- Exact command names, module layout, and test strategy for the new stack-level orchestrator are delegated to planning and validation, as long as they honor D1-D16.
- Exact implementation of reverse-proxy seam smoke is delegated to planning, as long as it stays optional/non-gating and production-facing only.
- Exact artifact shape for stack runbooks/docs is delegated to planning, as long as runbooks match shipped commands and verification paths exactly.

---

## Specific Ideas & References

- The stack feature should feel like the missing integration layer on top of already hardened components, not like a new platform product.
- The new stack contract should prove real host lifecycle paths:
  - fresh bootstrap
  - stack preflight
  - stack smoke/status
  - restart/recovery
  - backup/restore plus post-restore verification
- Review must continue using `EXISTS / SUBSTANTIVE / WIRED`, but at the stack boundary rather than stopping at individual service correctness.
- Reverse proxy remains part of the operator-console edge story, not the owner of whole-stack readiness.

---

## Existing Code Context

From the quick codebase scout during exploring.
Downstream agents: read these files before planning to avoid reinventing existing patterns.

### Reusable Assets
- `deploy/systemd/ids-live-sensor.service` — exact env, preflight, activation-path, and runtime contract for the live sensor daemon.
- `deploy/systemd/ids-operator-console.service` — console runtime unit with verify-only startup and proxy-facing environment contract.
- `deploy/systemd/ids-operator-console-notify.service` — explicit same-host notification worker unit separated from the web process.
- `deploy/nginx/ids-operator-console.conf.example` — current reverse-proxy seam for the operator-console edge.
- `scripts/ids_live_sensor.py` — canonical live sensor daemon composition across capture, bridge, realtime inference, and local sinks.
- `scripts/ids_live_sensor_preflight.py` — exact-path sensor preflight including NIC, helper binaries, writable paths, activation record, and bundle compatibility.
- `scripts/ids_model_bundle_manage.py` — canonical active-bundle status/verify/promote/rollback contract.
- `scripts/ids_operator_console_manage.py` — canonical operator CLI for migrate/bootstrap-admin/backup/restore/smoke/notify-* flows.
- `scripts/ids_operator_console_preflight.py` — verify-only console preflight covering runtime artifacts, proxy config, secrets, schema state, and optional Telegram contract.
- `scripts/ids_operator_console/ops.py` — underlying backup/restore/smoke/notification maintenance helpers that the management CLI exposes.
- `scripts/ids_operator_console/health.py` — readiness payload logic showing active bundle and non-gating notification semantics.

### Established Patterns
- Verify-only startup with explicit operator mutation paths: live sensor startup resolves/validates activation state; console startup verifies schema/bootstrap instead of mutating them.
- Exact-path preflight and one config source: systemd units pass explicit environment values into both `ExecStartPre=` and `ExecStart=`.
- Separate failure domains for long-running workers: notification ownership is outside the web process; capture failure and runtime failure stay distinct in the sensor.
- Read-only active-bundle visibility: the console surfaces active bundle state from sensor summary ingest rather than owning promotion state itself.
- Non-gating degraded subsystems: notification can be visible as `disabled` or `degraded` without collapsing console readiness by itself; the proxy seam is already modeled as outside app ownership.

### Integration Points
- `/var/lib/ids-live-sensor/active_bundle.json` — host-local activation record resolved by the live sensor runtime and model-bundle CLI.
- `/var/log/ids-live-sensor/ids_live_sensor_summary.jsonl` — summary stream that carries active-bundle visibility into the operator console.
- `/var/lib/ids-operator-console/operator_console.db` — console and notification worker shared persistent state.
- `scripts/ids_operator_console/web.py:create_operator_console_web_app` — canonical app factory behind the server entrypoint and smoke path.
- `ids-operator-console-notify.service` -> `scripts/ids_operator_console_manage.py notify-worker` — supervised outbound notification runtime using the same database/env contract as the console.
- `deploy/nginx/ids-operator-console.conf.example` -> `127.0.0.1:8765` — current edge seam for loopback console exposure.

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `AGENTS.md` — Khuym workflow, phase gates, and repo-specific rules for this project.
- `.khuym/STATE.md` — current feature state and phase anchor.
- `history/learnings/critical-patterns.md` — promoted critical patterns that must shape planning and validation.
- `history/learnings/20260328-live-sensor-runtime-contracts.md` — live sensor runtime/preflight/systemd lessons.
- `history/learnings/20260328-operator-console-runtime-wiring.md` — entrypoint wiring and `EXISTS / SUBSTANTIVE / WIRED` review lessons.
- `history/learnings/20260329-operator-console-production-hardening.md` — verify-only startup, proxy, and secret/preflight lessons.
- `history/learnings/20260329-model-bundle-promotion-hardening.md` — one activation contract for production bundle selection.
- `history/learnings/20260329-notification-runtime-contracts.md` — worker separation, long-running notification ownership, and restore/redrive lessons.
- `docs/final_model_bundle.md` — versioned model-bundle and activation-record contract.
- `docs/ids_live_sensor_architecture.md` — live sensor runtime boundary and same-host filesystem layout.
- `docs/ids_live_sensor_operations.md` — live sensor startup, promotion/rollback, and restore expectations.
- `docs/ids_operator_console_architecture.md` — console runtime, proxy, readiness, and notification boundary.
- `docs/ids_operator_console_operations.md` — operator bootstrap, smoke, backup/restore, and notification recovery flows.
- `docs/ids_realtime_pipeline_architecture.md` — runtime scoring boundary below the live sensor.
- `docs/ids_record_adapter_architecture.md` — adapter-to-runtime handoff boundary for flow records.
- `docs/ids_inference_architecture.md` — inference boundary and alerting/data-path responsibilities.
- `docs/experiment_progress_checkpoint.md` — final model choice and deployment-stage framing.

---

## Outstanding Questions

### Deferred to Planning
- [ ] What exact command surface should the new stack-level orchestrator expose (`bootstrap`, `preflight`, `status`, `smoke`, `recover-check`, `post-restore-check`, or similar) while still remaining thin? — This is a technical packaging decision that must align tests, docs, and Linux deployment ergonomics.
- [ ] How should the stack layer gather runtime evidence for the live sensor domain in a way that is testable in-repo without inventing a fake second readiness source? — Planning needs to choose the right seam between preflight, activation status, summary evidence, and service/runtime inspection.
- [ ] Should stack backup/restore ship a wrapper artifact that coordinates the existing per-service commands plus activation-record capture, or should the stack layer remain verification-only for restore while docs/runbooks orchestrate the mutation steps? — This is a design tradeoff about thin orchestration versus convenience wrappers and needs explicit validation before execution.
- [ ] What exact reverse-proxy seam check should be wired when a proxy is configured on-host? — Planning needs to choose a production-facing verification path that is real but still optional/non-gating.

---

## Deferred Ideas

- Multi-host rollout, fleet health, or control-plane style orchestration — explicitly out of scope for this feature.
- Webhook, SIEM, email, IPS, or auto-response integrations — explicitly out of scope for this feature.
- UI/UX redesign of the operator console — explicitly out of scope for this feature.

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions, code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1, D2...) are stable. Reference them by ID in all downstream artifacts.
