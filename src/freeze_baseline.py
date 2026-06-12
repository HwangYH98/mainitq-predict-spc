from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from data_integrity import validate_ai4i_dataset
from experiment_run import create_experiment_run, record_current_process
from final_policy import FINAL_CALIBRATION, FINAL_RAW_THRESHOLD, FINAL_TEST_METRICS, final_policy_dict
from thesis_methodology_validation import run_once


BASELINE_TOLERANCE = {
    "precision": 0.00005,
    "recall": 0.00005,
    "f1_score": 0.00005,
    "roc_auc": 0.00005,
    "pr_auc": 0.00005,
    "brier_score": 0.0000005,
}


def compare_metric_dict(
    observed: dict[str, Any],
    expected: dict[str, Any],
    metric_names: list[str],
) -> list[dict[str, Any]]:
    rows = []
    for metric in metric_names:
        actual = observed[metric]
        target = expected[metric]
        tolerance = BASELINE_TOLERANCE.get(metric, 0)
        rows.append(
            {
                "metric": metric,
                "observed": actual,
                "expected": target,
                "tolerance": tolerance,
                "passed": abs(float(actual) - float(target)) <= tolerance,
            }
        )
    return rows


def build_baseline_snapshot() -> dict[str, Any]:
    result = run_once(seed=42, save_artifacts=False)
    payload = result["payload"]
    selected = payload["xgboost_raw_threshold_selection"]
    observed_metrics = selected["test_metrics"]
    calibration_rows = payload["calibration"]["rows"]
    selected_method = payload["calibration"]["selected_method"]
    selected_calibration = next(row for row in calibration_rows if row["calibration_method"] == selected_method)

    metric_checks = compare_metric_dict(
        observed_metrics,
        FINAL_TEST_METRICS,
        ["precision", "recall", "f1_score", "roc_auc", "pr_auc", "brier_score"],
    )
    count_checks = compare_metric_dict(
        observed_metrics,
        FINAL_TEST_METRICS,
        ["alert_count", "false_alarm_count", "missed_failure_count", "true_positive_count", "true_negative_count"],
    )
    calibration_checks = [
        {
            "metric": "selected_method",
            "observed": selected_method,
            "expected": FINAL_CALIBRATION["selected_method"],
            "passed": selected_method == FINAL_CALIBRATION["selected_method"],
        },
        {
            "metric": "test_brier",
            "observed": selected_calibration["test_brier"],
            "expected": FINAL_CALIBRATION["test_brier"],
            "tolerance": BASELINE_TOLERANCE["brier_score"],
            "passed": abs(float(selected_calibration["test_brier"]) - float(FINAL_CALIBRATION["test_brier"]))
            <= BASELINE_TOLERANCE["brier_score"],
        },
    ]
    threshold_check = {
        "metric": "selected_threshold",
        "observed": selected["selected_threshold"],
        "expected": FINAL_RAW_THRESHOLD,
        "passed": float(selected["selected_threshold"]) == float(FINAL_RAW_THRESHOLD),
    }
    checks = [threshold_check, *metric_checks, *count_checks, *calibration_checks]

    return {
        "scope": "accepted 0.86 thesis/app baseline freeze",
        "status": "passed" if all(row["passed"] for row in checks) else "failed",
        "policy": final_policy_dict(),
        "observed": {
            "seed": payload["seed"],
            "split": payload["split"],
            "selected_threshold": selected["selected_threshold"],
            "validation_metrics": selected["validation_metrics"],
            "test_metrics": observed_metrics,
            "calibration": payload["calibration"],
        },
        "checks": checks,
        "source_payload": payload,
    }


def write_baseline_files(run_id: str | None) -> Path:
    run = create_experiment_run(run_id=run_id, prefix="baseline-freeze")
    record_current_process(run, phase="freeze_baseline")
    run.append_command("data_integrity", [sys.executable, "src/freeze_baseline.py", "--validate-ai4i"])

    data_manifest = validate_ai4i_dataset()
    run.write_json("data_manifest.json", data_manifest)

    snapshot = build_baseline_snapshot()
    run.write_json("baseline_metrics_snapshot.json", snapshot)
    run.write_json(
        "baseline_test_report.json",
        {
            "status": snapshot["status"],
            "summary": "Accepted baseline metrics match final_policy.py."
            if snapshot["status"] == "passed"
            else "Accepted baseline drift detected.",
            "checks": snapshot["checks"],
        },
    )
    run.write_json(
        "baseline_manifest.json",
        {
            "run_id": run.run_id,
            "baseline_status": snapshot["status"],
            "protected_outputs_policy": "Top-level outputs are not overwritten by freeze_baseline.py.",
            "new_artifact_root": str(run.run_dir),
        },
    )

    if snapshot["status"] != "passed":
        run.update_status("failed", {"reason": "baseline_drift", "checks": snapshot["checks"]})
        raise SystemExit("Baseline drift detected. See baseline_test_report.json.")

    run.update_status("baseline_frozen", {"baseline": "passed"})
    print(f"RUN_ID={run.run_id}")
    print(f"RUN_DIR={run.run_dir}")
    return run.run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze and verify the accepted thesis/app baseline.")
    parser.add_argument("--run-id", default=None, help="Experiment run id. A timestamped id is generated if omitted.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_baseline_files(args.run_id)


if __name__ == "__main__":
    main()
