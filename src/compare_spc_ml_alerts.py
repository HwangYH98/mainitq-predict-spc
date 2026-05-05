from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"
SPC_TIMESERIES_PATH = OUTPUT_DIR / "spc_timeseries.csv"
COMPARISON_CSV = OUTPUT_DIR / "spc_vs_ml_comparison.csv"
SUMMARY_PATH = OUTPUT_DIR / "spc_vs_ml_summary.md"
SUMMARY_JSON = OUTPUT_DIR / "spc_vs_ml_comparison.json"


def alert_metrics(y_true: pd.Series, y_pred: pd.Series) -> dict:
    """Calculate alert-level metrics against actual machine failure labels."""
    predicted = y_pred.astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
    return {
        "precision": round(float(precision_score(y_true, predicted, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, predicted, zero_division=0)), 4),
        "f1_score": round(float(f1_score(y_true, predicted, zero_division=0)), 4),
        "alert_count": int(fp + tp),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
        "true_negative": int(tn),
    }


def build_comparison(spc: pd.DataFrame) -> pd.DataFrame:
    """Compare SPC-style alerts and ML probability alerts on the same rows."""
    y_true = spc["actual_machine_failure"].astype(int)
    rows = []
    strategies = [
        {
            "strategy_id": "spc_only_torque_control_limit",
            "display_name": "SPC-only torque control limit",
            "description": "Single-sensor SPC-style torque control-limit rule.",
            "series": spc["torque_beyond_control_limit"].astype(bool),
        },
        {
            "strategy_id": "ml_selected_threshold",
            "display_name": "ML selected threshold",
            "description": "XGBoost probability crossing the F1-selected threshold.",
            "series": (spc["xgboost_probability"] >= spc["selected_threshold"]).astype(bool),
        },
        {
            "strategy_id": "ml_spc_combined",
            "display_name": "ML + Predictive SPC combined",
            "description": "Risk probability threshold or risk control-limit alert.",
            "series": spc["spc_risk_alert"].astype(bool),
        },
    ]

    for strategy in strategies:
        metrics = alert_metrics(y_true, strategy["series"])
        metrics.update(
            {
                "strategy_id": strategy["strategy_id"],
                "display_name": strategy["display_name"],
                "description": strategy["description"],
                "actual_failure_count": int(y_true.sum()),
                "total_rows": int(len(spc)),
            }
        )
        rows.append(metrics)

    return pd.DataFrame(rows)[
        [
            "strategy_id",
            "display_name",
            "description",
            "precision",
            "recall",
            "f1_score",
            "alert_count",
            "false_positive",
            "false_negative",
            "true_positive",
            "true_negative",
            "actual_failure_count",
            "total_rows",
        ]
    ]


def presentation_conclusion(comparison: pd.DataFrame) -> str:
    """Return a cautious comparison statement."""
    best_f1 = comparison.sort_values(["f1_score", "recall"], ascending=[False, False]).iloc[0]
    spc_only = comparison.loc[comparison["strategy_id"] == "spc_only_torque_control_limit"].iloc[0]
    combined = comparison.loc[comparison["strategy_id"] == "ml_spc_combined"].iloc[0]
    return (
        f"F1-score 기준 최고 alert 전략은 `{best_f1['display_name']}` "
        f"({best_f1['f1_score']:.4f})입니다. 단일 torque SPC rule은 "
        f"{int(spc_only['alert_count'])}개 alert만 발생시켜 recall이 "
        f"{spc_only['recall']:.4f}였고, ML+SPC combined는 "
        f"{int(combined['alert_count'])}개 alert와 recall {combined['recall']:.4f}를 보였습니다. "
        "이 결과는 실제 비용 절감 실증이 아니라, rule-based SPC-only와 ML probability 기반 alert의 "
        "탐지 특성 차이를 보여주는 로컬 비교입니다."
    )


def write_summary(comparison: pd.DataFrame, output_path: Path) -> None:
    """Write a Markdown summary for dashboard and presentation use."""
    rows = [
        "# SPC-only vs ML+SPC Alert Comparison",
        "",
        "## Scope",
        "",
        "This comparison uses AI4I UDI-order playback rows. It is not a live factory stream and does not prove real maintenance cost reduction.",
        "",
        "## Result Table",
        "",
        "| Strategy | Precision | Recall | F1 | Alerts | FP | FN | TP |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in comparison.iterrows():
        rows.append(
            f"| {row['display_name']} | {row['precision']:.4f} | {row['recall']:.4f} | "
            f"{row['f1_score']:.4f} | {int(row['alert_count'])} | "
            f"{int(row['false_positive'])} | {int(row['false_negative'])} | "
            f"{int(row['true_positive'])} |"
        )
    rows.extend(
        [
            "",
            "## Presentation-Safe Conclusion",
            "",
            presentation_conclusion(comparison),
            "",
            "## Guardrail",
            "",
            "Use this as an alert-strategy comparison, not as a claim that a real factory reduced downtime or maintenance cost.",
            "",
        ]
    )
    output_path.write_text("\n".join(rows), encoding="utf-8")


def main() -> None:
    """Run the SPC-only vs ML+SPC alert comparison."""
    if not SPC_TIMESERIES_PATH.exists():
        raise FileNotFoundError(
            f"Missing {SPC_TIMESERIES_PATH}. Run src\\predictive_spc.py first."
        )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    spc = pd.read_csv(SPC_TIMESERIES_PATH)
    comparison = build_comparison(spc)

    comparison.to_csv(COMPARISON_CSV, index=False, encoding="utf-8-sig")
    SUMMARY_JSON.write_text(
        json.dumps(
            {
                "rows": comparison.to_dict(orient="records"),
                "presentation_safe_conclusion": presentation_conclusion(comparison),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_summary(comparison, SUMMARY_PATH)

    print("SPC vs ML alert comparison finished successfully.")
    print(f"comparison_csv: {COMPARISON_CSV}")
    print(f"comparison_json: {SUMMARY_JSON}")
    print(f"summary: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
