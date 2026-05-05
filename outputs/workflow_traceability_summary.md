# Workflow Traceability Summary

## Scope

This evaluates the local approval workflow traceability. It is not automatic maintenance-command execution.

## Core Metrics

| Metric | Value | Description |
|---|---:|---|
| event_count | 80.0 | Prediction events stored in SQLite. |
| draft_count | 51.0 | Human-approved work-order drafts generated from events. |
| decision_count | 37.0 | Operator approve/reject/needs_review decisions. |
| event_to_draft_rate | 0.6375 | Share of stored events that have at least one draft. |
| event_to_decision_rate | 0.4625 | Share of stored events that reached an operator decision. |
| draft_to_decision_rate | 0.7255 | Share of drafts that received a decision. |
| operator_record_rate | 1.0 | Share of decisions with an operator id. |
| needs_review_retraining_candidates | 31.0 | Decisions marked as needs_review and therefore retraining candidates. |
| audit_log_count | 21.0 | Append-only product MVP audit log rows. |
| audit_failure_count | 4.0 | Failure audit rows useful for admin monitoring. |

## Decision Breakdown

| Decision | Count |
|---|---:|
| approve | 6 |
| needs_review | 31 |

## Presentation-Safe Conclusion

The local workflow stores 80.0 events, 51.0 drafts, and 37.0 operator decisions. Use this as approval-workflow traceability evidence, not as proof of autonomous maintenance.

## Guardrail

Do not describe this as automatic maintenance execution or validated CMMS/EAM integration.
