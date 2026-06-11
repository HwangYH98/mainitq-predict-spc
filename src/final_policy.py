from __future__ import annotations

from typing import Iterable


FINAL_POLICY_ID = "validation_selected_raw_threshold"
FINAL_POLICY_LABEL = "60:20:20 validation-selected raw threshold"
FINAL_PROBABILITY_BASIS = "raw_probability"
FINAL_RAW_THRESHOLD = 0.86

FINAL_TEST_METRICS = {
    "precision": 0.8065,
    "recall": 0.7353,
    "f1_score": 0.7692,
    "roc_auc": 0.9697,
    "pr_auc": 0.8118,
    "brier_score": 0.028006,
    "alert_count": 62,
    "false_alarm_count": 12,
    "missed_failure_count": 18,
    "true_positive_count": 50,
    "true_negative_count": 1920,
}

FINAL_VALIDATION_METRICS = {
    "precision": 0.8039,
    "recall": 0.6029,
    "f1_score": 0.6891,
    "roc_auc": 0.9754,
    "pr_auc": 0.7350,
    "brier_score": 0.034327,
}

FINAL_CALIBRATION = {
    "selection_basis": "validation Brier score",
    "selected_method": "isotonic",
    "validation_brier": 0.014800,
    "test_brier": 0.012369,
}

LEGACY_80_20_POLICY = {
    "selected_threshold": 0.87,
    "precision": 0.8197,
    "recall": 0.7353,
    "f1_score": 0.7752,
    "pr_auc": 0.8014,
    "interpretation": "legacy exploratory 80:20 same-holdout threshold search",
}


def final_policy_dict() -> dict[str, object]:
    """Return the canonical app decision policy."""
    return {
        "policy_id": FINAL_POLICY_ID,
        "label": FINAL_POLICY_LABEL,
        "probability_basis": FINAL_PROBABILITY_BASIS,
        "threshold": FINAL_RAW_THRESHOLD,
        "selection_split": "validation",
        "evaluation_split": "fixed_test",
        "metrics": dict(FINAL_TEST_METRICS),
        "calibration": dict(FINAL_CALIBRATION),
        "legacy_reference": dict(LEGACY_80_20_POLICY),
    }


def status_for_probability(probability: float) -> str:
    """Classify a raw failure probability with the final thesis/app threshold."""
    return "High Risk" if float(probability) >= FINAL_RAW_THRESHOLD else "Normal"


def statuses_for_probabilities(probabilities: Iterable[float]) -> list[str]:
    """Classify a sequence of raw probabilities with the final app policy."""
    return [status_for_probability(probability) for probability in probabilities]


def final_threshold_summary(default_0_5_metrics: dict[str, float] | None = None) -> dict[str, object]:
    """Build the app-compatible threshold summary used by dashboards and CI."""
    return {
        "model": "xgboost",
        "scope": "final 60:20:20 thesis/app decision threshold",
        "selection_rule": "validation-set F1-score over raw probabilities",
        "probability_basis": FINAL_PROBABILITY_BASIS,
        "policy_id": FINAL_POLICY_ID,
        "threshold_search": {
            "start": 0.05,
            "end": 0.95,
            "step": 0.01,
            "selection_split": "validation",
            "evaluation_split": "fixed_test",
        },
        "selected_threshold": FINAL_RAW_THRESHOLD,
        "selected_metrics": dict(FINAL_TEST_METRICS),
        "validation_selected_metrics": dict(FINAL_VALIDATION_METRICS),
        "default_0_5_metrics": default_0_5_metrics
        or {
            "precision": 0.3846,
            "recall": 0.8088,
            "f1_score": 0.5213,
        },
        "calibration": dict(FINAL_CALIBRATION),
        "test_rows": 2000,
        "test_failures": 68,
        "legacy_reference": dict(LEGACY_80_20_POLICY),
    }
