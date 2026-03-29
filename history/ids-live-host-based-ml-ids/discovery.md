# Discovery Report: IDS Live Host-Based ML Sensor

**Date**: 2026-03-28
**Feature**: ids-live-host-based-ml-ids
**CONTEXT.md reference**: `history/ids-live-host-based-ml-ids/CONTEXT.md`

---

## Institutional Learnings

> Read during Phase 0 from `history/learnings/`

### Critical Patterns (Always Applied)

- `history/learnings/critical-patterns.md`: avoid rollback-by-copy behavior on any file promotion path for local alert/quarantine outputs; use atomic rename/replace or fail closed.
- `history/learnings/critical-patterns.md`: decompose beads with clean write scopes and explicitly flag HIGH-risk components for validating spikes before execution.

### Domain-Specific Learnings

No prior learnings for this exact live-capture domain. The only strong institutional guidance comes from the recent adapter/runtime work: quarantine malformed data, keep file mutations transactional, and keep concurrent write scopes narrow.

---

## Agent A: Architecture Snapshot

> Source: gkg fallback plus direct file tree analysis
> Note: `gkg` is installed, but this build exposes indexing/server commands only, so the skill-level `repo_map/search/deps` commands were not available. Discovery used direct file reading and `rg` fallback.

### Relevant Packages / Modules

| Package/Module | Purpose | Key Files |
|----------------|---------|-----------|
| `scripts/ids_feature_contract.py` | Frozen 72-feature validation, alias handling, runtime quarantine model | `scripts/ids_feature_contract.py` |
| `scripts/ids_record_adapter.py` | Upstream structured-record normalization into runtime-ready canonical records | `scripts/ids_record_adapter.py` |
| `scripts/ids_realtime_pipeline.py` | Near-realtime buffering, inference orchestration, alert/quarantine writing | `scripts/ids_realtime_pipeline.py` |
| `scripts/ids_inference.py` | Bundle loading and CatBoost scoring on aligned DataFrames | `scripts/ids_inference.py` |
| `tests/test_ids_record_adapter.py` | Regression coverage for adapter profile mapping and runtime handoff | `tests/test_ids_record_adapter.py` |
| `tests/test_ids_realtime_pipeline.py` | Regression coverage for micro-batch runtime behavior and CLI modes | `tests/test_ids_realtime_pipeline.py` |
| `docs/*architecture.md` | Architecture baselines for inference, runtime, and adapter boundaries | `docs/ids_inference_architecture.md`, `docs/ids_realtime_pipeline_architecture.md`, `docs/ids_record_adapter_architecture.md` |

### Entry Points

- **Runtime CLI**: `scripts/ids_realtime_pipeline.py`
- **Adapter CLI**: `scripts/ids_record_adapter.py`
- **Inference CLI**: `scripts/ids_inference.py`
- **Tests**: `tests/test_ids_feature_contract.py`, `tests/test_ids_record_adapter.py`, `tests/test_ids_realtime_pipeline.py`, `tests/test_ids_inference.py`
- **Artifacts/fixtures**: `artifacts/demo/*.jsonl`

### Key Files to Model After

- `F:/Work/IDS_ML_New/scripts/ids_realtime_pipeline.py` - demonstrates the repo's current runtime orchestration style: one script, explicit CLI, reusable classes, JSONL outputs, and simple summary emission.
- `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py` - demonstrates how high-risk data-boundary logic is kept testable through dataclasses, reusable components, and strict quarantine behavior.
- `F:/Work/IDS_ML_New/tests/test_ids_realtime_pipeline.py` - demonstrates the current test pattern for streaming behavior, stdin/file modes, and threaded timing-sensitive assertions.

---

## Agent B: Pattern Search

> Source: `rg`, direct code reading

### Similar Existing Implementations

| Feature/Component | Location | Pattern Used | Reusable? |
|-------------------|----------|--------------|-----------|
| Runtime buffering and flush triggers | `scripts/ids_realtime_pipeline.py` | reusable class (`RealtimePipelineRunner`) plus CLI wrapper | Yes |
| Canonical schema validation | `scripts/ids_feature_contract.py` | strict validation object returning typed valid/quarantine results | Yes |
| Upstream shape normalization | `scripts/ids_record_adapter.py` | explicit profile registry, quarantine-first adaptation | Yes |
| CLI and transactional file output | `scripts/ids_record_adapter.py` | explicit path validation and temp-file promotion | Yes |
| Streaming/timing tests | `tests/test_ids_realtime_pipeline.py` | blocking stream double, threaded assertions, focused unit tests | Yes |

### Reusable Utilities

- **Validation**: `F:/Work/IDS_ML_New/scripts/ids_feature_contract.py` - frozen-schema validation with quarantine result types.
- **Adapter boundary**: `F:/Work/IDS_ML_New/scripts/ids_record_adapter.py` - explicit profile normalization into runtime-ready canonical records.
- **Inference construction**: `F:/Work/IDS_ML_New/scripts/ids_inference.py` - reusable `build_inferencer()` and model bundle config loading.
- **Micro-batch runtime**: `F:/Work/IDS_ML_New/scripts/ids_realtime_pipeline.py` - `RealtimePipelineRunner`, `run_pipeline_stream()`, summary dataclass.

### Naming Conventions

- Runtime scripts use `ids_<capability>.py` under `scripts/`.
- Test files use `tests/test_ids_<capability>.py`.
- Architecture/docs files use `docs/ids_<capability>_architecture.md`.
- Public data-boundary classes favor typed `@dataclass` models with explicit `to_*()` serializers instead of loose dictionaries everywhere.

---

## Agent C: Constraints Analysis

> Source: imports scan, file tree, existing tests/docs

### Runtime & Framework

- **Language/runtime**: Python script-first repository
- **Repo shape**: no `pyproject.toml`, `requirements*.txt`, `Pipfile`, or Conda environment file found at repo root
- **Current style**: direct script entrypoints plus pytest-based regression tests

### Existing Dependencies (Relevant to This Feature)

| Package | Evidence | Purpose |
|---------|----------|---------|
| `pandas` | `scripts/ids_inference.py`, `scripts/ids_realtime_pipeline.py` | DataFrame alignment and inference batching |
| `catboost` | `scripts/ids_inference.py` | Final model runtime |
| `pytest` | `tests/*` | Test execution |
| `pyarrow` | training/post-train scripts | Data artifacts, not current runtime critical path |

### New Dependencies / Runtime Requirements Likely Needed

| Package/Tool | Reason | Risk Level |
|--------------|--------|------------|
| `CICFlowMeter`-compatible extractor runtime | Best semantic match to the training-time feature family and timeout behavior | HIGH - external runtime/tooling, novel to this repo |
| Linux live capture utility or packet-capture library | Continuous host-based packet acquisition from one NIC | HIGH - privileged runtime behavior and no current precedent |
| `systemd` service packaging | Required for the locked fail-fast + supervised-restart deployment shape | MEDIUM - operational dependency, not a Python library |

### Build / Quality Requirements

```bash
# Existing regression anchors
python -m pytest -q tests/test_ids_feature_contract.py
python -m pytest -q tests/test_ids_record_adapter.py
python -m pytest -q tests/test_ids_realtime_pipeline.py
python -m pytest -q tests/test_ids_inference.py
python -m pytest -q
```

### Operational Constraints

- The current runtime only accepts already-structured records, so live capture must either feed the adapter's primary profile or produce an equivalent upstream shape.
- The model contract is frozen at 72 features from `artifacts/final_model/catboost_full_data_v1/feature_columns.json`; capture/extraction cannot improvise missing values.
- The feature is locked to one Linux host and one configured NIC, so planning should avoid abstractions for multi-host orchestration.

---

## Agent D: External Research

> Source: official docs and upstream project sources
> Guided by locked decisions in CONTEXT.md

### Library / Platform Documentation

| Library / Platform | Key Docs | Relevant Point |
|--------------------|----------|----------------|
| Python `socket` | [docs.python.org socket](https://docs.python.org/3/library/socket.html) | Python exposes Linux `AF_PACKET`, so direct packet capture is possible from stdlib on Linux. |
| Linux packet sockets | [man7 packet(7)](https://man7.org/linux/man-pages/man7/packet.7.html) | `AF_PACKET` is a low-level interface to network devices and is Linux-specific, confirming the portability/privilege boundary. |
| Scapy | [Scapy AsyncSniffer](https://scapy.readthedocs.io/en/latest/api/scapy.sendrecv.html) | Scapy offers `AsyncSniffer`, which makes live capture feasible in Python but does not solve CICFlowMeter-semantic feature extraction by itself. |
| Wireshark `dumpcap` | [dumpcap(1)](https://www.wireshark.org/docs/man-pages/dumpcap.html) | Official docs support live capture to files, per-interface capture filters, duration/file-size ring buffers, and `printname` notifications when a file closes. |
| systemd | [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html) | `Type=simple`/`notify` plus `Restart=` policies are the right fit for the locked fail-fast supervised process model. |
| CICFlowMeter | [CICFlowMeter ReadMe](https://github.com/ahlashkari/CICFlowMeter/blob/master/ReadMe.txt) | The upstream tool explicitly defines biflow generation, TCP teardown vs UDP timeout behavior, and the feature family used in IDS datasets. |

### Community / Upstream Patterns

- **Pattern**: keep flow semantics close to CICFlowMeter rather than re-inventing 72 feature calculations from scratch.
  - Why it applies: the current model is explicitly anchored to CICFlowMeter-like flow statistics and timeout behavior.
  - Reference: [CICFlowMeter ReadMe](https://github.com/ahlashkari/CICFlowMeter/blob/master/ReadMe.txt)

- **Pattern**: separate live capture from extraction by writing bounded rolling capture windows that downstream workers consume only after the file is closed.
  - Why it applies: `dumpcap` natively supports duration-based multi-file capture plus file-close notifications, which gives the plan a source-backed `live-first` path without requiring a direct live extractor mode.
  - Reference: [dumpcap(1)](https://www.wireshark.org/docs/man-pages/dumpcap.html)

- **Pattern**: use supervisor-managed long-running services with local durable logs before adding outbound notification sinks.
  - Why it applies: the feature is locked to fail-fast restart behavior and local-first outputs (`JSONL` + `journald`).
  - Reference: [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)

### Known Gotchas / Anti-Patterns

- **Gotcha**: `AF_PACKET`/live packet capture is Linux-specific and privilege-sensitive.
  - Why it matters: it reinforces the locked single-Linux-host boundary and means validating must prove the service startup/permission model.
  - How to avoid: keep Linux-specific capture isolated to one module and package it explicitly for `systemd`.

- **Gotcha**: Scapy or raw sockets only solve capture, not exact CICFlowMeter-compatible feature semantics.
  - Why it matters: a pure-Python sniffer can still leave the team re-implementing 72 nuanced flow features and timeout semantics by hand.
  - How to avoid: treat feature-extraction fidelity as a HIGH-risk architectural question and bias toward extractor compatibility instead of greenfield semantics.

- **Gotcha**: a direct live-compatible extractor path is not documented by the current CICFlowMeter planning evidence.
  - Why it matters: the first validating pass blocked on exactly this assumption.
  - How to avoid: plan around closed `pcap` windows as the extractor contract rather than pretending the extractor consumes the interface directly.

- **Anti-pattern**: reimplementing the whole feature family directly inside the daemon without first proving semantic parity.
  - Common mistake: merging packet capture, flow state math, feature semantics, adapter logic, and inference into one large new script.
  - Correct approach: isolate live capture/extraction as an upstream stage and reuse the already-tested adapter/runtime/inference path.

### Validation-Driven Replanning Addendum

The first validating pass produced a `NO` spike for the assumed direct live-compatible extractor seam. That changes the planning surface:

- `live-first` is still locked, but it does **not** require the extractor itself to read packets from the NIC directly.
- The revised architecture can remain faithful to `D1-D4` by treating live capture and extraction as two bounded stages:
  1. capture real traffic continuously from the configured interface into short rolling `pcap` windows
  2. extract flow records only from closed windows, then feed the existing adapter/runtime path

This addendum is also supported by repo-local evidence: dataset and manifest artifacts already use `*.pcap_Flow.csv` naming, which matches a `pcap -> flow export` operating model more naturally than an invented in-memory live extractor.

---

## Open Questions

> Items not fully resolvable through research alone.

- [ ] Which exact extractor package/binary should process each closed `pcap` window in v1, and what headless invocation contract does it guarantee? - this remains the main validation spike for the revised plan.
- [ ] What window duration/backlog threshold keeps end-to-end latency bounded while avoiding extractor starvation on the target host? - this affects daemon sizing and fatal-vs-recoverable backlog policy.
- [ ] Should closed `pcap` windows and extractor CSV/JSONL outputs be deleted immediately after successful downstream handoff, or retained briefly as bounded debug artifacts under a capped spool policy? - this affects disk pressure and local forensics.

---

## Summary for Synthesis (Phase 2 Input)

**What we have**: a tested downstream path for `structured record -> adapter -> canonical validation -> micro-batch inference -> alert/quarantine`, all implemented in script-first Python and documented clearly.

**What we need**: an upstream live Linux host sensor that continuously acquires TCP/UDP traffic from one NIC, turns it into CICFlowMeter-like flow records with acceptable semantic fidelity, and composes that into the existing downstream ML runtime.

**Key constraints from research**:
- The 72-feature contract is frozen and should not be re-invented casually.
- Linux-specific capture and supervised restart behavior are part of the product boundary, not optional deployment details.
- This repo has no existing dependency manifest or live-capture precedent, so new runtime/tooling dependencies are intrinsically HIGH-risk.
- The cleanest source-backed capture mechanism discovered so far is `dumpcap` in rolling multi-file mode, with downstream consumers triggered only after a window file closes.
- The planning blocker was not "live capture is impossible"; it was "direct live extraction is unproven." A staged-live `closed pcap window -> extractor` boundary directly addresses that gap.

**Institutional warnings to honor**:
- Keep output file mutation transactional and fail closed on unsafe restore paths.
- Decompose work into clean write scopes and flag extractor/service decisions for validating spikes before execution.
