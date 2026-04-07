# Phase Plan — Fix Failing Tests (M1)

**Feature:** fix-failing-tests-m1
**Mode:** Quick Mode (single phase, single story)
**Created:** 2026-04-04

---

## Feature Summary

Bốn test trong bộ test 590 test đang fail do hai nguyên nhân độc lập: ba test preflight thất bại vì gói `ids-ml-new` chưa được cài editable vào site-packages của interpreter, và một test service unit assert đường dẫn file script cũ đã không còn trong systemd unit hiện tại. Feature này sửa test drift mà không sửa bất kỳ code production nào và không làm suy yếu các hợp đồng bảo mật.

Sau khi landing, chạy `python -m pytest tests/ -q` sẽ báo `590 passed, 0 failed`, mở khoá công việc M2 (CI/CD pipeline).

---

## Phases

### Phase 1: Fix test drift và xác minh 590/590 pass

**What changes in real life:**
Bộ test Python chạy sạch 590/590 trên cả môi trường local (không cài package trước) và môi trường CI (có cài package). Developer có thể chạy `pytest` và thấy tất cả xanh mà không cần biết trước về yêu cầu `pip install -e .`.

**Why this phase exists first (và là duy nhất):**
Đây là Quick Mode — chỉ có một phase vì phạm vi đã hẹp tối đa. Không có gap khác cần đóng. Không có phase 2.

**Demo walkthrough:**
1. Clone/reset repo về trạng thái sạch.
2. Chạy `python -m pip uninstall -y ids-ml-new` (đảm bảo package chưa cài).
3. Chạy `python -m pytest tests/ -q --tb=line`.
4. Quan sát output cuối: `590 passed in <N>s`.
5. Chạy `git diff ids/ deploy/` → output rỗng (chứng minh không code production / không service unit nào bị đụng).
6. Chạy `git diff tests/conftest.py tests/runtime/test_ids_live_sensor.py` → chỉ thấy 2 thay đổi: fixture mới + 1 dòng assertion.

**What this phase unlocks:**
- M2 (CI/CD pipeline) — có thể thêm GitHub Actions workflow chạy `pytest` với niềm tin 590/590 sẽ pass.
- Các phase tương lai trong các feature audit khác có base test suite sạch để so sánh khi review.

**Out of scope:**
- Không thêm test mới
- Không refactor module_validation.py
- Không sửa service unit
- Không cập nhật docs
- Không đụng các mục H/M/L khác trong BACKLOG.md

**Pivot signals:**
- Nếu sau khi áp dụng Fix A, vẫn có test fail với lỗi khác → stop, mở debugging skill, không tiếp tục.
- Nếu fixture session gây hồi quy ≥1 test khác → stop, phân tích, có thể cần điều chỉnh scope fixture.
- Nếu `pip install -e .` fail trên môi trường dev → không phải scope M1, pause và surface.

---

## Stories Inside Phase 1

### Story 1: Đảm bảo package ids-ml-new được cài editable trước khi test preflight chạy, và sửa 1 dòng assertion service unit

**What happens:**
Thêm một fixture session `autouse=True` vào `tests/conftest.py` đảm bảo `ids-ml-new` được cài editable (idempotent — no-op nếu đã cài). Đồng thời sửa assertion trong `test_service_unit_keeps_preflight_and_stdout_journal_contract` từ `"ids_live_sensor_preflight.py"` thành `"-m ids.ops.live_sensor_preflight"`.

**Why now:**
Đây là thay đổi tối thiểu đóng trọn vẹn exit state của Phase 1. Hai fix đi chung trong một story vì cả hai đều là test drift, cùng phạm vi sửa, và verification phải được chạy một lần duy nhất (`pytest tests/ -q`).

**Exit state advance:**
Sau khi story này xong, `pytest tests/ -q` báo 590/590 pass. Exit state của phase = exit state của story.

**Done looks like:**
- `tests/conftest.py` có fixture `_ensure_editable_install(autouse=True, scope="session")` hoạt động idempotent
- `tests/runtime/test_ids_live_sensor.py` line 513 chứa `"-m ids.ops.live_sensor_preflight"`
- `python -m pytest tests/ -q` báo cáo `590 passed, 0 failed`
- `git diff ids/ deploy/ pyproject.toml requirements.txt` rỗng
- Commit duy nhất với message rõ ràng

---

## Current Phase Selection

Phase hiện tại = **Phase 1** (cũng là phase duy nhất).

Sẽ prepare: Phase 1 contract và story map.

---

## Approval Gate

Đây là HARD-GATE. Phase plan trên cần approval trước khi tiến hành Phase 4-5-7 (contract, story map, beads).

**Please review và confirm:**

1. Feature summary đúng chứ? (sửa 4 test drift, không động code production)
2. Phase 1 là đủ hay cần chia nhỏ hơn? (tôi nghĩ không — story quá nhỏ để tách)
3. Bạn đồng ý bỏ qua Phase 2+ vì không có gap nào khác? (có phải chờ M2 ở feature khác)
4. Bạn đồng ý tiếp tục prepare Phase 1 contract + story map + beads?

Nếu có bất kỳ quan ngại nào về Approach, Discovery, hoặc CONTEXT → báo tôi trước khi tôi tạo beads.
