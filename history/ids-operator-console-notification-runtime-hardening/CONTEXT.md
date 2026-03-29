# IDS Operator Console Notification Runtime Hardening — Context

**Feature slug:** ids-operator-console-notification-runtime-hardening
**Date:** 2026-03-29
**Exploring session:** complete
**Scope:** Deep

---

## Feature Boundary

Feature này harden outbound Telegram notification path của `ids_operator_console` thành một same-host runtime contract đủ production-ready bằng cách khóa ownership cho queue/dispatch/retry, bổ sung entrypoint vận hành rõ ràng, observability/readiness/runbook thực dụng, restart recoverability, và wiring deploy/preflight thật; feature này không mở rộng sang multi-host control plane, không thêm channel mới ngoài Telegram, và không cho notification failure làm hỏng ingest, triage, dashboard, hay readiness cốt lõi của console.

**Domain type(s):** CALL | RUN | READ | ORGANIZE

---

## Locked Decisions

These are fixed. Planning must implement them exactly. No creative reinterpretation.

### Scope Boundary
- **D1** Feature này chỉ harden notification runtime cho same-host deployment hiện tại của operator console; không mở rộng sang multi-host fleet routing, remote worker orchestration, hay control-plane semantics.
  *Rationale: User đã khóa rõ boundary là production hardening cho topology same-host hiện có, không phải thiết kế nền tảng phân tán mới.*

- **D2** Outbound channel duy nhất trong scope là `Telegram`; webhook, SIEM, email, hoặc channel abstraction tổng quát đều deferred.
  *Rationale: Repo đã có Telegram domain logic/tests; giá trị production gần nhất đến từ việc WIRED path hiện có thay vì nở rộng kênh mới.*

### Runtime Ownership
- **D3** Notification runtime ownership phải là một `same-host worker` riêng của operator console, tách khỏi web request path và tách khỏi live sensor producer; web app tiếp tục là surface `read/triage/monitoring`, không nhúng background dispatch thread bên trong process FastAPI.
  *Rationale: Scout cho thấy `notifications.py` đã tồn tại ở mức module nhưng chưa được WIRED vào runtime entrypoint nào; nhúng background loop vào web process sẽ làm mờ failure domain và đi ngược bài học giữ runtime entrypoint rõ ràng, một-canonical-path.*

- **D4** Worker này phải có `explicit operator/runtime entrypoint` do operator console sở hữu, đủ rõ để chạy `run-once` hoặc long-running loop dưới supervisor/systemd; không được tồn tại chỉ như helper function trong test/module.
  *Rationale: Khoảng trống production lớn nhất hiện tại là thiếu ownership/scheduling contract. Feature chỉ hoàn tất khi dispatch path có entrypoint vận hành thật.*

- **D5** Web service startup của operator console vẫn giữ posture `verify-only` cho runtime cốt lõi; notification dispatch/retry không được tự khởi chạy ngầm như side effect của `ids_operator_console_server.py`.
  *Rationale: Learning mới nhất của console yêu cầu tách runtime verification khỏi operator mutation/background work. Nếu web startup ngầm dispatch, readiness và rollback sẽ khó lý giải.*

### Queue Semantics And Delivery Boundary
- **D6** Queue nguồn cho Telegram chỉ đến từ `ingested attack alerts` đã qua suppression và loại trừ các triage terminal states hiện có; anomaly/summaries không trở thành Telegram notification trong feature này.
  *Rationale: Đây là semantics đã có trong `alerts.py`/`notifications.py` và đúng với boundary IDS operator alerting hiện tại.*

- **D7** `notification_deliveries` trong SQLite là source of truth local cho delivery state, gồm ít nhất pending/retry/failed/sent, attempt count, next-attempt timestamp, provider message id, và last error; planning không được thay sang external broker/queue trong feature này.
  *Rationale: Repo đã có bảng/state primitives phù hợp same-host, và user không muốn mở sang control-plane hay distributed queue.*

- **D8** Nếu Telegram hoàn toàn không được cấu hình thì notification path ở trạng thái `disabled` rõ ràng; partial/invalid Telegram config vẫn fail-closed qua config/preflight contract; disabled mode không được âm thầm tích lũy backlog vô hạn chỉ vì dispatch là bất khả thi.
  *Rationale: Production contract cần phân biệt `disabled on purpose` với `misconfigured/broken`, đồng thời tránh backlog giả gây khó vận hành.*

### Failure Isolation And Recovery
- **D9** Lỗi queueing, dispatch, retry, backoff, network outage, Telegram rejection, hay exhausted retry không được làm fail ingest JSONL, alert triage mutation, dashboard rendering, auth/session flow, hay core `/readyz` của console; các lỗi này chỉ được surfacing như notification degradation có thể quan sát và xử lý.
  *Rationale: Đây là objective cốt lõi của feature và cũng phù hợp boundary existing-console-not-control-plane.*

- **D10** Retry/backoff ownership vẫn là local, persisted, và restart-safe: worker sau restart phải có thể resume từ `notification_deliveries` hiện có mà không cần manual DB surgery, đồng thời failed terminal deliveries phải có một operator-visible redrive path thay vì yêu cầu sửa DB tay.
  *Rationale: User yêu cầu recoverability sau restart và runbook cho retry/drain/failure diagnosis; persisted retry state là seam production bắt buộc phải khóa.*

### Observability And Operator Surface
- **D11** Notification health phải xuất hiện như một `non-gating component` trong operator visibility surface: ít nhất qua status/readiness/ops output, với các tín hiệu như enabled/disabled state, backlog, oldest due item, retrying count, failed count, last error sample hoặc tương đương. Tuy nhiên degraded notification health một mình không được lật overall core console readiness sang failed.
  *Rationale: User muốn health/observability thật cho queue nhưng đồng thời đã khóa failure isolation khỏi readiness cốt lõi.*

- **D12** Operator surface tối thiểu phải hỗ trợ `status`, `test-send`, và `run-once/drain`, cùng với một long-running worker mode phù hợp supervisor/systemd; operator không được bị ép mở Python REPL hay SQLite trực tiếp để vận hành notification path.
  *Rationale: Candidate scope user đưa ra tập trung chính xác vào queue/drain/status/test-send và ownership của dispatch loop.*

- **D13** Journald/runbook/operator output phải đủ để chẩn đoán notification backlog, repeated retry, exhausted failure, disabled state, và recovery flow trên same host; không được để notification runtime chỉ “tồn tại trong DB”.
  *Rationale: Production-ready ở đây là vận hành được thật, không chỉ có code path và tests.*

### Deployment, Backup, And Done Criteria
- **D14** Nếu production bật Telegram notifications thì `runtime loader + preflight + deploy artifact + docs/runbook` phải được WIRED cùng một contract; không chấp nhận tình trạng code support nhưng preflight/unit/docs không biết worker thực sự chạy thế nào.
  *Rationale: Learning gần nhất của console đã chỉ ra secret/runtime drift giữa runtime và deploy artifact là wiring defect thực sự.*

- **D15** Backup/restore của operator-owned state phải preserve `notification_deliveries` và đủ metadata để queue/retry/failure history còn hiểu được sau restore; restore không được biến notification runtime thành “mất trí nhớ” trong khi các phần khác còn nguyên.
  *Rationale: User đã nêu backup/restore interaction với `notification_deliveries` như seam phải khóa.*

- **D16** Definition of done cho feature này là: operator có thể trên cùng host `enable hoặc disable Telegram` một cách explicit, chạy notification worker bằng command/service contract rõ ràng, quan sát queue health/degraded state, thực hiện test send và drain/retry workflow, survive restart/restore với persisted delivery state hợp lệ, và chứng minh notification failure không làm hỏng ingest/triage/dashboard/core readiness.
  *Rationale: Feature cần một acceptance target vận hành hoàn chỉnh thay vì danh sách module rời.*

### Agent's Discretion
- Planner có thể chọn tên command cụ thể, cấu trúc subcommand, polling interval, stale-queue heuristic, redrive UX, status payload shape, readiness field shape, và deploy artifact form miễn là tuân thủ D1-D16.
- Planner có thể quyết định worker chạy như sidecar systemd unit, explicit supervised loop khác, hoặc cả hai bề mặt `oneshot + long-running`, miễn ownership vẫn nằm ngoài web app request path theo D3-D5.
- Planner có thể chọn exact test matrix và observability fields miễn chúng đủ để chứng minh `EXISTS / SUBSTANTIVE / WIRED` cho runtime notification contract.

---

## Specific Ideas & References

- User framing: production gap lớn nhất còn lại của operator console là `explicit notification runtime entrypoint`, `dispatch ownership`, `queue observability`, `failure handling`, và `runbook` thay vì bản thân Telegram module.
- Review standard cho feature này phải là `EXISTS / SUBSTANTIVE / WIRED`, đặc biệt với manage CLI, worker/service loop, readiness/status, preflight, systemd, docs, và recoverability path.
- Existing repo direction từ v1 đã ngầm kỳ vọng Telegram delivery state là operator-owned local state, nhưng scout hiện tại cho thấy path này chưa được WIRED vào runtime/service flow thật.

---

## Existing Code Context

From the quick codebase scout during exploring.
Downstream agents: read these files before planning to avoid reinventing existing patterns.

### Reusable Assets
- `F:/Work/IDS_ML_New/scripts/ids_operator_console/notifications.py` — đã có Telegram queue/dispatch/retry/backoff logic và payload formatting; đây là domain core cần được runtime-wire, không phải viết lại từ đầu.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console/db.py` — đã có bảng `notification_deliveries` cùng persistence primitives cho pending/retry/sent/failed state và ingest offsets.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console/alerts.py` — đã khóa suppression + triage filtering cho candidate alerts được phép đi vào notification queue.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console/ingest.py` — đã có same-host JSONL ingest với persisted offsets và restart-safe import; đây là upstream seam thực tế của notification queue source.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console/config.py` — đã có Telegram config contract và paired-secret validation; planning cần mở rộng chứ không thay contract bừa.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console/health.py` — hiện dựng `/readyz` cho core console nhưng chưa có notification component; đây là seam chính cho observability hardening.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console/ops.py` — đã có smoke/backup/restore contract và là nơi tự nhiên để gắn verification cho notification runtime nếu cần.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console_manage.py` — hiện chỉ có `status/migrate/bootstrap-admin/backup/restore/prune-retention/smoke`; hoàn toàn thiếu notification operator surface.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console_server.py` — server entrypoint hiện đúng canonical app factory và không có notification worker loop; đây là bằng chứng rõ rằng Telegram chưa wired vào runtime path.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console_preflight.py` — đã validate Telegram config pairing nhưng chưa validate notification runtime ownership/entrypoint/deploy contract sâu hơn.
- `F:/Work/IDS_ML_New/deploy/systemd/ids-operator-console.service` — service unit hiện chỉ chạy web app + preflight; chưa có worker/dispatcher ownership surface dù env đã mang Telegram settings.
- `F:/Work/IDS_ML_New/tests/test_ids_operator_console_notifications.py` — chứng minh module-level queue/dispatch/retry behavior tồn tại nhưng chưa chứng minh runtime wiring.
- `F:/Work/IDS_ML_New/tests/test_ids_operator_console_ops.py` — chứng minh backup/restore/preflight/smoke baseline hiện có, là chỗ tự nhiên để thêm verification notification runtime contract.
- `F:/Work/IDS_ML_New/tests/test_ids_operator_console_web.py` — chứng minh readiness/dashboard baseline hiện có và cũng cho thấy notification health chưa hiện diện ở wired surface.

### Established Patterns
- Canonical app entrypoint pattern: runtime service phải chạy đúng app factory thật từ `web.py`, không tạo parallel runtime path ngầm.
- Verify-only runtime pattern: console startup production chỉ verify schema/bootstrap/config state; mutation và maintenance là explicit operator command.
- Same-host persisted-offset ingest pattern: operator console tiêu thụ durable JSONL outputs và lưu local state trong SQLite thay vì broker/distributed queue.
- Exact-path preflight + one-config-source pattern: deploy/systemd/preflight phải tiêu thụ cùng contract runtime, nhất là khi có secret hoặc optional subsystem.
- Exists/Substantive/Wired review pattern: module-level notification tests không đủ; cần chứng minh service/CLI/preflight/docs thực sự dùng path đó.

### Integration Points
- `F:/Work/IDS_ML_New/docs/ids_operator_console_architecture.md` — runtime contract hiện tại của console cần được mở rộng bằng notification ownership mà không phá same-host boundary.
- `F:/Work/IDS_ML_New/docs/ids_operator_console_operations.md` — runbook production hiện chưa có notification worker/drain/status/test-send contract rõ ràng.
- `F:/Work/IDS_ML_New/history/ids-operator-console-v1/CONTEXT.md` — boundary gốc của console, bao gồm Telegram là outbound channel đầu tiên nhưng không bắt buộc control plane.
- `F:/Work/IDS_ML_New/history/ids-operator-console-production-hardening/CONTEXT.md` — hardening trước đó đã khóa verify-only runtime, preflight, readiness, backup/restore; feature mới phải kế thừa và mở rộng đúng seam này.
- `F:/Work/IDS_ML_New/history/learnings/20260329-operator-console-production-hardening.md` — bắt buộc giữ runtime verification tách khỏi operator mutation/background work.
- `F:/Work/IDS_ML_New/history/learnings/20260328-operator-console-runtime-wiring.md` — cảnh báo trực tiếp rằng feature chỉ “có module” chưa đủ nếu entrypoint/deploy/runtime chưa wired thật.

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `F:/Work/IDS_ML_New/AGENTS.md` — workflow luật gốc, gate contract, và beads/bv/Agent Mail discipline cho repo này.
- `F:/Work/IDS_ML_New/.khuym/STATE.md` — trạng thái phase hiện tại; planning phải kế thừa đúng sau GATE 1.
- `F:/Work/IDS_ML_New/docs/ids_operator_console_architecture.md` — runtime/storage/deploy contract hiện tại của console.
- `F:/Work/IDS_ML_New/docs/ids_operator_console_operations.md` — operational runbook baseline của console cần được mở rộng cho notifications.
- `F:/Work/IDS_ML_New/docs/ids_live_sensor_architecture.md` — upstream producer boundary; notification hardening không được xâm lấn sensor runtime ownership.
- `F:/Work/IDS_ML_New/docs/ids_live_sensor_operations.md` — same-host service/preflight/journald patterns cần tái sử dụng.
- `F:/Work/IDS_ML_New/docs/final_model_bundle.md` — ví dụ gần nhất của explicit runtime contract + verify-only startup + operator mutation path.
- `F:/Work/IDS_ML_New/history/learnings/critical-patterns.md` — promoted learnings bắt buộc cho runtime/deploy/recovery features.
- `F:/Work/IDS_ML_New/history/learnings/20260328-operator-console-runtime-wiring.md` — mandatory lesson về runtime wiring và EXISTS/SUBSTANTIVE/WIRED.
- `F:/Work/IDS_ML_New/history/learnings/20260328-live-sensor-runtime-contracts.md` — daemon durability, restart, preflight, supervisor lessons áp dụng trực tiếp cho worker path.
- `F:/Work/IDS_ML_New/history/learnings/20260329-operator-console-production-hardening.md` — mandatory verify-only/runtime-vs-mutation lesson cho console.
- `F:/Work/IDS_ML_New/history/learnings/20260329-model-bundle-promotion-hardening.md` — pattern gần nhất về operator visibility, restore semantics, và same-host explicit lifecycle hardening.
- `F:/Work/IDS_ML_New/history/ids-operator-console-v1/CONTEXT.md` — locked boundary gốc của operator console, bao gồm Telegram-first outbound path.
- `F:/Work/IDS_ML_New/history/ids-operator-console-production-hardening/CONTEXT.md` — locked decisions của hardening phase trước mà feature này phải tôn trọng.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console/notifications.py` — existing notification domain logic needing runtime wiring.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console_manage.py` — operator CLI seam currently missing notification commands.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console_server.py` — canonical web runtime entrypoint whose boundary must stay clean.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console_preflight.py` — deployment gate that must consume the same notification contract shipped by runtime.
- `F:/Work/IDS_ML_New/deploy/systemd/ids-operator-console.service` — deploy artifact currently lacking notification worker ownership.

---

## Outstanding Questions

### Deferred to Planning
- [ ] Worker contract nên được đóng gói thành những subcommand cụ thể nào dưới `ids_operator_console_manage.py` để bao phủ `status`, `test-send`, `run-once/drain`, long-running loop, và redrive failed deliveries? — Planning cần thiết kế UX vận hành chi tiết nhưng không được vi phạm D12.
- [ ] Notification worker nên được deploy như sidecar `systemd` unit riêng, oneshot + timer, hay một service phụ có thể chạy loop liên tục từ cùng script quản lý? — Planning cần chọn form deploy nhỏ nhất vẫn production-real cho same-host.
- [ ] Notification health payload chính xác nên hiển thị ở `/readyz`, `status`, và journald ra sao để vừa actionable vừa non-gating theo D11? — Planning cần biến quyết định observability thành contract kiểm thử được.
- [ ] Disabled-mode “không tích backlog vô hạn” nên được hiện thực bằng skip-queue, short-circuit queueing, hay persisted disabled markers tối thiểu nào? — Planning cần chọn cơ chế cụ thể phù hợp với D8.
- [ ] Stale queue handling và redrive semantics nên dùng heuristic nào cho pending/retry/failed rows sau restart hoặc outage dài? — Planning cần thiết kế exact policy và test cases.
- [ ] Smoke/preflight verification nên chứng minh notification runtime đến mức nào khi Telegram enabled: chỉ contract local, test-send dry-run, hay worker run-once against injected sender? — Planning cần khóa verification slice đủ WIRED nhưng không phụ thuộc mạng ngoài.
- [ ] Backup/restore/runbook nên surfacing delivery history và post-restore expectations cho notification subsystem như thế nào để operator hiểu backlog nào còn actionable? — Planning cần hoàn thiện contract D15 thành procedure cụ thể.

---

## Deferred Ideas

- Multi-host notification routing hoặc separate notification control plane — deferred vì D1 khóa same-host operator-owned runtime.
- Channel abstraction hoặc plugin system cho multiple outbound providers — deferred vì D2 khóa Telegram-only hardening.
- UI-driven notification management/control plane trong dashboard — deferred vì feature này tập trung runtime/ops flow, không phải mở thêm control surface web-first.
- Replacing SQLite delivery state bằng broker/external queue — deferred vì cùng lúc tăng hạ tầng và phá same-host boundary hiện có.
- Notification cho anomaly/summaries hoặc incident aggregation — deferred vì feature hiện tại chỉ harden alert-driven Telegram path hiện có.

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions, code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1, D2...) are stable. Reference them by ID in all downstream artifacts.
