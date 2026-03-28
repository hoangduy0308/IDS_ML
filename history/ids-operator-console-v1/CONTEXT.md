# IDS Operator Console V1 — Context

**Feature slug:** ids-operator-console-v1
**Date:** 2026-03-28
**Exploring session:** complete
**Scope:** Deep

---

## Feature Boundary

This feature productizes the existing single-host IDS runtime into a user-facing operator platform by adding a separate backend service, centralized operational storage, authenticated dashboard access, alert triage workflow, health visibility, reporting/export, and Telegram notification delivery; it does not turn the IDS into an IPS/control plane, replace the existing sensor pipeline, or introduce multi-host fleet management in v1.

**Domain type(s):** SEE | CALL | RUN | ORGANIZE

---

## Locked Decisions

These are fixed. Planning must implement them exactly. No creative reinterpretation.

### Product Direction
- **D1** The next completion phase must include a user-facing dashboard/operator experience, not only local JSONL/journald outputs.
  *Rationale: The user wants an IDS that feels complete for operators, not just a daemon that writes local artifacts.*

- **D2** The next phase focuses on a user platform made of `backend API + centralized storage + operator dashboard`, while the live sensor remains the upstream producer.
  *Rationale: The repo already has the IDS detection runtime; the missing subsystem is the product layer around it.*

- **D3** v1 serves one host/sensor first, but the schema and API must remain sensor-aware so later work can expand to multiple sensors/hosts.
  *Rationale: This preserves the current one-host runtime boundary while avoiding a dead-end data model.*

- **D4** The primary UX is a `combined console` with alert triage at the center and sensor health/telemetry as supporting context.
  *Rationale: Operators need to distinguish “no alerts” from “sensor unhealthy,” so triage and health must live together.*

### Architecture Boundary
- **D5** The dashboard/backend is a separate web app/service behind the existing live sensor producer.
  *Rationale: The current sensor boundary is already clear and should stay narrow; the product layer should consume its outputs rather than collapsing into the daemon.*

- **D8** Backend v1 ingests from the existing sensor outputs (`alerts`, `quarantine`, `summary`) first, with the ingest layer designed so later work can extend to push/webhook/broker transports.
  *Rationale: Reusing the current output contract is the safest path to a product layer without destabilizing the live sensor.*

- **D20** v1 deploys the dashboard/backend on the same machine as the sensor, but as a separate service rather than embedding it into the daemon.
  *Rationale: Same-host deployment keeps self-hosting simple for v1 while preserving a clean service boundary.*

### Access And Workflow
- **D6** v1 starts with one internal admin user rather than multiple roles.
  *Rationale: This keeps the first product slice focused while still requiring authenticated access.*

- **D7** v1 alert workflow includes the states `new`, `acknowledged`, `investigating`, `resolved`, and `false_positive`.
  *Rationale: A production IDS console needs more than passive viewing; operators need real triage state transitions.*

- **D10** Dashboard/backend v1 is a `read/triage/monitoring` console, not a control plane for changing sensor config, threshold, or service behavior directly from the UI.
  *Rationale: Remote mutation and service control introduce a separate operational risk surface that should not be mixed into the first user platform.*

- **D14** Dashboard/API v1 requires login for the single internal admin user.
  *Rationale: Even with only one admin, the product layer must not be an open internal page with no authentication boundary.*

- **D16** Each alert supports investigation notes and status history.
  *Rationale: Triage without notes/history would be too shallow for real operator workflow.*

- **D17** v1 remains an `IDS`, not an `IPS`; the dashboard only supports `observe / triage / report / notify`, with no active response actions from the UI.
  *Rationale: Automated or manual response introduces safety, rollback, and audit concerns that belong to a later feature.*

- **D18** v1 handles each alert independently and does not introduce incident/case management yet.
  *Rationale: Case management is its own subsystem; v1 should keep alert detail rich enough for manual investigation without opening that larger scope.*

### Data And Signal Semantics
- **D9** `quarantine/schema anomaly` is an operational signal separate from the `attack alert` queue, but it still appears inside the same combined console as its own panel/section.
  *Rationale: The repo already treats schema anomalies as pipeline/forensic events rather than model-derived attack predictions.*

- **D11** Product-layer storage in v1 keeps `alerts + anomalies + summaries` plus enough metadata for drill-down, but does not ingest full raw/adapted event history into the dashboard datastore.
  *Rationale: This keeps the operator platform useful without prematurely turning it into a high-volume forensic data lake.*
  For anomaly records, the product layer should preserve the repo's existing redaction-first posture by default rather than assuming raw source payloads are always present or always safe to expose/export.

- **D15** v1 includes reporting/history and export for `alerts`, `anomalies`, and `sensor summaries`.
  *Rationale: A user-facing IDS console should support internal reporting and historical review from day one.*

- **D19** v1 includes basic `suppression/whitelist` capability to reduce noise, but not a complex policy engine.
  *Rationale: Without some noise control, the operator queue will degrade quickly; however, a full rules engine is beyond the initial platform slice.*
  This suppression capability applies to operator-facing attack-alert presentation/notification only; it must not hide pipeline `schema_anomaly` visibility or mutate sensor-side detection behavior.

### Notification
- **D12** v1 includes at least one proactive outbound notification path in addition to the dashboard.
  *Rationale: A production IDS should not rely solely on an operator manually opening the console.*

- **D13** The first outbound notification channel is `Telegram`.
  *Rationale: It is a practical first internal notification path and aligns with the repo’s previously deferred expansion direction.*

### Agent's Discretion
- The planner/implementer may choose the concrete backend framework, UI stack, and storage engine as long as they honor the locked same-host, separate-service, authenticated admin-console boundary.
- The planner/implementer may choose the concrete ingest mechanism for reading sensor outputs as long as the first supported source of truth is the existing alert/quarantine/summary output contract.
- The planner/implementer may choose the exact dashboard information architecture, page layout, and visual treatment as long as the combined console keeps alert triage central and surfaces sensor health prominently.
- The planner/implementer may choose the exact note/history/export/suppression data schema as long as it preserves the locked workflow and separates attack alerts from operational anomalies.
- The planner/implementer may choose the exact anomaly-detail and export presentation as long as default views stay consistent with the current redaction-first handling of quarantine/source payloads.

---

## Specific Ideas & References

- User intent: “hoàn thiện hệ thống ids” as a product for operators, not just continue improving the model/runtime internals.
- Clarified target: the user wants “dashboard hay cái gì đó đầy đủ cho người dùng,” meaning the next feature should make the IDS usable by a human operator.
- Scope refinement from exploring: the repo’s current IDS core already exists, so the next foundational work is the operator-facing platform around it rather than another round of sensor or model experimentation.

---

## Existing Code Context

From the quick codebase scout during exploring.
Downstream agents: read these files before planning to avoid reinventing existing patterns.

### Reusable Assets
- `F:/Work/IDS_ML_New/scripts/ids_live_sensor.py` — the current same-host daemon composition that produces the live IDS outputs the new backend will consume.
- `F:/Work/IDS_ML_New/scripts/ids_live_sensor_sinks.py` — defines the existing local output contract for alerts, quarantines, and summaries, including journald-friendly summary formatting.
- `F:/Work/IDS_ML_New/scripts/ids_realtime_pipeline.py` — defines the current `model_prediction` and `schema_anomaly` event boundary and the JSONL-oriented runtime surface upstream of the new platform.
- `F:/Work/IDS_ML_New/deploy/systemd/ids-live-sensor.service` — sample deployment shape showing the current same-host operational model and environment-driven configuration.

### Established Patterns
- Local-first durable outputs: the current sensor writes alert/quarantine/summary artifacts to local JSONL plus journald rather than depending on a broker or external service.
- Strict signal separation: `model alerts` and `schema/pipeline anomalies` are intentionally different signal types and should remain distinct in the operator experience.
- IDS-not-IPS boundary: the existing feature history explicitly defers active response and keeps the deployed system focused on detection, visibility, and operator review.
- Single-host operational envelope: the current live deployment target is one Linux host and one configured NIC, which the new product layer should respect in v1.

### Integration Points
- `F:/Work/IDS_ML_New/docs/ids_live_sensor_architecture.md` — documents the live sensor’s contract, deferred features, and local output shape that the backend must consume.
- `F:/Work/IDS_ML_New/docs/ids_live_sensor_operations.md` — documents the operational expectations for the sensor, including JSONL/journald traces and same-host systemd behavior.
- `F:/Work/IDS_ML_New/docs/ids_realtime_pipeline_architecture.md` — documents the semantic split between attack alerts and schema anomalies that the dashboard must preserve.
- `F:/Work/IDS_ML_New/docs/ids_inference_architecture.md` — shows the intended downstream “alert sink / dashboard / response flow” role and clarifies where the operator platform begins.

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `F:/Work/IDS_ML_New/history/ids-live-host-based-ml-ids/CONTEXT.md` — locked decisions for the current live sensor boundary that this feature must wrap, not replace.
- `F:/Work/IDS_ML_New/docs/ids_live_sensor_architecture.md` — current live sensor architecture, output streams, and deferred feature list.
- `F:/Work/IDS_ML_New/docs/ids_live_sensor_operations.md` — same-host deployment and operator-facing runtime traces.
- `F:/Work/IDS_ML_New/docs/ids_realtime_pipeline_architecture.md` — event semantics for `model_prediction` vs `schema_anomaly`.
- `F:/Work/IDS_ML_New/docs/ids_inference_architecture.md` — current downstream role of dashboard/alert sink after inference.
- `F:/Work/IDS_ML_New/deploy/systemd/ids-live-sensor.service` — concrete deployment reference for the existing producer side.

---

## Outstanding Questions

### Deferred to Planning
- [ ] What concrete backend framework, UI stack, and storage engine best fit a same-host self-hosted IDS console? — Planning should compare realistic implementation options without violating the locked product boundary.
- [ ] What ingest mechanism should the backend use to consume `alerts`, `quarantine`, and `summary` outputs reliably on the same machine? — Planning should choose the safest v1 contract, whether tailing JSONL, periodic import, or a local queue/watcher pattern.
- [ ] What exact relational/data model should represent alerts, anomaly records, summaries, notes, state-history entries, suppression rules, and login state? — Planning should design the minimal schema that supports the locked workflow without overfitting to v1.
- [ ] What exact dashboard information architecture should implement the combined console while keeping alert triage central and health prominent? — Planning should translate the locked UX direction into concrete pages/panels/components.
- [ ] How should Telegram delivery, retries, and suppression interaction work in v1? — Planning should define the first outbound notification contract and operational safeguards.
- [ ] What authentication mechanism is appropriate for a same-host single-admin deployment? — Planning should choose the simplest secure admin login path for v1.
- [ ] How should export/report generation work technically for alerts, anomalies, and summaries? — Planning should define formats, filters, and generation surfaces without expanding into a full BI/reporting subsystem.

---

## Deferred Ideas

- Multi-host / fleet management — deferred because v1 intentionally starts with one host/sensor even though the schema/API should stay sensor-aware.
- Direct UI control of sensor config, model thresholds, or service lifecycle — deferred because this would turn the console into a control plane.
- IPS / active response actions from the dashboard — deferred because the product remains IDS-only in v1.
- Full raw/adapted event-history ingestion into the product datastore — deferred because v1 is not a forensic data lake.
- Incident/case management — deferred because alert-level triage is sufficient for the first product slice.
- Complex rule engine for suppression, correlation, or response automation — deferred because v1 only needs basic suppression/whitelist capability.
- Additional outbound integrations beyond Telegram (`SIEM`, `webhook`, `email`, etc.) — deferred because one proactive channel is enough to prove the product layer first.

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions, code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1, D2...) are stable. Reference them by ID in all downstream artifacts.
