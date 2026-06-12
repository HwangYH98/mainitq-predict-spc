from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from data import ID_COLUMNS, LEAKAGE_COLUMNS, TARGET_COLUMN, load_data, preprocess_data
from experiment_run import PROJECT_ROOT, relative_to_project, sha256_file


DATA_PATH = PROJECT_ROOT / "data" / "ai4i2020.csv"
REQUIRED_COLUMNS = [
    "UDI",
    "Product ID",
    "Type",
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]",
    TARGET_COLUMN,
    *LEAKAGE_COLUMNS,
]


def validate_ai4i_dataset(path: str | Path = DATA_PATH) -> dict[str, Any]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"AI4I dataset not found: {csv_path}")

    raw_df = load_data(csv_path)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in raw_df.columns]
    if missing_columns:
        raise ValueError(f"AI4I dataset is missing required columns: {missing_columns}")

    X, y = preprocess_data(raw_df)
    remaining_forbidden = [column for column in [TARGET_COLUMN, *ID_COLUMNS, *LEAKAGE_COLUMNS] if column in X.columns]
    if remaining_forbidden:
        raise ValueError(f"Forbidden target/id/leakage columns remain after preprocessing: {remaining_forbidden}")

    class_counts = y.value_counts().sort_index().to_dict()
    return {
        "dataset": "AI4I 2020",
        "path": relative_to_project(csv_path),
        "sha256": sha256_file(csv_path),
        "rows": int(len(raw_df)),
        "columns": list(raw_df.columns),
        "column_count": int(len(raw_df.columns)),
        "target_column": TARGET_COLUMN,
        "target_class_counts": {str(key): int(value) for key, value in class_counts.items()},
        "id_columns_present": [column for column in ID_COLUMNS if column in raw_df.columns],
        "leakage_columns_present": [column for column in LEAKAGE_COLUMNS if column in raw_df.columns],
        "removed_columns": [TARGET_COLUMN, *ID_COLUMNS, *LEAKAGE_COLUMNS],
        "feature_columns_after_preprocessing": list(X.columns),
        "feature_column_count": int(X.shape[1]),
        "preprocessing_checks": {
            "target_removed_from_features": TARGET_COLUMN not in X.columns,
            "id_columns_removed_from_features": not any(column in X.columns for column in ID_COLUMNS),
            "leakage_columns_removed_from_features": not any(column in X.columns for column in LEAKAGE_COLUMNS),
            "type_one_hot_encoded": any(column.startswith("type_") for column in X.columns),
        },
    }


def assert_expected_ai4i_hash(expected_sha256: str, path: str | Path = DATA_PATH) -> None:
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ValueError(f"AI4I SHA-256 mismatch: expected {expected_sha256}, got {actual}")


def dataframe_has_forbidden_columns(df: pd.DataFrame) -> bool:
    return any(column in df.columns for column in [TARGET_COLUMN, *ID_COLUMNS, *LEAKAGE_COLUMNS])
