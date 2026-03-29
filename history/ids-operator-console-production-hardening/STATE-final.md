STATUS: swarming-in-progress
FEATURE: ids-operator-console-production-hardening
EPIC: ids_ml_new-z2i
ACTIVE_SKILL: khuym:swarming
DATE: 2026-03-29

Current Session:
- Goal: harden the existing same-host IDS operator console so it is materially closer to true production readiness for operators after `ids-operator-console-v1`.
- Scope classification: Deep
- Prior feature baseline: `ids-operator-console-v1` completed through compounding on 2026-03-28 and remains the functional baseline to harden rather than re-discover.
- Hard constraints from kickoff:
  - Stay focused on the operator console layer.
  - Do not expand into IPS/control-plane or multi-host fleet work unless exploring proves it is required.
  - Prioritize production gaps: safe deploy, secret/config management, reverse proxy/TLS readiness, retention/backup/restore, migration/bootstrap safety, smoke/UAT-ready operations.
- Mandatory learnings in force:
  - Service entrypoints must run the canonical app factory.
  - Review must verify `EXISTS / SUBSTANTIVE / WIRED`, not module presence alone.

Planning Bootstrap:
- Bootstrap/resume complete; previous feature state was `ids-operator-console-v1` at `compounding-complete`.
- Required context and baseline artifacts loaded:
  - `AGENTS.md`
  - `khuym:using-khuym`
  - prior operator-console v1 `CONTEXT.md`, `approach.md`, `STATE-final.md`
  - `history/learnings/critical-patterns.md`
  - `history/learnings/20260328-operator-console-runtime-wiring.md`
- Quick scout loaded:
  - `docs/ids_operator_console_architecture.md`
  - `scripts/ids_operator_console/config.py`
  - `scripts/ids_operator_console/db.py`
  - `scripts/ids_operator_console/web.py`
  - `scripts/ids_operator_console_server.py`
  - `scripts/ids_operator_console_preflight.py`
  - `deploy/systemd/ids-operator-console.service`
  - `tests/test_ids_operator_console_config.py`
  - `tests/test_ids_operator_console_web.py`
- Agent Mail bootstrap:
  - Registered as `RainyGrove`
  - Reserved `.khuym/STATE.md`
  - Reserved `history/ids-operator-console-production-hardening/CONTEXT.md`
  - Reserved `history/ids-operator-console-production-hardening/discovery.md`
  - Reserved `history/ids-operator-console-production-hardening/approach.md`

Locked Decisions:
- D1 same-host behind reverse proxy with TLS terminated at proxy
- D2 feature remains operator-console hardening only; no IPS/control-plane/fleet expansion
- D3 backup/restore covers operator DB + production config + secret references, not upstream raw feed
- D4 retention must be configurable and tied to safe cleanup + backup/restore contract
- D5 non-secret config via env/config file; sensitive secrets via secret file paths / credential-style paths
- D6 session/auth production hardening is in scope and must fail closed on secret/config misuse
- D7 startup verifies schema/bootstrap and fails closed; migrations are explicit operator actions
- D8 safe same-host upgrade from v1 is first-class
- D9 fresh bootstrap and upgrade paths are both first-class
- D10 done criteria require smoke deploy checks + runbook + restore drill verification
- D11 reverse proxy/TLS readiness must be real runtime contract, not documentation-only
- D12 observability must distinguish alive/ready/config-schema-valid/data-path-health
- D13 review must verify EXISTS / SUBSTANTIVE / WIRED for runtime and operations artifacts
- D14 restore keeps secret references in backup scope while secret material remains externally re-provisioned and fail-closed if missing
- D15 done means fresh bootstrap or v1 upgrade can pass proxy-aware smoke flow with explicit migration and restore drill

Planning Outputs:
- CONTEXT.md:
  - `F:/Work/IDS_ML_New/history/ids-operator-console-production-hardening/CONTEXT.md`
- Discovery:
  - `F:/Work/IDS_ML_New/history/ids-operator-console-production-hardening/discovery.md`
- Approach:
  - `F:/Work/IDS_ML_New/history/ids-operator-console-production-hardening/approach.md`
- Bead graph:
  - Epic `ids_ml_new-z2i`
  - `ids_ml_new-z2i.1` Harden runtime config for proxy-aware deployment and session security
  - `ids_ml_new-z2i.2` Implement explicit schema versioning, admin bootstrap, and migration CLI
  - `ids_ml_new-z2i.3` Add transactional backup, restore, and retention operations
  - `ids_ml_new-z2i.4` Wire preflight, systemd packaging, and reverse-proxy artifacts
  - `ids_ml_new-z2i.5` Add smoke workflow, restore drill, and production runbook

Bead Graph Status:
- `br` local DB corruption detected during planning and repaired by rebuilding from `.beads/issues.jsonl`; recovery artifact preserved under `.beads/.br_recovery/`.
- Execution order locked:
  - Actionable first layer: `ids_ml_new-z2i.1`, `ids_ml_new-z2i.2`
  - Then `ids_ml_new-z2i.3` depends on `.2`
  - Then `ids_ml_new-z2i.4` depends on `.1` and `.2`
  - Then `ids_ml_new-z2i.5` depends on `.1`, `.3`, and `.4`
- `bv --robot-plan` now reports `total_actionable=2`, `total_blocked=4`.

High-Risk Seams For Validating:
- Proxy-aware config + session hardening, including `public_base_url` correctness behind reverse proxy
- Schema versioning + explicit migration/upgrade path from v1
- Backup/restore + secret-reference validation, including offline restore discipline

Validating Focus:
- Run 8-dimension plan verification against the current bead set
- Execute three HIGH-risk spikes:
  - proxy-aware config + session hardening
  - schema versioning + explicit migration / fail-closed startup
  - backup/restore + secret-reference validation under offline restore discipline
- Polish bead graph and prepare Gate 2 approval packet

Validating Outputs:
- `F:/Work/IDS_ML_New/history/ids-operator-console-production-hardening/validation.md`
- Spike findings:
  - `F:/Work/IDS_ML_New/.spikes/ids-operator-console-production-hardening/ids_ml_new-gen/FINDINGS.md`
  - `F:/Work/IDS_ML_New/.spikes/ids-operator-console-production-hardening/ids_ml_new-n1m/FINDINGS.md`
  - `F:/Work/IDS_ML_New/.spikes/ids-operator-console-production-hardening/ids_ml_new-1hs/FINDINGS.md`
- Spike beads closed:
  - `ids_ml_new-gen`
  - `ids_ml_new-n1m`
  - `ids_ml_new-1hs`

Gate Status:
- Gate 2 approved for execution on 2026-03-29

Swarm Status:
- Execution started against epic `ids_ml_new-z2i`
- Current wave:
  - `ids_ml_new-z2i.1`
  - `ids_ml_new-z2i.2`
- Orchestration note:
  - executing in validated bead order while preserving the same artifact and verification contracts captured during planning/validating

Next:
- Complete `ids_ml_new-z2i.1` runtime hardening
- Complete `ids_ml_new-z2i.2` migration/bootstrap foundation
- Re-open graph after first wave to unlock `.3`, `.4`, and `.5`
