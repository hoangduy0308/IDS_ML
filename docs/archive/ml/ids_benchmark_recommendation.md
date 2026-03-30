# Khuyến nghị dataset và hướng benchmark cho đề tài IDS dùng Machine Learning

> Status: historical planning memo. Tài liệu này phản ánh giai đoạn chọn dataset và định hướng benchmark ban đầu. Kết luận chuẩn hiện tại nên đọc ở [training_benchmark_results.md](F:/Work/IDS_ML_New/docs/training_benchmark_results.md), [scaling_experiment_results.md](F:/Work/IDS_ML_New/docs/scaling_experiment_results.md), [scaling_threshold_analysis.md](F:/Work/IDS_ML_New/docs/scaling_threshold_analysis.md), và [final_model_decision.md](F:/Work/IDS_ML_New/docs/final_model_decision.md).

> Historical note: tài liệu này là ghi chú định hướng ở giai đoạn đầu để chọn dataset và hướng benchmark. Kết luận cuối cùng của repo hiện đã được thay thế bởi [training_benchmark_results.md](F:/Work/IDS_ML_New/docs/training_benchmark_results.md), [scaling_experiment_results.md](F:/Work/IDS_ML_New/docs/scaling_experiment_results.md), và [final_model_decision.md](F:/Work/IDS_ML_New/docs/final_model_decision.md). Không dùng file này làm nguồn kết luận model cuối.

## Mục tiêu

Mục tiêu của đề tài là xây dựng một hệ thống IDS dựa trên machine learning, vì vậy lựa chọn bộ dữ liệu cần ưu tiên:

- đủ mới để phản ánh tốt hơn lưu lượng và kiểu tấn công hiện nay,
- phù hợp với bài toán IDS thực tế,
- có thể huấn luyện nhiều mô hình để so sánh,
- và thuận tiện để đưa mô hình vào một pipeline phát hiện xâm nhập.

## Kết luận đã chốt

Dataset chính cho đề tài là `CIC IoT-DIAD 2024`.

Đây là lựa chọn phù hợp nhất ở thời điểm hiện tại vì cân bằng được giữa:

- tính mới,
- mức độ phù hợp với bài toán IDS,
- khả năng huấn luyện nhiều mô hình machine learning,
- và khả năng đưa mô hình vào một hệ thống phát hiện xâm nhập thực tế.

## Lý do chọn `CIC IoT-DIAD 2024`

### 1. Bộ dữ liệu mới và còn giá trị học thuật

`CIC IoT-DIAD 2024` là bộ dữ liệu mới hơn rõ rệt so với các bộ thường bị dùng lặp lại như `KDD99`, `NSL-KDD`, `UNSW-NB15` hay `CSE-CIC-IDS2018`.

Điều này quan trọng vì trong đề tài IDS hiện nay, vấn đề lớn không nằm ở việc chọn thật nhiều mô hình phức tạp, mà nằm ở việc dataset có còn phản ánh được ngữ cảnh tấn công hiện đại hay không.

### 2. Phù hợp trực tiếp với bài toán IDS

Bộ dữ liệu này được thiết kế cho các bài toán:

- anomaly detection,
- attack classification,
- device identification kết hợp phát hiện bất thường.

Đối với đề tài của bạn, phần phù hợp nhất là nhánh:

- `Anomaly Detection - Flow Based features`

Đây là đúng dạng dữ liệu dùng cho pipeline IDS thực tế:

`network traffic -> flow feature extraction -> machine learning model -> cảnh báo`

### 3. Phù hợp để huấn luyện nhiều mô hình ML

Nhánh `flow-based features` ở dạng `CSV/tabular`, nên rất phù hợp để so sánh các họ mô hình phổ biến:

- `Logistic Regression`
- `Linear SVM`
- `Random Forest`
- `XGBoost`
- `LightGBM`
- `MLP`

Điều này giúp benchmark rõ ràng, dễ báo cáo, và không làm đề tài bị lệch sang các mô hình deep quá phức tạp nhưng chưa chắc phù hợp với dữ liệu tabular.

### 4. Phù hợp với định hướng triển khai hệ thống

Nếu mục tiêu cuối cùng là đưa mô hình vào một hệ thống IDS, dữ liệu flow-based là hướng thực tế hơn so với các dataset thiên về malware behavior hoặc dữ liệu quá dị thể.

Với `CIC IoT-DIAD 2024`, bạn có thể xây dựng một pipeline gần với triển khai thật:

1. thu thập traffic,
2. trích xuất flow features,
3. chuẩn hóa dữ liệu,
4. đưa vào mô hình,
5. sinh cảnh báo tấn công.

## Vì sao không chọn các dataset khác làm dataset chính

### `KDD99` và `NSL-KDD`

- quá cũ,
- không còn phù hợp để làm dataset chính cho một đề tài IDS hiện nay,
- chỉ nên nhắc đến như mốc lịch sử.

### `UNSW-NB15`

- vẫn hữu ích cho baseline học thuật,
- nhưng không còn đủ mới để làm điểm nhấn chính của đề tài.

### `CSE-CIC-IDS2018`

- vẫn là bộ dữ liệu tốt,
- nhưng hiện nay phù hợp hơn cho đối chiếu hoặc baseline thay vì làm lựa chọn trung tâm nếu bạn cần nhấn mạnh tính mới.

### `DataSense IIoT 2025`

- mới hơn,
- nhưng thiên về bối cảnh IIoT đa nguồn và phức tạp hơn,
- phù hợp nếu đề tài của bạn nhắm riêng vào môi trường công nghiệp hoặc sensor-network đồng bộ,
- không gọn bằng `CIC IoT-DIAD 2024` cho một benchmark ML IDS thông thường.

### `CIC-YNU-IoTMal 2026`

- rất mới,
- nhưng nghiêng về malware behavior dataset hơn là bộ dữ liệu chuẩn để làm benchmark NIDS/flow-based IDS.

## Trạng thái hiện tại trong workspace

Dataset đã được tải về thư mục:

- `F:\Work\IDS_ML_New\CIC-IoT-DIAD-2024`

Phần đã tải là nhánh phù hợp trực tiếp cho IDS:

- `Anomaly Detection - Flow Based features`

Thông tin tải về hiện tại:

- số lượng file: `133`
- tổng dung lượng: khoảng `13.65 GB`

## Hướng benchmark nên dùng với dataset này

Vì trọng tâm chính là dataset chứ không phải chạy theo mô hình quá phức tạp, benchmark nên giữ ở mức gọn nhưng đủ mạnh:

### Nhóm baseline

- `Logistic Regression`
- `Random Forest`

### Nhóm ứng viên mạnh nhất trên dữ liệu tabular

- `XGBoost`
- `LightGBM`

### Nhóm kiểm tra bổ sung

- `MLP`

Với dữ liệu flow/tabular, khả năng cao hướng tốt nhất vẫn là `XGBoost` hoặc `LightGBM`.

## Giao thức đánh giá khuyến nghị

### Chia dữ liệu

Không nên chia ngẫu nhiên theo từng dòng nếu có thể tránh.

Ưu tiên:

- chia theo scenario,
- chia theo file capture,
- hoặc chia theo nhóm tấn công.

### Kiểm soát leakage

- chỉ fit scaler trên tập train,
- chỉ xử lý sampling trên tập train,
- theo dõi duplicate records,
- ghi rõ cách làm sạch dữ liệu.

### Metric nên báo cáo

- `Macro F1`
- `Weighted F1`
- `Per-class Recall`
- `PR-AUC`
- `False Positive Rate`
- `Confusion Matrix`
- `Training time`
- `Inference time`

Nếu triển khai theo hướng nhị phân `benign` và `attack`, nên bổ sung:

- `TPR at fixed FPR`

## Định hướng triển khai tiếp theo

Thứ tự làm việc hợp lý cho đề tài:

1. đọc toàn bộ các file CSV trong nhánh `flow-based`,
2. kiểm tra schema, nhãn và mức độ mất cân bằng dữ liệu,
3. xây dựng pipeline tiền xử lý thống nhất,
4. huấn luyện các mô hình baseline và boosting,
5. so sánh kết quả,
6. chọn mô hình tối ưu để tích hợp vào hệ thống IDS.

## Nguồn tham khảo chính

- UNB CIC IoT-DIAD 2024: https://www.unb.ca/cic/datasets/iot-diad-2024.html
- Scikit-learn documentation: https://scikit-learn.org/stable/
- Benchmark study 2025: https://link.springer.com/article/10.1007/s10489-025-06422-4
