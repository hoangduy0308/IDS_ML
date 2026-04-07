# Phase 1 Story Map — Fix Test Drift

**Feature:** fix-failing-tests-m1
**Phase:** 1
**Mode:** Quick Mode (1 story)
**Created:** 2026-04-04

---

## Story Inventory

| # | Story | Beads | Unlock |
|---|-------|-------|--------|
| 1 | Sửa test drift: thêm fixture editable install + sửa 1 dòng assertion service unit | TBD (tạo bằng `br create`) | Phase 1 exit state |

---

## Story 1: Sửa test drift (editable install fixture + assertion update)

### What Happens
Worker sẽ thực hiện ba thay đổi được gộp trong một commit duy nhất vì cả ba đều cần thiết để đạt exit state "590/590 pass":

1. **Thêm session fixture vào `tests/conftest.py`:**
   - Fixture name: `_ensure_editable_install`
   - Scope: `session`
   - Autouse: `True`
   - Logic:
     ```python
     import importlib.metadata
     import subprocess
     import sys
     from pathlib import Path

     import pytest

     _REPO_ROOT = Path(__file__).resolve().parents[1]

     @pytest.fixture(scope="session", autouse=True)
     def _ensure_editable_install() -> None:
         try:
             importlib.metadata.distribution("ids-ml-new")
             return  # already installed, no-op
         except importlib.metadata.PackageNotFoundError:
             pass
         result = subprocess.run(
             [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
             cwd=_REPO_ROOT,
             capture_output=True,
             text=True,
         )
         if result.returncode != 0:
             raise RuntimeError(
                 "Failed to install ids-ml-new as editable package.\n"
                 f"stdout: {result.stdout}\n"
                 f"stderr: {result.stderr}"
             )
         try:
             importlib.metadata.distribution("ids-ml-new")
         except importlib.metadata.PackageNotFoundError as exc:
             raise RuntimeError(
                 "pip install -e . reported success but ids-ml-new still not importable"
             ) from exc
     ```

2. **Sửa assertion trong `tests/runtime/test_ids_live_sensor.py` line 513:**
   - Từ: `assert "ids_live_sensor_preflight.py" in content`
   - Sang: `assert "-m ids.ops.live_sensor_preflight" in content`
   - Giữ nguyên tất cả 14 assertion khác trong cùng test function.

3. **Verify:**
   - Worker chạy `python -m pytest tests/ -q` và xác nhận output `590 passed`.
   - Worker chạy `git diff ids/ deploy/ pyproject.toml requirements.txt` và xác nhận output rỗng.

### Why This Story Happens Now
Đây là story duy nhất và cũng là story đầu tiên. Phase 1 exit state chỉ được đạt khi cả ba thay đổi cùng có mặt. Tách thành hai story riêng sẽ tạo ra một trạng thái trung gian mà pytest vẫn đỏ, và phải chạy pytest hai lần (waste).

### What Part Of Exit State This Advances
Đóng trọn vẹn exit state. Story 1 = Phase 1.

Observable checks ánh xạ tới exit state:
- Fixture hoạt động → 3 test preflight pass → exit check #1
- Assertion update → 1 test service unit pass → exit check #1
- `git diff` check → exit checks #2-#6
- `pip show ids-ml-new` → exit check #7
- Re-run pytest → exit check #8 (idempotency)

### What This Creates
- `tests/conftest.py`: thêm ~35 dòng (import + fixture)
- `tests/runtime/test_ids_live_sensor.py`: sửa 1 dòng

### What This Unlocks
- Phase 1 exit state đạt → Feature hoàn thành → Phase compounding (nếu chạy Go Mode) hoặc đóng feature (nếu Quick Mode)
- Story này cũng unlock M2 (có thể bắt đầu CI/CD work với confidence)

### Done Looks Like

**Hard checks:**
- [ ] `python -m pytest tests/ -q` trả về exit code 0 và output `590 passed`
- [ ] `git diff ids/` rỗng
- [ ] `git diff deploy/` rỗng
- [ ] `git diff pyproject.toml requirements.txt` rỗng
- [ ] `git diff --stat tests/conftest.py tests/runtime/test_ids_live_sensor.py` hiển thị chỉ 2 file
- [ ] `python -m pip show ids-ml-new` trả về package info với Name: ids-ml-new
- [ ] Chạy lại `python -m pytest tests/ -q` lần thứ hai trong cùng venv → vẫn 590 passed, không có lỗi fixture

**Soft checks:**
- [ ] Fixture có docstring giải thích lý do tồn tại (ref: critical-pattern 20260403)
- [ ] Không có `print()` hay `logging` leak trong fixture
- [ ] Fixture không tạo thêm file trong repo (không để lại `.pip-install-cache` hay tương tự)
- [ ] Commit message mô tả ngắn gọn: "test(m1): ensure editable install fixture + fix service unit assertion"

---

## Story-To-Bead Mapping

| Story | Bead IDs | Status |
|-------|----------|--------|
| Story 1 | `ids_ml_new-9wmb.1` (parent: epic `ids_ml_new-9wmb`) | open |

Trace: `feature fix-failing-tests-m1 → Phase 1 → Story 1 → ids_ml_new-9wmb.1`

---

## Dependencies Between Stories

Không có — chỉ 1 story.

---

## Institutional Learnings Embedded In Stories

- **[20260403] Bind Privileged Bootstrap Execution To The Validated Interpreter Contract** → Fixture phải dùng `sys.executable` (cùng interpreter pytest đang chạy), không tạo venv mới, không override `python_binary` trong test config.
- **[20260403] Prove Editable Installs In A Scrubbed Environment** → Fixture phải verify sau khi install bằng cách gọi lại `importlib.metadata.distribution(...)` (không chỉ tin vào pip exit code).
- **[20260330] Pin Multi-Token Runtime Contracts** → Fix B tuyệt đối không xóa các assertion khác trong cùng test function.
- **[20260331] Treat Compatibility Wrappers As Executable Contracts** → Fixture đảm bảo test chạy trong môi trường giống CI (package thật sự cài), không dựa vào path hack.
