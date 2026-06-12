from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from metropt3_loader import SIGNAL_COLUMNS, load_metropt3_frame, metropt3_failure_windows


def _metropt_frame(timestamps: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame({"timestamp": timestamps})
    for index, column in enumerate(SIGNAL_COLUMNS):
        frame[column] = 1.0 + index
    return frame


def test_failure_windows_are_source_traceable_and_chronological() -> None:
    windows = metropt3_failure_windows()

    assert len(windows) == 4
    assert windows["event_id"].is_unique
    assert (windows["end_time"] >= windows["start_time"]).all()
    assert windows["source_file"].str.contains("Data Description_Metro.pdf").all()
    assert windows.iloc[0]["start_time"] == pd.Timestamp("2020-04-18 00:00:00")


def test_loader_rejects_duplicate_timestamps(tmp_path: Path) -> None:
    path = tmp_path / "metropt.csv"
    _metropt_frame(["2020-02-01 00:00:00", "2020-02-01 00:00:00"]).to_csv(path, index=False)

    with pytest.raises(ValueError, match="duplicate timestamps"):
        load_metropt3_frame(path)


def test_loader_rejects_backwards_timestamps(tmp_path: Path) -> None:
    path = tmp_path / "metropt.csv"
    _metropt_frame(["2020-02-01 00:00:10", "2020-02-01 00:00:00"]).to_csv(path, index=False)

    with pytest.raises(ValueError, match="strictly chronological"):
        load_metropt3_frame(path)
