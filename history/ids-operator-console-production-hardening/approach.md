# Approach: IDS Operator Console Production Hardening

**Date**: 2026-03-29
**Feature**: `ids-operator-console-production-hardening`
**Based on**:
- `history/ids-operator-console-production-hardening/discovery.md`
- `history/ids-operator-console-production-hardening/CONTEXT.md`

---

## 1. Gap Analysis

| Component | Have | Need | Gap Size |
|-----------|------|------|----------|
| Reverse-proxy readiness | internal bindable FastAPI service with canonical entrypoint and basic `/healthz` | trusted proxy/header config, optional `root_path`, secure cookie posture, deployment artifact that is genuinely ready for HTTPS termination at the proxy | Medium |
| Secret/config contract | env-driven config with placeholder secret rejection in preflight | file-path based secret loading, optional credential-style paths, non-placeholder production defaults, explicit secret-reference semantics in backup/restore | New |
| Schema/bootstrap/migration safety | idempotent `CREATE TABLE IF NOT EXISTS` bootstrap in `db.py` | schema version tracking, explicit migration command, startup schema verification, safe v1-upgrade path, bootstrap-admin path | New |
| Backup/restore | none | SQLite backup workflow, manifest/config-reference backup, restore verification, fail-closed secret rebind contract, artifact retention | New |
| Retention | none | configurable retention/prune contract for operator-owned data/artifacts with rollback-safe cleanup | New |
| Operational readiness | preflight script + repo tests + minimal `/healthz` | layered health/readiness checks, smoke command, restore drill verification, production runbook, upgrade/runbook documentation | Medium |
| Deployment packaging | systemd unit with exact-path preflight and placeholder secret env | hardened unit/env example, proxy example/reference, ops workflow tied to explicit migration/smoke | Medium |

---

## 2. Recommended Approach

Implement `ids-operator-console-production-hardening` as an operational hardening layer on top of the existing Python-native console, without changing the product boundary or stack. Add a new operator-management seam centered on one explicit admin CLI (`scripts/ids_operator_console_manage.py`) backed by new library modules for schema versioning/migrations, backup/restore/retention operations, and richer readiness/smoke evaluation. Expand the existing config, web, server, preflight, and systemd surfaces so the running service is explicitly proxy-aware, secret-file aware, and fail-closed on schema/secret/config drift, while preserving the canonical app-factory deployment contract discovered in v1 review. Keep backup/restore focused on operator-owned artifacts by using SQLite’s built-in backup primitive plus a small manifest for config and secret references, never copying live DB files ad hoc and never treating secret material as restorable repo data.

### Why This Approach

- It preserves the codebase’s proven `FastAPI + Jinja2 + sqlite3 + systemd` shape instead of introducing infrastructure churn for a same-host hardening feature.
- It honors locked decisions `D1`-`D15` by keeping the app internal behind a reverse proxy, making migrations explicit, and treating smoke/runbook/restore drill as first-class deliverables rather than follow-up chores.
- It uses existing repo patterns for exact-path preflight and service packaging while closing the current production gaps exposed by discovery: placeholder secrets, weak `/healthz`, missing migration flow, missing backup/restore, and no runtime admin bootstrap.
- It aligns with institutional learnings by keeping the service entrypoint wired to the real app factory, making rollback/restore atomic and fail-closed, and giving validating clear HIGH-risk seams to spike before execution.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Operations entrypoint | Add one script-first admin CLI: `scripts/ids_operator_console_manage.py` | Fits the repo’s script-first style and centralizes `bootstrap-admin`, `migrate`, `backup`, `restore`, `prune-retention`, and `smoke` into one operator surface |
| Schema evolution | Introduce schema version metadata + ordered raw-SQL migration registry in new `scripts/ids_operator_console/migrations.py` | Avoids ORM/migration-framework churn while making startup verification and v1 upgrade explicit |
| Startup behavior | Service startup verifies config, secrets, admin bootstrap state, and schema compatibility, but never auto-applies shape-changing migrations | Directly enforces `D7` fail-closed startup behavior |
| Backup strategy | Use SQLite’s built-in backup primitive for DB snapshots plus a manifest that records config values and secret references (not secret values) | Safer than copying a live WAL-backed DB file and consistent with `D14` |
| Restore strategy | Restore DB + config/reference manifest atomically, then require validation that secret files are re-bound and readable before declaring success | Keeps restore security posture aligned with externalized secrets |
| Reverse-proxy readiness | Extend config/server/web to support trusted forwarded headers, optional `root_path`, and an explicit `public_base_url`; keep the app bound internally and let the proxy terminate TLS | Matches FastAPI/Uvicorn official proxy model, keeps redirects/cookies/docs paths honest behind the proxy, and satisfies `D1`/`D11` |
| Session hardening | Make session cookie security/path/domain posture configurable for production, default away from insecure placeholder behavior, and validate secret/config misuse pre-start | Current runtime has `https_only=False`; hardening must make this production-safe |
| Health model | Keep `/healthz` as lightweight liveness and add a richer readiness/smoke contract that surfaces schema/config/secret/data-path state | Satisfies `D10`-`D12` without overloading one liveness endpoint |
| Proxy artifact surface | Ship a proxy-agnostic contract plus one concrete Nginx example in-repo | Gives review a real `WIRED` deploy artifact while keeping scope bounded |
| Restore discipline | Allow online DB backup via SQLite backup API, but require restore and other destructive operator state replacement to run with the console service stopped and verified offline by CLI/preflight checks | Prevents restore claims from outrunning SQLite/process reality and keeps `D14`/`D15` fail-closed |

---

## 3. Alternatives Considered

### Option A: Auto-migrate on startup with env-only secrets

- Description: extend the current env-only unit and let startup apply pending migrations automatically when the DB version is behind.
- Why considered: minimal operator friction and fewer new scripts.
- Why rejected: violates `D5` and `D7`, keeps secrets in the least auditable path, and turns the most dangerous deployment step into implicit runtime behavior.

### Option B: Add a separate database / migration framework for hardening

- Description: introduce PostgreSQL or a full migration toolchain to formalize backup/restore and schema upgrades.
- Why considered: stronger long-term scalability and a more conventional production stack.
- Why rejected: the feature is explicitly same-host and console-only, and discovery showed the repo already has a functioning `sqlite3` boundary plus no package-manifest/dependency-management baseline for a bigger stack jump.

### Option C: Solve backup/restore with filesystem copy + shell scripts only

- Description: copy the DB file, archive config files, and restore them with shell-based wrappers.
- Why considered: easy to prototype and keeps the app code mostly untouched.
- Why rejected: conflicts with the promoted rollback/restore learnings, is brittle with WAL-backed SQLite, and makes `EXISTS / SUBSTANTIVE / WIRED` verification of restore safety much weaker.

### Option D: Put TLS termination into the app and skip reverse-proxy artifacts

- Description: use Uvicorn SSL options directly and make the console a public-edge HTTPS service.
- Why considered: fewer moving pieces for a small deployment.
- Why rejected: violates `D1`, broadens the operational surface unnecessarily, and moves the feature away from the same-host reverse-proxy topology the user explicitly approved.

---

## 4. Risk Map

| Component | Risk Level | Reason | Verification Needed |
|-----------|------------|--------|---------------------|
| Proxy-aware config + session hardening | **HIGH** | security-sensitive, crosses config/web/server/unit surfaces, and current runtime posture is intentionally looser than production | Spike in validating |
| Schema versioning + explicit migration/upgrade path | **HIGH** | new operational contract with upgrade-from-v1 semantics and startup fail-closed behavior | Spike in validating |
| Backup/restore workflow + secret-reference restore validation | **HIGH** | novel workflow, rollback-sensitive, directly constrained by security/restore learnings, and only safe if offline restore discipline is real | Spike in validating |
| Admin bootstrap / credential rotation workflow | **MEDIUM** | new ops surface, but built on existing auth/store primitives | Focused tests |
| Retention/prune contract | **MEDIUM** | new operator data lifecycle logic with some blast radius across tables/artifacts | Focused tests |
| Readiness + smoke surface | **MEDIUM** | new operational API/CLI contract, but built on existing app/preflight patterns | Focused tests |
| Systemd/proxy packaging + runbook artifacts | **MEDIUM** | mostly follows established service-packaging patterns, but must be wired to the new runtime contract | Artifact verification |

### Risk Classification Reference

```text
Pattern in codebase?        -> YES = LOW base
External dependency?        -> YES = HIGH
Blast radius > 5 files?     -> YES = HIGH
Otherwise                   -> MEDIUM
```

### HIGH-Risk Summary (for khuym:validating skill)

- `Proxy-aware config + session hardening`: prove the chosen config surface can run safely behind a trusted proxy, with secure cookie behavior, accurate `public_base_url` behavior, and no accidental fallback to placeholder/insecure settings.
- `Schema versioning + explicit migration/upgrade path`: prove a v1 database can be recognized and upgraded via an explicit command while normal startup fails closed before migration.
- `Backup/restore workflow + secret-reference restore validation`: prove the DB snapshot + manifest approach is consistent, that restore only proceeds under the required offline discipline, and that it fails closed when secret references are missing or stale.

---

## 5. Proposed File Structure

```text
scripts/
  ids_operator_console/
    config.py                         # Expanded runtime + proxy + secret-path config
    db.py                             # Store primitives + schema metadata hooks
    migrations.py                     # Schema versioning + ordered migration registry
    ops.py                            # Backup/restore/retention/smoke helpers
    health.py                         # Readiness evaluation and health payload builders
    auth.py                           # Session hardening + bootstrap/rotation helpers
    web.py                            # Liveness/readiness routes and proxy-aware app config
  ids_operator_console_server.py      # Uvicorn launcher with forwarded-header/root-path support
  ids_operator_console_preflight.py   # Expanded fail-closed deployment contract validation
  ids_operator_console_manage.py      # New operator CLI: bootstrap-admin/migrate/backup/restore/prune/smoke
deploy/
  systemd/
    ids-operator-console.service      # Hardened unit using env file + secret reference contract
  nginx/
    ids-operator-console.conf.example # Concrete reverse-proxy example
docs/
  ids_operator_console_architecture.md          # Updated runtime/deploy contract
  ids_operator_console_operations.md            # Production runbook: bootstrap/upgrade/backup/restore/smoke
tests/
  test_ids_operator_console_config.py
  test_ids_operator_console_auth.py
  test_ids_operator_console_db.py
  test_ids_operator_console_ingest.py
  test_ids_operator_console_notifications.py
  test_ids_operator_console_web.py
  test_ids_operator_console_ops.py              # New backup/restore/retention/smoke coverage
  test_ids_operator_console_preflight.py        # New deployment-contract coverage
```

---

## 6. Dependency Order

```text
Layer 1 (sequential): Contract foundations
  - config expansion
  - schema versioning/migration primitives
  - readiness model skeleton

Layer 2 (parallel): Operations primitives
  - admin/manage CLI bootstrap + migrate
  - backup/restore/retention helpers

Layer 3 (parallel): Runtime integration
  - web/server proxy-awareness + secure session posture
  - preflight/unit integration with the new config/ops contract

Layer 4 (sequential): Production artifacts
  - smoke flow
  - reverse-proxy example
  - operations runbook / upgrade doc
```

### Parallelizable Groups

- Group A: migration/versioning foundation and ops helper foundation can be prepared in parallel once the config contract is clear, but must keep disjoint write scopes.
- Group B: runtime integration (web/server) and deploy/preflight integration can run in parallel after Layer 1, provided unit/config ownership stays separate from DB/ops ownership.
- Group C: docs/proxy example/smoke artifact work depends on the runtime and ops surfaces being stable enough to document and verify.

---

## 7. Institutional Learnings Applied

| Learning Source | Key Insight | How Applied |
|-----------------|-------------|-------------|
| `history/learnings/20260328-operator-console-runtime-wiring.md` | Canonical entrypoint must run the real app factory | The plan preserves one canonical web app and extends the existing server entrypoint instead of adding a second “ops” or “proxy” app |
| `history/learnings/20260328-operator-console-runtime-wiring.md` | Review must check `EXISTS / SUBSTANTIVE / WIRED` | The plan explicitly includes wired deployment artifacts: unit changes, proxy example, smoke commands, and restore workflow, not only library modules |
| `history/learnings/20260328-live-sensor-runtime-contracts.md` | Linux services should use exact-path preflight and one config source | Hardening expands the current preflight/unit contract instead of scattering shell checks or duplicated runtime assumptions |
| `history/learnings/20260328-adapter-rollback-contract.md` | Multi-output publish/rollback is one contract; avoid copy-based restore fallback | Backup/restore is designed around SQLite backup + manifest + atomic promotion/fail-closed validation, not ad hoc file-copy recovery |
| `history/learnings/critical-patterns.md` | Validating must spike HIGH-risk items before swarming | The risk map calls out three HIGH-risk seams that validating must prove before execution starts |

---

## 8. Open Questions for Validating

- [ ] Does the chosen `public_base_url` contract fully cover redirects, cookies, and generated links behind the reverse proxy, or does validation discover one more canonical-origin/path seam that must be explicit? - if wrong, reverse-proxy readiness will look complete in code but still drift in deployment.
- [ ] Is one combined `ids_operator_console_manage.py` CLI still clear enough operationally, or does validation show that one subcommand family becomes too coupled for safe execution/test ownership? - if wrong, bead boundaries and worker write scopes may need refinement.
- [ ] Are the offline restore preconditions specific enough for same-host operations, including service-stop checks and destination cleanliness, or does validating require an even stricter lock/quiesce discipline? - if wrong, backup/restore safety claims would be overstated.
