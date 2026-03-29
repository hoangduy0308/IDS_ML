# Validation: IDS Operator Console Production Hardening

**Date**: 2026-03-29
**Feature**: `ids-operator-console-production-hardening`
**Epic**: `ids_ml_new-z2i`

---

## 1. Plan Verification

### Iteration 1

Result: **FAIL**

Failed dimensions:
- **File scope isolation**: the original plan made `ids_ml_new-z2i.1` and `ids_ml_new-z2i.2` concurrently actionable while both claimed `scripts/ids_operator_console/auth.py`, which would have created a real first-wave write conflict.
- **Risk alignment**: approach.md identified 3 HIGH-risk seams, but the bead graph initially had no spike beads for them.

Fixes applied:
- narrowed `ids_ml_new-z2i.2` so it no longer claims runtime-session/auth hardening files and instead stays focused on schema/bootstrap/CLI work
- clarified `ids_ml_new-z2i.1` around `public_base_url` and `ids_ml_new-z2i.3` around offline restore discipline
- created 3 explicit spike beads:
  - `ids_ml_new-gen`
  - `ids_ml_new-n1m`
  - `ids_ml_new-1hs`

### Iteration 2

Result: **PASS**

All 8 dimensions pass:
1. Requirement coverage: PASS
2. Dependency correctness: PASS
3. File scope isolation: PASS
4. Context budget: PASS
5. Test coverage: PASS
6. Gap detection: PASS
7. Risk alignment: PASS
8. Completeness: PASS

Notes:
- locked decisions `D1-D15` are covered by the revised bead set
- no dependency cycles were detected
- `br ready --json` now shows the intended first actionable layer:
  - `ids_ml_new-z2i.1`
  - `ids_ml_new-z2i.2`

---

## 2. Spike Execution

### HIGH-risk item 1

- Risk: `Proxy-aware config + session hardening`
- Spike bead: `ids_ml_new-gen`
- Findings: [FINDINGS.md](F:\Work\IDS_ML_New\.spikes\ids-operator-console-production-hardening\ids_ml_new-gen\FINDINGS.md)
- Result: **YES**

Validated constraints:
- add explicit `forwarded_allow_ips` / trusted-proxy config, optional `root_path`, and explicit `public_base_url`
- secure cookie posture must fail closed in production (`https_only=True`, non-placeholder secret, explicit cookie settings)
- keep redirects relative where possible; use `public_base_url` for absolute-URL and smoke-facing origin contracts
- proxy/preflight artifacts must require `Host`, `X-Forwarded-Proto`, and `X-Forwarded-For`

### HIGH-risk item 2

- Risk: `Schema versioning + explicit migration/upgrade path`
- Spike bead: `ids_ml_new-n1m`
- Findings: [FINDINGS.md](F:\Work\IDS_ML_New\.spikes\ids-operator-console-production-hardening\ids_ml_new-n1m\FINDINGS.md)
- Result: **YES**

Validated constraints:
- startup must stop mutating schema implicitly
- add explicit schema metadata/version tracking and ordered migrations
- `bootstrap-admin` and `migrate` stay in the operator CLI, not the runtime request path
- upgrade from v1 is `verify -> explicit migrate -> start`

### HIGH-risk item 3

- Risk: `Backup/restore + secret-reference validation`
- Spike bead: `ids_ml_new-1hs`
- Findings: [FINDINGS.md](F:\Work\IDS_ML_New\.spikes\ids-operator-console-production-hardening\ids_ml_new-1hs\FINDINGS.md)
- Result: **YES**

Validated constraints:
- online backup may use SQLite backup primitives against the live WAL database
- restore must be offline-only with explicit service-stop and destination-validation preconditions
- manifest scope includes config + secret references, never secret material
- restore success requires secret references to be rebound and validated before completion

Spike learnings embedded into affected beads:
- `ids_ml_new-z2i.1`
- `ids_ml_new-z2i.2`
- `ids_ml_new-z2i.3`
- `ids_ml_new-z2i.4`
- `ids_ml_new-z2i.5`

---

## 3. Bead Polishing

### `bv --robot-suggest`

- dependency suggestions adopted: `0`
- rationale: repo-wide duplicate/label suggestions were unrelated to the current epic; no current-epic dependency gap required graph changes after the spike/bead fixes

### `bv --robot-insights`

- critical issues resolved: `0`
- cycles found: `0`
- notable graph facts:
  - `ids_ml_new-z2i.2` is the first meaningful unblock point because it unlocks `ids_ml_new-z2i.3`
  - `ids_ml_new-z2i.4` and `ids_ml_new-z2i.3` are the two medium-depth integration steps before the final production-artifact bead

### `bv --robot-priority`

- priority adjustments made: `0`
- rationale: the current `P1/P2` split still reflects the intended execution order and keeps the first wave on the two highest-risk foundations

### Deduplication

- duplicates found in the current epic: `0`

### Fresh-eyes review

Manual cold-read pass against the revised beads:
- critical issues: `0`
- minor issues: `0`

---

## 4. Conclusion

Validation status: **READY FOR APPROVAL**

Residual concerns:
- actual reverse-proxy/header details still depend on the concrete host deployment, but the runtime contract is now explicit instead of implied
- backup safety is now bounded by an explicit offline-restore discipline, which must be enforced during execution and review rather than treated as optional operator hygiene

Confidence level: **HIGH**

The plan is now structurally sound, the HIGH-risk seams have definitive YES spikes with concrete constraints, and the bead graph is actionable without first-wave file conflicts. The feature is ready for the GATE 2 execution decision.
