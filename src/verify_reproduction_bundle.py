from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from final_policy import FINAL_CALIBRATION, FINAL_RAW_THRESHOLD, FINAL_TEST_METRICS


REQUIRED_BASELINE_FILES = [
    "run_manifest.json",
    "environment.json",
    "data_manifest.json",
    "command_log.txt",
    "artifact_manifest.csv",
    "baseline_metrics_snapshot.json",
    "baseline_test_report.json",
]
REQUIRED_ROBUST_FILES = [
    "metrics/robust_validation_fold_metrics.csv",
    "metrics/robust_validation_summary.json",
    "metrics/robust_validation_bootstrap.csv",
    "predictions/robust_validation_oof_predictions.csv",
    "figures/robust_validation_metric_distribution.png",
    "figures/robust_validation_threshold_distribution.png",
    "reports/robust_validation_report.md",
]
SECRET_PATTERNS = [
    re.compile(r"OPENAI_API_KEY\s*=", re.IGNORECASE),
    re.compile(r"GEMINI_API_KEY\s*=", re.IGNORECASE),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"sk-[0-9A-Za-z_\-]{20,}"),
]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_required_files(run_dir: Path, names: list[str]) -> list[dict[str, Any]]:
    checks = []
    for name in names:
        path = run_dir / name
        checks.append(
            {
                "check": f"required_file:{name}",
                "passed": path.exists() and path.stat().st_size > 0,
                "path": str(path),
            }
        )
    return checks


def _check_baseline_snapshot(run_dir: Path) -> list[dict[str, Any]]:
    snapshot_path = run_dir / "baseline_metrics_snapshot.json"
    if not snapshot_path.exists():
        return [{"check": "baseline_snapshot_parse", "passed": False, "reason": "missing"}]

    snapshot = _read_json(snapshot_path)
    observed = snapshot["observed"]
    metrics = observed["test_metrics"]
    calibration = observed["calibration"]
    selected_calibration = next(
        row for row in calibration["rows"] if row["calibration_method"] == calibration["selected_method"]
    )
    checks = [
        {
            "check": "baseline_status",
            "passed": snapshot.get("status") == "passed",
            "observed": snapshot.get("status"),
        },
        {
            "check": "final_threshold",
            "passed": float(observed["selected_threshold"]) == float(FINAL_RAW_THRESHOLD),
            "observed": observed["selected_threshold"],
            "expected": FINAL_RAW_THRESHOLD,
        },
    ]
    for metric in ["precision", "recall", "f1_score", "roc_auc", "pr_auc", "brier_score"]:
        checks.append(
            {
                "check": f"final_metric:{metric}",
                "passed": metrics[metric] == FINAL_TEST_METRICS[metric],
                "observed": metrics[metric],
                "expected": FINAL_TEST_METRICS[metric],
            }
        )
    checks.append(
        {
            "check": "calibration_test_brier",
            "passed": selected_calibration["test_brier"] == FINAL_CALIBRATION["test_brier"],
            "observed": selected_calibration["test_brier"],
            "expected": FINAL_CALIBRATION["test_brier"],
        }
    )
    return checks


def _check_artifact_manifest(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "artifact_manifest.json"
    csv_path = run_dir / "artifact_manifest.csv"
    if not path.exists():
        return [{"check": "artifact_manifest_parse", "passed": False, "reason": "missing"}]
    manifest = _read_json(path)
    artifacts = manifest.get("artifacts", [])
    return [
        {
            "check": "artifact_manifest_has_hashes",
            "passed": bool(artifacts) and all(item.get("sha256") for item in artifacts),
            "artifact_count": len(artifacts),
        },
        {
            "check": "artifact_manifest_csv_exists",
            "passed": csv_path.exists() and csv_path.stat().st_size > 0,
            "path": str(csv_path),
        },
    ]


def _check_command_log(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "command_log.txt"
    if not path.exists():
        return [{"check": "command_log_exists", "passed": False}]
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    parsed = []
    for line in lines:
        parsed.append(json.loads(line))
    return [
        {
            "check": "command_log_nonempty",
            "passed": bool(parsed),
            "command_count": len(parsed),
        }
    ]


def _check_no_secrets(run_dir: Path) -> list[dict[str, Any]]:
    scanned_files = []
    for path in run_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".json", ".jsonl", ".csv", ".txt", ".md"}:
            continue
        scanned_files.append(path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                return [
                    {
                        "check": "no_secret_like_values",
                        "passed": False,
                        "path": str(path),
                        "pattern": pattern.pattern,
                    }
                ]
    return [{"check": "no_secret_like_values", "passed": True, "scanned_files": len(scanned_files)}]


def verify_bundle(run_dir: Path, require_robust: bool = False) -> dict[str, Any]:
    checks = []
    checks.extend(_check_required_files(run_dir, REQUIRED_BASELINE_FILES))
    if require_robust:
        checks.extend(_check_required_files(run_dir, REQUIRED_ROBUST_FILES))
    checks.extend(_check_baseline_snapshot(run_dir))
    checks.extend(_check_artifact_manifest(run_dir))
    checks.extend(_check_command_log(run_dir))
    checks.extend(_check_no_secrets(run_dir))

    report = {
        "run_dir": str(run_dir),
        "require_robust": require_robust,
        "status": "passed" if all(item["passed"] for item in checks) else "failed",
        "checks": checks,
    }
    (run_dir / "verification_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify an experiment reproduction bundle.")
    parser.add_argument("run_dir", help="Path to outputs/experiments/<run_id>.")
    parser.add_argument("--require-robust", action="store_true", help="Require robust validation artifacts.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = verify_bundle(Path(args.run_dir), require_robust=args.require_robust)
    print(json.dumps({"status": report["status"], "run_dir": report["run_dir"]}, ensure_ascii=False))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
