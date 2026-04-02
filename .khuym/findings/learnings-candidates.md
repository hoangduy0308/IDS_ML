# Learning Candidates

## 1. Bind Preflight Approval To The Exact Privileged Execution Origin
- Source findings: A
- Candidate category: failure
- Candidate severity: critical
- Domain/tags: [ops, preflight, security, bootstrap, trust-boundary]
- Related history:
  - `history/learnings/20260328-live-sensor-runtime-contracts.md` (`Systemd Packaging Is Safer With Exact-Path Preflight And One Config Source`)
  - `history/learnings/20260331-repo-structure-wrapper-contracts.md` (`Resolve Paths Then Prove Root Containment For Host-Level File Operations`)
- Proposed learning:
  Preflight is not a security boundary if privileged follow-on execution re-resolves the target through ambient cwd, `PYTHON*` environment, or a different interpreter/module search path. When a same-host stack preflight approves a module/interpreter pair for privileged actions, the later execution path must invoke that exact approved origin under the same sanitized execution contract, or fail closed.
- Applicable when:
  A bootstrap, migration, promotion, or admin command validates Python modules before invoking them with elevated operational impact.

## 2. Treat Constructor Fields And Exported Wrapper Signatures As Compatibility Surfaces
- Source findings: B, C
- Candidate category: failure
- Candidate severity: standard
- Domain/tags: [compatibility, packaging, api-contracts, wrappers, migration]
- Related history:
  - `history/learnings/20260331-repo-structure-wrapper-contracts.md` (`Treat Compatibility Wrappers As Executable Contracts`)
  - `history/learnings/20260331-repo-structure-wrapper-contracts.md` (`Keep Canonical Modules Independent From Compatibility Layers`)
  - `history/learnings/20260328-operator-console-runtime-wiring.md` (`Keep The Service Entrypoint Wired To The Real App Factory`)
- Proposed learning:
  During canonical-module migrations, compatibility scope is wider than CLI names. Renaming config payload fields from `*_entrypoint` to `*_module` or narrowing exported wrapper call signatures can break external automation and import-based callers even when the new canonical path is correct. Migrations should either ship explicit alias/adapter handling for the old contract or prove no supported callers exist.
- Applicable when:
  A packaging or architecture cleanup keeps old wrappers alive while changing constructor payloads, import surfaces, or callable signatures behind them.

## 6. Always Escape User Data Before innerHTML Injection In Polling Renderers

- Source findings: ids-console-ui-pencil-rebuild review (tb05)
- Candidate category: failure
- Candidate severity: critical
- Domain/tags: [security, xss, javascript, innerHTML, polling]
- Related history: none
- Proposed learning:
  Client-side polling renderers that rebuild DOM via `innerHTML` must escape all user-controlled fields before injection. Fields like `source_event_id`, timestamps, or any DB-origin string can contain `<`, `>`, `&`, `"`. A simple `esc()` helper (5 lines) blocks XSS across the entire renderer. Add it to the reviewer checklist for any JS code that does `container.innerHTML = ...` with data from a fetch response.
- Applicable when:
  Any vanilla JS function renders API response data into the DOM via innerHTML (not textContent or a safe DOM API).

## 5. Lock Data-Field Key Names In Triage Helpers And Cross-Reference In All Templates

- Source findings: ids-console-ui-pencil-rebuild review (mpc0)
- Candidate category: failure
- Candidate severity: standard
- Domain/tags: [jinja2, templates, data-contracts, consistency]
- Related history: none
- Proposed learning:
  When a DB-layer helper (`list_alerts_for_triage`) sets a specific key (`alert["suppressed"]`), any template that references a variant of that key (`alert.get("is_suppressed")`) silently renders the wrong result. The canonical key name should be anchored in the triage helper's docstring or a data-contract note in the approach/CONTEXT document, and new templates must be cross-checked against the canonical name during review.
- Applicable when:
  Multiple Jinja2 templates consume the same triage/query helper output and any of them are written in a different session or by a different worker.

## 4. Use Single-Hyphen CSS Modifier Convention Consistently Across Component Classes

- Source findings: ids-console-ui-pencil-rebuild review (rs8j)
- Candidate category: failure
- Candidate severity: standard
- Domain/tags: [css, naming-convention, templates, ui]
- Related history: none
- Proposed learning:
  When a CSS file defines single-hyphen modifier classes (`btn-primary`, `btn-danger`) and templates in the same project use the same pattern, any new template written with double-hyphen BEM (`btn--primary`, `btn--danger`) will produce silent styling failures — the element renders but unstyled. Establish the modifier convention in the CSS architecture decision (D4 equivalent) and check all new templates against it during review.
- Applicable when:
  Adding Jinja2/HTML templates to a project with a hand-rolled CSS token layer. Especially when multiple templates are added in one swarm.

## 3. Pin Command-Resolution Branches With Direct Success And Failure Tests
- Source findings: D
- Candidate category: failure
- Candidate severity: standard
- Domain/tags: [testing, cli, path-resolution, runtime, contracts]
- Related history:
  - `history/learnings/20260330-extractor-contract-hardening.md` (`Pin Command Tokenization And Negative Paths With Executable Round-Trip Tests`)
  - `history/learnings/20260329-same-host-stack-runtime-hardening.md` (`Failure: wired contract drift at the stack boundary`)
- Proposed learning:
  New command-resolution logic is an executable contract, not an implementation detail. If a stack helper adds PATH-based lookup or alternate resolution branches, tests must exercise the real success and failure behavior directly rather than relying on broader bootstrap coverage to reach it incidentally.
- Applicable when:
  A stack/runtime helper resolves binaries, modules, or command prefixes before spawning subprocesses or supervising host services.
