# Review Findings for ids_ml_new-f4w rerun #2

## code-quality
code-quality: 3 findings (P1: 0, P2: 2, P3: 1)

### Finding 1
Severity: P2
Title: `stdin` mode skips the sink-collision guard and can silently corrupt JSONL output
File and line(s): `scripts/ids_record_adapter.py` lines 835, 867, 875
Problem statement: The distinct-path check is only applied in file mode. In `stdin` mode, `--output-path` and `--quarantine-output-path` can point to the same file, which opens that path twice in write mode and lets adapted/quarantine writes clobber each other.
Why it matters: This breaks the D6/D11 expectation that valid output and quarantine output remain separate streams.
Recommended fix: Reuse the same collision validation for `stdin` mode before opening either handle.
Acceptance criteria: Either mode rejects identical output/quarantine paths before writing.

### Finding 2
Severity: P2
Title: Shipped profiles still accept canonical feature payloads as long as profile metadata is present
File and line(s): `scripts/ids_record_adapter.py` lines 314, 542, 904, 912
Problem statement: Shipped profiles still allow canonical feature-name fallback as long as metadata aliases prove profile presence.
Why it matters: This widens the supported surface beyond the explicit profile maps and undermines the locked guardrail that v1 must prove actual CICFlowMeter-like normalization.
Recommended fix: Disable canonical fallback for shipped profiles or require at least one profile-specific feature alias.
Acceptance criteria: Canonical 72-feature payloads with only profile metadata aliases quarantine as unmapped input.

### Finding 3
Severity: P3
Title: Custom profiles can overwrite the adapter-owned `adapter_profile` field
File and line(s): `scripts/ids_record_adapter.py` lines 25, 265, 592, 593
Problem statement: A custom profile can target `adapter_profile` in `metadata_alias_map` and overwrite the selected profile id.
Why it matters: This weakens the D7/D8 invariant that `adapter_profile` is adapter-owned.
Recommended fix: Exclude `adapter_profile` from allowed metadata alias targets or always write the selected profile id last.
Acceptance criteria: Custom profiles cannot remap upstream data onto `adapter_profile`.

## architecture
architecture: 2 findings (P1: 0, P2: 1, P3: 1)

### Finding 4
Severity: P2
Title: Shipped profiles still accept a hybrid canonical input surface instead of owning a complete upstream profile contract
File and line(s): `scripts/ids_record_adapter.py` lines 314-316, 542-557, 898-913
Problem statement: Both shipped profiles define partial alias maps plus fallback to canonical keys instead of two closed upstream schemas.
Why it matters: This weakens separation between upstream normalization and the model-facing contract and conflicts with D2/D10.
Recommended fix: Reject canonical feature names for shipped profiles and encode intentional identical keys as explicit one-to-one mappings.
Acceptance criteria: Each accepted input key for the two shipped profiles is declared explicitly by the selected profile contract.

### Finding 5
Severity: P3
Title: The public API still models a default-profile concept even though D8 forbids one
File and line(s): `scripts/ids_record_adapter.py` lines 423-456, 915-952; `docs/ids_record_adapter_architecture.md` line 114
Problem statement: Public constants/signatures still expose an optional/default-profile concept, even though runtime behavior rejects omitted profiles.
Why it matters: This makes the adapter boundary ambiguous and makes a silent default path easier to reintroduce later.
Recommended fix: Remove the default-profile concept from the public API surface.
Acceptance criteria: Public helper functions require `profile_id` and docs present explicit profile selection as the only supported path.

## security
security: 2 findings (P1: 0, P2: 2, P3: 0)

### Finding 6
Severity: P2
Title: Library quarantine serialization exposes raw rejected records by default
File and line(s): `scripts/ids_record_adapter.py` lines 380, 393, 403
Problem statement: `AdapterQuarantineRecord.to_event()` defaults `include_source_record=True`, so library callers can emit full rejected payloads unintentionally.
Why it matters: Raw quarantine payload capture was meant to be opt-in; this reverses the hardening boundary for downstream integrations.
Recommended fix: Make redaction the default at the serialization boundary.
Acceptance criteria: `to_event()` without arguments does not emit raw `source_record` content.

### Finding 7
Severity: P2
Title: Default-redacted quarantine still leaks attacker-controlled metadata and passthrough fields
File and line(s): `scripts/ids_record_adapter.py` lines 50, 56, 80, 86, 398
Problem statement: Even in redacted mode, `metadata` and `controlled_extras` are emitted verbatim from attacker-controlled input fields.
Why it matters: This leaves a straightforward exfiltration path into quarantine sinks despite redaction-by-default.
Recommended fix: Omit or sanitize metadata and controlled extras in redacted mode, or gate them behind explicit opt-in.
Acceptance criteria: Default-redacted quarantine output does not expose raw attacker-controlled metadata values.

## test-coverage
test-coverage: 3 findings (P1: 1, P2: 2, P3: 0)

### Finding 8
Severity: P1
Title: Profile-mapping tests are self-referential and do not independently verify the shipped alias contracts
File and line(s): `tests/test_ids_record_adapter.py` lines 66, 133, 237, 328; `scripts/ids_record_adapter.py` lines 33, 63
Problem statement: Test fixtures and alias expectations are generated from the adapter module itself, so mapping mistakes can drift together and still pass.
Why it matters: Profile mapping is the highest-risk area, and current coverage does not provide an independent oracle for shipped CICFlowMeter-like field names or metadata keys.
Recommended fix: Add literal, hand-authored source records or assert against checked-in demo fixtures without importing alias maps from the adapter.
Acceptance criteria: Swapped or misspelled alias/metadata targets cause at least one test failure.

### Finding 9
Severity: P2
Title: No test covers mixed canonical/profile-specific payloads, so the “not a pass-through wrapper” guardrail is unverified
File and line(s): `scripts/ids_record_adapter.py` lines 314, 543, 904, 912; `tests/test_ids_record_adapter.py` line 431
Problem statement: The suite rejects only a fully canonical payload and does not test mostly-canonical mixed inputs.
Why it matters: The approach explicitly says the primary profile must not collapse into already-canonical input.
Recommended fix: Add mixed canonical/profile cases for both profiles and assert quarantine.
Acceptance criteria: Mostly canonical shortcut payloads are quarantined.

### Finding 10
Severity: P2
Title: Default quarantine-redaction tests check only the flag, not that raw payload content is actually absent
File and line(s): `scripts/ids_record_adapter.py` lines 380, 697, 804, 822; `tests/test_ids_record_adapter.py` lines 575, 634, 780, 808, 858
Problem statement: Tests assert `source_record_redacted` but do not verify that raw field values or malformed JSON text are absent.
Why it matters: A regression could emit full payloads and still satisfy the current assertions.
Recommended fix: Assert that redacted quarantine output excludes original keys/values and malformed JSON text in default mode.
Acceptance criteria: Default mode never includes raw payload content; the opt-in path does.
