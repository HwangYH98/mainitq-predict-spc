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
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

from evaluation_metrics import collapse_alert_episodes, evaluate_event_alert_metrics
from experiment_run import DEFAULT_EXPERIMENT_ROOT, create_experiment_run, record_current_process
from metropt3_loader import SIGNAL_COLUMNS, TIMESTAMP_COLUMN, load_metropt3_dataset


DEFAULT_HORIZONS_MINUTES = [30, 120, 360, 1440]


def failure_point_labels(timestamps: pd.Series, failure_windows: pd.DataFrame) -> pd.Series:
    labels = pd.Series(False, index=timestamps.index)
    for _, event in failure_windows.iterrows():
        labels |= (timestamps >= event["start_time"]) & (timestamps <= event["end_time"])
    return labels.astype(int)


def reference_period(frame: pd.DataFrame, failure_windows: pd.DataFrame) -> dict[str, Any]:
    start = frame[TIMESTAMP_COLUMN].min()
    end = start + pd.DateOffset(months=1)
    timestamps = frame[TIMESTAMP_COLUMN]
    failure_labels = failure_point_labels(timestamps, failure_windows).astype(bool)
    mask = (timestamps >= start) & (timestamps < end) & (~failure_labels)
    if int(mask.sum()) <= 10:
        raise ValueError("Reference period has too few normal rows.")
    return {
        "start_time": start,
        "end_time": end,
        "definition": "first calendar month of MetroPT-3 rows, excluding published failure windows",
        "row_count": int(mask.sum()),
        "mask": mask,
    }


def fit_reference_limits(frame: pd.DataFrame, reference_mask: pd.Series, alpha: float = 0.2) -> dict[str, Any]:
    reference = frame.loc[reference_mask, SIGNAL_COLUMNS]
    means = reference.mean()
    stds = reference.std(ddof=0).replace(0, 1.0)
    z = (frame[SIGNAL_COLUMNS] - means) / stds
    shewhart_score = z.abs().max(axis=1)
    risk_score = np.sqrt((z**2).mean(axis=1))
    ewma_score = shewhart_score.ewm(alpha=alpha, adjust=False).mean()

    reference_shewhart = shewhart_score.loc[reference_mask]
    reference_risk = risk_score.loc[reference_mask]
    reference_ewma = ewma_score.loc[reference_mask]
    limits = {
        "shewhart": {
            "score_column": "shewhart_score",
            "limit": float(reference_shewhart.mean() + 3.0 * reference_shewhart.std(ddof=0)),
            "basis": "max absolute standardized residual; limit = reference mean + 3*reference std",
        },
        "ewma": {
            "score_column": "ewma_score",
            "limit": float(reference_ewma.mean() + 3.0 * reference_ewma.std(ddof=0)),
            "basis": f"EWMA(alpha={alpha}) of Shewhart score; limit = reference mean + 3*reference std",
        },
        "risk_score": {
            "score_column": "risk_score",
            "limit": float(reference_risk.mean() + 3.0 * reference_risk.std(ddof=0)),
            "basis": "sqrt(mean squared standardized residuals); limit = reference mean + 3*reference std",
        },
    }
    score_frame = pd.DataFrame(
        {
            TIMESTAMP_COLUMN: frame[TIMESTAMP_COLUMN],
            "shewhart_score": shewhart_score,
            "ewma_score": ewma_score,
            "risk_score": risk_score,
        }
    )
    return {
        "means": means.to_dict(),
        "stds": stds.to_dict(),
        "limits": limits,
        "scores": score_frame,
        "alpha": alpha,
    }


def point_level_metrics(y_true: pd.Series, alerts: pd.Series, scores: pd.Series) -> dict[str, Any]:
    y = y_true.astype(int).to_numpy()
    pred = alerts.astype(int).to_numpy()
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "point_precision": round(float(precision_score(y, pred, zero_division=0)), 6),
        "point_recall": round(float(recall_score(y, pred, zero_division=0)), 6),
        "point_f1_score": round(float(f1_score(y, pred, zero_division=0)), 6),
        "alert_point_count": int(tp + fp),
        "false_alarm_point_count": int(fp),
        "missed_failure_point_count": int(fn),
        "true_positive_point_count": int(tp),
        "true_negative_point_count": int(tn),
        "score_mean": round(float(scores.mean()), 6),
        "score_median": round(float(scores.median()), 6),
        "score_max": round(float(scores.max()), 6),
    }


def evaluate_strategies(
    frame: pd.DataFrame,
    failure_windows: pd.DataFrame,
    reference: dict[str, Any],
    fitted: dict[str, Any],
    horizons_minutes: list[int] | None = None,
) -> dict[str, pd.DataFrame | dict[str, Any]]:
    horizons = horizons_minutes or DEFAULT_HORIZONS_MINUTES
    scores = fitted["scores"].copy()
    timestamps = scores[TIMESTAMP_COLUMN]
    evaluation_mask = timestamps >= reference["end_time"]
    if int(evaluation_mask.sum()) <= 10:
        raise ValueError("Evaluation period has too few rows.")

    point_labels = failure_point_labels(timestamps, failure_windows)
    point_rows = []
    event_rows = []
    all_event_details = []
    all_episodes = []

    for strategy_id, limit_info in fitted["limits"].items():
        score_column = str(limit_info["score_column"])
        limit = float(limit_info["limit"])
        strategy_frame = scores.loc[evaluation_mask, [TIMESTAMP_COLUMN, score_column]].copy()
        strategy_frame["alert"] = strategy_frame[score_column] > limit
        y_eval = point_labels.loc[evaluation_mask]
        point_rows.append(
            {
                "strategy_id": strategy_id,
                "score_column": score_column,
                "control_limit": round(limit, 6),
                "evaluation_rows": int(len(strategy_frame)),
                "failure_window_rows": int(y_eval.sum()),
                **point_level_metrics(y_eval, strategy_frame["alert"], strategy_frame[score_column]),
            }
        )

        episodes = collapse_alert_episodes(strategy_frame, alert_column="alert")
        if not episodes.empty:
            episodes.insert(0, "strategy_id", strategy_id)

        summary, event_detail, episodes_with_flags = evaluate_event_alert_metrics(
            failure_windows=failure_windows,
            alert_episodes=episodes.drop(columns=["strategy_id"]) if "strategy_id" in episodes.columns else episodes,
            evaluation_start=strategy_frame[TIMESTAMP_COLUMN].min(),
            evaluation_end=strategy_frame[TIMESTAMP_COLUMN].max(),
            horizons_minutes=horizons,
        )
        event_rows.append(
            {
                "strategy_id": strategy_id,
                "score_column": score_column,
                "control_limit": round(limit, 6),
                **summary,
            }
        )
        event_detail.insert(0, "strategy_id", strategy_id)
        if not episodes_with_flags.empty:
            episodes_with_flags.insert(0, "strategy_id", strategy_id)
        all_event_details.append(event_detail)
        all_episodes.append(episodes_with_flags)

    return {
        "point_metrics": pd.DataFrame(point_rows),
        "event_metrics": pd.DataFrame(event_rows),
        "event_details": pd.concat(all_event_details, ignore_index=True),
        "alert_episodes": pd.concat(all_episodes, ignore_index=True)
        if all_episodes
        else pd.DataFrame(),
        "scores": scores,
        "evaluation_mask": evaluation_mask,
        "point_labels": point_labels,
    }


def write_figures(
    scores: pd.DataFrame,
    failure_windows: pd.DataFrame,
    fitted: dict[str, Any],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    sample = scores.iloc[:: max(len(scores) // 8000, 1)].copy()
    fig, ax = plt.subplots(figsize=(12, 5.6))
    for strategy_id, limit_info in fitted["limits"].items():
        score_column = str(limit_info["score_column"])
        ax.plot(sample[TIMESTAMP_COLUMN], sample[score_column], linewidth=0.8, label=strategy_id)
        ax.axhline(float(limit_info["limit"]), linestyle="--", linewidth=0.9)
    for _, event in failure_windows.iterrows():
        ax.axvspan(event["start_time"], event["end_time"], color="#ef4444", alpha=0.16)
    ax.set_title("MetroPT-3 Timestamp SPC Scores and Published Failure Windows")
    ax.set_ylabel("SPC score")
    ax.legend(loc="upper right")
    ax.grid(alpha=0.2)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "metropt3_spc_timeline.png", dpi=180)
    plt.close(fig)

    event = failure_windows.iloc[0]
    window_start = event["start_time"] - pd.Timedelta(hours=24)
    window_end = event["end_time"] + pd.Timedelta(hours=6)
    panel = scores[(scores[TIMESTAMP_COLUMN] >= window_start) & (scores[TIMESTAMP_COLUMN] <= window_end)].copy()
    fig, ax = plt.subplots(figsize=(12, 5.2))
    for strategy_id, limit_info in fitted["limits"].items():
        score_column = str(limit_info["score_column"])
        ax.plot(panel[TIMESTAMP_COLUMN], panel[score_column], linewidth=0.9, label=strategy_id)
        ax.axhline(float(limit_info["limit"]), linestyle="--", linewidth=0.8)
    ax.axvspan(event["start_time"], event["end_time"], color="#ef4444", alpha=0.18, label="failure window")
    ax.set_title(f"MetroPT-3 Event Panel: {event['event_id']}")
    ax.set_ylabel("SPC score")
    ax.legend(loc="upper right")
    ax.grid(alpha=0.2)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "metropt3_event_panel.png", dpi=180)
    plt.close(fig)


def write_report(
    report_path: Path,
    manifest: dict[str, Any],
    reference_payload: dict[str, Any],
    point_metrics: pd.DataFrame,
    event_metrics: pd.DataFrame,
) -> None:
    lines = [
        "# MetroPT-3 Timestamp-Based SPC Validation",
        "",
        "## Scope",
        "",
        "This experiment uses the public MetroPT-3 timestamped compressor dataset and published company failure report windows.",
        "It does not modify the AI4I UDI-order SPC analysis, Desktop app, Streamlit app, or thesis manuscript numbers.",
        "",
        "## Data and Reference Period",
        "",
        f"- Rows: {manifest['rows']}",
        f"- Time range: {manifest['timestamp_start']} to {manifest['timestamp_end']}",
        f"- Normal reference period: {reference_payload['start_time']} to {reference_payload['end_time']}",
        f"- Reference rows: {reference_payload['row_count']}",
        "- Control limits are fitted only on the reference period.",
        "",
        "## Event Metrics",
        "",
        "| Strategy | Event detection | Pre-event detection | Median lead time min | False alarms/day | Median alert duration min |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in event_metrics.iterrows():
        lead = "" if pd.isna(row["median_lead_time_minutes"]) else f"{row['median_lead_time_minutes']:.2f}"
        lines.append(
            f"| {row['strategy_id']} | {row['event_detection_rate']:.4f} | {row['pre_event_detection_rate']:.4f} | "
            f"{lead} | {row['false_alarms_per_operating_day']:.4f} | {row['median_alert_duration_minutes']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Point Metrics",
            "",
            "| Strategy | Precision | Recall | F1 | Alert points | Missed failure points |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in point_metrics.iterrows():
        lines.append(
            f"| {row['strategy_id']} | {row['point_precision']:.4f} | {row['point_recall']:.4f} | "
            f"{row['point_f1_score']:.4f} | {int(row['alert_point_count'])} | {int(row['missed_failure_point_count'])} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            "Report these as public timestamped benchmark results only. Do not claim real-time deployment, factory cost reduction, or company-data field validation.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")


def build_verification_report(
    run_dir: Path,
    reference_payload: dict[str, Any],
    event_metrics: pd.DataFrame,
) -> dict[str, Any]:
    required_files = [
        "dataset_manifest.json",
        "data_manifest.json",
        "failure_windows.csv",
        "reference_period.json",
        "metrics/metropt3_point_metrics.csv",
        "metrics/metropt3_event_metrics.csv",
        "metrics/lead_time_distribution.csv",
        "events/metropt3_alert_episodes.csv",
        "figures/metropt3_spc_timeline.png",
        "figures/metropt3_event_panel.png",
        "reports/metropt3_time_series_spc_report.md",
    ]
    checks = [
        {
            "check": f"required_file:{name}",
            "passed": (run_dir / name).exists() and (run_dir / name).stat().st_size > 0,
        }
        for name in required_files
    ]
    checks.append(
        {
            "check": "reference_period_is_first_month_only",
            "passed": reference_payload["start_time"].startswith("2020-02-01")
            and reference_payload["end_time"].startswith("2020-03-01"),
            "start_time": reference_payload["start_time"],
            "end_time": reference_payload["end_time"],
        }
    )
    checks.append(
        {
            "check": "all_strategies_report_false_alarms_per_day",
            "passed": bool(
                "false_alarms_per_operating_day" in event_metrics.columns
            and event_metrics["false_alarms_per_operating_day"].notna().all(),
            ),
        }
    )
    checks.append(
        {
            "check": "expected_strategy_set",
            "passed": bool(set(event_metrics["strategy_id"]) == {"shewhart", "ewma", "risk_score"}),
            "observed": sorted(event_metrics["strategy_id"].astype(str).tolist()),
        }
    )
    return {
        "status": "passed" if all(check["passed"] for check in checks) else "failed",
        "scope": "MetroPT-3 timestamp-based SPC validation",
        "checks": checks,
    }


def run_metropt3_spc(
    run_id: str | None = None,
    max_rows: int | None = None,
    alpha: float = 0.2,
) -> Path:
    if run_id:
        target = DEFAULT_EXPERIMENT_ROOT / run_id
        if target.exists() and any(target.iterdir()):
            raise FileExistsError(f"Experiment run folder already exists and will not be overwritten: {target}")

    run = create_experiment_run(run_id=run_id, prefix="metropt3-spc")
    record_current_process(run, phase="metropt3_time_series_spc")
    run.append_command("metropt3_spc_parameters", [sys.executable, "src/time_series_spc_validation.py"])

    dataset = load_metropt3_dataset(max_rows=max_rows)
    reference = reference_period(dataset.frame, dataset.failure_windows)
    fitted = fit_reference_limits(dataset.frame, reference["mask"], alpha=alpha)
    evaluation = evaluate_strategies(dataset.frame, dataset.failure_windows, reference, fitted)

    metrics_dir = run.run_dir / "metrics"
    events_dir = run.run_dir / "events"
    figures_dir = run.run_dir / "figures"
    reports_dir = run.run_dir / "reports"
    scores_dir = run.run_dir / "scores"
    for directory in [metrics_dir, events_dir, figures_dir, reports_dir, scores_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    reference_payload = {
        "start_time": reference["start_time"].isoformat(),
        "end_time": reference["end_time"].isoformat(),
        "definition": reference["definition"],
        "row_count": reference["row_count"],
        "limits": fitted["limits"],
        "ewma_alpha": fitted["alpha"],
    }

    run.write_json("dataset_manifest.json", dataset.manifest)
    run.write_json("data_manifest.json", dataset.manifest)
    run.write_json("reference_period.json", reference_payload)
    dataset.failure_windows.to_csv(run.run_dir / "failure_windows.csv", index=False, encoding="utf-8-sig")
    evaluation["point_metrics"].to_csv(metrics_dir / "metropt3_point_metrics.csv", index=False, encoding="utf-8-sig")
    evaluation["event_metrics"].to_csv(metrics_dir / "metropt3_event_metrics.csv", index=False, encoding="utf-8-sig")
    evaluation["event_details"].to_csv(metrics_dir / "metropt3_event_details.csv", index=False, encoding="utf-8-sig")
    evaluation["event_details"].to_csv(metrics_dir / "lead_time_distribution.csv", index=False, encoding="utf-8-sig")
    evaluation["alert_episodes"].to_csv(events_dir / "metropt3_alert_episodes.csv", index=False, encoding="utf-8-sig")

    score_sample = evaluation["scores"].iloc[:: max(len(evaluation["scores"]) // 20000, 1)].copy()
    score_sample.to_csv(scores_dir / "metropt3_spc_scores_sample.csv", index=False, encoding="utf-8-sig")
    write_figures(evaluation["scores"], dataset.failure_windows, fitted, figures_dir)
    write_report(
        reports_dir / "metropt3_time_series_spc_report.md",
        dataset.manifest,
        reference_payload,
        evaluation["point_metrics"],
        evaluation["event_metrics"],
    )
    verification_report = build_verification_report(run.run_dir, reference_payload, evaluation["event_metrics"])
    (run.run_dir / "verification_report.json").write_text(
        json.dumps(verification_report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    for path, artifact_type, description in [
        (run.run_dir / "failure_windows.csv", "csv", "Source-traceable MetroPT-3 published failure windows."),
        (run.run_dir / "reference_period.json", "json", "Normal reference period and fitted control limits."),
        (metrics_dir / "metropt3_point_metrics.csv", "csv", "Point-level SPC alert metrics."),
        (metrics_dir / "metropt3_event_metrics.csv", "csv", "Event-level detection and false-alarm metrics."),
        (metrics_dir / "metropt3_event_details.csv", "csv", "Event-level lead-time details."),
        (metrics_dir / "lead_time_distribution.csv", "csv", "Lead-time distribution by event and strategy."),
        (events_dir / "metropt3_alert_episodes.csv", "csv", "Collapsed alert episodes by strategy."),
        (scores_dir / "metropt3_spc_scores_sample.csv", "csv", "Sampled SPC score timeline."),
        (figures_dir / "metropt3_spc_timeline.png", "png", "Timeline score chart with failure windows."),
        (figures_dir / "metropt3_event_panel.png", "png", "First event score panel."),
        (reports_dir / "metropt3_time_series_spc_report.md", "markdown", "Thesis-safe MetroPT-3 SPC report."),
        (run.run_dir / "verification_report.json", "json", "MetroPT-3 SPC run verification report."),
    ]:
        run.record_artifact(path, artifact_type, description)

    run.update_status(
        "metropt3_time_series_spc_completed",
        {
            "failure_event_count": int(len(dataset.failure_windows)),
            "strategy_count": int(len(evaluation["event_metrics"])),
            "reference_rows": int(reference["row_count"]),
        },
    )
    print(f"RUN_ID={run.run_id}")
    print(f"RUN_DIR={run.run_dir}")
    return run.run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MetroPT-3 timestamp-based SPC validation.")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--max-rows", type=int, default=0, help="Optional debug row cap; 0 means full dataset.")
    parser.add_argument("--alpha", type=float, default=0.2, help="EWMA smoothing alpha.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_metropt3_spc(
        run_id=args.run_id,
        max_rows=args.max_rows if args.max_rows > 0 else None,
        alpha=args.alpha,
    )


if __name__ == "__main__":
    main()
