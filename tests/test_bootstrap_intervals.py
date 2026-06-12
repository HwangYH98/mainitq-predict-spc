from __future__ import annotations

import numpy as np

from bootstrap_intervals import stratified_bootstrap_intervals


def test_stratified_bootstrap_intervals_are_deterministic() -> None:
    y_true = np.array([0, 0, 0, 1, 1, 1])
    probabilities = np.array([0.1, 0.2, 0.9, 0.6, 0.7, 0.8])
    predictions = np.array([0, 0, 1, 1, 1, 1])

    first = stratified_bootstrap_intervals(
        y_true,
        probabilities,
        predictions,
        n_iterations=20,
        random_state=123,
    )
    second = stratified_bootstrap_intervals(
        y_true,
        probabilities,
        predictions,
        n_iterations=20,
        random_state=123,
    )

    assert first == second
    assert first["iterations"] == 20
    assert "f1_score" in first["metrics"]
    assert {"mean", "std", "median", "min", "max", "lower_95", "upper_95"} <= set(first["metrics"]["f1_score"])
    assert any(row["metric"] == "f1_score" for row in first["rows"])
    assert first["metrics"]["f1_score"]["lower_95"] <= first["metrics"]["f1_score"]["upper_95"]
