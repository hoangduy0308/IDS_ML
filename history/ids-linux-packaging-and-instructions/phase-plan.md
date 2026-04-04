# Phase Plan: Linux Packaging & Instructions Readiness

**Date**: 2026-04-04
**Feature**: ids-linux-packaging-and-instructions
**Based on**:
- `history/ids-linux-packaging-and-instructions/CONTEXT.md`
- `history/ids-linux-packaging-and-instructions/discovery.md`
- `history/ids-linux-packaging-and-instructions/approach.md`

---

## 1. Feature Summary

The IDS same-host stack already has a working installer, release builder, systemd services, and operations docs — but an operator landing on a fresh Ubuntu box today has no single document telling them what system packages to install first, the release tarball ships ~40% dev-only content, and some key docs only show Windows commands. This feature closes those gaps so the system can be built, shipped, and run on a fresh Linux host from one set of instructions without guesswork.

---

## 2. Why This Breakdown

- Phase 1 does the packaging infrastructure work (`.gitattributes`, installer hardening) because all documentation should reference the trimmed tarball and improved installer, not the other way around.
- Phase 2 does the documentation work because it depends on knowing the final tarball contents and installer behavior from Phase 1.
- Two phases is the right split because packaging changes and doc changes are independent workstreams with different verification methods, but docs should describe the final state of the tooling.

---

## 3. Phase Overview Table

| Phase | What Changes In Real Life | Why This Phase Exists Now | Demo Walkthrough | Unlocks Next |
|-------|---------------------------|---------------------------|------------------|--------------|
| Phase 1: Clean release artifact + installer hardening | Running `build_release.sh` produces a smaller tarball without dev artifacts, and the installer catches wrong Python versions before wasting time | The release tarball and installer are the foundation — docs should describe the final tooling | Run `build_release.sh`, inspect archive contents, confirm dev dirs are absent; run installer with Python 3.10, see clear error | Phase 2: documentation |
| Phase 2: Complete Linux deployment documentation | An operator with a fresh Ubuntu box can follow one set of docs from `apt install` through `ids-stack smoke` without guessing | Docs are the user-facing product of this feature; they must describe the final tooling from Phase 1 | Start with prerequisites doc, install packages, follow quickstart, reach a passing `ids-stack preflight` | Feature complete |

---

## 4. Phase Details

### Phase 1: Clean release artifact + installer hardening

- **What Changes In Real Life**: The release tarball built by `build_release.sh` no longer contains test suites, agent coordination files, spike results, or historical learning artifacts. The installer fails early with a clear message if the Python version is wrong. The tarball is smaller and contains only what a production host needs.

- **Why This Phase Exists Now**: Every documentation reference to "extract the tarball" and "run the installer" should describe the final state of these tools. Fixing tooling after writing docs means rewriting docs.

- **Stories Inside This Phase**:
  - Story 1: Add `.gitattributes` with `export-ignore` rules — dev-only directories are excluded from `git archive` output
  - Story 2: Add Python version check to `install.sh` — the installer fails early with a clear message instead of a cryptic venv error
  - Story 3: Verify the release artifact — run `build_release.sh`, inspect the archive, confirm excluded dirs are absent and required dirs are present

- **Demo Walkthrough**: Run `bash ops/build_release.sh`. Extract the tarball to a temp dir. Confirm `tests/`, `.khuym/`, `.beads/`, `history/`, `kaggle/` are absent. Confirm `ids/`, `deploy/`, `ops/`, `artifacts/final_model/`, `pyproject.toml` are present. Run the installer with Python 3.10 and see it refuse with a version error.

- **Unlocks Next**: Phase 2 — documentation can now describe the final tarball contents and installer behavior

### Phase 2: Complete Linux deployment documentation

- **What Changes In Real Life**: An operator starting from scratch on a fresh Ubuntu/Debian host can follow documentation from "install system packages" through "verify the stack is running" without hitting undocumented steps. The demo runbook works on Linux. The root README shows bash commands.

- **Why This Phase Exists Now**: The tooling from Phase 1 is finalized, so docs can describe the real behavior without risk of drift.

- **Stories Inside This Phase**:
  - Story 1: Write Linux prerequisites doc — a new `docs/current/operations/linux_prerequisites.md` listing every system package, install commands, and verification steps
  - Story 2: Add bash examples to operator-facing docs — the e2e demo runbook and root README get bash command blocks alongside or replacing PowerShell
  - Story 3: Link and cross-reference — the operations README and deployment quickstart link to the new prerequisites doc, creating a complete reading path

- **Demo Walkthrough**: Open `docs/current/operations/linux_prerequisites.md`. Follow the `apt install` commands on a fresh Ubuntu 22.04 box (or read through them). Then follow the deployment quickstart from tarball extraction through `ids-stack preflight`. Every step should be documented with no gaps.

- **Unlocks Next**: Feature complete — the system is fully packaged and documented for Linux deployment

---

## 5. Phase Order Check

- [x] Phase 1 is obviously first — tooling must be finalized before docs describe it
- [x] Phase 2 depends on Phase 1 — docs reference the trimmed tarball and improved installer
- [x] No phase is just a technical bucket — Phase 1 = "the release artifact is production-clean", Phase 2 = "an operator can deploy without guesswork"

---

## 6. Approval Summary

- **Current phase to prepare next**: Phase 1 - Clean release artifact + installer hardening
- **What the user should picture after that phase**: Running `build_release.sh` produces a lean tarball with only production files, and the installer catches version mismatches early
- **What will not happen until later phases**: Writing the prerequisites doc and fixing doc syntax happens in Phase 2
