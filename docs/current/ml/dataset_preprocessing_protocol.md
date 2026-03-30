# Dataset Preprocessing Protocol

## Mục tiêu

Tài liệu này mô tả protocol tiền xử lý dùng để biến nhánh `Anomaly Detection - Flow Based features` của `CIC IoT-DIAD 2024` thành bộ dữ liệu nhị phân phục vụ cho đồ án IDS:

- lớp `Benign`
- lớp `Attack`

Đây là tài liệu chuẩn để giải thích phần dữ liệu và tránh phải suy luận lại từ code hoặc manifest rời.

## Nguồn dữ liệu đầu vào

- input root: `F:\Work\IDS_ML_New\CIC-IoT-DIAD-2024\Anomaly Detection - Flow Based features`
- pipeline chính: [scripts/preprocess_iot_diad.py](F:/Work/IDS_ML_New/scripts/preprocess_iot_diad.py)
- báo cáo manifest sau khi chạy: [artifacts/cic_iot_diad_2024_binary/manifests/cleaning_report.json](F:/Work/IDS_ML_New/artifacts/cic_iot_diad_2024_binary/manifests/cleaning_report.json)

## Mục tiêu đầu ra

Pipeline sinh bộ dữ liệu đã freeze tại:

- [artifacts/cic_iot_diad_2024_binary](F:/Work/IDS_ML_New/artifacts/cic_iot_diad_2024_binary)

Các file split chính:

- `clean/train.parquet`
- `clean/val.parquet`
- `clean/test.parquet`
- `clean/ood_attack_holdout.parquet`

Các manifest đi kèm:

- `manifests/file_manifest.csv`
- `manifests/quarantine_manifest.csv`
- `manifests/feature_columns.json`
- `manifests/cleaning_report.json`

## Luật kiểm tra file đầu vào

Mỗi CSV đầu vào phải thỏa:

- đúng `84` cột
- cột đầu tiên là `Flow ID`

Các file lỗi header hoặc nằm trong vùng đã biết có vấn đề sẽ bị đưa sang `quarantine_manifest.csv`, không cho đi tiếp vào pipeline chính.

## Gán nhãn

Nhãn được suy ra từ cấu trúc thư mục dataset:

- thư mục `Benign` được map thành `Benign`
- mọi họ tấn công còn lại được map thành `Attack`

Ngoài nhãn nhị phân, pipeline vẫn giữ metadata về họ tấn công (`attack_family`) để phục vụ phân tích sau này.

## Loại cột leakage

Các cột sau bị loại bỏ trước khi train:

- `Flow ID`
- `Src IP`
- `Dst IP`
- `Timestamp`
- `Label`

Mục tiêu là tránh leakage từ các định danh hoặc nhãn gốc không nên xuất hiện trong feature space của mô hình IDS.

## Làm sạch dữ liệu

Các bước clean chính:

1. ép toàn bộ feature còn lại sang numeric
2. thay `inf/-inf` thành `NaN`
3. loại toàn bộ dòng còn `NaN/inf`
4. giữ metadata truy vết riêng
5. dedupe exact rows bằng hash bucket

Kết quả đã ghi nhận:

- `rows_before_clean = 27,783,340`
- `rows_after_clean_before_dedupe = 27,693,632`
- `rows_dropped_nan_inf = 89,708`
- `rows_removed_duplicates = 14,162`
- `rows_after_dedupe = 27,679,470`

## Chiến lược chia split

Pipeline không chia ngẫu nhiên theo từng dòng. Thay vào đó, nó chia theo `source_file` trong từng họ dữ liệu để giảm rủi ro leakage giữa các split.

Thiết lập hiện tại:

- `seed = 42`
- `hash_buckets = 256`
- tỷ lệ mục tiêu cho các họ in-distribution:
  - `train = 70%`
  - `val = 15%`
  - `test = 15%`

Hai họ được giữ riêng làm out-of-distribution attack holdout:

- `BruteForce`
- `Recon`

Điều này giúp đánh giá khả năng tổng quát hóa của mô hình trên tấn công không dùng trong train.

## Feature set cuối

Sau khi tạo stage parquet và tính phương sai trên train split, pipeline loại các cột zero-variance sau:

- `Bwd PSH Flags`
- `Fwd URG Flags`
- `Bwd URG Flags`
- `URG Flag Count`
- `Fwd Bytes/Bulk Avg`
- `Fwd Packet/Bulk Avg`
- `Fwd Bulk Rate Avg`

Feature set cuối cùng còn:

- `72` feature

Danh sách chuẩn được lưu tại:

- [artifacts/cic_iot_diad_2024_binary/manifests/feature_columns.json](F:/Work/IDS_ML_New/artifacts/cic_iot_diad_2024_binary/manifests/feature_columns.json)

## Phân bố dữ liệu cuối

| Split | Rows | Attack | Benign |
|---|---:|---:|---:|
| `train` | `18,679,445` | `18,457,115` | `222,330` |
| `val` | `4,410,064` | `4,318,898` | `91,166` |
| `test` | `4,145,539` | `4,061,119` | `84,420` |
| `ood_attack_holdout` | `444,422` | `444,422` | `0` |

## Cách chạy lại pipeline

```powershell
python -m scripts.preprocess_iot_diad `
  --input-root "F:\Work\IDS_ML_New\CIC-IoT-DIAD-2024\Anomaly Detection - Flow Based features" `
  --output-root "F:\Work\IDS_ML_New\artifacts\cic_iot_diad_2024_binary" `
  --task binary `
  --seed 42 `
  --chunk-size 100000 `
  --hash-buckets 256
```

## Điều cần nêu trong báo cáo sau này

- dữ liệu được chia theo `source_file`, không chia random theo từng dòng
- có loại cột leakage rõ ràng
- có làm sạch `NaN/inf`
- có loại duplicate exact rows
- có giữ riêng `ood_attack_holdout` để kiểm tra khả năng tổng quát hóa

Nhờ vậy, phần thực nghiệm phía sau có cơ sở chặt hơn cho một đồ án IDS dùng ML.
