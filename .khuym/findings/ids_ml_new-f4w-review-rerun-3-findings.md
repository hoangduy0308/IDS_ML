# Review Findings for ids_ml_new-f4w rerun #3

## code-quality
code-quality: 3 findings (P1: 0, P2: 2, P3: 1)

### Finding 1
Severity: P2
Title: Shipped profiles are partly generated instead of being fully explicit contracts
File and line(s): `scripts/ids_record_adapter.py` lines 98-114, 955-976
Problem statement: `_build_closed_feature_alias_map()` auto-expands canonical feature columns into identity mappings, so shipped profile acceptance is partly derived from `feature_columns.json` at runtime.
Why it matters: A feature-columns artifact change can silently change accepted upstream keys without a profile-definition code change.
Recommended fix: Freeze the shipped profile source-key maps explicitly in code or in a checked-in generated artifact.
Acceptance criteria: Changing `feature_columns.json` alone does not change profile input acceptance.

### Finding 2
Severity: P2
Title: Canonical-only quarantine path drops mapped metadata and controlled extras
File and line(s): `scripts/ids_record_adapter.py` lines 570-586, 593-596
Problem statement: The early return on `canonical_override_breaches` happens before source partitioning, so valid metadata/extras from the same record are lost in quarantine output.
Why it matters: This makes the same quarantine class less traceable on one branch than on the normal unmapped-field path.
Recommended fix: Partition source fields before the early return or pre-extract metadata/extras.
Acceptance criteria: Canonical-only invalid records still preserve mapped metadata and controlled extras in quarantine.

### Finding 3
Severity: P3
Title: Redaction flags can contradict the serialized quarantine payload
File and line(s): `scripts/ids_record_adapter.py` lines 405-439
Problem statement: Empty metadata/extras emit redacted placeholder objects while the companion `*_redacted` flags remain false.
Why it matters: Consumers cannot rely on the redaction flags as a stable schema signal.
Recommended fix: Either emit `{}` when nothing is redacted or set flags consistently when placeholder objects are emitted.
Acceptance criteria: Empty metadata/extras no longer produce contradictory redaction state.

## architecture
architecture: 3 findings (P1: 0, P2: 2, P3: 1)

### Finding 4
Severity: P2
Title: Core adapter is hard-wired to the repo layout instead of being a clean reusable boundary
File and line(s): `scripts/ids_record_adapter.py` lines 14-26, 117-140, 530-539
Problem statement: The core module mutates/imports based on repo layout and reads repo artifacts at import time.
Why it matters: This weakens the intended reusable-core/thin-CLI split and makes embedding the adapter brittle.
Recommended fix: Move repo-default wiring into CLI/composition code and keep core construction explicit.
Acceptance criteria: Importing the core performs no repo-root path mutation and no artifact file I/O.

### Finding 5
Severity: P2
Title: Contract and profile registry can drift because they are configured from different sources of truth
File and line(s): `scripts/ids_record_adapter.py` lines 98-102, 527-540, 955-980
Problem statement: Profile alias maps are derived from `DEFAULT_ADAPTER_FEATURE_COLUMNS`, while the adapter contract is independently injectable with no compatibility guard.
Why it matters: A custom contract and custom registry can disagree on canonical features, creating split-brain configuration.
Recommended fix: Derive registry targets from the contract or validate registry/contract compatibility eagerly.
Acceptance criteria: Construction fails or binds consistently when registry and contract disagree.

### Finding 6
Severity: P3
Title: Public profile API leaves an escape hatch that weakens the locked v1 profile boundary
File and line(s): `scripts/ids_record_adapter.py` lines 232-237, 268-271, 335-341
Problem statement: Public profile construction still exposes `accept_canonical_feature_names`, enabling canonical/hybrid passthrough profiles by configuration.
Why it matters: The v1 boundary becomes convention rather than enforced API shape.
Recommended fix: Remove this toggle from the public v1 API or make it internal-only.
Acceptance criteria: Public profile construction cannot enable canonical fallback in v1.

## security
security: 0 findings (P1: 0, P2: 0, P3: 0)
No findings in security scope.

## test-coverage
test-coverage: 2 findings (P1: 0, P2: 1, P3: 1)

### Finding 7
Severity: P2
Title: Secondary profile lacks end-to-end runtime compatibility coverage
File and line(s): `history/ids-structured-record-adapter/approach.md` line 68; `tests/test_ids_record_adapter.py` lines 324, 415, 679, 971
Problem statement: End-to-end adapter-to-runtime coverage exists only for the primary profile.
Why it matters: The extensibility proof requires both shipped profiles to be proven runtime-compatible.
Recommended fix: Add a secondary-profile handoff test into `ids_realtime_pipeline.py` runtime acceptance.
Acceptance criteria: Both shipped profiles are proven to feed the realtime pipeline without extra translation.

### Finding 8
Severity: P3
Title: File-mode `input == quarantine` collision branch is untested
File and line(s): `scripts/ids_record_adapter.py` lines 747, 758; `tests/test_ids_record_adapter.py` lines 831, 859
Problem statement: Tests cover `input == output` and `output == quarantine`, but not `input == quarantine`.
Why it matters: One branch of the file-mode safety logic can regress without coverage.
Recommended fix: Add a subprocess test for `input == quarantine` and verify no file handle opens.
Acceptance criteria: All three collision pairs are covered.
