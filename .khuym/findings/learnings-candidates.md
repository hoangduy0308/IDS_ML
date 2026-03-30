## Candidate: collapse-live-extractor-dependency-configuration-into-one-canonical-contract
Category: pattern
Tags: systemd, preflight, deployment, configuration, legacy-contract
Summary: Live extractor wiring should expose one canonical dependency/configuration contract rather than a split surface with both new multi-argv prefix handling and deprecated runtime knobs. The service unit, preflight, and stack entrypoints should agree on one representation so deployment behavior stays reasoned and testable.
Evidence: review findings about multi-token extractor prefixes in `deploy/systemd/ids-live-sensor.service` and split-source runtime knobs in `scripts/ids_live_sensor_preflight.py`, `scripts/ids_same_host_stack.py`, and `scripts/ids_same_host_stack_manage.py`.
Related patterns: `history/learnings/20260328-live-sensor-runtime-contracts.md`, `history/learnings/20260329-same-host-stack-runtime-hardening.md`
Recommended title: YYYYMMDD-collapse-live-extractor-dependency-configuration-into-one-canonical-contract.md

## Candidate: separate-canonical-extractor-semantics-from-adapter-serialization
Category: pattern
Tags: extractor, adapter, serializer, contract-boundary, maintainability
Summary: The replacement extractor should own canonical flow semantics only, while profile mapping and CSV serialization stay in a separate adapter/serializer layer. Keeping semantic extraction, compatibility mapping, and row emission in one module makes the boundary brittle and forces adapter/profile churn to change extractor internals.
Evidence: review finding about the replacement extractor being coupled to adapter serialization in `scripts/ids_offline_window_extractor.py`, plus the bridge-side single-row/quarantine coverage gap in `scripts/ids_live_flow_bridge.py`.
Related patterns: `history/learnings/20260328-adapter-rollback-contract.md`, `history/learnings/20260329-model-bundle-promotion-hardening.md`
Recommended title: YYYYMMDD-separate-canonical-extractor-semantics-from-adapter-serialization.md

## Candidate: pin-extractor-semantic-and-parser-edge-cases-with-negative-fixtures
Category: failure
Tags: test-coverage, pcap, parser, flow-classification, regression
Summary: The new extractor and bridge need negative-path coverage for malformed pcaps, unsupported link types, non-IP filtering, VLAN/UDP branches, reverse-first aggregation, sub-second duration math, and multi-row bridge handling. Happy-path golden output is not enough to protect the contract surface from silent regressions.
Evidence: review findings about missing parser/flow-classification coverage in `scripts/ids_offline_window_extractor.py` / `tests/test_ids_offline_window_extractor.py`, bridge multi-row coverage gaps in `scripts/ids_live_flow_bridge.py` / `tests/test_ids_live_flow_bridge.py`, and sub-second rate undercounting in `scripts/ids_offline_window_extractor.py`.
Related patterns: `history/learnings/20260328-live-sensor-runtime-contracts.md`, `history/learnings/20260328-adapter-rollback-contract.md`
Recommended title: YYYYMMDD-pin-extractor-semantic-and-parser-edge-cases-with-negative-fixtures.md

## Candidate: typed-serializer-seam
Category: pattern
Tags: serializer, typing, seam, extractor, contract
Summary: When splitting extractor and serializer responsibilities, keep the seam strongly typed so the contract does not drift into `Any`-based plumbing.
Evidence: serializer seam follow-up review on `scripts/ids_offline_window_serializer.py` and `scripts/ids_offline_window_extractor.py`.
Recommended title: YYYYMMDD-typed-serializer-seam.md

## Candidate: tokenization-roundtrip-coverage
Category: failure
Tags: cli, systemd, shell, tokenization, roundtrip, tests
Summary: Multi-token command-prefix handling needs explicit round-trip coverage across argparse, systemd, and shell tokenization to prevent compatibility regressions.
Evidence: review follow-up on `scripts/ids_live_sensor_preflight.py`, `deploy/systemd/ids-live-sensor.service`, and `tests/test_ids_live_sensor.py`.
Recommended title: YYYYMMDD-tokenization-roundtrip-coverage.md
