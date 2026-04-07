# Discovery — Fix Failing Tests (M1)

## Institutional Learnings

4 critical patterns từ `history/learnings/critical-patterns.md` áp dụng trực tiếp:

### [20260403] Bind Privileged Bootstrap Execution To The Validated Interpreter Contract
**Feature:** ids-repo-installable-full-stack-packaging
**Tags:** [bootstrap, trust-boundary, security]

> "Preflight approval is meaningless if privileged bootstrap can still resolve code through a different interpreter, `cwd`, or inherited `PYTHON*` state. Future module-based bootstrap paths must run under the exact validated interpreter/env contract and ship contamination tests that prove approval and execution stay bound together."

**Áp dụng:** Đây chính xác là điều mà `_run_module_check` đang làm với `-I` + CWD khóa + env scrubbed. Ba test fail vì thử chạy trong môi trường chưa có package cài editable. **Không được làm suy yếu hợp đồng này.** Phải cài package thật thay vì nới lỏng subprocess validation.

### [20260403] Prove Editable Installs In A Scrubbed Environment That Cannot Fall Back To Warmed `__pycache__`
**Feature:** ids-repo-installable-full-stack-packaging
**Tags:** [packaging, editable-install, verification]

> "In-tree or already-warmed verification is not enough to prove an install contract because it can hide missing source files, templates, or package data. Future packaging work should always run a fresh editable-install proof that removes `__pycache__` dependence and asserts the real shipped module and asset payload exists."

**Áp dụng:** Test preflight đang gián tiếp kiểm tra install contract. Phải đảm bảo package thật sự có trong site-packages trước khi chạy test.

### [20260330] Pin Multi-Token Runtime Contracts With End-To-End Tokenization Tests
**Feature:** ids-flow-extractor-replacement
**Tags:** [systemd, shell, cli, testing]

> "This feature's follow-up review found that preserving a multi-token extractor command prefix in code and service units was not enough; the real risk lived in the tokenization chain across systemd, shell expansion, and argparse."

**Áp dụng:** Test `test_service_unit_keeps_preflight_and_stdout_journal_contract` chứa nhiều assertion tokenization quan trọng (`--dumpcap-binary`, `--extractor-command-prefix` không lặp lại, `shlex.split` chứng minh multi-token). **Tuyệt đối không xóa** các assertion tokenization; chỉ sửa 1 dòng preflight assertion.

### [20260331] Treat Compatibility Wrappers As Executable Contracts
**Feature:** repo-structure-rationalization
**Tags:** [wrappers, testing, compatibility, migration]

> "Wrapper stability is not real unless CI exercises those wrappers directly. Runtime, ops, and ML wrapper smoke coverage all had to be added after execution, costing a substantial review-fix wave."

**Áp dụng:** Củng cố lý do: test phải chạy trong môi trường có package cài đặt thật, giống CI sẽ làm. Fixture session cài editable chính là hành động tuân thủ pattern này.

---

## Codebase Topology

### Cấu trúc liên quan
```
F:/Work/IDS_ML_New/
├── pyproject.toml                 ← khai báo package ids-ml-new v0.1.0
├── tests/
│   ├── conftest.py                ← SẼ SỬA: thêm fixture session cài editable
│   ├── ops/
│   │   └── test_ids_operator_console_ops.py   ← 3 test fail, KHÔNG sửa
│   └── runtime/
│       └── test_ids_live_sensor.py            ← SẼ SỬA: 1 dòng assertion
├── ids/
│   ├── ops/
│   │   ├── module_validation.py              ← nguyên nhân gốc; KHÔNG sửa
│   │   └── operator_console_preflight.py     ← gọi module_validation; KHÔNG sửa
│   └── console/
│       └── server.py                         ← module được preflight kiểm tra
└── deploy/systemd/
    └── ids-live-sensor.service               ← service unit; KHÔNG sửa
```

### Contract boundary
`ids/ops/module_validation.py::_run_module_check` là security boundary. Nó:
- Chạy `python -I` (isolated mode — cờ `-I` bật ba thứ: ignore `PYTHONPATH`, ignore user site-packages, không thêm script dir vào `sys.path`)
- CWD = `python_binary.parent` (thư mục chứa executable, không phải CWD của caller)
- `env` loại bỏ mọi biến `PYTHON*` (PYTHONPATH, PYTHONHOME, PYTHONSTARTUP, v.v.)

Đây là hợp đồng "same interpreter contract" mà critical-pattern [20260403] yêu cầu. Không được nới lỏng.

### Test setup hiện tại
`tests/ops/test_ids_operator_console_ops.py::_make_preflight_config` set:
```python
"python_binary": Path(sys.executable).resolve()
```
Tức là dùng cùng interpreter pytest đang chạy. Hợp đồng: nếu pytest chạy bằng interpreter X, thì X phải có `ids-ml-new` trong site-packages. Điều này đúng trong CI nếu CI chạy `pip install -e .` trước test. Nhưng với developer local chạy pytest mà không cài package trước, test sẽ fail.

---

## Repository State

### Kiểm tra gói ids-ml-new
```
$ python -m pip show ids-ml-new
WARNING: Package(s) not found: ids-ml-new
```
→ **Không cài.** Pytest đang tìm thấy `ids` vì tình cờ có repo root trong `sys.path`, không phải qua site-packages.

### Test output thực tế
```
4 failed, 586 passed, 4 warnings in 749.29s (0:12:29)

FAILED tests/ops/test_ids_operator_console_ops.py::test_preflight_accepts_valid_contract
FAILED tests/ops/test_ids_operator_console_ops.py::test_preflight_rejects_missing_admin_bootstrap
FAILED tests/ops/test_ids_operator_console_ops.py::test_preflight_rejects_telegram_pairing
FAILED tests/runtime/test_ids_live_sensor.py::test_service_unit_keeps_preflight_and_stdout_journal_contract
```

Tất cả 3 test đầu cùng lỗi: `ValueError: app_module is not importable by python_binary: ids.console.server`

Test thứ 4: `AssertionError: assert 'ids_live_sensor_preflight.py' in '[Unit]\nDescription=...'`

### Service unit thực tế
```ini
ExecStartPre=/opt/ids_ml_new/.venv/bin/python -m ids.ops.live_sensor_preflight ...
```
→ Dùng form `-m module`, không dùng đường dẫn script.

### pyproject.toml packages
```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["ids*", "ml_pipeline*"]
```
→ Package discovery đúng. `pip install -e .` sẽ cài cả `ids` và `ml_pipeline` vào site-packages.

---

## Technical Constraints

1. **Không được phá security contract** của `_run_module_check` (`-I`, CWD khoá, env scrub).
2. **Không được sửa service unit file** — nó đã đúng.
3. **pytest 8.3.5** được pin trong requirements — fixture API stable.
4. **Python 3.11+** được yêu cầu trong pyproject.
5. **Test suite phải chạy được trên cả Windows và Linux** (dev machine hiện tại là Windows; CI Linux). `pip install -e .` hoạt động trên cả hai.
6. **Không thay đổi dependencies** — không thêm package mới vào `requirements.txt`.
7. **Fixture phải idempotent** — chạy nhiều lần (ví dụ pytest --cache-clear rồi chạy lại) không được gây hỏng.
8. **Không tạo side effect môi trường** — fixture cài editable vào site-packages của interpreter hiện tại là cần thiết, nhưng phải là hành vi test documented.

---

## External Research

Không cần. Đây là bug test đơn giản với nguyên nhân gốc đã xác định từ code nội bộ và critical patterns.

---

## Summary of Discovery

- Nguyên nhân gốc đã rõ cho cả 2 nhóm lỗi.
- 4 critical patterns áp dụng trực tiếp.
- Phạm vi file sửa = 2 file.
- Phạm vi file KHÔNG sửa = security boundary + service unit + test logic chính.
- Không có gray area, không cần exploring bổ sung.
