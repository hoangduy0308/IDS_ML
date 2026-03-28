## Review Rerun 5 Findings

### code-quality

- Severity: P2
  Title: File-mode sink setup can leave truncated outputs behind on failure
  File: `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py`
  Problem: file-mode opens final output and quarantine sinks directly in write mode before setup fully succeeds, so a failure can truncate previous artifacts and leave empty partial files behind.
  Recommended fix: stage file-mode writes through temporary files or add equivalent rollback cleanup before any final-path truncation becomes visible.

### architecture

- Severity: P2
  Title: Primary profile is still mostly canonical, so the adapter barely proves upstream normalization
  File: `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py`
  Problem: the primary profile still accepts a largely canonical 72-feature surface through identity mappings, which weakens the claimed CICFlowMeter-like normalization boundary.
  Recommended fix: define the primary profile from an explicit upstream source schema and avoid accepting canonical feature names unless a separate compatibility mode is intentionally documented.

- Severity: P2
  Title: Controlled extras are flattened into the model record instead of staying behind a stable passthrough envelope
  File: `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py`
  Problem: controlled extras are merged into the same top-level record as model features and fixed metadata, increasing coupling at the adapter/runtime seam.
  Recommended fix: keep controlled extras in a dedicated envelope or explicitly document flattening as a locked decision if that coupling is intentional.

### security

- No findings in security scope.

### test-coverage

- Severity: P2
  Title: Stdin-mode file sinks are not tested for truncation
  File: `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py`
  Problem: current stdin sink tests only use fresh files and do not assert that pre-existing sink content is overwritten rather than appended.
  Recommended fix: add a regression test that pre-populates sink files with sentinel content and verifies overwrite behavior across reruns.

- Severity: P2
  Title: Contract-result failure shape is not locked down
  Files: `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py`, `F:/Work/IDS_ML_New/tests/test_ids_record_adapter.py`
  Problem: new duck-typed contract tests do not exercise the malformed result branch where `validate_record()` returns an object with neither `aligned_features` nor `reason`.
  Recommended fix: add a unit test asserting the stable `TypeError` path for malformed delegated contract results.

- Severity: P3
  Title: Empty or whitespace-only JSONL streams are untested
  File: `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py`
  Problem: `_read_jsonl_payloads()` skips blank lines, but there is no regression coverage for empty feeds in file mode or stdin mode.
  Recommended fix: add empty-input tests for both I/O modes and assert zero outputs, zero quarantine, and clean exit.
