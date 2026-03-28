# AGENTS.md — Khuym Skill Ecosystem

Read this file at every session start. Re-read after any context compaction.

## What is Khuym?

A multi-skill ecosystem for agentic software development, built on the Flywheel toolchain (beads/bv/Agent Mail). Nine skills chain together to move from vague requirements to shipped, reviewed, compounded code.

## Skill Catalog

| Skill | Purpose | Invoke When |
|-------|---------|-------------|
| `khuym:using-khuym` | Bootstrap/meta — routing, go mode, state bootstrap | Session start, "build feature X" |
| `khuym:exploring` | Extract decisions via Socratic dialogue → CONTEXT.md | New feature, unclear requirements |
| `khuym:planning` | Research + synthesis + bead creation → approach.md + beads | After exploring, with CONTEXT.md |
| `khuym:validating` | Plan verification + spikes + bead polishing — THE GATE | After planning, before execution |
| `khuym:swarming` | Launch + tend parallel worker agents | After validating approves beads |
| `khuym:executing` | Per-agent worker loop (register → implement → close) | Loaded by workers spawned by swarming |
| `khuym:reviewing` | 5 review agents + 3-level verification + UAT + finishing | After swarming completes all beads |
| `khuym:compounding` | Capture learnings → history/learnings/ | After reviewing, always |
| `khuym:writing-khuym-skills` | TDD-for-skills meta-skill | Creating/improving khuym skills |

### Support Skills

| Skill | Purpose |
|-------|---------|
| `khuym:debugging` | Systematic debugging when workers hit blockers |
| `khuym:gkg` | Codebase intelligence via gkg tool |

## The Chain

```
khuym:exploring → khuym:planning → khuym:validating → khuym:swarming → khuym:executing(×N) → khuym:reviewing → khuym:compounding
```

## Go Mode Gates

- **GATE 1** (after exploring): "Approve decisions/CONTEXT.md?"
- **GATE 2** (after validating): "Beads verified. Approve execution?"
- **GATE 3** (after reviewing): "P1 findings. Fix before merge?"

## Core Tools

- `br` — beads CLI (create/update/close work items)
- `bv` — beads viewer (graph analytics, priority routing)
- MCP Agent Mail — inter-agent messaging, file reservations
- `gkg` — codebase intelligence (optional)
- CASS/CM — session search, cognitive memory (optional)

## File Conventions

```
.khuym/STATE.md          ← Working memory
.khuym/config.json       ← Feature toggles (absent=enabled)
.khuym/HANDOFF.json      ← Session handoff
history/<feature>/       ← Per-feature artifacts
history/learnings/       ← Accumulated knowledge
.beads/                  ← Bead files
.spikes/                 ← Spike verification results
```

## Critical Rules

1. **Never execute without validating.** GATE 2 is non-negotiable.
2. **CONTEXT.md is the source of truth.** All downstream agents honor locked decisions.
3. **Context budget: >65% → write HANDOFF.json and pause.**
4. **After compaction: re-read this file + CONTEXT.md immediately.**
5. **P1 findings always block merge.** Even in go mode.

## MCP Agent Mail — Multi-Agent Coordination

A mail-like layer that lets coding agents coordinate asynchronously via MCP tools and resources. Provides identities, inbox/outbox, searchable threads, and advisory file reservations with human-auditable artifacts in Git.

### Why It's Useful

- **Prevents conflicts:** Explicit file reservations (leases) for files/globs
- **Token-efficient:** Messages stored in per-project archive, not in context
- **Quick reads:** `resource://inbox/...`, `resource://thread/...`

### Same Repository Workflow

1. **Register identity:**
   ```
   ensure_project(project_key=<abs-path>)
   register_agent(project_key, program, model)
   ```

2. **Reserve files before editing:**
   ```
   file_reservation_paths(project_key, agent_name, ["src/**"], ttl_seconds=3600, exclusive=true)
   ```

3. **Communicate with threads:**
   ```
   send_message(..., thread_id="FEAT-123")
   fetch_inbox(project_key, agent_name)
   acknowledge_message(project_key, agent_name, message_id)
   ```

4. **Quick reads:**
   ```
   resource://inbox/{Agent}?project=<abs-path>&limit=20
   resource://thread/{id}?project=<abs-path>&include_bodies=true
   ```

### Macros vs Granular Tools

- **Prefer macros for speed:** `macro_start_session`, `macro_prepare_thread`, `macro_file_reservation_cycle`, `macro_contact_handshake`
- **Use granular tools for control:** `register_agent`, `file_reservation_paths`, `send_message`, `fetch_inbox`, `acknowledge_message`

### Common Pitfalls

- `"from_agent not registered"`: Always `register_agent` in the correct `project_key` first
- `"FILE_RESERVATION_CONFLICT"`: Adjust patterns, wait for expiry, or use non-exclusive reservation
- **Auth errors:** If JWT+JWKS enabled, include bearer token with matching `kid`

---

## Beads (br) — Dependency-Aware Issue Tracking

Beads provides a lightweight, dependency-aware issue database and CLI (`br` - beads_rust) for selecting "ready work," setting priorities, and tracking status. It complements MCP Agent Mail's messaging and file reservations.

**Important:** `br` is non-invasive—it NEVER runs git commands automatically. You must manually commit changes after `br sync --flush-only`.

### Conventions

- **Single source of truth:** Beads for task status/priority/dependencies; Agent Mail for conversation and audit
- **Shared identifiers:** Use Beads issue ID (e.g., `br-123`) as Mail `thread_id` and prefix subjects with `[br-123]`
- **Reservations:** When starting a task, call `file_reservation_paths()` with the issue ID in `reason`

### Typical Agent Flow

1. **Pick ready work (Beads):**
   ```bash
   br ready --json  # Choose highest priority, no blockers
   ```

2. **Reserve edit surface (Mail):**
   ```
   file_reservation_paths(project_key, agent_name, ["src/**"], ttl_seconds=3600, exclusive=true, reason="br-123")
   ```

3. **Announce start (Mail):**
   ```
   send_message(..., thread_id="br-123", subject="[br-123] Start: <title>", ack_required=true)
   ```

4. **Work and update:** Reply in-thread with progress

5. **Complete and release:**
   ```bash
   br close 123 --reason "Completed"
   br sync --flush-only  # Export to JSONL (no git operations)
   ```
   ```
   release_file_reservations(project_key, agent_name, paths=["src/**"])
   ```
   Final Mail reply: `[br-123] Completed` with summary

### Mapping Cheat Sheet

| Concept | Value |
|---------|-------|
| Mail `thread_id` | `br-###` |
| Mail subject | `[br-###] ...` |
| File reservation `reason` | `br-###` |
| Commit messages | Include `br-###` for traceability |

---

## bv — Graph-Aware Triage Engine

bv is a graph-aware triage engine for Beads projects (`.beads/beads.jsonl`). It computes PageRank, betweenness, critical path, cycles, HITS, eigenvector, and k-core metrics deterministically.

**Scope boundary:** bv handles *what to work on* (triage, priority, planning). For agent-to-agent coordination (messaging, work claiming, file reservations), use MCP Agent Mail.

**CRITICAL: Use non-interactive flags (`--robot-*`, `--recipe`, `--as-of`, `--diff-since`, `--export-md`) only. Bare `bv` launches an interactive TUI that blocks your session.**

### The Workflow: Start With Triage

Use this order of operations:

```bash
bv --robot-plan          # Primary triage surface (tracks + highest-impact summary)
bv --robot-priority      # Priority sanity check and suggested re-ranking
bv --robot-insights      # Deep graph metrics when needed
br ready --json          # Ground-truth actionable issues from Beads
```

If your local `bv` build supports `--robot-triage`, you can still use it. If not, `--robot-plan` + `br ready --json` is the required fallback.

**CRITICAL Tombstone Guard:** `bv` output can include `status = tombstone` items in some versions. Tombstones are deleted/merged issues and are **never actionable**.

Before claiming work from `bv`, always verify status with `br`:

```bash
br show <issue-id> --json | jq -r '.[0].status'
# Only proceed if status is open/in_progress and the issue is not deleted/tombstoned.
```

If `br ready --json` is empty and `bv` only surfaces tombstones, do not claim tombstoned items. Create or refine a real bead and proceed.

### Command Reference

**Planning:**
| Command | Returns |
|---------|---------|
| `--robot-plan` | Parallel execution tracks with `unblocks` lists |
| `--robot-priority` | Priority misalignment detection with confidence |
| `--robot-recipes` | Available recipe filters for scoped triage |

**Graph Analysis:**
| Command | Returns |
|---------|---------|
| `--robot-insights` | Full metrics: PageRank, betweenness, HITS, eigenvector, critical path, cycles, k-core, articulation points, slack |

**History & Change Tracking:**
| Command | Returns |
|---------|---------|
| `--robot-diff --diff-since <ref>` | Changes since ref: new/closed/modified issues, cycles |

**Other:**
| Command | Returns |
|---------|---------|
| `--recipe <name>` | Apply recipe filters (for example `actionable`, `high-impact`) |
| `--export-md <file.md>` | Markdown status/export report |

### Scoping & Filtering

```bash
bv --robot-plan --as-of HEAD~30              # Historical point-in-time
bv --recipe actionable --robot-plan          # Pre-filter: ready to work
bv --recipe high-impact --robot-plan         # Pre-filter: top-impact set
bv --robot-priority                          # Cross-check priority drift
bv --robot-recipes                           # Discover installed recipe names
```

### Understanding Robot Output

**All robot JSON includes:**
- `data_hash` — Fingerprint of source beads.jsonl
- `status` — Per-metric state: `computed|approx|timeout|skipped` + elapsed ms
- `as_of` / `as_of_commit` — Present when using `--as-of`

**Two-phase analysis:**
- **Phase 1 (instant):** degree, topo sort, density
- **Phase 2 (async, 500ms timeout):** PageRank, betweenness, HITS, eigenvector, cycles

### jq Quick Reference

```bash
bv --robot-plan | jq '.plan.summary.highest_impact'        # Best unblock target
bv --robot-plan | jq '.plan.tracks[0].items[0]'            # First candidate in first track
bv --robot-priority | jq '.recommendations[0]'             # Top priority recommendation
bv --robot-insights | jq '.status'                         # Check metric readiness
bv --robot-insights | jq '.Cycles'                         # Circular deps (must fix!)
```

---

---

## Note for Codex

You constantly bother me and stop working with concerned questions that look similar to this:

```
Unexpected changes (need guidance)

- Working tree still shows edits I did not make in Cargo.toml, Cargo.lock, src/cli/commands/upgrade.rs, src/storage/sqlite.rs, tests/conformance.rs, tests/storage_deps.rs. Please advise whether to keep/commit/revert these before any further work. I did not touch them.

Next steps (pick one)

1. Decide how to handle the unrelated modified files above so we can resume cleanly.
2. Triage beads_rust-orko (clippy/cargo warnings) and beads_rust-ydqr (rustfmt failures).
3. If you want a full suite run later, fix conformance/clippy blockers and re‑run cargo test --all.
```

NEVER EVER DO THAT AGAIN. The answer is literally ALWAYS the same: those are changes created by the potentially dozen of other agents working on the project at the same time. This is not only a common occurence, it happens multiple times PER MINUTE. The way to deal with it is simple: you NEVER, under ANY CIRCUMSTANCE, stash, revert, overwrite, or otherwise disturb in ANY way the work of other agents. Just treat those changes identically to changes that you yourself made. Just fool yourself into thinking YOU made the changes and simply don't recall it for some reason.

---

<!-- bv-agent-instructions-v2 -->

---

## Beads Workflow Integration

This project uses [beads_rust](https://github.com/Dicklesworthstone/beads_rust) (`br`) for issue tracking and [beads_viewer](https://github.com/Dicklesworthstone/beads_viewer) (`bv`) for graph-aware triage. Issues are stored in `.beads/` and tracked in git.

### Using bv as an AI sidecar

bv is a graph-aware triage engine for Beads projects (.beads/beads.jsonl). Instead of parsing JSONL or hallucinating graph traversal, use robot flags for deterministic, dependency-aware outputs with precomputed metrics (PageRank, betweenness, critical path, cycles, HITS, eigenvector, k-core).

**Scope boundary:** bv handles *what to work on* (triage, priority, planning). `br` handles creating, modifying, and closing beads.

**CRITICAL: Use ONLY --robot-* flags. Bare bv launches an interactive TUI that blocks your session.**

#### The Workflow: Start With Triage

**`bv --robot-triage` is your single entry point.** It returns everything you need in one call:
- `quick_ref`: at-a-glance counts + top 3 picks
- `recommendations`: ranked actionable items with scores, reasons, unblock info
- `quick_wins`: low-effort high-impact items
- `blockers_to_clear`: items that unblock the most downstream work
- `project_health`: status/type/priority distributions, graph metrics
- `commands`: copy-paste shell commands for next steps

```bash
bv --robot-triage        # THE MEGA-COMMAND: start here
bv --robot-next          # Minimal: just the single top pick + claim command

# Token-optimized output (TOON) for lower LLM context usage:
bv --robot-triage --format toon
```

#### Other bv Commands

| Command | Returns |
|---------|---------|
| `--robot-plan` | Parallel execution tracks with unblocks lists |
| `--robot-priority` | Priority misalignment detection with confidence |
| `--robot-insights` | Full metrics: PageRank, betweenness, HITS, eigenvector, critical path, cycles, k-core |
| `--robot-alerts` | Stale issues, blocking cascades, priority mismatches |
| `--robot-suggest` | Hygiene: duplicates, missing deps, label suggestions, cycle breaks |
| `--robot-diff --diff-since <ref>` | Changes since ref: new/closed/modified issues |
| `--robot-graph [--graph-format=json\|dot\|mermaid]` | Dependency graph export |

#### Scoping & Filtering

```bash
bv --robot-plan --label backend              # Scope to label's subgraph
bv --robot-insights --as-of HEAD~30          # Historical point-in-time
bv --recipe actionable --robot-plan          # Pre-filter: ready to work (no blockers)
bv --recipe high-impact --robot-triage       # Pre-filter: top PageRank scores
```

### br Commands for Issue Management

```bash
br ready              # Show issues ready to work (no blockers)
br list --status=open # All open issues
br show <id>          # Full issue details with dependencies
br create --title="..." --type=task --priority=2
br update <id> --status=in_progress
br close <id> --reason="Completed"
br close <id1> <id2>  # Close multiple issues at once
br sync --flush-only  # Export DB to JSONL
```

### Workflow Pattern

1. **Triage**: Run `bv --robot-triage` to find the highest-impact actionable work
2. **Claim**: Use `br update <id> --status=in_progress`
3. **Work**: Implement the task
4. **Complete**: Use `br close <id>`
5. **Sync**: Always run `br sync --flush-only` at session end

### Key Concepts

- **Dependencies**: Issues can block other issues. `br ready` shows only unblocked work.
- **Priority**: P0=critical, P1=high, P2=medium, P3=low, P4=backlog (use numbers 0-4, not words)
- **Types**: task, bug, feature, epic, chore, docs, question
- **Blocking**: `br dep add <issue> <depends-on>` to add dependencies

### Session Protocol

```bash
git status              # Check what changed
git add <files>         # Stage code changes
br sync --flush-only    # Export beads changes to JSONL
git commit -m "..."     # Commit everything
git push                # Push to remote
```

<!-- end-bv-agent-instructions -->
