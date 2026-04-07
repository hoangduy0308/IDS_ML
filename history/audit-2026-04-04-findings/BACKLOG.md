# Audit Backlog — IDS ML New

**Nguồn:** Báo cáo audit bảo mật toàn diện ngày 2026-04-04
**Trạng thái:** Đang thực hiện
**Phạm vi:** Các mục HIGH (H1–H5), MEDIUM (M1–M9), và LOW tham khảo (L1–L7) từ báo cáo audit

---

## HIGH Severity (5 mục)

### H1 — Chỉ phân loại nhị phân
**Trạng thái hiện tại:** Đang thực hiện một phần — đã hoàn tất lane operator-facing, chưa hoàn tất full multiclass attack-category rollout
**File:** `ids/runtime/inference.py`
**Vấn đề:** Mô hình chỉ xuất Attack/Benign, không phân loại loại tấn công cụ thể (DDoS, BruteForce, Mirai, Recon, Spoofing, Web-based, DoS).
**Ảnh hưởng:** Phân tích viên không thể phân loại cảnh báo theo loại tấn công nếu không kiểm tra luồng thô thủ công.
**Độ phức tạp:** LỚN — cần huấn luyện lại mô hình (đa lớp), cập nhật schema cảnh báo, cập nhật UI console.
**Tiến độ đã có trong repo:**
- Đã có family-view artifact và training lane cho stage-2 family classifier
- Đã có direct multiclass baseline để so sánh offline
- Đã có composite runtime contract để enrich thêm family fields mà vẫn giữ binary contract cũ
- Đã hoàn tất phần console/operator-facing acceptance qua lane `ids-multiclass-two-stage-operator-surfaces`
- Queue/detail/docs/tests cho family prediction đã được pin sạch và epic `ids_ml_new-3rc7` đã đóng
- Vẫn chưa hoàn tất phần closed-set multiclass attack-category theo đúng wording acceptance của audit
**Acceptance criteria:**
- Mô hình CatBoost đa lớp được huấn luyện trên CIC IoT-DIAD 2024
- Bundle mô hình mới có `prediction_type: multiclass_classifier`
- Trường `attack_category` xuất hiện trong alert JSONL
- Cột "Attack Type" hiển thị trong trang Alerts của console
- Không hồi quy độ chính xác nhị phân so với mô hình hiện tại

**Đánh giá hiện tại so với acceptance audit:**
- Chưa chứng minh rollout `attack_category` closed-set end-to-end
- Chưa có bằng chứng rằng bundle production đã chuyển sang `prediction_type: multiclass_classifier`
- Phần hiển thị operator-facing cho two-stage family prediction đã hoàn tất, nhưng chưa tương đương hoàn tất toàn bộ H1 theo wording hiện tại

---

### H2 — Không tích hợp SIEM
**File:** Thiếu hoàn toàn
**Vấn đề:** Không có syslog, CEF, LEEF, hay webhook đầu ra.
**Ảnh hưởng:** Không thể đẩy cảnh báo vào SIEM doanh nghiệp (Splunk, QRadar, Elastic SIEM).
**Độ phức tạp:** TRUNG BÌNH — thêm module sink mới song song với Telegram.
**Acceptance criteria:**
- Module mới `ids/console/siem_sink.py` hỗ trợ ít nhất syslog (RFC 5424) và HTTP webhook
- Cấu hình qua env + Settings UI giống Telegram
- Worker notification gửi cảnh báo qua các sink đã bật
- Retry/backoff giống như Telegram
- Test bao phủ: syslog format, webhook JSON payload, failure retry

---

### H3 — Một giao diện mạng duy nhất
**File:** `ids/runtime/live_sensor.py`
**Vấn đề:** Cảm biến trực tiếp chỉ bắt một interface tại một thời điểm.
**Ảnh hưởng:** Không thể giám sát nhiều phân đoạn mà không chạy N instance cảm biến độc lập.
**Độ phức tạp:** TRUNG BÌNH-LỚN — cần refactor capture loop và activation contract.
**Acceptance criteria:**
- `--interface` chấp nhận nhiều giá trị hoặc `--interfaces ethX,ethY`
- Mỗi interface có capture session riêng với spool dir riêng
- Flow records được gắn nhãn `sensor_interface`
- Cập nhật systemd unit và install script

---

### H4 — Không xử lý lưu lượng mã hoá
**File:** `ids/runtime/extractor/offline_window_extractor.py`
**Vấn đề:** PCAP parser chỉ xử lý IPv4/TCP/UDP rõ. Luồng TLS/HTTPS không trong suốt.
**Ảnh hưởng:** Trích xuất đặc trưng bị suy giảm cho lưu lượng mã hoá.
**Độ phức tạp:** LỚN — cần thêm các đặc trưng TLS (JA3/JA4 fingerprinting, SNI, cert metadata).
**Acceptance criteria:**
- Parser nhận dạng ClientHello/ServerHello
- Trích xuất JA3 hoặc JA4 hash
- Thêm các đặc trưng TLS vào feature contract (phiên bản mới của bundle)
- Tài liệu về cách huấn luyện lại với feature mới

---

### H5 — Nút thắt ghi đơn SQLite
**File:** `ids/console/db.py`
**Vấn đề:** DB bảng điều khiển không thể mở rộng ngang.
**Ảnh hưởng:** Môi trường lưu lượng cao (>1000 cảnh báo/phút) sẽ gặp tranh chấp ghi.
**Độ phức tạp:** LỚN — yêu cầu lớp trừu tượng DB (SQLAlchemy) và hỗ trợ PostgreSQL.
**Acceptance criteria:**
- Lớp DB trừu tượng hỗ trợ SQLite (mặc định) và PostgreSQL (tuỳ chọn)
- Migration tương thích cả hai backend
- Benchmark chứng minh throughput >1000 alerts/min trên PostgreSQL
- Tài liệu hướng dẫn chuyển đổi

---

## MEDIUM Severity (9 mục)

### M1 — 4 test thất bại
**Trạng thái hiện tại:** Hoàn tất
**File:** `tests/ops/test_ids_operator_console_ops.py`, `tests/runtime/test_ids_live_sensor.py`
**Vấn đề:**
- 3 test preflight lỗi vì `ids.console.server` "không import được" trong ngữ cảnh pytest
- 1 test service unit kỳ vọng đường dẫn script cũ `ids_live_sensor_preflight.py` nhưng service giờ dùng `-m ids.ops.live_sensor_preflight`
**Ảnh hưởng:** Độ tin cậy test giảm; CI/CD sẽ chặn tại đây.
**Độ phức tạp:** NHỎ — test drift, không phải lỗi chức năng.
**Acceptance criteria:**
- Cả 4 test đạt
- Không có test nào khác bị hồi quy
- Tổng test suite: 590/590 pass

**Kết quả đã đạt trong repo:**
- Đã sửa fixture/install-check contract cho `ids.console.server`
- Đã cập nhật assertion service unit sang module-form invocation mới
- Lane này đã được đóng trong bead/commit trước đó

**Ưu tiên cao nhất — khuyến nghị làm đầu tiên (Quick Mode)**

---

### M2 — Không có pipeline CI/CD
**File:** Thiếu hoàn toàn
**Vấn đề:** Không có GitHub Actions, GitLab CI, hay Jenkins config.
**Ảnh hưởng:** Không có cổng build/test/deploy tự động.
**Độ phức tạp:** NHỎ-TRUNG BÌNH.
**Acceptance criteria:**
- `.github/workflows/ci.yml` chạy pytest trên mỗi PR
- Chạy trên Python 3.11 trên Ubuntu
- Cache dependencies
- Gắn badge status vào README

**Phụ thuộc:** M1 phải hoàn thành trước (không thể có CI xanh khi có test đỏ).

---

### M3 — Không xoay vòng log
**File:** `ids/runtime/live_sensor_sinks.py`, `ops/` (cấu hình logrotate)
**Vấn đề:** Tệp JSONL cảnh báo/cách ly tăng không giới hạn.
**Ảnh hưởng:** Đầy ổ đĩa nếu cảm biến chạy lâu dài.
**Độ phức tạp:** NHỎ.
**Acceptance criteria:**
- Thêm `ops/logrotate.d/ids-live-sensor` với rotation hàng ngày, giữ 14 ngày, nén
- Install script copy cấu hình vào `/etc/logrotate.d/`
- Tài liệu trong `docs/current/operations/deployment-quickstart.md`
- Test integration: sink mở lại được file sau khi bị xoay vòng

---

### M4 — Không giới hạn tốc độ trên web console
**File:** `ids/console/web.py`
**Vấn đề:** Endpoint login không có bảo vệ brute-force.
**Ảnh hưởng:** Có thể bị tấn công dò mật khẩu.
**Độ phức tạp:** NHỎ.
**Acceptance criteria:**
- Login endpoint giới hạn 5 lần thử/IP/phút
- Sử dụng in-memory store hoặc SQLite table
- Thông báo lỗi chung chung (không tiết lộ user tồn tại)
- Test: vượt quá giới hạn → 429 Too Many Requests
- Log cảnh báo khi IP vượt giới hạn

---

### M5 — Không hỗ trợ IPv6
**File:** `ids/runtime/extractor/offline_window_extractor.py`
**Vấn đề:** Parser gói tin chỉ lọc IPv4 (EtherType 0x0800).
**Ảnh hưởng:** Lưu lượng IPv6 bị bỏ qua hoàn toàn.
**Độ phức tạp:** TRUNG BÌNH — cần cập nhật parser và có thể cả feature engineering.
**Acceptance criteria:**
- Parser nhận dạng EtherType 0x86DD (IPv6)
- Trích xuất địa chỉ IPv6 src/dst
- Feature contract hỗ trợ cả v4 và v6
- Test: PCAP fixture chứa lưu lượng IPv6
- Tài liệu: cập nhật feature schema docs

---

### M6 — Không có TLS tích hợp
**File:** `ids/console/server.py`
**Vấn đề:** uvicorn chỉ phục vụ HTTP.
**Ảnh hưởng:** Cần reverse proxy bên ngoài; có rủi ro cấu hình sai.
**Độ phức tạp:** NHỎ — tài liệu + tuỳ chọn CLI.
**Acceptance criteria:**
- Thêm flag `--tls-cert` và `--tls-key` cho server
- Preflight kiểm tra tệp chứng chỉ tồn tại và hợp lệ
- Tài liệu: khuyến nghị nginx là chính, uvicorn TLS là phương án dự phòng
- Test: khởi động với cert tự ký

---

### M7 — OOD recall chỉ 49.9%
**File:** `artifacts/final_model/catboost_full_data_v1/metrics.json`
**Vấn đề:** Mô hình chỉ phát hiện khoảng nửa số tấn công BruteForce và Recon từ họ ngoài phân phối.
**Ảnh hưởng:** Các loại tấn công mới/chưa biết sẽ bị bỏ sót.
**Độ phức tạp:** LỚN — cần thử nghiệm ML (augmentation, ensemble, hoặc anomaly detection layer bổ sung).
**Acceptance criteria:**
- Thí nghiệm có hệ thống ghi lại OOD recall cho từng cấu hình
- OOD recall >= 70% trên cả BruteForce và Recon mà không giảm F1 quá 1%
- Báo cáo so sánh và quyết định cuối cùng

**Phụ thuộc:** Có thể kết hợp với H1 trong cùng một đợt huấn luyện lại mô hình.

---

### M8 — Không có trigger tái huấn luyện mô hình
**File:** Thiếu
**Vấn đề:** Không có phát hiện drift hay lịch tái huấn luyện.
**Ảnh hưởng:** Mô hình suy giảm âm thầm.
**Độ phức tạp:** TRUNG BÌNH.
**Acceptance criteria:**
- Script theo dõi drift (PSI hoặc KS test trên phân phối đặc trưng)
- CLI `ids-model-drift-check` so sánh lưu lượng gần đây với baseline huấn luyện
- Cảnh báo trong console khi drift vượt ngưỡng
- Tài liệu playbook tái huấn luyện

---

### M9 — Không có triển khai Docker/container
**File:** Thiếu hoàn toàn
**Vấn đề:** Chỉ bare-metal.
**Ảnh hưởng:** Không thể triển khai trên Kubernetes, ECS.
**Độ phức tạp:** TRUNG BÌNH.
**Acceptance criteria:**
- `Dockerfile` cho console (multi-stage, non-root user)
- `Dockerfile` cho live sensor (yêu cầu CAP_NET_RAW)
- `docker-compose.yml` cho dev/test
- Tài liệu triển khai container
- Test: container khởi động và vượt qua health check

---

## LOW Severity (tham khảo — không trong phạm vi ban đầu)

- **L1** — Không có test JavaScript cho `console.js`
- **L2** — Không có benchmark hiệu năng/tải
- **L3** — Thông báo email chưa triển khai
- **L4** — Đường dẫn Windows trong `model_bundle.json` (cosmetic)
- **L5** — Cảnh báo deprecation pytest-asyncio
- **L6** — matplotlib trong requirements production (nên tách ra extras)
- **L7** — Không hỗ trợ multi-tenancy

---

## Nhóm Đề Xuất (cho Go Mode)

| Nhóm | Mục | Lý do gộp |
|------|-----|-----------|
| **Feature 1 — Test & CI Hygiene** | M1 + M2 + L5 | Nền tảng cho tất cả công việc tiếp theo |
| **Feature 2 — Operational Hardening** | M3 + M4 + M6 + L4 | Củng cố vận hành, ít rủi ro, giá trị cao |
| **Feature 3 — SIEM & Notifications** | H2 + L3 | Cùng lớp kiến trúc (notification sinks) |
| **Feature 4 — Multi-class & OOD** | H1 + M7 | Cùng đợt huấn luyện lại mô hình |
| **Feature 5 — Protocol Coverage** | M5 + H4 | Cùng tệp parser (`offline_window_extractor.py`) |
| **Feature 6 — Container & Drift** | M9 + M8 | Phụ trợ triển khai và bảo trì |
| **Deferred** | H3, H5 | Yêu cầu refactor lớn, chờ quyết định kiến trúc |

---

## Ưu Tiên Thực Hiện Đề Xuất

1. **Feature 1 (Test & CI)** — Làm trước để mọi thứ sau có CI gate
2. **Feature 2 (Operational Hardening)** — Nhanh, giá trị cao, rủi ro thấp
3. **Feature 3 (SIEM)** — Mở rộng khả năng cho doanh nghiệp
4. **Feature 5 (Protocol Coverage)** — Tăng độ phủ phát hiện
5. **Feature 4 (Multi-class & OOD)** — Lớn nhất, cần nhiều thời gian ML
6. **Feature 6 (Container & Drift)** — Có thể làm cuối khi hệ thống đã ổn định

---

**Ghi chú:**
- Mỗi Feature sẽ được khởi tạo qua skill `khuym:exploring` hoặc `khuym:planning` riêng
- Bead sẽ được tạo khi Feature được lên kế hoạch cụ thể
- File này là nguồn tham chiếu duy nhất cho backlog audit; không đại diện cho bead hay epic
