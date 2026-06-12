from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd

from evaluation_metrics import classification_metrics


DEFAULT_BOOTSTRAP_METRICS = [
    "precision",
    "recall",
    "f1_score",
    "roc_auc",
    "pr_auc",
    "false_alarm_rate",
    "missed_failure_rate",
]


def _as_array(values: Iterable[float] | pd.Series | np.ndarray) -> np.ndarray:
    return np.asarray(list(values) if not isinstance(values, (pd.Series, np.ndarray)) else values)


def stratified_bootstrap_indices(y_true: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    sampled_parts = []
    for class_value in np.unique(y_true):
        class_indices = np.flatnonzero(y_true == class_value)
        sampled_parts.append(rng.choice(class_indices, size=len(class_indices), replace=True))
    sampled = np.concatenate(sampled_parts)
    rng.shuffle(sampled)
    return sampled


def stratified_bootstrap_intervals(
    y_true: Iterable[int] | pd.Series | np.ndarray,
    probabilities: Iterable[float] | pd.Series | np.ndarray,
    predictions: Iterable[int] | pd.Series | np.ndarray,
    n_iterations: int = 2000,
    random_state: int = 20260612,
    metrics: list[str] | None = None,
) -> dict[str, Any]:
    if n_iterations <= 0:
        raise ValueError("n_iterations must be positive.")

    y_array = _as_array(y_true).astype(int)
    probability_array = _as_array(probabilities).astype(float)
    prediction_array = _as_array(predictions).astype(int)
    if not (len(y_array) == len(probability_array) == len(prediction_array)):
        raise ValueError("y_true, probabilities, and predictions must have the same length.")
    if len(np.unique(y_array)) != 2:
        raise ValueError("Stratified bootstrap requires both classes.")

    metric_names = metrics or DEFAULT_BOOTSTRAP_METRICS
    rng = np.random.default_rng(random_state)
    samples: dict[str, list[float]] = {metric: [] for metric in metric_names}

    for _ in range(n_iterations):
        indices = stratified_bootstrap_indices(y_array, rng)
        values = classification_metrics(
            y_array[indices],
            probability_array[indices],
            predictions=prediction_array[indices],
            rounded=False,
        )
        for metric in metric_names:
            samples[metric].append(float(values[metric]))

    intervals = {}
    rows = []
    for metric, values in samples.items():
        array = np.asarray(values, dtype=float)
        summary = {
            "mean": round(float(np.mean(array)), 6),
            "std": round(float(np.std(array, ddof=1)), 6),
            "median": round(float(np.median(array)), 6),
            "min": round(float(np.min(array)), 6),
            "max": round(float(np.max(array)), 6),
            "lower_95": round(float(np.percentile(array, 2.5)), 6),
            "upper_95": round(float(np.percentile(array, 97.5)), 6),
        }
        intervals[metric] = summary
        rows.append({"metric": metric, **summary})

    return {
        "method": "stratified percentile bootstrap",
        "iterations": int(n_iterations),
        "random_state": int(random_state),
        "metrics": intervals,
        "rows": rows,
    }
