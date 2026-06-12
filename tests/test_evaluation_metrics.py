from __future__ import annotations

import numpy as np

from evaluation_metrics import classification_metrics, select_threshold_by_f1, threshold_grid_metrics


def test_classification_metrics_include_counts_and_rates() -> None:
    y_true = np.array([0, 0, 1, 1])
    probabilities = np.array([0.1, 0.8, 0.7, 0.9])

    metrics = classification_metrics(y_true, probabilities, threshold=0.5)

    assert metrics["precision"] == 0.6667
    assert metrics["recall"] == 1.0
    assert metrics["f1_score"] == 0.8
    assert metrics["false_alarm_count"] == 1
    assert metrics["missed_failure_count"] == 0
    assert metrics["false_alarm_rate"] == 0.5
    assert metrics["missed_failure_rate"] == 0.0


def test_threshold_grid_selects_best_f1_then_recall_then_precision() -> None:
    y_true = np.array([0, 0, 1, 1])
    probabilities = np.array([0.1, 0.2, 0.8, 0.9])

    grid = threshold_grid_metrics(y_true, probabilities, thresholds=[0.2, 0.21, 0.8])

    assert select_threshold_by_f1(grid) == 0.21
