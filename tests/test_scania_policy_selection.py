from __future__ import annotations

import inspect

import numpy as np
import pandas as pd

import scania_policy_selection as policy
from scania_official_cost_validation import OFFICIAL_COST_MATRIX, ScaniaOfficialData, official_cost


def _synthetic_scania_data() -> ScaniaOfficialData:
    train_labels = [0, 1, 2, 3, 4] * 4
    validation_labels = [0, 1, 2, 3, 4]
    train = pd.DataFrame(
        {
            "vehicle_id": [f"T{i:03d}" for i in range(len(train_labels))],
            "time_step": np.arange(len(train_labels)),
            "class_label": train_labels,
            "sensor_a": np.linspace(0.0, 1.0, len(train_labels)),
            "sensor_b": np.tile([0.1, 0.4, 0.7, 1.0], 5),
        }
    )
    validation = pd.DataFrame(
        {
            "vehicle_id": [f"V{i:03d}" for i in range(len(validation_labels))],
            "time_step": np.arange(len(validation_labels)),
            "class_label": validation_labels,
            "sensor_a": np.linspace(0.2, 0.9, len(validation_labels)),
            "sensor_b": np.linspace(0.1, 0.5, len(validation_labels)),
        }
    )
    return ScaniaOfficialData(train=train, validation=validation, source_note="synthetic")


class DummyModel:
    classes_ = np.array([0, 1, 2, 3, 4])

    def predict_proba(self, X_frame):
        rows = len(X_frame)
        probabilities = np.tile(np.array([0.55, 0.1, 0.1, 0.1, 0.15]), (rows, 1))
        if rows:
            probabilities[:, 4] = np.linspace(0.15, 0.55, rows)
            probabilities[:, 0] = 1.0 - probabilities[:, 1:].sum(axis=1)
        return probabilities

    def predict(self, X_frame):
        return self.predict_proba(X_frame).argmax(axis=1)


def test_official_cost_matrix_matches_row_actual_column_predicted_contract() -> None:
    y_true = np.array([0, 1, 2, 3, 4])
    y_pred = np.array([0, 0, 1, 2, 3])
    expected = OFFICIAL_COST_MATRIX[0, 0] + OFFICIAL_COST_MATRIX[1, 0] + OFFICIAL_COST_MATRIX[2, 1] + OFFICIAL_COST_MATRIX[3, 2] + OFFICIAL_COST_MATRIX[4, 3]

    assert official_cost(y_true, y_pred) == expected


def test_constrained_expected_cost_predictions_respect_alert_cap() -> None:
    probabilities = np.tile(np.array([0.15, 0.05, 0.1, 0.2, 0.5]), (20, 1))

    predictions = policy.constrained_expected_cost_predictions(probabilities, alert_cap=0.10)

    assert (predictions > 0).mean() <= 0.10
    assert (predictions > 0).sum() <= 2


def test_policy_selection_signature_cannot_accept_official_validation_labels() -> None:
    signature = inspect.signature(policy.select_constrained_policy_from_training)

    assert "y_validation" not in signature.parameters
    assert "validation_labels" not in signature.parameters
    assert "official_validation_labels" not in signature.parameters


def test_train_select_and_evaluate_keeps_all_alert_and_uses_train_labels_for_selection(monkeypatch) -> None:
    data = _synthetic_scania_data()
    selection_label_lengths = []

    def fake_select(X_train, y_train, **kwargs):
        selection_label_lengths.append(len(y_train))
        assert len(y_train) == len(data.train)
        assert list(y_train.astype(int).unique()) == [0, 1, 2, 3, 4]
        return (
            0.20,
            pd.DataFrame(
                [
                    {
                        "selection_fold": 1,
                        "candidate_alert_cap": 0.20,
                        "official_cost": 10.0,
                        "macro_f1": 0.1,
                        "balanced_accuracy": 0.2,
                        "alert_like_rate": 0.2,
                        "selection_source": "training_fold_only",
                    }
                ]
            ),
            pd.DataFrame(
                [
                    {
                        "candidate_alert_cap": 0.20,
                        "mean_official_cost": 10.0,
                        "mean_alert_like_rate": 0.2,
                        "mean_macro_f1": 0.1,
                        "mean_balanced_accuracy": 0.2,
                        "selected": True,
                    }
                ]
            ),
        )

    monkeypatch.setattr(policy, "select_constrained_policy_from_training", fake_select)
    monkeypatch.setattr(policy, "_fit_logistic_model", lambda X, y: DummyModel())
    monkeypatch.setattr(policy, "_fit_xgboost_model", lambda X, y, random_state: DummyModel())

    result = policy.train_select_and_evaluate(data)
    metrics = result["metrics"]

    assert selection_label_lengths == [len(data.train)]
    assert "all_alert_class_4_failure_baseline" in set(metrics["strategy_id"])
    all_alert = metrics[metrics["strategy_id"] == "all_alert_class_4_failure_baseline"].iloc[0]
    constrained = metrics[metrics["strategy_id"] == "xgboost_constrained_expected_cost"].iloc[0]
    assert all_alert["alert_like_rate"] == 1.0
    assert constrained["alert_like_rate"] <= 0.20
    assert result["metadata"]["official_validation_policy"] == "Official validation labels are used only after policy selection."
