# IDS Operator Console Production Hardening - Context

**Feature slug:** ids-operator-console-production-hardening
**Date:** 2026-03-29
**Exploring session:** complete
**Scope:** Deep

---

## Feature Boundary

Feature này harden `ids_operator_console` từ baseline `ids-operator-console-v1` thành một same-host operator service đủ gần production cho triển khai thật phía sau reverse proxy, bằng cách bổ sung và khóa contract cho deploy an toàn, secret/config management, reverse proxy/TLS readiness, retention/backup/restore, migration/bootstrap safety, observability/health, smoke/UAT-ready operations, và safe same-host upgrade; feature này không mở rộng sang IPS/control-plane, multi-host fleet, hay public-edge app-managed TLS.

**Domain type(s):** SEE | CALL | RUN | READ | ORGANIZE

---

## Locked Decisions

These are fixed. Planning must implement them exactly. No creative reinterpretation.

### Production Topology
- **D1** Hardening phase này nhắm tới topology `same-host behind reverse proxy`; operator console tiếp tục bind như internal service và TLS terminate ở reverse proxy phía trước.
  *Rationale: Đây là con đường production thực tế nhất cho same-host FastAPI service, mở đường cho TLS/headers/cert rotation mà không kéo feature sang public-edge platform.*

- **D2** Feature này vẫn chỉ harden lớp operator console đã có; không mở rộng sang IPS/control-plane, không thêm remote sensor management, và không thiết kế multi-host fleet trừ khi planning chứng minh một integration point bắt buộc tối thiểu.
  *Rationale: User đã chốt rõ boundary là production hardening của console, không phải mở subsystem mới.*

### Backup, Retention, And Restore
- **D3** Hardening phải hỗ trợ backup/restore đầy đủ cho `operator console database + production config + secret references`, nhưng không cố snapshot toàn bộ upstream JSONL/raw sensor feed.
  *Rationale: Operator DB và deployment contract là state do console sở hữu; upstream JSONL vẫn là producer source of truth riêng.*

- **D4** Feature phải đưa ra retention policy có thể cấu hình cho operator-side data/artifacts và cleanup an toàn, gắn với backup/restore contract thay vì chỉ xóa dữ liệu ad hoc.
  *Rationale: Retention chỉ hữu ích nếu không phá backup/restore và không gây mất dữ liệu vận hành ngoài ý muốn.*

- **D14** Restore contract phải phân biệt rõ `secret references` với `secret material`: workflow backup/restore phải lưu và khôi phục metadata/path/config tham chiếu đến secret, còn secret value thực tế vẫn là input do operator tái cấp phát hoặc re-bind ngoài repo; hệ thống phải fail-closed nếu restore xong mà secret chưa được gắn lại hợp lệ.
  *Rationale: Điều này giữ được security posture của secret ngoài repo nhưng vẫn cho planning một contract restore rõ ràng, không phải tự đoán backup có chứa secret thật hay không.*

### Secrets And Config
- **D5** Non-secret production config đi qua env/config file; secret nhạy cảm đi qua secret file paths hoặc systemd credential-style paths. Repo chỉ chứa template/example chứ không chứa secret thật.
  *Rationale: Đây là contract ổn định hơn cho same-host Linux service, dễ preflight, rotate, audit, và tránh secret xuất hiện trực tiếp trong repo/unit mặc định.*

- **D6** Session/auth hardening phải đi cùng secret management production, bao gồm ít nhất việc loại bỏ default placeholder secret, làm rõ secure deployment expectations cho session secret/cookie posture phía sau reverse proxy, và kiểm tra misconfiguration fail-closed.
  *Rationale: V1 đã có auth/session, nhưng production hardening phải nâng contract vận hành thật của lớp đó chứ không chỉ giữ nguyên logic hiện hữu.*

### Migration, Bootstrap, And Upgrade Safety
- **D7** Startup production phải `fail-closed`: app chỉ verify schema/bootstrap state và báo actionable error nếu cần migrate; migration/upgrade là một bước explicit riêng của operator/admin.
  *Rationale: Tự động shape-change database trên startup làm tăng rủi ro rollout và rollback cho same-host production.*

- **D8** Feature phải hỗ trợ safe same-host upgrade path từ operator console v1 hiện có sang bản hardening mà không yêu cầu rebuild dữ liệu thủ công và không giả định install mới.
  *Rationale: User muốn tiến gần production thật sự cho người dùng hiện tại, nên upgrade path phải là contract chính thức của feature.*

- **D9** Fresh bootstrap cho install mới vẫn phải an toàn, nhưng không được hy sinh upgrade safety; planning phải coi `bootstrap mới` và `upgrade từ v1` đều là first-class paths.
  *Rationale: Một feature hardening chỉ an toàn cho install mới là chưa đủ giá trị production.*

### Operational Readiness
- **D10** Done criteria vận hành của feature bao gồm `smoke deploy checks + runbook production cơ bản + restore drill/verification thực tế`, không chỉ thêm endpoint health.
  *Rationale: Hardening phải có artifact để operator dùng thật, không chỉ code path nội bộ.*

- **D11** Reverse proxy/TLS readiness phải là readiness thật: app/proxy contract cần hỗ trợ headers, trusted deployment assumptions, callback/URL/session behavior phù hợp cho reverse-proxied HTTPS deployment, thay vì chỉ ghi chú “có thể đặt sau Nginx”.
  *Rationale: User đã ưu tiên rõ reverse proxy/TLS readiness như một khoảng trống production quan trọng.*

- **D12** Observability/health cho production phải phân biệt ít nhất giữa `service alive`, `app ready`, `schema/config/secret contract valid`, và `operator data path healthy enough for smoke/UAT`, thay vì một `/healthz` sống-chết đơn giản.
  *Rationale: Production operators cần thấy failure modes chẩn đoán được, không chỉ biết process còn chạy.*

- **D15** Definition of done cho feature này là: một deployment same-host phía sau reverse proxy có thể `bootstrap mới hoặc upgrade từ v1`, dùng non-placeholder secret/config contract, chạy explicit migration step khi cần, pass smoke deployment checks, và hoàn thành restore drill ở mức operator-owned artifacts mà không phải suy diễn thủ công các bước còn thiếu.
  *Rationale: Planning cần một acceptance target rõ ràng cho “production hardening” thay vì một danh sách cải tiến rời rạc.*

### Review And Verification Discipline
- **D13** Mọi downstream verification của feature này phải áp dụng kiểm tra `EXISTS / SUBSTANTIVE / WIRED`, đặc biệt với entrypoint, migration path, backup/restore path, smoke commands, và deployment artifacts.
  *Rationale: Learning mới nhất cho thấy artifact tồn tại không đủ; production hardening phải chứng minh wiring runtime thật.*

### Agent's Discretion
- Planner có thể chọn cơ chế cụ thể cho reverse proxy reference surface, backup file layout, retention windows, credential-loading API, migration command UX, readiness endpoint shapes, và smoke command form miễn là tuân thủ D1-D13.
- Planner có thể quyết định phần nào là CLI/script riêng, phần nào là app route/health endpoint, miễn production workflow cuối cùng rõ ràng, fail-closed, và kiểm chứng được.

---

## Specific Ideas & References

- User framing: feature mới phải đưa operator console tiến gần trạng thái production thật sự sau khi `ids-operator-console-v1` hoàn tất, thay vì lặp lại discovery của v1.
- Ưu tiên đã được user khóa: deploy an toàn, secret/config management, reverse proxy/TLS readiness, retention/backup/restore, migration/bootstrap safety, smoke/UAT-ready operations.
- Exploring chọn hướng mặc định “ổn định và tốt nhất” cho các option còn lại sau khi user cho phép agent tự khóa các quyết định tiếp theo mà không cần hỏi thêm.

---

## Existing Code Context

From the quick codebase scout during exploring.
Downstream agents: read these files before planning to avoid reinventing existing patterns.

### Reusable Assets
- `F:/Work/IDS_ML_New/scripts/ids_operator_console/config.py` - config loader hiện tại cho host/port/secret/database/input paths/templates/static; đây là điểm xuất phát trực tiếp cho production config contract.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console/db.py` - store bootstrap hiện tại và schema SQLite hiện hữu; mọi quyết định migration/backup/restore phải bám vào surface này.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console/web.py` - canonical FastAPI app factory hiện tại, route surface, session middleware, và health endpoint baseline.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console_server.py` - service entrypoint đã được sửa để chạy canonical app factory; đây là runtime seam quan trọng cho readiness/review.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console_preflight.py` - preflight exact-path contract hiện tại cho Python/app entrypoint/database/input/templates/static/secret/Telegram.
- `F:/Work/IDS_ML_New/deploy/systemd/ids-operator-console.service` - unit file baseline cho same-host deployment; hiện vẫn để placeholder secret trong environment và là target chính của hardening.
- `F:/Work/IDS_ML_New/tests/test_ids_operator_console_config.py` - regression baseline cho config/server wiring.
- `F:/Work/IDS_ML_New/tests/test_ids_operator_console_web.py` - route/auth/dashboard regression baseline cho combined console.

### Established Patterns
- Canonical app factory pattern: service entrypoint phải import và chạy app factory thật từ `web.py`, không dựng bootstrap app song song.
- Exact-path preflight pattern: Linux service trong repo dùng preflight kiểm tra exact runtime contract trước `ExecStart`.
- Same-host Python-native service pattern: `FastAPI + Jinja2 + sqlite3 + systemd` là baseline được chứng minh ở v1 và nên được harden thay vì thay stack.
- JSONL producer boundary pattern: operator console tiêu thụ output của sensor chứ không sở hữu upstream feed lifecycle.

### Integration Points
- `F:/Work/IDS_ML_New/docs/ids_operator_console_architecture.md` - runtime contract hiện tại của console, đặc biệt ingest/storage/notification/deployment boundaries.
- `F:/Work/IDS_ML_New/history/ids-operator-console-v1/CONTEXT.md` - boundary đã khóa ở v1; hardening phải kế thừa chứ không reset.
- `F:/Work/IDS_ML_New/history/ids-operator-console-v1/approach.md` - risk map và architectural choices của v1 làm baseline để xác định phần nào bây giờ phải productize thêm.
- `F:/Work/IDS_ML_New/history/ids-operator-console-v1/STATE-final.md` - xác nhận những gì v1 đã ship và những review issues đã được sửa.
- `F:/Work/IDS_ML_New/history/learnings/20260328-operator-console-runtime-wiring.md` - learning bắt buộc về canonical app factory và `EXISTS / SUBSTANTIVE / WIRED`.

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `F:/Work/IDS_ML_New/history/ids-operator-console-v1/CONTEXT.md` - locked product and architecture boundary from v1 that this feature hardens.
- `F:/Work/IDS_ML_New/history/ids-operator-console-v1/approach.md` - baseline implementation strategy and original v1 risk map.
- `F:/Work/IDS_ML_New/history/ids-operator-console-v1/STATE-final.md` - shipped scope, verification baseline, and review closure for v1.
- `F:/Work/IDS_ML_New/history/learnings/critical-patterns.md` - promoted mandatory learnings for validation, deployment safety, and runtime wiring.
- `F:/Work/IDS_ML_New/history/learnings/20260328-operator-console-runtime-wiring.md` - detailed operator-console-specific runtime wiring and review lesson.
- `F:/Work/IDS_ML_New/docs/ids_operator_console_architecture.md` - current runtime/storage/deployment contract of the operator console.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console_server.py` - canonical entrypoint seam that must stay wired.
- `F:/Work/IDS_ML_New/scripts/ids_operator_console_preflight.py` - current preflight seam likely to be expanded for production hardening.
- `F:/Work/IDS_ML_New/deploy/systemd/ids-operator-console.service` - deployment surface to harden for production.

---

## Outstanding Questions

### Deferred to Planning
- [ ] Reverse proxy reference target nên ưu tiên artifact cụ thể nào (`nginx`, `caddy`, hay proxy-agnostic contract + one example`) để vừa production-real vừa không nở scope quá lớn? - Planning cần chọn surface nhỏ nhất vẫn đủ actionable cho deployment thật.
- [ ] Secret file loading nên đi qua env chứa path, systemd `LoadCredential`, hay hỗn hợp cả hai? - Planning cần chọn contract cụ thể phù hợp với repo và testability.
- [ ] Retention policy nên áp dụng cho những bảng/artifact nào, với default windows nào, và cleanup chạy theo cơ chế nào? - Planning cần xác định data classes, blast radius, và operator ergonomics.
- [ ] Backup artifact format và restore workflow nên được đóng gói thành script/CLI nào để vừa hỗ trợ automation vừa fail-closed? - Planning cần thiết kế concrete workflow và acceptance checks.
- [ ] Migration command surface nên nằm ở script riêng, app-admin CLI, hay preflight companion command? - Planning cần chọn UX triển khai rõ ràng cho upgrade path.
- [ ] Readiness/health model nên gồm những endpoint hoặc smoke primitives nào để chứng minh `alive`, `ready`, `migration needed`, `secret/config invalid`, và `data path degraded`? - Planning cần biến D10-D12 thành contract kiểm thử được.
- [ ] Restore drill tối thiểu nên chứng minh những artifact nào được khôi phục thành công trên same-host deployment? - Planning cần chốt verification slice đủ thực tế nhưng không quá nặng.

---

## Deferred Ideas

- App-managed public TLS termination - deferred vì D1 đã khóa TLS ở reverse proxy.
- Multi-host / fleet-aware operator console deployment - deferred vì feature này chỉ harden same-host production topology.
- IPS / control-plane actions từ UI hoặc API - deferred vì boundary vẫn là IDS operator console.
- Snapshot/full backup upstream JSONL or raw sensor feed - deferred vì upstream vẫn là producer-owned source of truth riêng.
- External database / HA deployment / clustered console - deferred vì không cần cho hardening phase hiện tại.

---

## Handoff Note

CONTEXT.md is the single source of truth for this feature.

- **planning** reads: locked decisions, code context, canonical refs, deferred-to-planning questions
- **validating** reads: locked decisions (to verify plan-checker coverage)
- **reviewing** reads: locked decisions (for UAT verification)

Decision IDs (D1, D2...) are stable. Reference them by ID in all downstream artifacts.
