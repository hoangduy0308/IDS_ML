---
date: 2026-04-04
feature: ids-linux-packaging-and-instructions
categories: [pattern, failure]
severity: standard
tags: [packaging, documentation, git, installer, review]
---

# Learning: Fail-Closed Version Checks In Installers

**Category:** failure
**Severity:** standard
**Tags:** [installer, version-check, fail-closed]
**Applicable-when:** Adding any preflight or version guard to an installer or bootstrap script

## What Happened

The initial Python version check in `ops/install.sh` used an `if command -v` guard that silently skipped the entire version check when the binary was missing. The script would still fail later inside `install_python_product()`, but the error message said "Python binary not found" without mentioning the 3.11+ requirement. Similarly, if the Python binary existed but couldn't run `import sys` (broken install), the empty-output guard skipped the version check entirely. Review caught both paths.

## Root Cause / Key Insight

Defensive guards that silently skip instead of fail-closed create a gap where the operator gets a confusing downstream error instead of the specific early-exit message. When a version check exists to give operators a clear early error, the missing-binary and broken-binary paths must also produce clear errors — otherwise the guard is only useful for the happy path where it's least needed.

## Recommendation for Future Work

When adding version or dependency guards to installers, structure them as fail-closed: if the binary is missing, fail with a message that names the requirement. If the binary exists but can't report its version, fail with a message that names the requirement. Only proceed when the version is positively confirmed. Never silently skip a guard.

---

# Learning: Replace Absolute Paths With Relative Paths In Documentation Links

**Category:** failure
**Severity:** standard
**Tags:** [documentation, markdown, portability]
**Applicable-when:** Writing or reviewing Markdown documentation that contains links to other files in the repo

## What Happened

The root `README.md` and `e2e_demo_runbook.md` contained absolute Windows paths (e.g., `F:/Work/IDS_ML_New/docs/README.md`) as Markdown link targets. These links are broken for anyone who clones the repo to a different path or OS. The review caught this as a P2 pre-existing issue. The paths were written during initial development and never converted to relative paths.

## Root Cause / Key Insight

Absolute local paths in Markdown links are a subtle portability defect. They work on the author's machine and silently break everywhere else. CI does not catch broken Markdown links by default, so they persist until a human notices. The fix is trivial (use relative paths), but the pattern recurs because the author's IDE often inserts absolute paths when auto-completing.

## Recommendation for Future Work

Always use relative paths in Markdown links. When reviewing documentation changes, grep for absolute local paths (`F:/`, `C:/`, `/home/`, `/Users/`) in `.md` files and fix them before merge. If the repo grows a link-checking CI step, this class of defect disappears automatically.

---

# Learning: Use Export-Ignore To Trim Dev Artifacts From Release Tarballs

**Category:** pattern
**Severity:** standard
**Tags:** [packaging, git, release, gitattributes]
**Applicable-when:** Building release archives from a git repo that contains dev-only directories (tests, agent state, history)

## What Happened

Adding a `.gitattributes` file with `export-ignore` rules for dev-only directories (`tests/`, `.khuym/`, `.beads/`, `history/`, `kaggle/`, etc.) reduced the `git archive` output from 771 to 329 files — a 57% reduction — without changing the `build_release.sh` contract at all. The `git archive` safety pattern (from the previous feature's learning) was preserved because `.gitattributes` is part of git's native archive mechanism, not a manual tar exclusion.

## Root Cause / Key Insight

`git archive` respects `.gitattributes` `export-ignore` by design. This is the correct allow-list complement to the `git archive` safety pattern: `git archive` ensures only tracked files ship (preventing secret leaks), and `export-ignore` further trims tracked-but-dev-only content. Together they produce a minimal, clean release artifact.

## Recommendation for Future Work

When a repo's `git archive` output includes dev-only directories, add `.gitattributes` with `export-ignore` rules rather than modifying the build script. Review the exclusion list when adding new top-level directories — any new dev-only directory should get an `export-ignore` entry.
