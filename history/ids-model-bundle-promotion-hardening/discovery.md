# Discovery Report: IDS Model Bundle Promotion Hardening

**Date**: 2026-03-29
**Feature**: ids-model-bundle-promotion-hardening
**CONTEXT.md reference**: `history/ids-model-bundle-promotion-hardening/CONTEXT.md`

---

## Institutional Learnings

> Read during Phase 0 from `history/learnings/`

### Critical Patterns (Always Applied)

- `history/learnings/critical-patterns.md` — rollback on filesystem state must stay on atomic rename/replace only; never add copy-based fallback restore paths.
- `history/learnings/critical-patterns.md` — Linux service hardening should use one exact-path config source and a dedicated preflight contract.
- `history/learnings/critical-patterns.md` — runtime mutation and operator mutation must stay separate; startup should verify, not self-heal.

### Domain-Specific Learnings

| File | Module | Key Insight | Severity |
|------|--------|-------------|----------|
| `history/learnings/20260328-adapter-rollback-contract.md` | Filesystem publish/rollback | Stage state first, promote transactionally, and fail closed if restore cannot complete atomically. | high |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | Live sensor runtime/preflight | Systemd-facing runtime values must flow through one config source and one explicit preflight, not drift across service/unit/runtime layers. | high |
| `history/learnings/20260328-operator-console-runtime-wiring.md` | Service wiring/review | Review must verify EXISTS / SUBSTANTIVE / WIRED, especially for entrypoints, summaries, and deployment surfaces. | high |
| `history/learnings/20260329-operator-console-production-hardening.md` | Operator mutation paths | Bootstrap/migrate/recovery style mutations belong in explicit management commands, while runtime startup remains verify-only. | high |

---

## Agent A: Architecture Snapshot

> Source: file tree analysis, targeted file reading

### Relevant Packages / Modules

| Package/Module | Purpose | Key Files |
|----------------|---------|-----------|
| `scripts/ids_inference.py` | Canonical bundle/model config loader and batch scoring path | `scripts/ids_inference.py`, `tests/test_ids_inference.py` |
| `scripts/package_final_model.py` | Current final bundle packager | `scripts/package_final_model.py`, `docs/final_model_bundle.md` |
| `scripts/ids_realtime_pipeline.py` | Micro-batch scoring around `IDSInferencer` | `scripts/ids_realtime_pipeline.py`, `docs/ids_realtime_pipeline_architecture.md`, `tests/test_ids_realtime_pipeline.py` |
| `scripts/ids_live_sensor.py` | Same-host daemon entrypoint that composes capture, extraction, runtime, and local sinks | `scripts/ids_live_sensor.py`, `docs/ids_live_sensor_architecture.md`, `tests/test_ids_live_sensor.py` |
| `scripts/ids_live_sensor_preflight.py` | Systemd `ExecStartPre` contract for the sensor | `scripts/ids_live_sensor_preflight.py`, `tests/test_ids_live_sensor_preflight.py`, `deploy/systemd/ids-live-sensor.service` |
| `scripts/ids_live_sensor_sinks.py` | Durable alert/quarantine/summary publication | `scripts/ids_live_sensor_sinks.py`, `tests/test_ids_live_sensor_sinks.py` |
| `scripts/ids_operator_console/*` | Same-host operator service, ingest path, readiness, and dashboard | `scripts/ids_operator_console_manage.py`, `scripts/ids_operator_console/config.py`, `scripts/ids_operator_console/ingest.py`, `scripts/ids_operator_console/health.py`, `scripts/ids_operator_console/web.py`, `scripts/ids_operator_console/templates/dashboard.html` |
| `artifacts/final_model/catboost_full_data_v1` | Current finalized bundle payload | `artifacts/final_model/catboost_full_data_v1/model_bundle.json`, `artifacts/final_model/catboost_full_data_v1/feature_columns.json` |

### Entry Points

- **CLI / scoring**: `scripts/ids_inference.py`
- **Bundle packaging**: `scripts/package_final_model.py`
- **Live daemon**: `scripts/ids_live_sensor.py`
- **Live preflight**: `scripts/ids_live_sensor_preflight.py`
- **Operator mutation CLI**: `scripts/ids_operator_console_manage.py`
- **Operator service**: `scripts/ids_operator_console_server.py` with app factory in `scripts/ids_operator_console/web.py`
- **Systemd deployment**: `deploy/systemd/ids-live-sensor.service`, `deploy/systemd/ids-operator-console.service`

### Key Files to Model After

- `scripts/ids_operator_console_manage.py` — demonstrates the repo’s preferred explicit mutation CLI pattern (`status`, `migrate`, `bootstrap-admin`, `backup`, `restore`, `smoke`).
- `scripts/ids_live_sensor_preflight.py` — demonstrates exact-path preflight checks for same-host Linux services.
- `scripts/ids_live_sensor_sinks.py` — demonstrates durable runtime summary payload publication and contains an existing transactional promotion helper.
- `scripts/ids_record_adapter.py` — contains the same transactional staged-output promotion pattern and related rollback tests that already encode the no-copy-fallback lesson.
- `scripts/ids_operator_console/web.py` + `scripts/ids_operator_console/templates/dashboard.html` — demonstrate how latest summary payloads become operator-visible state.

---

## Agent B: Pattern Search

> Source: targeted grep and code reading

### Similar Existing Implementations

| Feature/Component | Location | Pattern Used | Reusable? |
|-------------------|----------|--------------|-----------|
| Explicit operator mutations | `scripts/ids_operator_console_manage.py` | Explicit subcommands for all state-changing actions; runtime remains verify-only | Yes |
| Runtime-to-preflight contract parity | `scripts/ids_operator_console/config.py` + `scripts/ids_operator_console_preflight.py` | Preflight consumes the same runtime-facing inputs and blocks startup when contract is narrower than runtime | Yes |
| Exact-path Linux service preflight | `scripts/ids_live_sensor_preflight.py` + `deploy/systemd/ids-live-sensor.service` | Service values are declared once and reused in `ExecStartPre` and `ExecStart` | Yes |
| Transactional filesystem promotion | `scripts/ids_live_sensor_sinks.py` and `scripts/ids_record_adapter.py` | Stage temp paths, promote with `Path.replace()`, restore backups only via rename/replace | Yes |
| Operator visibility via summaries | `scripts/ids_live_sensor_sinks.py` -> `scripts/ids_operator_console/ingest.py` -> `scripts/ids_operator_console/db.py` -> `scripts/ids_operator_console/web.py` | Runtime publishes summary JSONL, console ingests/stores/display it | Yes |

### Reusable Utilities

- **Bundle config loading**: `scripts/ids_inference.py` — already resolves a bundle-local `model_bundle.json` and returns `IDSModelConfig`.
- **Feature contract validation**: `scripts/ids_feature_contract.py` — already enforces the canonical feature schema and fail-closed numeric conversion behavior.
- **Transactional publish helper**: `_promote_staged_output_paths_transactionally()` in `scripts/ids_live_sensor_sinks.py` and `scripts/ids_record_adapter.py`.
- **Summary ingest pipeline**: `scripts/ids_operator_console/ingest.py` — summary records are opaque payloads, so new active-bundle fields can flow through without schema redesign.
- **Readiness payload construction**: `scripts/ids_operator_console/health.py` — existing place to expose new active-bundle readiness state.

### Naming Conventions

- Python scripts use `snake_case` filenames and `argparse` entrypoints with `parse_args()`, `main()`, and small dataclass configs.
- Management CLIs prefer explicit subcommands over mode flags.
- Tests use `tests/test_<module>.py` and exercise both unit-level behavior and deploy wiring contracts.
- Runtime summaries are JSON objects with explicit field names and are treated as durable operational state.

---

## Agent C: Constraints Analysis

> Source: existing scripts, deploy artifacts, and tests

### Runtime & Framework

- **Runtime**: Python 3 via `/usr/bin/python3` in systemd artifacts
- **Language**: Python
- **Web framework**: FastAPI + Jinja2 for the operator console
- **Storage**: local filesystem for bundle/runtime artifacts, SQLite for operator state, JSONL for sensor outputs

### Existing Dependencies (Relevant to This Feature)

| Package | Purpose |
|---------|---------|
| `catboost` | Model loading and scoring in `scripts/ids_inference.py` |
| `pandas` | DataFrame alignment/scoring path |
| `fastapi` / `starlette` / `jinja2` | Operator console service and dashboard |
| `sqlite3` | Embedded operator store |
| Python stdlib `argparse`, `json`, `pathlib`, `dataclasses` | Existing CLI/config/runtime patterns |

### New Dependencies Needed

| Package | Reason | Risk Level |
|---------|--------|------------|
| None required by current plan | The feature can be built on existing Python stdlib, current ML runtime, and current console stack | low |

### Build / Quality Requirements

```bash
# Must pass before bead is closeable:
python -m py_compile scripts/ids_inference.py scripts/package_final_model.py scripts/ids_live_sensor.py scripts/ids_live_sensor_preflight.py scripts/ids_operator_console_manage.py scripts/ids_operator_console/*.py
python -m pytest -q tests/test_ids_inference.py tests/test_ids_live_sensor_preflight.py tests/test_ids_live_sensor.py tests/test_ids_live_sensor_sinks.py tests/test_ids_operator_console_ingest.py tests/test_ids_operator_console_web.py tests/test_ids_operator_console_preflight.py tests/test_ids_operator_console_ops.py
```

### Database / Storage

- **Operator state**: SQLite via `scripts/ids_operator_console/db.py`
- **Operational ingress**: JSONL summary stream ingested by `scripts/ids_operator_console/ingest.py`
- **Deployment state**: host-local filesystem paths in systemd env vars and bundle directories under the repo/deploy root
- **Current gap**: there is no canonical active-bundle state file or activation journal yet

---

## Agent D: External Research

> Source: intentionally skipped
> Guided by locked decisions in CONTEXT.md — not generic research

No external research required for planning. The feature can be implemented with repo-native Python/service patterns and existing standard-library filesystem semantics. Validating may still choose a local spike to confirm edge-case behavior for the activation pointer and rollback contract, but planning does not require a new library or internet dependency.

---

## Open Questions

> Items that were not resolvable through research alone.
> These will be raised to the synthesis phase in Phase 2.

- [ ] Should the versioned compatibility metadata evolve `model_bundle.json` in place, or should a successor manifest be introduced with a compatibility reader? — impacts migration ergonomics and test surface.
- [ ] Should the activation state live as a pointer file, a symlink-like contract, or a small activation journal plus current pointer? — impacts rollback provenance and restore semantics.
- [ ] Should promote/rollback live in a dedicated `ids_model_bundle_manage.py` CLI or be folded into an existing management script family? — impacts operational discoverability and file scope.
- [ ] What same-host smoke input source is safest for candidate verification without building a new replay subsystem? — impacts validating spike design and operational trust.

---

## Summary for Synthesis (Phase 2 Input)

> Brief synthesis for the approach.

**What we have**: a finalized bundle format, bundle-backed scoring path, live sensor runtime, exact-path preflight patterns, runtime summary publication, and an operator console that already ingests and displays summary-derived operational state.

**What we need**: a canonical production bundle lifecycle around those pieces: versioned compatibility metadata, one active bundle resolution path, explicit promote/activate/rollback commands, fail-closed startup/readiness, and operator visibility for active-model state.

**Key constraints from research**:
- Runtime startup must stay verify-only and must not mutate active-model state.
- Preflight and runtime must consume the same exact-path activation contract; split env/model/schema paths are a known drift seam.
- New work should avoid new dependencies and stay inside the existing Python + JSONL + SQLite + systemd topology.

**Institutional warnings to honor**:
- Never add copy-based rollback fallback logic; restore via atomic replace only.
- Treat deploy artifacts, preflight, runtime, and console visibility as one wired contract, not isolated modules.
