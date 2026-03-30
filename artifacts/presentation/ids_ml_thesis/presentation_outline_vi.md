# Đề cương thuyết trình - Hệ thống IDS dựa trên Machine Learning

## Slide 1 - Tiêu đề
- Giới thiệu đề tài và ba trụ cột: dữ liệu, mô hình, runtime IDS.

## Slide 2 - Bài toán và mục tiêu
- IDS cần phát hiện attack nhưng vẫn phải giữ false positive thấp.
- Mục tiêu kép: chọn model tốt và đưa model vào hệ thống có thể vận hành.

## Slide 3 - Toàn cảnh repo
- Chia repo thành 4 lớp: data, experiments, runtime, operations.
- Nhấn mạnh đây là hệ thống IDS hoàn chỉnh, không chỉ là notebook benchmark.

## Slide 4 - Dữ liệu và tiền xử lý
- Lý do chọn CIC IoT-DIAD 2024.
- Các bước clean: gán nhãn, bỏ leakage, ép numeric, loại NaN/inf/duplicate, freeze split.
- Nhắc 72 feature và 4 split train/val/test/OOD.

## Slide 5 - Protocol thực nghiệm
- Benchmark 5 model -> tuning -> promotion -> scaling -> full-data -> threshold -> final decision.
- Test không được dùng để chọn hyperparameter.

## Slide 6 - Benchmark vòng đầu
- F1 của nhiều model đều cao, nhưng FPR mới là metric quyết định.
- CatBoost có FPR thấp nhất; Random Forest có F1 cao nhất trong nhóm hợp lệ.
- LogReg và MLP bị loại vì FPR quá cao.

## Slide 7 - Scaling experiment và chọn model
- Giải thích vì sao scaling quan trọng để tránh kết luận vội.
- Random Forest mạnh về F1 nhưng FPR tăng rõ khi scale.
- CatBoost full-data là điểm cân bằng để deploy.

## Slide 8 - Threshold và metric cuối cùng
- Final operating point: CatBoost full-data, threshold 0.5.
- Threshold 0.475 chỉ tăng F1/OOD recall rất ít nhưng FPR tăng thêm.
- Lập luận: ưu tiên dễ giải thích, dễ tái lập, ít nhiễu.

## Slide 9 - Final model bundle
- Trình bày gói model sẵn sàng vận hành: model, schema, manifest, metrics, training summary, model card.
- Giải thích verify -> promote -> rollback.

## Slide 10 - Realtime pipeline
- Adapter -> contract check -> micro-batch -> inferencer -> sinks.
- Phân biệt model prediction với schema anomaly.

## Slide 11 - Live sensor
- dumpcap -> flow bridge -> adapter/runtime -> local sink.
- Nhắc phạm vi V1: single host, single NIC, TCP/UDP, local outputs.

## Slide 12 - Operator console và deployment
- Console có dashboard, anomalies, reports, API, readiness.
- Notification worker tách riêng, có backup/restore và runbook same-host.

## Slide 13 - Validation và demo
- Repo có 28 test modules, demo fixtures, dry-run bundle, deploy artifacts.
- Đây là bằng chứng hệ thống đã được harden.

## Slide 14 - Hạn chế và hướng phát triển
- OOD recall còn hạn chế.
- V1 chưa có SIEM bus, fleet rollout, drift adaptation.
- Đề xuất các hướng mở rộng tiếp theo.

## Slide 15 - Kết luận
- Protocol thực nghiệm chặt.
- Model chốt phù hợp IDS thực tế.
- Stack runtime và vận hành đã hiện thực được.
