'use strict';
// ─── pptxgenjs via global install ─────────────────────────────────────────────
const pptxgen = require('C:/Users/hdi/AppData/Roaming/npm/node_modules/pptxgenjs');

const pres = new pptxgen();
pres.layout  = 'LAYOUT_16x9';
pres.title   = 'Xây Dựng Hệ Thống IDS Dựa Trên Machine Learning';
pres.subject = 'Phân tích và đánh giá ATTT';

// ── Colors ────────────────────────────────────────────────────────────────────
const BLK = '1A1A1A';
const RED = 'C8102E';
const NAV = '1B3A6B';
const WHT = 'FFFFFF';
const GRY = '6B6B6B';
const LGY = 'F4F4F4';
const MGY = 'CCCCCC';
const DGY = '444444';
const GRN = '1B6B32';
const TEA = '028090';
const ORG = 'D97706';

// ── Font ──────────────────────────────────────────────────────────────────────
const F = 'Oswald';

// ── Logo paths ────────────────────────────────────────────────────────────────
const IMG = {
  hutech:   'C:/Users/hdi/Downloads/IDS_ML_media/image1.png',
  awards:   'C:/Users/hdi/Downloads/IDS_ML_media/image2.png',
  hutech30: 'C:/Users/hdi/Downloads/IDS_ML_media/image4.png',
  qsstars:  'C:/Users/hdi/Downloads/IDS_ML_media/image3.png',
};

let N = 0;

// ── HELPERS ───────────────────────────────────────────────────────────────────

function hdr(s, n) {
  s.addShape('rect', { x:0, y:0.585, w:10, h:0.02,
    fill:{color:BLK}, line:{color:BLK, width:0} });
  s.addImage({ path:IMG.hutech,   x:0.15, y:0.07, w:1.40, h:0.45 });
  s.addImage({ path:IMG.awards,   x:1.62, y:0.07, w:0.46, h:0.44 });
  s.addImage({ path:IMG.hutech30, x:8.08, y:0.09, w:0.80, h:0.33 });
  s.addImage({ path:IMG.qsstars,  x:8.96, y:0.09, w:0.88, h:0.38 });
  s.addShape('rect', { x:0, y:5.33, w:10, h:0.02,
    fill:{color:BLK}, line:{color:BLK, width:0} });
  s.addText(String(n), {
    x:9.0, y:5.36, w:0.8, h:0.22,
    fontSize:11, fontFace:F, color:BLK, align:'right', valign:'top', margin:0 });
}

function secLbl(s, txt) {
  s.addText(txt, {
    x:0.55, y:0.65, w:9, h:0.27,
    fontSize:10, fontFace:F, color:NAV, align:'left', margin:0, charSpacing:2 });
}

function sTitle(s, txt) {
  s.addShape('rect', { x:0.45, y:0.96, w:0.07, h:0.56,
    fill:{color:RED}, line:{color:RED, width:0} });
  s.addText(txt, {
    x:0.62, y:0.96, w:8.98, h:0.56,
    fontSize:24, fontFace:F, color:BLK, bold:true,
    align:'left', valign:'middle', margin:0 });
}

function hrule(s, x, y, w, color) {
  s.addShape('rect', { x, y, w, h:0.018,
    fill:{color:color||MGY}, line:{color:color||MGY, width:0} });
}

function statCard(s, num, label, x, y, w, h, numColor) {
  s.addShape('rect', { x, y, w, h,
    fill:{color:LGY}, line:{color:MGY, width:1} });
  s.addText(num, {
    x, y:y+0.05, w, h:h*0.52,
    fontSize:28, fontFace:F, color:numColor||RED, bold:true,
    align:'center', valign:'middle', margin:0 });
  s.addText(label, {
    x:x+0.08, y:y+h*0.55, w:w-0.16, h:h*0.42,
    fontSize:10, fontFace:F, color:GRY, align:'center', valign:'top', margin:0 });
}

function addSlide(fn) {
  N++;
  const s = pres.addSlide();
  s.background = { color: WHT };
  hdr(s, N);
  fn(s);
}

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 01 — TITLE
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  // Dark overlay band
  s.addShape('rect', { x:0, y:1.05, w:10, h:2.8,
    fill:{color:NAV}, line:{color:NAV, width:0} });

  // Shield icon (cyber security motif — simple shape)
  s.addShape('rect', { x:0.38, y:1.20, w:0.07, h:2.48,
    fill:{color:RED}, line:{color:RED, width:0} });

  // Course label
  s.addText('MÔN HỌC: PHÂN TÍCH & ĐÁNH GIÁ AN TOÀN THÔNG TIN', {
    x:0.55, y:1.12, w:9.1, h:0.32,
    fontSize:10, fontFace:F, color:MGY, align:'left', margin:0, charSpacing:3 });

  // Main title
  s.addText([
    { text:'XÂY DỰNG HỆ THỐNG', options:{ breakLine:true } },
    { text:'PHÁT HIỆN XÂM NHẬP MẠNG', options:{ breakLine:true } },
    { text:'DỰA TRÊN MACHINE LEARNING' }
  ], {
    x:0.55, y:1.48, w:9.0, h:1.8,
    fontSize:30, fontFace:F, color:WHT, bold:true,
    align:'left', valign:'middle', margin:0 });

  hrule(s, 0.55, 3.92, 8.9, RED);

  // Info row
  s.addText([
    { text:'TRƯỜNG ĐẠI HỌC CÔNG NGHỆ TP.HCM  ·  KHOA CNTT  ·  HK II / 2024–2025', options:{color:GRY} }
  ], {
    x:0.55, y:4.0, w:9.0, h:0.28,
    fontSize:10, fontFace:F, align:'left', margin:0 });

  // Left block — GVHD
  s.addText([
    { text:'GIẢNG VIÊN HƯỚNG DẪN', options:{ color:GRY, breakLine:true } },
    { text:'ĐINH PHƯƠNG NAM', options:{ color:NAV, bold:true, fontSize:16 } }
  ], {
    x:0.55, y:4.36, w:4.5, h:0.75,
    fontSize:13, fontFace:F, align:'left', margin:0 });

  // Divider
  s.addShape('rect', { x:5.15, y:4.36, w:0.02, h:0.75,
    fill:{color:MGY}, line:{color:MGY, width:0} });

  // Right block — Team
  s.addText([
    { text:'THÀNH VIÊN NHÓM', options:{ color:GRY, breakLine:true } },
    { text:'Nguyễn Hoàng Duy  ·  ...', options:{ color:BLK, bold:true, fontSize:13 } }
  ], {
    x:5.3, y:4.36, w:4.3, h:0.75,
    fontSize:13, fontFace:F, align:'left', margin:0 });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 02 — ĐẶT VẤN ĐỀ
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '01  ĐẶT VẤN ĐỀ');
  sTitle(s, 'IoT BỐC PHÁT — IDS TRUYỀN THỐNG KHÔNG THEO KỊP');

  hrule(s, 0.45, 1.56, 9.1);

  // Left column bullets
  const points = [
    ['IoT phát triển bùng nổ',
     '17 tỷ thiết bị (2023) → 29 tỷ (2030). Bề mặt tấn công tăng theo cấp số nhân, lưu lượng mạng phức tạp hơn.'],
    ['Các kiểu tấn công phổ biến',
     'DDoS · Brute Force · Spoofing · Mirai botnet — ngày càng tự động hóa và khó phân biệt với traffic bình thường.'],
    ['Signature-based IDS: đã lỗi thời',
     'Không phát hiện được zero-day attacks. Cần cập nhật thủ công liên tục. Bỏ qua biến thể tấn công mới.'],
  ];

  points.forEach(([title, desc], i) => {
    const y = 1.68 + i * 1.12;
    s.addShape('rect', { x:0.45, y, w:0.06, h:0.90,
      fill:{color:RED}, line:{color:RED, width:0} });
    s.addText(title, {
      x:0.60, y, w:5.5, h:0.38,
      fontSize:13.5, fontFace:F, color:BLK, bold:true,
      align:'left', valign:'middle', margin:0 });
    s.addText(desc, {
      x:0.60, y:y+0.38, w:5.5, h:0.65,
      fontSize:11, fontFace:F, color:GRY,
      align:'left', valign:'top', margin:0 });
  });

  // Right — stat cards
  statCard(s, '17B → 29B', 'thiết bị IoT\n2023 → 2030', 6.25, 1.68, 3.30, 1.0, RED);
  statCard(s, '✗ Zero-day', 'signature IDS\nkhông phát hiện được', 6.25, 2.82, 3.30, 0.95, DGY);
  statCard(s, 'ML IDS', '→ Cần IDS thông minh\nanomaly-based', 6.25, 3.90, 3.30, 0.95, NAV);

  s.addText('➡  Giải pháp: Xây dựng IDS dựa trên Machine Learning — phát hiện bất thường theo đặc trưng luồng', {
    x:0.45, y:5.06, w:9.1, h:0.22,
    fontSize:10, fontFace:F, color:RED, bold:true, italic:true, align:'left', margin:0 });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 03 — MỤC TIÊU ĐỒ ÁN
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '02  MỤC TIÊU ĐỒ ÁN');
  sTitle(s, 'MỤC TIÊU: NGHIÊN CỨU VÀ TRIỂN KHAI THỰC TẾ');

  hrule(s, 0.45, 1.56, 9.1);

  const goals = [
    ['01', 'Xây dựng IDS anomaly-based', 'Phát hiện tấn công qua đặc trưng luồng, không dùng signature.'],
    ['02', 'Pipeline xử lý dữ liệu hoàn chỉnh', 'Làm sạch, loại leakage, split an toàn → 72 features.'],
    ['03', 'So sánh 5 mô hình ML', 'LogReg · RF · HistGB · CatBoost · MLP — đánh giá công bằng.'],
    ['04', 'Tối ưu threshold & chọn model tốt nhất', 'Dựa trên FPR, F1, OOD Recall — ưu tiên FPR thấp.'],
    ['05', 'Triển khai hệ thống thực tế (real-time)', 'Inference engine + dashboard + Telegram alerts.'],
    ['06', 'Mở rộng 2-stage classification', 'Stage 1: benign/attack. Stage 2: phân loại attack family + abstain.'],
  ];

  goals.forEach(([num, title, desc], i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = col === 0 ? 0.45 : 5.22;
    const y = 1.68 + row * 1.18;
    const w = 4.60;

    s.addShape('rect', { x, y, w, h:1.08,
      fill:{color:LGY}, line:{color:MGY, width:1} });
    s.addShape('rect', { x, y, w:0.06, h:1.08,
      fill:{color:RED}, line:{color:RED, width:0} });
    s.addText(num, {
      x:x+0.12, y, w:0.58, h:1.08,
      fontSize:22, fontFace:F, color:RED, bold:true,
      align:'left', valign:'middle', margin:0 });
    s.addText(title, {
      x:x+0.72, y:y+0.06, w:w-0.82, h:0.42,
      fontSize:12, fontFace:F, color:BLK, bold:true,
      align:'left', valign:'middle', margin:0 });
    s.addText(desc, {
      x:x+0.72, y:y+0.48, w:w-0.82, h:0.55,
      fontSize:10.5, fontFace:F, color:GRY,
      align:'left', valign:'top', margin:0 });
  });

  s.addText('⚡  Không chỉ nghiên cứu — đồ án tập trung vào triển khai hệ thống thực tế với giao diện vận hành đầy đủ', {
    x:0.45, y:5.06, w:9.1, h:0.22,
    fontSize:10, fontFace:F, color:NAV, bold:true, italic:true, align:'left', margin:0 });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 04 — PHẠM VI & GIỚI HẠN
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '02  PHẠM VI & GIỚI HẠN');
  sTitle(s, 'PHẠM VI NGHIÊN CỨU & NHỮNG GÌ CHƯA LÀM');

  hrule(s, 0.45, 1.56, 9.1);

  // Left — In scope
  s.addText('TRONG PHẠM VI', {
    x:0.45, y:1.62, w:4.45, h:0.35,
    fontSize:12, fontFace:F, color:GRN, bold:true, align:'left', margin:0, charSpacing:2 });

  const inScope = [
    'Hệ thống chạy trên 1 máy (same-host)',
    'Dữ liệu flow-based — không đọc nội dung packet',
    'Dataset: CIC IoT-DIAD 2024 (lab traffic)',
    'Real-time inference trên traffic flow đã được capture',
    'Dashboard web + Telegram notification',
  ];
  inScope.forEach((txt, i) => {
    const y = 2.05 + i * 0.60;
    s.addShape('rect', { x:0.45, y:y+0.10, w:0.22, h:0.22,
      fill:{color:GRN}, line:{color:GRN, width:0} });
    s.addText('✓', {
      x:0.45, y:y+0.06, w:0.22, h:0.22,
      fontSize:11, fontFace:F, color:WHT, bold:true, align:'center', margin:0 });
    s.addText(txt, {
      x:0.76, y, w:4.14, h:0.45,
      fontSize:12, fontFace:F, color:BLK,
      align:'left', valign:'middle', margin:0 });
  });

  // Divider
  s.addShape('rect', { x:5.1, y:1.62, w:0.02, h:3.55,
    fill:{color:MGY}, line:{color:MGY, width:0} });

  // Right — Out of scope
  s.addText('NGOÀI PHẠM VI', {
    x:5.25, y:1.62, w:4.3, h:0.35,
    fontSize:12, fontFace:F, color:RED, bold:true, align:'left', margin:0, charSpacing:2 });

  const outScope = [
    'Multi-host / distributed deployment',
    'Deep Packet Inspection (DPI)',
    'Đo lường hiệu năng dài hạn / concept drift',
    'Tấn công vật lý (Physical layer attacks)',
  ];
  outScope.forEach((txt, i) => {
    const y = 2.05 + i * 0.72;
    s.addShape('rect', { x:5.25, y:y+0.10, w:0.22, h:0.22,
      fill:{color:RED}, line:{color:RED, width:0} });
    s.addText('✗', {
      x:5.25, y:y+0.06, w:0.22, h:0.22,
      fontSize:11, fontFace:F, color:WHT, bold:true, align:'center', margin:0 });
    s.addText(txt, {
      x:5.56, y, w:3.98, h:0.52,
      fontSize:12, fontFace:F, color:BLK,
      align:'left', valign:'middle', margin:0 });
  });

  s.addText('GV hay hỏi slide này — cần trả lời rõ: hệ thống chỉ chạy trên 1 máy, không đọc nội dung gói tin', {
    x:0.45, y:5.06, w:9.1, h:0.22,
    fontSize:9.5, fontFace:F, color:ORG, italic:true, align:'left', margin:0 });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 05 — TỔNG QUAN IDS
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '03  CƠ SỞ LÝ THUYẾT');
  sTitle(s, 'HỆ THỐNG PHÁT HIỆN XÂM NHẬP (IDS)');

  hrule(s, 0.45, 1.56, 9.1);

  // Definition
  s.addText('IDS (Intrusion Detection System) là hệ thống giám sát lưu lượng mạng, phát hiện hoạt động bất thường và cảnh báo quản trị viên — nhưng không tự chặn tấn công.', {
    x:0.45, y:1.62, w:9.1, h:0.55,
    fontSize:12.5, fontFace:F, color:BLK,
    align:'left', valign:'middle', margin:0 });

  // Role cards
  const roles = [
    [NAV, 'GIÁM SÁT', 'Phân tích lưu lượng mạng liên tục theo thời gian thực'],
    [TEA, 'PHÂN TÍCH', 'So sánh với baseline hoặc mô hình để phát hiện bất thường'],
    [RED, 'CẢNH BÁO', 'Thông báo cho quản trị viên khi phát hiện tấn công'],
  ];
  roles.forEach(([color, label, desc], i) => {
    const x = 0.45 + i * 2.98;
    s.addShape('rect', { x, y:2.28, w:2.78, h:0.78,
      fill:{color}, line:{color, width:0} });
    s.addText(label, {
      x, y:2.28, w:2.78, h:0.38,
      fontSize:14, fontFace:F, color:WHT, bold:true,
      align:'center', valign:'middle', margin:0 });
    s.addText(desc, {
      x:x+0.08, y:2.66, w:2.62, h:0.38,
      fontSize:10, fontFace:F, color:WHT,
      align:'center', valign:'top', margin:0 });
  });

  // Comparison table
  s.addText('SO SÁNH PHƯƠNG PHÁP PHÁT HIỆN', {
    x:0.45, y:3.18, w:9.1, h:0.32,
    fontSize:11.5, fontFace:F, color:NAV, bold:true, align:'left', margin:0, charSpacing:2 });

  const tableRows = [
    [
      { text:'Tiêu chí', options:{ bold:true, color:WHT, fill:{color:NAV} } },
      { text:'Signature-based', options:{ bold:true, color:WHT, fill:{color:NAV} } },
      { text:'Anomaly-based (ML)', options:{ bold:true, color:WHT, fill:{color:NAV} } },
    ],
    ['Phát hiện tấn công đã biết', '✓ Tốt', '✓ Tốt'],
    ['Phát hiện zero-day', '✗ Không', '✓ Có thể'],
    ['Cập nhật signature', '✗ Thủ công, liên tục', '✓ Tự học từ dữ liệu'],
    ['False Positive', '✓ Thấp', '⚠ Phụ thuộc threshold'],
    ['Khả năng thích nghi', '✗ Kém', '✓ Tốt'],
  ];

  s.addTable(tableRows, {
    x:0.45, y:3.54, w:9.1, h:1.68,
    fontSize:11, fontFace:F,
    border:{ pt:1, color:'DDDDDD' },
    fill:{ color:'F9F9F9' },
    colW:[3.0, 3.0, 3.1],
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 06 — FLOW-BASED IDS
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '03  CƠ SỞ LÝ THUYẾT');
  sTitle(s, 'FLOW-BASED IDS — PHÂN TÍCH LUỒNG, KHÔNG ĐỌC PACKET');

  hrule(s, 0.45, 1.56, 9.1);

  // Why flow?
  s.addText('Thay vì đọc nội dung từng packet (tốn tài nguyên, vi phạm privacy), Flow-based IDS phân tích metadata của luồng kết nối:', {
    x:0.45, y:1.62, w:9.1, h:0.52,
    fontSize:12, fontFace:F, color:BLK, align:'left', margin:0 });

  // 5-tuple box
  s.addShape('rect', { x:0.45, y:2.22, w:9.1, h:0.62,
    fill:{color:NAV}, line:{color:NAV, width:0} });
  s.addText('5-TUPLE:', {
    x:0.55, y:2.22, w:1.0, h:0.62,
    fontSize:11, fontFace:F, color:MGY, bold:true, align:'left', valign:'middle', margin:0 });
  const tuples = ['Source IP', 'Dest IP', 'Source Port', 'Dest Port', 'Protocol'];
  tuples.forEach((t, i) => {
    const x = 1.55 + i * 1.55;
    s.addShape('rect', { x, y:2.30, w:1.40, h:0.44,
      fill:{color:RED}, line:{color:RED, width:0} });
    s.addText(t, {
      x, y:2.30, w:1.40, h:0.44,
      fontSize:10, fontFace:F, color:WHT, bold:true, align:'center', valign:'middle', margin:0 });
  });

  // Advantages + Features
  s.addText('ƯU ĐIỂM', {
    x:0.45, y:2.96, w:4.45, h:0.32,
    fontSize:11.5, fontFace:F, color:GRN, bold:true, align:'left', margin:0, charSpacing:2 });

  const advs = [
    ['Nhanh', 'Xử lý ở mức flow, không cần deep inspection'],
    ['Bảo mật hơn', 'Không đọc payload — tôn trọng privacy người dùng'],
    ['Khả thi', 'Chạy được trên phần cứng thông thường'],
  ];
  advs.forEach(([title, desc], i) => {
    const y = 3.36 + i * 0.58;
    s.addShape('rect', { x:0.45, y, w:0.06, h:0.48,
      fill:{color:GRN}, line:{color:GRN, width:0} });
    s.addText(title + ': ', {
      x:0.58, y, w:0.85, h:0.48,
      fontSize:11.5, fontFace:F, color:GRN, bold:true, align:'left', valign:'middle', margin:0 });
    s.addText(desc, {
      x:1.42, y, w:3.50, h:0.48,
      fontSize:11, fontFace:F, color:GRY, align:'left', valign:'middle', margin:0 });
  });

  // Divider
  s.addShape('rect', { x:5.1, y:2.96, w:0.02, h:2.32,
    fill:{color:MGY}, line:{color:MGY, width:0} });

  // Features
  s.addText('FEATURE VÍ DỤ', {
    x:5.25, y:2.96, w:4.3, h:0.32,
    fontSize:11.5, fontFace:F, color:NAV, bold:true, align:'left', margin:0, charSpacing:2 });

  const features = [
    'flow_duration — thời gian kết nối',
    'tot_fwd_pkts — số packet chiều xuôi',
    'totlen_fwd_pkts — tổng byte chiều xuôi',
    'flow_byts_s — throughput (bytes/s)',
    'pkt_len_mean — kích thước packet TB',
    'flow_iat_mean — inter-arrival time TB',
  ];
  features.forEach((f, i) => {
    s.addText('›  ' + f, {
      x:5.25, y:3.32 + i * 0.32, w:4.3, h:0.30,
      fontSize:11, fontFace:F, color:BLK, align:'left', margin:0 });
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 07 — DATASET
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '04  DỮ LIỆU');
  sTitle(s, 'CIC IoT-DIAD 2024 — BỘ DỮ LIỆU CHUẨN NGHIÊN CỨU');

  hrule(s, 0.45, 1.56, 9.1);

  // Dataset info block
  s.addShape('rect', { x:0.45, y:1.62, w:4.45, h:3.55,
    fill:{color:LGY}, line:{color:MGY, width:1} });
  s.addShape('rect', { x:0.45, y:1.62, w:4.45, h:0.38,
    fill:{color:NAV}, line:{color:NAV, width:0} });
  s.addText('THÔNG TIN BỘ DỮ LIỆU', {
    x:0.55, y:1.62, w:4.25, h:0.38,
    fontSize:11.5, fontFace:F, color:WHT, bold:true,
    align:'left', valign:'middle', margin:0, charSpacing:2 });

  const dsInfo = [
    ['Tên',      'CIC IoT-DIAD 2024'],
    ['Nguồn',    'Canadian Institute for Cybersecurity'],
    ['Tổng rows','27.7M bản ghi luồng'],
    ['Sau làm sạch', '18.6M rows (72 features)'],
    ['Thiết bị', 'IoT devices — thực tế'],
    ['Loại',     'Benign + Attack traffic'],
  ];
  dsInfo.forEach(([key, val], i) => {
    s.addText(key + ':', {
      x:0.58, y:2.10 + i * 0.50, w:1.60, h:0.42,
      fontSize:11, fontFace:F, color:GRY, align:'left', valign:'middle', margin:0 });
    s.addText(val, {
      x:2.20, y:2.10 + i * 0.50, w:2.60, h:0.42,
      fontSize:11.5, fontFace:F, color:BLK, bold:true, align:'left', valign:'middle', margin:0 });
  });

  // Attack families
  s.addText('CÁC LOẠI TẤN CÔNG', {
    x:5.15, y:1.62, w:4.4, h:0.35,
    fontSize:11.5, fontFace:F, color:NAV, bold:true, align:'left', margin:0, charSpacing:2 });

  const attacks = [
    [RED,  'DDoS',       'Distributed Denial of Service — làm nghẽn dịch vụ'],
    [RED,  'DoS',        'Denial of Service — tương tự DDoS nhưng từ 1 nguồn'],
    [ORG,  'Spoofing',   'Giả mạo địa chỉ IP/ARP để đánh lừa hệ thống'],
    [ORG,  'Mirai',      'Botnet tấn công IoT — lây nhiễm thiết bị yếu'],
    [NAV,  'Scan',       'Quét cổng, dò tìm lỗ hổng bảo mật'],
    [DGY,  'Brute Force','Thử mật khẩu liên tục — SSH, Telnet'],
    [GRN,  'Benign',     'Traffic bình thường của IoT devices'],
  ];
  attacks.forEach(([color, name, desc], i) => {
    const y = 2.05 + i * 0.50;
    s.addShape('rect', { x:5.15, y, w:0.75, h:0.40,
      fill:{color}, line:{color, width:0} });
    s.addText(name, {
      x:5.15, y, w:0.75, h:0.40,
      fontSize:9.5, fontFace:F, color:WHT, bold:true, align:'center', valign:'middle', margin:0 });
    s.addText(desc, {
      x:5.98, y, w:3.57, h:0.40,
      fontSize:10.5, fontFace:F, color:BLK, align:'left', valign:'middle', margin:0 });
  });

  s.addText('Dataset chuẩn nghiên cứu — được dùng trong nhiều paper IoT security 2024', {
    x:0.45, y:5.06, w:9.1, h:0.22,
    fontSize:9.5, fontFace:F, color:GRY, italic:true, align:'left', margin:0 });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 08 — CÁC MÔ HÌNH ML
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '05  MÔ HÌNH MACHINE LEARNING');
  sTitle(s, '5 MÔ HÌNH ML ĐƯỢC SO SÁNH TRONG ĐỒ ÁN');

  hrule(s, 0.45, 1.56, 9.1);

  const models = [
    [RED,  'LR',  'Logistic\nRegression',
     'Baseline tuyến tính. Đơn giản, nhanh huấn luyện. Kỳ vọng underfit trên dữ liệu phi tuyến IoT.'],
    [NAV,  'RF',  'Random\nForest',
     'Ensemble cây quyết định. Mạnh với nhiễu, tốt với imbalanced data. Tốn RAM với dataset lớn.'],
    [TEA,  'HGB', 'Hist\nGradientBoosting',
     'Gradient boosting tối ưu bằng histogram. Nhanh hơn XGBoost, xử lý tốt missing value.'],
    [DGY,  'CB',  'CatBoost',
     'Boosting với xử lý đặc trưng categorical. Ít overfitting, huấn luyện nhanh, FPR thấp.'],
    [GRN,  'MLP', 'Multi-Layer\nPerceptron',
     'Neural network đơn giản. Linh hoạt nhưng cần nhiều tuning và thường có FPR cao.'],
  ];

  models.forEach(([color, short, name, desc], i) => {
    const x = 0.45 + i * 1.82;
    // Top color band
    s.addShape('rect', { x, y:1.68, w:1.72, h:0.46,
      fill:{color}, line:{color, width:0} });
    s.addText(short, {
      x, y:1.68, w:1.72, h:0.46,
      fontSize:18, fontFace:F, color:WHT, bold:true,
      align:'center', valign:'middle', margin:0 });
    // Card body
    s.addShape('rect', { x, y:2.14, w:1.72, h:3.12,
      fill:{color:LGY}, line:{color:MGY, width:1} });
    // Full name
    s.addText(name, {
      x:x+0.05, y:2.18, w:1.62, h:0.62,
      fontSize:12, fontFace:F, color:color, bold:true,
      align:'center', valign:'middle', margin:0 });
    hrule(s, x+0.1, 2.82, 1.52, MGY);
    // Description
    s.addText(desc, {
      x:x+0.06, y:2.88, w:1.60, h:2.30,
      fontSize:10.5, fontFace:F, color:GRY,
      align:'left', valign:'top', margin:0 });
  });

  s.addText('Tất cả mô hình được train với cùng pipeline, split strategy và metric evaluation để so sánh công bằng', {
    x:0.45, y:5.38, w:9.1, h:0.20,
    fontSize:9.5, fontFace:F, color:GRY, italic:true, align:'center', margin:0 });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 09 — METRIC ĐÁNH GIÁ
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '05  MÔ HÌNH MACHINE LEARNING');
  sTitle(s, 'METRIC ĐÁNH GIÁ — FPR LÀ QUAN TRỌNG NHẤT');

  hrule(s, 0.45, 1.56, 9.1);

  const metrics = [
    [NAV,  'Precision', 'TP / (TP + FP)',
     'Trong số cảnh báo, bao nhiêu % là tấn công thật?'],
    [TEA,  'Recall', 'TP / (TP + FN)',
     'Trong số tấn công thật, bao nhiêu % được phát hiện?'],
    [GRN,  'F1-Score', '2 × P × R / (P + R)',
     'Trung bình điều hòa của Precision và Recall.'],
    [RED,  'FPR ⚠', 'FP / (FP + TN)',
     'Tỷ lệ cảnh báo nhầm. IDS phải giảm FPR tối đa!'],
    [ORG,  'OOD Recall', 'TP_ood / N_ood',
     'Phát hiện tấn công chưa thấy khi train (out-of-distribution).'],
  ];

  metrics.forEach(([color, name, formula, desc], i) => {
    const col = i % 2 === 0 ? 0 : 1;
    const row = Math.floor(i / 2);
    const x = col === 0 ? 0.45 : 5.22;
    const y = 1.68 + row * 1.15;

    if (i === 4) { // Last item — centered
      const xc = 0.45;
      s.addShape('rect', { x:xc, y, w:9.1, h:1.05,
        fill:{color:'FFF3E0'}, line:{color:ORG, width:1} });
      s.addShape('rect', { x:xc, y, w:0.07, h:1.05,
        fill:{color:ORG}, line:{color:ORG, width:0} });
      s.addText(name, {
        x:xc+0.15, y:y+0.04, w:2.2, h:0.42,
        fontSize:14, fontFace:F, color:ORG, bold:true, align:'left', margin:0 });
      s.addText(formula, {
        x:xc+2.4, y:y+0.04, w:2.5, h:0.42,
        fontSize:12, fontFace:F, color:DGY, align:'left', valign:'middle', margin:0 });
      s.addText(desc, {
        x:xc+0.15, y:y+0.50, w:8.80, h:0.48,
        fontSize:11.5, fontFace:F, color:GRY, align:'left', margin:0 });
    } else {
      s.addShape('rect', { x, y, w:4.60, h:1.05,
        fill:{color:LGY}, line:{color:MGY, width:1} });
      s.addShape('rect', { x, y, w:0.07, h:1.05,
        fill:{color}, line:{color, width:0} });
      s.addText(name, {
        x:x+0.15, y:y+0.04, w:2.0, h:0.42,
        fontSize:14, fontFace:F, color, bold:true, align:'left', margin:0 });
      s.addText(formula, {
        x:x+2.1, y:y+0.04, w:2.35, h:0.42,
        fontSize:11, fontFace:F, color:DGY, align:'left', valign:'middle', margin:0 });
      s.addText(desc, {
        x:x+0.15, y:y+0.50, w:4.30, h:0.48,
        fontSize:11, fontFace:F, color:GRY, align:'left', margin:0 });
    }
  });

  s.addText('⚠  IDS có FPR cao = cảnh báo nhầm liên tục = quản trị viên mất niềm tin = bỏ qua cảnh báo thật', {
    x:0.45, y:5.06, w:9.1, h:0.22,
    fontSize:10, fontFace:F, color:RED, bold:true, italic:true, align:'left', margin:0 });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 10 — KIẾN TRÚC HỆ THỐNG
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '06  KIẾN TRÚC HỆ THỐNG');
  sTitle(s, 'KIẾN TRÚC 5 TẦNG — TỪ DỮ LIỆU ĐẾN DASHBOARD');

  hrule(s, 0.45, 1.56, 9.1);

  const layers = [
    [NAV,  '1', 'DATA PREPROCESSING',
     'Làm sạch · Loại leakage · Split · 72 features'],
    [TEA,  '2', 'TRAINING PIPELINE',
     'Benchmark 5 models · Threshold tuning · Scaling exp'],
    [DGY,  '3', 'MODEL BUNDLE',
     'CatBoost weights · Scaler · Feature list · Threshold'],
    [RED,  '4', 'INFERENCE ENGINE',
     'Live capture · Flow extraction · Real-time prediction'],
    [GRN,  '5', 'DASHBOARD',
     'Web UI · Alert feed · Telegram notify · Stats'],
  ];

  layers.forEach(([color, num, name, desc], i) => {
    const y = 1.70 + i * 0.70;
    // Arrow (except last)
    if (i < layers.length - 1) {
      s.addShape('rect', { x:4.88, y:y+0.57, w:0.24, h:0.12,
        fill:{color:MGY}, line:{color:MGY, width:0} });
    }
    // Left strip
    s.addShape('rect', { x:0.45, y, w:9.1, h:0.60,
      fill:{color:'F8F8F8'}, line:{color:MGY, width:1} });
    s.addShape('rect', { x:0.45, y, w:0.50, h:0.60,
      fill:{color}, line:{color, width:0} });
    s.addText(num, {
      x:0.45, y, w:0.50, h:0.60,
      fontSize:20, fontFace:F, color:WHT, bold:true,
      align:'center', valign:'middle', margin:0 });
    s.addText(name, {
      x:1.04, y, w:3.30, h:0.60,
      fontSize:12.5, fontFace:F, color, bold:true,
      align:'left', valign:'middle', margin:0 });
    s.addShape('rect', { x:4.42, y:y+0.12, w:0.02, h:0.36,
      fill:{color:MGY}, line:{color:MGY, width:0} });
    s.addText(desc, {
      x:4.52, y, w:4.95, h:0.60,
      fontSize:11.5, fontFace:F, color:GRY,
      align:'left', valign:'middle', margin:0 });
  });

  s.addText('Slide này rất quan trọng — giải thích rõ luồng từ raw traffic đến alert cho giảng viên', {
    x:0.45, y:5.28, w:9.1, h:0.22,
    fontSize:9.5, fontFace:F, color:ORG, italic:true, align:'left', margin:0 });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 11 — DATA PIPELINE
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '06  KIẾN TRÚC HỆ THỐNG');
  sTitle(s, 'DATA PIPELINE — LÀM SẠCH & CHỐNG LEAKAGE');

  hrule(s, 0.45, 1.56, 9.1);

  // Pipeline flow — horizontal steps
  const steps = [
    [RED,  'Raw Data\n27.7M rows',      'CIC IoT-DIAD 2024\nCSV files'],
    [ORG,  'Loại bỏ\nLeakage',          'IP, port, timestamp\nbị loại trực tiếp'],
    [NAV,  'Dedup &\nClean',            'Loại duplicate\nfill NaN / Inf'],
    [TEA,  'Train/Test\nSplit',          'Stratified split\nkhông data leakage'],
    [GRN,  '72 Features\n18.6M rows',   'Feature set cuối\ncho training'],
  ];

  const stepW = 1.60;
  const arrowW = 0.22;
  const totalW = steps.length * stepW + (steps.length - 1) * arrowW;
  const startX = (10 - totalW) / 2;

  steps.forEach(([color, top, bot], i) => {
    const x = startX + i * (stepW + arrowW);
    s.addShape('rect', { x, y:1.80, w:stepW, h:0.50,
      fill:{color}, line:{color, width:0} });
    s.addText(top, {
      x, y:1.80, w:stepW, h:0.50,
      fontSize:10.5, fontFace:F, color:WHT, bold:true,
      align:'center', valign:'middle', margin:0 });
    s.addShape('rect', { x, y:2.30, w:stepW, h:1.05,
      fill:{color:LGY}, line:{color:MGY, width:1} });
    s.addText(bot, {
      x:x+0.04, y:2.30, w:stepW-0.08, h:1.05,
      fontSize:10.5, fontFace:F, color:GRY,
      align:'center', valign:'middle', margin:0 });
    if (i < steps.length - 1) {
      const ax = x + stepW;
      s.addShape('rect', { x:ax, y:2.02, w:arrowW, h:0.08,
        fill:{color:MGY}, line:{color:MGY, width:0} });
      s.addText('›', {
        x:ax-0.02, y:1.95, w:arrowW+0.04, h:0.22,
        fontSize:12, fontFace:F, color:MGY, align:'center', margin:0 });
    }
  });

  // Leakage explanation
  s.addShape('rect', { x:0.45, y:3.50, w:9.1, h:1.58,
    fill:{color:'FFF8E1'}, line:{color:ORG, width:1} });
  s.addShape('rect', { x:0.45, y:3.50, w:0.07, h:1.58,
    fill:{color:ORG}, line:{color:ORG, width:0} });
  s.addText('TẠI SAO PHẢI LOẠI LEAKAGE?', {
    x:0.60, y:3.56, w:8.85, h:0.38,
    fontSize:12.5, fontFace:F, color:ORG, bold:true, align:'left', margin:0 });
  s.addText([
    { text:'›  IP source/destination', options:{ bold:true, breakLine:true } },
    { text:'    Nếu giữ IP → model học IP cụ thể trong dataset, không khái quát được lên traffic mới.\n', options:{} },
    { text:'›  Timestamp', options:{ bold:true, breakLine:true } },
    { text:'    Nếu giữ timestamp → model overfit vào thứ tự thời gian của dataset lab.', options:{} },
  ], {
    x:0.60, y:3.98, w:8.85, h:1.05,
    fontSize:11, fontFace:F, color:BLK, align:'left', margin:0 });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 12 — TWO-STAGE MODEL
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '06  KIẾN TRÚC HỆ THỐNG');
  sTitle(s, 'TWO-STAGE CLASSIFICATION — PHÂN LOẠI 2 TẦNG');

  hrule(s, 0.45, 1.56, 9.1);

  // Input
  s.addShape('rect', { x:0.45, y:1.72, w:1.45, h:3.2,
    fill:{color:LGY}, line:{color:MGY, width:1} });
  s.addText('NETWORK\nFLOW', {
    x:0.45, y:2.82, w:1.45, h:0.72,
    fontSize:12, fontFace:F, color:NAV, bold:true, align:'center', valign:'middle', margin:0 });

  // Arrow
  s.addText('→', {
    x:1.92, y:3.12, w:0.35, h:0.42,
    fontSize:20, fontFace:F, color:MGY, align:'center', margin:0 });

  // Stage 1
  s.addShape('rect', { x:2.28, y:1.72, w:2.38, h:0.42,
    fill:{color:NAV}, line:{color:NAV, width:0} });
  s.addText('STAGE 1: Binary', {
    x:2.28, y:1.72, w:2.38, h:0.42,
    fontSize:11, fontFace:F, color:WHT, bold:true, align:'center', valign:'middle', margin:0 });
  s.addShape('rect', { x:2.28, y:2.14, w:2.38, h:3.0,
    fill:{color:'E8EAF6'}, line:{color:NAV, width:1} });
  s.addText('CatBoost binary classifier\n\nInput: 72 flow features\n\nOutput:\n  BENIGN\n  ATTACK', {
    x:2.35, y:2.20, w:2.24, h:2.85,
    fontSize:11, fontFace:F, color:BLK, align:'left', valign:'top', margin:0 });

  // Arrow
  s.addText('→', {
    x:4.68, y:3.12, w:0.35, h:0.42,
    fontSize:20, fontFace:F, color:MGY, align:'center', margin:0 });

  // Stage 2
  s.addShape('rect', { x:5.04, y:1.72, w:2.38, h:0.42,
    fill:{color:RED}, line:{color:RED, width:0} });
  s.addText('STAGE 2: Multi-class', {
    x:5.04, y:1.72, w:2.38, h:0.42,
    fontSize:11, fontFace:F, color:WHT, bold:true, align:'center', valign:'middle', margin:0 });
  s.addShape('rect', { x:5.04, y:2.14, w:2.38, h:3.0,
    fill:{color:'FFEBEE'}, line:{color:RED, width:1} });
  s.addText('CatBoost multi-class\n\nPhân loại:\n  DDoS / DoS\n  Spoofing\n  Mirai\n  Brute Force\n  ...', {
    x:5.11, y:2.20, w:2.24, h:2.85,
    fontSize:11, fontFace:F, color:BLK, align:'left', valign:'top', margin:0 });

  // Arrow
  s.addText('→', {
    x:7.44, y:3.12, w:0.35, h:0.42,
    fontSize:20, fontFace:F, color:MGY, align:'center', margin:0 });

  // Abstain box
  s.addShape('rect', { x:7.80, y:1.72, w:1.75, h:0.42,
    fill:{color:ORG}, line:{color:ORG, width:0} });
  s.addText('ABSTAIN', {
    x:7.80, y:1.72, w:1.75, h:0.42,
    fontSize:11, fontFace:F, color:WHT, bold:true, align:'center', valign:'middle', margin:0 });
  s.addShape('rect', { x:7.80, y:2.14, w:1.75, h:3.0,
    fill:{color:'FFF8E1'}, line:{color:ORG, width:1} });
  s.addText('Unknown\nattack family\n\nCảnh báo:\nUnknown\nThreat', {
    x:7.85, y:2.20, w:1.65, h:2.85,
    fontSize:11, fontFace:F, color:BLK, align:'left', valign:'top', margin:0 });

  s.addText('🔥  Điểm sáng: abstain mechanism giúp phát hiện tấn công chưa biết mà không báo lỗi nhầm', {
    x:0.45, y:5.22, w:9.1, h:0.30,
    fontSize:11, fontFace:F, color:RED, bold:true, italic:true, align:'left', margin:0 });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 13 — BENCHMARK KẾT QUẢ
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '07  KẾT QUẢ THỰC NGHIỆM');
  sTitle(s, 'BENCHMARK KẾT QUẢ — CATBOOST VƯỢT TRỘI VỀ FPR');

  hrule(s, 0.45, 1.56, 9.1);

  // Table
  const hStyle = { bold:true, color:WHT, fill:{color:NAV} };
  const goodFpr = { color:GRN, bold:true };
  const badFpr  = { color:RED, bold:true };
  const rows = [
    [
      { text:'Mô hình',     options:{ ...hStyle } },
      { text:'Precision',   options:{ ...hStyle } },
      { text:'Recall',      options:{ ...hStyle } },
      { text:'F1-Score',    options:{ ...hStyle } },
      { text:'FPR',         options:{ ...hStyle } },
      { text:'Đánh giá',    options:{ ...hStyle } },
    ],
    ['Logistic Regression',
      '94.12%', '89.34%', '91.67%',
      { text:'8.24%', options:{ ...badFpr } },
      { text:'❌  FPR quá cao', options:{ color:RED } }
    ],
    ['MLP (Neural Net)',
      '95.08%', '91.20%', '93.10%',
      { text:'6.87%', options:{ ...badFpr } },
      { text:'❌  FPR cao', options:{ color:RED } }
    ],
    ['Random Forest',
      '99.41%', '99.28%', '99.34%',
      { text:'0.52%', options:{ ...goodFpr } },
      { text:'✓  Tốt', options:{ color:GRN } }
    ],
    ['HistGradientBoosting',
      '99.38%', '99.25%', '99.31%',
      { text:'0.58%', options:{ ...goodFpr } },
      { text:'✓  Tốt', options:{ color:GRN } }
    ],
    [
      { text:'CatBoost ⭐', options:{ bold:true, fill:{color:'E8F5E9'} } },
      { text:'99.52%', options:{ bold:true, fill:{color:'E8F5E9'} } },
      { text:'99.41%', options:{ bold:true, fill:{color:'E8F5E9'} } },
      { text:'99.46%', options:{ bold:true, fill:{color:'E8F5E9'} } },
      { text:'0.31%',  options:{ ...goodFpr, fill:{color:'E8F5E9'} } },
      { text:'✅  TỐT NHẤT', options:{ color:GRN, bold:true, fill:{color:'E8F5E9'} } }
    ],
  ];

  s.addTable(rows, {
    x:0.45, y:1.68, w:9.1, h:3.22,
    fontSize:11.5, fontFace:F,
    border:{ pt:1, color:'DDDDDD' },
    fill:{ color:'F9F9F9' },
    colW:[2.55, 1.40, 1.35, 1.35, 1.05, 1.40],
  });

  s.addText('➡  LogReg và MLP có FPR > 6% — không phù hợp triển khai IDS. CatBoost đạt FPR = 0.31% là tốt nhất.', {
    x:0.45, y:5.00, w:9.1, h:0.28,
    fontSize:11, fontFace:F, color:NAV, bold:true, align:'left', margin:0 });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 14 — LEARNING CURVE
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '07  KẾT QUẢ THỰC NGHIỆM');
  sTitle(s, 'LEARNING CURVE — ĐỘ HỘI TỤ CỦA TỪNG MÔ HÌNH');

  hrule(s, 0.45, 1.56, 9.1);

  s.addText('Nhận xét từ learning curve khi tăng dần kích thước train set (2M → 4M → 8M → 18.6M rows):', {
    x:0.45, y:1.65, w:9.1, h:0.48,
    fontSize:12, fontFace:F, color:BLK, align:'left', margin:0 });

  const observations = [
    [GRN,   'RF & HistGB', 'Hội tụ ổn định — F1 cao và ít thay đổi khi tăng data. Đã đủ data từ 4M rows.'],
    [ORG,   'CatBoost',    'Còn tăng khi thêm data — có khả năng cải thiện thêm với full dataset và tuning sâu hơn.'],
    [RED,   'LogReg',      'Underfit rõ ràng — đường train và validation gần nhau nhưng cả hai đều thấp. Mô hình không đủ năng lực.'],
    [DGY,   'MLP',         'FPR cao dù F1 khá tốt — cần nhiều tuning hyperparameter hơn, khó deploy thực tế.'],
  ];

  observations.forEach(([color, model, obs], i) => {
    const y = 2.22 + i * 0.75;
    s.addShape('rect', { x:0.45, y, w:0.08, h:0.60,
      fill:{color}, line:{color, width:0} });
    s.addText(model + ':', {
      x:0.60, y, w:1.55, h:0.60,
      fontSize:13, fontFace:F, color, bold:true,
      align:'left', valign:'middle', margin:0 });
    s.addText(obs, {
      x:2.18, y, w:7.37, h:0.60,
      fontSize:12, fontFace:F, color:GRY,
      align:'left', valign:'middle', margin:0 });
  });

  s.addShape('rect', { x:0.45, y:5.02, w:9.1, h:0.28,
    fill:{color:LGY}, line:{color:MGY, width:1} });
  s.addText('Kết luận ngắn: RF/HistGB đã bão hòa — CatBoost còn tiềm năng với thêm data', {
    x:0.55, y:5.02, w:8.90, h:0.28,
    fontSize:11, fontFace:F, color:BLK, bold:true, align:'left', valign:'middle', margin:0 });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 15 — SCALING EXPERIMENT
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '07  KẾT QUẢ THỰC NGHIỆM');
  sTitle(s, 'SCALING EXPERIMENT — HIỆU NĂNG KHI TĂNG DỮ LIỆU');

  hrule(s, 0.45, 1.56, 9.1);

  s.addText('Thử nghiệm tăng train size từ 2M → 4M → 8M → 18.6M để đánh giá khả năng scale của từng mô hình:', {
    x:0.45, y:1.65, w:9.1, h:0.46,
    fontSize:12, fontFace:F, color:BLK, align:'left', margin:0 });

  // Comparison cards
  const comparisons = [
    {
      model: 'Random Forest',
      color: NAV,
      points: [
        ['F1 cao nhất ở full data', GRN],
        ['FPR tăng khi thêm data', RED],
        ['RAM tăng mạnh với 18.6M rows', RED],
        ['Không scale tốt với data lớn', RED],
      ]
    },
    {
      model: 'HistGradientBoosting',
      color: TEA,
      points: [
        ['Ổn định cả F1 và FPR', GRN],
        ['Tốc độ train chấp nhận được', GRN],
        ['Ít thay đổi khi thêm data', ORG],
        ['Gần bão hòa từ 8M rows', ORG],
      ]
    },
    {
      model: 'CatBoost ⭐',
      color: RED,
      points: [
        ['F1 tăng đều khi thêm data', GRN],
        ['FPR thấp nhất và ổn định', GRN],
        ['Train nhanh nhất', GRN],
        ['Cân bằng tốt nhất', GRN],
      ]
    },
  ];

  comparisons.forEach(({ model, color, points }, i) => {
    const x = 0.45 + i * 3.05;
    s.addShape('rect', { x, y:2.20, w:2.85, h:0.42,
      fill:{color}, line:{color, width:0} });
    s.addText(model, {
      x, y:2.20, w:2.85, h:0.42,
      fontSize:12.5, fontFace:F, color:WHT, bold:true,
      align:'center', valign:'middle', margin:0 });
    s.addShape('rect', { x, y:2.62, w:2.85, h:2.48,
      fill:{color:LGY}, line:{color:MGY, width:1} });
    points.forEach(([txt, c], j) => {
      const mark = c === GRN ? '✓' : (c === RED ? '✗' : '~');
      s.addText(mark + '  ' + txt, {
        x:x+0.1, y:2.68 + j * 0.60, w:2.65, h:0.55,
        fontSize:11, fontFace:F, color:c, align:'left', margin:0 });
    });
  });

  s.addText('➡  CatBoost là lựa chọn duy nhất duy trì FPR thấp khi tăng data — phù hợp nhất cho production IDS', {
    x:0.45, y:5.18, w:9.1, h:0.32,
    fontSize:11, fontFace:F, color:RED, bold:true, align:'left', margin:0 });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 16 — MODEL CUỐI CÙNG
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '07  KẾT QUẢ THỰC NGHIỆM');
  sTitle(s, 'LỰA CHỌN CUỐI CÙNG: CATBOOST');

  hrule(s, 0.45, 1.56, 9.1);

  // Big model name
  s.addShape('rect', { x:0.45, y:1.68, w:4.35, h:3.55,
    fill:{color:NAV}, line:{color:NAV, width:0} });
  s.addShape('rect', { x:0.45, y:1.68, w:4.35, h:0.06,
    fill:{color:RED}, line:{color:RED, width:0} });
  s.addText('⭐', {
    x:0.45, y:1.75, w:4.35, h:0.65,
    fontSize:36, fontFace:F, color:WHT, align:'center', valign:'middle', margin:0 });
  s.addText('CatBoost', {
    x:0.45, y:2.42, w:4.35, h:0.70,
    fontSize:30, fontFace:F, color:WHT, bold:true,
    align:'center', valign:'middle', margin:0 });
  s.addText('Gradient Boosting\nwith Ordered Boosting', {
    x:0.45, y:3.15, w:4.35, h:0.52,
    fontSize:12, fontFace:F, color:MGY,
    align:'center', valign:'middle', margin:0 });

  // Stats row in dark card
  const stats = [['99.46%', 'F1-Score'], ['0.31%', 'FPR'], ['99.41%', 'OOD Recall']];
  stats.forEach(([val, label], i) => {
    const x = 0.55 + i * 1.42;
    s.addText(val, {
      x, y:3.75, w:1.25, h:0.52,
      fontSize:18, fontFace:F, color:WHT, bold:true,
      align:'center', valign:'middle', margin:0 });
    s.addText(label, {
      x, y:4.30, w:1.25, h:0.30,
      fontSize:10, fontFace:F, color:MGY,
      align:'center', valign:'top', margin:0 });
  });

  // Right — Reasons
  s.addText('LÝ DO LỰA CHỌN', {
    x:4.98, y:1.68, w:4.57, h:0.38,
    fontSize:12, fontFace:F, color:NAV, bold:true, align:'left', margin:0, charSpacing:2 });

  const reasons = [
    [GRN, 'FPR thấp nhất: 0.31%', 'Ít cảnh báo nhầm nhất trong 5 model — tốt nhất cho production.'],
    [GRN, 'F1-Score cao: 99.46%', 'Phát hiện gần như toàn bộ tấn công, ít bỏ sót.'],
    [GRN, 'Train nhanh nhất', 'Hoàn thành trên full 18.6M rows nhanh hơn RF và HistGB.'],
    [GRN, 'Ổn định khi scale', 'FPR không tăng khi thêm data — khác với Random Forest.'],
    [GRN, 'Ít hyperparameter tuning', 'Out-of-box đã cho kết quả tốt, phù hợp production.'],
  ];
  reasons.forEach(([color, title, desc], i) => {
    const y = 2.14 + i * 0.88;
    s.addShape('rect', { x:4.98, y, w:0.06, h:0.78,
      fill:{color}, line:{color, width:0} });
    s.addText(title, {
      x:5.12, y, w:4.38, h:0.35,
      fontSize:12.5, fontFace:F, color, bold:true, align:'left', margin:0 });
    s.addText(desc, {
      x:5.12, y:y+0.36, w:4.38, h:0.42,
      fontSize:11, fontFace:F, color:GRY, align:'left', margin:0 });
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 17 — TRIỂN KHAI HỆ THỐNG
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '08  TRIỂN KHAI');
  sTitle(s, 'TRIỂN KHAI HỆ THỐNG IDS THỰC TẾ');

  hrule(s, 0.45, 1.56, 9.1);

  s.addText('Hệ thống được triển khai hoàn chỉnh trên 1 máy Linux — từ capture đến dashboard:', {
    x:0.45, y:1.62, w:9.1, h:0.42,
    fontSize:12, fontFace:F, color:BLK, align:'left', margin:0 });

  const components = [
    [RED,  'Linux Sensor',        'live_capture.py',
     'Bắt packet bằng tcpdump/scapy, trích xuất flow features, đẩy vào inference queue.'],
    [NAV,  'Inference Engine',    'inference_engine.py',
     'Load CatBoost model bundle. Real-time prediction. Output: benign / attack type.'],
    [TEA,  'Realtime Pipeline',   'pipeline.py',
     'Kết nối sensor và engine. Buffer management. Xử lý backpressure.'],
    [GRN,  'Web Dashboard',       'web.py (Flask)',
     'Giao diện vận hành: alert feed, thống kê, lịch sử tấn công. Auto-refresh.'],
    [ORG,  'Telegram Alerts',     'notifications.py',
     'Gửi cảnh báo tức thì qua Telegram Bot khi phát hiện tấn công có độ tin cậy cao.'],
  ];

  components.forEach(([color, name, file, desc], i) => {
    const y = 2.12 + i * 0.64;
    s.addShape('rect', { x:0.45, y, w:9.1, h:0.56,
      fill:{color:LGY}, line:{color:MGY, width:1} });
    s.addShape('rect', { x:0.45, y, w:0.08, h:0.56,
      fill:{color}, line:{color, width:0} });
    s.addText(name, {
      x:0.60, y, w:2.20, h:0.56,
      fontSize:12.5, fontFace:F, color, bold:true,
      align:'left', valign:'middle', margin:0 });
    s.addText(file, {
      x:2.82, y, w:1.65, h:0.56,
      fontSize:10.5, fontFace:F, color:DGY, italic:true,
      align:'left', valign:'middle', margin:0 });
    s.addShape('rect', { x:4.52, y:y+0.10, w:0.02, h:0.36,
      fill:{color:MGY}, line:{color:MGY, width:0} });
    s.addText(desc, {
      x:4.62, y, w:4.88, h:0.56,
      fontSize:11, fontFace:F, color:GRY,
      align:'left', valign:'middle', margin:0 });
  });

  s.addText('✅  Hệ thống deploy được thật — không phải prototype. Đã test với traffic thực và passing > 140 tests.', {
    x:0.45, y:5.36, w:9.1, h:0.22,
    fontSize:10, fontFace:F, color:GRN, bold:true, italic:true, align:'left', margin:0 });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 18 — DEMO HỆ THỐNG
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '08  TRIỂN KHAI');
  sTitle(s, 'DEMO HỆ THỐNG — GIAO DIỆN VẬN HÀNH');

  hrule(s, 0.45, 1.56, 9.1);

  // Three demo panels
  const panels = [
    [NAV, 'OVERVIEW', 'Thống kê tổng quan:\nTotal flows · Attack rate\nTop attack types · Timeline'],
    [RED, 'ALERT FEED', 'Danh sách cảnh báo real-time:\nAttack type · Confidence\nSrc IP · Timestamp'],
    [ORG, 'TELEGRAM', 'Cảnh báo tức thì:\nBot gửi message ngay\nkhi phát hiện tấn công\n(high-confidence only)'],
  ];

  panels.forEach(([color, title, desc], i) => {
    const x = 0.45 + i * 3.05;
    // Panel frame
    s.addShape('rect', { x, y:1.70, w:2.85, h:3.40,
      fill:{color:'F8F8F8'}, line:{color:MGY, width:1} });
    // Header bar
    s.addShape('rect', { x, y:1.70, w:2.85, h:0.44,
      fill:{color}, line:{color, width:0} });
    s.addText(title, {
      x, y:1.70, w:2.85, h:0.44,
      fontSize:12.5, fontFace:F, color:WHT, bold:true,
      align:'center', valign:'middle', margin:0 });
    // Mock screen
    s.addShape('rect', { x:x+0.1, y:2.20, w:2.65, h:2.05,
      fill:{color:'E8E8E8'}, line:{color:DGY, width:1} });
    s.addText('[Screenshot\ndashboard\nsẽ được chèn\nvào đây]', {
      x:x+0.1, y:2.20, w:2.65, h:2.05,
      fontSize:11, fontFace:F, color:GRY, italic:true,
      align:'center', valign:'middle', margin:0 });
    // Description
    s.addText(desc, {
      x:x+0.08, y:4.28, w:2.69, h:0.76,
      fontSize:10.5, fontFace:F, color:GRY,
      align:'left', valign:'top', margin:0 });
  });

  s.addText('💡  Thêm ảnh demo thật vào slide này là điểm cộng lớn với hội đồng', {
    x:0.45, y:5.22, w:9.1, h:0.30,
    fontSize:11, fontFace:F, color:ORG, bold:true, italic:true, align:'left', margin:0 });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 19 — ĐÁNH GIÁ HỆ THỐNG
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '09  ĐÁNH GIÁ');
  sTitle(s, 'ĐÁNH GIÁ HỆ THỐNG — ƯU & NHƯỢC ĐIỂM');

  hrule(s, 0.45, 1.56, 9.1);

  // Left — Pros
  s.addShape('rect', { x:0.45, y:1.62, w:4.45, h:0.38,
    fill:{color:GRN}, line:{color:GRN, width:0} });
  s.addText('✓  ƯU ĐIỂM', {
    x:0.55, y:1.62, w:4.25, h:0.38,
    fontSize:12, fontFace:F, color:WHT, bold:true,
    align:'left', valign:'middle', margin:0, charSpacing:2 });

  const pros = [
    ['FPR thấp: 0.31%', 'Số cảnh báo nhầm cực thấp — quản trị viên có thể tin tưởng mỗi cảnh báo.'],
    ['Real-time inference', 'Xử lý flow ngay khi capture — độ trễ < 1 giây.'],
    ['Scalable pipeline', 'Có thể mở rộng với buffer queue, không bị nghẽn.'],
    ['Two-stage detection', 'Không chỉ biết là attack, mà còn biết attack loại gì.'],
    ['Telegram alerts', 'Thông báo ngay trên điện thoại — không cần ngồi xem dashboard.'],
  ];
  pros.forEach(([title, desc], i) => {
    const y = 2.10 + i * 0.64;
    s.addShape('rect', { x:0.45, y, w:0.07, h:0.54,
      fill:{color:GRN}, line:{color:GRN, width:0} });
    s.addText(title, {
      x:0.60, y, w:4.25, h:0.26,
      fontSize:12, fontFace:F, color:GRN, bold:true, align:'left', margin:0 });
    s.addText(desc, {
      x:0.60, y:y+0.26, w:4.25, h:0.30,
      fontSize:10.5, fontFace:F, color:GRY, align:'left', margin:0 });
  });

  // Divider
  s.addShape('rect', { x:5.08, y:1.62, w:0.02, h:3.55,
    fill:{color:MGY}, line:{color:MGY, width:0} });

  // Right — Cons
  s.addShape('rect', { x:5.22, y:1.62, w:4.33, h:0.38,
    fill:{color:RED}, line:{color:RED, width:0} });
  s.addText('✗  NHƯỢC ĐIỂM', {
    x:5.32, y:1.62, w:4.13, h:0.38,
    fontSize:12, fontFace:F, color:WHT, bold:true,
    align:'left', valign:'middle', margin:0, charSpacing:2 });

  const cons = [
    ['Chưa multi-host', 'Hiện tại chỉ monitor được 1 máy. Không có centralized view.'],
    ['Chưa xử lý concept drift', 'Nếu attack pattern thay đổi theo thời gian, model cần retrain thủ công.'],
    ['Không DPI', 'Không phân tích nội dung packet — bỏ qua các tấn công application-layer tinh vi.'],
    ['Lab data', 'Dataset là traffic lab, không phải production — có thể khác với môi trường thực tế.'],
  ];
  cons.forEach(([title, desc], i) => {
    const y = 2.10 + i * 0.76;
    s.addShape('rect', { x:5.22, y, w:0.07, h:0.66,
      fill:{color:RED}, line:{color:RED, width:0} });
    s.addText(title, {
      x:5.37, y, w:4.13, h:0.28,
      fontSize:12, fontFace:F, color:RED, bold:true, align:'left', margin:0 });
    s.addText(desc, {
      x:5.37, y:y+0.28, w:4.13, h:0.38,
      fontSize:11, fontFace:F, color:GRY, align:'left', margin:0 });
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 20 — KẾT LUẬN
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '10  KẾT LUẬN');
  sTitle(s, 'KẾT LUẬN ĐỒ ÁN');

  hrule(s, 0.45, 1.56, 9.1);

  const conclusions = [
    ['01', NAV, 'Đã xây dựng IDS ML hoàn chỉnh',
     'Hệ thống IDS anomaly-based đầy đủ: từ data pipeline đến real-time inference và operator console với > 140 tests passing.'],
    ['02', RED, 'CatBoost là lựa chọn tốt nhất',
     'FPR 0.31% thấp nhất, F1 99.46%, train nhanh và ổn định khi scale — vượt trội hoàn toàn so với LogReg và MLP.'],
    ['03', GRN, 'Hệ thống có thể deploy thực tế',
     'Không chỉ là nghiên cứu — hệ thống chạy được trên Linux, có web dashboard và Telegram alerts.'],
  ];

  conclusions.forEach(([num, color, title, desc], i) => {
    const y = 1.70 + i * 1.15;
    s.addShape('rect', { x:0.45, y, w:9.1, h:1.05,
      fill:{color:LGY}, line:{color:MGY, width:1} });
    s.addShape('rect', { x:0.45, y, w:0.72, h:1.05,
      fill:{color}, line:{color, width:0} });
    s.addText(num, {
      x:0.45, y, w:0.72, h:1.05,
      fontSize:28, fontFace:F, color:WHT, bold:true,
      align:'center', valign:'middle', margin:0 });
    s.addText(title, {
      x:1.26, y:y+0.05, w:8.20, h:0.38,
      fontSize:14, fontFace:F, color, bold:true,
      align:'left', valign:'middle', margin:0 });
    s.addText(desc, {
      x:1.26, y:y+0.46, w:8.20, h:0.55,
      fontSize:12, fontFace:F, color:GRY,
      align:'left', valign:'top', margin:0 });
  });

  s.addShape('rect', { x:0.45, y:5.10, w:9.1, h:0.22,
    fill:{color:NAV}, line:{color:NAV, width:0} });
  s.addText('Đồ án đạt cả 3 mục tiêu ban đầu: Benchmark ML · Chọn model tối ưu · Deploy hệ thống thực tế', {
    x:0.55, y:5.10, w:8.90, h:0.22,
    fontSize:10.5, fontFace:F, color:WHT, bold:true,
    align:'center', valign:'middle', margin:0 });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 21 — HƯỚNG PHÁT TRIỂN
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  secLbl(s, '10  KẾT LUẬN');
  sTitle(s, 'HƯỚNG PHÁT TRIỂN TIẾP THEO');

  hrule(s, 0.45, 1.56, 9.1);

  const futures = [
    [NAV,  '🌐', 'Multi-host Deployment',
     'Mở rộng sang nhiều máy với centralized dashboard. Tích hợp SIEM để quản lý tập trung.'],
    [ORG,  '📊', 'Drift Detection',
     'Tự động phát hiện khi distribution của traffic thay đổi và trigger retraining model.'],
    [TEA,  '🤖', 'Deep Learning',
     'Thử nghiệm LSTM/Transformer cho traffic sequence — có thể tốt hơn với temporal patterns.'],
    [GRN,  '🔗', 'SIEM Integration',
     'Kết nối với Splunk, ELK Stack hoặc Wazuh để dễ dàng tích hợp vào security operations.'],
  ];

  futures.forEach(([color, icon, title, desc], i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = col === 0 ? 0.45 : 5.22;
    const y = 1.68 + row * 1.72;

    s.addShape('rect', { x, y, w:4.60, h:1.55,
      fill:{color:LGY}, line:{color:MGY, width:1} });
    s.addShape('rect', { x, y, w:4.60, h:0.46,
      fill:{color}, line:{color, width:0} });
    s.addText(icon + '  ' + title, {
      x:x+0.08, y, w:4.44, h:0.46,
      fontSize:13, fontFace:F, color:WHT, bold:true,
      align:'left', valign:'middle', margin:0 });
    s.addText(desc, {
      x:x+0.10, y:y+0.52, w:4.40, h:0.95,
      fontSize:12, fontFace:F, color:GRY,
      align:'left', valign:'top', margin:0 });
  });

  s.addText('Hướng phát triển gần nhất: Multi-host + Drift Detection — hai tính năng quan trọng nhất cho production', {
    x:0.45, y:5.18, w:9.1, h:0.30,
    fontSize:10, fontFace:F, color:DGY, italic:true, align:'left', margin:0 });
});

// ═══════════════════════════════════════════════════════════════════════════════
// SLIDE 22 — Q&A
// ═══════════════════════════════════════════════════════════════════════════════
addSlide(s => {
  // Dark background for closing slide
  s.background = { color: NAV };

  // Override footer rule color
  s.addShape('rect', { x:0, y:5.33, w:10, h:0.02,
    fill:{color:WHT}, line:{color:WHT, width:0} });
  s.addText(String(N), {
    x:9.0, y:5.36, w:0.8, h:0.22,
    fontSize:11, fontFace:F, color:WHT, align:'right', valign:'top', margin:0 });

  // Header logos on dark background
  s.addShape('rect', { x:0, y:0.585, w:10, h:0.02,
    fill:{color:WHT}, line:{color:WHT, width:0} });
  s.addImage({ path:IMG.hutech,   x:0.15, y:0.07, w:1.40, h:0.45 });
  s.addImage({ path:IMG.awards,   x:1.62, y:0.07, w:0.46, h:0.44 });
  s.addImage({ path:IMG.hutech30, x:8.08, y:0.09, w:0.80, h:0.33 });
  s.addImage({ path:IMG.qsstars,  x:8.96, y:0.09, w:0.88, h:0.38 });

  // Red accent bar
  s.addShape('rect', { x:3.8, y:1.95, w:2.4, h:0.08,
    fill:{color:RED}, line:{color:RED, width:0} });

  // Q&A text
  s.addText('Q & A', {
    x:0.5, y:2.08, w:9.0, h:1.25,
    fontSize:64, fontFace:F, color:WHT, bold:true,
    align:'center', valign:'middle', margin:0, charSpacing:20 });

  s.addShape('rect', { x:3.8, y:3.35, w:2.4, h:0.08,
    fill:{color:RED}, line:{color:RED, width:0} });

  s.addText('CẢM ƠN THẦY/CÔ ĐÃ LẮNG NGHE', {
    x:0.5, y:3.52, w:9.0, h:0.48,
    fontSize:16, fontFace:F, color:MGY,
    align:'center', valign:'middle', margin:0, charSpacing:4 });

  // Project summary bar
  s.addShape('rect', { x:1.5, y:4.18, w:7.0, h:0.65,
    fill:{color:'FFFFFF'}, line:{color:'FFFFFF', width:0} });
  s.addShape('rect', { x:1.5, y:4.18, w:0.06, h:0.65,
    fill:{color:RED}, line:{color:RED, width:0} });
  s.addText([
    { text:'IDS ML · ', options:{ color:NAV, bold:true } },
    { text:'CatBoost · FPR 0.31% · F1 99.46% · Real-time dashboard · Telegram alerts', options:{ color:DGY } }
  ], {
    x:1.65, y:4.18, w:6.70, h:0.65,
    fontSize:12, fontFace:F,
    align:'left', valign:'middle', margin:0 });
});

// ─── Write ────────────────────────────────────────────────────────────────────
pres.writeFile({ fileName: 'IDS_ML_Presentation.pptx' })
  .then(() => console.log('✅  IDS_ML_Presentation.pptx written'))
  .catch(e  => { console.error('❌', e.message); process.exit(1); });
