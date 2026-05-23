from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from create_field_validation_protocol import (
    COST_TEMPLATE_CSV,
    DATA_TEMPLATE_CSV,
    FIELD_VALIDATION_KIT_ZIP,
    MAINTENANCE_TEMPLATE_CSV,
    PROTOCOL_MD,
    create_field_cost_template,
    create_field_data_template,
    create_field_maintenance_template,
    create_field_validation_kit_zip,
)
from evaluate_field_validation_report import evaluate_field_validation, evaluate_field_validation_package


def test_field_validation_report_generates_metrics(tmp_path: Path) -> None:
    field_path = tmp_path / "field_data.csv"
    cost_path = tmp_path / "field_cost.csv"
    output_dir = tmp_path / "outputs"
    create_field_data_template().to_csv(field_path, index=False)
    create_field_cost_template().to_csv(cost_path, index=False)

    metrics = evaluate_field_validation(field_path, cost_path, output_dir)

    assert metrics["field_data_rows"] == 2
    assert "precision" in metrics
    assert "recall" in metrics
    assert metrics["claim_status"] == "field_validation_ready"
    assert metrics["source_mode"] == "company_field_logs"
    assert metrics["maintenance_cost_delta_rate"] is not None
    assert metrics["downtime_delta_rate"] is not None
    assert metrics["detection_time_delta_rate"] is not None
    assert metrics["field_claim_ready"] is True
    assert (output_dir / "field_validation_report.md").exists()


def test_field_validation_report_requires_labels(tmp_path: Path) -> None:
    field_path = tmp_path / "field_data.csv"
    cost_path = tmp_path / "field_cost.csv"
    field_df = create_field_data_template().drop(columns=["actual_failure"])
    field_df.to_csv(field_path, index=False)
    create_field_cost_template().to_csv(cost_path, index=False)

    with pytest.raises(ValueError, match="actual_failure|missing required"):
        evaluate_field_validation(field_path, cost_path, tmp_path / "outputs")


def test_field_validation_report_marks_template_mode(tmp_path: Path) -> None:
    field_path = tmp_path / "field_data.csv"
    cost_path = tmp_path / "field_cost.csv"
    create_field_data_template().to_csv(field_path, index=False)
    create_field_cost_template().to_csv(cost_path, index=False)

    metrics = evaluate_field_validation(
        field_path,
        cost_path,
        tmp_path / "outputs",
        source_mode_override="template_demo",
    )

    assert metrics["source_mode"] == "template_demo"
    assert metrics["claim_status"] == "template_demo_not_field_proof"
    report_text = (tmp_path / "outputs" / "field_validation_report.md").read_text(encoding="utf-8")
    assert "Claim status" in report_text


def test_field_validation_package_allows_missing_cost_log_with_guardrail(tmp_path: Path) -> None:
    field_path = tmp_path / "field_data.csv"
    output_dir = tmp_path / "outputs"
    create_field_data_template().to_csv(field_path, index=False)

    metrics = evaluate_field_validation_package(field_path, output_dir=output_dir)

    assert metrics["field_data_rows"] == 2
    assert metrics["cost_rows"] == 0
    assert metrics["claim_status"] == "performance_recheck_only_cost_and_downtime_claim_not_supported"
    assert metrics["maintenance_cost_delta_rate"] is None
    assert metrics["downtime_delta_rate"] is None
    assert metrics["field_claim_ready"] is False
    assert (output_dir / "field_validation_report.md").exists()
    assert (output_dir / "field_validation_report_bundle.zip").exists()


def test_field_validation_separates_cost_and_downtime_claims(tmp_path: Path) -> None:
    field_path = tmp_path / "field_data.csv"
    cost_path = tmp_path / "field_cost.csv"
    create_field_data_template().to_csv(field_path, index=False)

    cost_df = create_field_cost_template().drop(columns=["baseline_downtime_minutes", "new_policy_downtime_minutes"])
    cost_df.to_csv(cost_path, index=False)

    metrics = evaluate_field_validation(field_path, cost_path, tmp_path / "outputs")

    assert metrics["claim_status"] == "cost_validation_ready_downtime_claim_not_supported"
    assert metrics["maintenance_cost_delta_rate"] is not None
    assert metrics["downtime_delta_rate"] is None
    assert metrics["cost_reduction_claim_allowed"] is True
    assert metrics["downtime_reduction_claim_allowed"] is False


def test_field_validation_package_records_maintenance_traceability_without_cost(tmp_path: Path) -> None:
    field_path = tmp_path / "field_data.csv"
    maintenance_path = tmp_path / "maintenance_history.csv"
    output_dir = tmp_path / "outputs"
    create_field_data_template().to_csv(field_path, index=False)
    pd.DataFrame(
        [
            {
                "work_order_id": "WO-001",
                "equipment_id": "EQ-001",
                "maintenance_start": "2026-05-01T00:00:00Z",
                "maintenance_end": "2026-05-01T01:00:00Z",
                "maintenance_action_type": "inspection",
            }
        ]
    ).to_csv(maintenance_path, index=False)

    metrics = evaluate_field_validation_package(
        field_path,
        output_dir=output_dir,
        maintenance_data_path=maintenance_path,
    )

    assert metrics["maintenance_rows"] == 1
    assert metrics["maintenance_schema_status"] == "ok"
    assert metrics["claim_status"] == "performance_and_traceability_only_cost_claim_not_supported"
    assert Path(metrics["report_zip"]).exists()


def test_field_validation_data_request_kit_contains_three_templates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import create_field_validation_protocol as protocol

    monkeypatch.setattr(protocol, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(protocol, "PROTOCOL_MD", tmp_path / PROTOCOL_MD.name)
    monkeypatch.setattr(protocol, "DATA_TEMPLATE_CSV", tmp_path / DATA_TEMPLATE_CSV.name)
    monkeypatch.setattr(protocol, "MAINTENANCE_TEMPLATE_CSV", tmp_path / MAINTENANCE_TEMPLATE_CSV.name)
    monkeypatch.setattr(protocol, "COST_TEMPLATE_CSV", tmp_path / COST_TEMPLATE_CSV.name)
    monkeypatch.setattr(protocol, "FIELD_VALIDATION_KIT_ZIP", tmp_path / FIELD_VALIDATION_KIT_ZIP.name)

    protocol.PROTOCOL_MD.write_text(protocol.create_protocol_markdown(), encoding="utf-8")
    create_field_data_template().to_csv(protocol.DATA_TEMPLATE_CSV, index=False)
    create_field_maintenance_template().to_csv(protocol.MAINTENANCE_TEMPLATE_CSV, index=False)
    create_field_cost_template().to_csv(protocol.COST_TEMPLATE_CSV, index=False)

    kit_path = create_field_validation_kit_zip()

    assert kit_path.exists()
    import zipfile

    with zipfile.ZipFile(kit_path) as archive:
        names = set(archive.namelist())
    assert {
        "field_validation_protocol.md",
        "field_data_template.csv",
        "field_maintenance_template.csv",
        "field_cost_template.csv",
    }.issubset(names)
