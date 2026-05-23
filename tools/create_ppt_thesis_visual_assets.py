from __future__ import annotations

import csv
import json
import os
import re
import shutil
import stat
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
ASSET_DIR = OUT / "ppt_thesis_visual_assets"
FIG_DIR = ASSET_DIR / "figures"
ZIP_PATH = OUT / "ppt_thesis_visual_assets.zip"

WIDE = (1920, 1080)
BG = "#F7FAFC"
INK = "#102033"
MUTED = "#5F6B7A"
GREEN = "#146B55"
GREEN_2 = "#E6F4EF"
BLUE = "#2E77AE"
BLUE_2 = "#EAF3FA"
ORANGE = "#D97918"
RED = "#C0392B"
LINE = "#D6E0EA"
WHITE = "#FFFFFF"


def reset_dir(path: Path) -> None:
    if path.exists():
        for child in sorted(path.rglob("*"), reverse=True):
            try:
                os.chmod(child, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
            except OSError:
                pass
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8-sig")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\malgunbd.ttf" if bold else r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\NotoSansKR-Bold.otf" if bold else r"C:\Windows\Fonts\NotoSansKR-Regular.otf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


F_TITLE = font(50, True)
F_SUBTITLE = font(28, False)
F_H = font(30, True)
F_BODY = font(25, False)
F_SMALL = font(21, False)
F_TINY = font(18, False)


def load_json(name: str) -> dict:
    path = OUT / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_csv(name: str) -> list[dict[str, str]]:
    path = OUT / name
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def text_width(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=fnt)
    return bbox[2] - bbox[0]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = word if not line else f"{line} {word}"
        if text_width(draw, candidate, fnt) <= max_width:
            line = candidate
            continue
        if line:
            lines.append(line)
            line = word
        else:
            # Long Korean/English token fallback: split by character.
            current = ""
            for ch in word:
                cand = current + ch
                if text_width(draw, cand, fnt) <= max_width:
                    current = cand
                else:
                    if current:
                        lines.append(current)
                    current = ch
            line = current
    if line:
        lines.append(line)
    return lines


def draw_header(draw: ImageDraw.ImageDraw, title: str, subtitle: str | None = None) -> None:
    draw.text((90, 58), title, fill=GREEN, font=F_TITLE)
    draw.rounded_rectangle((90, 128, 1830, 134), radius=3, fill=GREEN)
    if subtitle:
        draw.text((90, 155), subtitle, fill=MUTED, font=F_SUBTITLE)


def save_table(filename: str, title: str, subtitle: str, headers: list[str], rows: list[list[str]], widths: list[int]) -> None:
    width, height = WIDE
    img = Image.new("RGB", WIDE, BG)
    draw = ImageDraw.Draw(img)
    draw_header(draw, title, subtitle)

    x0, y0 = 90, 245
    table_w = sum(widths)
    row_h = 82
    header_h = 76
    draw.rounded_rectangle((x0, y0, x0 + table_w, y0 + header_h + row_h * len(rows)), radius=18, fill=WHITE, outline=LINE, width=2)
    draw.rounded_rectangle((x0, y0, x0 + table_w, y0 + header_h), radius=18, fill=GREEN)
    # Square off header bottom so the outer rounded shape remains clean.
    draw.rectangle((x0, y0 + header_h - 18, x0 + table_w, y0 + header_h), fill=GREEN)

    cx = x0
    for i, h in enumerate(headers):
        draw.text((cx + 18, y0 + 22), h, fill=WHITE, font=F_SMALL)
        cx += widths[i]
        if i < len(headers) - 1:
            draw.line((cx, y0, cx, y0 + header_h + row_h * len(rows)), fill=LINE, width=2)

    for r, row in enumerate(rows):
        y = y0 + header_h + r * row_h
        fill = GREEN_2 if r % 2 == 0 else WHITE
        draw.rectangle((x0, y, x0 + table_w, y + row_h), fill=fill)
        draw.line((x0, y, x0 + table_w, y), fill=LINE, width=2)
        cx = x0
        for c, cell in enumerate(row):
            fnt = F_SMALL if c == 0 else F_BODY
            color = INK
            lines = wrap_text(draw, str(cell), fnt, widths[c] - 32)[:2]
            ty = y + 17 if len(lines) == 1 else y + 9
            for line in lines:
                draw.text((cx + 18, ty), line, fill=color, font=fnt)
                ty += 30
            cx += widths[c]

    draw.text((90, 1018), "MaintiQ Predict | PPT/논문 삽입용 시각자료", fill=MUTED, font=F_TINY)
    img.save(FIG_DIR / filename, quality=95)


def save_flow(filename: str, title: str, subtitle: str, steps: list[tuple[str, str]], colors: list[str] | None = None) -> None:
    img = Image.new("RGB", WIDE, BG)
    draw = ImageDraw.Draw(img)
    draw_header(draw, title, subtitle)
    colors = colors or [GREEN, BLUE, ORANGE, GREEN, BLUE]
    n = len(steps)
    margin_x = 100
    gap = 38
    box_w = int((WIDE[0] - 2 * margin_x - gap * (n - 1)) / n)
    box_h = 275
    y = 390

    for i, (head, body) in enumerate(steps):
        x = margin_x + i * (box_w + gap)
        col = colors[i % len(colors)]
        draw.rounded_rectangle((x, y, x + box_w, y + box_h), radius=24, fill=WHITE, outline=LINE, width=2)
        draw.rounded_rectangle((x, y, x + box_w, y + 72), radius=24, fill=col)
        draw.rectangle((x, y + 48, x + box_w, y + 72), fill=col)
        draw.text((x + 24, y + 20), f"{i + 1}. {head}", fill=WHITE, font=F_SMALL)
        lines = wrap_text(draw, body, F_BODY, box_w - 46)
        ty = y + 105
        for line in lines[:4]:
            draw.text((x + 24, ty), line, fill=INK, font=F_BODY)
            ty += 38
        if i < n - 1:
            ax = x + box_w + 10
            ay = y + box_h // 2
            draw.line((ax, ay, ax + gap - 20, ay), fill=GREEN, width=5)
            draw.polygon([(ax + gap - 20, ay - 12), (ax + gap - 20, ay + 12), (ax + gap - 2, ay)], fill=GREEN)

    draw.text((90, 1018), "MaintiQ Predict | PPT/논문 삽입용 시각자료", fill=MUTED, font=F_TINY)
    img.save(FIG_DIR / filename, quality=95)


def save_architecture() -> None:
    img = Image.new("RGB", WIDE, BG)
    draw = ImageDraw.Draw(img)
    draw_header(draw, "전체 시스템 아키텍처", "CSV 입력부터 예측, SPC, GenAI 리포트, 작업지시까지 이어지는 운영 흐름")

    boxes = [
        (130, 280, 460, 470, "센서 CSV 입력", "AI4I형 / 회사형 CSV\n컬럼 매핑·단위 확인"),
        (560, 280, 890, 470, "전처리·예측", "XGBoost / Threshold\n고장 확률·High Risk"),
        (990, 280, 1320, 470, "Predictive SPC", "위험 확률 시계열\n관리한계·추세 확인"),
        (1420, 280, 1750, 470, "GenAI 리포트", "관리자 참고 요약\n위험요인·조치 방향"),
        (560, 635, 890, 825, "작업지시 초안", "센서 이벤트 기반\n승인 전 초안 생성"),
        (990, 635, 1320, 825, "작업자 결정", "승인 / 검토 / 반려\n이력 저장"),
    ]
    for x1, y1, x2, y2, head, body in boxes:
        draw.rounded_rectangle((x1, y1, x2, y2), radius=24, fill=WHITE, outline=LINE, width=2)
        draw.text((x1 + 28, y1 + 28), head, fill=GREEN, font=F_H)
        ty = y1 + 88
        for line in body.split("\n"):
            draw.text((x1 + 28, ty), line, fill=INK, font=F_BODY)
            ty += 36

    arrows = [
        ((460, 375), (560, 375)),
        ((890, 375), (990, 375)),
        ((1320, 375), (1420, 375)),
        ((725, 470), (725, 635)),
        ((890, 730), (990, 730)),
    ]
    for (x1, y1), (x2, y2) in arrows:
        draw.line((x1, y1, x2, y2), fill=GREEN, width=5)
        if x2 > x1:
            draw.polygon([(x2 - 16, y2 - 12), (x2 - 16, y2 + 12), (x2, y2)], fill=GREEN)
        else:
            draw.polygon([(x2 - 12, y2 - 16), (x2 + 12, y2 - 16), (x2, y2)], fill=GREEN)

    draw.rounded_rectangle((1420, 635, 1750, 825), radius=24, fill="#FFF4E8", outline="#F0C28F", width=2)
    draw.text((1448, 663), "Claim Boundary", fill=ORANGE, font=F_H)
    draw.text((1448, 725), "자동 정비 명령 아님\n현장 실증은 별도 필요", fill=INK, font=F_BODY)
    draw.text((90, 1018), "그림: MaintiQ Predict 전체 시스템 구조", fill=MUTED, font=F_TINY)
    img.save(FIG_DIR / "01_system_architecture.png", quality=95)


def save_paper_structure() -> None:
    rows = [
        ["구분", "분량", "핵심 내용"],
        ["서론", "3쪽", "문제 배경, 연구 목적, 주장 경계"],
        ["이론/선행연구", "5쪽", "예지보전, SPC, ML, SHAP, 비용민감 학습"],
        ["연구 방법", "5쪽", "전처리, 모델, threshold, SPC 비교, benchmark"],
        ["시스템 구현", "5쪽", "데스크톱 앱, GenAI 리포트, 작업지시"],
        ["실험 및 검증", "8쪽", "AI4I, SMOTE, SPC, cost simulation, SCANIA"],
        ["결론", "2쪽", "성과, 한계, 향후 실제 회사 데이터 실증"],
    ]
    save_table(
        "12_paper_structure_29p.png",
        "논문 29쪽 내외 구성",
        "장별 분량과 필수 작성 내용을 한 장으로 정리",
        rows[0],
        rows[1:],
        [300, 220, 1120],
    )


def copy_existing_assets() -> None:
    copies = [
        ("maintiq_predict_screenshot.png", "20_app_main_screen.png"),
        ("maintiq_predict_lite_screenshot.png", "21_app_lite_screen.png"),
        ("pr_curve.png", "22_pr_curve.png"),
        ("threshold_tuning.png", "23_threshold_tuning.png"),
        ("spc_risk_chart.png", "24_spc_risk_chart.png"),
        ("spc_control_chart.png", "25_spc_control_chart.png"),
        ("shap_summary.png", "26_shap_summary.png"),
        ("shap_bar.png", "27_shap_bar.png"),
        ("operational_value_simulation.png", "28_operational_value_simulation.png"),
        ("scania_official_cost_comparison.png", "29_scania_cost_comparison.png"),
        ("scania_official_confusion_matrix.png", "30_scania_confusion_matrix.png"),
        ("public_industrial_cost_chart.png", "31_public_benchmark_cost_chart.png"),
        ("public_industrial_lead_time_chart.png", "32_public_benchmark_lead_time.png"),
        ("model_strategy_pr_curve.png", "33_model_strategy_pr_curve.png"),
    ]
    for src, dst in copies:
        src_path = OUT / src
        if src_path.exists():
            shutil.copy2(src_path, FIG_DIR / dst)


def create_contact_sheet() -> None:
    paths = sorted(FIG_DIR.glob("*.png"))
    thumbs: list[tuple[Path, Image.Image]] = []
    for path in paths:
        img = Image.open(path).convert("RGB")
        img.thumbnail((360, 210))
        thumbs.append((path, img.copy()))
        img.close()

    cols = 4
    cell_w, cell_h = 430, 280
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h + 80), BG)
    draw = ImageDraw.Draw(sheet)
    draw.text((30, 24), "PPT/논문 시각자료 Contact Sheet", fill=GREEN, font=F_H)
    for i, (path, thumb) in enumerate(thumbs):
        col = i % cols
        row = i // cols
        x = col * cell_w + 28
        y = row * cell_h + 80
        draw.rounded_rectangle((x - 8, y - 8, x + 380, y + 236), radius=12, fill=WHITE, outline=LINE)
        sheet.paste(thumb, (x, y))
        label = path.name
        draw.text((x, y + 216), label[:42], fill=INK, font=F_TINY)
    sheet.save(ASSET_DIR / "contact_sheet.png", quality=95)


def validate_and_zip() -> None:
    patterns = [r"AIza[0-9A-Za-z_\-]{20,}", r"sk-[0-9A-Za-z_\-]{20,}"]
    for path in ASSET_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in {".txt", ".md", ".csv"}:
            text = path.read_text(encoding="utf-8-sig")
            if "\ufffd" in text:
                raise RuntimeError(f"Replacement character found: {path}")
            for pattern in patterns:
                if re.search(pattern, text):
                    raise RuntimeError(f"API key-like pattern found: {path}")

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(ASSET_DIR.rglob("*")):
            if path.is_file():
                zf.write(path, arcname=str(path.relative_to(ASSET_DIR)))


def main() -> None:
    reset_dir(ASSET_DIR)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    metrics = load_json("metrics.json")
    threshold = load_json("threshold_summary.json")
    scania = load_json("scania_official_cost_metrics.json")

    xgb = metrics.get("models", {}).get("xgboost", {})
    logreg = metrics.get("models", {}).get("logistic_regression", {})
    selected = threshold.get("selected_metrics", {})
    scania_metrics = scania.get("metrics", [])
    scania_best = next((m for m in scania_metrics if m.get("strategy_id") == "xgboost_cost_optimized"), {})
    scania_rule = next((m for m in scania_metrics if m.get("strategy_id") == "rule_based_threshold"), {})

    save_architecture()
    save_flow(
        "02_data_preprocessing_pipeline.png",
        "데이터 입력 및 전처리 흐름",
        "AI4I/회사형 CSV를 예측 가능한 feature matrix로 변환",
        [
            ("CSV 입력", "센서 row와 설비 정보를 파일로 입력"),
            ("컬럼 정리", "UDI, Product ID 제거\nleakage 컬럼 제거"),
            ("인코딩", "Type one-hot encoding\n수치형 feature 구성"),
            ("예측", "XGBoost 고장 확률\nthreshold 0.87 적용"),
            ("결과", "High Risk 판정\n우선순위·CSV 저장"),
        ],
    )
    save_flow(
        "03_work_order_workflow.png",
        "승인형 작업지시 Workflow",
        "자동 정비 명령이 아니라 작업자 승인 기반 의사결정 구조",
        [
            ("센서 이벤트", "고위험 row 또는 직접 입력 기반 이벤트 생성"),
            ("초안 생성", "위험요인과 추천 조치를 작업지시 초안으로 정리"),
            ("작업자 판단", "승인 / 검토 필요 / 반려 중 선택"),
            ("이력 저장", "event, draft, decision을 로컬 이력으로 보관"),
            ("재검토", "needs_review 항목은 재학습 후보로 표시"),
        ],
        colors=[GREEN, BLUE, ORANGE, GREEN, BLUE],
    )

    save_table(
        "04_maintenance_strategy_comparison_table.png",
        "보전 전략 비교",
        "사후보전, 예방보전, 예지보전의 운영상 차이",
        ["전략", "판단 기준", "장점", "한계"],
        [
            ["사후보전", "고장 발생 후 대응", "초기 구축 부담 낮음", "downtime과 긴급 정비 위험"],
            ["예방보전", "정해진 주기 기반 정비", "운영 계획 수립 쉬움", "과잉 정비 또는 미탐 위험"],
            ["예지보전", "센서 데이터 기반 위험 예측", "고장 전 조치 가능성", "데이터 품질과 검증 필요"],
        ],
        [250, 420, 430, 540],
    )
    save_table(
        "05_ai4i_baseline_table.png",
        "AI4I Baseline 성능",
        "XGBoost가 PR-AUC 기준 기준모델보다 높은 탐지 성능을 보임",
        ["모델", "Precision", "Recall", "F1", "ROC-AUC", "PR-AUC"],
        [
            ["Logistic Regression", logreg.get("precision"), logreg.get("recall"), logreg.get("f1_score"), logreg.get("roc_auc"), logreg.get("pr_auc")],
            ["XGBoost", xgb.get("precision"), xgb.get("recall"), xgb.get("f1_score"), xgb.get("roc_auc"), xgb.get("pr_auc")],
        ],
        [430, 230, 230, 210, 260, 260],
    )
    save_table(
        "06_threshold_tuning_table.png",
        "Threshold Tuning 결과",
        "F1 기준으로 threshold 0.87 선택",
        ["기준", "Precision", "Recall", "F1-score", "해석"],
        [
            ["Default 0.5", "0.4444", "0.8824", "0.5911", "recall은 높지만 false alarm 증가 가능"],
            ["Selected 0.87", selected.get("precision"), selected.get("recall"), selected.get("f1_score"), "precision-recall 균형 개선"],
        ],
        [320, 230, 230, 250, 610],
    )
    save_table(
        "07_spc_vs_ml_table.png",
        "SPC-only vs ML+SPC 비교",
        "탐지 정책별 alert, false alarm, missed failure trade-off",
        ["전략", "Precision", "Recall", "F1", "Alerts", "FP", "FN"],
        [
            ["SPC-only", "0.8571", "0.0882", "0.1600", "7", "1", "62"],
            ["ML threshold", "0.8197", "0.7353", "0.7752", "61", "11", "18"],
            ["ML+SPC", "0.6250", "0.8088", "0.7051", "88", "33", "13"],
        ],
        [430, 220, 220, 180, 180, 180, 180],
    )
    save_table(
        "08_genai_report_evidence_table.png",
        "Gemini AI 리포트 검증",
        "위험 context를 관리자 참고 리포트로 변환",
        ["항목", "값", "논문/PPT 해석"],
        [
            ["mode", "gemini_generate_content:gemini-2.5-flash", "실제 API 호출 기반 생성"],
            ["probability", "0.993616", "고위험 row 예측 확률"],
            ["threshold", "0.87", "위험 판정 기준"],
            ["status", "High Risk", "관리자 확인 필요"],
            ["factors", "torque, speed, air temp", "주요 위험 요인 요약"],
        ],
        [330, 560, 750],
    )
    save_table(
        "09_scania_cost_metric_table.png",
        "SCANIA Official Cost Metric",
        "공개 실제 산업 benchmark의 공식 cost matrix 기준 비교",
        ["전략", "Official cost", "Normalized cost", "Rule 대비 개선"],
        [
            ["Rule baseline", scania_rule.get("official_cost"), scania_rule.get("normalized_cost"), "0"],
            ["XGBoost cost-optimized", scania_best.get("official_cost"), scania_best.get("normalized_cost"), "17.02%"],
        ],
        [520, 360, 360, 400],
    )
    save_table(
        "10_claim_boundary_table.png",
        "가능한 주장 / 금지 주장",
        "논문과 발표에서 방어 가능한 표현만 사용",
        ["가능한 주장", "피해야 할 표현"],
        [
            ["공개 데이터 기반 모델·정책 비교", "회사 실제 라벨 데이터로 최종 성능 확인"],
            ["SCANIA official cost metric 개선", "회사 현장 원화 비용 절감 입증"],
            ["관리자 참고 GenAI 리포트", "정비 명령 자동 실행"],
            ["CSV 기반 제품형 MVP", "PLC/SCADA 운영망 배포 완료"],
        ],
        [820, 820],
    )
    save_table(
        "11_experiment_design_table.png",
        "실험 설계 요약",
        "데이터셋, 비교군, 지표를 분리해 검증",
        ["실험", "데이터", "비교군", "주요 지표"],
        [
            ["AI4I baseline", "AI4I 2020", "LR vs XGBoost", "PR-AUC, ROC-AUC, F1"],
            ["Threshold", "AI4I test", "0.5 vs 0.87", "Precision, Recall, F1"],
            ["SPC 비교", "AI4I playback", "SPC-only vs ML+SPC", "FP, FN, Alerts"],
            ["SCANIA", "Component X", "rule vs cost-optimized", "official cost metric"],
        ],
        [340, 360, 460, 480],
    )
    save_paper_structure()

    copy_existing_assets()
    create_contact_sheet()

    manifest_lines = [
        "# PPT/논문 시각자료 패키지",
        "",
        "이 폴더는 PPT와 논문에 바로 삽입할 수 있는 PNG 표/그림 자료를 모은 것이다.",
        "파일명은 PowerPoint/HWP 삽입 안정성을 위해 영문과 숫자로 구성했다.",
        "",
        "## 생성 표/다이어그램",
    ]
    for path in sorted(FIG_DIR.glob("*.png")):
        manifest_lines.append(f"- `figures/{path.name}`")
    write_text(ASSET_DIR / "README_visual_assets.md", "\n".join(manifest_lines))

    validate_and_zip()
    print(f"asset_dir={ASSET_DIR}")
    print(f"figure_count={len(list(FIG_DIR.glob('*.png')))}")
    print(f"zip_path={ZIP_PATH}")
    print(f"zip_size={ZIP_PATH.stat().st_size}")


if __name__ == "__main__":
    main()
