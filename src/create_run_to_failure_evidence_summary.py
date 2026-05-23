from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"
REPORT_PATH = OUTPUT_DIR / "run_to_failure_evidence_summary.md"


def read_csv_summary(path: Path, key_columns: list[str]) -> list[str]:
    if not path.exists():
        return [f"- `{path.name}`: not generated yet."]
    frame = pd.read_csv(path)
    rows = [f"- `{path.name}`: {len(frame)} rows."]
    visible_columns = [column for column in key_columns if column in frame.columns]
    if visible_columns and not frame.empty:
        preview = frame[visible_columns].head(6).fillna("")
        rows.append("")
        rows.append("| " + " | ".join(visible_columns) + " |")
        rows.append("|" + "|".join(["---"] * len(visible_columns)) + "|")
        for _, record in preview.iterrows():
            rows.append("| " + " | ".join(str(record[column]) for column in visible_columns) + " |")
    return rows


def read_json_note(path: Path) -> list[str]:
    if not path.exists():
        return [f"- `{path.name}`: not generated yet."]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [f"- `{path.name}`: generated, but JSON preview failed."]
    if isinstance(payload, dict):
        keys = ", ".join(sorted(payload.keys())[:10])
        return [f"- `{path.name}`: generated. Top-level keys: {keys}."]
    if isinstance(payload, list):
        return [f"- `{path.name}`: generated. List records: {len(payload)}."]
    return [f"- `{path.name}`: generated. JSON type: {type(payload).__name__}."]


def create_run_to_failure_evidence_summary(output_dir: Path = OUTPUT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[str] = [
        "# Run-to-Failure Benchmark Evidence Summary",
        "",
        "This file gathers public benchmark and field-validation evidence into one paper-ready index.",
        "It supports public benchmark claims only; actual company cost reduction or lead-time reduction requires company logs.",
        "",
        "## Public Industrial Benchmarks",
        "",
    ]
    rows.extend(
        read_csv_summary(
            output_dir / "public_industrial_validation_metrics.csv",
            ["dataset_id", "strategy", "precision", "recall", "f1_score", "pr_auc"],
        )
    )
    rows.extend(["", "## Lead-Time Metrics", ""])
    rows.extend(
        read_csv_summary(
            output_dir / "public_industrial_lead_time_metrics.csv",
            ["dataset_id", "strategy", "mean_lead_time_steps", "early_warning_rate"],
        )
    )
    rows.extend(["", "## RUL Metrics", ""])
    rows.extend(
        read_csv_summary(
            output_dir / "public_industrial_rul_metrics.csv",
            ["dataset_id", "strategy", "rul_mae", "rul_rmse"],
        )
    )
    rows.extend(["", "## SCANIA Official Cost Metric", ""])
    rows.extend(
        read_csv_summary(
            output_dir / "scania_official_cost_metrics.csv",
            ["strategy", "official_cost", "normalized_cost", "cost_improvement_vs_rule"],
        )
    )
    rows.extend(["", "## Field Validation Readiness", ""])
    rows.extend(
        read_csv_summary(
            output_dir / "field_validation_report.csv",
            [
                "source_mode",
                "precision",
                "recall",
                "false_alarm_count",
                "missed_failure_count",
                "maintenance_cost_delta_rate",
                "claim_status",
            ],
        )
    )
    rows.extend(["", "## Metadata", ""])
    rows.extend(read_json_note(output_dir / "public_industrial_validation_metadata.json"))
    rows.extend(
        [
            "",
            "## Claim Guardrail",
            "",
            "- Public benchmark improvements can be stated only for the named public dataset and metric.",
            "- Actual plant cost savings require before/after maintenance cost logs.",
            "- Actual detection-time reduction requires failure timestamps and first-alert timestamps.",
            "- Lite runtime results are not a replacement for Full research-model benchmark results.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(rows), encoding="utf-8")
    return REPORT_PATH


def main() -> int:
    path = create_run_to_failure_evidence_summary()
    print("Run-to-failure evidence summary created.")
    print(f"report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
