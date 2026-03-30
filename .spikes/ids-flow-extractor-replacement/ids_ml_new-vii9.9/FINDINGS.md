## Spike: ids_ml_new-vii9.9

### Question
Can Java/jnetpcap/Cmd assumptions be removed or parameterized from live-sensor preflight and same-host stack contracts without weakening exact-path fail-closed startup semantics?

### Determination
YES

### Evidence
- [`scripts/ids_live_sensor_preflight.py`](F:\Work\IDS_ML_New\scripts\ids_live_sensor_preflight.py) does not embed extractor-specific logic beyond absolute-path existence and executability checks for `java_binary`, `extractor_binary`, and `jnetpcap_path`.
- [`scripts/ids_same_host_stack.py`](F:\Work\IDS_ML_New\scripts\ids_same_host_stack.py) simply builds `LiveSensorPreflightConfig` and delegates to `validate_live_sensor_preflight`; the stack layer is propagation glue, not deep extractor logic.
- [`scripts/ids_same_host_stack_manage.py`](F:\Work\IDS_ML_New\scripts\ids_same_host_stack_manage.py) exposes the legacy dependencies as CLI defaults, which means the current coupling is mainly parameter/default surface, not an algorithmic requirement.
- [`deploy/systemd/ids-live-sensor.service`](F:\Work\IDS_ML_New\deploy\systemd\ids-live-sensor.service) hardcodes `/usr/bin/java`, `/opt/cicflowmeter/Cmd`, and `/opt/cicflowmeter/lib/jnetpcap.jar` as environment values, confirming the current lock-in is packaging-level.
- Tests such as [`tests/test_ids_live_sensor_preflight.py`](F:\Work\IDS_ML_New\tests\test_ids_live_sensor_preflight.py) and [`tests/test_ids_same_host_stack_manage.py`](F:\Work\IDS_ML_New\tests\test_ids_same_host_stack_manage.py) assert exact-path verification and CLI wiring, not that Java or jnetpcap are semantically required by the runtime itself.

### Migration Shape
- Replace the legacy trio with an explicit extractor dependency contract in preflight, for example `extractor_entrypoint` plus zero or more extractor-specific auxiliary paths.
- Keep the fail-closed rule unchanged: every declared dependency must still be absolute, present, and executable/readable as appropriate before startup.
- Update the same-host stack and systemd unit to pass the new contract explicitly, rather than hardcoding Java/Cmd/jnetpcap names.
- Preserve error domains so operators still get precise failures for missing extractor runtime prerequisites.

### Constraints
- This YES is for parameterization or replacement of the dependency surface, not for silently deleting startup checks.
- The live sensor service unit, same-host stack CLI defaults, preflight tests, and operator docs all need synchronized updates.
- A generic extractor contract still needs one canonical source of truth so preflight and service runtime cannot drift.

### Conclusion
The repo supports a YES for removing the Java/jnetpcap/Cmd assumptions as named legacy dependencies, provided they are replaced with a declarative extractor dependency surface that keeps the same exact-path fail-closed behavior. The coupling today is mostly in config defaults, service-unit environment variables, and path-validation code, not in irreplaceable runtime semantics. That means the safe migration path is parameterization first, not hardcoded legacy names forever.
