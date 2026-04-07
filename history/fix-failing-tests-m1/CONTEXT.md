# CONTEXT — Fix Failing Tests (M1 Quick Mode)

**Feature slug:** fix-failing-tests-m1
**Source:** Audit 2026-04-04, mục M1 trong `history/audit-2026-04-04-findings/BACKLOG.md`
**Mode:** Quick Mode (single story, no exploring phase)
**Created:** 2026-04-04

---

## Plain-Language Summary

Bốn test đang fail trong bộ test 590 test của repo. Ba test preflight thất bại vì gói `ids-ml-new` không được cài đặt vào site-packages của interpreter, và test preflight spawn một subprocess `python -I` (isolated mode) mà không thể tìm thấy `ids.console.server`. Test thứ tư assert một đường dẫn script cũ trong file service systemd, nhưng file service đã được cập nhật để dùng form `-m ids.ops.live_sensor_preflight` (module form). Đây đều là vấn đề test drift — không có lỗi trong code production. Mục tiêu: 590/590 pass mà không làm suy yếu các hợp đồng bảo mật mà test đang kiểm tra.

---

## Locked Decisions

### D1 — Nguyên nhân gốc đã được xác định

**Quyết định:** Bốn test thất bại có hai nguyên nhân gốc riêng biệt:

**Nhóm A (3 test preflight trong `tests/ops/test_ids_operator_console_ops.py`):**
- `test_preflight_accepts_valid_contract`
- `test_preflight_rejects_missing_admin_bootstrap`
- `test_preflight_rejects_telegram_pairing`

Tất cả fail với cùng một lỗi ở bước đầu tiên của `validate_preflight`:
```
ValueError: app_module is not importable by python_binary: ids.console.server
```

Nguyên nhân: `ids/ops/module_validation.py::_run_module_check` spawn một subprocess với:
1. `python -I` (isolated mode — bỏ qua `PYTHONPATH`, CWD, user site-packages)
2. `cwd=resolved_python.parent` (CWD của subprocess là thư mục chứa `python.exe`, không phải repo root)
3. `env` loại bỏ mọi `PYTHON*` variable (defense-in-depth)

Trong subprocess đó, cách duy nhất để tìm thấy `ids.console.server` là gói `ids-ml-new` phải được cài vào site-packages của interpreter (`pip install -e .`). Hiện tại gói **không** được cài — `python -m pip show ids-ml-new` trả về "Package(s) not found". Pytest vẫn import được `ids` vì tình cờ có `F:\Work\IDS_ML_New` trong `sys.path` của pytest runner, nhưng subprocess isolated mode không kế thừa điều đó.

**Đây không phải là bug.** Đây là hợp đồng bảo mật có chủ đích từ critical-pattern [20260403] *"Bind Privileged Bootstrap Execution To The Validated Interpreter Contract"*. Preflight phải kiểm tra rằng module có thể import được bởi **chính cái interpreter mà production sẽ dùng**, không được fallback qua `cwd` hay `PYTHONPATH`.

**Nhóm B (1 test trong `tests/runtime/test_ids_live_sensor.py`):**
- `test_service_unit_keeps_preflight_and_stdout_journal_contract`

Fail tại:
```python
assert "ids_live_sensor_preflight.py" in content
```

Nhưng file `deploy/systemd/ids-live-sensor.service` hiện tại không chứa chuỗi đó; nó dùng:
```
ExecStartPre=/opt/ids_ml_new/.venv/bin/python -m ids.ops.live_sensor_preflight ...
```

Nguyên nhân: Test chưa được cập nhật khi service unit chuyển từ đường dẫn file script sang module form. Hợp đồng mà test muốn kiểm tra (preflight được chạy trước khi daemon start) vẫn còn nguyên — chỉ có dạng biểu đạt là thay đổi.

**Why:** Mục M1 chỉ có thể sửa đúng sau khi hiểu rõ cả hai nguyên nhân. Nếu sửa Nhóm A bằng cách làm suy yếu `_run_module_check` (ví dụ thêm repo root vào `sys.path` của subprocess), chúng ta phá vỡ critical-pattern [20260403] và tạo ra một lỗ hổng bảo mật. Nếu sửa Nhóm B bằng cách sửa service unit về dạng cũ, chúng ta phá vỡ cấu trúc installable package.

**How to apply:** Mọi giải pháp cho Nhóm A phải bảo toàn hợp đồng `-I` và `env` sạch của `_run_module_check`. Mọi giải pháp cho Nhóm B phải chỉ cập nhật test, không cập nhật service unit.

---

### D2 — Cách tiếp cận sửa Nhóm A

**Quyết định:** Cập nhật test setup để đảm bảo gói `ids-ml-new` được cài editable trước khi chạy các test preflight.

**Ba phương án được xem xét:**

| Phương án | Mô tả | Đánh giá |
|-----------|-------|----------|
| **A.1** (chọn) | Session-scoped pytest fixture trong `tests/conftest.py` đảm bảo `ids-ml-new` được cài editable. Nếu chưa cài, fixture chạy `pip install -e .` một lần cho cả session. | ✅ Khớp với critical-pattern [20260403]: test exercise hợp đồng production thật sự |
| A.2 | Test tự skip nếu `ids-ml-new` không cài. | ❌ Ẩn vấn đề thật sự; CI có thể fail vì skip khi không có package |
| A.3 | Truyền `python_binary` khác (venv có cài package) vào test. | ❌ Phức tạp, khó tái lập, phá vỡ cách test thực sự đo contract |

**Why:** Critical-pattern [20260403] *"Prove Editable Installs In A Scrubbed Environment That Cannot Fall Back To Warmed `__pycache__`"* nói rõ: "In-tree or already-warmed verification is not enough to prove an install contract because it can hide missing source files, templates, or package data. Future packaging work should always run a fresh editable-install proof." Test preflight chính là loại test đó — nó phải chạy trong môi trường mà package thật sự được cài.

**How to apply:** Fixture phải:
- Scope = "session" (cài một lần)
- Kiểm tra `ids-ml-new` đã cài chưa qua `importlib.metadata.distribution("ids-ml-new")` hoặc `pip show`
- Nếu chưa: chạy `subprocess.run([sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"])` với `cwd=REPO_ROOT`
- Nếu đã cài: no-op
- Tên rõ ràng ví dụ `_ensure_editable_install`
- Áp dụng cho 3 test preflight qua `autouse=True` ở module level hoặc qua fixture rõ ràng

---

### D3 — Cách tiếp cận sửa Nhóm B

**Quyết định:** Cập nhật assertion trong `test_service_unit_keeps_preflight_and_stdout_journal_contract` để khớp với form module hiện tại.

**Thay đổi:**
```python
# Cũ (fail):
assert "ids_live_sensor_preflight.py" in content

# Mới (pass):
assert "-m ids.ops.live_sensor_preflight" in content
```

Giữ nguyên tất cả assertion khác trong test (các flag `--dumpcap-binary`, `--extractor-command-prefix`, `--activation-path`, v.v.), vì chúng vẫn đang chứng minh các hợp đồng thật sự.

**Why:** Critical-pattern [20260330] *"Pin Multi-Token Runtime Contracts With End-To-End Tokenization Tests"* nhắc nhở rằng test cho service unit nên tập trung vào hợp đồng tokenization thật sự, không phải tên file. Form module `-m ids.ops.live_sensor_preflight` vừa đúng hợp đồng vừa nằm trong trusted-root contract của installable package.

**How to apply:** Chỉ sửa duy nhất dòng assertion, không sửa file service, không sửa test khác.

---

### D4 — Phạm vi sửa đổi

**Quyết định:** Phạm vi file thay đổi:

**Sẽ sửa:**
- `tests/conftest.py` — thêm session fixture `_ensure_editable_install`
- `tests/runtime/test_ids_live_sensor.py` — sửa 1 dòng assertion

**Không sửa:**
- `ids/ops/module_validation.py` — giữ nguyên hợp đồng `-I` và env sạch
- `ids/ops/operator_console_preflight.py` — giữ nguyên
- `deploy/systemd/ids-live-sensor.service` — đã đúng, không cần sửa
- `tests/ops/test_ids_operator_console_ops.py` — fixture session sẽ lo việc cài package; không cần sửa logic test
- `pyproject.toml` / `requirements.txt` — không đổi dependency

**Why:** Nguyên tắc "Don't add features, refactor code, or make improvements beyond what was asked" — scope phải hẹp nhất có thể.

**How to apply:** Nếu trong quá trình thực thi phát hiện cần sửa file khác, pause và surface conflict trước khi mở rộng scope.

---

### D5 — Acceptance criteria

**Quyết định:** Phase/story này được coi là xong khi:

1. `python -m pytest tests/ -q` báo cáo **590 passed, 0 failed** (tăng từ 586 passed, 4 failed)
2. Không có test nào khác bị hồi quy
3. Không có file nào ngoài phạm vi D4 bị sửa đổi
4. Hợp đồng bảo mật trong `module_validation.py` vẫn còn nguyên (xác minh bằng `git diff ids/ops/module_validation.py` trả về rỗng)
5. Service unit `ids-live-sensor.service` không bị sửa đổi (xác minh bằng `git diff deploy/systemd/` trả về rỗng)

**Why:** Acceptance phải observable. Mỗi tiêu chí kiểm tra được bằng một lệnh CLI duy nhất.

**How to apply:** Khi validating và reviewing, kiểm tra từng tiêu chí trên. Nếu bất kỳ tiêu chí nào không đạt, không được coi là xong.

---

### D6 — Critical patterns được áp dụng

**Quyết định:** Các critical patterns sau đây được bind vào phase này:

- **[20260403] Bind Privileged Bootstrap Execution To The Validated Interpreter Contract** — D1, D2 dựa trực tiếp vào pattern này. Không được phá hợp đồng `-I` + env sạch để "cho test pass."
- **[20260403] Prove Editable Installs In A Scrubbed Environment** — D2 phương án A.1 tuân thủ pattern này bằng cách test thật sự chạy trong môi trường có package cài đặt.
- **[20260330] Pin Multi-Token Runtime Contracts With End-To-End Tokenization Tests** — D3 giữ nguyên các assertion tokenization thật sự.
- **[20260331] Treat Compatibility Wrappers As Executable Contracts** — xác nhận rằng test phải chạy trong môi trường có package cài đặt thật, giống CI.

**Why:** 22 entries trong `history/learnings/critical-patterns.md` đã được đọc. 4 entries trên có liên quan trực tiếp.

**How to apply:** Mọi quyết định trong validating và reviewing phải nhất quán với 4 patterns trên. Nếu không, pause và thảo luận lại.

---

## Gray Areas (None)

Tất cả quyết định trong CONTEXT này đã được lock dựa trên bằng chứng trực tiếp từ:
- Output pytest (đã chạy trong phiên audit)
- Mã nguồn `ids/ops/module_validation.py`, `tests/ops/test_ids_operator_console_ops.py`, `tests/runtime/test_ids_live_sensor.py`, `deploy/systemd/ids-live-sensor.service`
- Critical patterns đã thiết lập trong `history/learnings/critical-patterns.md`

Không có gray area. Có thể bỏ qua exploring đầy đủ và tiến thẳng vào planning Quick Mode.

---

## Out of Scope

- M2 (CI/CD pipeline) — sẽ làm sau khi M1 xanh
- Bất kỳ mục H/M/L nào khác từ BACKLOG.md
- Refactor module_validation.py
- Thêm test mới cho chính hợp đồng preflight/tokenization
- Cập nhật docs

---

## Success Metric

Chạy `python -m pytest tests/ -q --tb=line` cho kết quả:
```
590 passed in <N>s
```

Không có test failure, không có error, không có skip.
