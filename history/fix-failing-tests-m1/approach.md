# Approach — Fix Failing Tests (M1)

## 1. Gap Analysis

| Điều cần có | Trạng thái hiện tại | Gap |
|-------------|---------------------|-----|
| 590/590 test pass | 586/590 pass, 4 fail | 4 test fail |
| Test preflight chạy trong môi trường có `ids-ml-new` cài editable | Pytest chạy nhưng package không cài; `_run_module_check` subprocess không tìm thấy `ids.console.server` | Thiếu cơ chế đảm bảo install trước test |
| Test service unit khớp với form `-m ids.ops.live_sensor_preflight` | Test assert đường dẫn script cũ `ids_live_sensor_preflight.py` | Test drift 1 dòng |
| Security contract của `_run_module_check` được bảo toàn | Còn nguyên | — |
| Không suy yếu tokenization contract của service unit test | Còn nguyên (các assertion tokenization khác đều đúng) | — |

---

## 2. Recommended Approach

### Fix A (REVISED v2 — 2026-04-04 16:45Z) — Session fixture cài editable package, check qua subprocess isolated

**File:** `tests/conftest.py`

**Lý do revise:** Phiên bản v1 dùng `importlib.metadata.distribution("ids-ml-new")` làm check đã fail khi pytest chạy (587/590 pass thay vì 590/590). Nguyên nhân gốc: `conftest.py` line 12-13 tự thêm `REPO_ROOT` vào `sys.path`, và khi có `ids_ml_new.egg-info/` trong repo root (từ bất kỳ lần `pip install -e .` nào trước đó), `importlib.metadata` scan `sys.path` và tìm thấy metadata ở repo root — mặc dù package **không thực sự** nằm trong `site-packages` của interpreter. Fixture đi vào nhánh no-op, pip install không bao giờ chạy, và subprocess `python -I` trong `_run_module_check` (có `cwd=python_binary.parent` + env scrubbed) vẫn không tìm thấy `ids.console.server`.

**Nguyên tắc đúng:** Check của fixture phải khớp **chính xác** với điều kiện mà production contract (`_run_module_check` với `-I` + env scrubbed + CWD khoá) sẽ yêu cầu. Vì vậy check phải cũng là subprocess isolated, không phải `importlib.metadata` trên sys.path của pytest.

**Logic mới:**

1. Chạy subprocess `python -I -c "import ids.console.server"` với `cwd=python_binary.parent` và env scrubbed (giống `_run_module_check`).
2. Nếu returncode == 0 → package thực sự nằm trong site-packages → no-op.
3. Nếu returncode != 0 → chạy `pip install -e .` với `cwd=REPO_ROOT`.
4. Sau khi cài, chạy lại subprocess check để verify.
5. Nếu verify vẫn fail → raise RuntimeError.

**Tại sao check qua subprocess mà không phải importlib.metadata:**
- Subprocess trong isolated mode + CWD khoá + env scrubbed là **cùng một hợp đồng** mà test preflight sẽ yêu cầu
- Không bị false positive khi có egg-info còn sót trong CWD hoặc PYTHONPATH
- Khớp critical-pattern [20260403] "Bind Privileged Bootstrap Execution To The Validated Interpreter Contract" — kiểm tra dưới cùng interpreter/env contract mà production sẽ chạy

**Tại sao session scope:** Như cũ — `pip install -e .` tốn vài giây, chạy một lần cho cả session đủ.

**Tại sao autouse:** Như cũ.

**Về egg-info còn sót:** Fixture KHÔNG xoá `ids_ml_new.egg-info/`. Nó có thể thuộc về phiên song song hoặc setup cục bộ của user. Fixture chỉ đảm bảo package có trong site-packages thật; egg-info ngoài repo là lo lắng của user, không phải của fixture.

### Fix B — Sửa 1 dòng assertion

**File:** `tests/runtime/test_ids_live_sensor.py` line 513

```python
# Cũ:
assert "ids_live_sensor_preflight.py" in content

# Mới:
assert "-m ids.ops.live_sensor_preflight" in content
```

Giữ nguyên tất cả assertion khác (14 assertion khác trong test). Tokenization contract không đổi.

---

## 3. Alternatives Considered

### Alt A — Skip test nếu package chưa cài
```python
pytest.skip("ids-ml-new not installed as editable")
```
**Bác bỏ:** Ẩn vấn đề. Developer local có thể ship code với test bị skip mà không biết. Critical-pattern [20260331] nhắc: *"wrapper stability is not real unless CI exercises those wrappers directly"*.

### Alt B — Gỡ `-I` flag khỏi `_run_module_check`
**Bác bỏ mạnh:** Phá vỡ security contract [20260403]. Đây là chính xác điều mà critical pattern đó cảnh báo không được làm.

### Alt C — Pass cwd=REPO_ROOT vào subprocess của `_run_module_check`
**Bác bỏ:** Cũng phá contract — `-I` bao gồm việc không thêm `sys.path[0]` từ CWD. Thậm chí nếu fix được lỗi ngay bây giờ, nó tạo ra một lỗ hổng mà attacker có thể lợi dụng bằng cách đặt code độc trong CWD của user trước khi chạy preflight.

### Alt D — Tạo một venv riêng trong `tmp_path`, cài package vào đó, dùng nó làm `python_binary`
**Bác bỏ:** Phức tạp, chậm (tạo venv mới mỗi test ~3-5s × 3 test = 10-15s overhead), và không phản ánh cách production chạy. Production chạy từ `/opt/ids_ml_new/.venv/bin/python`, trong đó package đã cài. Fixture A.1 mô phỏng điều đó trung thực hơn.

### Alt E — Sửa service unit về dạng `python ids/ops/live_sensor_preflight.py`
**Bác bỏ mạnh:** Phá vỡ packaging contract. Khi package được cài vào site-packages, `ids/ops/live_sensor_preflight.py` không có trong filesystem tại `/opt/ids_ml_new/`. Dạng `-m` là dạng đúng cho installable package.

---

## 4. Risk Map

| Rủi ro | Mức độ | Giảm thiểu |
|--------|--------|------------|
| Fixture cài editable gây xung đột với dependency đã cài | LOW | `pip install -e .` không đụng các dependency đã cài; chỉ thêm `ids-ml-new` vào site-packages |
| Session fixture chạy quá sớm, trước khi REPO_ROOT được detect | LOW | Dùng `Path(__file__).resolve().parents[1]` trực tiếp từ `conftest.py`, pattern đã có trong codebase |
| CI không có quyền ghi vào site-packages | LOW | CI chạy với venv riêng, luôn có quyền ghi. Local dev cũng thường chạy trong venv |
| pip install fail do network / mirror | LOW | `pip install -e .` không cần network nếu không có dependency mới; tất cả deps đã cài sẵn |
| Test khác bị break do package đã cài | VERY LOW | Kiểm tra trong validating bằng cách chạy full suite sau fix |
| Assertion B khớp false positive với chuỗi khác | VERY LOW | Chuỗi `-m ids.ops.live_sensor_preflight` rất đặc thù, không xuất hiện ở đâu khác trong file service |

**Overall risk: LOW.** Phù hợp Quick Mode.

---

## 5. Proposed File Structure

```
Sẽ sửa (2 tệp):
├── tests/conftest.py
│   └── + _ensure_editable_install (session autouse fixture, ~20 dòng)
└── tests/runtime/test_ids_live_sensor.py
    └── Sửa 1 dòng (line 513)

Sẽ đọc để verify (không sửa):
├── ids/ops/module_validation.py             (xác nhận contract)
├── tests/ops/test_ids_operator_console_ops.py  (xác nhận 3 test fail chung nguyên nhân)
├── deploy/systemd/ids-live-sensor.service   (xác nhận service unit đã đúng)
└── pyproject.toml                            (xác nhận package name = ids-ml-new)
```

---

## 6. Institutional Learnings Applied

- **[20260403] Bind Privileged Bootstrap Execution To The Validated Interpreter Contract** → Approach bảo toàn toàn bộ hợp đồng `-I` + CWD + env scrub trong `_run_module_check`.
- **[20260403] Prove Editable Installs In A Scrubbed Environment** → Fixture A.1 thực thi pattern này: test chạy trong môi trường mà package thật sự được cài, không dựa vào `sys.path` warm.
- **[20260330] Pin Multi-Token Runtime Contracts With End-To-End Tokenization Tests** → Fix B chỉ sửa 1 dòng, giữ nguyên 14 assertion tokenization khác.
- **[20260331] Treat Compatibility Wrappers As Executable Contracts** → Fixture session đảm bảo test exercise wrapper/packaging contract giống CI thật.

---

## 7. Risk Classification: **LOW**

- Pattern exists in codebase (session fixtures, install checks)
- Variation không đáng kể (chỉ là thêm một fixture chuẩn)
- Blast radius = 2 file
- Reversible hoàn toàn
- Không có architecture change, auth flow, data model change

→ **Proceed to Quick Mode planning without HIGH-risk spike.**
