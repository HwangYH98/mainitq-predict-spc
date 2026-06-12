from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def _as_numpy(values: Iterable[float] | pd.Series | np.ndarray) -> np.ndarray:
    return np.asarray(list(values) if not isinstance(values, (pd.Series, np.ndarray)) else values)


def classification_metrics(
    y_true: Iterable[int] | pd.Series | np.ndarray,
    probabilities: Iterable[float] | pd.Series | np.ndarray,
    threshold: float | None = None,
    predictions: Iterable[int] | pd.Series | np.ndarray | None = None,
    rounded: bool = True,
) -> dict[str, float | int]:
    """Return the common thesis classification metrics for a binary classifier."""
    y_array = _as_numpy(y_true).astype(int)
    probability_array = _as_numpy(probabilities).astype(float)
    if predictions is None:
        if threshold is None:
            raise ValueError("Either threshold or predictions must be provided.")
        prediction_array = (probability_array >= float(threshold)).astype(int)
    else:
        prediction_array = _as_numpy(predictions).astype(int)

    tn, fp, fn, tp = confusion_matrix(y_array, prediction_array, labels=[0, 1]).ravel()
    failure_count = int(tp + fn)
    normal_count = int(tn + fp)
    total_count = int(len(y_array))

    result: dict[str, float | int] = {
        "precision": float(precision_score(y_array, prediction_array, zero_division=0)),
        "recall": float(recall_score(y_array, prediction_array, zero_division=0)),
        "f1_score": float(f1_score(y_array, prediction_array, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_array, probability_array)),
        "pr_auc": float(average_precision_score(y_array, probability_array)),
        "brier_score": float(brier_score_loss(y_array, probability_array)),
        "alert_count": int(fp + tp),
        "false_alarm_count": int(fp),
        "missed_failure_count": int(fn),
        "true_positive_count": int(tp),
        "true_negative_count": int(tn),
        "false_alarm_rate": float(fp / normal_count) if normal_count else 0.0,
        "missed_failure_rate": float(fn / failure_count) if failure_count else 0.0,
        "alert_rate": float((fp + tp) / total_count) if total_count else 0.0,
    }
    if threshold is not None:
        result["threshold"] = float(threshold)

    if not rounded:
        return result

    rounded_result: dict[str, float | int] = {}
    for key, value in result.items():
        if isinstance(value, int):
            rounded_result[key] = value
        elif key == "brier_score":
            rounded_result[key] = round(float(value), 6)
        elif key == "threshold":
            rounded_result[key] = round(float(value), 2)
        else:
            rounded_result[key] = round(float(value), 4)
    return rounded_result


def threshold_grid_metrics(
    y_true: Iterable[int] | pd.Series | np.ndarray,
    probabilities: Iterable[float] | pd.Series | np.ndarray,
    thresholds: Iterable[float],
) -> pd.DataFrame:
    rows = [classification_metrics(y_true, probabilities, float(threshold)) for threshold in thresholds]
    return pd.DataFrame(rows)


def select_threshold_by_f1(grid: pd.DataFrame) -> float:
    selected = grid.sort_values(["f1_score", "recall", "precision"], ascending=[False, False, False]).iloc[0]
    return float(selected["threshold"])


def collapse_alert_episodes(
    frame: pd.DataFrame,
    timestamp_column: str = "timestamp",
    alert_column: str = "alert",
    merge_gap: pd.Timedelta | timedelta = pd.Timedelta(minutes=5),
) -> pd.DataFrame:
    """Collapse timestamped alert rows into alert episodes."""
    if timestamp_column not in frame.columns or alert_column not in frame.columns:
        raise ValueError(f"Frame must contain {timestamp_column!r} and {alert_column!r}.")

    timestamps = pd.to_datetime(frame[timestamp_column], errors="coerce")
    if timestamps.isna().any():
        raise ValueError("Alert frame contains invalid timestamps.")

    work = frame.copy()
    work[timestamp_column] = timestamps
    work = work.sort_values(timestamp_column).reset_index(drop=True)
    alert_rows = work[work[alert_column].astype(bool)].copy()
    if alert_rows.empty:
        return pd.DataFrame(
            columns=[
                "episode_id",
                "start_time",
                "end_time",
                "duration_minutes",
                "row_count",
            ]
        )

    max_gap = pd.Timedelta(merge_gap)
    episodes: list[dict[str, Any]] = []
    start = alert_rows.iloc[0][timestamp_column]
    end = start
    row_count = 1
    for timestamp in alert_rows[timestamp_column].iloc[1:]:
        if timestamp - end <= max_gap:
            end = timestamp
            row_count += 1
        else:
            episodes.append(
                {
                    "episode_id": len(episodes) + 1,
                    "start_time": start,
                    "end_time": end,
                    "duration_minutes": max((end - start).total_seconds() / 60.0, 0.0),
                    "row_count": row_count,
                }
            )
            start = timestamp
            end = timestamp
            row_count = 1
    episodes.append(
        {
            "episode_id": len(episodes) + 1,
            "start_time": start,
            "end_time": end,
            "duration_minutes": max((end - start).total_seconds() / 60.0, 0.0),
            "row_count": row_count,
        }
    )
    return pd.DataFrame(episodes)


def evaluate_event_alert_metrics(
    failure_windows: pd.DataFrame,
    alert_episodes: pd.DataFrame,
    evaluation_start: str | pd.Timestamp,
    evaluation_end: str | pd.Timestamp,
    horizons_minutes: list[int] | None = None,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    """Evaluate event-level detection and operating false alarms from alert episodes."""
    horizons = horizons_minutes or [30, 120, 360, 1440]
    if not horizons:
        raise ValueError("At least one horizon is required.")

    eval_start = pd.Timestamp(evaluation_start)
    eval_end = pd.Timestamp(evaluation_end)
    if eval_end <= eval_start:
        raise ValueError("evaluation_end must be after evaluation_start.")

    events = failure_windows.copy()
    if events.empty:
        raise ValueError("At least one failure window is required.")
    events["event_id"] = events.get("event_id", pd.Series(range(1, len(events) + 1))).astype(str)
    events["start_time"] = pd.to_datetime(events["start_time"], errors="coerce")
    events["end_time"] = pd.to_datetime(events["end_time"], errors="coerce")
    if events[["start_time", "end_time"]].isna().any().any():
        raise ValueError("Failure windows contain invalid timestamps.")
    if (events["end_time"] < events["start_time"]).any():
        raise ValueError("Failure window end_time must be at or after start_time.")

    episodes = alert_episodes.copy()
    if episodes.empty:
        episodes = pd.DataFrame(columns=["episode_id", "start_time", "end_time", "duration_minutes"])
    else:
        episodes["start_time"] = pd.to_datetime(episodes["start_time"], errors="coerce")
        episodes["end_time"] = pd.to_datetime(episodes["end_time"], errors="coerce")
        if episodes[["start_time", "end_time"]].isna().any().any():
            raise ValueError("Alert episodes contain invalid timestamps.")

    max_horizon = max(horizons)
    event_rows: list[dict[str, Any]] = []
    linked_episode_ids: set[int] = set()
    lead_times: list[float] = []
    post_event_delays: list[float] = []
    horizon_hits = {horizon: 0 for horizon in horizons}

    for _, event in events.iterrows():
        event_start = event["start_time"]
        event_end = event["end_time"]
        pre_window_start = event_start - pd.Timedelta(minutes=max_horizon)
        pre_candidates = episodes[
            (episodes["start_time"] >= pre_window_start)
            & (episodes["start_time"] < event_start)
        ]
        during_candidates = episodes[
            (episodes["start_time"] >= event_start)
            & (episodes["start_time"] <= event_end)
        ]
        detected_pre_event = not pre_candidates.empty
        detected_during_event = not during_candidates.empty
        first_pre = pre_candidates.sort_values("start_time").iloc[0] if detected_pre_event else None
        first_during = during_candidates.sort_values("start_time").iloc[0] if detected_during_event else None

        lead_time = None
        if first_pre is not None:
            lead_time = (event_start - first_pre["start_time"]).total_seconds() / 60.0
            lead_times.append(float(lead_time))
            linked_episode_ids.add(int(first_pre["episode_id"]))

        post_delay = None
        if first_during is not None:
            post_delay = (first_during["start_time"] - event_start).total_seconds() / 60.0
            post_event_delays.append(float(post_delay))
            linked_episode_ids.add(int(first_during["episode_id"]))

        horizon_flags = {}
        for horizon in horizons:
            hit = bool(
                (
                    (episodes["start_time"] >= event_start - pd.Timedelta(minutes=horizon))
                    & (episodes["start_time"] < event_start)
                ).any()
            )
            horizon_flags[f"detected_within_{horizon}_min"] = hit
            if hit:
                horizon_hits[horizon] += 1

        event_rows.append(
            {
                "event_id": event["event_id"],
                "start_time": event_start,
                "end_time": event_end,
                "detected_pre_event": detected_pre_event,
                "detected_during_event": detected_during_event,
                "detected_any": detected_pre_event or detected_during_event,
                "lead_time_minutes": lead_time,
                "post_event_detection_delay_minutes": post_delay,
                **horizon_flags,
            }
        )

        linked_window_start = event_start - pd.Timedelta(minutes=max_horizon)
        linked = episodes[
            (episodes["start_time"] >= linked_window_start)
            & (episodes["start_time"] <= event_end)
        ]
        linked_episode_ids.update(int(value) for value in linked.get("episode_id", pd.Series(dtype=int)).tolist())

    event_results = pd.DataFrame(event_rows)
    all_episode_ids = set(int(value) for value in episodes.get("episode_id", pd.Series(dtype=int)).tolist())
    false_episode_ids = all_episode_ids - linked_episode_ids
    if episodes.empty:
        episodes_out = episodes.copy()
        episodes_out["linked_to_event"] = pd.Series(dtype=bool)
        episodes_out["false_alarm_episode"] = pd.Series(dtype=bool)
    else:
        episodes_out = episodes.copy()
        episodes_out["linked_to_event"] = episodes_out["episode_id"].astype(int).isin(linked_episode_ids)
        episodes_out["false_alarm_episode"] = episodes_out["episode_id"].astype(int).isin(false_episode_ids)

    failure_seconds = 0.0
    for _, event in events.iterrows():
        overlap_start = max(event["start_time"], eval_start)
        overlap_end = min(event["end_time"], eval_end)
        if overlap_end > overlap_start:
            failure_seconds += (overlap_end - overlap_start).total_seconds()
    evaluation_seconds = (eval_end - eval_start).total_seconds()
    operating_days = max((evaluation_seconds - failure_seconds) / 86400.0, 1e-12)
    alert_minutes = float(episodes_out.get("duration_minutes", pd.Series(dtype=float)).sum()) if not episodes_out.empty else 0.0

    summary = {
        "event_count": int(len(events)),
        "detected_event_count": int(event_results["detected_any"].sum()),
        "pre_event_detected_count": int(event_results["detected_pre_event"].sum()),
        "during_event_detected_count": int(event_results["detected_during_event"].sum()),
        "event_detection_rate": round(float(event_results["detected_any"].mean()), 6),
        "pre_event_detection_rate": round(float(event_results["detected_pre_event"].mean()), 6),
        "false_alarm_episode_count": int(len(false_episode_ids)),
        "false_alarms_per_operating_day": round(float(len(false_episode_ids) / operating_days), 6),
        "alert_episode_count": int(len(all_episode_ids)),
        "alert_episodes_per_operating_day": round(float(len(all_episode_ids) / operating_days), 6),
        "episode_precision": round(float(len(linked_episode_ids) / max(len(all_episode_ids), 1)), 6),
        "median_lead_time_minutes": round(float(np.median(lead_times)), 6) if lead_times else None,
        "iqr_lead_time_minutes": round(float(np.percentile(lead_times, 75) - np.percentile(lead_times, 25)), 6)
        if lead_times
        else None,
        "median_post_event_detection_delay_minutes": round(float(np.median(post_event_delays)), 6)
        if post_event_delays
        else None,
        "mean_alert_duration_minutes": round(float(episodes_out["duration_minutes"].mean()), 6)
        if not episodes_out.empty
        else 0.0,
        "median_alert_duration_minutes": round(float(episodes_out["duration_minutes"].median()), 6)
        if not episodes_out.empty
        else 0.0,
        "percent_time_in_alarm": round(float((alert_minutes * 60.0) / evaluation_seconds), 6),
        "operating_days_excluding_failure_windows": round(float(operating_days), 6),
    }
    for horizon, count in horizon_hits.items():
        summary[f"event_detection_rate_within_{horizon}_min"] = round(float(count / len(events)), 6)

    lead_distribution = event_results[
        [
            "event_id",
            "start_time",
            "end_time",
            "detected_pre_event",
            "detected_during_event",
            "detected_any",
            "lead_time_minutes",
            "post_event_detection_delay_minutes",
        ]
    ].copy()
    return summary, event_results, episodes_out
