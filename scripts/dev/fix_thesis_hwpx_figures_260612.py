from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageOps
from sklearn.metrics import average_precision_score, precision_recall_curve

import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from data import load_data, preprocess_data  # noqa: E402
from thesis_methodology_validation import build_models, choose_threshold_by_validation_f1, split_60_20_20  # noqa: E402


OUTPUTS = ROOT / "outputs"
PACK = OUTPUTS / "thesis_alignment_260612_v2"
FIGURES = PACK / "figures"
TABLES = PACK / "tables"
DOCS = PACK / "docs"
VALIDATION = PACK / "validation"
ZIP_PATH = OUTPUTS / "thesis_alignment_260612_v2.zip"

DESKTOP = Path.home() / "Desktop"
SOURCE_HWPX = DESKTOP / "학부졸업논문_평가반영_최종본_0.86앱통일본.hwpx"
FINAL_HWPX = DESKTOP / "학부졸업논문_평가반영_최종본_0.86앱통일본_그림표수정본.hwpx"
DESKTOP_SCREENSHOT = OUTPUTS / "thesis_alignment_260612_v2_desktop_0_86_screenshot.png"


def set_korean_font() -> None:
    plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def reset_pack() -> None:
    if PACK.exists():
        shutil.rmtree(PACK)
    for path in [FIGURES, TABLES, DOCS, VALIDATION]:
        path.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()


def load_threshold_summary() -> dict:
    return json.loads((OUTPUTS / "threshold_summary.json").read_text(encoding="utf-8"))


def resize_image(source: Path, destination: Path, size: tuple[int, int], fit: bool = False) -> None:
    with Image.open(source) as image:
        image = image.convert("RGB")
        if fit:
            resized = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
        else:
            resized = ImageOps.contain(image, size, method=Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", size, "white")
            offset = ((size[0] - resized.width) // 2, (size[1] - resized.height) // 2)
            canvas.paste(resized, offset)
            resized = canvas
        destination.parent.mkdir(parents=True, exist_ok=True)
        resized.save(destination, format="PNG", optimize=True)


def render_method_flow(path: Path) -> None:
    set_korean_font()
    fig, ax = plt.subplots(figsize=(11.23, 6.32))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.set_title("60:20:20 검증-평가 분리 연구 절차", fontsize=18, weight="bold", pad=16)

    boxes = [
        (0.4, 3.7, "AI4I 2020\n원자료"),
        (2.0, 3.7, "전처리\nID/누수 컬럼 제거\nType one-hot"),
        (3.8, 3.7, "60:20:20 분할\nTrain / Validation\nFixed Test"),
        (5.7, 3.7, "Train\nXGBoost 학습"),
        (7.3, 3.7, "Validation\nRaw threshold 0.86\nIsotonic 선택"),
        (8.8, 3.7, "Fixed Test\nF1 0.7692\nPR-AUC 0.8118"),
        (3.0, 1.45, "운영 보조\nSPC 위험 흐름\nSHAP/GenAI\n작업자 승인"),
        (6.6, 1.45, "범위 제한\n공개 데이터 검증\n현장 실증은 향후 연구"),
    ]
    for x, y, text in boxes:
        width = 1.35 if x < 8.8 else 1.1
        height = 1.05
        ax.add_patch(
            plt.Rectangle(
                (x, y),
                width,
                height,
                facecolor="#edf4ff" if y > 3 else "#f6f8fb",
                edgecolor="#315d9f",
                linewidth=1.5,
                joinstyle="round",
            )
        )
        ax.text(x + width / 2, y + height / 2, text, ha="center", va="center", fontsize=10.5, linespacing=1.35)
    for x1, x2 in [(1.75, 2.0), (3.35, 3.8), (5.15, 5.7), (7.05, 7.3), (8.65, 8.8)]:
        ax.annotate("", xy=(x2, 4.22), xytext=(x1, 4.22), arrowprops=dict(arrowstyle="->", lw=1.5, color="#243b53"))
    ax.annotate("", xy=(4.4, 2.5), xytext=(4.4, 3.7), arrowprops=dict(arrowstyle="->", lw=1.3, color="#6b7280"))
    ax.annotate("", xy=(7.2, 2.5), xytext=(8.1, 3.7), arrowprops=dict(arrowstyle="->", lw=1.3, color="#6b7280"))
    ax.text(5.0, 0.45, "최종 앱 판정 기준: raw_probability >= 0.86", ha="center", fontsize=12, weight="bold", color="#b3261e")
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    resize_image(path, path, (1123, 632), fit=True)


def fixed_test_probabilities() -> tuple[pd.Series, dict[str, np.ndarray], float]:
    data = load_data(ROOT / "data" / "ai4i2020.csv")
    X, y = preprocess_data(data)
    split = split_60_20_20(X, y, seed=42)
    models = build_models(split.y_train, seed=42)
    probabilities: dict[str, np.ndarray] = {}
    for name, model in models.items():
        model.fit(split.X_train, split.y_train)
        probabilities[name] = model.predict_proba(split.X_test)[:, 1]
    valid_xgb = models["xgboost"].predict_proba(split.X_valid)[:, 1]
    selected_threshold, _ = choose_threshold_by_validation_f1(split.y_valid, valid_xgb)
    return split.y_test, probabilities, selected_threshold


def render_pr_curve(path: Path, title: str, size: tuple[int, int]) -> None:
    set_korean_font()
    y_test, probabilities, selected_threshold = fixed_test_probabilities()
    fig, ax = plt.subplots(figsize=(size[0] / 120, size[1] / 120))
    for name, proba, color in [
        ("Logistic Regression", probabilities["logistic_regression"], "#6b7280"),
        ("XGBoost", probabilities["xgboost"], "#1f77b4"),
    ]:
        precision, recall, _ = precision_recall_curve(y_test, proba)
        ap = average_precision_score(y_test, proba)
        ax.plot(recall, precision, label=f"{name} PR-AUC={ap:.4f}", linewidth=2.3, color=color)
    ax.axvline(0.7353, color="#b3261e", linestyle="--", linewidth=1.4, label=f"0.86 recall={0.7353:.4f}")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title(title)
    ax.grid(alpha=0.25)
    ax.legend(loc="lower left", fontsize=9, framealpha=0.92)
    ax.text(0.98, 0.94, f"Selected threshold = {selected_threshold:.2f}", transform=ax.transAxes, ha="right", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor="white")
    plt.close(fig)
    resize_image(path, path, size)


def render_final_confusion_matrix(path: Path) -> None:
    set_korean_font()
    matrix = np.array([[1920, 12], [18, 50]])
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(matrix, cmap="Blues")
    ax.set_title("Final Fixed-Test Confusion Matrix\nRaw threshold 0.86", fontsize=16, weight="bold")
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_xticks([0, 1], ["Normal", "High Risk"])
    ax.set_yticks([0, 1], ["Normal", "Failure"])
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(matrix[i, j]), ha="center", va="center", fontsize=22, weight="bold")
    ax.text(0.5, -0.20, "Precision 0.8065 / Recall 0.7353 / F1 0.7692", transform=ax.transAxes, ha="center", fontsize=12)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor="white")
    plt.close(fig)
    resize_image(path, path, (1000, 800), fit=True)


def render_bridge_comparison(path: Path) -> None:
    set_korean_font()
    labels = ["Initial 80:20\n0.87", "Final 60:20:20\n0.86"]
    precision = [0.8197, 0.8065]
    recall = [0.7353, 0.7353]
    f1 = [0.7752, 0.7692]
    pr_auc = [0.8014, 0.8118]
    x = np.arange(len(labels))
    width = 0.18
    fig, ax = plt.subplots(figsize=(10.56, 7.65))
    ax.bar(x - 1.5 * width, precision, width, label="Precision", color="#2563eb")
    ax.bar(x - 0.5 * width, recall, width, label="Recall", color="#16a34a")
    ax.bar(x + 0.5 * width, f1, width, label="F1", color="#f59e0b")
    ax.bar(x + 1.5 * width, pr_auc, width, label="PR-AUC", color="#7c3aed")
    ax.set_ylim(0.65, 0.86)
    ax.set_ylabel("Score")
    ax.set_title("Initial Presentation Result vs Final Thesis/App Validation Result", fontsize=15, weight="bold")
    ax.set_xticks(x, labels)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(ncol=4, loc="upper center")
    ax.text(
        0.5,
        -0.16,
        "0.87 is the initial exploratory result; 0.86 is the final app decision policy.",
        transform=ax.transAxes,
        ha="center",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(path, dpi=150, facecolor="white")
    plt.close(fig)
    resize_image(path, path, (1056, 765), fit=True)


def copy_and_resize_existing_figures() -> dict[str, Path]:
    generated = {
        "image2": FIGURES / "figure_3_1_method_flow_0_86.png",
        "image4": FIGURES / "figure_4_2_desktop_0_86.png",
        "image5": FIGURES / "figure_5_1_fixed_test_pr_curve.png",
        "image6": FIGURES / "figure_5_2_final_confusion_matrix_0_86.png",
        "image7": FIGURES / "figure_5_3_validation_threshold_curve_0_86.png",
        "image8": FIGURES / "figure_5_4_initial_vs_final_comparison.png",
        "image9": FIGURES / "figure_5_5_spc_risk_chart_0_86.png",
        "image11": FIGURES / "figure_5_7_calibration_after_validation_selection.png",
        "image13": FIGURES / "appendix_A1_local_validation_screen_0_86.png",
    }
    render_method_flow(generated["image2"])
    resize_image(DESKTOP_SCREENSHOT, generated["image4"], (1209, 663), fit=True)
    render_pr_curve(generated["image5"], "Fixed-Test Precision-Recall Curve", (1012, 754))
    render_final_confusion_matrix(generated["image6"])
    resize_image(OUTPUTS / "thesis_validation_threshold_curve.png", generated["image7"], (1056, 698))
    render_bridge_comparison(generated["image8"])
    resize_image(OUTPUTS / "spc_risk_chart.png", generated["image9"], (1056, 453))
    resize_image(OUTPUTS / "thesis_calibration_curve_independent_test.png", generated["image11"], (1248, 960))
    resize_image(DESKTOP_SCREENSHOT, generated["image13"], (1001, 570), fit=True)
    return generated


def replace_row_values(xml: str, label: str, replacements: list[tuple[str, str]]) -> str:
    label_token = f"<hp:t>{label}</hp:t>"
    search_from = 0
    row_bounds: tuple[int, int] | None = None
    row = ""
    while True:
        label_pos = xml.find(label_token, search_from)
        if label_pos < 0:
            break
        start = xml.rfind("<hp:tr", 0, label_pos)
        end = xml.find("</hp:tr>", label_pos)
        if start < 0 or end < 0:
            raise ValueError(f"Could not find table row bounds for: {label}")
        end += len("</hp:tr>")
        candidate = xml[start:end]
        if all(f"<hp:t>{old}</hp:t>" in candidate for old, _ in replacements):
            row_bounds = (start, end)
            row = candidate
            break
        search_from = label_pos + len(label_token)

    if row_bounds is None:
        raise ValueError(f"Could not find matching table row for: {label}")

    for old, new in replacements:
        old_token = f"<hp:t>{old}</hp:t>"
        new_token = f"<hp:t>{new}</hp:t>"
        if old_token not in row:
            raise ValueError(f"Could not find {old} in row {label}")
        row = row.replace(old_token, new_token, 1)
    start, end = row_bounds
    return xml[:start] + row + xml[end:]


def replace_text(xml: str) -> str:
    replacements = {
        "[그림 5.2] AI4I 혼동행렬": "[그림 5.2] 최종 0.86 기준 AI4I 혼동행렬",
        "[그림 5.3] 임계값 조정 결과": "[그림 5.3] 검증 세트 임계값 조정 결과",
        "[그림 5.4] 모델 전략별 정밀도-재현율 곡선": "[그림 5.4] 초기 발표 실험과 최종 보완 실험 비교",
        "[표 5.1] 기준 모델 성능 비교": "[표 5.1] 60:20:20 기준 모델 성능 비교",
        "[표 5.2] 모델 전략 비교": "[표 5.2] 초기 80:20 모델 전략 탐색 결과",
        "[표 5.3] SPC 단독 기준 vs ML 임계값 vs ML+SPC 결합 비교": "[표 5.3] 최종 0.86 기준 SPC 단독 vs ML vs ML+SPC 결합 비교",
        "[부록 그림 A.2]와 [부록 그림 A.3]": "[부록 그림 B.1]과 [부록 그림 B.2]",
        "[부록 그림 A.2] Gemini 관리자 참고 리포트 생성 화면": "[부록 그림 B.1] Gemini 관리자 참고 리포트 생성 화면",
        "[부록 그림 A.2]는 고위험 관측치의 분류 결과가 관리자 참고 리포트로 변환된 화면이다.": "[부록 그림 B.1]은 고위험 관측치의 분류 결과가 관리자 참고 리포트로 변환된 화면이다.",
        "[부록 그림 A.3] 승인형 작업지시 결과 화면": "[부록 그림 B.2] 승인형 작업지시 결과 화면",
        "[부록 그림 A.3]은 AI 리포트 검토 이후 작업자가 승인·검토·반려를 선택하고 이력을 저장하는 화면이다.": "[부록 그림 B.2]는 AI 리포트 검토 이후 작업자가 승인·검토·반려를 선택하고 이력을 저장하는 화면이다.",
        "[그림 5.1]은 Python 실험 코드로 산출한 XGBoost와 Logistic Regression의 precision-recall 곡선이며, 임계값 변화에 따른 precision-recall 상충관계를 보여준다.": "[그림 5.1]은 60:20:20 보완 실험의 고정 테스트 세트에서 산출한 Logistic Regression과 XGBoost의 precision-recall 곡선이다. 최종 해석에서는 XGBoost의 PR-AUC 0.8118과 검증 세트에서 선택한 원시 확률 임계값 0.86을 기준으로 삼았다.",
        "혼동행렬은 경보 정책 후보의 영향을 확인하기 위한 기준이다. 기존 80:20 동일 홀드아웃 초기 탐색에서 탐색한 원시 확률 임계값 0.87에서는 정밀도 0.8197, 재현율 0.7353, F1-score 0.7752가 관찰되었다. 기본 임계값보다 경보 신뢰도가 높아졌지만, 같은 자료에서 임계값을 선택하고 평가했으므로 독립적인 최종 성능으로 해석하지 않는다.": "혼동행렬은 최종 경보 정책의 오경보와 미탐 구성을 확인하기 위한 기준이다. 검증 세트에서 선택한 원시 확률 임계값 0.86을 고정 테스트 세트에 적용한 결과 TN 1920, FP 12, FN 18, TP 50이 산출되었고, 정밀도 0.8065, 재현율 0.7353, F1-score 0.7692를 보였다.",
        "임계값 0.87은 공개 데이터 기반 탐색적 정책 후보이다. 실제 설비에서는 별도 검증셋에서 임계값을 정하고, 고정 테스트셋 또는 시간 순서 기반 평가에서 마지막 한 번만 성능을 계산해야 한다.": "기존 0.87은 초기 80:20 동일 홀드아웃 탐색 결과로만 해석한다. 최종 논문과 앱의 기본 판정 기준은 검증 세트에서 선택한 원시 확률 임계값 0.86이며, 고정 테스트 세트는 선택 완료 후 최종 평가에만 사용하였다.",
        "[그림 5.3]은 Python 실험 코드로 산출한 임계값 조정 결과이며, 임계값이 높아질수록 정밀도(precision)는 증가하고 recall은 감소할 수 있음을 보여준다.": "[그림 5.3]은 검증 세트에서 원시 확률 임계값을 탐색한 결과이다. F1-score 기준으로 0.86이 선택되었고, 이 기준은 고정 테스트 세트 평가와 앱 기본 High Risk 판정에 동일하게 적용하였다.",
        "[그림 5.4]는 Python 실험 코드로 산출한 모델 전략별 precision-recall 비교 결과이며, SMOTE 적용과 임계값 조정이 동일한 방향의 성능 변화를 보장하지 않음을 나타낸다.": "[그림 5.4]는 제출 발표자료에 포함된 초기 80:20 탐색 결과와 논문 보완 과정에서 추가한 60:20:20 최종 검증 결과를 비교한 것이다. 두 결과의 임계값과 F1-score는 유사하지만, 최종 주 결과는 검증 세트에서 0.86을 선택한 보완 실험으로 해석한다.",
        "[그림 5.7]은 raw, sigmoid, isotonic 확률 보정 곡선을 비교한 것이다. 보완 실험에서는 검증 세트 Brier score를 기준으로 보정 방식을 선택하고, 선택된 방식을 고정한 뒤 테스트 세트에서 Brier score를 계산하였다.": "[그림 5.7]은 검증 세트에서 보정 방식을 선택한 뒤 고정 테스트 세트에 적용한 확률 보정 곡선이다. 보정 방식은 검증 세트 Brier score 기준으로 isotonic이 선택되었고, 테스트 세트 Brier score는 0.012369로 나타났다.",
    }
    for old, new in replacements.items():
        xml = xml.replace(old, new)

    xml = replace_row_values(
        xml,
        "Logistic Regression",
        [("0.1418", "0.1466"), ("0.2419", "0.2489"), ("0.9069", "0.9037"), ("0.3817", "0.3929")],
    )
    xml = replace_row_values(
        xml,
        "XGBoost",
        [("0.4444", "0.4553"), ("0.8824", "0.8235"), ("0.5911", "0.5864"), ("0.9736", "0.9697"), ("0.8014", "0.8118")],
    )
    xml = replace_row_values(
        xml,
        "ML 선택 임계값",
        [("ML 선택 임계값", "ML 0.86 임계값"), ("0.8197", "0.8065"), ("0.7752", "0.7692"), ("61", "62"), ("11", "12")],
    )
    xml = replace_row_values(
        xml,
        "ML + SPC OR 결합",
        [("0.6250", "0.4211"), ("0.8088", "0.8235"), ("0.7051", "0.5572"), ("88", "133"), ("33", "77"), ("13", "12")],
    )
    return xml


def patch_hwpx(images: dict[str, Path]) -> None:
    if not SOURCE_HWPX.exists():
        raise FileNotFoundError(SOURCE_HWPX)
    image_zip_map = {
        "image2": "BinData/image2.PNG",
        "image4": "BinData/image4.PNG",
        "image5": "BinData/image5.PNG",
        "image6": "BinData/image6.PNG",
        "image7": "BinData/image7.PNG",
        "image8": "BinData/image8.PNG",
        "image9": "BinData/image9.PNG",
        "image11": "BinData/image11.PNG",
        "image13": "BinData/image13.PNG",
    }
    with zipfile.ZipFile(SOURCE_HWPX, "r") as zin, zipfile.ZipFile(FINAL_HWPX, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "Contents/section2.xml":
                data = replace_text(data.decode("utf-8")).encode("utf-8")
            for image_id, image_name in image_zip_map.items():
                if item.filename == image_name:
                    data = images[image_id].read_bytes()
                    break
            zout.writestr(item, data)
    shutil.copy2(FINAL_HWPX, PACK / FINAL_HWPX.name)
    shutil.copy2(SOURCE_HWPX, PACK / SOURCE_HWPX.name)


def zip_all_text(path: Path) -> str:
    texts: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.lower().endswith((".xml", ".txt")):
                data = archive.read(name).decode("utf-8", errors="ignore")
                texts.append(re.sub(r"<[^>]+>", " ", data))
    return "\n".join(texts)


def validation_report() -> dict[str, object]:
    text = zip_all_text(FINAL_HWPX)
    checks = {
        "0.86": text.count("0.86"),
        "0.7692": text.count("0.7692"),
        "0.87": text.count("0.87"),
        "0.7752": text.count("0.7752"),
        "threshold 0.87": text.count("threshold 0.87"),
        "Best threshold=0.87": text.count("Best threshold=0.87"),
        "old_table_5_3_precision_0.6250": text.count("0.6250"),
        "old_table_5_3_alerts_88": text.count("0.6250") + text.count("0.7051"),
        "final_spc_precision_0.4211": text.count("0.4211"),
        "final_spc_recall_0.8235": text.count("0.8235"),
        "final_spc_alerts_133": text.count("133"),
        "appendix_A2": text.count("부록 그림 A.2"),
        "appendix_A3": text.count("부록 그림 A.3"),
        "appendix_B1": text.count("부록 그림 B.1"),
        "appendix_B2": text.count("부록 그림 B.2"),
    }
    report = {
        "final_hwpx": str(FINAL_HWPX),
        "package": str(PACK),
        "zip": str(ZIP_PATH),
        "checks": checks,
        "image_mapping": {
            "figure_3_1": "BinData/image2.PNG",
            "figure_4_2": "BinData/image4.PNG",
            "figure_5_1": "BinData/image5.PNG",
            "figure_5_2": "BinData/image6.PNG",
            "figure_5_3": "BinData/image7.PNG",
            "figure_5_4": "BinData/image8.PNG",
            "figure_5_5": "BinData/image9.PNG",
            "figure_5_7": "BinData/image11.PNG",
            "appendix_A_1": "BinData/image13.PNG",
        },
    }
    (VALIDATION / "hwpx_figure_table_patch_report_260612_v2.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def write_package_docs(report: dict[str, object]) -> None:
    checks = report["checks"]
    (DOCS / "README_260612_v2.md").write_text(
        f"""# 260612 논문 그림표 수정본 패키지

- 최종 HWPX: `{FINAL_HWPX}`
- 원본 보존: `{SOURCE_HWPX}`
- 수정본 ZIP: `{ZIP_PATH}`

## 핵심 수정

- 그림 3.1: 60:20:20 검증-평가 분리 절차도로 교체
- 그림 4.2: Desktop 0.86 / 고위험 62건 화면으로 교체
- 그림 5.1: fixed-test PR curve로 교체
- 그림 5.2: 최종 0.86 혼동행렬(TN 1920, FP 12, FN 18, TP 50)로 교체
- 그림 5.3: validation-selected threshold 0.86 곡선으로 교체
- 그림 5.4: 초기 발표 실험과 최종 보완 실험 비교 그림으로 교체
- 그림 5.5: 0.86 기준 SPC risk chart로 교체
- 그림 5.7: validation-set method selection 이후 calibration curve로 교체
- 표 5.1, 표 5.3 수치를 최종 60:20:20 / 0.86 결과로 보정
- 부록 그림 A.2/A.3을 B.1/B.2로 수정

## 검증 카운트

```json
{json.dumps(checks, indent=2, ensure_ascii=False)}
```
""",
        encoding="utf-8",
    )


def zip_package() -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in PACK.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(PACK.parent))


def main() -> None:
    reset_pack()
    images = copy_and_resize_existing_figures()
    for path in [
        OUTPUTS / "threshold_summary.json",
        OUTPUTS / "thesis_methodology_metrics.json",
        OUTPUTS / "spc_summary.json",
        OUTPUTS / "thesis_60_20_20_metrics.csv",
        OUTPUTS / "thesis_calibration_comparison.csv",
        OUTPUTS / "spc_timeseries.csv",
    ]:
        if path.exists():
            shutil.copy2(path, TABLES / path.name)
    patch_hwpx(images)
    report = validation_report()
    write_package_docs(report)
    zip_package()
    print(f"Final HWPX: {FINAL_HWPX}")
    print(f"Package: {PACK}")
    print(f"ZIP: {ZIP_PATH}")
    print(json.dumps(report["checks"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
