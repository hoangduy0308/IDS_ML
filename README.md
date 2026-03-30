# IDS_ML_New

Repository for the IDS ML pipeline and the same-host runtime stack.

## Current navigation

- [docs/README.md](F:/Work/IDS_ML_New/docs/README.md): start here for canonical vs historical docs
- [docs/current/README.md](F:/Work/IDS_ML_New/docs/current/README.md): current docs home
- [docs/archive/README.md](F:/Work/IDS_ML_New/docs/archive/README.md): archived docs home

## Core flow

`flow-based features -> preprocessing -> benchmark/tuning -> final model bundle -> inference/runtime IDS`

## Main areas

- [docs/current/runtime/README.md](F:/Work/IDS_ML_New/docs/current/runtime/README.md)
- [docs/current/console/README.md](F:/Work/IDS_ML_New/docs/current/console/README.md)
- [docs/current/operations/README.md](F:/Work/IDS_ML_New/docs/current/operations/README.md)
- [docs/current/ml/README.md](F:/Work/IDS_ML_New/docs/current/ml/README.md)

## Quick test

```powershell
python -m pytest tests/test_ids_inference.py tests/test_ids_realtime_pipeline.py tests/test_ids_record_adapter.py -q
```
