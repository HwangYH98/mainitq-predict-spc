from __future__ import annotations

import numpy as np
import pandas as pd

from metropt3_loader import SIGNAL_COLUMNS
from time_series_spc_validation import (
    evaluate_strategies,
    failure_point_labels,
    fit_reference_limits,
    reference_period,
)


def _synthetic_metropt() -> tuple[pd.DataFrame, pd.DataFrame]:
    timestamps = pd.date_range("2020-02-01", periods=60 * 24 * 12, freq="5min")
    frame = pd.DataFrame({"timestamp": timestamps})
    rng = np.random.default_rng(123)
    for index, column in enumerate(SIGNAL_COLUMNS):
        frame[column] = 10.0 + index + rng.normal(0, 0.05, size=len(frame))

    event_start = pd.Timestamp("2020-03-10 12:00:00")
    pre_event_mask = (frame["timestamp"] >= event_start - pd.Timedelta(hours=2)) & (
        frame["timestamp"] < event_start
    )
    event_mask = (frame["timestamp"] >= event_start) & (
        frame["timestamp"] <= event_start + pd.Timedelta(hours=2)
    )
    frame.loc[pre_event_mask | event_mask, "Motor_current"] += 5.0
    windows = pd.DataFrame(
        [
            {
                "event_id": "synthetic_event",
                "start_time": event_start,
                "end_time": event_start + pd.Timedelta(hours=2),
            }
        ]
    )
    return frame, windows


def test_failure_point_labels_mark_only_failure_windows() -> None:
    frame, windows = _synthetic_metropt()
    labels = failure_point_labels(frame["timestamp"], windows)

    assert labels.sum() > 0
    assert labels.loc[frame["timestamp"] < windows.iloc[0]["start_time"]].sum() == 0


def test_reference_limits_do_not_use_evaluation_extremes() -> None:
    frame, windows = _synthetic_metropt()
    reference = reference_period(frame, windows)
    fitted = fit_reference_limits(frame, reference["mask"])

    changed = frame.copy()
    changed.loc[changed["timestamp"] >= reference["end_time"], "Motor_current"] += 1000.0
    fitted_changed = fit_reference_limits(changed, reference["mask"])

    for strategy_id in ["shewhart", "ewma", "risk_score"]:
        assert fitted["limits"][strategy_id]["limit"] == fitted_changed["limits"][strategy_id]["limit"]


def test_evaluate_strategies_reports_event_metrics_from_evaluation_period() -> None:
    frame, windows = _synthetic_metropt()
    reference = reference_period(frame, windows)
    fitted = fit_reference_limits(frame, reference["mask"])
    result = evaluate_strategies(frame, windows, reference, fitted, horizons_minutes=[30, 120, 1440])

    event_metrics = result["event_metrics"]
    point_metrics = result["point_metrics"]

    assert set(event_metrics["strategy_id"]) == {"shewhart", "ewma", "risk_score"}
    assert set(point_metrics["strategy_id"]) == {"shewhart", "ewma", "risk_score"}
    assert (event_metrics["event_detection_rate"] >= 0).all()
    assert "median_alert_duration_minutes" in event_metrics.columns
    assert not result["alert_episodes"].empty
