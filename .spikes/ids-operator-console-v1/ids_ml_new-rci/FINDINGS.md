# Spike Findings: ids_ml_new-rci

## Question

Can single-admin cookie auth satisfy the console boundary safely?

## Result

**YES**

## Evidence

- The v1 product boundary is explicitly single-admin and same-host in [CONTEXT.md](F:/Work/IDS_ML_New/history/ids-operator-console-v1/CONTEXT.md), so the plan does not need OAuth, SSO, or multi-role policy machinery.
- Official Starlette middleware documentation includes `SessionMiddleware`, which is appropriate for signed-cookie session handling on protected server-rendered routes:
  - [Starlette middleware](https://www.starlette.io/middleware/)
- FastAPI's form support covers standard login form posts, and the local environment already has `python-multipart` importable.
- The current plan already limits the console to observe/triage/report/notify, so the auth boundary is protecting a narrow admin console rather than a broader control plane.

## Validated Constraints

1. The auth bead should implement signed session cookies, not a heavier multi-user auth subsystem.
2. CSRF protection must be explicit for state-changing form posts; this cannot be left implicit in the framework defaults.
3. Protected routes must fail closed for unauthenticated access.
4. Production deployment should keep secure cookie settings configurable so the same-host service can run safely behind a reverse proxy/TLS terminator.

## Impact on Plan

- The single-admin auth approach remains viable.
- Validation is not blocked on the authentication boundary.
- Execution beads should lock around signed cookies, explicit CSRF tokens, and fail-closed protected routes.
