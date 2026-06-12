from __future__ import annotations

import pandas as pd

from data import ID_COLUMNS, LEAKAGE_COLUMNS, TARGET_COLUMN, preprocess_data
from data_integrity import dataframe_has_forbidden_columns, validate_ai4i_dataset


def test_validate_ai4i_dataset_records_hash_and_preprocessing_contract() -> None:
    manifest = validate_ai4i_dataset()

    assert manifest["rows"] == 10000
    assert manifest["sha256"]
    assert manifest["target_column"] == TARGET_COLUMN
    assert manifest["preprocessing_checks"]["target_removed_from_features"] is True
    assert manifest["preprocessing_checks"]["id_columns_removed_from_features"] is True
    assert manifest["preprocessing_checks"]["leakage_columns_removed_from_features"] is True
    assert manifest["preprocessing_checks"]["type_one_hot_encoded"] is True


def test_forbidden_columns_are_removed_by_preprocess_data() -> None:
    df = pd.DataFrame(
        {
            "UDI": [1, 2],
            "Product ID": ["A", "B"],
            "Type": ["L", "M"],
            "Air temperature [K]": [300.0, 301.0],
            "Process temperature [K]": [310.0, 311.0],
            "Rotational speed [rpm]": [1500, 1600],
            "Torque [Nm]": [40.0, 41.0],
            "Tool wear [min]": [10, 20],
            "Machine failure": [0, 1],
            "TWF": [0, 0],
            "HDF": [0, 1],
            "PWF": [0, 0],
            "OSF": [0, 0],
            "RNF": [0, 0],
        }
    )

    X, _ = preprocess_data(df)

    assert not dataframe_has_forbidden_columns(X)
    assert TARGET_COLUMN not in X.columns
    assert all(column not in X.columns for column in ID_COLUMNS + LEAKAGE_COLUMNS)
