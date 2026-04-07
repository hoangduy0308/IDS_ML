# Nội dung slide — IDS ML Thesis (25 slides)
> Trạng thái: đang làm — từng slide một

---

## SLIDE 01 — Title

**Layout:** 1 cột, căn trái, nền tối

```
[HEADER]
  Logo HUTECH (trái) | Logo QS Stars + 30 năm (phải)
  ─────────────────────── đường vàng ──────────────────────

[BODY]
  ──── đường vàng dày ────────────────────────────────────

  Xây dựng Hệ thống
  Phát hiện Xâm nhập Mạng
  bằng Học Máy
  (cỡ chữ lớn, trắng, đậm)

  ──── đường vàng mỏng ───────────────────────────────────

  LUẬN VĂN TỐT NGHIỆP · ĐẠI HỌC CÔNG NGHỆ TP.HCM · KHOA CNTT · HK II / 2024–2025
  (nhỏ, xám)

  [CIC IoT-DIAD 2024]   [CatBoost]   [Runtime IDS Pipeline]
  (3 pill box viền vàng, chữ vàng)

  ┌──────────────────────────────────────────────────────┐
  │ Người thực hiện:  ________________________________   │
  │ Giảng viên hướng dẫn:  ___________________________  │
  │ Học kỳ II · Năm học 2024–2025                        │
  └──────────────────────────────────────────────────────┘
```

---

## SLIDE 02 — Mục lục

**Layout:** 2 cột × 4 hàng, mỗi ô là 1 block

```
[HEADER]  (như mọi slide)
  Section label: NỘI DUNG TRÌNH BÀY

[BODY — 2 cột]

  Cột trái:                           Cột phải:
  ┌──────────────────────────┐        ┌──────────────────────────┐
  │ 01  Vấn đề nghiên cứu   │        │ 02  Mục tiêu & PP        │
  │     IoT · signature gap  │        │     3 mục tiêu · pipeline│
  │                 slide 3 →│        │                 slide 4–5│
  └──────────────────────────┘        └──────────────────────────┘
  ┌──────────────────────────┐        ┌──────────────────────────┐
  │ 03  Dữ liệu              │        │ 04  Thực nghiệm ML       │
  │     CIC IoT-DIAD · tiền  │        │     Benchmark · Tuning   │
  │     xử lý               │        │     Threshold · Model    │
  │                 slide 6–7│        │                 slide 8–13│
  └──────────────────────────┘        └──────────────────────────┘
  ┌──────────────────────────┐        ┌──────────────────────────┐
  │ 05  Kiến trúc Runtime    │        │ 06  Kịch bản & Demo      │
  │     4 thành phần         │        │     Attack · Luồng xử lý │
  │     Adapter→Console      │        │     Kết quả · Quarantine │
  │                slide 14–16│       │                slide 17–21│
  └──────────────────────────┘        └──────────────────────────┘
  ┌──────────────────────────┐
  │ 07  Đánh giá & Tổng kết  │
  │     Kiểm thử · Giới hạn  │
  │     Hướng PT · Kết luận  │
  │                slide 22–25│
  └──────────────────────────┘
```

> Ghi chú Canva: Mỗi block là 1 rectangle, viền trái dày màu vàng. Số thứ tự (01–07) cỡ chữ lớn màu vàng sáng. Chữ tên section đậm trắng. Chữ mô tả nhỏ xám. Số slide nhỏ căn phải.

---

## SLIDE 03 — Vấn đề nghiên cứu

**Layout:** 2 cột (trái: bullets, phải: 2 stat card)

```
[HEADER]
  Section label: VẤN ĐỀ NGHIÊN CỨU

[TITLE]
  Tấn công mạng IoT ngày càng tinh vi —
  IDS dựa trên chữ ký không theo kịp

  ──── đường kẻ mỏng ────────────────────────────────────

[BODY — 2 cột]

  Cột trái (60%):                     Cột phải (40%):
  • IoT bùng nổ:                       ┌────────────────┐
    hàng tỷ thiết bị kết nối,          │      17        │  ← số vàng lớn
    bề mặt tấn công mở rộng            │ họ tấn công IoT│
    nhanh chóng.                        │ trong CIC 2024 │
                                        └────────────────┘
  • Giới hạn của signature-based IDS:
    bỏ qua zero-day và biến thể         ┌────────────────┐
    tấn công mới.                       │     27.7M      │  ← số vàng lớn
                                        │ bản ghi luồng  │
  • Anomaly-based ML:                   │ (sau làm sạch) │
    phát hiện qua đặc trưng hành vi     └────────────────┘
    luồng mạng (flow features).

  • Khoảng trống thực tế:
    thiếu pipeline end-to-end từ dữ
    liệu thô đến IDS có thể triển khai.

[FOOTNOTE]
  Nguồn: Neto et al. (2024) – CIC IoT-DIAD 2024, Canadian Institute for Cybersecurity
```

---

## SLIDE 04 — Mục tiêu & câu hỏi nghiên cứu

**Layout:** 3 hàng dọc, mỗi hàng = số lớn + đường kẻ + tiêu đề + mô tả

```
[HEADER]
  Section label: MỤC TIÊU & CÂU HỎI NGHIÊN CỨU

[TITLE]
  Đồ án xây dựng pipeline ML đầu cuối: từ dữ liệu
  luồng IoT đến IDS phân loại thời gian thực

  ──── đường kẻ mỏng ────────────────────────────────────

[BODY — 3 hàng]

  01  │  Tiền xử lý & Benchmark ML
      │  So sánh CatBoost, HistGB, RandomForest trên CIC IoT-DIAD 2024
      │  với protocol thực nghiệm công bằng — 2M / 4M / 8M / full-data.

  02  │  Chọn mô hình tối ưu
      │  Đánh giá F1, FPR và OOD Recall để chọn mô hình cân bằng nhất
      │  giữa hiệu năng phát hiện và chi phí triển khai.

  03  │  Xây dựng Runtime IDS
      │  Triển khai pipeline đầy đủ: Record Adapter → Realtime Pipeline
      │  → Inference Engine → Operator Console.
```

> Ghi chú Canva: "01", "02", "03" cỡ chữ 48–60px, màu vàng, căn trái. Đường kẻ dọc giữa số và text: 1–2px xám tối. Tiêu đề đậm trắng. Mô tả xám nhạt.

---

## SLIDE 05 — Tổng quan pipeline nghiên cứu

**Layout:** 5 box ngang nối nhau bằng mũi tên

```
[HEADER]
  Section label: PHƯƠNG PHÁP

[TITLE]
  Pipeline nghiên cứu 5 giai đoạn: từ raw dataset đến
  hệ thống IDS chạy được

  ──── đường kẻ mỏng ────────────────────────────────────

[BODY — 5 box ngang]

  ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
  │    ①    │  →  │    ②    │  →  │    ③    │  →  │    ④    │  →  │    ⑤    │
  │ Dataset │     │ Tiền    │     │Benchmark│     │ Model   │     │ Runtime │
  │         │     │ xử lý  │     │   ML    │     │ Select  │     │   IDS   │
  ├─────────┤     ├─────────┤     ├─────────┤     ├─────────┤     ├─────────┤
  │CIC IoT  │     │Dedup    │     │CatBoost │     │F1 · FPR │     │Adapter  │
  │2024     │     │Leakage  │     │HistGB   │     │OOD      │     │Pipeline │
  │27.7M    │     │Split    │     │RF       │     │Threshold│     │Inference│
  │17 attack│     │OOD      │     │2M/4M/8M │     │CatBoost │     │Console  │
  │families │     │holdout  │     │Tuning   │     │full     │     │98 tests │
  └─────────┘     └─────────┘     └─────────┘     └─────────┘     └─────────┘
```

> Ghi chú Canva: Mỗi box có viền trên màu khác nhau (vàng → vàng → vàng sáng → xanh lạnh → xanh lá). Nền tối. Số ① màu tương ứng viền. Mũi tên → màu vàng mờ.

---

*→ Tiếp tục từ slide 06...*
