# Approach: Linux Packaging & Instructions Readiness

**Date**: 2026-04-04
**Feature**: ids-linux-packaging-and-instructions
**Based on**:
- `history/ids-linux-packaging-and-instructions/discovery.md`
- `history/ids-linux-packaging-and-instructions/CONTEXT.md`

---

## 1. Gap Analysis

| Component | Have | Need | Gap Size |
|-----------|------|------|----------|
| Release tarball trimming | `git archive HEAD` exports all 771 tracked files | `.gitattributes` with `export-ignore` rules for dev-only content | Small — add one file |
| Linux prerequisites doc | Nothing — installer assumes packages exist | Single doc listing system packages, install commands, verification | New — write from scratch |
| Doc platform consistency | 7 files bash, 3 PowerShell, 5 mixed | Decision per file: add bash equivalents or leave as-is based on audience | Medium — update 2-6 files |
| Model bundle in release | Git-tracked, ships in archive automatically | Explicit decision: keep bundled or add `export-ignore` | Tiny — one `.gitattributes` line either way |
| Python version check in installer | Installer creates venv but doesn't verify Python version | Add version check before `python3.11 -m venv` | Tiny — ~5 lines in `install.sh` |
| `MANIFEST.in` | Missing | Not needed — deployment uses editable install from extracted checkout | No gap — skip |

---

## 2. Recommended Approach

Add a `.gitattributes` file to trim dev-only directories from the release tarball. Write a single prerequisites document listing all system packages needed on a fresh Linux host. Fix the e2e demo runbook and root README to include bash examples alongside PowerShell. Leave ML-specific docs (training, benchmarking) as PowerShell-only since they target Windows dev machines. Keep the model bundle in the tarball since it's intentionally git-tracked and operators expect a self-contained deployment archive.

### Why This Approach

- Trimming via `.gitattributes` `export-ignore` keeps the `git archive` safety contract intact (critical pattern from `20260404-telegram-settings-deploy-hardening.md`) while reducing tarball size
- A single prerequisites doc fills the most impactful documentation gap — operators currently have no way to know what to `apt install` before running the installer
- Fixing only operator-facing docs (demo runbook, README) respects the natural audience split: deployment docs → bash, ML research docs → PowerShell
- Keeping the model bundled matches the documented workflow in `ops/README-deploy.md` where `--candidate-bundle-root /opt/ids_ml_new/artifacts/final_model/catboost_full_data_v1` is the in-checkout path

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| D1: Tarball trimming | Add `.gitattributes` with `export-ignore` | Removes ~40% dev content; preserves git archive safety |
| D2: Prerequisites audience | Sysadmin-level (package names + commands, no hand-holding) | Matches the tone of existing ops docs |
| D3: Doc platform syntax | Bash examples for operator-facing docs; PowerShell stays in ML/dev docs | Natural audience split already exists |
| D4: Model bundle | Keep bundled in tarball | Operators expect self-contained archive; model is intentionally tracked |

---

## 3. Alternatives Considered

### Option A: Ship model separately

- Description: Add `artifacts/ export-ignore` to `.gitattributes`, document separate model staging
- Why considered: Smaller tarball, model updates decouple from code releases
- Why rejected: The model is intentionally git-tracked with explicit `.gitignore` allowlist. Removing it from the archive breaks the documented `--candidate-bundle-root /opt/ids_ml_new/artifacts/...` workflow and requires a new staging procedure that doesn't exist yet.

### Option B: Dual-syntax for all docs

- Description: Add both bash and PowerShell examples to every documentation file
- Why considered: Maximum cross-platform coverage
- Why rejected: ML docs (training, benchmarking, tuning) are inherently Windows dev workflows. Adding bash examples there adds maintenance burden with no deployment benefit. The natural split is already clean.

### Option C: No tarball trimming

- Description: Ship the full 36.5 MB archive as-is
- Why considered: Simplest, no `.gitattributes` maintenance
- Why rejected: Dev artifacts (`.khuym/`, `.beads/`, `.spikes/`, `history/`, `tests/`, `kaggle/`, `.claude/`) have no purpose on a production host. Trimming is low-effort and reduces the attack surface.

---

## 4. Risk Map

| Component | Risk Level | Reason | Verification Needed |
|-----------|------------|--------|---------------------|
| `.gitattributes` export-ignore | **LOW** | Well-documented git feature, no code changes | Verify archive contents after adding |
| Linux prerequisites doc | **LOW** | Pure documentation, no runtime impact | Peer review for completeness |
| Demo runbook bash examples | **LOW** | Adding bash alternatives to existing content | Run the bash commands to verify they work |
| `install.sh` Python version check | **LOW** | Small guard at script start | Test with wrong Python version |
| Root README bash examples | **LOW** | Trivial syntax addition | Visual review |

No HIGH-risk components. Validating may skip spike phase.

---

## 5. Proposed File Structure

```
New files:
  .gitattributes                                    # export-ignore rules for dev content
  docs/current/operations/linux_prerequisites.md    # system package requirements

Modified files:
  ops/install.sh                                    # add Python version check (~5 lines)
  docs/current/operations/e2e_demo_runbook.md       # add bash examples alongside PowerShell
  docs/current/operations/README.md                 # link to new prerequisites doc
  README.md                                         # add bash quick-test example
```

---

## 6. Dependency Order

```
Layer 1 (parallel): .gitattributes + linux_prerequisites.md (independent)
Layer 2 (parallel): install.sh version check + doc updates (independent of each other)
Layer 3 (sequential): verify tarball contents + verify docs (depends on Layer 1-2)
```

All components are independent and LOW risk. Maximum parallelization is possible.

---

## 7. Institutional Learnings Applied

| Learning Source | Key Insight | How Applied |
|-----------------|-------------|-------------|
| `20260404-telegram-settings-deploy-hardening.md` | Use `git archive`, never raw tar | `.gitattributes` `export-ignore` works with `git archive` by design — preserves the safety contract |
| `20260403-packaging-contract-proof.md` | Scrubbed install proof required | Verification story includes fresh install proof after packaging changes |
| `20260403-packaging-contract-proof.md` | Bind execution to validated interpreter | Prerequisites doc and all bash examples reference `.venv/bin/python`, not host Python |
| `20260404-telegram-settings-deploy-hardening.md` | Config contracts shared, not reimplemented | Prerequisites doc references the canonical `ids-stack` CLI, not reimplemented check commands |

---

## 8. Open Questions for Validating

- [ ] Does `scripts/` need to ship in the release for backward compatibility? — Some wrapper scripts may still be documented as user-facing
- [ ] Are there any demo artifacts under `artifacts/demo/` that should also ship? — The e2e demo runbook references them

No HIGH-risk items requiring spikes.
