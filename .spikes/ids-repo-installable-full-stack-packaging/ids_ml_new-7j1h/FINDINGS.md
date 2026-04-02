# Spike: ids_ml_new-7j1h

Result: YES

Question:
- Can deploy assets and operator docs converge on packaged canonical entrypoints and `ids/console` assets in one pass?

Decision:
- Yes. The target state is coherent, but it is a broad pass that must update deploy assets, operator docs, and asset-root references together.

Validated convergence shape:
- Move deploy assets from `/opt/ids_ml_new/scripts/*.py` entrypoints to installed canonical entrypoints that resolve directly into `ids/*` modules.
- Move operator-console asset roots from `/opt/ids_ml_new/scripts/ids_operator_console/{templates,static}` to packaged canonical `ids/console/{templates,static}`.
- Converge same-host docs on one operator story:
  - installed canonical entrypoints as the primary path
  - `verify/promote -> active_bundle.json -> runtime` as the only production activation story
  - externalized env/config/secret inputs under `/etc` and `/var`, not packaged defaults
- Keep `scripts/*` only as narrow compatibility notes for direct repo execution and smoke coverage.

Evidence:
- Docs already hint at the target state in:
  - [ids_same_host_stack_operations.md](F:/Work/IDS_ML_New/docs/current/operations/ids_same_host_stack_operations.md)
- Shipped assets still lag behind:
  - [ids-live-sensor.service](F:/Work/IDS_ML_New/deploy/systemd/ids-live-sensor.service)
  - [ids-operator-console.service](F:/Work/IDS_ML_New/deploy/systemd/ids-operator-console.service)
  - [ids-operator-console-notify.service](F:/Work/IDS_ML_New/deploy/systemd/ids-operator-console-notify.service)
  - [ids-operator-console.conf.example](F:/Work/IDS_ML_New/deploy/nginx/ids-operator-console.conf.example)
  - [final_model_bundle.md](F:/Work/IDS_ML_New/docs/current/runtime/final_model_bundle.md)

Constraints:
- Do not preserve wrapper-local template/static paths as a long-lived seam.
- `final_model_bundle.md` still needs a real rewrite onto the packaged operator path, not wording polish only.
- This is a multi-file convergence pass, not a one-line service-unit retarget.
