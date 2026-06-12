from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from experiment_run import DEFAULT_EXPERIMENT_ROOT, create_experiment_run, record_current_process
from scania_official_cost_validation import (
    CLASSES,
    DEFAULT_DATA_DIR,
    OFFICIAL_COST_MATRIX,
    RANDOM_STATE,
    ScaniaOfficialData,
    evaluate_strategy,
    load_scania_official_data,
    official_cost,
    prepare_features,
    probability_matrix,
    rule_based_predictions,
    spc_style_predictions,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_ALERT_CAPS = (0.05, 0.10, 0.20, 0.30)
DEFAULT_RUN_PREFIX = "scania-policy"


def constrained_expected_cost_predictions(
    probability_by_class: np.ndarray,
    alert_cap: float,
    *,
    cost_matrix: np.ndarray = OFFICIAL_COST_MATRIX,
) -> np.ndarray:
    """Choose alert rows by expected-cost benefit while respecting an alert-rate cap."""
    if not 0 <= alert_cap <= 1:
        raise ValueError("alert_cap must be between 0 and 1.")

    probabilities = np.asarray(probability_by_class, dtype=float)
    expected_cost = probabilities @ np.asarray(cost_matrix, dtype=float)
    no_alert_cost = expected_cost[:, 0]
    alert_cost = expected_cost[:, 1:]
    best_alert_class = alert_cost.argmin(axis=1).astype(int) + 1
    best_alert_cost = alert_cost.min(axis=1)
    alert_benefit = no_alert_cost - best_alert_cost

    max_alerts = int(np.floor(alert_cap * len(probabilities)))
    predictions = np.zeros(len(probabilities), dtype=int)
    if max_alerts <= 0:
        return predictions

    eligible = np.flatnonzero(alert_benefit > 0)
    if len(eligible) == 0:
        return predictions

    order = eligible[np.argsort(-alert_benefit[eligible], kind="mergesort")]
    selected = order[:max_alerts]
    predictions[selected] = best_alert_class[selected]
    return predictions


def unconstrained_expected_cost_predictions(
    probability_by_class: np.ndarray,
    *,
    cost_matrix: np.ndarray = OFFICIAL_COST_MATRIX,
) -> np.ndarray:
    """Return the old expected-cost policy, preserved as an unconstrained baseline."""
    expected_cost = np.asarray(probability_by_class, dtype=float) @ np.asarray(cost_matrix, dtype=float)
    return expected_cost.argmin(axis=1).astype(int)


def _fit_logistic_model(X_train: pd.DataFrame, y_train: pd.Series) -> Pipeline:
    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )
    model.fit(X_train, y_train)
    return model


def _fit_xgboost_model(X_train: pd.DataFrame, y_train: pd.Series, random_state: int) -> XGBClassifier:
    sample_weight = compute_sample_weight("balanced", y_train)
    model = XGBClassifier(
        n_estimators=220,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        objective="multi:softprob",
        num_class=5,
        eval_metric="mlogloss",
        tree_method="hist",
        random_state=random_state,
        n_jobs=1,
    )
    model.fit(X_train, y_train, sample_weight=sample_weight)
    return model


def _predict_class_probabilities(model: Any, X_frame: pd.DataFrame) -> np.ndarray:
    return probability_matrix(model.classes_, model.predict_proba(X_frame))


def select_constrained_policy_from_training(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    *,
    candidate_alert_caps: tuple[float, ...] = CANDIDATE_ALERT_CAPS,
    selection_folds: int = 3,
    random_state: int = RANDOM_STATE,
) -> tuple[float, pd.DataFrame, pd.DataFrame]:
    """
    Select the constrained policy only with training labels.

    This function intentionally accepts no official validation labels. Tests lock
    this contract so the official validation set cannot be used for policy choice.
    """
    if selection_folds < 2:
        raise ValueError("selection_folds must be at least 2.")
    if len(set(y_train.astype(int))) < len(CLASSES):
        raise ValueError("Training labels must include all official classes 0~4 for selection.")

    splitter = StratifiedKFold(
        n_splits=selection_folds,
        shuffle=True,
        random_state=random_state,
    )
    fold_rows = []
    for fold, (inner_train_idx, inner_valid_idx) in enumerate(splitter.split(X_train, y_train), start=1):
        X_inner_train = X_train.iloc[inner_train_idx]
        y_inner_train = y_train.iloc[inner_train_idx]
        X_inner_valid = X_train.iloc[inner_valid_idx]
        y_inner_valid = y_train.iloc[inner_valid_idx].reset_index(drop=True)

        model = _fit_xgboost_model(X_inner_train, y_inner_train, random_state=random_state + fold)
        probabilities = _predict_class_probabilities(model, X_inner_valid)
        no_alert_cost = official_cost(y_inner_valid, np.zeros(len(y_inner_valid), dtype=int))
        rule_cost = no_alert_cost

        for cap in candidate_alert_caps:
            predictions = constrained_expected_cost_predictions(probabilities, cap)
            row = evaluate_strategy(
                f"candidate_cap_{int(cap * 100):02d}",
                f"Training-fold constrained expected cost cap {cap:.0%}",
                y_inner_valid,
                predictions,
                no_alert_cost,
                rule_cost,
            )
            row.update(
                {
                    "selection_fold": fold,
                    "candidate_alert_cap": cap,
                    "selection_source": "training_fold_only",
                    "inner_train_rows": int(len(y_inner_train)),
                    "inner_validation_rows": int(len(y_inner_valid)),
                }
            )
            fold_rows.append(row)

    selection_folds_df = pd.DataFrame(fold_rows)
    candidate_summary = (
        selection_folds_df.groupby("candidate_alert_cap", as_index=False)
        .agg(
            mean_official_cost=("official_cost", "mean"),
            std_official_cost=("official_cost", "std"),
            mean_macro_f1=("macro_f1", "mean"),
            mean_balanced_accuracy=("balanced_accuracy", "mean"),
            mean_alert_like_rate=("alert_like_rate", "mean"),
        )
        .sort_values(
            ["mean_official_cost", "mean_alert_like_rate", "mean_macro_f1"],
            ascending=[True, True, False],
        )
        .reset_index(drop=True)
    )
    selected_cap = float(candidate_summary.iloc[0]["candidate_alert_cap"])
    candidate_summary["selected"] = candidate_summary["candidate_alert_cap"].eq(selected_cap)
    return selected_cap, selection_folds_df, candidate_summary


def add_pareto_columns(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """Mark policies dominated on cost, alert burden, Macro-F1, and balanced accuracy."""
    frame = metrics_df.copy().reset_index(drop=True)
    dominated = []
    for index, row in frame.iterrows():
        is_dominated = False
        for other_index, other in frame.iterrows():
            if index == other_index:
                continue
            no_worse = (
                other["official_cost"] <= row["official_cost"]
                and other["alert_like_rate"] <= row["alert_like_rate"]
                and other["macro_f1"] >= row["macro_f1"]
                and other["balanced_accuracy"] >= row["balanced_accuracy"]
            )
            strictly_better = (
                other["official_cost"] < row["official_cost"]
                or other["alert_like_rate"] < row["alert_like_rate"]
                or other["macro_f1"] > row["macro_f1"]
                or other["balanced_accuracy"] > row["balanced_accuracy"]
            )
            if no_worse and strictly_better:
                is_dominated = True
                break
        dominated.append(is_dominated)
    frame["pareto_dominated"] = dominated
    frame["pareto_front"] = [not value for value in dominated]
    return frame


def train_select_and_evaluate(
    data: ScaniaOfficialData,
    *,
    candidate_alert_caps: tuple[float, ...] = CANDIDATE_ALERT_CAPS,
    selection_folds: int = 3,
    random_state: int = RANDOM_STATE,
) -> dict[str, Any]:
    X_train, X_validation, y_train, y_validation, feature_columns, raw_feature_columns, categorical_columns = prepare_features(
        data.train,
        data.validation,
    )

    selected_cap, selection_folds_df, candidate_summary = select_constrained_policy_from_training(
        X_train,
        y_train,
        candidate_alert_caps=candidate_alert_caps,
        selection_folds=selection_folds,
        random_state=random_state,
    )

    no_alert_pred = np.zeros(len(y_validation), dtype=int)
    all_alert_pred = np.full(len(y_validation), max(CLASSES), dtype=int)
    rule_pred, rule_feature = rule_based_predictions(X_train, X_validation, y_train)
    spc_pred, spc_feature = spc_style_predictions(X_train, X_validation, y_train)

    logistic = _fit_logistic_model(X_train, y_train)
    logistic_pred = logistic.predict(X_validation).astype(int)

    xgb = _fit_xgboost_model(X_train, y_train, random_state=random_state)
    xgb_prob = _predict_class_probabilities(xgb, X_validation)
    xgb_argmax_pred = xgb_prob.argmax(axis=1).astype(int)
    unconstrained_pred = unconstrained_expected_cost_predictions(xgb_prob)
    constrained_pred = constrained_expected_cost_predictions(xgb_prob, selected_cap)

    no_alert_cost = official_cost(y_validation, no_alert_pred)
    rule_cost = official_cost(y_validation, rule_pred)
    strategies = [
        ("no_alert_all_0", "No-alert all class 0", no_alert_pred),
        ("all_alert_class_4_failure_baseline", "All-alert class 4 failure baseline", all_alert_pred),
        ("rule_based_threshold", f"Rule-based threshold ({rule_feature})", rule_pred),
        ("spc_style_baseline", f"SPC-style baseline ({spc_feature})", spc_pred),
        ("logistic_multiclass", "Logistic Regression multiclass", logistic_pred),
        ("xgboost_multiclass_argmax", "XGBoost multiclass argmax", xgb_argmax_pred),
        (
            "xgboost_cost_optimized",
            "XGBoost unconstrained expected cost (preserved baseline)",
            unconstrained_pred,
        ),
        (
            "xgboost_constrained_expected_cost",
            f"XGBoost constrained expected cost cap {selected_cap:.0%}",
            constrained_pred,
        ),
    ]
    rows = [
        evaluate_strategy(strategy_id, display_name, y_validation, y_pred, no_alert_cost, rule_cost)
        for strategy_id, display_name, y_pred in strategies
    ]
    metrics_df = add_pareto_columns(pd.DataFrame(rows).sort_values("official_cost", ascending=True))

    predictions_df = data.validation[["vehicle_id", "time_step", "class_label"]].copy()
    predictions_df = predictions_df.rename(columns={"class_label": "actual_class"})
    for strategy_id, _, y_pred in strategies:
        predictions_df[f"{strategy_id}_predicted_class"] = y_pred
    for class_id in CLASSES:
        predictions_df[f"xgboost_probability_class_{class_id}"] = xgb_prob[:, class_id]
    expected_cost = xgb_prob @ OFFICIAL_COST_MATRIX
    predictions_df["xgboost_unconstrained_expected_cost_min"] = expected_cost.min(axis=1)
    predictions_df["selected_constrained_alert_cap"] = selected_cap

    metadata = {
        "source_note": data.source_note,
        "train_rows": int(len(data.train)),
        "validation_rows": int(len(data.validation)),
        "feature_count": int(len(feature_columns)),
        "raw_feature_columns": raw_feature_columns,
        "categorical_columns": categorical_columns,
        "train_class_distribution": {
            str(class_id): int((data.train["class_label"] == class_id).sum()) for class_id in CLASSES
        },
        "validation_class_distribution": {
            str(class_id): int((data.validation["class_label"] == class_id).sum()) for class_id in CLASSES
        },
        "candidate_alert_caps": list(candidate_alert_caps),
        "selected_alert_cap": selected_cap,
        "selection_rule": (
            "Select the lowest mean official cost across training-only folds; break ties by lower "
            "alert-like rate and then higher Macro-F1."
        ),
        "official_validation_policy": "Official validation labels are used only after policy selection.",
        "official_cost_matrix": OFFICIAL_COST_MATRIX.astype(int).tolist(),
    }

    return {
        "metrics": metrics_df,
        "predictions": predictions_df,
        "selection_folds": selection_folds_df,
        "candidate_summary": candidate_summary,
        "metadata": metadata,
    }


def write_charts(run_dir: Path, metrics_df: pd.DataFrame) -> list[Path]:
    figures = run_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    cost_alert_path = figures / "scania_cost_vs_alert_rate.png"
    cost_f1_path = figures / "scania_cost_vs_macro_f1.png"

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(metrics_df["alert_like_rate"], metrics_df["official_cost"], color="#0f766e")
    for _, row in metrics_df.iterrows():
        ax.annotate(row["strategy_id"], (row["alert_like_rate"], row["official_cost"]), fontsize=7)
    ax.set_xlabel("Alert-like rate")
    ax.set_ylabel("Official cost")
    ax.set_title("SCANIA Cost vs Alert Burden")
    fig.tight_layout()
    fig.savefig(cost_alert_path, dpi=220, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(metrics_df["macro_f1"], metrics_df["official_cost"], color="#7c3aed")
    for _, row in metrics_df.iterrows():
        ax.annotate(row["strategy_id"], (row["macro_f1"], row["official_cost"]), fontsize=7)
    ax.set_xlabel("Macro-F1")
    ax.set_ylabel("Official cost")
    ax.set_title("SCANIA Cost vs Macro-F1")
    fig.tight_layout()
    fig.savefig(cost_f1_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return [cost_alert_path, cost_f1_path]


def write_report(run_dir: Path, result: dict[str, Any]) -> Path:
    report_path = run_dir / "reports" / "scania_policy_selection_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_df = result["metrics"]
    metadata = result["metadata"]
    selected = metrics_df[metrics_df["strategy_id"] == "xgboost_constrained_expected_cost"].iloc[0]
    unconstrained = metrics_df[metrics_df["strategy_id"] == "xgboost_cost_optimized"].iloc[0]
    all_alert = metrics_df[metrics_df["strategy_id"] == "all_alert_class_4_failure_baseline"].iloc[0]
    lines = [
        "# Workstream 4 SCANIA Constrained Policy Analysis",
        "",
        "## Scope",
        "",
        "This run preserves the unconstrained/all-alert failure mode and adds a training-only alert-rate constrained policy.",
        "Official validation labels are used only once, after the cap is selected on training folds.",
        "This is public benchmark evidence, not real factory cost reduction proof.",
        "",
        "## Policy Selection",
        "",
        f"- Candidate caps: `{metadata['candidate_alert_caps']}`",
        f"- Selected cap: `{metadata['selected_alert_cap']:.0%}`",
        f"- Selection rule: {metadata['selection_rule']}",
        "",
        "## Final Official Validation",
        "",
        f"- Constrained official cost: `{selected['official_cost']:.0f}`",
        f"- Constrained alert-like rate: `{selected['alert_like_rate']:.2%}`",
        f"- Constrained Macro-F1: `{selected['macro_f1']:.4f}`",
        f"- Constrained balanced accuracy: `{selected['balanced_accuracy']:.4f}`",
        f"- Unconstrained expected-cost alert-like rate: `{unconstrained['alert_like_rate']:.2%}`",
        f"- All-alert failure baseline official cost: `{all_alert['official_cost']:.0f}`",
        f"- All-alert failure baseline Macro-F1: `{all_alert['macro_f1']:.4f}`",
        "",
        "## Guardrail",
        "",
        "Do not describe the unconstrained or all-alert result as practical field performance.",
        "Report cost, Macro-F1, balanced accuracy, class recalls, alert-like rate, and predicted class distribution together.",
        "Negative or dominated constrained-policy results must remain in the output tables.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def write_outputs(run_dir: Path, result: dict[str, Any]) -> dict[str, Path]:
    metrics_dir = run_dir / "metrics"
    predictions_dir = run_dir / "predictions"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    predictions_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "final_metrics": metrics_dir / "scania_policy_final_metrics.csv",
        "selection_folds": metrics_dir / "scania_policy_selection_folds.csv",
        "candidate_summary": metrics_dir / "scania_policy_candidate_summary.csv",
        "pareto": metrics_dir / "scania_policy_pareto.csv",
        "predictions": predictions_dir / "scania_policy_validation_predictions.csv",
        "metadata": run_dir / "scania_policy_metadata.json",
        "verification": run_dir / "verification_report.json",
    }
    result["metrics"].to_csv(paths["final_metrics"], index=False, encoding="utf-8-sig")
    result["selection_folds"].to_csv(paths["selection_folds"], index=False, encoding="utf-8-sig")
    result["candidate_summary"].to_csv(paths["candidate_summary"], index=False, encoding="utf-8-sig")
    result["metrics"].to_csv(paths["pareto"], index=False, encoding="utf-8-sig")
    result["predictions"].to_csv(paths["predictions"], index=False, encoding="utf-8-sig")
    paths["metadata"].write_text(json.dumps(result["metadata"], indent=2, ensure_ascii=False), encoding="utf-8")
    chart_paths = write_charts(run_dir, result["metrics"])
    report_path = write_report(run_dir, result)
    paths["cost_vs_alert_chart"] = chart_paths[0]
    paths["cost_vs_macro_f1_chart"] = chart_paths[1]
    paths["report"] = report_path

    verification = verify_policy_outputs(result)
    paths["verification"].write_text(json.dumps(verification, indent=2, ensure_ascii=False), encoding="utf-8")
    return paths


def verify_policy_outputs(result: dict[str, Any]) -> dict[str, Any]:
    metrics_df = result["metrics"]
    required_strategies = {
        "no_alert_all_0",
        "all_alert_class_4_failure_baseline",
        "rule_based_threshold",
        "spc_style_baseline",
        "logistic_multiclass",
        "xgboost_multiclass_argmax",
        "xgboost_cost_optimized",
        "xgboost_constrained_expected_cost",
    }
    missing_strategies = sorted(required_strategies - set(metrics_df["strategy_id"].astype(str)))
    constrained = metrics_df[metrics_df["strategy_id"] == "xgboost_constrained_expected_cost"]
    selected_cap = float(result["metadata"]["selected_alert_cap"])
    checks = [
        {
            "check": "required_strategies_present",
            "passed": bool(not missing_strategies),
            "missing": missing_strategies,
        },
        {
            "check": "all_alert_baseline_preserved",
            "passed": bool(
                float(
                    metrics_df.loc[
                        metrics_df["strategy_id"] == "all_alert_class_4_failure_baseline",
                        "alert_like_rate",
                    ].iloc[0]
                )
                == 1.0
            ),
        },
        {
            "check": "constrained_alert_rate_within_selected_cap",
            "passed": bool(
                not constrained.empty and float(constrained.iloc[0]["alert_like_rate"]) <= selected_cap + 1e-12
            ),
            "selected_cap": selected_cap,
            "observed": None if constrained.empty else float(constrained.iloc[0]["alert_like_rate"]),
        },
        {
            "check": "selection_source_training_only",
            "passed": bool(
                set(result["selection_folds"]["selection_source"].astype(str)) == {"training_fold_only"}
            ),
        },
    ]
    return {
        "status": "passed" if all(bool(item["passed"]) for item in checks) else "failed",
        "checks": checks,
    }


def run_scania_policy_selection(
    *,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    max_rows_per_class: int = 10000,
    chunk_size: int = 200000,
    selection_folds: int = 3,
    run_id: str | None = None,
    experiment_root: str | Path = DEFAULT_EXPERIMENT_ROOT,
) -> Path:
    if run_id:
        requested_dir = Path(experiment_root) / run_id
        if requested_dir.exists() and any(requested_dir.iterdir()):
            raise FileExistsError(f"Refusing to reuse non-empty run directory: {requested_dir}")

    run = create_experiment_run(run_id=run_id, experiment_root=experiment_root, prefix=DEFAULT_RUN_PREFIX)
    record_current_process(run, "scania_policy_selection")
    run.append_command(
        phase="scania_policy_selection_settings",
        command={
            "data_dir": str(data_dir),
            "max_rows_per_class": max_rows_per_class,
            "chunk_size": chunk_size,
            "selection_folds": selection_folds,
        },
        exit_code=0,
    )
    try:
        data = load_scania_official_data(
            Path(data_dir),
            max_rows_per_class=max_rows_per_class,
            chunk_size=chunk_size,
        )
        result = train_select_and_evaluate(data, selection_folds=selection_folds)
        paths = write_outputs(run.run_dir, result)
        for path in paths.values():
            run.record_artifact(path, artifact_type=path.suffix.lower().lstrip(".") or "file")
        verification = json.loads(paths["verification"].read_text(encoding="utf-8"))
        run.update_status(verification["status"], {"workstream_4": verification})
        if verification["status"] != "passed":
            raise RuntimeError(f"SCANIA policy verification failed: {verification}")
    except FileNotFoundError as error:
        skipped = {
            "status": "skipped",
            "reason": str(error),
            "workstream": 4,
        }
        skip_path = run.run_dir / "verification_report.json"
        skip_path.write_text(json.dumps(skipped, indent=2, ensure_ascii=False), encoding="utf-8")
        run.record_artifact(skip_path, artifact_type="json")
        run.update_status("skipped", {"workstream_4": skipped})
    return run.run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Workstream 4 SCANIA constrained policy analysis.")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="SCANIA Component X data directory.")
    parser.add_argument("--max-rows-per-class", type=int, default=10000, help="Training rows per class sample cap.")
    parser.add_argument("--chunk-size", type=int, default=200000, help="CSV chunk size for train readouts.")
    parser.add_argument("--selection-folds", type=int, default=3, help="Training-only policy selection folds.")
    parser.add_argument("--run-id", default=None, help="Optional explicit run id.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        run_dir = run_scania_policy_selection(
            data_dir=args.data_dir,
            max_rows_per_class=args.max_rows_per_class,
            chunk_size=args.chunk_size,
            selection_folds=args.selection_folds,
            run_id=args.run_id,
        )
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        raise
    print(json.dumps({"status": "completed", "run_dir": str(run_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
