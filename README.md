# IDS_ML_New

Repository for the IDS ML pipeline and the same-host runtime stack.

## Current navigation

- [docs/README.md](docs/README.md): start here for canonical vs historical docs
- [docs/current/README.md](docs/current/README.md): current docs home
- [docs/archive/README.md](docs/archive/README.md): archived docs home

Some legacy top-level docs under `docs/*.md` are compatibility stubs. Use `docs/current/` for active material.

## Core flow

`flow-based features -> preprocessing -> benchmark/tuning -> final model bundle -> inference/runtime IDS`

## Main areas

- [docs/current/runtime/README.md](docs/current/runtime/README.md)
- [docs/current/console/README.md](docs/current/console/README.md)
- [docs/current/operations/README.md](docs/current/operations/README.md)
- [docs/current/ml/README.md](docs/current/ml/README.md)

## Quick test

```powershell
python -m pytest tests/runtime/test_ids_inference.py tests/runtime/test_ids_realtime_pipeline.py tests/runtime/test_ids_record_adapter.py -q
```

```bash
python3.11 -m pytest tests/runtime/test_ids_inference.py tests/runtime/test_ids_realtime_pipeline.py tests/runtime/test_ids_record_adapter.py -q
```
