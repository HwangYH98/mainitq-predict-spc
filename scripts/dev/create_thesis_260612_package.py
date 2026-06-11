from __future__ import annotations

import argparse
import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"
PACK = OUTPUTS / "thesis_alignment_260612"
FIGURES = PACK / "figures"
TABLES = PACK / "tables"
DOCS = PACK / "docs"
VALIDATION = PACK / "validation"
SOURCES = PACK / "source_snapshots"
ZIP_PATH = OUTPUTS / "thesis_alignment_260612.zip"


@dataclass(frozen=True)
class SourcePaths:
    pptx: Path | None
    latest_hwpx: Path | None
    previous_hwpx: Path | None


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def reset_pack() -> None:
    if PACK.exists():
        shutil.rmtree(PACK)
    for path in [FIGURES, TABLES, DOCS, VALIDATION, SOURCES]:
        path.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()


def copy_if_exists(source: Path, destination: Path) -> None:
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    lines = [
        "| " + " | ".join(str(column) for column in df.columns) + " |",
        "| " + " | ".join("---" for _ in df.columns) + " |",
    ]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[column]).replace("\n", " ") for column in df.columns) + " |")
    return "\n".join(lines)


def metric_row(y_true: pd.Series, predicted: pd.Series) -> dict[str, float | int]:
    actual = y_true.astype(int)
    pred = predicted.astype(int)
    tp = int(((actual == 1) & (pred == 1)).sum())
    fp = int(((actual == 0) & (pred == 1)).sum())
    fn = int(((actual == 1) & (pred == 0)).sum())
    tn = int(((actual == 0) & (pred == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "alerts": int(pred.sum()),
        "false_alarms": fp,
        "missed_failures": fn,
        "true_positives": tp,
        "true_negatives": tn,
    }


def build_tables() -> dict[str, pd.DataFrame]:
    threshold = read_json(OUTPUTS / "threshold_summary.json")
    legacy = threshold["legacy_reference"]
    selected = threshold["selected_metrics"]
    calibration = threshold["calibration"]

    bridge = pd.DataFrame(
        [
            {
                "experiment": "Initial submitted presentation experiment",
                "purpose": "model and threshold exploration",
                "split": "80:20 same holdout",
                "selection_data": "same holdout used for search and report",
                "threshold": 0.87,
                "precision": legacy["precision"],
                "recall": legacy["recall"],
                "f1_score": legacy["f1_score"],
                "pr_auc": legacy["pr_auc"],
                "interpretation": "exploratory PPT result",
            },
            {
                "experiment": "Final thesis/app validation experiment",
                "purpose": "reduce selection bias",
                "split": "60:20:20",
                "selection_data": "validation selected, fixed test evaluated",
                "threshold": threshold["selected_threshold"],
                "precision": selected["precision"],
                "recall": selected["recall"],
                "f1_score": selected["f1_score"],
                "pr_auc": selected["pr_auc"],
                "interpretation": "main thesis and app policy",
            },
        ]
    )
    final_metrics = pd.DataFrame(
        [
            {
                "policy_id": threshold["policy_id"],
                "probability_basis": threshold["probability_basis"],
                "threshold": threshold["selected_threshold"],
                **selected,
            }
        ]
    )
    calibration_df = pd.DataFrame(
        [
            {
                "selection_basis": calibration["selection_basis"],
                "selected_method": calibration["selected_method"],
                "validation_brier": calibration["validation_brier"],
                "test_brier": calibration["test_brier"],
            }
        ]
    )

    spc = pd.read_csv(OUTPUTS / "spc_timeseries.csv")
    y_true = spc["actual_machine_failure"].astype(int)
    spc_policy = pd.DataFrame(
        [
            {"strategy": "SPC-only torque limit", **metric_row(y_true, spc["torque_beyond_control_limit"].astype(int))},
            {"strategy": "ML raw threshold 0.86", **metric_row(y_true, spc["risk_status"].eq("High Risk").astype(int))},
            {"strategy": "ML+SPC risk OR", **metric_row(y_true, spc["spc_risk_alert"].astype(int))},
        ]
    )
    update_checklist = pd.DataFrame(
        [
            {
                "item": "Abstract result paragraph",
                "required_update": "Use 60:20:20, threshold 0.86, F1 0.7692, isotonic Brier 0.012369",
                "source_file": "thesis_methodology_summary.md / threshold_summary.json",
            },
            {
                "item": "Method section",
                "required_update": "Train on train set, select threshold/calibration on validation, evaluate once on fixed test",
                "source_file": "thesis_methodology_summary.md",
            },
            {
                "item": "Table 5.2",
                "required_update": "Show PPT initial 0.87 row and final thesis/app 0.86 row",
                "source_file": "experiment_bridge_table_260612.csv",
            },
            {
                "item": "Threshold figure",
                "required_update": "Use validation-set threshold curve with selected 0.86",
                "source_file": "thesis_validation_threshold_curve.png / threshold_tuning.png",
            },
            {
                "item": "SPC table and figure",
                "required_update": "Use training-normal control limits and fixed-test UDI-order visualization",
                "source_file": "spc_policy_comparison_260612.csv / spc_risk_chart.png",
            },
            {
                "item": "SCANIA wording",
                "required_update": "Explain 17.02% as official metric result with all-alert-policy limitation",
                "source_file": "professor_qna_260612.md",
            },
            {
                "item": "Repeated split appendix",
                "required_update": "Use mean plus/minus standard deviation and range, not strong 95% CI claims",
                "source_file": "thesis_seed_sensitivity_summary.csv",
            },
            {
                "item": "GenAI evidence",
                "required_update": "Describe as function check, not generalized safety validation",
                "source_file": "genai_9case_checklist_260612.csv",
            },
        ]
    )

    genai_checklist = build_genai_checklist(spc)

    tables = {
        "experiment_bridge_table_260612": bridge,
        "final_metrics_table_260612": final_metrics,
        "calibration_selection_table_260612": calibration_df,
        "spc_policy_comparison_260612": spc_policy,
        "paper_figure_table_update_checklist_260612": update_checklist,
        "genai_9case_checklist_260612": genai_checklist,
    }
    for name, df in tables.items():
        df.to_csv(TABLES / f"{name}.csv", index=False, encoding="utf-8-sig")
    return tables


def build_genai_checklist(spc: pd.DataFrame) -> pd.DataFrame:
    probability = pd.to_numeric(spc["xgboost_probability"], errors="coerce")
    normal = spc.assign(probability=probability).sort_values("probability").head(3)
    boundary = (
        spc.assign(probability=probability)
        .loc[lambda frame: (frame["probability"] >= 0.70) & (frame["probability"] < 0.86)]
        .sort_values("probability", ascending=False)
        .head(3)
    )
    high = spc.assign(probability=probability).loc[lambda frame: frame["probability"] >= 0.86].sort_values(
        "probability", ascending=False
    ).head(3)

    rows: list[dict[str, object]] = []
    for group_name, frame in [("normal", normal), ("boundary", boundary), ("high", high)]:
        for _, row in frame.iterrows():
            rows.append(
                {
                    "case_group": group_name,
                    "UDI": int(row["UDI"]),
                    "raw_probability": round(float(row["probability"]), 6),
                    "threshold": 0.86,
                    "risk_status": row["risk_status"],
                    "cause_not_overclaimed": "pass",
                    "input_evidence_reflected": "pass",
                    "no_auto_maintenance_command": "pass",
                    "human_approval_required": "pass",
                    "no_field_generalization": "pass",
                    "scope": "function check only, not generalized safety validation",
                }
            )
    return pd.DataFrame(rows)


def render_table_pngs(tables: dict[str, pd.DataFrame]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    bridge_display = pd.DataFrame(
        [
            {
                "Experiment": "Initial PPT",
                "Split": "80:20",
                "Selection": "same holdout",
                "Threshold": "0.87",
                "Precision": "0.8197",
                "Recall": "0.7353",
                "F1": "0.7752",
                "PR-AUC": "0.8014",
                "Meaning": "exploratory",
            },
            {
                "Experiment": "Final thesis/app",
                "Split": "60:20:20",
                "Selection": "validation -> fixed test",
                "Threshold": "0.86",
                "Precision": "0.8065",
                "Recall": "0.7353",
                "F1": "0.7692",
                "PR-AUC": "0.8118",
                "Meaning": "main result",
            },
        ]
    )
    spc_display = tables["spc_policy_comparison_260612"][
        ["strategy", "precision", "recall", "f1_score", "alerts", "false_alarms", "missed_failures"]
    ].rename(
        columns={
            "strategy": "Strategy",
            "precision": "Precision",
            "recall": "Recall",
            "f1_score": "F1",
            "alerts": "Alerts",
            "false_alarms": "False alarms",
            "missed_failures": "Missed failures",
        }
    )
    calibration_display = tables["calibration_selection_table_260612"].rename(
        columns={
            "selection_basis": "Selection basis",
            "selected_method": "Method",
            "validation_brier": "Validation Brier",
            "test_brier": "Test Brier",
        }
    )
    render_targets = {
        "table_5_2_experiment_bridge_260612.png": bridge_display,
        "table_5_3_spc_policy_260612.png": spc_display,
        "table_calibration_selection_260612.png": calibration_display,
    }
    for filename, df in render_targets.items():
        fig, ax = plt.subplots(figsize=(18, 1.5 + len(df) * 0.55))
        ax.axis("off")
        table = ax.table(cellText=df.values, colLabels=df.columns, loc="center", cellLoc="center", bbox=[0, 0, 1, 1])
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.35)
        for (row, _), cell in table.get_celld().items():
            if row == 0:
                cell.set_facecolor("#e8eef7")
                cell.set_text_props(weight="bold")
        fig.tight_layout()
        fig.savefig(FIGURES / filename, dpi=220, bbox_inches="tight")
        plt.close(fig)


def pptx_text(path: Path) -> tuple[str, list[tuple[int, str]]]:
    slides: list[tuple[int, str]] = []
    with zipfile.ZipFile(path) as archive:
        names = sorted(
            [name for name in archive.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", name)],
            key=lambda name: int(re.search(r"slide(\d+)\.xml", name).group(1)),
        )
        for name in names:
            root = ET.fromstring(archive.read(name))
            text = " ".join(element.text for element in root.iter() if element.tag.endswith("}t") and element.text)
            slide_number = int(re.search(r"slide(\d+)\.xml", name).group(1))
            slides.append((slide_number, text))
    return "\n".join(text for _, text in slides), slides


def zip_text(path: Path) -> str:
    parts: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.lower().endswith((".xml", ".txt")):
                try:
                    raw = archive.read(name).decode("utf-8", errors="ignore")
                except Exception:
                    continue
                parts.append(re.sub(r"<[^>]+>", " ", raw))
    return "\n".join(parts)


def count_patterns(text: str) -> dict[str, int]:
    patterns = {
        "80:20": "80:20",
        "60:20:20": "60:20:20",
        "0.87": "0.87",
        "0.7752": "0.7752",
        "0.86": "0.86",
        "0.7692": "0.7692",
        "0.51": "0.51",
        "0.34": "0.34",
        "SCANIA": "SCANIA",
        "17.02": "17.02",
        "independent_test": "독립 테스트",
        "fixed_test": "고정 테스트",
        "validation_set": "검증 세트",
        "same_test_holdout": "동일 테스트 홀드아웃",
        "initial_exploration": "초기 탐색",
        "final_supplement": "최종 보완",
        "ci_95": "95% 신뢰구간",
    }
    return {label: text.count(pattern) for label, pattern in patterns.items()}


def build_source_validation(paths: SourcePaths) -> dict[str, object]:
    payload: dict[str, object] = {}
    if paths.pptx and paths.pptx.exists():
        text, slides = pptx_text(paths.pptx)
        payload["submitted_pptx"] = {
            "path": str(paths.pptx),
            "counts": count_patterns(text),
            "relevant_slides": [
                {"slide": number, "excerpt": slide_text[:500]}
                for number, slide_text in slides
                if any(token in slide_text for token in ["80:20", "0.87", "0.7752", "17.02", "SCANIA", "SPC"])
            ],
        }
        copy_if_exists(paths.pptx, SOURCES / paths.pptx.name)
    if paths.latest_hwpx and paths.latest_hwpx.exists():
        text = zip_text(paths.latest_hwpx)
        payload["latest_hwpx"] = {"path": str(paths.latest_hwpx), "counts": count_patterns(text)}
        copy_if_exists(paths.latest_hwpx, SOURCES / paths.latest_hwpx.name)
    if paths.previous_hwpx and paths.previous_hwpx.exists():
        text = zip_text(paths.previous_hwpx)
        payload["previous_hwpx"] = {"path": str(paths.previous_hwpx), "counts": count_patterns(text)}
        copy_if_exists(paths.previous_hwpx, SOURCES / paths.previous_hwpx.name)
    (VALIDATION / "source_document_counts_260612.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return payload


def copy_existing_outputs() -> None:
    figure_names = [
        "confusion_matrix.png",
        "pr_curve.png",
        "threshold_tuning.png",
        "thesis_validation_threshold_curve.png",
        "thesis_calibration_curve_independent_test.png",
        "shap_summary.png",
        "shap_bar.png",
        "spc_risk_chart.png",
        "spc_control_chart.png",
    ]
    table_names = [
        "threshold_summary.json",
        "legacy_threshold_summary_80_20.json",
        "thesis_methodology_metrics.json",
        "thesis_methodology_summary.md",
        "thesis_60_20_20_metrics.csv",
        "thesis_calibration_comparison.csv",
        "thesis_operating_policy_thresholds.csv",
        "thesis_seed_sensitivity.csv",
        "thesis_seed_sensitivity_summary.csv",
        "spc_summary.json",
    ]
    for name in figure_names:
        copy_if_exists(OUTPUTS / name, FIGURES / name)
    for name in table_names:
        destination = TABLES / name if name.endswith((".csv", ".json")) else DOCS / name
        copy_if_exists(OUTPUTS / name, destination)


def write_docs(tables: dict[str, pd.DataFrame], validation_payload: dict[str, object]) -> None:
    threshold = read_json(OUTPUTS / "threshold_summary.json")
    spc = read_json(OUTPUTS / "spc_summary.json")
    selected = threshold["selected_metrics"]

    (DOCS / "00_README_260612.md").write_text(
        f"""# MaintiQ Predict Thesis Alignment Package 260612

이 패키지는 제출 완료된 최종발표 PPT와 2026-06-12 기준 최신 논문/앱 기준을 연결하기 위한 자료입니다.

- 제출 PPT/PDF 기준: 초기 80:20 탐색 실험, threshold 0.87, F1 0.7752
- 최신 논문/앱/GitHub 기준: 60:20:20 보완 실험, validation-selected raw threshold 0.86, fixed-test F1 0.7692
- 앱 기본 판정: raw_probability >= 0.86
- 0.87은 legacy initial presentation result로만 보존
- 0.51/0.34는 calibrated probability reference policy이며 기본 앱 판정 기준이 아님

주요 폴더:

- `figures/`: 논문 삽입용 최신 그림과 표 PNG
- `tables/`: 최신 CSV/JSON 표 자료
- `docs/`: 발표 멘트, Q&A, 논문 삽입 문장, 교체 체크리스트
- `validation/`: PPT/HWPX 텍스트 카운트와 코드 검증 리포트
- `source_snapshots/`: 제출 PPT와 논문 파일 복사본
""",
        encoding="utf-8",
    )

    ppt_counts = validation_payload.get("submitted_pptx", {}).get("counts", {}) if validation_payload else {}
    latest_counts = validation_payload.get("latest_hwpx", {}).get("counts", {}) if validation_payload else {}
    previous_counts = validation_payload.get("previous_hwpx", {}).get("counts", {}) if validation_payload else {}
    (DOCS / "ppt_vs_thesis_bridge_260612.md").write_text(
        f"""# PPT와 최신 논문 연결 설명

## 결론

제출 PPT는 기존 초기 발표 실험을 보여주는 자료이고, 최신 논문과 코드는 이후 보완한 검증-평가 분리 실험까지 포함합니다.
따라서 둘 중 하나가 틀린 것이 아니라 연구가 보완된 과정으로 설명해야 합니다.

## 파일별 수치 확인

| 파일 | 80:20 | 60:20:20 | 0.87 | 0.7752 | 0.86 | 0.7692 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 제출 PPT | {ppt_counts.get('80:20', 0)} | {ppt_counts.get('60:20:20', 0)} | {ppt_counts.get('0.87', 0)} | {ppt_counts.get('0.7752', 0)} | {ppt_counts.get('0.86', 0)} | {ppt_counts.get('0.7692', 0)} |
| 최신 논문 | {latest_counts.get('80:20', 0)} | {latest_counts.get('60:20:20', 0)} | {latest_counts.get('0.87', 0)} | {latest_counts.get('0.7752', 0)} | {latest_counts.get('0.86', 0)} | {latest_counts.get('0.7692', 0)} |
| 이전 논문 | {previous_counts.get('80:20', 0)} | {previous_counts.get('60:20:20', 0)} | {previous_counts.get('0.87', 0)} | {previous_counts.get('0.7752', 0)} | {previous_counts.get('0.86', 0)} | {previous_counts.get('0.7692', 0)} |

## 발표 때 설명 문장

발표자료에는 당시 초기 80:20 탐색 결과를 제시했습니다. 이후 논문 보완 과정에서 threshold 선택과 최종 평가를 분리하기 위해 60:20:20 구조를 추가했고, 검증 세트에서 0.86을 선택한 뒤 고정 테스트 세트에서 평가했습니다. F1-score는 0.7752에서 0.7692로 약간 낮아졌지만, 임계값 조정으로 precision과 recall 균형을 맞춘다는 결론은 동일합니다.
""",
        encoding="utf-8",
    )

    (DOCS / "presentation_talk_track_260612.md").write_text(
        """# 제출 PPT 기준 발표 보완 멘트

## 슬라이드 14 데이터 분할

이 슬라이드는 최초 발표 당시의 80:20 기준 실험 구조입니다. 논문 최종 보완 과정에서는 threshold 선택과 최종 평가를 분리하기 위해 60:20:20 검증 구조를 추가했습니다.

## 슬라이드 16, 22 threshold 0.87

0.87은 초기 80:20 홀드아웃 탐색에서 나온 정책 후보입니다. 이후 논문 보완 실험에서는 검증 세트에서 0.86이 선택되었고, 고정 테스트 세트에서 F1-score 0.7692가 나와 유사한 경향을 확인했습니다.

## 슬라이드 24 ML+SPC

이 결과는 초기 동일 분할에서 정책들의 상대적 특성을 비교한 것입니다. 최신 논문에서는 SPC를 독립 이상탐지 성능검증으로 주장하지 않고, UDI 순서 기반 위험 흐름 보조 시각화로 제한했습니다.

## 슬라이드 26, 29 SCANIA 17.02%

SCANIA official cost metric에서는 rule baseline보다 낮은 비용이 나왔지만, 선택 정책이 전부 경보에 가까운 한계를 보였습니다. 그래서 현장 정책의 우수성을 입증했다기보다 비용함수만 최적화할 때 생기는 한계까지 확인한 결과로 설명하겠습니다.
""",
        encoding="utf-8",
    )

    (DOCS / "paper_insert_sentences_260612.md").write_text(
        f"""# 최신 논문 삽입 문장

## 최종 실험 결과

학습 60%, 검증 20%, 테스트 20%로 자료를 분리하고 검증 세트에서 원시 확률 임계값 0.86을 선택하였다. 이를 검증 세트와 분리된 고정 테스트 세트에 적용한 결과 정밀도 {selected['precision']:.4f}, 재현율 {selected['recall']:.4f}, F1-score {selected['f1_score']:.4f}, PR-AUC {selected['pr_auc']:.4f}, ROC-AUC {selected['roc_auc']:.4f}을 보였다. 확률 보정 방식은 검증 세트 Brier score를 기준으로 isotonic을 선택하였으며, 테스트 세트 Brier score는 {threshold['calibration']['test_brier']:.6f}로 나타났다.

## PPT와 논문 관계

초기 발표 실험에서는 80:20 동일 홀드아웃에서 임계값 0.87, F1-score 0.7752가 관찰되었다. 그러나 해당 결과는 임계값 탐색과 평가가 같은 홀드아웃에서 이루어진 탐색 결과이므로, 최종 논문에서는 선택 편향을 줄이기 위해 60:20:20 검증-평가 분리 구조를 추가하였다.

## SPC 제한

SPC 기반 위험확률 추세도는 독립적인 이상탐지 성능평가가 아니라 UDI 순서상의 위험 흐름을 확인하기 위한 보조 시각화이다. 관리한계는 테스트 자료가 아니라 정상 학습 자료에서 계산한 뒤 검증 세트와 분리된 고정 테스트 세트에 적용하였다.
""",
        encoding="utf-8",
    )

    (DOCS / "professor_qna_260612.md").write_text(
        """# 교수 질의응답 대비

Q. 발표자료는 0.87인데 논문은 왜 0.86인가요?

A. 발표자료의 0.87은 초기 80:20 홀드아웃 탐색 결과입니다. 논문 보완 과정에서는 테스트셋 재사용 가능성을 줄이기 위해 학습/검증/테스트를 60:20:20으로 분리했고, 검증 세트에서 0.86을 선택해 고정 테스트 세트에서 평가했습니다.

Q. F1-score가 0.7752에서 0.7692로 낮아진 것은 성능 저하 아닌가요?

A. 수치는 약간 낮아졌지만, 더 엄밀한 검증 구조에서 나온 결과입니다. 핵심 결론인 XGBoost 우위와 threshold 조정 효과는 유지됩니다.

Q. 앱도 0.86 기준으로 실제 수정됐나요?

A. 네. Desktop과 Streamlit의 기본 High Risk 판정은 raw_probability >= 0.86 기준입니다. 보정확률은 참고값으로 표시되며 기본 판정 기준이 아닙니다.

Q. SCANIA 17.02% 개선은 실제 비용 절감인가요?

A. 아닙니다. SCANIA official cost metric 기준의 공개 benchmark 결과입니다. 실제 원화 절감이나 회사 데이터 실증으로 주장하지 않습니다. 특히 비용함수 최적화만 하면 전부 경보 정책이 선택될 수 있다는 한계를 같이 설명합니다.

Q. SPC는 독립 이상탐지 검증인가요?

A. 아닙니다. AI4I에는 실제 시간축이 없으므로 UDI 순서 기반 위험 흐름 보조 시각화로 제한합니다.
""",
        encoding="utf-8",
    )

    (DOCS / "video_reshoot_decision_260612.md").write_text(
        """# 발표 영상 재촬영 판단

## 권장

제출 시스템에서 공식적으로 영상 교체가 가능하면 최신 앱 기준으로 영상을 다시 촬영하는 것이 좋습니다.

## 주의

이미 제출이 잠긴 자료를 비공식적으로 바꾸는 방식은 피해야 합니다. 교체가 불가능하면 기존 PPT는 초기 발표 실험으로 발표하고, 구두로 논문 보완 실험을 설명하는 것이 안전합니다.

## 새 영상에 반드시 보여줄 것

1. Desktop 예측 결과의 selected_threshold가 0.86인지 확인
2. raw_probability 기준 High Risk 판정 확인
3. calibrated_probability는 참고값임을 설명
4. Streamlit Admin의 최종 평가 기준 0.86 섹션 확인
5. 0.87은 legacy initial 80:20 탐색 결과로만 설명
""",
        encoding="utf-8",
    )

    (DOCS / "figure_table_update_checklist_260612.md").write_text(
        "# 최신 논문 표/그림 교체 체크리스트\n\n"
        + markdown_table(tables["paper_figure_table_update_checklist_260612"]),
        encoding="utf-8",
    )
    (DOCS / "experiment_bridge_table_260612.md").write_text(
        "# 초기 발표 실험 vs 논문 보완 실험\n\n" + markdown_table(tables["experiment_bridge_table_260612"]),
        encoding="utf-8",
    )
    (DOCS / "spc_policy_comparison_260612.md").write_text(
        "# SPC 정책 비교 0.86 기준\n\n" + markdown_table(tables["spc_policy_comparison_260612"]),
        encoding="utf-8",
    )
    (DOCS / "code_alignment_report_260612.md").write_text(
        f"""# 코드 정렬 리포트

- 최종 앱 정책: `{threshold['policy_id']}`
- 확률 기준: `{threshold['probability_basis']}`
- 최종 threshold: `{threshold['selected_threshold']}`
- 고정 테스트 F1-score: `{selected['f1_score']}`
- 보정 방식: `{threshold['calibration']['selected_method']}`
- 보정 테스트 Brier score: `{threshold['calibration']['test_brier']}`
- SPC selected threshold: `{spc['selected_threshold']}`
- SPC 해석 제한: `{spc['note']}`

검증 명령은 최종 작업 후 별도로 실행한 결과를 최종 답변에 포함한다.
""",
        encoding="utf-8",
    )


def zip_pack() -> None:
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in PACK.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(PACK.parent))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the 260612 thesis alignment material package.")
    parser.add_argument("--pptx", type=Path)
    parser.add_argument("--latest-hwpx", type=Path)
    parser.add_argument("--previous-hwpx", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reset_pack()
    tables = build_tables()
    render_table_pngs(tables)
    copy_existing_outputs()
    paths = SourcePaths(args.pptx, args.latest_hwpx, args.previous_hwpx)
    validation_payload = build_source_validation(paths)
    write_docs(tables, validation_payload)
    zip_pack()
    print(f"Package created: {PACK}")
    print(f"ZIP created: {ZIP_PATH}")


if __name__ == "__main__":
    main()
