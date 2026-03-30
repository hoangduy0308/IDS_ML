const path = require("path");
const pptxgen = require("pptxgenjs");
const { imageSizingContain } = require("./pptxgenjs_helpers/image");
const {
  warnIfSlideHasOverlaps,
  warnIfSlideElementsOutOfBounds,
} = require("./pptxgenjs_helpers/layout");
const ShapeType = new pptxgen().ShapeType;
const ChartType = new pptxgen().ChartType;

const ROOT = path.resolve(__dirname, "..", "..", "..");
const FIGURES = path.join(ROOT, "docs", "figures");
const OUTLINE_PATH = path.join(__dirname, "presentation_outline_vi.md");
const OUT_PPTX = path.join(__dirname, "IDS_ML_Thuyet_Trinh_Hoan_Chinh.pptx");

const COLORS = {
  ink: "0E1B2A",
  inkSoft: "41576D",
  teal: "2B7A78",
  tealSoft: "E2F3F1",
  blue: "3D6C8D",
  blueSoft: "E7F0F6",
  orange: "C96A2B",
  orangeSoft: "F6E7DA",
  green: "4E8B61",
  greenSoft: "E8F2EA",
  red: "AE4C4C",
  redSoft: "F7E4E4",
  sand: "F2E8DC",
  paper: "FCF8F2",
  gray: "7A7A76",
  line: "DED7CE",
  white: "FFFFFF",
  charcoal: "132436",
  mist: "F5F1EA",
};

const datasetStats = {
  sourceFiles: 133,
  sizeGb: 13.65,
  features: 72,
  splits: [
    { label: "Train", rows: 18679445, rowsM: 18.68 },
    { label: "Validation", rows: 4410064, rowsM: 4.41 },
    { label: "Test", rows: 4145539, rowsM: 4.15 },
    { label: "OOD Holdout", rows: 444422, rowsM: 0.44 },
  ],
};

const benchmarkModels = [
  { label: "CatBoost", testF1: 0.9909, fpr: 0.012639, oodRecall: 0.400354, trainSeconds: 127.68 },
  { label: "RandomForest", testF1: 0.990995, fpr: 0.015304, oodRecall: 0.400354, trainSeconds: 136.63 },
  { label: "HistGB", testF1: 0.99096, fpr: 0.014463, oodRecall: 0.39721, trainSeconds: 306.22 },
  { label: "LogReg", testF1: 0.990002, fpr: 0.770623, oodRecall: 0.816622, trainSeconds: 165.4 },
  { label: "MLP", testF1: 0.989924, fpr: 0.978086, oodRecall: 0.998956, trainSeconds: 566.06 },
];

const scalingRuns = {
  labels: ["2M", "4M", "8M", "18.68M"],
  f1: {
    CatBoost: [0.99311, 0.993191, 0.993267, 0.993358],
    HistGB: [0.992478, 0.992708, 0.992704, null],
    RandomForest: [0.993182, 0.993852, 0.994047, null],
  },
  fpr: {
    CatBoost: [0.022921, 0.026285, 0.025184, 0.027411],
    HistGB: [0.017366, 0.020173, 0.019889, null],
    RandomForest: [0.02638, 0.033167, 0.040287, null],
  },
};

const finalModel = {
  threshold: 0.5,
  testF1: 0.993358,
  testFpr: 0.027411,
  oodRecall: 0.499575,
  altThreshold: 0.475,
  altF1: 0.993411,
  altFpr: 0.028358,
  altOodRecall: 0.503949,
};

const validationStats = { docs: 21, scripts: 40, tests: 28, deployArtifacts: 4 };

function fmtPct(value, digits = 2) {
  return `${(value * 100).toFixed(digits)}%`;
}

function addCanvas(slide) {
  slide.background = { color: COLORS.paper };
  slide.addShape(ShapeType.rect, {
    x: 0,
    y: 0,
    w: 13.333,
    h: 0.24,
    fill: { color: COLORS.ink },
    line: { color: COLORS.ink },
  });
  slide.addShape(ShapeType.rect, {
    x: 0.62,
    y: 0.78,
    w: 0.06,
    h: 0.94,
    fill: { color: COLORS.orange },
    line: { color: COLORS.orange },
  });
  slide.addShape(ShapeType.rect, {
    x: 10.45,
    y: 0.9,
    w: 2.2,
    h: 0.04,
    fill: { color: COLORS.orange, transparency: 28 },
    line: { color: COLORS.orange, transparency: 28 },
  });
  slide.addShape(ShapeType.ellipse, {
    x: 11.45,
    y: 0.32,
    w: 1.18,
    h: 1.18,
    line: { color: COLORS.orange, transparency: 82, pt: 1.0 },
    fill: { color: COLORS.orange, transparency: 100 },
  });
  slide.addShape(ShapeType.ellipse, {
    x: 0.08,
    y: 5.75,
    w: 1.08,
    h: 1.08,
    line: { color: COLORS.teal, transparency: 86, pt: 0.9 },
    fill: { color: COLORS.teal, transparency: 100 },
  });
}

function addHeader(slide, page, title, kicker) {
  addCanvas(slide);
  slide.addText(kicker, {
    x: 0.84, y: 0.66, w: 4.4, h: 0.26, color: COLORS.orange, fontFace: "Bahnschrift",
    fontSize: 11, bold: true, characterSpacing: 1.2,
  });
  slide.addText(title, {
    x: 0.84, y: 0.94, w: 8.75, h: 0.5, color: COLORS.ink, fontFace: "Bahnschrift",
    fontSize: 25, bold: true,
  });
  slide.addShape(ShapeType.rect, {
    x: 0.84,
    y: 1.52,
    w: 2.15,
    h: 0.04,
    fill: { color: COLORS.orange },
    line: { color: COLORS.orange },
  });
  slide.addText(`${String(page).padStart(2, "0")}`, {
    x: 11.82, y: 0.62, w: 0.55, h: 0.26, align: "right", color: COLORS.gray,
    fontFace: "Bahnschrift", fontSize: 12, bold: true,
  });
}

function addFooter(slide, text) {
  slide.addText(text, {
    x: 0.6, y: 7.08, w: 10.4, h: 0.18, color: COLORS.gray,
    fontFace: "Aptos", fontSize: 9,
  });
}

function addSectionCard(slide, x, y, w, h, title, body, accent, tint) {
  const compact = h < 0.95;
  const titleY = compact ? y + 0.2 : y + 0.24;
  const titleSize = compact ? 12.8 : 14.5;
  const bodyY = compact ? y + 0.4 : y + 0.6;
  const bodyH = Math.max(0.2, h - (compact ? 0.5 : 0.74));
  const bodySize = compact ? 9.6 : 10.5;
  slide.addShape(ShapeType.rect, {
    x, y, w, h, fill: { color: tint }, line: { color: tint },
  });
  slide.addShape(ShapeType.rect, {
    x, y, w: 0.08, h, fill: { color: accent }, line: { color: accent },
  });
  slide.addShape(ShapeType.rect, {
    x: x + 0.16, y: y + 0.14, w: compact ? 0.38 : 0.52, h: 0.03, fill: { color: accent }, line: { color: accent },
  });
  slide.addText(title, {
    x: x + 0.22, y: titleY, w: w - 0.34, h: 0.24, fontFace: "Bahnschrift",
    fontSize: titleSize, bold: true, color: COLORS.ink,
  });
  slide.addText(body, {
    x: x + 0.22, y: bodyY, w: w - 0.34, h: bodyH, fontFace: "Aptos",
    fontSize: bodySize, color: COLORS.inkSoft, valign: "top", margin: 0.02,
  });
}

function addNumberCard(slide, x, y, w, h, label, value, accent, tint, subtext) {
  slide.addShape(ShapeType.rect, {
    x, y, w, h, fill: { color: tint }, line: { color: tint },
  });
  slide.addShape(ShapeType.rect, {
    x, y, w, h: 0.04, fill: { color: accent }, line: { color: accent },
  });
  slide.addText(label, {
    x: x + 0.16, y: y + 0.12, w: w - 0.32, h: 0.2, fontFace: "Aptos",
    fontSize: 10.3, color: COLORS.gray, bold: true,
  });
  slide.addText(value, {
    x: x + 0.16, y: y + 0.34, w: w - 0.32, h: 0.42, fontFace: "Bahnschrift",
    fontSize: 22, color: accent, bold: true,
  });
  if (subtext) {
    slide.addText(subtext, {
      x: x + 0.16, y: y + 0.83, w: w - 0.32, h: h - 0.92, fontFace: "Aptos",
      fontSize: 9.5, color: COLORS.inkSoft,
    });
  }
}

function addBulletBlock(slide, x, y, w, h, text, fontSize = 14, color = COLORS.inkSoft) {
  slide.addText(text, {
    x, y, w, h, fontFace: "Aptos", fontSize, color, valign: "top", bullet: true,
    margin: 0.05, paraSpaceAfterPt: 8,
  });
}

function addProcessArrow(slide, x, y, w, h, label, fill, textColor = COLORS.white) {
  slide.addShape(ShapeType.rect, {
    x, y, w, h, fill: { color: fill }, line: { color: fill },
  });
  slide.addText(label, {
    x: x + 0.08, y: y + 0.14, w: w - 0.2, h: h - 0.2, align: "center", valign: "mid",
    fontFace: "Bahnschrift", fontSize: 11, bold: true, color: textColor,
  });
}

function addFlowNode(slide, x, y, w, h, title, subtitle, fill, textColor = COLORS.ink) {
  slide.addShape(ShapeType.rect, {
    x, y, w, h, fill: { color: fill }, line: { color: fill },
  });
  slide.addText(title, {
    x: x + 0.12, y: y + 0.16, w: w - 0.24, h: 0.22, fontFace: "Bahnschrift",
    fontSize: 12, bold: true, color: textColor, align: "center",
  });
  slide.addText(subtitle, {
    x: x + 0.12, y: y + 0.48, w: w - 0.24, h: h - 0.58, fontFace: "Aptos",
    fontSize: 9.5, color: textColor, align: "center", valign: "mid",
  });
}

function addArrowConnector(slide, x1, y1, x2, y2, color = COLORS.inkSoft) {
  slide.addShape(ShapeType.rect, {
    x: Math.min(x1, x2),
    y: Math.min(y1, y2) + Math.abs(y2 - y1) / 2 - 0.015,
    w: Math.max(0.12, Math.abs(x2 - x1)),
    h: 0.035,
    fill: { color },
    line: { color },
  });
}

function finalizeSlide(slide, pptx) {
  warnIfSlideHasOverlaps(slide, pptx, { ignoreDecorativeShapes: true, muteContainment: true });
  warnIfSlideElementsOutOfBounds(slide, pptx);
}

function fig(name) {
  return path.join(FIGURES, name);
}

async function main() {
  const pptx = new pptxgen();
  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "OpenAI Codex";
  pptx.company = "IDS_ML_New";
  pptx.subject = "Hệ thống IDS dựa trên Machine Learning";
  pptx.title = "Xây dựng hệ thống IDS dựa trên ML";
  pptx.lang = "vi-VN";
  pptx.theme = { headFontFace: "Bahnschrift", bodyFontFace: "Aptos", lang: "vi-VN" };
  pptx.defineSlideMaster({
    title: "IDS_MASTER",
    background: { color: COLORS.paper },
    objects: [],
    slideNumber: { x: 12.55, y: 7.05, w: 0.35, h: 0.18, color: COLORS.gray, fontSize: 8 },
  });

  let slide = pptx.addSlide("IDS_MASTER");
  addCanvas(slide);
  slide.addShape(ShapeType.rect, {
    x: 0, y: 0.24, w: 7.85, h: 5.42, fill: { color: COLORS.charcoal }, line: { color: COLORS.charcoal },
  });
  slide.addShape(ShapeType.rect, {
    x: 7.85, y: 0.24, w: 5.48, h: 5.42, fill: { color: COLORS.mist }, line: { color: COLORS.mist },
  });
  slide.addShape(ShapeType.rect, {
    x: 0.88, y: 1.1, w: 0.09, h: 2.95, fill: { color: COLORS.orange }, line: { color: COLORS.orange },
  });
  slide.addText("ĐỀ TÀI TỐT NGHIỆP", {
    x: 1.18, y: 1.06, w: 3.0, h: 0.3, color: "F3C9A8", fontFace: "Bahnschrift",
    fontSize: 12, bold: true, characterSpacing: 1.2,
  });
  slide.addText("XÂY DỰNG HỆ THỐNG IDS\nDỰA TRÊN MACHINE LEARNING", {
    x: 1.18, y: 1.46, w: 5.95, h: 1.72, color: COLORS.white, fontFace: "Bahnschrift",
    fontSize: 28, bold: true,
  });
  slide.addText("Bài thuyết trình này đi từ bài toán IDS, cách chuẩn hóa dữ liệu và protocol thực nghiệm, đến quyết định chọn CatBoost full-data và phần kiến trúc vận hành realtime trên host thật.", {
    x: 1.18, y: 3.42, w: 5.55, h: 1.0, color: "D7E2EC", fontFace: "Aptos", fontSize: 12.4,
  });
  slide.addText("Trục nội dung", {
    x: 8.45, y: 1.02, w: 3.0, h: 0.28, fontFace: "Bahnschrift", fontSize: 18, color: COLORS.ink, bold: true,
  });
  slide.addText("01", {
    x: 8.45, y: 1.55, w: 0.6, h: 0.36, fontFace: "Bahnschrift", fontSize: 22, bold: true, color: COLORS.orange,
  });
  slide.addText("Bài toán và mục tiêu hệ thống IDS", {
    x: 9.12, y: 1.58, w: 3.48, h: 0.28, fontFace: "Aptos", fontSize: 12.4, color: COLORS.inkSoft,
  });
  slide.addText("02", {
    x: 8.45, y: 2.15, w: 0.6, h: 0.36, fontFace: "Bahnschrift", fontSize: 22, bold: true, color: COLORS.orange,
  });
  slide.addText("Dữ liệu, tiền xử lý và protocol thực nghiệm", {
    x: 9.12, y: 2.18, w: 3.48, h: 0.28, fontFace: "Aptos", fontSize: 12.4, color: COLORS.inkSoft,
  });
  slide.addText("03", {
    x: 8.45, y: 2.75, w: 0.6, h: 0.36, fontFace: "Bahnschrift", fontSize: 22, bold: true, color: COLORS.orange,
  });
  slide.addText("Kết quả chọn model, threshold và model bundle", {
    x: 9.12, y: 2.78, w: 3.48, h: 0.28, fontFace: "Aptos", fontSize: 12.4, color: COLORS.inkSoft,
  });
  slide.addText("04", {
    x: 8.45, y: 3.35, w: 0.6, h: 0.36, fontFace: "Bahnschrift", fontSize: 22, bold: true, color: COLORS.orange,
  });
  slide.addText("Runtime IDS, live sensor và vận hành same-host", {
    x: 9.12, y: 3.38, w: 3.48, h: 0.32, fontFace: "Aptos", fontSize: 12.4, color: COLORS.inkSoft,
  });
  addNumberCard(slide, 8.45, 4.35, 1.7, 1.02, "Feature", `${datasetStats.features}`, COLORS.orange, COLORS.orangeSoft, "Schema canonical");
  addNumberCard(slide, 10.35, 4.35, 1.85, 1.02, "Model chốt", "CatBoost", COLORS.teal, COLORS.tealSoft, "Threshold 0.5");
  slide.addText("Điểm nổi bật", {
    x: 1.18, y: 4.78, w: 2.0, h: 0.24, color: "F3C9A8", fontFace: "Bahnschrift", fontSize: 11.5, bold: true,
  });
  slide.addText("Project không dừng ở mô hình offline mà đã đi tới bundle versioned, pipeline realtime, cảm biến host-based và lớp vận hành có thể demo.", {
    x: 1.18, y: 5.08, w: 5.9, h: 0.55, color: COLORS.white, fontFace: "Aptos", fontSize: 11.2,
  });
  addFooter(slide, "Đề tài tập trung vào một hệ thống IDS dựa trên ML theo hướng có thể triển khai, chứ không chỉ dừng ở mô hình offline.");
  finalizeSlide(slide, pptx);

  slide = pptx.addSlide("IDS_MASTER");
  addHeader(slide, 2, "Bài toán, mục tiêu và đóng góp", "01  VẤN ĐỀ NGHIÊN CỨU");
  addSectionCard(slide, 0.7, 1.64, 4.0, 1.58, "Bài toán", "Hệ thống IDS cần phát hiện lưu lượng tấn công từ network flow, nhưng đồng thời phải kiểm soát false positive để có thể đưa vào vận hành thực tế mà không gây quá nhiều nhiễu cho người quản trị.", COLORS.orange, COLORS.orangeSoft);
  addSectionCard(slide, 4.95, 1.64, 3.75, 1.58, "Mục tiêu học thuật", "So sánh nhiều họ mô hình trên cùng một protocol đánh giá, từ đó phân tích trade-off giữa F1, FPR, OOD recall và chi phí huấn luyện.", COLORS.blue, COLORS.blueSoft);
  addSectionCard(slide, 8.95, 1.64, 3.65, 1.58, "Mục tiêu hệ thống", "Đóng gói model thành bundle có contract, xây dựng runtime realtime, live sensor host-based và operator console để chứng minh khả năng triển khai thành hệ thống IDS hoàn chỉnh.", COLORS.teal, COLORS.tealSoft);
  addBulletBlock(slide, 0.85, 3.55, 5.65, 2.7, "Project không dừng ở benchmark notebook, mà đã đi tới bundle versioned, verify/promote/rollback và stack vận hành same-host.\nRanh giới V1 được định nghĩa rõ: flow-based IDS, micro-batch near-real-time, single host, single NIC, local outputs và dashboard nội bộ.\nCâu hỏi trung tâm của đề tài là: mô hình nào cân bằng nhất để đưa vào IDS thực tế, thay vì chỉ tối ưu một chỉ số đơn lẻ.", 11.6, COLORS.inkSoft);
  addNumberCard(slide, 7.35, 3.78, 1.65, 1.0, "Mô hình", "5", COLORS.ink, COLORS.sand, "Benchmark vòng đầu");
  addNumberCard(slide, 9.15, 3.78, 1.65, 1.0, "Finalist", "3", COLORS.blue, COLORS.blueSoft, "CatBoost, RF, HistGB");
  addNumberCard(slide, 10.95, 3.78, 1.65, 1.0, "Test suite", `${validationStats.tests}`, COLORS.green, COLORS.greenSoft, "Bao phủ runtime");
  addSectionCard(slide, 7.2, 5.0, 5.35, 1.35, "Thông điệp khoa học", "CatBoost full-data không đứng đầu tuyệt đối ở mọi metric, nhưng lại là lựa chọn cân bằng nhất giữa hiệu năng phát hiện, FPR, khả năng scale và mức độ sẵn sàng để deploy.", COLORS.green, COLORS.greenSoft);
  addFooter(slide, "Mục tiêu của project là tạo ra một IDS có thể giải thích, tái lập và vận hành được, thay vì chỉ tối ưu duy nhất một metric.");
  finalizeSlide(slide, pptx);

  slide = pptx.addSlide("IDS_MASTER");
  addHeader(slide, 3, "Phạm vi repo và các lớp thành phần", "02  TOÀN CẢNH PROJECT");
  addSectionCard(slide, 0.7, 1.6, 3.0, 2.1, "Lớp dữ liệu", "Nguồn CIC IoT-DIAD 2024, pipeline tiền xử lý từ CSV sang parquet binary IDS, cùng bộ split đã freeze và manifest để bảo đảm benchmark công bằng.", COLORS.orange, COLORS.orangeSoft);
  addSectionCard(slide, 3.95, 1.6, 3.0, 2.1, "Lớp thực nghiệm ML", "Benchmark 5 model trên Kaggle, tuning cho 3 model mạnh, scaling 2M/4M/8M + full-data, rồi threshold analysis và chọn model cuối cùng.", COLORS.blue, COLORS.blueSoft);
  addSectionCard(slide, 7.2, 1.6, 2.7, 2.1, "Lớp runtime IDS", "Bao gồm model bundle, batch inference, realtime pipeline micro-batch, structured record adapter và live host-based sensor.", COLORS.teal, COLORS.tealSoft);
  addSectionCard(slide, 10.15, 1.6, 2.45, 2.1, "Lớp vận hành", "Operator console FastAPI + SQLite, notification worker riêng, deploy bằng systemd + Nginx và runbook same-host cho toàn stack.", COLORS.green, COLORS.greenSoft);
  addNumberCard(slide, 0.82, 4.15, 1.8, 0.98, "Tài liệu", `${validationStats.docs}`, COLORS.ink, COLORS.sand, "docs/*.md");
  addNumberCard(slide, 2.82, 4.15, 1.8, 0.98, "Scripts", `${validationStats.scripts}`, COLORS.blue, COLORS.blueSoft, "scripts/**/*.py");
  addNumberCard(slide, 4.82, 4.15, 1.8, 0.98, "Test module", `${validationStats.tests}`, COLORS.teal, COLORS.tealSoft, "tests/test_*.py");
  addNumberCard(slide, 6.82, 4.15, 2.0, 0.98, "Deploy artifact", `${validationStats.deployArtifacts}`, COLORS.orange, COLORS.orangeSoft, "systemd + nginx");
  addBulletBlock(slide, 0.86, 5.42, 11.2, 1.15, "Khối lượng repo cho thấy đề tài đã đi qua đầy đủ các giai đoạn: xử lý dữ liệu, thực nghiệm, đóng gói model, runtime realtime, live sensor và công cụ quan sát vận hành.\nVì vậy trong bài thuyết trình nên nhấn mạnh đây là một hệ thống IDS hoàn chỉnh dựa trên ML, chứ không phải một bài benchmark đơn lẻ.", 11.3, COLORS.inkSoft);
  addFooter(slide, "Cách kể chuyện hiệu quả nhất là nhóm project thành 4 lớp: dữ liệu, thực nghiệm, runtime và vận hành.");
  finalizeSlide(slide, pptx);

  slide = pptx.addSlide("IDS_MASTER");
  addHeader(slide, 4, "Dữ liệu và tiền xử lý", "03  DATASET");
  addSectionCard(slide, 0.72, 1.64, 4.8, 1.55, "Dataset chọn cho đề tài", 'CIC IoT-DIAD 2024, nhánh "Anomaly Detection - Flow Based features". Đây là bộ dữ liệu mới, đúng ngữ cảnh IDS và phù hợp trực tiếp với pipeline traffic -> flow features -> model -> alert.', COLORS.orange, COLORS.orangeSoft);
  addSectionCard(slide, 0.86, 3.35, 5.75, 0.72, "Phân bố split đã freeze", "Toàn bộ benchmark, tuning, scaling và đánh giá OOD đều dùng cùng một protocol dữ liệu đã khóa.", COLORS.blue, COLORS.blueSoft);
  addNumberCard(slide, 1.05, 4.18, 1.95, 0.95, "Train", "18.68M", COLORS.ink, COLORS.sand, "Tập học chính");
  addNumberCard(slide, 3.15, 4.18, 1.95, 0.95, "Validation", "4.41M", COLORS.blue, COLORS.blueSoft, "Chọn threshold / tuning");
  addNumberCard(slide, 1.05, 5.28, 1.95, 0.95, "Test", "4.15M", COLORS.teal, COLORS.tealSoft, "Đánh giá cuối");
  addNumberCard(slide, 3.15, 5.28, 1.95, 0.95, "OOD Holdout", "0.44M", COLORS.orange, COLORS.orangeSoft, "Attack khác phân bố");
  addNumberCard(slide, 7.2, 1.66, 1.7, 0.95, "Nguồn file", `${datasetStats.sourceFiles}`, COLORS.ink, COLORS.sand, "CSV gốc");
  addNumberCard(slide, 9.0, 1.66, 1.7, 0.95, "Dung lượng", `${datasetStats.sizeGb} GB`, COLORS.teal, COLORS.tealSoft, "Nhánh đã tải");
  addNumberCard(slide, 10.8, 1.66, 1.7, 0.95, "Feature", `${datasetStats.features}`, COLORS.orange, COLORS.orangeSoft, "Schema canonical");
  addBulletBlock(slide, 7.15, 2.9, 5.0, 2.6, "Gán lại nhãn từ cấu trúc thư mục thành bài toán Benign/Attack để phục vụ IDS nhị phân.\nLoại bỏ leakage columns như Flow ID, Src IP, Dst IP, Timestamp và Label.\nÉp toàn bộ feature về numeric, loại NaN/inf, exact duplicates và đưa file lỗi vào quarantine.\nĐóng băng bộ split train/val/test/OOD holdout để mọi thực nghiệm về sau dùng chung một chuẩn đánh giá.", 11.0, COLORS.inkSoft);
  addFooter(slide, "Tập train cuối cùng có 18.679.445 dòng, cung cấp một nền dữ liệu rất dày cho scaling experiment và full-data training.");
  finalizeSlide(slide, pptx);

  slide = pptx.addSlide("IDS_MASTER");
  addHeader(slide, 5, "Protocol thực nghiệm và cách chọn model", "04  EXPERIMENT DESIGN");
  addProcessArrow(slide, 0.9, 2.05, 1.95, 0.82, "Benchmark 5 mô hình", COLORS.ink);
  addProcessArrow(slide, 3.0, 2.05, 1.95, 0.82, "Tuning + promotion", COLORS.blue);
  addProcessArrow(slide, 5.1, 2.05, 2.1, 0.82, "Scaling 2M / 4M / 8M", COLORS.orange);
  addProcessArrow(slide, 7.35, 2.05, 1.95, 0.82, "CatBoost full-data", COLORS.green);
  addProcessArrow(slide, 9.45, 2.05, 2.2, 0.82, "Threshold + chốt model", COLORS.teal);
  addSectionCard(slide, 0.88, 3.35, 3.7, 2.55, "Nguyên tắc đánh giá", "Tất cả model dùng chung bộ split đã freeze. Test không được phép dùng để chọn hyperparameter, còn OOD holdout được giữ riêng để đo khả năng tổng quát hóa trước các attack khác phân bố.", COLORS.orange, COLORS.orangeSoft);
  addSectionCard(slide, 4.78, 3.35, 3.95, 2.55, "Selection rule", "Hard gate cho tuning là val_fpr_at_default_0.5 <= 0.02. Sau đó xếp hạng theo F1 ở operating point đã tune, rồi tie-break bằng FPR, OOD recall và train time.", COLORS.blue, COLORS.blueSoft);
  addSectionCard(slide, 8.93, 3.35, 3.55, 2.55, "Thông điệp quan trọng", "Scaling công bằng giúp tránh kết luận vội từ promotion run. Chỉ sau khi có 2M/4M/8M và full-data mới có đủ cơ sở chắc để chốt model cuối cùng.", COLORS.green, COLORS.greenSoft);
  addFooter(slide, "Protocol của repo khá chặt: benchmark -> tuning -> scaling -> threshold -> final decision, nhờ đó lập luận học thuật khi bảo vệ sẽ vững hơn.");
  finalizeSlide(slide, pptx);

  slide = pptx.addSlide("IDS_MASTER");
  addHeader(slide, 6, "Kết quả benchmark vòng đầu", "05  INITIAL MODEL SCREENING");
  slide.addImage({ path: fig("kaggle_metric_overview.png"), ...imageSizingContain(fig("kaggle_metric_overview.png"), 0.7, 1.55, 6.55, 4.7) });
  addSectionCard(slide, 7.55, 1.62, 4.7, 1.2, "Nhận xét tổng quát", "Cả 5 mô hình đều cho F1 cao, nhưng IDS không thể chỉ nhìn F1. FPR mới là metric quyết định khả năng vận hành thực tế và mức độ nhiễu cảnh báo.", COLORS.orange, COLORS.orangeSoft);
  addBulletBlock(slide, 7.72, 3.0, 4.4, 2.45, `CatBoost có FPR thấp nhất trong nhóm hợp lệ: ${fmtPct(benchmarkModels[0].fpr, 2)}.\nRandom Forest có Test F1 cao nhất nhưng FPR vẫn nhỉnh hơn CatBoost.\nHistGB bám rất sát hai đối thủ trên và đóng vai trò baseline CPU-only đáng tin cậy.\nLogReg và MLP bị loại khỏi hướng deploy vì FPR quá cao (${fmtPct(benchmarkModels[3].fpr, 2)} và ${fmtPct(benchmarkModels[4].fpr, 2)}), dù một số metric khác nhìn có vẻ hấp dẫn.`, 11.0, COLORS.inkSoft);
  addSectionCard(slide, 7.55, 5.58, 4.7, 0.72, "Kết luận vòng 1", "Ba ứng viên đi tiếp là CatBoost, Random Forest và HistGradientBoosting.", COLORS.green, COLORS.greenSoft);
  addFooter(slide, "Vòng benchmark có vai trò sàng lọc: loại mô hình gây báo động giả lớn và giữ lại nhóm mô hình cây để đào sâu.");
  finalizeSlide(slide, pptx);

  slide = pptx.addSlide("IDS_MASTER");
  addHeader(slide, 7, "Scaling experiment và quyết định chốt model", "06  FINAL MODEL SELECTION");
  addSectionCard(slide, 0.82, 1.72, 5.75, 1.35, "CatBoost full-data", "Test F1 = 0.993358, Test FPR = 2.74%, OOD Recall = 49.96%. Khi tăng dữ liệu lên full train, CatBoost vẫn giữ được sự cân bằng giữa hiệu năng phát hiện, chi phí huấn luyện và khả năng vận hành.", COLORS.teal, COLORS.tealSoft);
  addSectionCard(slide, 0.82, 3.35, 5.75, 1.35, "RandomForest 8M", "Đạt F1 và OOD recall cao nhất trong scaling, nhưng FPR tăng lên 4.03%. Điều đó đồng nghĩa hệ thống sẽ nhiễu hơn đáng kể nếu đưa trực tiếp vào vận hành thật.", COLORS.orange, COLORS.orangeSoft);
  addSectionCard(slide, 0.82, 4.98, 5.75, 1.35, "HistGB 8M", "Bảo thủ hơn về FPR so với RandomForest, nhưng không dẫn đầu về F1/OOD và train chậm hơn. Đây là baseline CPU-only mạnh nhưng chưa phải lựa chọn cân bằng nhất.", COLORS.blue, COLORS.blueSoft);
  slide.addImage({ path: fig("model_selection_tradeoff.png"), ...imageSizingContain(fig("model_selection_tradeoff.png"), 7.1, 1.72, 5.1, 3.55) });
  addSectionCard(slide, 7.1, 5.48, 5.15, 0.85, "Kết luận chốt", "CatBoost full-data là điểm cân bằng dễ bảo vệ nhất cho IDS thực tế.", COLORS.green, COLORS.greenSoft);
  addFooter(slide, "Scaling experiment là bằng chứng mạnh nhất cho lập luận chọn mô hình: cân bằng quan trọng hơn cực trị trên một metric.");
  finalizeSlide(slide, pptx);

  slide = pptx.addSlide("IDS_MASTER");
  addHeader(slide, 8, "Operating point cuối cùng và metric của model chốt", "07  THRESHOLD DECISION");
  slide.addImage({ path: fig("catboost_full_threshold_sweep.png"), ...imageSizingContain(fig("catboost_full_threshold_sweep.png"), 0.7, 1.5, 6.4, 4.75) });
  addNumberCard(slide, 7.45, 1.72, 2.0, 1.0, "Threshold chốt", `${finalModel.threshold}`, COLORS.teal, COLORS.tealSoft, "Conservative, dễ giải thích");
  addNumberCard(slide, 9.65, 1.72, 2.0, 1.0, "Test F1", finalModel.testF1.toFixed(6), COLORS.blue, COLORS.blueSoft, "Mốc triển khai");
  addNumberCard(slide, 7.45, 2.95, 2.0, 1.0, "Test FPR", fmtPct(finalModel.testFpr, 2), COLORS.orange, COLORS.orangeSoft, "Mức báo động giả");
  addNumberCard(slide, 9.65, 2.95, 2.0, 1.0, "OOD Recall", fmtPct(finalModel.oodRecall, 2), COLORS.green, COLORS.greenSoft, "Tổng quát hóa attack mới");
  addSectionCard(slide, 7.35, 4.28, 4.45, 1.62, "So sánh với threshold 0.475", `Threshold tune ${finalModel.altThreshold} chỉ nhích F1 lên ${finalModel.altF1.toFixed(6)} và OOD recall lên ${fmtPct(finalModel.altOodRecall, 2)}, nhưng FPR cũng tăng lên ${fmtPct(finalModel.altFpr, 2)}. Vì vậy đề tài giữ threshold 0.5 để hệ thống ít nhiễu hơn và dễ tái lập hơn.`, COLORS.ink, COLORS.sand);
  addFooter(slide, "Thông điệp thuyết trình: threshold 0.5 được chọn để phục vụ deploy thực tế, không phải để tối ưu tuyệt đối trên từng metric.");
  finalizeSlide(slide, pptx);

  slide = pptx.addSlide("IDS_MASTER");
  addHeader(slide, 9, "Final model bundle và inference contract", "08  DEPLOYABLE MODEL PACKAGE");
  slide.addShape(ShapeType.roundRect, {
    x: 0.76, y: 1.78, w: 11.78, h: 1.58, rectRadius: 0.08,
    line: { color: COLORS.line, pt: 1.1 }, fill: { color: COLORS.white, transparency: 100 },
  });
  addFlowNode(slide, 0.9, 2.0, 1.72, 1.15, "model.cbm", "Artifact CatBoost đã chốt", COLORS.blueSoft);
  addFlowNode(slide, 2.8, 2.0, 1.92, 1.15, "feature_columns.json", "72 feature canonical", COLORS.tealSoft);
  addFlowNode(slide, 4.95, 2.0, 1.92, 1.15, "model_bundle.json", "Manifest versioned + threshold", COLORS.orangeSoft);
  addFlowNode(slide, 7.1, 2.0, 1.6, 1.15, "metrics.json", "Metric cuối cùng", COLORS.greenSoft);
  addFlowNode(slide, 8.95, 2.0, 1.85, 1.15, "training_summary.json", "Thông tin full-data train", COLORS.blueSoft);
  addFlowNode(slide, 11.05, 2.0, 1.4, 1.15, "MODEL_CARD.md", "Tóm tắt model", COLORS.tealSoft);
  addSectionCard(slide, 0.82, 3.8, 3.72, 1.8, "Khả năng verify", "Candidate bundle được kiểm tra contract tương thích trước khi mutate activation state, giúp tránh việc trỏ nhầm model hoặc schema trong runtime.", COLORS.blue, COLORS.blueSoft);
  addSectionCard(slide, 4.82, 3.8, 3.72, 1.8, "Promotion lifecycle", "Activation record chỉ trỏ tới một bundle đang live và lưu previous known-good để rollback bằng cơ chế atomic replace khi cần.", COLORS.teal, COLORS.tealSoft);
  addSectionCard(slide, 8.82, 3.8, 3.65, 1.8, "Contract fail-closed", "Runtime không được mix model, schema hay threshold ngoài bundle. Sai contract thì fail sớm thay vì chấm điểm sai mà không ai phát hiện.", COLORS.orange, COLORS.orangeSoft);
  addBulletBlock(slide, 0.95, 5.95, 11.1, 0.55, "Từ góc nhìn thuyết trình, đây là bằng chứng repo đã vượt qua giai đoạn notebook và bước sang giai đoạn model lifecycle có thể vận hành.", 10.8, COLORS.inkSoft);
  addFooter(slide, "Bundle final nằm tại artifacts/final_model/catboost_full_data_v1 và là entrypoint chính thức cho runtime.");
  finalizeSlide(slide, pptx);

  slide = pptx.addSlide("IDS_MASTER");
  addHeader(slide, 10, "Kiến trúc runtime IDS trước model", "09  REALTIME PIPELINE");
  addFlowNode(slide, 0.75, 2.1, 1.8, 1.18, "Adapter", "Chuẩn hóa profile record từ upstream", COLORS.blueSoft);
  addFlowNode(slide, 2.85, 2.1, 1.9, 1.18, "FlowFeatureContract", "Kiểm tra đủ 72 feature", COLORS.tealSoft);
  addFlowNode(slide, 5.05, 2.1, 2.0, 1.18, "RealtimePipelineRunner", "Micro-batch + flush interval", COLORS.orangeSoft);
  addFlowNode(slide, 7.38, 2.1, 1.8, 1.18, "IDSInferencer", "CatBoost bundle scoring", COLORS.greenSoft);
  addFlowNode(slide, 9.48, 1.55, 1.9, 1.0, "model_prediction", "attack_score / is_alert", COLORS.blueSoft);
  addFlowNode(slide, 9.48, 2.75, 1.9, 1.0, "schema_anomaly", "Quarantine record lỗi", COLORS.redSoft);
  addFlowNode(slide, 11.7, 2.1, 1.0, 1.18, "Sinks", "Alert / dashboard / forensic", COLORS.sand);
  addArrowConnector(slide, 2.55, 2.69, 2.85, 2.69);
  addArrowConnector(slide, 4.75, 2.69, 5.05, 2.69);
  addArrowConnector(slide, 7.05, 2.69, 7.38, 2.69);
  addArrowConnector(slide, 9.18, 2.69, 9.48, 2.05);
  addArrowConnector(slide, 9.18, 2.69, 9.48, 3.2);
  addArrowConnector(slide, 11.38, 2.05, 11.7, 2.69);
  addArrowConnector(slide, 11.38, 3.2, 11.7, 2.69);
  addSectionCard(slide, 0.9, 4.28, 3.7, 1.6, "Ranh giới quan trọng", "IDS v1 nhận structured flow records, không sniff packet thô và cũng không tự suy diễn feature bị thiếu. Nếu upstream sai schema thì runtime phải phát hiện ngay.", COLORS.orange, COLORS.orangeSoft);
  addSectionCard(slide, 4.82, 4.28, 3.58, 1.6, "Xử lý record lỗi", "Record sai schema không làm fail toàn batch; nó bị quarantine riêng và phát schema_anomaly để vừa giữ được khả năng chấm điểm, vừa giữ dấu vết forensic.", COLORS.red, COLORS.redSoft);
  addSectionCard(slide, 8.62, 4.28, 3.7, 1.6, "Lợi ích kiến trúc", "Kiến trúc này tái sử dụng được lõi scoring batch cũ, đồng thời đặt runtime boundary rõ ràng cho bài toán near-real-time IDS.", COLORS.green, COLORS.greenSoft);
  addFooter(slide, "Khi thuyết trình nên nhấn mạnh sự tách biệt giữa model alert và pipeline/schema anomaly.");
  finalizeSlide(slide, pptx);

  slide = pptx.addSlide("IDS_MASTER");
  addHeader(slide, 11, "Live host-based sensor", "10  IDS TRÊN HOST THẬT");
  addFlowNode(slide, 0.82, 2.2, 1.85, 1.18, "dumpcap", "Capture rolling windows trên 1 NIC", COLORS.blueSoft);
  addFlowNode(slide, 3.0, 2.2, 1.9, 1.18, "LiveFlowBridge", "Đóng cửa sổ capture thành flow records", COLORS.tealSoft);
  addFlowNode(slide, 5.2, 2.2, 1.95, 1.18, "Adapter + Runtime", "Validate, micro-batch, score", COLORS.orangeSoft);
  addFlowNode(slide, 7.47, 2.2, 1.75, 1.18, "LocalSink", "JSONL + journald + summary", COLORS.greenSoft);
  addFlowNode(slide, 9.55, 1.62, 2.0, 0.95, "Positive alerts", "Chỉ persist alert dương", COLORS.blueSoft);
  addFlowNode(slide, 9.55, 2.72, 2.0, 0.95, "Quarantine events", "Lỗi contract / runtime", COLORS.redSoft);
  addFlowNode(slide, 9.55, 3.82, 2.0, 0.95, "Summary telemetry", "Thống kê benign, queue, active bundle", COLORS.tealSoft);
  addArrowConnector(slide, 2.67, 2.79, 3.0, 2.79);
  addArrowConnector(slide, 4.9, 2.79, 5.2, 2.79);
  addArrowConnector(slide, 7.15, 2.79, 7.47, 2.79);
  addArrowConnector(slide, 9.22, 2.79, 9.55, 2.08);
  addArrowConnector(slide, 9.22, 2.79, 9.55, 3.18);
  addArrowConnector(slide, 9.22, 2.79, 9.55, 4.28);
  addSectionCard(slide, 0.95, 4.95, 3.7, 1.32, "Phạm vi V1", "Single host, single interface, chỉ TCP/UDP, local outputs và fail-fast khi gặp lỗi capture/runtime nghiêm trọng.", COLORS.orange, COLORS.orangeSoft);
  addSectionCard(slide, 4.85, 4.95, 3.55, 1.32, "Ý nghĩa hệ thống", "Đây là cầu nối quan trọng giữa model offline và một IDS có khả năng chạy liên tục trên Linux host thật.", COLORS.teal, COLORS.tealSoft);
  addSectionCard(slide, 8.6, 4.95, 3.6, 1.32, "Giá trị khi trình bày", "Bạn có thể nhấn mạnh repo đã tiến tới live sensing thay vì dừng ở replay hoặc batch scoring.", COLORS.green, COLORS.greenSoft);
  addFooter(slide, "Trong V1, hệ thống lưu alert và quarantine đầy đủ; benign được tổng hợp thành summary để giảm storage noise.");
  finalizeSlide(slide, pptx);

  slide = pptx.addSlide("IDS_MASTER");
  addHeader(slide, 12, "Operator console và same-host deployment", "11  OPERATIONS");
  addFlowNode(slide, 1.0, 2.05, 2.2, 1.2, "ids-live-sensor.service", "Daemon capture + scoring", COLORS.blueSoft);
  addFlowNode(slide, 3.6, 2.05, 2.25, 1.2, "SQLite + summaries", "Nguồn dữ liệu cho quan sát", COLORS.tealSoft);
  addFlowNode(slide, 6.22, 2.05, 2.4, 1.2, "Operator Console", "FastAPI + Jinja2 + auth admin", COLORS.orangeSoft);
  addFlowNode(slide, 9.0, 2.05, 2.35, 1.2, "Notify Worker", "Telegram runtime tách riêng", COLORS.greenSoft);
  addFlowNode(slide, 11.6, 2.05, 1.0, 1.2, "Nginx", "TLS / reverse proxy", COLORS.sand);
  addArrowConnector(slide, 3.2, 2.65, 3.6, 2.65);
  addArrowConnector(slide, 5.85, 2.65, 6.22, 2.65);
  addArrowConnector(slide, 8.65, 2.65, 9.0, 2.65);
  addArrowConnector(slide, 11.35, 2.65, 11.6, 2.65);
  addSectionCard(slide, 0.92, 3.95, 3.65, 1.76, "Web UI thực sự", "Console không phải placeholder: có dashboard, alert detail, anomalies, reports và API /api/v1/* để xem snapshot vận hành, trạng thái sensor và active bundle.", COLORS.blue, COLORS.blueSoft);
  addSectionCard(slide, 4.82, 3.95, 3.7, 1.76, "Readiness và backup", "Có /healthz, /readyz, backup/restore SQLite, preflight gate, worker status và phân tách rõ các failure domain trong quá trình vận hành.", COLORS.teal, COLORS.tealSoft);
  addSectionCard(slide, 8.75, 3.95, 3.55, 1.76, "Same-host stack", "Runbook thống nhất bootstrap, status, smoke, recover và post-restore-check cho toàn bộ stack model + sensor + console + notification.", COLORS.orange, COLORS.orangeSoft);
  addFooter(slide, "Giá trị của phần operations là chứng minh hệ thống không chỉ phát hiện, mà còn có thể được vận hành, khởi động và kiểm tra.");
  finalizeSlide(slide, pptx);

  slide = pptx.addSlide("IDS_MASTER");
  addHeader(slide, 13, "Bằng chứng validation và demo", "12  EVIDENCE");
  addNumberCard(slide, 0.9, 1.65, 2.2, 1.08, "Test module", `${validationStats.tests}`, COLORS.blue, COLORS.blueSoft, "Bao gồm inference, realtime, live sensor, console");
  addNumberCard(slide, 3.35, 1.65, 2.2, 1.08, "Dry-run bundle", "1000 rows", COLORS.teal, COLORS.tealSoft, "Score thành công từ bundle final");
  addNumberCard(slide, 5.8, 1.65, 2.2, 1.08, "Demo fixture", "5 JSONL", COLORS.orange, COLORS.orangeSoft, "Adapter / realtime / live sensor");
  addNumberCard(slide, 8.25, 1.65, 2.2, 1.08, "Deploy files", "systemd + nginx", COLORS.green, COLORS.greenSoft, "Dùng được trên host Linux");
  slide.addImage({ path: fig("catboost_full_pr_roc.png"), ...imageSizingContain(fig("catboost_full_pr_roc.png"), 0.85, 3.0, 5.8, 2.9) });
  addBulletBlock(slide, 7.1, 3.2, 5.0, 2.2, "Repo có artifacts demo để trình diễn đường JSONL -> alert/quarantine mà không cần chuẩn bị dataset nặng.\nCó dry-run inference từ bundle final và contract versioned để kiểm thử đường deploy.\nHệ thống vận hành có preflight, smoke, health/readiness và runbook recover rõ ràng, nên phần demo thuyết phục hơn nhiều so với một mô hình thuần offline.", 10.8, COLORS.inkSoft);
  addSectionCard(slide, 7.08, 5.45, 5.05, 0.82, "Thông điệp trình bày", "Bằng chứng validation giúp khẳng định đây là hệ thống IDS đã được harden, không chỉ là kết quả train model.", COLORS.ink, COLORS.sand);
  addFooter(slide, "PR-AUC và ROC-AUC của CatBoost full-data rất cao; phần hạn chế còn lại chủ yếu nằm ở OOD recall và phạm vi triển khai V1.");
  finalizeSlide(slide, pptx);

  slide = pptx.addSlide("IDS_MASTER");
  addHeader(slide, 14, "Hạn chế hiện tại và hướng phát triển", "13  LIMITATIONS & FUTURE WORK");
  addSectionCard(slide, 0.8, 1.7, 3.8, 2.2, "Hạn chế về mô hình", `OOD recall của model chốt mới ở mức ${fmtPct(finalModel.oodRecall, 2)}. Điều đó cho thấy vẫn còn khoảng trống nếu hệ thống phải đối mặt với các kiểu attack mới khác phân bố train.`, COLORS.orange, COLORS.orangeSoft);
  addSectionCard(slide, 4.82, 1.7, 3.8, 2.2, "Hạn chế về hệ thống", "V1 mới dừng ở same-host, single NIC, TCP/UDP-only và local outputs; chưa có SIEM bus, fleet rollout hay threshold thích nghi theo môi trường vận hành.", COLORS.blue, COLORS.blueSoft);
  addSectionCard(slide, 8.84, 1.7, 3.6, 2.2, "Hạn chế về dữ liệu", "Hệ thống vẫn dựa trên flow-based features và binary classification; chưa khai thác attack family classification hoặc online drift adaptation.", COLORS.teal, COLORS.tealSoft);
  addBulletBlock(slide, 0.96, 4.35, 11.3, 1.9, "Hướng 1: mở rộng sang SIEM / message bus / fleet deployment để đưa IDS vào vận hành thật trên nhiều host.\nHướng 2: đánh giá threshold theo traffic thật và bổ sung giám sát drift / recalibration định kỳ.\nHướng 3: nghiên cứu thêm OOD robustness, attack-family classification và adaptation cho môi trường IIoT đa dạng hơn.", 11.0, COLORS.inkSoft);
  addFooter(slide, "Nói phần hạn chế một cách trung thực sẽ làm bài bảo vệ thuyết phục hơn: repo đã rất dày, nhưng vẫn còn roadmap rõ ràng.");
  finalizeSlide(slide, pptx);

  slide = pptx.addSlide("IDS_MASTER");
  addHeader(slide, 15, "Kết luận", "14  CLOSING");
  addSectionCard(slide, 0.9, 1.8, 3.8, 1.55, "Kết quả học thuật", "Đã xây dựng protocol thực nghiệm đầy đủ trên CIC IoT-DIAD 2024 và chốt CatBoost full-data là mô hình cân bằng nhất cho IDS.", COLORS.blue, COLORS.blueSoft);
  addSectionCard(slide, 4.95, 1.8, 3.8, 1.55, "Kết quả kỹ thuật", "Đã đóng gói model bundle versioned, hoàn thiện batch inference, realtime pipeline, structured adapter và live sensor host-based.", COLORS.teal, COLORS.tealSoft);
  addSectionCard(slide, 9.0, 1.8, 3.35, 1.55, "Kết quả vận hành", "Đã có operator console, health/readiness, backup/restore, notification worker và same-host runbook.", COLORS.orange, COLORS.orangeSoft);
  slide.addShape(ShapeType.rect, {
    x: 0.92, y: 4.08, w: 6.2, h: 1.8, fill: { color: COLORS.charcoal }, line: { color: COLORS.charcoal },
  });
  slide.addShape(ShapeType.rect, {
    x: 1.12, y: 4.32, w: 0.08, h: 1.28, fill: { color: COLORS.orange }, line: { color: COLORS.orange },
  });
  slide.addText("Thông điệp chốt", {
    x: 1.38, y: 4.3, w: 2.8, h: 0.26, fontFace: "Bahnschrift", fontSize: 17, bold: true, color: COLORS.white,
  });
  slide.addText("Giá trị lớn nhất của project không nằm ở một mô hình điểm số cao đơn lẻ, mà nằm ở việc nối được machine learning với runtime, cảm biến sống và lớp vận hành để hình thành một IDS có khả năng triển khai thực tế.", {
    x: 1.38, y: 4.72, w: 5.25, h: 0.9, fontFace: "Aptos", fontSize: 11.6, color: "D8E4EE",
  });
  slide.addShape(ShapeType.rect, {
    x: 7.5, y: 4.08, w: 4.55, h: 1.8, fill: { color: COLORS.orange }, line: { color: COLORS.orange },
  });
  slide.addText("Q & A", {
    x: 7.72, y: 4.72, w: 4.0, h: 0.42, align: "center", fontFace: "Bahnschrift",
    fontSize: 30, bold: true, color: COLORS.white,
  });
  addFooter(slide, `Outline tham khảo chi tiết cho người thuyết trình được lưu tại ${path.basename(OUTLINE_PATH)}.`);
  finalizeSlide(slide, pptx);

  await pptx.writeFile({ fileName: OUT_PPTX });
  console.log(`Wrote deck to ${OUT_PPTX}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
