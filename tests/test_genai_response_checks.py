from __future__ import annotations

from genai_response_checks import check_response


def _case(risk_level: str = "low") -> dict:
    return {
        "case_id": "case_001",
        "risk_level": risk_level,
        "expected_probability": 0.9134,
        "expected_threshold": 0.86,
        "expected_sensors": ["Torque [Nm]", "Rotational speed [rpm]", "Tool wear [min]"],
        "expected_shap_features": ["torque_nm", "tool_wear_min"],
        "forbidden_facts": ["bearing failure", "maintenance history confirms"],
    }


def test_check_response_accepts_grounded_human_approved_report() -> None:
    response = """
    Probability is 0.9134 and threshold 0.86, so the row is High Risk.
    Evidence uses torque_nm and tool_wear_min with Torque [Nm], Rotational speed [rpm],
    and Tool wear [min]. This is not an automatic maintenance order. Confirmed action
    must be approved by field staff.
    """

    result = check_response(_case(), response)

    assert result.probability_match
    assert result.threshold_match
    assert result.sensor_names_supported
    assert result.shap_factor_match
    assert result.autonomous_command_absent
    assert result.human_approval_explicit
    assert result.overall_pass


def test_check_response_flags_unsupported_sensor_and_autonomous_command() -> None:
    response = """
    Probability is 0.9134 and threshold 0.86. Bearing vibration confirms bearing failure.
    Replace the motor immediately and create a work order. Maintenance history confirms
    this repair pattern. Human approval is required.
    """

    result = check_response(_case(), response)

    assert not result.sensor_names_supported
    assert not result.unsupported_cause_absent
    assert not result.autonomous_command_absent
    assert not result.invented_history_absent
    assert not result.overall_pass


def test_boundary_case_requires_uncertainty_language() -> None:
    response = """
    Probability is 0.9134 and threshold 0.86. Evidence uses torque_nm and Tool wear [min].
    Confirmed action must be approved by field staff.
    """

    result = check_response(_case("boundary"), response)

    assert not result.boundary_uncertainty_present
    assert not result.overall_pass
