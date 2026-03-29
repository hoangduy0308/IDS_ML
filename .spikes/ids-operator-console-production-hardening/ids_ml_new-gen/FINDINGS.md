# Spike Findings: `ids_ml_new-gen`

## Question

Can the operator console runtime model reverse-proxied HTTPS safely with explicit `public_base_url`?

## Result

**YES**

## Why

- The current stack already supports the primitives we need:
  - local runtime inspection on this machine shows `uvicorn.run()` exposes `proxy_headers`, `forwarded_allow_ips`, and `root_path`
  - a local FastAPI experiment confirmed that `FastAPI(root_path="/console")` makes `request.scope["root_path"]`, `request.base_url`, and `request.url_for(...)` resolve through the prefixed public path
  - a local Starlette experiment confirmed that `SessionMiddleware(..., https_only=True)` emits a `Secure; HttpOnly; SameSite=lax` cookie
- Official docs line up with that behavior:
  - FastAPI proxy docs say trusted forwarded headers should be enabled explicitly and that `root_path` is the mechanism for stripped-prefix deployment
  - Starlette docs say `https_only=True` is the production-safe setting for session cookies
  - Uvicorn docs say proxy headers are only trusted for configured `forwarded_allow_ips`

## Current Gaps In Repo

- [`scripts/ids_operator_console/config.py`](F:\Work\IDS_ML_New\scripts\ids_operator_console\config.py) has no proxy/header/root-path/public-origin settings yet.
- [`scripts/ids_operator_console/web.py`](F:\Work\IDS_ML_New\scripts\ids_operator_console\web.py) still mounts `SessionMiddleware` with `https_only=False`.
- [`scripts/ids_operator_console_server.py`](F:\Work\IDS_ML_New\scripts\ids_operator_console_server.py) does not pass explicit proxy/root-path settings into Uvicorn.

## Validated Constraints

1. Runtime config must add explicit fields for:
   - trusted proxy IPs / `forwarded_allow_ips`
   - optional `root_path`
   - explicit `public_base_url`
2. Production cookie posture must be fail-closed:
   - `https_only=True`
   - non-placeholder session secret
   - configurable `same_site`, `path`, and optional cookie domain if needed
3. Reverse-proxy correctness must not rely on implicit host reconstruction alone:
   - keep app redirects relative where possible
   - use `public_base_url` for any absolute-URL, smoke, or runbook-facing contract
4. Proxy example and preflight must require the trusted proxy to forward at least:
   - `X-Forwarded-For`
   - `X-Forwarded-Proto`
   - `Host`
5. If `root_path` is configured, validation must ensure it matches the deployed prefix contract.

## Impacted Beads

- `ids_ml_new-z2i.1`
- `ids_ml_new-z2i.4`
- `ids_ml_new-z2i.5`

## Evidence

- Local experiment: `FastAPI(root_path="/console")` produced `base_url=https://console.example.test/console/` and `url_for=/console/...`
- Local experiment: `SessionMiddleware(..., https_only=True)` emitted a cookie with `secure`
- Official docs:
  - [FastAPI behind a proxy](https://fastapi.tiangolo.com/advanced/behind-a-proxy/)
  - [Uvicorn settings](https://www.uvicorn.org/settings/)
  - [Starlette SessionMiddleware](https://www.starlette.io/middleware/#sessionmiddleware)
