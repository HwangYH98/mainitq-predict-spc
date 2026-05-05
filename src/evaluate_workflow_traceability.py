from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd

from operations_store import (
    DEFAULT_DB_PATH,
    list_audit_logs,
    list_prediction_events,
    list_work_order_decisions,
    list_work_order_drafts,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"

SUMMARY_CSV = OUTPUT_DIR / "workflow_traceability_summary.csv"
SUMMARY_JSON = OUTPUT_DIR / "workflow_traceability_summary.json"
SUMMARY_MD = OUTPUT_DIR / "workflow_traceability_summary.md"


def safe_rate(numerator: int, denominator: int) -> float:
    """Return a rounded rate without failing on empty local databases."""
    if denominator <= 0:
        return 0.0
    return round(float(numerator / denominator), 4)


def build_traceability_summary() -> tuple[pd.DataFrame, dict]:
    """Calculate event-draft-decision traceability from the local operations DB."""
    events = list_prediction_events(limit=10000, db_path=DEFAULT_DB_PATH)
    drafts = list_work_order_drafts(limit=10000, db_path=DEFAULT_DB_PATH)
    decisions = list_work_order_decisions(limit=10000, db_path=DEFAULT_DB_PATH)
    audit_logs = list_audit_logs(limit=10000, db_path=DEFAULT_DB_PATH)

    event_ids = {event["event_id"] for event in events}
    draft_event_ids = {draft["event_id"] for draft in drafts}
    decision_event_ids = {decision["event_id"] for decision in decisions}
    draft_ids = {draft["draft_id"] for draft in drafts}
    decision_draft_ids = {decision["draft_id"] for decision in decisions}

    events_with_draft = len(event_ids & draft_event_ids)
    events_with_decision = len(event_ids & decision_event_ids)
    drafts_with_decision = len(draft_ids & decision_draft_ids)
    decisions_with_operator = sum(1 for decision in decisions if str(decision.get("operator_id", "")).strip())
    needs_review_count = sum(1 for decision in decisions if decision.get("decision") == "needs_review")
    failure_audit_count = sum(1 for entry in audit_logs if entry.get("status") == "failure")

    decision_breakdown = Counter(decision.get("decision", "unknown") for decision in decisions)
    action_breakdown = Counter(entry.get("action", "unknown") for entry in audit_logs)

    metrics = [
        {
            "metric": "event_count",
            "value": len(events),
            "description": "Prediction events stored in SQLite.",
        },
        {
            "metric": "draft_count",
            "value": len(drafts),
            "description": "Human-approved work-order drafts generated from events.",
        },
        {
            "metric": "decision_count",
            "value": len(decisions),
            "description": "Operator approve/reject/needs_review decisions.",
        },
        {
            "metric": "event_to_draft_rate",
            "value": safe_rate(events_with_draft, len(event_ids)),
            "description": "Share of stored events that have at least one draft.",
        },
        {
            "metric": "event_to_decision_rate",
            "value": safe_rate(events_with_decision, len(event_ids)),
            "description": "Share of stored events that reached an operator decision.",
        },
        {
            "metric": "draft_to_decision_rate",
            "value": safe_rate(drafts_with_decision, len(draft_ids)),
            "description": "Share of drafts that received a decision.",
        },
        {
            "metric": "operator_record_rate",
            "value": safe_rate(decisions_with_operator, len(decisions)),
            "description": "Share of decisions with an operator id.",
        },
        {
            "metric": "needs_review_retraining_candidates",
            "value": needs_review_count,
            "description": "Decisions marked as needs_review and therefore retraining candidates.",
        },
        {
            "metric": "audit_log_count",
            "value": len(audit_logs),
            "description": "Append-only product MVP audit log rows.",
        },
        {
            "metric": "audit_failure_count",
            "value": failure_audit_count,
            "description": "Failure audit rows useful for admin monitoring.",
        },
    ]
    summary = pd.DataFrame(metrics)
    details = {
        "scope": "human-approved work-order traceability; not automatic maintenance execution",
        "database_path": str(DEFAULT_DB_PATH),
        "decision_breakdown": dict(decision_breakdown),
        "audit_action_breakdown": dict(action_breakdown),
        "metrics": summary.to_dict(orient="records"),
    }
    return summary, details


def write_summary(summary: pd.DataFrame, details: dict) -> None:
    """Write a thesis-safe traceability summary."""
    metric_lookup = {row["metric"]: row["value"] for row in summary.to_dict(orient="records")}
    rows = [
        "# Workflow Traceability Summary",
        "",
        "## Scope",
        "",
        "This evaluates the local approval workflow traceability. It is not automatic maintenance-command execution.",
        "",
        "## Core Metrics",
        "",
        "| Metric | Value | Description |",
        "|---|---:|---|",
    ]
    for _, row in summary.iterrows():
        rows.append(f"| {row['metric']} | {row['value']} | {row['description']} |")

    rows.extend(
        [
            "",
            "## Decision Breakdown",
            "",
            "| Decision | Count |",
            "|---|---:|",
        ]
    )
    for decision, count in sorted(details["decision_breakdown"].items()):
        rows.append(f"| {decision} | {count} |")

    rows.extend(
        [
            "",
            "## Presentation-Safe Conclusion",
            "",
            (
                f"The local workflow stores {metric_lookup.get('event_count', 0)} events, "
                f"{metric_lookup.get('draft_count', 0)} drafts, and "
                f"{metric_lookup.get('decision_count', 0)} operator decisions. "
                "Use this as approval-workflow traceability evidence, not as proof of autonomous maintenance."
            ),
            "",
            "## Guardrail",
            "",
            "Do not describe this as automatic maintenance execution or validated CMMS/EAM integration.",
            "",
        ]
    )
    SUMMARY_MD.write_text("\n".join(rows), encoding="utf-8")


def main() -> None:
    """Create workflow traceability evidence artifacts."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary, details = build_traceability_summary()
    summary.to_csv(SUMMARY_CSV, index=False, encoding="utf-8-sig")
    SUMMARY_JSON.write_text(json.dumps(details, indent=2, ensure_ascii=False), encoding="utf-8")
    write_summary(summary, details)

    print("Workflow traceability evaluation finished successfully.")
    print(f"summary_csv: {SUMMARY_CSV}")
    print(f"summary_json: {SUMMARY_JSON}")
    print(f"summary_md: {SUMMARY_MD}")


if __name__ == "__main__":
    main()
