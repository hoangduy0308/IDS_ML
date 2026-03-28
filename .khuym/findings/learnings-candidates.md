## Candidate: rollback-fallback-safety
Category: failure
Tags: rollback, symlink, junction, atomic-write, security
Summary: Rollback code should refuse unsafe restore targets instead of falling back to a path-based copy, because a symlink or junction can turn a recovery path into an arbitrary-file overwrite.
Evidence: `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py`
Recommended title: 20260328-rollback-fallback-safety.md

## Candidate: asymmetric-rollback-coverage
Category: failure
Tags: rollback, rerun, partial-state, tmp-artifacts, test-coverage
Summary: Partial rerun states need explicit rollback tests, not just clean-state and all-existing coverage, so future recovery logic is verified against mixed output presence and leftover artifact cleanup.
Evidence: `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py`, `F:/Work/IDS_ML_New/tests/test_ids_record_adapter.py`
Recommended title: 20260328-asymmetric-rollback-coverage.md

## Candidate: rollback-byte-fidelity
Category: pattern
Tags: rollback, byte-fidelity, file-mode, recovery, tests
Summary: When validating restoration of preexisting outputs, assert byte-for-byte preservation instead of only semantic JSON equality so newline or encoding drift cannot hide a recovery regression.
Evidence: `F:/Work/IDS_ML_New/tests/test_ids_record_adapter.py`
Recommended title: 20260328-rollback-byte-fidelity.md

## Candidate: adapter-expected-record-builder
Category: decision
Tags: adapter, tests, contract, d7, expected-values
Summary: Build expected adapted records from the intended output contract only, with explicit handling for same-name features, alias maps, metadata aliases, and controlled extras rather than copying the whole source payload.
Evidence: `F:/Work/IDS_ML_New/tests/test_ids_record_adapter.py`
Recommended title: 20260328-adapter-expected-record-builder.md

## Candidate: rollback-contract-matrix
Category: pattern
Tags: rollback, multi-output, tests, quarantine, cleanup
Summary: Treat multi-output rollback as one contract and verify adapted output, quarantine output, temp cleanup, and backup preservation together to catch partial-recovery regressions.
Evidence: `F:/Work/IDS_ML_New/tests/test_ids_record_adapter.py`
Recommended title: 20260328-rollback-contract-matrix.md
