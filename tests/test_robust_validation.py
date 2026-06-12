from __future__ import annotations

import numpy as np
import pandas as pd

import robust_validation


def _synthetic_data() -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(7)
    y = np.array([0] * 96 + [1] * 24)
    order = rng.permutation(len(y))
    y = y[order]
    signal = y + rng.normal(0, 0.15, size=len(y))
    X = pd.DataFrame(
        {
            "sensor_signal": signal,
            "sensor_noise": rng.normal(0, 1, size=len(y)),
            "type_l": (rng.random(len(y)) > 0.5).astype(int),
        }
    )
    return X, pd.Series(y)


def test_run_repeated_validation_creates_fold_rows_and_oof_predictions(monkeypatch) -> None:
    X, y = _synthetic_data()

    monkeypatch.setattr(robust_validation, "load_data", lambda path: pd.DataFrame())
    monkeypatch.setattr(robust_validation, "preprocess_data", lambda raw_df: (X, y))

    result = robust_validation.run_repeated_validation(
        repeats=1,
        folds=3,
        bootstrap_iterations=10,
        random_state=11,
    )

    folds_df = result["folds"]
    predictions_df = result["predictions"]

    assert len(folds_df) == 3
    assert len(predictions_df) == len(y)
    assert {"repeat", "fold", "fold_seed", "y_true", "raw_probability", "prediction"} <= set(predictions_df.columns)
    assert predictions_df["source_row_index"].value_counts().nunique() == 1
    assert predictions_df["source_row_index"].value_counts().iloc[0] == 1
    assert result["summary"]["outer_fold_count"] == 3
    assert result["summary"]["bootstrap"]["iterations"] == 10
    assert "fold_metric_summary" in result["summary"]
    assert folds_df["selected_threshold"].between(0.05, 0.95).all()


def test_repeated_validation_is_deterministic_with_same_seed(monkeypatch) -> None:
    X, y = _synthetic_data()

    monkeypatch.setattr(robust_validation, "load_data", lambda path: pd.DataFrame())
    monkeypatch.setattr(robust_validation, "preprocess_data", lambda raw_df: (X, y))

    first = robust_validation.run_repeated_validation(repeats=1, folds=3, bootstrap_iterations=10, random_state=17)
    second = robust_validation.run_repeated_validation(repeats=1, folds=3, bootstrap_iterations=10, random_state=17)

    pd.testing.assert_frame_equal(first["folds"], second["folds"])
    pd.testing.assert_frame_equal(first["predictions"], second["predictions"])
    assert first["summary"]["bootstrap"] == second["summary"]["bootstrap"]


def test_repeated_validation_evaluates_each_row_once_per_repeat(monkeypatch) -> None:
    X, y = _synthetic_data()

    monkeypatch.setattr(robust_validation, "load_data", lambda path: pd.DataFrame())
    monkeypatch.setattr(robust_validation, "preprocess_data", lambda raw_df: (X, y))

    result = robust_validation.run_repeated_validation(
        repeats=2,
        folds=3,
        bootstrap_iterations=10,
        random_state=19,
    )

    predictions_df = result["predictions"]
    assert len(result["folds"]) == 6
    assert len(predictions_df) == len(y) * 2
    assert predictions_df.groupby(["repeat", "source_row_index"]).size().eq(1).all()
    assert predictions_df["source_row_index"].value_counts().eq(2).all()


def test_each_outer_fold_trains_new_model_and_selects_threshold_on_inner_validation(monkeypatch) -> None:
    X, y = _synthetic_data()
    fit_calls = []
    threshold_selection_lengths = []
    calibration_selection_lengths = []

    class CountingModel:
        def __init__(self, seed: int) -> None:
            self.seed = seed

        def fit(self, X_train, y_train):
            fit_calls.append({"seed": self.seed, "rows": len(y_train), "failures": int(y_train.sum())})
            return self

        def predict_proba(self, X_frame):
            signal = X_frame["sensor_signal"].to_numpy(dtype=float)
            probabilities = 1.0 / (1.0 + np.exp(-3.0 * (signal - 0.5)))
            return np.column_stack([1.0 - probabilities, probabilities])

    def fake_build_models(y_train, seed):
        return {"xgboost": CountingModel(seed)}

    original_choose = robust_validation.choose_threshold_by_validation_f1

    def recording_choose(y_valid, probabilities):
        threshold_selection_lengths.append(len(y_valid))
        return original_choose(y_valid, probabilities)

    original_calibration = robust_validation.select_calibration_by_validation_brier

    def recording_calibration(y_valid, probabilities):
        calibration_selection_lengths.append(len(y_valid))
        return original_calibration(y_valid, probabilities)

    monkeypatch.setattr(robust_validation, "load_data", lambda path: pd.DataFrame())
    monkeypatch.setattr(robust_validation, "preprocess_data", lambda raw_df: (X, y))
    monkeypatch.setattr(robust_validation, "build_models", fake_build_models)
    monkeypatch.setattr(robust_validation, "choose_threshold_by_validation_f1", recording_choose)
    monkeypatch.setattr(robust_validation, "select_calibration_by_validation_brier", recording_calibration)

    result = robust_validation.run_repeated_validation(
        repeats=1,
        folds=3,
        bootstrap_iterations=10,
        random_state=23,
    )

    assert len(fit_calls) == 3
    assert len({call["seed"] for call in fit_calls}) == 3
    assert set(threshold_selection_lengths) == {20}
    assert set(calibration_selection_lengths) == {20}
    assert set(result["folds"]["outer_test_rows"]) == {40}
