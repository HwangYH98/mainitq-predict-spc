from __future__ import annotations

import numpy as np
import pandas as pd

from thesis_methodology_validation import (
    choose_threshold_by_validation_f1,
    markdown_table,
    metrics_at_threshold,
    split_60_20_20,
)
from final_policy import FINAL_RAW_THRESHOLD, final_threshold_summary, status_for_probability


def test_split_60_20_20_keeps_independent_index_sets() -> None:
    X = pd.DataFrame({"x": range(100)})
    y = pd.Series([0] * 80 + [1] * 20)

    split = split_60_20_20(X, y, seed=42)

    assert len(split.X_train) == 60
    assert len(split.X_valid) == 20
    assert len(split.X_test) == 20
    assert set(split.X_train.index).isdisjoint(set(split.X_valid.index))
    assert set(split.X_train.index).isdisjoint(set(split.X_test.index))
    assert set(split.X_valid.index).isdisjoint(set(split.X_test.index))
    assert int(split.y_train.sum()) == 12
    assert int(split.y_valid.sum()) == 4
    assert int(split.y_test.sum()) == 4


def test_threshold_is_selected_from_validation_probabilities() -> None:
    y_valid = pd.Series([0, 0, 1, 1])
    validation_probabilities = np.array([0.10, 0.20, 0.80, 0.90])

    selected_threshold, grid = choose_threshold_by_validation_f1(y_valid, validation_probabilities)
    test_metrics = metrics_at_threshold(pd.Series([0, 1]), np.array([0.10, 0.70]), selected_threshold)

    assert selected_threshold == 0.21
    assert not grid.empty
    assert test_metrics["f1_score"] == 1.0


def test_markdown_table_does_not_require_optional_tabulate_dependency() -> None:
    rendered = markdown_table(pd.DataFrame([{"metric": "f1", "mean": 0.5}]))

    assert "| metric | mean |" in rendered
    assert "| f1 | 0.5 |" in rendered


def test_final_policy_uses_raw_threshold_086() -> None:
    summary = final_threshold_summary()

    assert FINAL_RAW_THRESHOLD == 0.86
    assert summary["selected_threshold"] == 0.86
    assert summary["probability_basis"] == "raw_probability"
    assert summary["selected_metrics"]["f1_score"] == 0.7692
    assert status_for_probability(0.8599) == "Normal"
    assert status_for_probability(0.86) == "High Risk"
