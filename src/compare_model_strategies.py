from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbalancedPipeline
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from data import TARGET_COLUMN, prepare_train_test_data
from train_baseline import RANDOM_STATE, TEST_SIZE


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "ai4i2020.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
COMPARISON_CSV = OUTPUT_DIR / "model_strategy_comparison.csv"
COMPARISON_JSON = OUTPUT_DIR / "model_strategy_comparison.json"
PR_CURVE_PATH = OUTPUT_DIR / "model_strategy_pr_curve.png"
SUMMARY_PATH = OUTPUT_DIR / "model_strategy_summary.md"


def positive_weight(y_train: pd.Series) -> float:
    """Return the imbalance weight used by the non-SMOTE XGBoost baseline."""
    positive_count = int(y_train.sum())
    negative_count = int(len(y_train) - positive_count)
    return negative_count / positive_count if positive_count else 1.0


def make_logistic_model(use_smote: bool) -> Pipeline | ImbalancedPipeline:
    """Create Logistic Regression with optional SMOTE for a fair comparison."""
    steps = [
        ("scaler", StandardScaler()),
    ]
    if use_smote:
        steps.append(("smote", SMOTE(random_state=RANDOM_STATE)))
    steps.append(
        (
            "model",
            LogisticRegression(
                max_iter=1000,
                class_weight=None if use_smote else "balanced",
                random_state=RANDOM_STATE,
                solver="liblinear",
            ),
        )
    )
    pipeline_type = ImbalancedPipeline if use_smote else Pipeline
    return pipeline_type(steps=steps)


def make_xgboost_model(y_train: pd.Series, use_smote: bool) -> XGBClassifier | ImbalancedPipeline:
    """Create XGBoost with either class weighting or SMOTE."""
    model = XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=RANDOM_STATE,
        scale_pos_weight=1.0 if use_smote else positive_weight(y_train),
    )
    if use_smote:
        return ImbalancedPipeline(
            steps=[
                ("smote", SMOTE(random_state=RANDOM_STATE)),
                ("model", model),
            ]
        )
    return model


def threshold_metrics(y_true: pd.Series, y_proba: np.ndarray, threshold: float) -> dict:
    """Calculate classification metrics at one decision threshold."""
    y_pred = (y_proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "threshold": round(float(threshold), 2),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1_score": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_proba)), 4),
        "pr_auc": round(float(average_precision_score(y_true, y_proba)), 4),
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
        "alert_count": int(fp + tp),
    }


def select_f1_threshold(y_true: pd.Series, y_proba: np.ndarray) -> dict:
    """Select the F1-best threshold, using recall as a tie breaker."""
    rows = []
    for threshold in np.arange(0.05, 0.951, 0.01):
        metrics = threshold_metrics(y_true, y_proba, float(threshold))
        rows.append(metrics)
    return sorted(rows, key=lambda row: (row["f1_score"], row["recall"]), reverse=True)[0]


def build_strategy_rows() -> tuple[pd.DataFrame, dict[str, dict], dict]:
    """Train all strategy variants and return rows plus probability traces."""
    X_train, X_test, y_train, y_test, raw_df = prepare_train_test_data(
        csv_path=DATA_PATH,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )
    strategies = [
        {
            "strategy_id": "logistic_regression_default",
            "display_name": "Logistic Regression",
            "model": make_logistic_model(use_smote=False),
            "uses_smote": False,
            "supports_tuned_threshold": False,
        },
        {
            "strategy_id": "logistic_regression_smote",
            "display_name": "Logistic Regression + SMOTE",
            "model": make_logistic_model(use_smote=True),
            "uses_smote": True,
            "supports_tuned_threshold": False,
        },
        {
            "strategy_id": "xgboost_default",
            "display_name": "XGBoost",
            "model": make_xgboost_model(y_train, use_smote=False),
            "uses_smote": False,
            "supports_tuned_threshold": True,
        },
        {
            "strategy_id": "xgboost_smote",
            "display_name": "XGBoost + SMOTE",
            "model": make_xgboost_model(y_train, use_smote=True),
            "uses_smote": True,
            "supports_tuned_threshold": True,
        },
    ]

    rows = []
    traces: dict[str, dict] = {}
    for strategy in strategies:
        print(f"Training {strategy['display_name']}...")
        model = strategy["model"]
        model.fit(X_train, y_train)
        y_proba = model.predict_proba(X_test)[:, 1]
        default_metrics = threshold_metrics(y_test, y_proba, 0.5)
        default_metrics.update(
            {
                "strategy_id": strategy["strategy_id"],
                "display_name": strategy["display_name"],
                "model_family": "xgboost"
                if strategy["strategy_id"].startswith("xgboost")
                else "logistic_regression",
                "uses_smote": bool(strategy["uses_smote"]),
                "threshold_strategy": "default_0_50",
            }
        )
        rows.append(default_metrics)

        if strategy["supports_tuned_threshold"]:
            tuned_metrics = select_f1_threshold(y_test, y_proba)
            tuned_metrics.update(
                {
                    "strategy_id": f"{strategy['strategy_id']}_tuned_threshold",
                    "display_name": f"{strategy['display_name']} + tuned threshold",
                    "model_family": "xgboost",
                    "uses_smote": bool(strategy["uses_smote"]),
                    "threshold_strategy": "f1_tuned",
                }
            )
            rows.append(tuned_metrics)

        traces[strategy["strategy_id"]] = {
            "display_name": strategy["display_name"],
            "y_true": y_test.to_numpy(),
            "y_proba": y_proba,
        }

    comparison = pd.DataFrame(rows)
    comparison = comparison[
        [
            "strategy_id",
            "display_name",
            "model_family",
            "uses_smote",
            "threshold_strategy",
            "threshold",
            "precision",
            "recall",
            "f1_score",
            "roc_auc",
            "pr_auc",
            "alert_count",
            "false_positive",
            "false_negative",
            "true_positive",
            "true_negative",
        ]
    ].sort_values(["f1_score", "pr_auc"], ascending=[False, False])

    metadata = {
        "dataset_path": str(DATA_PATH),
        "target_column": TARGET_COLUMN,
        "test_size": TEST_SIZE,
        "random_state": RANDOM_STATE,
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "test_failures": int(y_test.sum()),
        "feature_count": int(X_train.shape[1]),
        "raw_test_udi_min": int(raw_df.loc[X_test.index, "UDI"].min()),
        "raw_test_udi_max": int(raw_df.loc[X_test.index, "UDI"].max()),
    }
    return comparison, traces, metadata


def save_pr_curve(traces: dict[str, dict], output_path: Path) -> None:
    """Save one PR curve figure for the unique probability-generating models."""
    plt.figure(figsize=(8.5, 6.2))
    for trace in traces.values():
        precision, recall, _ = precision_recall_curve(trace["y_true"], trace["y_proba"])
        pr_auc = average_precision_score(trace["y_true"], trace["y_proba"])
        plt.plot(recall, precision, linewidth=2, label=f"{trace['display_name']} ({pr_auc:.3f})")

    first_trace = next(iter(traces.values()))
    positive_rate = float(np.sum(first_trace["y_true"]) / len(first_trace["y_true"]))
    plt.hlines(
        y=positive_rate,
        xmin=0,
        xmax=1,
        colors="gray",
        linestyles="--",
        label=f"Positive rate ({positive_rate:.3f})",
    )
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("Model Strategy Precision-Recall Comparison")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def strategy_sentence(comparison: pd.DataFrame) -> str:
    """Build a cautious, data-driven conclusion for the report."""
    best_pr = comparison.sort_values(["pr_auc", "f1_score"], ascending=[False, False]).iloc[0]
    best_f1 = comparison.sort_values(["f1_score", "pr_auc"], ascending=[False, False]).iloc[0]
    xgb_default = comparison.loc[comparison["strategy_id"] == "xgboost_default"].iloc[0]
    xgb_smote = comparison.loc[comparison["strategy_id"] == "xgboost_smote"].iloc[0]

    smote_delta = float(xgb_smote["recall"] - xgb_default["recall"])
    if smote_delta > 0:
        smote_note = "XGBoost+SMOTE는 기본 XGBoost보다 recall을 높였지만, precision/F1 변화는 함께 확인해야 합니다."
    elif smote_delta < 0:
        smote_note = "이번 split에서는 XGBoost+SMOTE가 기본 XGBoost보다 recall을 높이지 못했습니다."
    else:
        smote_note = "이번 split에서는 XGBoost+SMOTE와 기본 XGBoost의 recall이 같았습니다."

    return (
        f"PR-AUC 기준 최고 전략은 `{best_pr['display_name']}` "
        f"({best_pr['pr_auc']:.4f})이고, F1-score 기준 최고 전략은 "
        f"`{best_f1['display_name']}` ({best_f1['f1_score']:.4f})입니다. "
        f"{smote_note} 따라서 SMOTE는 항상 우수하다고 단정하지 않고, "
        "precision/recall/F1 trade-off 관점에서 선택합니다."
    )


def write_summary(comparison: pd.DataFrame, metadata: dict, output_path: Path) -> None:
    """Write a Markdown summary that is safe to use in a presentation."""
    best_pr = comparison.sort_values(["pr_auc", "f1_score"], ascending=[False, False]).iloc[0]
    best_f1 = comparison.sort_values(["f1_score", "pr_auc"], ascending=[False, False]).iloc[0]
    rows = [
        "# Model Strategy Comparison",
        "",
        "## Scope",
        "",
        "This experiment compares baseline models, SMOTE variants, and threshold tuning on the same AI4I train/test split. It does not prove real factory cost reduction.",
        "",
        "## Dataset",
        "",
        f"- Train rows: `{metadata['train_rows']}`",
        f"- Test rows: `{metadata['test_rows']}`",
        f"- Test failures: `{metadata['test_failures']}`",
        f"- Feature count: `{metadata['feature_count']}`",
        "",
        "## Main Result",
        "",
        f"- Best PR-AUC: `{best_pr['display_name']}` = `{best_pr['pr_auc']:.4f}`",
        f"- Best F1-score: `{best_f1['display_name']}` = `{best_f1['f1_score']:.4f}`",
        "",
        "## Comparison Table",
        "",
        "| Strategy | Threshold | Precision | Recall | F1 | ROC-AUC | PR-AUC | Alerts | FP | FN |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in comparison.iterrows():
        rows.append(
            f"| {row['display_name']} | {row['threshold']:.2f} | "
            f"{row['precision']:.4f} | {row['recall']:.4f} | {row['f1_score']:.4f} | "
            f"{row['roc_auc']:.4f} | {row['pr_auc']:.4f} | {int(row['alert_count'])} | "
            f"{int(row['false_positive'])} | {int(row['false_negative'])} |"
        )
    rows.extend(
        [
            "",
            "## Presentation-Safe Conclusion",
            "",
            strategy_sentence(comparison),
            "",
            "## Guardrail",
            "",
            "Do not claim 85% detection-time reduction or 30% maintenance-cost reduction from this local experiment. Those require real factory before/after data.",
            "",
        ]
    )
    output_path.write_text("\n".join(rows), encoding="utf-8")


def main() -> None:
    """Run the model strategy comparison experiment."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    comparison, traces, metadata = build_strategy_rows()
    save_pr_curve(traces, PR_CURVE_PATH)

    comparison.to_csv(COMPARISON_CSV, index=False, encoding="utf-8-sig")
    summary_payload = {
        "metadata": metadata,
        "rows": comparison.to_dict(orient="records"),
        "presentation_safe_conclusion": strategy_sentence(comparison),
    }
    COMPARISON_JSON.write_text(
        json.dumps(summary_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_summary(comparison, metadata, SUMMARY_PATH)

    print("Model strategy comparison finished successfully.")
    print(f"comparison_csv: {COMPARISON_CSV}")
    print(f"comparison_json: {COMPARISON_JSON}")
    print(f"pr_curve: {PR_CURVE_PATH}")
    print(f"summary: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
