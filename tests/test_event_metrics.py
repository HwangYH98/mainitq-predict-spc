from __future__ import annotations

import pandas as pd

from evaluation_metrics import collapse_alert_episodes, evaluate_event_alert_metrics


def test_collapse_alert_episodes_merges_adjacent_alerts() -> None:
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2020-01-01 00:00:00",
                    "2020-01-01 00:01:00",
                    "2020-01-01 00:20:00",
                    "2020-01-01 00:21:00",
                ]
            ),
            "alert": [True, True, True, False],
        }
    )

    episodes = collapse_alert_episodes(frame, merge_gap=pd.Timedelta(minutes=5))

    assert len(episodes) == 2
    assert episodes.iloc[0]["duration_minutes"] == 1.0
    assert episodes.iloc[0]["row_count"] == 2


def test_event_metrics_report_lead_time_and_false_alarm_rate() -> None:
    failure_windows = pd.DataFrame(
        [
            {
                "event_id": "e1",
                "start_time": "2020-01-02 00:00:00",
                "end_time": "2020-01-02 01:00:00",
            }
        ]
    )
    alert_episodes = pd.DataFrame(
        [
            {
                "episode_id": 1,
                "start_time": "2020-01-01 23:00:00",
                "end_time": "2020-01-01 23:10:00",
                "duration_minutes": 10.0,
            },
            {
                "episode_id": 2,
                "start_time": "2020-01-03 00:00:00",
                "end_time": "2020-01-03 00:05:00",
                "duration_minutes": 5.0,
            },
        ]
    )

    summary, event_rows, episodes = evaluate_event_alert_metrics(
        failure_windows,
        alert_episodes,
        evaluation_start="2020-01-01 00:00:00",
        evaluation_end="2020-01-04 00:00:00",
        horizons_minutes=[30, 120, 1440],
    )

    assert summary["event_detection_rate"] == 1.0
    assert summary["pre_event_detection_rate"] == 1.0
    assert summary["median_lead_time_minutes"] == 60.0
    assert summary["event_detection_rate_within_30_min"] == 0.0
    assert summary["event_detection_rate_within_120_min"] == 1.0
    assert summary["false_alarm_episode_count"] == 1
    assert summary["false_alarms_per_operating_day"] > 0
    assert bool(event_rows.iloc[0]["detected_pre_event"]) is True
    assert episodes.set_index("episode_id").loc[2, "false_alarm_episode"] == True
