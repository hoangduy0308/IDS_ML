# Migration Map: Repo Structure Rationalization

**Feature:** `repo-structure-rationalization`  
**Phase:** 1 package spine and wrapper contract

This file is the initial routing map for downstream beads. It records the
canonical package names and the phase-1 compatibility rule so later work does
not invent a different structure.

## Canonical Package Spine

- `ids.core` for shared cross-domain contracts, schemas, config primitives, and
  other narrowly reusable definitions.
- `ids.runtime` for runtime-serving code: inference, live sensor, capture,
  bridge, extractor, adapter, and sink surfaces.
- `ids.console` for the operator console application package and its internal
  web, auth, DB, notifications, reporting, and asset wiring.
- `ids.ops` for preflight, manage, stack orchestration, and other maintenance
  entrypoints.

## Compatibility Rule

- `scripts/*.py` remains the public compatibility surface in phase 1.
- Each wrapper keeps its existing CLI signature.
- Wrappers delegate only to canonical `ids.*` package modules.
- No wrapper may introduce a reverse import from `ids` back into `scripts`.
- Thin wrappers may keep the repo-root bootstrap shim when direct file
  execution is still supported.

## Initial Phase-1 Mapping

| Current surface | Canonical target |
| --- | --- |
| `scripts/ids_feature_contract.py` | `ids/core/` |
| `scripts/ids_model_bundle.py` | `ids/core/` |
| `scripts/ids_inference.py` | `ids/runtime/` |
| `scripts/ids_live_capture.py` | `ids/runtime/` |
| `scripts/ids_live_flow_bridge.py` | `ids/runtime/` |
| `scripts/ids_live_sensor.py` | `ids/runtime/` |
| `scripts/ids_live_sensor_health.py` | `ids/runtime/` |
| `scripts/ids_live_sensor_sinks.py` | `ids/runtime/` |
| `scripts/ids_offline_window_extractor.py` | `ids/runtime/` |
| `scripts/ids_offline_window_serializer.py` | `ids/runtime/` |
| `scripts/ids_realtime_pipeline.py` | `ids/runtime/` |
| `scripts/ids_record_adapter.py` | `ids/runtime/` |
| `scripts/ids_operator_console/` | `ids/console/` |
| `scripts/ids_operator_console_preflight.py` | `ids/ops/` |
| `scripts/ids_operator_console_manage.py` | `ids/ops/` |
| `scripts/ids_operator_console_server.py` | `ids/ops/` or `ids/console/` wrapper seam, depending on final app-factory ownership |
| `scripts/ids_model_bundle_manage.py` | `ids/ops/` |
| `scripts/ids_same_host_stack.py` | `ids/ops/` |
| `scripts/ids_same_host_stack_manage.py` | `ids/ops/` |

## Out Of Scope For Phase 1

- No production-path logic moves are completed in this bead.
- No packaging metadata is introduced as a prerequisite.
- No training/benchmark/preprocessing code is moved yet; those remain for the
  separate `ml_pipeline` zone.
- No new public entrypoints are added.

## Downstream Expectations

- Keep the package tree shallow and explicit.
- Keep `ids.core` narrow; do not use it as a dumping ground.
- Move implementation behind the canonical package roots before deleting any
  compatibility wrappers.
- Preserve the current `scripts.*` CLI and file-execution surfaces until later
  beads deliberately retire them.
