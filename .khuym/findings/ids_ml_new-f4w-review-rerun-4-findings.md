## Review Rerun 4 Findings

### code-quality

- Severity: P2
  Title: Whitespace-normalized duplicate keys are only quarantined in one insertion order
  File: `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py`
  Problem: `_normalize_source_record()` only records a normalized-key collision when the later key is not already stripped, so payload ordering can let ambiguous duplicate keys pass instead of quarantine.
  Recommended fix: Quarantine whenever two distinct raw keys normalize to the same canonical source key, regardless of insertion order.

- Severity: P3
  Title: Redirected stdin sinks can leave partial output artifacts on open failure
  File: `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py`
  Problem: stdin redirected sink files are opened sequentially outside an `ExitStack`; if the second open fails, the first file may already be created or truncated.
  Recommended fix: Open redirected sinks under a single context manager and only expose handles after all opens succeed.

### architecture

- Severity: P2
  Title: Adapter duplicates ownership of the canonical 72-feature contract
  File: `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py`
  Problem: `SHIPPED_ADAPTER_FEATURE_COLUMNS` hardcodes the full canonical feature list and is used to build both the default contract and shipped profiles, creating a second owner for the model-facing schema.
  Recommended fix: Source default feature columns from the shared contract owner and let the adapter own only profile mappings and adapter-specific metadata/quarantine rules.

- Severity: P2
  Title: Shipped profile IDs are not stable contracts because their accepted keys are derived from downstream contract state
  File: `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py`
  Problem: `build_default_adapter_registry(feature_columns=...)` synthesizes accepted source keys for shipped profiles from injected contract columns, so the same shipped profile ID can mean different upstream surfaces.
  Recommended fix: Keep shipped profile definitions fixed and versioned; require explicit custom profile definitions for non-default contracts.

- Severity: P3
  Title: The reusable core API still has hidden repo-specific coupling to `scripts.ids_feature_contract`
  File: `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py`
  Problem: adaptation still imports `scripts.ids_feature_contract` and branches on its concrete `QuarantinedFlowRecord` type even when a caller injects an explicit contract.
  Recommended fix: Use a narrow validation-result protocol or discriminant so repo-specific imports stay in default wiring only.

### security

- No findings in security scope.

### test-coverage

- Severity: P2
  Title: Profile-definition guardrails are only partially tested
  Files: `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py`, `F:/Work/IDS_ML_New/tests/test_ids_record_adapter.py`
  Problem: `AdapterProfileDefinition.__post_init__` has multiple validation branches without direct tests for blank `profile_id`, duplicate alias targets, source-key overlap, invalid metadata targets, or controlled-extra overlap.
  Recommended fix: Add focused unit tests for each validation class and assert they fail with `ValueError`.

- Severity: P2
  Title: Numeric coercion is not exercised through the adapter boundary
  Files: `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py`, `F:/Work/IDS_ML_New/tests/test_ids_record_adapter.py`
  Problem: happy-path tests only use pre-floated values, and failure tests only use obviously bad strings; numeric strings and ints are not tested through adapter and CLI success paths.
  Recommended fix: Add direct adapter and CLI integration tests with representative numeric strings or ints and assert successful adaptation plus runtime handoff.

- Severity: P3
  Title: Custom-contract registry rebuild path has no test coverage
  Files: `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py`, `F:/Work/IDS_ML_New/tests/test_ids_record_adapter.py`
  Problem: the lazy registry rebuild path for custom contracts is only covered by mismatch rejection, not by a successful adaptation case.
  Recommended fix: Add a unit test constructing `StructuredRecordAdapter(contract=FlowFeatureContract([...]))` without an explicit registry and adapting successfully through the rebuilt registry.
