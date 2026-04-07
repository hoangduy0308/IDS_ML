# Phase 1 Contract — Fix Test Drift

**Feature:** fix-failing-tests-m1
**Phase:** 1 (of 1)
**Mode:** Quick Mode
**Created:** 2026-04-04

---

## What Changes In Real Life

Sau khi Phase 1 landing, developer chạy `python -m pytest tests/ -q` (trên máy local không cần cài package trước) sẽ thấy `590 passed, 0 failed`. CI chạy cùng lệnh cũng thấy `590 passed`. Không còn 4 test đỏ chặn merge hoặc làm hỏng niềm tin vào test suite.

Không có thay đổi nào trong behavior của production code (live sensor, console, model inference). Chỉ có test infrastructure và 1 dòng assertion được cập nhật.

---

## Entry State (trước khi Phase 1 bắt đầu)

```
$ python -m pytest tests/ -q --tb=line
...
4 failed, 586 passed, 4 warnings in 749.29s
FAILED tests/ops/test_ids_operator_console_ops.py::test_preflight_accepts_valid_contract
FAILED tests/ops/test_ids_operator_console_ops.py::test_preflight_rejects_missing_admin_bootstrap
FAILED tests/ops/test_ids_operator_console_ops.py::test_preflight_rejects_telegram_pairing
FAILED tests/runtime/test_ids_live_sensor.py::test_service_unit_keeps_preflight_and_stdout_journal_contract
```

- `ids-ml-new` không có trong site-packages
- `tests/conftest.py` không có fixture đảm bảo editable install
- `tests/runtime/test_ids_live_sensor.py` line 513 assert `"ids_live_sensor_preflight.py"`
- `deploy/systemd/ids-live-sensor.service` dùng `-m ids.ops.live_sensor_preflight` (đã đúng)
- `ids/ops/module_validation.py` chạy subprocess với `-I`, CWD khoá, env scrub (security contract còn nguyên)

---

## Exit State (sau khi Phase 1 hoàn thành)

```
$ python -m pytest tests/ -q
...
590 passed in <N>s
```

Observable checks:

1. `python -m pytest tests/ -q` báo cáo `590 passed, 0 failed, 0 error, 0 skip`.
2. `git diff ids/` → rỗng.
3. `git diff deploy/` → rỗng.
4. `git diff pyproject.toml requirements.txt` → rỗng.
5. `git diff tests/conftest.py` → hiển thị fixture mới (~20-30 dòng).
6. `git diff tests/runtime/test_ids_live_sensor.py` → hiển thị đúng 1 dòng thay đổi ở line 513.
7. `python -m pip show ids-ml-new` → trả về package info (chứng minh fixture đã cài thành công).
8. Chạy lần 2 `pytest tests/ -q` trong cùng venv → vẫn 590 pass, không crash do fixture re-run (idempotent).

---

## Demo Walkthrough

```bash
# 1. Bắt đầu từ trạng thái sạch — gỡ package nếu có
python -m pip uninstall -y ids-ml-new 2>&1 || true
python -m pip show ids-ml-new  # → Package(s) not found

# 2. Chạy pytest — fixture sẽ tự cài editable
python -m pytest tests/ -q --tb=line
# Expected: 590 passed

# 3. Xác minh package đã được cài
python -m pip show ids-ml-new
# Expected: Name: ids-ml-new, Version: 0.1.0, Location: ...

# 4. Xác minh không có production code bị đụng
git diff ids/ deploy/ pyproject.toml requirements.txt
# Expected: empty output

# 5. Xác minh đúng phạm vi sửa
git diff --stat tests/
# Expected: tests/conftest.py và tests/runtime/test_ids_live_sensor.py only

# 6. Chạy lần nữa để verify idempotency
python -m pytest tests/ -q
# Expected: vẫn 590 passed, không lỗi fixture
```

Nếu tất cả 6 bước đều pass → Phase 1 exit state đạt.

---

## What This Phase Unlocks

- **M2 (CI/CD Pipeline):** Có thể thêm GitHub Actions workflow chạy `pytest` với niềm tin 590/590 sẽ pass.
- **Base line cho các feature audit tương lai:** Bất kỳ PR nào cho H1-H5 hay M3-M9 đều có thể so sánh với baseline 590/590.
- **Developer confidence:** Không còn 4 test đỏ làm nhiễu khi review diff.

---

## Explicitly Out of Scope

- Thêm test mới (dù có thể là tốt cho fixture) — sẽ làm riêng nếu cần
- Refactor `ids/ops/module_validation.py`
- Thay đổi `deploy/systemd/ids-live-sensor.service`
- Cập nhật `docs/` (không có docs nào nói về test workflow cần cập nhật)
- Cập nhật `pyproject.toml` test config (dù thêm `pytest.ini` hay `[tool.pytest.ini_options]` có thể sửa warning pytest-asyncio — đó là L5, để dành)
- Bất kỳ mục nào khác trong `BACKLOG.md`

---

## Pivot Signals

Nếu bất kỳ tín hiệu nào dưới đây xuất hiện, **dừng execution và báo cáo**, không cố "fix forward":

1. Sau khi apply Fix A (fixture), 3 test preflight vẫn fail với lỗi khác (không phải `not importable`) → có nguyên nhân gốc khác chưa biết, cần debugging skill.
2. Sau khi apply Fix B, test service unit vẫn fail hoặc có assertion khác fail → test drift rộng hơn dự kiến.
3. Fixture cài editable gây hồi quy ≥1 test khác trong 586 test đang pass → scope fixture sai.
4. `pip install -e .` fail trên máy dev → môi trường Python của dev bị hỏng, không phải scope M1.
5. CI không thể chạy fixture do hạn chế permission site-packages → cần điều chỉnh approach (ví dụ require CI pre-install package trước pytest).

---

## Phase Size Check

- Stories: 1
- Beads dự kiến: 1-2 (một cho implement, optionally một cho verification)
- Files touched: 2
- Lines changed: ~25
- Estimated worker time: 15-30 phút

→ Quá nhỏ để tách thành nhiều phase. Quick Mode phù hợp.
