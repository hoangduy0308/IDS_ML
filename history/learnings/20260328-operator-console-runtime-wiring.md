---
date: 2026-03-28
feature: ids-operator-console-v1
categories: [failure, pattern, decision]
severity: critical
tags: [fastapi, runtime, deployment, review, testing]
---

# Learning: Keep The Service Entrypoint Wired To The Real App Factory

**Category:** failure
**Severity:** critical
**Tags:** [fastapi, runtime, deployment]
**Applicable-when:** Building any service that separates a server entrypoint file from the module that owns the real route tree or app factory

## What Happened

`ids_operator_console_server.py` originally kept a bootstrap-only FastAPI app with `/healthz` plus a placeholder root page, while the real authenticated dashboard, alert detail, anomaly, report, and API routes lived in `scripts/ids_operator_console/web.py`. Execution beads and route tests made the console itself real, but review caught that the runnable service path still pointed at the bootstrap app, so a systemd deployment would not expose the product the feature claimed to ship.

## Root Cause / Key Insight

The project had two parallel app-construction paths: one for the real feature and one for the server launcher. That split let implementation progress and even route-level tests look healthy while the deployment surface silently drifted away from the tested app. In service-style Python features, the runnable entrypoint is part of the feature contract, not just a thin wrapper to ignore until packaging.

## Recommendation for Future Work

Always make the server entrypoint import and run the same canonical app factory that owns the real routes. If the service needs extra endpoints like `/healthz`, add them to the canonical app or compose them in one place only. Add at least one regression test that proves the runnable server/app factory exposes a representative feature route, not only a bootstrap page.

---

# Learning: Use EXISTS-SUBSTANTIVE-WIRED Verification To Catch Runtime Drift

**Category:** pattern
**Severity:** standard
**Tags:** [review, verification, integration]
**Applicable-when:** Reviewing a feature that spans multiple layers such as route modules, service entrypoints, deployment files, and runtime integration boundaries

## What Happened

The operator console implementation looked complete on a normal bead-by-bead pass: the web routes existed, the templates were substantive, and the route tests passed. The blocker appeared only when reviewing applied the three-level artifact check and asked whether the feature was actually wired into the service entrypoint named by deployment.

## Root Cause / Key Insight

Module-level correctness is not the same as runtime integration. A feature can satisfy “exists” and “substantive” while still failing “wired” if the entrypoint, router registration, or deployment contract points at a different object than the one tests exercised.

## Recommendation for Future Work

When reviewing any service feature, explicitly verify all three levels: the artifact exists, the implementation is substantive, and the runtime/deployment path actually imports and uses it. Treat the “wired” check as mandatory for entrypoints, routers, workers, systemd units, and background jobs.

---

# Learning: The Python-Native Same-Host Console Stack Was The Right First Product Slice

**Category:** decision
**Severity:** standard
**Tags:** [architecture, fastapi, sqlite, same-host]
**Applicable-when:** Productizing a local-first Python service into an operator-facing v1 without introducing a separate frontend or external database stack

## What Happened

The feature shipped as `FastAPI + Jinja2 + sqlite3` on the same host as the existing sensor, using JSONL ingest instead of changing the producer contract. That choice let the team deliver auth, triage, reporting, notifications, preflight, and deployment in one slice while keeping write scopes small enough for swarming and verification clean enough for a full `173 passed` repo run.

## Root Cause / Key Insight

The repo already had strong Python, systemd, and local-artifact patterns. Aligning the product layer with those strengths removed unnecessary infrastructure risk and made the missing product concerns visible as normal code modules rather than as a multi-stack migration.

## Recommendation for Future Work

When wrapping an existing same-host Python daemon with a first operator-facing surface, prefer a Python-native web/service stack and embedded storage unless a locked requirement truly demands more infrastructure. Save SPA/external-DB expansion for the point where multi-host, multi-user, or scale requirements are real rather than hypothetical.
