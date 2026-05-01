from pathlib import Path
import re

import pandas as pd
from sklearn.model_selection import train_test_split


TARGET_COLUMN = "Machine failure"
ID_COLUMNS = ["UDI", "Product ID"]

# These columns are specific failure labels in the AI4I dataset.
# They are removed because they can reveal the answer too directly.
LEAKAGE_COLUMNS = ["TWF", "HDF", "PWF", "OSF", "RNF"]


def load_data(csv_path: str | Path) -> pd.DataFrame:
    """Load the AI4I CSV file."""
    csv_path = Path(csv_path)

    # Do not hide this error. If the dataset is missing, the user should know
    # exactly where to place the file before running the baseline again.
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {csv_path}. "
            "Please save the AI4I 2020 CSV file as data/ai4i2020.csv."
        )

    return pd.read_csv(csv_path)


def _clean_feature_name(column_name: str) -> str:
    """Make column names simple and safe for machine learning libraries."""
    cleaned = re.sub(r"[^0-9a-zA-Z_]+", "_", column_name)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned.lower()


def preprocess_features(
    df: pd.DataFrame,
    expected_columns: list[str] | None = None,
) -> pd.DataFrame:
    """
    Convert raw sensor rows into model-ready input features.

    This is used by both training and the Stage 7-lite CSV upload demo. When
    expected_columns is provided, the output is aligned to the training schema.
    """
    columns_to_drop = []
    if TARGET_COLUMN in df.columns:
        columns_to_drop.append(TARGET_COLUMN)
    columns_to_drop += [column for column in ID_COLUMNS if column in df.columns]
    columns_to_drop += [column for column in LEAKAGE_COLUMNS if column in df.columns]

    X = df.drop(columns=columns_to_drop).copy()

    if "Type" not in X.columns:
        raise ValueError("Column 'Type' is missing, so one-hot encoding cannot be applied.")

    # Machine learning models need numbers. One-hot encoding changes Type into
    # columns such as type_h, type_l, and type_m.
    X = pd.get_dummies(X, columns=["Type"], dtype=int)
    X.columns = [_clean_feature_name(column_name) for column_name in X.columns]

    if expected_columns is not None:
        missing_sensor_columns = [
            column
            for column in expected_columns
            if column not in X.columns and not column.startswith("type_")
        ]
        if missing_sensor_columns:
            missing_text = ", ".join(missing_sensor_columns)
            raise ValueError(
                "Uploaded data is missing required sensor columns after preprocessing: "
                f"{missing_text}"
            )

        # Missing one-hot Type columns simply mean that category did not appear
        # in the uploaded sample. Add them as 0 so the model schema still fits.
        for column in expected_columns:
            if column not in X.columns:
                X[column] = 0

        X = X[list(expected_columns)]

    return X


def preprocess_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Convert the raw dataset into model-ready X and y.

    X means input features.
    y means the answer column that the model tries to predict.
    """
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"Target column '{TARGET_COLUMN}' is missing from the dataset.")

    # Machine failure is already 0 or 1, but astype(int) makes that explicit.
    y = df[TARGET_COLUMN].astype(int)
    X = preprocess_features(df)

    return X, y


def prepare_train_test_data(
    csv_path: str | Path,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.DataFrame]:
    """
    Load, preprocess, and split the data.

    stratify=y keeps the failure/non-failure ratio similar in train and test data.
    """
    raw_df = load_data(csv_path)
    X, y = preprocess_data(raw_df)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        stratify=y,
        random_state=random_state,
    )

    # raw_df is returned so train_baseline.py can save readable prediction rows.
    return X_train, X_test, y_train, y_test, raw_df
