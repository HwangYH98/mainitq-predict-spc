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
PACK = OUTPUTS / "thesis_alignment_260612_v3"
FIGURES = PACK / "figures"
TABLES = PACK / "tables"
DOCS = PACK / "docs"
VALIDATION = PACK / "validation"
ZIP_PATH = OUTPUTS / "thesis_alignment_260612_v3.zip"

DESKTOP = Path.home() / "Desktop"
SOURCE_HWPX = DESKTOP / "학부졸업논문_평가반영_최종본_0.86앱통일본.hwpx"
FINAL_HWPX = DESKTOP / "학부졸업논문_평가반영_최종본_0.86앱통일본_문장용어최종수정본.hwpx"
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


def render_concept_architecture(path: Path) -> None:
    set_korean_font()
    fig, ax = plt.subplots(figsize=(11.87, 6.67))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.text(0.35, 5.55, "연구 개념과 주장 범위", fontsize=21, weight="bold", color="#0f766e")
    ax.plot([0.35, 9.65], [5.3, 5.3], color="#0f766e", lw=2.2)
    ax.text(0.35, 5.0, "공개 데이터 기반 위험 분류부터 관리자 참고 리포트와 승인형 작업지시까지의 연구 범위", fontsize=12, color="#475569")

    boxes = [
        (0.6, 3.25, "센서 CSV 입력\nAI4I/회사식 CSV\n컬럼 매핑·단위 확인"),
        (2.75, 3.25, "전처리·위험 분류\nXGBoost 확률 계산\n고위험 판정"),
        (4.9, 3.25, "SPC 기반 위험확률 추세도\nUDI 순서 위험 흐름\n관리한계 참고 신호"),
        (7.05, 3.25, "GenAI 참고 리포트\n위험 요인 요약\n관리자 참고 문장"),
        (2.75, 1.25, "작업지시 초안\n센서 이벤트 기반\n승인 전 초안 생성"),
        (4.9, 1.25, "작업자 결정\n승인 / 검토 / 반려\n이력 저장"),
        (7.05, 1.25, "주장 범위\n자동 정비 명령 아님\n현장 실증은 별도 필요"),
    ]
    for i, (x, y, text) in enumerate(boxes):
        face = "#f0fdfa" if i < 6 else "#fff7ed"
        edge = "#0f766e" if i < 6 else "#f97316"
        ax.add_patch(plt.Rectangle((x, y), 1.75, 1.05, facecolor=face, edgecolor=edge, linewidth=1.5, joinstyle="round"))
        ax.text(x + 0.875, y + 0.525, text, ha="center", va="center", fontsize=10.5, linespacing=1.4)
    for x1, x2 in [(2.35, 2.75), (4.5, 4.9), (6.65, 7.05)]:
        ax.annotate("", xy=(x2, 3.78), xytext=(x1, 3.78), arrowprops=dict(arrowstyle="-|>", lw=1.6, color="#0f766e"))
    ax.annotate("", xy=(3.62, 2.3), xytext=(3.62, 3.25), arrowprops=dict(arrowstyle="-|>", lw=1.6, color="#0f766e"))
    ax.annotate("", xy=(4.9, 1.78), xytext=(4.5, 1.78), arrowprops=dict(arrowstyle="-|>", lw=1.6, color="#0f766e"))
    ax.text(5.0, 0.45, "핵심 차별점: 분류 결과를 그래프·리포트·작업지시 이력으로 연결", ha="center", fontsize=13, weight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor="white")
    plt.close(fig)
    resize_image(path, path, (1187, 667), fit=True)


def render_technical_architecture(path: Path) -> None:
    set_korean_font()
    fig, ax = plt.subplots(figsize=(18, 6.2))
    ax.axis("off")
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 5.4)
    ax.text(0.45, 5.0, "시스템 모듈·데이터 저장 구조", fontsize=20, weight="bold", color="#0f766e")
    ax.text(0.45, 4.65, "데스크톱 앱, 모델 파일, 로컬 산출물, SQLite 이력을 분리한 운영 아키텍처", fontsize=12, color="#475569")

    boxes = [
        (0.45, 3.15, "입력 계층\n센서 CSV\n스키마·품질 점검"),
        (2.75, 3.15, "전처리 엔진\nID/누수 컬럼 제거\nType 매핑"),
        (5.05, 3.15, "모델 엔진\nXGBoost joblib\nraw probability"),
        (7.35, 3.15, "판정 정책\nthreshold 0.86\n고위험 판정"),
        (9.65, 3.15, "SPC 기반 위험확률 추세도\n학습 정상 자료 관리한계\nUDI 순서 보조 시각화"),
        (12.4, 3.15, "GenAI 리포트\n세션 API key\n관리자 참고 문장"),
        (7.35, 1.15, "작업지시 기록\n초안·승인·검토·반려\nSQLite / CSV 감사 로그"),
        (10.0, 1.15, "출력 산출물\n예측 CSV\n그래프 PNG\n검증 리포트"),
        (12.65, 1.15, "주장 경계\n실시간 PLC/SCADA 아님\n현장 성과 입증 아님"),
    ]
    for i, (x, y, text) in enumerate(boxes):
        w = 2.0 if i not in (4, 6, 7, 8) else 2.25
        face = "#ecfeff" if i < 8 else "#fff7ed"
        edge = "#0f766e" if i < 8 else "#f97316"
        ax.add_patch(plt.Rectangle((x, y), w, 1.0, facecolor=face, edgecolor=edge, linewidth=1.5, joinstyle="round"))
        ax.text(x + w / 2, y + 0.5, text, ha="center", va="center", fontsize=10.5, linespacing=1.35)
    for x1, x2 in [(2.45, 2.75), (4.75, 5.05), (7.05, 7.35), (9.35, 9.65), (11.9, 12.4)]:
        ax.annotate("", xy=(x2, 3.65), xytext=(x1, 3.65), arrowprops=dict(arrowstyle="-|>", lw=1.6, color="#334155"))
    ax.annotate("", xy=(8.45, 2.15), xytext=(8.45, 3.15), arrowprops=dict(arrowstyle="-|>", lw=1.6, color="#334155"))
    ax.annotate("", xy=(10.0, 1.65), xytext=(9.6, 1.65), arrowprops=dict(arrowstyle="-|>", lw=1.6, color="#334155"))
    ax.text(8.0, 0.35, "최종 앱 판정 기준: raw_probability >= 0.86", ha="center", fontsize=13, weight="bold", color="#b3261e")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor="white")
    plt.close(fig)
    resize_image(path, path, (1800, 620), fit=True)


def render_local_validation_report(path: Path) -> None:
    set_korean_font()
    fig, ax = plt.subplots(figsize=(10.01, 5.7))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.7)
    ax.text(0.35, 5.25, "0.86 기준 로컬 검증 리포트", fontsize=19, weight="bold", color="#0f172a")
    ax.text(0.35, 4.95, "Desktop/Streamlit/GitHub 산출물의 최종 연구 기준 일치 여부", fontsize=11.5, color="#475569")

    cards = [
        (0.45, 3.6, "최종 판정 기준", "raw_probability >= 0.86"),
        (3.55, 3.6, "고정 테스트 F1", "0.7692"),
        (6.65, 3.6, "고정 테스트 PR-AUC", "0.8118"),
        (0.45, 2.15, "혼동행렬", "TN 1920 / FP 12 / FN 18 / TP 50"),
        (3.55, 2.15, "확률 보정", "validation Brier 기준 isotonic"),
        (6.65, 2.15, "테스트 Brier", "0.012369"),
        (0.45, 0.7, "구버전 기준 처리", "0.87은 초기 80:20 탐색 결과"),
        (3.55, 0.7, "앱 기준", "보정 확률은 참고값, 판정은 raw 0.86"),
        (6.65, 0.7, "검증 범위", "공개 데이터 기반 로컬 검증"),
    ]
    for x, y, label, value in cards:
        ax.add_patch(plt.Rectangle((x, y), 2.8, 1.05, facecolor="#f8fafc", edgecolor="#94a3b8", linewidth=1.1, joinstyle="round"))
        ax.text(x + 0.18, y + 0.72, label, ha="left", va="center", fontsize=10.5, color="#475569")
        ax.text(x + 0.18, y + 0.34, value, ha="left", va="center", fontsize=11.5, weight="bold", color="#0f172a")
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor="white")
    plt.close(fig)
    resize_image(path, path, (1001, 570), fit=True)


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
    ax.set_xticks([0, 1], ["Normal", "고위험"])
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
    ax.set_title("Initial Holdout Search vs Validation-Test Split Result", fontsize=15, weight="bold")
    ax.set_xticks(x, labels)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(ncol=4, loc="upper center")
    ax.text(
        0.5,
        -0.16,
        "0.87 is the initial holdout-search result; 0.86 is the validation-selected decision policy.",
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
        "image1": FIGURES / "figure_1_1_research_concept_boundary.png",
        "image3": FIGURES / "figure_4_1_technical_architecture.png",
        "image2": FIGURES / "figure_3_1_method_flow_0_86.png",
        "image4": FIGURES / "figure_4_2_desktop_0_86.png",
        "image5": FIGURES / "figure_5_1_fixed_test_pr_curve.png",
        "image6": FIGURES / "figure_5_2_final_confusion_matrix_0_86.png",
        "image7": FIGURES / "figure_5_3_validation_threshold_curve_0_86.png",
        "image8": FIGURES / "figure_5_4_holdout_vs_validation_test_comparison.png",
        "image9": FIGURES / "figure_5_5_spc_risk_chart_0_86.png",
        "image11": FIGURES / "figure_5_7_calibration_after_validation_selection.png",
        "image13": FIGURES / "appendix_A1_local_validation_report_0_86.png",
    }
    render_concept_architecture(generated["image1"])
    render_method_flow(generated["image2"])
    render_technical_architecture(generated["image3"])
    resize_image(DESKTOP_SCREENSHOT, generated["image4"], (1209, 663), fit=True)
    render_pr_curve(generated["image5"], "Fixed-Test Precision-Recall Curve", (1012, 754))
    render_final_confusion_matrix(generated["image6"])
    resize_image(OUTPUTS / "thesis_validation_threshold_curve.png", generated["image7"], (1056, 698))
    render_bridge_comparison(generated["image8"])
    resize_image(OUTPUTS / "spc_risk_chart.png", generated["image9"], (1056, 453))
    resize_image(OUTPUTS / "thesis_calibration_curve_independent_test.png", generated["image11"], (1248, 960))
    render_local_validation_report(generated["image13"])
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

    v3_replacements = {
        "[그림 5.1] XGBoost 정밀도-재현율 곡선": "[그림 5.1] 기준 모델별 정밀도-재현율 곡선",
        "[그림 5.4] 초기 발표 실험과 최종 보완 실험 비교": "[그림 5.4] 초기 홀드아웃 탐색과 검증-테스트 분리 결과 비교",
        "[부록 그림 A.1] 로컬 검증 화면": "[부록 그림 A.1] 0.86 기준 로컬 검증 리포트",
        "[부록 그림 A.1] MaintiQ Predict 로컬 검증 화면": "[부록 그림 A.1] 0.86 기준 로컬 검증 리포트",
        "[부록 그림 A.1]은 로컬 실행 환경에서 센서 CSV 기반 위험도 확인 화면을 제시한다.": "[부록 그림 A.1]은 최종 판정 기준 0.86, 고정 테스트 성능, 보정 방식, 앱 기준을 한 화면에 요약한 로컬 검증 리포트이다.",
        "AI4I 기준 실험에서는 Logistic Regression을 선형 기준선으로, XGBoost를 비교 모델로 설정하였다. XGBoost는 PR-AUC 0.8014, ROC-AUC 0.9736, F1-score 0.5911로 Logistic Regression보다 우수하여 이후 임계값 조정과 운영 검증의 기준 위험 분류 엔진으로 사용하였다.": "60:20:20 분할의 고정 테스트 세트에서 XGBoost는 PR-AUC 0.8118, ROC-AUC 0.9697, F1-score 0.5864를 보여 Logistic Regression보다 높은 판별 성능을 나타냈다. 이 값은 기본 모델 비교 성능이며, 검증 세트에서 선택한 임계값 0.86을 적용한 정책 성능은 별도로 F1-score 0.7692로 해석하였다.",
        "임계값 조정은 XGBoost가 산출한 고장 확률을 경보 후보로 변환하는 기준을 탐색하기 위해 수행하였다. 기본 임계값 0.50은 통계적 기본값일 뿐 제조 현장의 오경보와 미탐 비용 구조를 반영하지 못할 수 있다. 본 연구에서는 기존 80:20 동일 홀드아웃 초기 탐색에서 0.05~0.95를 탐색해 선택된 원시 확률 임계값 0.87의 정밀도와 재현율을 비교하였다. 따라서 0.87에서의 성능은 독립 최종 성능이 아니라 탐색적 정책 후보 성능이다.": "임계값 조정은 XGBoost가 산출한 고장 확률을 경보 후보로 변환하는 기준을 선택하기 위해 수행하였다. 본 연구에서는 학습 60%, 검증 20%, 테스트 20%로 자료를 층화 분할하였다. 모델은 학습 세트에서 적합하고, 임계값과 확률 보정 방식은 검증 세트에서 선택하였다. 선택된 임계값 0.86과 isotonic 보정 방식은 검증 세트와 분리된 고정 테스트 세트에 적용하여 최종 성능을 평가하였다. 기존 80:20 실험의 0.87은 초기 탐색 결과로서 표 5.2에서 참고용으로만 제시하였다.",
        "특히 임계값 선택, 보정 방식 선택, 하이퍼파라미터 선택과 최종 성능 평가는 원칙적으로 분리되어야 한다. 본 연구는 공개 데이터 기반 정책 후보의 탐색적 비교에 초점을 두었으므로, 후속 검증에서는 학습-검증-테스트 분리 또는 반복 층화 교차검증과 별도 고정 테스트셋을 사용해야 한다. 부트스트랩 신뢰구간이나 여러 난수 조건의 평균·표준편차를 제시하는 것도 단일 분할의 변동성을 확인하는 방법이다.": "초기 탐색의 선택 편향을 줄이기 위해 검증 세트와 테스트 세트를 분리하였다. 다만 동일 공개 데이터 내부의 정적 분할이므로 외부 타당도에는 한계가 있다. 따라서 후속 연구에서는 외부 데이터, 시간 순서 분할, 반복 교차검증을 통해 임계값과 보정 방식의 안정성을 추가로 확인할 필요가 있다.",
        "[표 5.3]은 SPC 단독 기준이 경보 수를 줄이는 대신 재현율이 낮고, ML 임계값 후보는 해당 홀드아웃에서 F1이 높으며, ML+SPC OR 결합은 검토 후보를 넓이는 대신 오경보 증가를 감수함을 보여준다.": "[표 5.3]은 SPC 단독 기준이 경보 수를 줄이는 대신 재현율이 낮고, ML 0.86 기준은 고정 테스트 세트에서 세 전략 중 가장 높은 F1-score를 보였으며, ML+SPC OR 결합은 검토 후보를 넓이는 대신 오경보 증가를 감수함을 보여준다.",
        "[그림 5.4]는 제출 발표자료에 포함된 초기 80:20 탐색 결과와 논문 보완 과정에서 추가한 60:20:20 최종 검증 결과를 비교한 것이다. 두 결과의 임계값과 F1-score는 유사하지만, 최종 주 결과는 검증 세트에서 0.86을 선택한 보완 실험으로 해석한다.": "[그림 5.4]는 초기 80:20 홀드아웃 탐색 결과와 60:20:20 검증-테스트 분리 결과를 비교한 것이다. 두 결과의 임계값과 F1-score는 유사하지만, 최종 주 결과는 검증 세트에서 0.86을 선택하고 고정 테스트 세트에 적용한 분리 평가 결과로 해석한다.",
        "[표 5.2]의 결과는 모델 복잡도, SMOTE 적용 여부, 임계값 조정 여부가 경보 특성에 상이한 영향을 미침을 보여준다. 다만 기존 표의 조정 임계값 행은 동일 홀드아웃에서 탐색한 후보이므로 최종 일반화 성능으로 단정하지 않는다. 최종 보완 실험에서는 검증 세트 선택 임계값 0.86을 고정한 뒤 검증 세트와 분리된 고정 테스트 세트에서 F1-score 0.7692를 확인하였다.": "[표 5.2]는 기존 80:20 단일 홀드아웃에서 수행한 초기 전략 탐색 결과이다. 이 결과는 최종 일반화 성능이 아니라 SMOTE와 임계값 조정의 상충관계를 확인하기 위한 참고 결과로 사용하였다. 최종 보완 실험에서는 검증 세트에서 임계값 0.86을 선택하고 고정 테스트 세트에 적용하여 정밀도 0.8065, 재현율 0.7353, F1-score 0.7692를 확인하였다.",
    }
    for old, new in v3_replacements.items():
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
    xml = replace_row_values(
        xml,
        "임계값·보정 선택 타당도",
        [
            ("임계값, 보정 방식, 정책 임계값 선택과 평가가 동일 테스트셋에 의존할 경우 과대평가 가능성", "단일 검증 분할에서 선택한 임계값과 보정 방식이 다른 분할에서 달라질 가능성"),
            ("해당 수치를 최종 성능이 아닌 탐색적 정책 후보로 제한하여 해석", "검증 세트에서 임계값 0.86과 isotonic을 선택하고, 검증 세트와 분리된 고정 테스트 세트에서 최종 평가"),
            ("검증셋에서 선택하고 별도 고정 테스트셋에서 최종 평가 필요", "외부 데이터, 시간 순서 분할, 반복 교차검증에 따른 정책 안정성 추가 검증 필요"),
        ],
    )
    cleanup_replacements = {
        "분류은": "분류는",
        "해당 홀드아웃": "고정 테스트 세트",
        "고위험 row": "고위험 행",
        "High Risk": "고위험",
        "trade-off": "상충관계",
        "metric": "지표",
        "SPC-inspired": "SPC 원리를 참고한",
        "테스트셋": "테스트 세트",
        "검증셋": "검증 세트",
        "확률보정": "확률 보정",
        "정상자료": "정상 자료",
        "공개데이터": "공개 데이터",
        "운영가치": "운영 가치",
        "Predictive SPC": "SPC 기반 위험확률 추세도",
    }
    for old, new in cleanup_replacements.items():
        xml = xml.replace(old, new)
    return xml


def replace_common_frontmatter_text(xml: str) -> str:
    common_replacements = {
        "[그림 5.1] XGBoost 정밀도-재현율 곡선": "[그림 5.1] 기준 모델별 정밀도-재현율 곡선",
        "[그림 5.4] 초기 발표 실험과 최종 보완 실험 비교": "[그림 5.4] 초기 홀드아웃 탐색과 검증-테스트 분리 결과 비교",
        "[부록 그림 A.1] 로컬 검증 화면": "[부록 그림 A.1] 0.86 기준 로컬 검증 리포트",
        "[부록 그림 A.1] MaintiQ Predict 로컬 검증 화면": "[부록 그림 A.1] 0.86 기준 로컬 검증 리포트",
        "High Risk": "고위험",
        "Predictive SPC": "SPC 기반 위험확률 추세도",
        "trade-off": "상충관계",
        "metric": "지표",
        "SPC-inspired": "SPC 원리를 참고한",
        "테스트셋": "테스트 세트",
        "검증셋": "검증 세트",
    }
    for old, new in common_replacements.items():
        xml = xml.replace(old, new)
    return xml


def patch_hwpx(images: dict[str, Path]) -> None:
    if not SOURCE_HWPX.exists():
        raise FileNotFoundError(SOURCE_HWPX)
    image_zip_map = {
        "image1": "BinData/image1.PNG",
        "image2": "BinData/image2.PNG",
        "image3": "BinData/image3.PNG",
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
            elif item.filename.startswith("Contents/section") and item.filename.endswith(".xml"):
                data = replace_common_frontmatter_text(data.decode("utf-8")).encode("utf-8")
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
        "legacy_metric_pr_auc_0.8014": text.count("0.8014"),
        "legacy_metric_roc_auc_0.9736": text.count("0.9736"),
        "legacy_metric_f1_0.5911": text.count("0.5911"),
        "final_table_5_1_pr_auc_0.8118": text.count("0.8118"),
        "final_table_5_1_roc_auc_0.9697": text.count("0.9697"),
        "final_table_5_1_f1_0.5864": text.count("0.5864"),
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
        "typo_분류은": text.count("분류은"),
        "old_phrase_해당_홀드아웃": text.count("해당 홀드아웃"),
        "old_phrase_별도_고정_테스트셋": text.count("별도 고정 테스트셋"),
        "old_phrase_선택과_평가가_동일_테스트셋": text.count("선택과 평가가 동일 테스트셋"),
        "old_title_XGBoost_PR_curve": text.count("XGBoost 정밀도-재현율 곡선"),
        "old_phrase_고위험_row": text.count("고위험 row"),
        "old_phrase_Predictive_SPC": text.count("Predictive SPC"),
        "old_phrase_High_Risk": text.count("High Risk"),
        "old_phrase_trade_off": text.count("trade-off"),
        "old_phrase_metric": text.count("metric"),
        "old_phrase_SPC_inspired": text.count("SPC-inspired"),
        "old_phrase_테스트셋": text.count("테스트셋"),
        "old_phrase_검증셋": text.count("검증셋"),
    }
    report = {
        "final_hwpx": str(FINAL_HWPX),
        "package": str(PACK),
        "zip": str(ZIP_PATH),
        "checks": checks,
        "image_mapping": {
            "figure_1_1": "BinData/image1.PNG",
            "figure_3_1": "BinData/image2.PNG",
            "figure_4_1": "BinData/image3.PNG",
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
    (VALIDATION / "hwpx_sentence_term_patch_report_260612_v3.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def write_package_docs(report: dict[str, object]) -> None:
    checks = report["checks"]
    (DOCS / "README_260612_v3.md").write_text(
        f"""# 260612 논문 문장·용어 최종 수정본 패키지

- 최종 HWPX: `{FINAL_HWPX}`
- 원본 보존: `{SOURCE_HWPX}`
- 수정본 ZIP: `{ZIP_PATH}`

## 핵심 수정

- 표 5.1 앞 본문 수치를 60:20:20 기준 `PR-AUC 0.8118 / ROC-AUC 0.9697 / F1 0.5864`로 수정
- 3장의 구버전 “향후 검증-테스트 분리 필요” 문장을 현재 60:20:20 설계 설명으로 교체
- 표 5.7의 임계값·보정 선택 타당도 행을 현재 검증 세트 선택/고정 테스트 평가 구조로 수정
- `분류은`, `해당 홀드아웃`, `고위험 row`, `High Risk`, `trade-off`, `metric`, `SPC-inspired`, `테스트셋`, `검증셋` 등 잔여 용어 정리
- 그림 1.1, 그림 4.1의 `Predictive SPC` 표현 제거 및 역할 분리
- 그림 5.1 제목을 기준 모델별 정밀도-재현율 곡선으로 수정
- 그림 5.4를 초기 홀드아웃 탐색과 검증-테스트 분리 결과 비교로 수정
- 부록 A.1을 홈 화면 중복이 아닌 0.86 기준 로컬 검증 리포트로 교체
- 그림 3.1: 60:20:20 검증-평가 분리 절차도로 유지
- 그림 4.2: Desktop 0.86 / 고위험 62건 화면으로 유지
- 그림 5.1: fixed-test PR curve로 유지
- 그림 5.2: 최종 0.86 혼동행렬(TN 1920, FP 12, FN 18, TP 50)로 교체
- 그림 5.3: validation-selected threshold 0.86 곡선으로 교체
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
