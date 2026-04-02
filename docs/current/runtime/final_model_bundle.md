# Gói Model Cuối Cùng

## Mục tiêu

Model cuối cùng không còn là tập hợp file rời rạc trong `artifacts`, mà là một bundle có contract versioned để runtime, preflight, và operator workflow cùng đọc theo một chuẩn duy nhất.

Canonical command surfaces:

- `ids-package-final-model` (`ml_pipeline.packaging.package_final_model`)
- `ids-inference` (`ids.runtime.inference`)
- `ids-model-bundle-manage` (`ids.ops.model_bundle_manage`)

Compatibility wrappers dưới `scripts/*` vẫn được giữ để tương thích, nhưng runbook vận hành dùng các installed commands canonical ở trên.

## Bundle nằm ở đâu

Bundle production được ship trong checkout dưới:

- `/opt/ids_ml_new/artifacts/final_model/catboost_full_data_v1`

Runtime production không đọc bundle bằng cách trỏ tay vào `model.cbm` hay `feature_columns.json`. Thay vào đó, runtime resolve bundle đang active qua activation record host-local:

- `/var/lib/ids-live-sensor/active_bundle.json`

Activation record này trỏ tới đúng một bundle đang active và giữ thêm metadata rollback về bundle known-good trước đó.

## Bundle gồm gì

Nội dung bundle:

- `model.cbm`
- `feature_columns.json`
- `model_bundle.json`
- `metrics.json`
- `training_summary.json`
- `MODEL_CARD.md`

## Ý nghĩa từng file

### `model.cbm`

Artifact mô hình `CatBoost full-data` đã được chốt.

### `feature_columns.json`

Schema canonical của feature set mà inference contract hiện tại chấp nhận.

### `model_bundle.json`

Đây là manifest versioned của bundle. Từ `manifest_version = 2`, file này là production contract chính thức cho:

- vị trí model artifact
- vị trí feature schema
- threshold vận hành
- nhãn `Attack/Benign`
- provenance cơ bản
- compatibility metadata để chứng minh bundle khớp với feature schema và inference contract hiện tại

Compatibility block hiện tại khóa:

- `feature_schema.kind = "feature_columns_json.v1"`
- `inference_contract.version = "ids_binary_classifier.v1"`
- `threshold_source = "bundle"`
- không cho phép external override cho `model_path`, `feature_columns_path`, hoặc `threshold`

Điều này có nghĩa là production runtime không được trộn bundle A với schema hoặc threshold ngoài bundle. Nếu không có activation record hợp lệ, canonical runtime entrypoints phải fail-closed thay vì ngầm rơi về raw artifacts.

### `metrics.json`

Tóm tắt metric cuối cùng cho model card hoặc báo cáo nhanh.

### `training_summary.json`

Thông tin train full-data gốc.

### `MODEL_CARD.md`

Tài liệu mô tả model cuối dưới dạng ngắn gọn, dễ tra cứu.

## Cách dựng lại bundle

```bash
ids-package-final-model
```

Lệnh này emit `model_bundle.json` theo contract versioned hiện tại.

## Cách verify và dùng bundle

### 1. Verify candidate bundle

```bash
ids-model-bundle-manage \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --json verify \
  --bundle-root /opt/ids_ml_new/artifacts/final_model/catboost_full_data_v1
```

Lệnh này chỉ kiểm tra compatibility contract của candidate bundle. Nó không mutate trạng thái active.

### 2. Dry-run inference trên cùng host

```bash
ids-inference \
  --bundle-root /opt/ids_ml_new/artifacts/final_model/catboost_full_data_v1 \
  --input-path /opt/ids_ml_new/artifacts/cic_iot_diad_2024_binary/clean/test.parquet \
  --output-path /opt/ids_ml_new/artifacts/demo/test_predictions_from_bundle.parquet \
  --limit 1000
```

Đây là same-host dry-run path để kiểm tra bundle mới có thể load, align schema, và score theo đúng inference contract trước khi promote.

### 3. Promote bundle đã verify

```bash
ids-model-bundle-manage \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --json promote \
  --bundle-root /opt/ids_ml_new/artifacts/final_model/catboost_full_data_v1
```

Promotion sẽ ghi lại bundle active mới bằng atomic replace. Nếu đã có bundle active trước đó, activation record cũng lưu `previous_bundle_*` để rollback.

### 4. Rollback về known-good trước đó

```bash
ids-model-bundle-manage \
  --activation-path /var/lib/ids-live-sensor/active_bundle.json \
  --json rollback
```

Rollback dùng cùng activation contract và cùng cơ chế atomic replace. Không có copy-based fallback.

## Vai trò của bundle trong realtime pipeline

Bundle là nguồn cấu hình chuẩn cho lớp realtime pre-model pipeline:

- `ids-realtime-pipeline` (`ids.runtime.realtime_pipeline`)
- [ids_realtime_pipeline_architecture.md](./ids_realtime_pipeline_architecture.md)

Trong pipeline hiện tại:

- `feature_columns.json` là contract của canonical model features
- `model_bundle.json` giữ threshold, label names, và compatibility metadata
- `model.cbm` là artifact scoring trung tâm
- `active_bundle.json` là entrypoint production duy nhất để runtime resolve bundle đang live

Lớp realtime chỉ được phép dùng bundle để:

- validate và align record vào canonical feature order
- build inferencer dùng lại logic batch hiện có
- chấm điểm các record hợp lệ

Lớp realtime không được phép:

- tự điền feature bị thiếu
- suy diễn feature mới
- dùng external `model_path`, `feature_columns_path`, hoặc threshold override để thay đổi semantics của bundle đang active

## Kết luận

Bundle final bây giờ là model package có thể vận hành production trên single host:

- có artifact, schema, threshold, metrics, và model card
- có manifest versioned và compatibility contract
- có explicit verify/promote/rollback flow
- có activation record để runtime fail-closed nếu bundle active bị sai hoặc không tương thích

Nó vẫn chưa phải control plane hay fleet rollout system, nhưng đã đủ để harden model lifecycle cho deployment hiện tại.
