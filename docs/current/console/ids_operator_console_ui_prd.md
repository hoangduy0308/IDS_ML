# PRD — Thiết Kế Giao Diện IDS Operator Console

## 1. Mục tiêu tài liệu

Tài liệu này chốt yêu cầu sản phẩm và yêu cầu thiết kế giao diện cho bề mặt web hiện có của hệ thống IDS trong repo này.
Phạm vi bám theo code hiện tại, không giả định một control plane lớn hơn những gì hệ thống đang sở hữu.

Kết luận quan trọng từ codebase:

- Web surface hiện tại là `ids.console.web:create_operator_console_web_app`
- Đây là same-host operator console, ưu tiên quan sát và triage
- Các tác vụ mutate hạ tầng như `promote`, `rollback`, `restore`, `recover`, `migrate` vẫn là CLI/ops surface
- Legacy route compatibility vẫn tồn tại qua redirect:
  - `/dashboard -> /overview`
  - `/anomalies -> /operations`

## 2. Bối cảnh hiện tại

Hệ thống hiện đã có đầy đủ nền cho một console vận hành:

- Auth session-based với login/logout và CSRF cho form action
- Các màn hình Jinja server-rendered:
  - `Login`
  - `Overview`
  - `Alerts`
  - `Alert Detail`
  - `Operations`
  - `Reports`
- Dữ liệu runtime đã có sẵn:
  - `alerts`
  - `anomalies`
  - `summaries`
  - `readiness payload`
  - `active bundle visibility`
  - `notification state`

Điểm rất quan trọng của domain:

- `alert` là tín hiệu nghi ngờ tấn công cần analyst xử lý
- `anomaly` là tín hiệu vận hành/data-path cần operator chẩn đoán
- Hai lane này phải luôn được tách bạch trong IA lẫn visual hierarchy

## 3. Tuyên bố sản phẩm

IDS Operator Console là giao diện điều hành cho một IDS chạy trên cùng một máy, giúp operator:

- quét nhanh tải cảnh báo
- đi vào đọc sâu từng cảnh báo
- phân biệt lỗi vận hành với tín hiệu tấn công
- theo dõi tình trạng readiness, bundle đang active, và lịch sử summary

Nó không phải là:

- fleet manager đa host
- SIEM portal
- công cụ IPS / active response
- giao diện để start/stop service hay promote model trực tiếp trong phase này

## 4. Personas

### 4.1 Security Analyst

Mục tiêu:

- đọc nhanh hàng đợi cảnh báo
- cập nhật trạng thái triage
- để lại ghi chú điều tra
- mở chi tiết đúng lúc, không bị chìm trong noise vận hành

### 4.2 System Operator

Mục tiêu:

- biết console có thực sự ready không
- biết data-path, notification, schema, admin bootstrap đang ở trạng thái nào
- biết bundle nào đang active và còn tương thích hay không
- đọc anomaly lane mà không làm loãng workflow analyst

### 4.3 Same-host Owner / Admin

Mục tiêu:

- xác nhận hệ thống đang chạy đúng contract
- xem đủ visibility để quyết định quay ra CLI ops nếu cần
- không cần web UI phải gánh hết trách nhiệm vận hành sâu

## 5. Mục tiêu sản phẩm

### 5.1 Product goals

- Giảm thời gian từ lúc mở console tới lúc hiểu được "nên vào lane nào".
- Làm cho `Overview` trở thành màn quyết định đầu tiên, không chỉ là dashboard trang trí.
- Giữ `Alerts` là lane làm việc chính cho analyst.
- Giữ `Operations` là lane riêng cho readiness và anomaly.
- Làm `Reports` đủ hữu ích cho đọc lịch sử và đối soát, nhưng không biến thành BI tool nặng chart.
- Tăng độ dễ đọc của active bundle, readiness, notification health trong mọi trạng thái `ok`, `disabled`, `degraded`, `no-data`.

### 5.2 Non-goals

- Không thêm model promotion / rollback UI trong phase 1.
- Không thêm service restart / recovery UI trong phase 1.
- Không thiết kế đa tenant hoặc đa organization.
- Không chuyển console sang SPA trước khi server-rendered flow hiện tại được tối ưu rõ ràng.

## 6. Nguyên tắc thiết kế

### 6.1 Domain-first hierarchy

Ưu tiên cấu trúc theo nghiệp vụ thật:

- `Attack signal lane`
- `Operational anomaly lane`
- `System readiness lane`
- `Historical report lane`

Không tổ chức theo kiểu "dashboard chung chung".

### 6.2 Read fast, drill deep later

Mọi màn chính phải hỗ trợ:

- 5 giây đầu: hiểu tình trạng
- 30 giây tiếp: xác định ưu tiên
- sau đó mới drill-down vào record cụ thể

### 6.3 Separate visibility from mutation

Giao diện được phép cho thấy:

- active bundle
- notification health
- runtime/console posture

Nhưng phase 1 chưa được giả vờ là web control plane cho các hành động ops nhạy cảm.

### 6.4 Light-mode operational clarity

Console hiện tại đã đi theo hướng light-first, precision-lab, table-first. PRD giữ hướng này:

- không dùng dark SOC cliché
- không lạm dụng chart
- không biến layout thành "AI dashboard" generic

## 7. Information Architecture

### 7.1 Primary navigation

Giữ 4 mục chính:

1. `Overview`
2. `Alerts`
3. `Operations`
4. `Reports`

### 7.2 Page roles

- `Overview`: decision hub
- `Alerts`: primary triage queue
- `Alert Detail`: investigation workspace
- `Operations`: runtime/anomaly diagnosis
- `Reports`: historical and rollup reading

### 7.3 Secondary system surfaces

Không đặt vào primary nav của phase 1:

- login state
- readiness JSON
- health JSON
- CLI-only ops workflows

### 7.4 Route contract cần giữ ổn định

Route HTML hiện có:

- `/login`
- `/overview`
- `/alerts`
- `/alerts/{alert_id}`
- `/operations`
- `/reports`

Route JSON hiện có:

- `/healthz`
- `/readyz`
- `/api/v1/console/snapshot`
- `/api/v1/alerts`
- `/api/v1/anomalies`
- `/api/v1/summaries`

Legacy redirect cần tiếp tục hoạt động:

- `/dashboard -> /overview`
- `/anomalies -> /operations`

## 8. Yêu cầu màn hình

### 8.1 Login

Vai trò:

- cổng vào duy nhất cho console

Yêu cầu:

- form tối giản, dễ đọc
- hiển thị rõ đây là bề mặt "đọc / triage / báo cáo"
- thông báo lỗi đăng nhập rõ ràng nhưng kín đáo
- không thêm nội dung marketing hoặc minh họa thừa

Trạng thái:

- default
- invalid credentials

### 8.2 Overview

Vai trò:

- màn quyết định đầu tiên sau login

Yêu cầu bắt buộc:

- hero tóm tắt ba câu hỏi:
  - hệ thống có ready không
  - tải alert hiện ra sao
  - có anomaly vận hành nào cần tách riêng không
- 4 metric-card tối thiểu:
  - queue alert
  - need-attention count
  - anomaly count
  - active bundle
- khối `priority alert snapshot`
- khối `runtime health snapshot`
- khối `readiness component matrix`
- preview anomaly table ở cuối trang

Yêu cầu trải nghiệm:

- người dùng phải nhìn ra ngay đường rẽ:
  - vào `Alerts` nếu trọng tâm là triage
  - vào `Operations` nếu trọng tâm là runtime

### 8.3 Alerts

Vai trò:

- work queue chính cho analyst

Yêu cầu bắt buộc:

- filter theo `triage_status`
- giữ suppressed rows hiển thị được trong queue mặc định, không làm chúng biến mất âm thầm
- hiển thị suppression ngay trong danh sách
- badge cho severity và triage status
- card/list density đủ dày để quét nhanh
- side panel tóm tắt phân bố queue và context runtime song song

Yêu cầu cải tiến trong redesign:

- thêm quick filter chips thay cho chỉ một dropdown
- cho phép đổi density `comfortable / compact`
- sticky filter bar trên desktop
- sort mặc định theo urgency/time, không tạo cảm giác ngẫu nhiên

### 8.4 Alert Detail

Vai trò:

- không gian điều tra của từng alert

Yêu cầu bắt buộc:

- giữ rõ raw identifiers:
  - source event id
  - timestamp
  - src/dst IP
  - protocol / ports
  - score
  - fingerprint
  - sensor id
- thao tác inline:
  - cập nhật triage status
  - thêm investigation note
- lịch sử song song:
  - timeline status history
  - note timeline

Yêu cầu UX:

- phần context alert phải nằm trên fold đầu
- phần action phải đủ gần context, không tách quá xa
- timeline phải đọc được theo chiều dọc, không cần mental jump

### 8.5 Operations

Vai trò:

- lane riêng cho anomaly và readiness

Yêu cầu bắt buộc:

- table anomaly rõ ràng, ưu tiên reading
- xử lý tốt 3 trạng thái:
  - `no-data`
  - `degraded but no anomaly rows`
  - `clean`
- side panel riêng cho:
  - health snapshot
  - component readiness
- không thêm inline mutate action cho service/model lifecycle trong phase này

Yêu cầu thiết kế:

- visually distinct khỏi `Alerts`
- không dùng cùng nhịp màu/nhấn với lane triage để tránh lẫn domain

### 8.6 Reports

Vai trò:

- màn lịch sử và rollup đọc được

Yêu cầu bắt buộc:

- top rollup summary
- bảng recent summaries
- rollup by triage status
- rollup by severity
- anomaly history table

Yêu cầu trải nghiệm:

- table-first, chart-second
- nếu có chart ở phase sau, chart chỉ để bổ trợ xu hướng, không thay bảng
- màn này phải hữu ích cho đối soát vận hành và backup/restore verification

## 9. Data requirements theo code hiện tại

### 9.1 Alert fields phải có khả năng hiển thị

- `id`
- `sensor_id`
- `source_event_id`
- `event_ts`
- `severity`
- `triage_status`
- `suppressed`
- `src_ip`
- `dst_ip`
- `src_port`
- `dst_port`
- `protocol`
- `fingerprint`
- `payload.score`

### 9.2 Anomaly fields phải có khả năng hiển thị

- `id`
- `anomaly_type`
- `reason`
- `redacted_summary`
- `event_ts`
- `sensor_id`

### 9.3 Summary / readiness / bundle fields phải có khả năng hiển thị

- `summary_ts`
- `alert_count`
- `anomaly_count`
- `window_seconds`
- `active_bundle.active_bundle_name`
- `active_bundle.compatibility_status`
- `active_bundle.previous_bundle_name`
- `components.schema.state`
- `components.admin_bootstrap.admin_count`
- `components.data_paths.ok`
- `components.notification.state`
- `components.notification.failed_count`

Lưu ý:

- `active_bundle` là summary-backed visibility; có thể vắng mặt nếu hệ thống chưa ingest được summary phù hợp
- một phần field có thể là optional và UI phải có empty/degraded copy tương ứng thay vì giả định luôn có dữ liệu

## 10. Trạng thái hệ thống cần được thiết kế rõ

PRD yêu cầu mọi màn chính xử lý được các trạng thái:

- `ok`
- `degraded`
- `disabled`
- `no-data`
- `misconfigured`
- `unknown`

Nguyên tắc:

- không chỉ đổi màu
- phải đổi cả copy, icon/state label, và hành động kế tiếp được gợi ý

Ví dụ:

- `notification = disabled`: trạng thái hợp lệ, không dùng tone lỗi
- `notification = degraded`: hiển thị như một domain suy giảm thật
- `ready = false` nhưng `alerts = 0`: vẫn phải cho thấy đây là lỗi readiness, không phải yên ổn

## 11. Visual direction

### 11.1 Brand and mood

Định hướng visual:

- precision lab
- same-host operational workspace
- calm, exact, table-centric
- tin cậy hơn flashy

### 11.2 Typography

- Giữ hướng `Be Vietnam Pro` cho body/headline
- Giữ `JetBrains Mono` cho metadata, id, badge, timestamp, technical labels
- Headlines phải chắc và ngắn, tránh văn phong marketing

### 11.3 Color system

Giữ light-first palette, tinh chỉnh quanh 4 nhóm:

- neutral paper / shell
- accent teal cho hệ thống
- green cho trạng thái healthy/resolved
- amber/red cho degraded và danger

Không dùng:

- purple SaaS gradient
- dark neon security theme
- saturation quá mạnh ở màn đọc bảng

### 11.4 Layout

- desktop-first vì operator shell hiện tại ưu tiên desktop
- sidebar + sticky utility bar tiếp tục là cấu trúc đúng
- content area dùng module `hero -> workspace -> detail/report blocks`
- tables và lists phải đọc tốt ở 1280px trở lên

### 11.5 Motion

- chỉ dùng motion nhẹ: fade-up, drawer transition, loading sheen
- không dùng animation liên tục trong lane cảnh báo
- `prefers-reduced-motion` phải được giữ

## 12. Responsive requirements

### 12.1 Desktop

- trải nghiệm chuẩn cho operator
- sidebar sticky
- utility bar sticky
- split layout cho list/detail panels

### 12.2 Tablet

- hero và side panels stack lại
- filter/actions vẫn giữ được gần content chính

### 12.3 Mobile

- drawer nav hoạt động tốt
- bảng dài cần có chiến lược co hẹp hoặc chuyển card/table hybrid
- alert detail form không được quá dài và đẩy timeline xuống vô tận

Lưu ý:

- mobile là supported, nhưng không phải primary usage mode

## 13. Accessibility requirements

- keyboard navigation đầy đủ
- focus states rõ
- màu trạng thái không là tín hiệu duy nhất
- table headers và labels semantic
- form error dễ hiểu
- badge/status copy phải đọc được với screen reader

## 14. Functional opportunities cho phase sau

Các khả năng này có cơ sở từ code, nhưng chưa nên đưa vào phase 1:

- sensor selector trong UI
  - vì JSON API hiện đã nhận `sensor_id`
- notification diagnostics panel sâu hơn
- active bundle detail drawer
- report export action
- read-only stack health page tổng hợp nhiều domain hơn

Các khả năng này chưa nên làm trên web ở giai đoạn này:

- promote / rollback bundle
- service restart / recover
- migrate / bootstrap admin
- restore execution

## 15. Success metrics

### 15.1 UX metrics

- giảm thời gian tìm alert cần xử lý đầu tiên
- giảm số lần nhảy sai giữa `Alerts` và `Operations`
- tăng tốc độ đọc trạng thái readiness/bundle trên `Overview`

### 15.2 Product metrics

- tỷ lệ alert được triage từ queue mà không cần rời flow
- tỷ lệ anomaly vận hành được xem ở `Operations` thay vì bị lẫn ở queue alert
- thời gian xác nhận active bundle sau deploy/restore

### 15.3 Engineering metrics

- redesign không làm thay đổi contract của route hiện có
- giữ tương thích với auth/session/CSRF hiện hữu
- không yêu cầu backend rewrite để ship phase 1
- không làm mất legacy redirect contract đã được test

## 16. Phạm vi triển khai đề xuất

### Phase 1 — Visual and IA hardening on existing backend

- redesign `Login`
- redesign `Overview`
- redesign `Alerts`
- redesign `Alert Detail`
- redesign `Operations`
- redesign `Reports`
- chuẩn hóa status system, spacing, table readability, responsive behavior

Không yêu cầu:

- route mới
- database schema mới
- ops mutation qua web

### Phase 2 — Read-only power features

- sensor switcher
- richer summary trend modules
- bundle detail panel
- notification diagnostics panel

### Phase 3 — Carefully selected operator actions

Chỉ xem xét sau khi phase 1 và 2 ổn định, và phải đánh giá lại boundary bảo mật:

- read-only deep links sang ops commands/runbooks
- bulk triage affordances chỉ khi backend contract tương ứng được thiết kế rõ ràng

## 17. Quyết định cuối cùng

PRD này chốt rằng giao diện cần phục vụ đúng bản chất của hệ thống hiện tại:

- một IDS same-host
- một operator console visibility-first
- tách rõ analyst lane và operations lane
- làm mạnh phần đọc, triage, readiness, bundle visibility
- không giả lập một control plane mà codebase hiện chưa chủ đích cung cấp trên web
