from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from experiment_run import PROJECT_ROOT, relative_to_project, sha256_file


DEFAULT_METROPT3_ROOT = PROJECT_ROOT / "data_external" / "metropt3"
DEFAULT_METROPT3_CSV = DEFAULT_METROPT3_ROOT / "extracted" / "MetroPT3(AirCompressor).csv"
DEFAULT_METROPT3_DESCRIPTION = DEFAULT_METROPT3_ROOT / "extracted" / "Data Description_Metro.pdf"

TIMESTAMP_COLUMN = "timestamp"
SIGNAL_COLUMNS = [
    "TP2",
    "TP3",
    "H1",
    "DV_pressure",
    "Reservoirs",
    "Oil_temperature",
    "Motor_current",
    "Caudal_impulses",
]
DIGITAL_COLUMNS = [
    "COMP",
    "DV_eletric",
    "Towers",
    "MPG",
    "LPS",
    "Pressure_switch",
    "Oil_level",
]


@dataclass(frozen=True)
class MetroPT3Dataset:
    frame: pd.DataFrame
    failure_windows: pd.DataFrame
    manifest: dict[str, Any]


def metropt3_failure_windows() -> pd.DataFrame:
    """Return the published MetroPT-3 failure report windows from the data description PDF."""
    rows = [
        {
            "event_id": "metropt3_failure_001",
            "report_number": "#1",
            "start_time": "2020-04-18 00:00:00",
            "end_time": "2020-04-18 23:59:00",
            "failure": "Air leak",
            "severity": "High stress",
            "report_note": "",
        },
        {
            "event_id": "metropt3_failure_002",
            "report_number": "#2",
            "start_time": "2020-05-29 23:30:00",
            "end_time": "2020-05-30 06:00:00",
            "failure": "Air leak",
            "severity": "High stress",
            "report_note": "Maintenance on 30Apr at 12:00 as written in source PDF.",
        },
        {
            "event_id": "metropt3_failure_003",
            "report_number": "#3",
            "start_time": "2020-06-05 10:00:00",
            "end_time": "2020-06-07 14:30:00",
            "failure": "Air leak",
            "severity": "High stress",
            "report_note": "Maintenance on 8Jun at 16:00.",
        },
        {
            "event_id": "metropt3_failure_004",
            "report_number": "#4",
            "start_time": "2020-07-15 14:30:00",
            "end_time": "2020-07-15 19:00:00",
            "failure": "Air leak",
            "severity": "High stress",
            "report_note": "Maintenance on 16Jul at 00:00.",
        },
    ]
    frame = pd.DataFrame(rows)
    frame["start_time"] = pd.to_datetime(frame["start_time"])
    frame["end_time"] = pd.to_datetime(frame["end_time"])
    frame["source_file"] = relative_to_project(DEFAULT_METROPT3_DESCRIPTION)
    frame["source_table"] = "Failure Information table in Data Description_Metro.pdf"
    return frame


def find_metropt3_csv(root: str | Path = DEFAULT_METROPT3_ROOT) -> Path:
    root_path = Path(root)
    if DEFAULT_METROPT3_CSV.exists():
        return DEFAULT_METROPT3_CSV
    candidates = sorted(root_path.rglob("*.csv")) if root_path.exists() else []
    if not candidates:
        raise FileNotFoundError(f"MetroPT-3 CSV not found under {root_path}")
    return candidates[0]


def load_metropt3_frame(
    csv_path: str | Path = DEFAULT_METROPT3_CSV,
    max_rows: int | None = None,
) -> pd.DataFrame:
    csv_file = Path(csv_path)
    if not csv_file.exists():
        csv_file = find_metropt3_csv(csv_file.parent)
    read_kwargs = {"nrows": max_rows} if max_rows else {}
    frame = pd.read_csv(csv_file, **read_kwargs)
    if TIMESTAMP_COLUMN not in frame.columns:
        raise ValueError("MetroPT-3 CSV must contain a timestamp column.")

    frame = frame.copy()
    frame[TIMESTAMP_COLUMN] = pd.to_datetime(frame[TIMESTAMP_COLUMN], errors="coerce")
    if frame[TIMESTAMP_COLUMN].isna().any():
        raise ValueError("MetroPT-3 CSV contains invalid timestamps.")
    if frame[TIMESTAMP_COLUMN].duplicated().any():
        raise ValueError("MetroPT-3 CSV contains duplicate timestamps.")
    if not frame[TIMESTAMP_COLUMN].is_monotonic_increasing:
        raise ValueError("MetroPT-3 timestamps must be strictly chronological.")

    missing_signals = [column for column in SIGNAL_COLUMNS if column not in frame.columns]
    if missing_signals:
        raise ValueError(f"MetroPT-3 CSV is missing signal columns: {missing_signals}")

    for column in SIGNAL_COLUMNS + [column for column in DIGITAL_COLUMNS if column in frame.columns]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[SIGNAL_COLUMNS].isna().any().any():
        raise ValueError("MetroPT-3 signal columns contain non-numeric or missing values.")

    if "Unnamed: 0" in frame.columns:
        frame = frame.drop(columns=["Unnamed: 0"])
    return frame


def build_dataset_manifest(
    frame: pd.DataFrame,
    csv_path: str | Path = DEFAULT_METROPT3_CSV,
    description_path: str | Path = DEFAULT_METROPT3_DESCRIPTION,
) -> dict[str, Any]:
    csv_file = Path(csv_path)
    description_file = Path(description_path)
    timestamp_deltas = frame[TIMESTAMP_COLUMN].diff().dropna().dt.total_seconds()
    return {
        "dataset_id": "metropt3",
        "dataset_name": "UCI MetroPT-3 Air Compressor",
        "source_scope": "public timestamped compressor time series with company failure reports",
        "csv_path": relative_to_project(csv_file),
        "csv_sha256": sha256_file(csv_file) if csv_file.exists() else None,
        "description_path": relative_to_project(description_file),
        "description_sha256": sha256_file(description_file) if description_file.exists() else None,
        "rows": int(len(frame)),
        "timestamp_start": frame[TIMESTAMP_COLUMN].min().isoformat(),
        "timestamp_end": frame[TIMESTAMP_COLUMN].max().isoformat(),
        "timestamp_monotonic_increasing": bool(frame[TIMESTAMP_COLUMN].is_monotonic_increasing),
        "duplicate_timestamp_count": int(frame[TIMESTAMP_COLUMN].duplicated().sum()),
        "median_sample_interval_seconds": float(timestamp_deltas.median()) if not timestamp_deltas.empty else None,
        "signal_columns": SIGNAL_COLUMNS,
        "digital_columns": [column for column in DIGITAL_COLUMNS if column in frame.columns],
        "claim_boundary": "Public benchmark validation only; not real factory deployment or cost reduction proof.",
    }


def load_metropt3_dataset(
    csv_path: str | Path = DEFAULT_METROPT3_CSV,
    max_rows: int | None = None,
) -> MetroPT3Dataset:
    frame = load_metropt3_frame(csv_path=csv_path, max_rows=max_rows)
    csv_file = Path(csv_path)
    if not csv_file.exists():
        csv_file = find_metropt3_csv(csv_file.parent)
    failure_windows = metropt3_failure_windows()
    manifest = build_dataset_manifest(frame, csv_path=csv_file)
    manifest["failure_event_count"] = int(len(failure_windows))
    manifest["failure_windows"] = json.loads(failure_windows.to_json(orient="records", date_format="iso"))
    return MetroPT3Dataset(frame=frame, failure_windows=failure_windows, manifest=manifest)
