# CICFlowMeter Dependency Map

**Feature:** `ids-flow-extractor-replacement`  
**Bead:** `ids_ml_new-vii9.10`  
**Purpose:** classify the current repo's CICFlowMeter-linked assumptions into `hard dependency`, `configurable dependency`, or `documentation-only`, using code and tests as the source of truth when docs disagree.

## Classification Legend

- `hard dependency`: enforced by current shipped code or required startup validation on a supported runtime path.
- `configurable dependency`: present as a default or current deployment choice, but implemented as an explicit configuration surface that can be changed without redesigning the model-serving contract.
- `documentation-only`: appears in docs or runbooks without a matching hard enforcement in the current code/tests.

## Summary Table

| Assumption | Class | Why |
| --- | --- | --- |
| `Cmd` command prefix / extractor entrypoint name | `configurable dependency` | The bridge defaults to `("Cmd",)` but exposes `extractor_command_prefix` as config, and tests prove a non-single-token prefix is accepted. Live packaging still hardcodes `/opt/cicflowmeter/Cmd`, so the current coupling is mostly default/deploy surface rather than model/runtime law. |
| `_Flow.csv` output naming | `configurable dependency` | The bridge defaults to `_Flow.csv` but exposes `flow_suffix` as config with only a generic `_<name>.csv` shape guard. |
| `cicflowmeter_primary_v1` adapter profile | `configurable dependency` | The bridge and service unit currently default to the primary profile, but the adapter exposes explicit profile selection and tests lock two shipped profiles, not one hardcoded upstream schema forever. |
| CICFlowMeter-style CSV headers | `configurable dependency` | The bridge only requires a CSV header row and then delegates meaning to the selected adapter profile. The adapter/test suite enforces explicit profile-specific accepted keys rather than a universal CICFlowMeter header law. |
| `java` runtime path | `hard dependency` | Live sensor preflight, service-unit wiring, stack CLI defaults, and tests all require an absolute executable Java path on the current live deployment path. |
| `jnetpcap` asset path | `hard dependency` | Live sensor preflight, service-unit wiring, stack CLI defaults, and tests all require a declared `jnetpcap` path on the current live deployment path. |

## Evidence By Assumption

### 1. `Cmd` command prefix / extractor entrypoint name

**Classification:** `configurable dependency`

**Repo evidence**

- `scripts/ids_live_flow_bridge.py:19-40` sets `DEFAULT_EXTRACTOR_COMMAND_PREFIX = ("Cmd",)` but stores it in `LiveFlowBridgeConfig.extractor_command_prefix`.
- `scripts/ids_live_flow_bridge.py:82-93` builds the extractor command from the configured prefix plus `<pcap> <output-dir>`.
- `tests/test_ids_live_flow_bridge.py:58-86` uses `LiveFlowBridgeConfig(extractor_command_prefix=("cfm", "Cmd"))` and asserts the bridge preserves that explicit command prefix.
- `deploy/systemd/ids-live-sensor.service:17-22` hardcodes `/opt/cicflowmeter/Cmd` into the shipped live unit and passes it to `--extractor-command-prefix`.
- `docs/ids_live_sensor_architecture.md:104-116` and `docs/ids_live_sensor_operations.md:10-23` still describe the CICFlowMeter command-mode wrapper as required runtime packaging.

**Interpretation**

The literal `Cmd` token is real in today's defaults and deployment artifacts, but the bridge already treats it as a caller-supplied command prefix rather than a fixed algorithmic invariant. That makes this a `configurable dependency`, not a hard model-serving contract.

### 2. `_Flow.csv` output naming

**Classification:** `configurable dependency`

**Repo evidence**

- `scripts/ids_live_flow_bridge.py:20-40` defines `DEFAULT_FLOW_SUFFIX = "_Flow.csv"` and stores it in `LiveFlowBridgeConfig.flow_suffix`.
- `scripts/ids_live_flow_bridge.py:73-80` computes output discovery from `window.path.stem + flow_suffix`.
- `tests/test_ids_live_flow_bridge.py:74-86` asserts the default output path is `capture-00001_Flow.csv`.
- `tests/test_ids_live_flow_bridge.py:105-192` repeatedly checks error payloads against the default `_Flow.csv` naming.
- `history/ids-flow-extractor-replacement/discovery.md` already summarized this as part of the current shell contract.

**Interpretation**

The bridge clearly ships with `_Flow.csv` as the current convention, but the code allows other suffixes as long as they remain underscored CSV filenames. This is therefore a `configurable dependency`.

### 3. `cicflowmeter_primary_v1` adapter profile

**Classification:** `configurable dependency`

**Repo evidence**

- `scripts/ids_live_flow_bridge.py:19-40` defines `DEFAULT_ADAPTER_PROFILE_ID = "cicflowmeter_primary_v1"` and stores it in `LiveFlowBridgeConfig.adapter_profile_id`.
- `scripts/ids_live_flow_bridge.py:192-209` delegates adaptation through `adapt_record(..., profile_id=self.config.adapter_profile_id, ...)`.
- `deploy/systemd/ids-live-sensor.service:22` launches the live sensor with `--adapter-profile-id cicflowmeter_primary_v1`.
- `tests/test_ids_record_adapter.py:161-180` locks two explicit shipped profiles, primary and secondary.
- `tests/test_ids_record_adapter.py:967-987` proves shipped profiles reject mixed canonical/profile payloads instead of silently accepting arbitrary canonical input.
- `docs/ids_record_adapter_architecture.md:15-40` describes the adapter as explicit-profile-only and closed-surface.

**Interpretation**

The primary profile is the current default for the live bridge, but the adapter boundary is explicitly profile-driven and already supports more than one shipped profile. That makes the assumption a `configurable dependency`.

### 4. CICFlowMeter-style CSV headers

**Classification:** `configurable dependency`

**Repo evidence**

- `scripts/ids_live_flow_bridge.py:167-198` only requires readable CSV rows, then passes header/value dictionaries to the adapter selected by profile ID.
- `scripts/ids_live_flow_bridge.py:247-252` only hard-fails when the CSV has no header row at all.
- `tests/test_ids_live_flow_bridge.py:195-222` mutates `FlowDuration` in a bridge row and shows the bridge+adapter contract is expressed through the profile mapping surface.
- `tests/test_ids_record_adapter.py:161-180` proves the registry exposes two explicit accepted-source-key surfaces.
- `tests/test_ids_record_adapter.py:967-987` proves the shipped profiles reject hybrid canonical/profile payloads, so the accepted header set is explicit and bounded rather than generic.
- `docs/ids_record_adapter_architecture.md:1-40` frames the adapter as CICFlowMeter-like input normalization rather than a generic schema translator.

**Interpretation**

Header semantics matter today, but they matter because the chosen adapter profile defines an accepted upstream key surface. The runtime and bridge do not require one immortal CICFlowMeter header contract beyond that explicit profile mapping, so this is a `configurable dependency`.

### 5. `java` runtime path

**Classification:** `hard dependency`

**Repo evidence**

- `scripts/ids_live_sensor_preflight.py:12-23` includes `java_binary` in the live preflight config.
- `scripts/ids_live_sensor_preflight.py:90-101` rejects startup unless `java_binary` is an absolute executable path.
- `scripts/ids_live_sensor_preflight.py:104-133` requires `--java-binary` on the CLI.
- `deploy/systemd/ids-live-sensor.service:17-21` wires `/usr/bin/java` into the shipped service unit and preflight call.
- `docs/ids_live_sensor_architecture.md:104-116` and `docs/ids_live_sensor_operations.md:10-23` list Java as required runtime packaging.
- `tests/test_ids_live_sensor_preflight.py:91-124` constructs the passing preflight fixture with an executable Java binary.
- `scripts/ids_same_host_stack_manage.py:29-47` and `docs/ids_same_host_stack_operations.md:68-86` propagate `--java-binary` through the same-host stack surface.

**Interpretation**

On the current live deployment path, Java is enforced before startup and carried through service, preflight, stack CLI, tests, and docs. That makes it a current `hard dependency` even though later beads may parameterize it away.

### 6. `jnetpcap` asset path

**Classification:** `hard dependency`

**Repo evidence**

- `scripts/ids_live_sensor_preflight.py:12-23` includes `jnetpcap_path` in the live preflight config.
- `scripts/ids_live_sensor_preflight.py:90-101` rejects startup unless `jnetpcap_path` exists at an absolute path.
- `scripts/ids_live_sensor_preflight.py:104-133` requires `--jnetpcap-path` on the CLI.
- `deploy/systemd/ids-live-sensor.service:19-21` wires `/opt/cicflowmeter/lib/jnetpcap.jar` into the shipped service unit and preflight call.
- `docs/ids_live_sensor_architecture.md:104-116` and `docs/ids_live_sensor_operations.md:10-23` list `jnetpcap` as required runtime packaging.
- `tests/test_ids_live_sensor_preflight.py:91-124` creates a concrete `jnetpcap.jar` fixture for the passing preflight path.
- `scripts/ids_same_host_stack_manage.py:34-47` and `docs/ids_same_host_stack_operations.md:68-86` propagate `--jnetpcap-path` through same-host orchestration.

**Interpretation**

Like Java, `jnetpcap` is part of the currently enforced live startup contract. It is a `hard dependency` on today's live path, even if later migration work replaces it with a different extractor dependency declaration.

## Documentation-Only Notes

None of the six acceptance-scope assumptions is purely `documentation-only` once code and tests are considered together. The main doc drift is broader wording that treats CICFlowMeter branding as if it were the same thing as the true model-serving contract. In code, the hard boundary is the 72-feature model bundle plus exact-path live startup checks; the CICFlowMeter-specific pieces mostly sit above that boundary as current deployment defaults or explicit adapter/profile surfaces.

## Takeaways For Downstream Beads

- `ids_ml_new-vii9.4` should treat Java and `jnetpcap` as current live-path hard requirements, but it should not mistake `Cmd`, `_Flow.csv`, or `cicflowmeter_primary_v1` for model-facing invariants.
- `ids_ml_new-vii9.9` was right to focus on parameterizing the live extractor dependency surface rather than redesigning the 72-feature runtime contract.
- `ids_ml_new-vii9.1`, `ids_ml_new-vii9.3`, and `ids_ml_new-vii9.6` should preserve D2 and D4 by keeping the source of truth in code/tests: model-serving correctness stays hard, while extractor shell details can move behind explicit bridge/preflight configuration.
