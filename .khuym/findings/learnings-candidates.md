# Learning Candidates

## Candidate: safe-export-surface-release-bundles
Category: failure
Tags: [release, packaging, git, security, tar]
Summary: Release bundles should be built from a tracked or allowlisted export surface, not by archiving the live working tree with a short manual exclude list. Otherwise ignored or untracked local files can leak into deployment artifacts.
Evidence: Review bead `ids_ml_new-i7oa.1` found `ops/build_release.sh` archiving `.` from the repo root and relying on a manual exclude list; the closest existing packaging learnings cover scrubbed install proof, but not the export surface itself.
Recommended title: 20260404-safe-export-surface-release-bundles.md

## Candidate: harden-preseeded-secret-files-during-install
Category: failure
Tags: [install, permissions, secrets, systemd, security]
Summary: If an installer accepts a pre-seeded operator secret file as a supported input, it must re-harden ownership and mode on that file instead of only setting secure permissions when creating it. Otherwise a valid headless bootstrap path can leave secrets exposed under the caller's umask.
Evidence: Review bead `ids_ml_new-fsoc` found `ops/install.sh` only applies `0640 root:ids-operator` when it creates `/etc/ids-operator-console/ids-operator-console.env`, but leaves an existing file untouched; the same install path also finishes enabling the advertised worker set.
Recommended title: 20260404-harden-preseeded-secret-files-during-install.md

## Candidate: db-persisted-settings-need-key-allowlists-and-paired-validation
Category: pattern
Tags: [sqlite, settings, config, fail-closed, validation]
Summary: When a local SQLite settings table uses a generic key-value schema (`set_setting(key, value)`), the absence of a key allowlist means typos silently persist wrong keys and partial saves can leave the system half-configured (e.g., chat_id without bot_token). Future DB-backed settings surfaces should validate keys against an explicit allowlist and enforce paired-config invariants at the write boundary, not only at read time. This compounds two existing learnings: "Fail Closed On Partial Telegram Config" (20260329) warned about partial config drift, and "Normalize Hostile Metadata At Contract Boundaries" (20260331) warned about unvalidated inputs at persistence boundaries. The new insight is that a generic settings store creates a third drift seam between the write surface, the read surface, and the runtime contract.
Evidence: P2-C (no key validation) and P2-E (partial Telegram config persisted) from this review. `set_setting()` in `ids/console/db.py` accepts arbitrary string keys with no allowlist. `/settings` POST handler saves chat_id without requiring bot_token.
Recommended title: 20260404-db-settings-key-allowlist-and-paired-validation.md
