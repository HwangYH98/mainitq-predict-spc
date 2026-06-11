from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"
DATA_EXTERNAL_DIR = PROJECT_ROOT / "data_external" / "scania_component_x"

SCANIA_MODEL_ARTIFACT = OUTPUT_DIR / "scania_cost_optimized_model.joblib"
SCANIA_PRODUCT_PREDICTIONS_CSV = OUTPUT_DIR / "scania_product_predictions.csv"
SCANIA_PRODUCT_PRIORITY_CSV = OUTPUT_DIR / "scania_product_priority_queue.csv"

SCANIA_REQUIRED_COLUMNS = {"vehicle_id", "time_step"}
SCANIA_CLASS_LABELS = {
    0: "고장 window 밖 또는 수리 없음",
    1: "고장 48~24 time units 전",
    2: "고장 24~12 time units 전",
    3: "고장 12~6 time units 전",
    4: "고장 6~0 time units 전",
}


def looks_like_scania_csv(df: pd.DataFrame) -> bool:
    """Return True when a CSV resembles SCANIA Component X readout data."""
    columns = {str(column) for column in df.columns}
    if not SCANIA_REQUIRED_COLUMNS.issubset(columns):
        return False
    anonymized_feature_count = sum(
        1
        for column in columns
        if "_" in column and column.split("_", 1)[0].isdigit() and column.split("_", 1)[1].isdigit()
    )
    return anonymized_feature_count >= 10


def detect_input_schema(df: pd.DataFrame) -> str:
    """Classify an uploaded CSV into the supported product schemas."""
    if looks_like_scania_csv(df):
        return "scania"
    return "ai4i"


def load_scania_artifact(path: Path = SCANIA_MODEL_ARTIFACT) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            "SCANIA 모델 파일이 없습니다. 먼저 다음 명령으로 모델을 생성하세요: "
            ".\\.venv\\Scripts\\python.exe src\\scania_official_cost_validation.py"
        )
    artifact = joblib.load(path)
    required_keys = {"model", "feature_columns", "raw_feature_columns", "official_cost_matrix"}
    missing = sorted(required_keys - set(artifact))
    if missing:
        raise ValueError(f"SCANIA 모델 파일 형식이 올바르지 않습니다. 누락 항목: {', '.join(missing)}")
    return artifact


def _prepare_scania_features(df: pd.DataFrame, artifact: dict[str, Any]) -> pd.DataFrame:
    raw_feature_columns = list(artifact["raw_feature_columns"])
    categorical_columns = set(artifact.get("categorical_columns", []))
    final_feature_columns = list(artifact["feature_columns"])
    fill_values = artifact.get("fill_values", {})

    frame = df.copy()
    if "vehicle_id" in frame.columns and "time_step" in frame.columns:
        frame = (
            frame.sort_values(["vehicle_id", "time_step"])
            .groupby("vehicle_id", as_index=False)
            .tail(1)
            .reset_index(drop=True)
        )

    feature_data = {
        column: frame[column] if column in frame.columns else pd.Series(np.nan, index=frame.index)
        for column in raw_feature_columns
    }
    features = pd.DataFrame(feature_data, index=frame.index)

    for column in raw_feature_columns:
        if column in categorical_columns:
            features[column] = features[column].astype(str).fillna("nan")
        else:
            features[column] = pd.to_numeric(features[column], errors="coerce")

    encoded = pd.get_dummies(features, columns=[c for c in raw_feature_columns if c in categorical_columns], dummy_na=True)
    for column in final_feature_columns:
        if column not in encoded.columns:
            encoded[column] = fill_values.get(column, 0)
    encoded = encoded[final_feature_columns]
    encoded = encoded.replace([np.inf, -np.inf], np.nan)
    encoded = encoded.fillna(pd.Series(fill_values)).fillna(0)
    return encoded


def _recommendation(predicted_class: int, failure_probability: float) -> str:
    if predicted_class >= 4:
        return "즉시 정비 검토가 필요한 임박 고장 위험입니다."
    if predicted_class >= 2:
        return "정비 우선순위를 높이고 다음 점검 일정에 반영하세요."
    if predicted_class == 1:
        return "고장 window 진입 가능성이 있어 추세를 추적하세요."
    if failure_probability >= 0.5:
        return "모델 확률은 높지만 비용 최적화 기준에서는 즉시 조치 대상이 아닐 수 있습니다."
    return "정상 범위로 보이며 정기 모니터링을 유지하세요."


def predict_scania_csv(
    df: pd.DataFrame,
    *,
    write_outputs: bool = True,
    artifact_path: Path = SCANIA_MODEL_ARTIFACT,
) -> dict[str, Any]:
    """Predict SCANIA Component X official classes with the saved cost-optimized model."""
    if not looks_like_scania_csv(df):
        raise ValueError("SCANIA CSV 형식이 아닙니다. vehicle_id, time_step, 익명화 센서 컬럼이 필요합니다.")

    artifact = load_scania_artifact(artifact_path)
    model = artifact["model"]
    cost_matrix = np.asarray(artifact["official_cost_matrix"], dtype=float)
    features = _prepare_scania_features(df, artifact)
    probabilities = model.predict_proba(features)
    classes = np.asarray(model.classes_, dtype=int)

    probability_matrix = np.zeros((probabilities.shape[0], 5), dtype=float)
    for index, class_id in enumerate(classes):
        probability_matrix[:, class_id] = probabilities[:, index]

    expected_cost = probability_matrix @ cost_matrix
    cost_optimized_class = expected_cost.argmin(axis=1).astype(int)
    argmax_class = probability_matrix.argmax(axis=1).astype(int)
    failure_window_probability = probability_matrix[:, 1:].sum(axis=1)

    base = df.copy()
    base = (
        base.sort_values(["vehicle_id", "time_step"])
        .groupby("vehicle_id", as_index=False)
        .tail(1)
        .reset_index(drop=True)
    )
    result_df = base[["vehicle_id", "time_step"]].copy()
    result_df["input_row"] = result_df.index
    result_df["engine_profile"] = "scania"
    result_df["score_method"] = "SCANIA 공식 비용 최적화 모델"
    result_df["interpretation_note"] = (
        "SCANIA Component X 공식 class 0~4와 official cost matrix를 사용하는 전용 모델입니다. "
        "AI4I 기본 모델 결과와 직접 비교하지 마세요."
    )
    result_df["predicted_class"] = cost_optimized_class
    result_df["argmax_class"] = argmax_class
    result_df["class_meaning"] = [SCANIA_CLASS_LABELS[int(value)] for value in cost_optimized_class]
    result_df["failure_window_probability"] = np.round(failure_window_probability, 6)
    result_df["calibrated_probability"] = np.round(failure_window_probability, 6)
    result_df["expected_cost_min"] = np.round(expected_cost.min(axis=1), 4)
    result_df["risk_status"] = np.where(cost_optimized_class > 0, "High Risk", "Normal")
    result_df["risk_priority_score"] = np.round(
        failure_window_probability * 70 + cost_optimized_class * 12 + np.minimum(expected_cost.min(axis=1), 500) / 25,
        2,
    )
    result_df["recommendation"] = [
        _recommendation(int(predicted), float(probability))
        for predicted, probability in zip(cost_optimized_class, failure_window_probability)
    ]
    for class_id in range(5):
        result_df[f"probability_class_{class_id}"] = np.round(probability_matrix[:, class_id], 6)

    priority_df = result_df.sort_values(
        ["risk_priority_score", "failure_window_probability"],
        ascending=[False, False],
    ).reset_index(drop=True)
    priority_df.insert(0, "priority_rank", range(1, len(priority_df) + 1))

    if write_outputs:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        result_df.to_csv(SCANIA_PRODUCT_PREDICTIONS_CSV, index=False, encoding="utf-8-sig")
        priority_df.to_csv(SCANIA_PRODUCT_PRIORITY_CSV, index=False, encoding="utf-8-sig")

    high_risk_count = int((result_df["risk_status"] == "High Risk").sum())
    return {
        "schema": "scania",
        "result_df": result_df,
        "priority_df": priority_df,
        "quality_df": pd.DataFrame(),
        "quality_report": {
            "quality_score": 1.0,
            "quality_status": "OK",
            "row_count": int(len(result_df)),
            "note": "SCANIA 전용 스키마로 처리되었습니다.",
        },
        "policy_id": "official_cost_optimized",
        "policy": {"threshold": 0.5, "name": "SCANIA official cost optimized"},
        "engine_profile": "scania",
        "score_method": "SCANIA 공식 비용 최적화 모델",
        "high_risk_count": high_risk_count,
        "max_probability": float(result_df["failure_window_probability"].max()) if len(result_df) else 0.0,
        "output_path": SCANIA_PRODUCT_PREDICTIONS_CSV,
    }


def sample_scania_dataframe(row_count: int = 20) -> pd.DataFrame:
    """Return a small SCANIA-like sample CSV for UI smoke tests and sample export."""
    validation_path = DATA_EXTERNAL_DIR / "validation_operational_readouts.csv"
    if validation_path.exists():
        collected: list[pd.DataFrame] = []
        seen: set[Any] = set()
        for chunk in pd.read_csv(validation_path, chunksize=50000):
            final_rows = (
                chunk.sort_values(["vehicle_id", "time_step"])
                .groupby("vehicle_id", as_index=False)
                .tail(1)
                .reset_index(drop=True)
            )
            final_rows = final_rows[~final_rows["vehicle_id"].isin(seen)]
            if not final_rows.empty:
                collected.append(final_rows)
                seen.update(final_rows["vehicle_id"].tolist())
            if len(seen) >= row_count:
                break
        if collected:
            return pd.concat(collected, ignore_index=True).head(row_count)

    if SCANIA_MODEL_ARTIFACT.exists():
        raw_feature_columns = list(load_scania_artifact()["raw_feature_columns"])
    else:
        # Keep CI and UI sample export independent from the optional SCANIA model artifact.
        raw_feature_columns = [f"{group}_{sensor}" for group in range(3) for sensor in range(4)]

    columns = ["vehicle_id", "time_step", *raw_feature_columns]
    rows = []
    for index in range(max(1, row_count)):
        row = {column: float((index + 1) * (position + 1)) for position, column in enumerate(columns)}
        row["vehicle_id"] = index
        row["time_step"] = float(index + 1)
        rows.append(row)
    return pd.DataFrame(rows)
