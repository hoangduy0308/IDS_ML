# IDS Operator Console UI Surface Spec

## 1. Mục tiêu tài liệu

Tài liệu này đặc tả chi tiết bề mặt UI hiện có của IDS Operator Console ở mức đủ dùng cho:

- thiết kế UI chi tiết
- implement frontend/server-rendered templates
- tích hợp API cùng session auth hiện tại
- kiểm tra phạm vi dữ liệu được phép hiển thị

Tài liệu này không thay thế PRD. Nó là contract thực thi bám theo code hiện tại.

Nguồn sự thật chính:

- [web.py](F:\Work\IDS_ML_New\ids\console\web.py)
- [health.py](F:\Work\IDS_ML_New\ids\console\health.py)
- [alerts.py](F:\Work\IDS_ML_New\ids\console\alerts.py)
- [reporting.py](F:\Work\IDS_ML_New\ids\console\reporting.py)
- [db.py](F:\Work\IDS_ML_New\ids\console\db.py)
- [auth.py](F:\Work\IDS_ML_New\ids\console\auth.py)

## 2. Boundary của surface

### 2.1 Surface này là gì

Đây là operator console chạy cùng host với IDS runtime, chịu trách nhiệm:

- hiển thị queue cảnh báo
- hiển thị anomaly vận hành
- hiển thị readiness và active bundle visibility
- hỗ trợ triage status update và investigation note
- hỗ trợ đọc report/summary lịch sử

### 2.2 Surface này không phải gì

Không thuộc phạm vi web UI hiện tại:

- promote bundle
- rollback bundle
- restart service
- recover stack
- migrate schema
- bootstrap admin
- restore backup

Các tác vụ trên vẫn là CLI/ops boundary.

## 3. Kiến trúc giao diện hiện tại

### 3.1 Rendering model

- FastAPI + Jinja2
- session-based auth qua `SessionMiddleware`
- static assets từ `/static`
- light-mode desktop-first shell

### 3.2 Navigation chính

- `/overview`
- `/alerts`
- `/operations`
- `/reports`

### 3.3 Compatibility routes

- `/dashboard` redirect `303` sang `/overview`
- `/anomalies` redirect `303` sang `/operations`

UI redesign phải giữ compatibility này.

## 4. Auth và quyền truy cập

### 4.1 HTML routes

Các route HTML yêu cầu đăng nhập. Nếu chưa đăng nhập:

- trả về `303 See Other`
- redirect sang `/login`

Áp dụng cho:

- `/`
- `/overview`
- `/dashboard`
- `/alerts`
- `/alerts/{alert_id}`
- `/operations`
- `/anomalies`
- `/reports`

### 4.2 JSON routes

Các route JSON yêu cầu session auth. Nếu chưa đăng nhập:

- trả về `401`
- payload lỗi: `{"detail":"Authentication required"}`

Áp dụng cho:

- `/api/v1/console/snapshot`
- `/api/v1/alerts`
- `/api/v1/anomalies`
- `/api/v1/summaries`

### 4.3 Form mutation routes

Các route mutate bằng form bắt buộc:

- user đã đăng nhập
- có `csrf_token` hợp lệ

Áp dụng cho:

- `POST /logout`
- `POST /alerts/{alert_id}/notes`
- `POST /alerts/{alert_id}/status`

### 4.4 Session info sẵn có cho UI

Nếu đã đăng nhập, template có thể dùng:

- `admin.username`
- `admin.csrf_token`

## 5. Route inventory chi tiết

## 5.1 `GET /login`

Mục đích:

- render trang đăng nhập

Response:

- `200` nếu chưa đăng nhập
- `303 -> /overview` nếu đã đăng nhập

Template:

- `login.html`

Context:

- `login_error`

## 5.2 `POST /login`

Mục đích:

- xác thực admin bằng username/password

Form fields:

- `username`
- `password`

Response:

- `303 -> /overview` khi thành công
- `200` render lại `login.html` khi sai thông tin

UI message lỗi hiện có:

- `Tên đăng nhập hoặc mật khẩu không đúng.`

## 5.3 `POST /logout`

Mục đích:

- xóa session hiện tại

Form fields:

- `csrf_token`

Response:

- `303 -> /login`

## 5.4 `GET /overview`

Mục đích:

- decision hub sau login

Data source:

- `alerts = list_alerts_for_triage(include_suppressed=True, limit=8)`
- `anomalies = list_anomalies(limit=100)` rồi decode payload
- `summaries = list_recent_summaries(limit=30)` rồi decode payload
- `health = _prepare_health_snapshot(summaries)`
- `readiness = build_readiness_payload(include_sensitive=True)`

Template:

- `overview.html`

UI obligations:

- hiển thị alert pressure
- hiển thị runtime health snapshot
- hiển thị readiness components
- hiển thị preview anomaly lane
- hiển thị active bundle nếu summary payload có block này

## 5.5 `GET /alerts`

Mục đích:

- primary triage queue

Query params:

- `status_filter: str | None`

Validation:

- nếu `status_filter` không thuộc triage state hợp lệ thì trả `400`

Data source:

- `alerts = list_alerts_for_triage(triage_status=status_filter, include_suppressed=True, limit=200)`
- `summaries = list_recent_summaries(limit=30)`
- `health = _prepare_health_snapshot(summaries)`
- `readiness = build_readiness_payload(include_sensitive=True)`

Template:

- `alerts.html`

Queue family contract:

- `Family Signal` stays compact and table-first.
- `known` renders as `known family` plus the family label.
- `unknown` renders as `unknown family` plus a short attack/no-family note.
- `legacy_unavailable` renders as `family unavailable` plus a legacy note.
- `benign` stays neutral with a dash and no attack-family label.

UI obligations:

- hiển thị full queue sau filter
- suppressed rows vẫn có thể nhìn thấy
- severity và triage status phải hiện cùng nhau
- runtime context phải được hiển thị kề queue

## 5.6 `GET /alerts/{alert_id}`

Mục đích:

- investigation workspace cho một alert

Data source:

- `_find_alert(store, alert_id)`
- `timeline = get_alert_timeline(alert_id)`

Template:

- `alert_detail.html`

Error behavior:

- `404` nếu không tìm thấy alert

UI obligations:

- hiển thị raw alert context
- hiển thị status history
- hiển thị note history
- cho phép update status và thêm note

## 5.7 `POST /alerts/{alert_id}/notes`

Mục đích:

- thêm note điều tra

Form fields:

- `note_text`
- `csrf_token`

Auth:

- yêu cầu session auth + CSRF

Response:

- `303 -> /alerts/{alert_id}`

Data effect:

- insert vào `alert_notes`

Validation notes:

- `note_text` không được blank

## 5.8 `POST /alerts/{alert_id}/status`

Mục đích:

- cập nhật triage status

Form fields:

- `to_status`
- `csrf_token`

Auth:

- yêu cầu session auth + CSRF

Response:

- `303 -> /alerts/{alert_id}`

Data effect:

- update `alerts.triage_status`
- insert vào `alert_status_history`

Validation notes:

- `to_status` phải thuộc tập triage state hợp lệ

## 5.9 `GET /operations`

Mục đích:

- runtime/anomaly diagnosis lane

Data source:

- `anomalies = list_anomalies(limit=200)` rồi decode payload
- `summaries = list_recent_summaries(limit=30)` rồi decode payload
- `health = _prepare_health_snapshot(summaries)`
- `readiness = build_readiness_payload(include_sensitive=True)`

Template:

- `operations.html`

UI obligations:

- anomaly table rõ ràng
- tách biệt khỏi attack queue
- thể hiện readiness và health song song

## 5.10 `GET /reports`

Mục đích:

- historical rollup surface

Data source:

- `build_report_bundle(alert_limit=200, anomaly_limit=100, summary_limit=100, include_suppressed_alerts=True)`
- `build_report_rollup(report_bundle)`

Template:

- `reports.html`

UI obligations:

- recent summaries
- rollup theo status
- rollup theo severity
- anomaly history

## 5.11 `GET /healthz`

Mục đích:

- lightweight liveness

Behavior:

- luôn trả `200`

Unauthenticated payload:

```json
{
  "status": "ok",
  "service": "ids-operator-console"
}
```

Authenticated payload thêm:

- `environment`
- `database_path`

UI use:

- không phải primary UI page
- có thể dùng cho diagnostics/read-only meta panel nếu cần

## 5.12 `GET /readyz`

Mục đích:

- readiness có component breakdown

Status code:

- `200` nếu `payload.ready == true`
- `503` nếu `payload.ready == false`

Unauthenticated payload:

```json
{
  "status": "ok|degraded",
  "ready": true|false,
  "service": "ids-operator-console"
}
```

Authenticated payload thêm:

- `environment`
- `proxy`
- `components`

UI use:

- là nguồn readiness chính cho component matrix nếu cần fetch client-side
- hoặc dữ liệu nền cho server-rendered `Overview` và `Operations`

## 5.13 `GET /api/v1/console/snapshot`

Mục đích:

- trả gộp alert/anomaly/summary theo `sensor_id`

Query params:

- `sensor_id` default `sensor-local`
- `include_suppressed` default `false`

Response shape:

```json
{
  "sensor_id": "sensor-local",
  "alerts": [],
  "anomalies": [],
  "summaries": []
}
```

Limits nội bộ:

- alerts `500`
- anomalies `500`
- summaries `200`

UI use:

- phù hợp cho future sensor switcher hoặc client-side refresh nhẹ

## 5.14 `GET /api/v1/alerts`

Query params:

- `sensor_id` default `sensor-local`
- `triage_status` optional
- `include_suppressed` default `true`

Response shape:

```json
{
  "sensor_id": "sensor-local",
  "alerts": []
}
```

Limit nội bộ:

- `500`

## 5.15 `GET /api/v1/anomalies`

Query params:

- `sensor_id` default `sensor-local`

Response shape:

```json
{
  "sensor_id": "sensor-local",
  "anomalies": []
}
```

Limit nội bộ:

- `500`

## 5.16 `GET /api/v1/summaries`

Query params:

- `sensor_id` default `sensor-local`

Response shape:

```json
{
  "sensor_id": "sensor-local",
  "summaries": []
}
```

Limit nội bộ:

- `300`

## 6. Tập trạng thái hợp lệ

### 6.1 Alert triage states

Chỉ có 5 trạng thái hợp lệ:

- `new`
- `acknowledged`
- `investigating`
- `resolved`
- `false_positive`

Mọi UI control cập nhật status phải khóa theo đúng tập này.

### 6.2 Notification states

Notification component có thể ở các trạng thái:

- `disabled`
- `ok`
- `degraded`
- `misconfigured`

Lưu ý:

- `disabled` là trạng thái hợp lệ, không phải lỗi
- `degraded` không tự động làm `ready=false`

### 6.3 High-level service states

UI hiện đang dùng hoặc có thể gặp:

- `ok`
- `degraded`
- `no-data`
- `unknown`
- `compatible`
- `current`
- `active`
- `none`

Không được hardcode giả định rằng chỉ có `ok` và `degraded`.

## 7. Data model chi tiết cho UI

## 7.1 Alert row

Nguồn:

- bảng `alerts`
- payload decode từ `payload_json`
- suppression tính động từ `suppression_rules`

Fields có thể hiển thị:

- `id: int`
- `sensor_id: str`
- `source_event_id: str | null`
- `event_ts: str`
- `severity: str | null`
- `src_ip: str | null`
- `dst_ip: str | null`
- `src_port: int | null`
- `dst_port: int | null`
- `protocol: str | null`
- `fingerprint: str | null`
- `triage_status: str`
- `triage_updated_at: str`
- `suppressed: bool`
- `payload: object`

Payload fields UI hiện đã dùng hoặc nên ưu tiên:

- `score`
- `protocol`
- `src_ip`
- `event_type`

Notes:

- suppression không làm thay đổi record gốc trong DB
- suppressed row có thể bị ẩn hoặc hiện tùy endpoint/flag

Family fields:

- `family.family_state: known | unknown | benign | legacy_unavailable`
- `family.attack_family: str | null`
- `family.attack_family_confidence: float | null`
- `family.attack_family_margin: float | null`

## 7.2 Alert detail timeline

### Status history item

- `id`
- `alert_id`
- `from_status`
- `to_status`
- `changed_by`
- `changed_at`

### Note item

- `id`
- `alert_id`
- `note_text`
- `author`
- `created_at`

UI ordering hiện tại:

- mới nhất trước

## 7.3 Anomaly row

Nguồn:

- bảng `anomalies`

Fields:

- `id: int`
- `sensor_id: str`
- `source_event_id: str | null`
- `event_ts: str`
- `anomaly_type: str`
- `reason: str | null`
- `redacted_summary: str | null`
- `payload_json` decode được nếu cần

UI hiện đang ưu tiên:

- `anomaly_type`
- `reason`
- `redacted_summary`
- `event_ts`

## 7.4 Summary row

Nguồn:

- bảng `summaries`

Fields:

- `id`
- `sensor_id`
- `summary_ts`
- `payload`

Payload fields đã được hệ thống kỳ vọng:

- `window_seconds`
- `alert_count`
- `anomaly_count`
- `active_bundle`

### `active_bundle` block

Các field đã xuất hiện trong tests/docs:

- `active_bundle_name`
- `compatibility_status`
- `activated_at`
- `previous_bundle_name`

Quan trọng:

- active bundle visibility là summary-backed
- có thể `null` hoặc không tồn tại nếu chưa ingest summary thích hợp

## 7.5 Readiness payload

Top-level:

- `status`
- `ready`
- `service`

Authenticated payload thêm:

- `environment`
- `proxy`
- `components`

### Proxy block

- `public_base_url`
- `root_path`
- `forwarded_allow_ips`

### Components block

#### `config`

- `ok`
- `session_cookie_https_only`
- `session_cookie_same_site`
- `secret_source`

#### `schema`

- `ok`
- `state`
- `version`
- `detail`

#### `admin_bootstrap`

- `ok`
- `admin_count`

#### `data_paths`

- `ok`
- `streams.alerts`
- `streams.quarantine`
- `streams.summary`

Mỗi stream path có:

- `path`
- `exists`
- `readable`
- `parent_exists`
- `parent_readable`

#### `active_bundle`

- `ok`
- `state`

#### `notification`

- `ok`
- `state`
- `enabled`
- `configured`
- `channel`
- `target` hoặc `null`
- `backlog`
- `pending_count`
- `retry_count`
- `failed_count`
- `sent_count`
- `due_count`
- `oldest_due_at`
- `last_error`

### Ready calculation nuance

Top-level `ready` hiện chỉ phụ thuộc vào:

- config hợp lệ
- schema/admin/runtime inspection hợp lệ
- data path parent tồn tại

Nó không bị kéo xuống `false` chỉ vì:

- notification degraded
- active bundle visibility vắng mặt

UI phải diễn giải nuance này đúng.

## 7.6 Health snapshot trong page context

`_prepare_health_snapshot(summaries)` tạo một view model page-level khác `readyz`.

Nếu không có summary:

- `status = "no-data"`
- `summary_ts = null`
- `alert_count = 0`
- `anomaly_count = 0`
- `window_seconds = null`
- `active_bundle = null`

Nếu có summary:

- `status = "ok"`
- lấy dữ liệu từ summary mới nhất

Lưu ý rất quan trọng:

- đây là summary-backed runtime snapshot
- không phải readiness truth đầy đủ

UI cần hiển thị song song `health snapshot` và `readiness`, không gộp nhầm làm một.

## 8. Mapping dữ liệu theo màn hình

## 8.1 Login

Hiển thị tối thiểu:

- tiêu đề surface
- username input
- password input
- login error nếu có

Không cần:

- readiness chi tiết
- health chi tiết
- active bundle

## 8.2 Overview

Bắt buộc hiển thị:

- readiness top-level
- readiness component snapshot
- notification state
- active bundle visibility
- alert pressure counts
- anomaly preview
- summary-backed health snapshot

Field matrix:

- `readiness.ready`
- `readiness.components.schema.state`
- `readiness.components.admin_bootstrap.admin_count`
- `readiness.components.data_paths.ok`
- `readiness.components.notification.state`
- `health.summary_ts`
- `health.alert_count`
- `health.anomaly_count`
- `health.window_seconds`
- `health.active_bundle.active_bundle_name`
- `health.active_bundle.compatibility_status`
- `health.active_bundle.previous_bundle_name`
- alert queue cards:
  - `id`
  - `src_ip`
  - `dst_ip`
  - `triage_status`
  - `severity`
  - `protocol`
  - `source_event_id`
  - `payload.score`
  - `event_ts`
- anomaly preview rows:
  - `id`
  - `anomaly_type`
  - `reason|redacted_summary`
  - `event_ts`

## 8.3 Alerts

Bắt buộc hiển thị:

- `status_filter`
- queue counts theo triage state
- suppressed indicator
- runtime context sidebar

Field matrix:

- `alerts[*].id`
- `alerts[*].source_event_id`
- `alerts[*].src_ip`
- `alerts[*].dst_ip`
- `alerts[*].triage_status`
- `alerts[*].severity`
- `alerts[*].suppressed`
- `alerts[*].family.family_state`
- `alerts[*].family.attack_family`
- `alerts[*].family.attack_family_confidence`
- `alerts[*].family.attack_family_margin`
- `alerts[*].protocol|payload.protocol`
- `alerts[*].payload.score`
- `alerts[*].event_ts`
- sidebar:
  - `health.status`
  - `health.summary_ts`
  - `health.alert_count`
  - `health.anomaly_count`
  - `health.active_bundle.active_bundle_name`

## 8.4 Alert Detail

Bắt buộc hiển thị:

- raw context
- current triage status
- severity
- suppressed state
- note form
- status form
- timeline status history
- timeline notes

Field matrix:

- `alert.id`
- `alert.source_event_id`
- `alert.event_ts`
- `alert.src_ip`
- `alert.dst_ip`
- `alert.src_port`
- `alert.dst_port`
- `alert.protocol|alert.payload.protocol`
- `alert.payload.score`
- `alert.fingerprint`
- `alert.sensor_id`
- `alert.suppressed`
- `timeline.status_history[*].changed_at`
- `timeline.status_history[*].from_status`
- `timeline.status_history[*].to_status`
- `timeline.status_history[*].changed_by`
- `timeline.notes[*].created_at`
- `timeline.notes[*].author`
- `timeline.notes[*].note_text`

## 8.5 Operations

Bắt buộc hiển thị:

- anomaly list
- runtime health snapshot
- readiness components

Field matrix:

- `anomalies[*].id`
- `anomalies[*].anomaly_type`
- `anomalies[*].reason`
- `anomalies[*].redacted_summary`
- `anomalies[*].event_ts`
- sidebar:
  - `health.status`
  - `health.summary_ts`
  - `health.anomaly_count`
  - `health.alert_count`
  - `health.active_bundle.compatibility_status`
  - `readiness.components.schema.state`
  - `readiness.components.admin_bootstrap.admin_count`
  - `readiness.components.data_paths.ok`
  - `readiness.components.notification.state`

## 8.6 Reports

Bắt buộc hiển thị:

- recent summary table
- alerts total
- alerts by status
- alerts by severity
- anomalies total
- summaries total
- anomaly history

Field matrix:

- `report_rollup.alerts_total`
- `report_rollup.alerts_by_status`
- `report_rollup.alerts_by_severity`
- `report_rollup.anomalies_total`
- `report_rollup.summaries_total`
- `summaries[*].summary_ts`
- `summaries[*].payload.alert_count`
- `summaries[*].payload.anomaly_count`
- `summaries[*].payload.window_seconds`
- `report_bundle.anomalies[*].id`
- `report_bundle.anomalies[*].anomaly_type`
- `report_bundle.anomalies[*].reason|redacted_summary`
- `report_bundle.anomalies[*].event_ts`

## 9. Gaps và cẩn trọng khi thiết kế UI

## 9.1 Sensor filtering chưa có trên HTML pages

JSON API đã hỗ trợ `sensor_id`, nhưng HTML pages hiện chưa có selector.

Hệ quả:

- future multi-sensor UI có cơ sở
- phase hiện tại không nên giả định page HTML đã sensor-aware

## 9.2 Summary-backed fields có thể vắng

Các field sau có thể không có:

- `health.active_bundle`
- `summary.payload.window_seconds`
- `summary.payload.alert_count`
- `summary.payload.anomaly_count`

UI phải có empty/degraded/no-data copy rõ ràng.

## 9.3 Suppression là concern của presentation

Suppression không xóa alert khỏi DB.

Hệ quả:

- queue, notification, report cần nhất quán về suppressed policy
- UI phải gắn nhãn suppressed rõ ràng khi row vẫn hiển thị

## 9.4 Notification detail có redaction

`readyz` khi authenticated vẫn giữ `target = null` và `last_error` bị redacted ở một số trường hợp public-safe.

Hệ quả:

- UI không nên hứa hiển thị full notification diagnostic từ `readyz`
- nếu cần full delivery debug thì đó là ops/CLI concern

## 9.5 Ready không đồng nghĩa mọi thứ đều hoàn hảo

Top-level `ready=true` vẫn có thể đi cùng:

- `notification.state = degraded`
- `active_bundle.ok = false`

UI phải thể hiện readiness tổng và degraded subdomain song song.

## 10. Khuyến nghị cho thiết kế chi tiết

- Dùng `Overview` để trả lời ngay:
  - console có ready không
  - queue alert có nóng không
  - anomaly lane có vấn đề không
- Dùng `Alerts` như work queue thực sự, không kéo anomaly vào cùng layout
- Dùng `Operations` như domain diagnosis surface, không biến thành clone của `Overview`
- Dùng `Reports` theo table-first, rollup-second
- Mọi mutate form phải hiển thị trạng thái submit rõ, nhưng vẫn dựa trên server redirect hiện tại

## 11. Quyết định chốt cho implement

Frontend/UI implement phải xem đây là contract:

- giữ nguyên route topology hiện có
- giữ session + CSRF model hiện có
- không vượt boundary sang control-plane mutation
- ưu tiên hiển thị đúng `alerts`, `anomalies`, `summaries`, `readiness`
- xử lý tốt optional/degraded/no-data states
