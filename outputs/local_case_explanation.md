# Local XGBoost Failure Prediction Explanation

## Selected Case

- Test row index: `6497`
- Actual Machine failure: `1`
- XGBoost prediction using threshold 0.87: `1`
- XGBoost failure probability: `0.9936`

## Raw Sensor Values

- UDI: `6498`
- Product ID: `L53677`
- Type: `L`
- Air temperature [K]: `300.8`
- Process temperature [K]: `309.9`
- Rotational speed [rpm]: `1312`
- Torque [Nm]: `65.3`
- Tool wear [min]: `192`
- Machine failure: `1`

## Top SHAP Factors

Positive SHAP values push the model toward failure. Negative SHAP values push the model toward normal.

- `torque_nm` = `65.3` has SHAP `3.9352`, pushing toward **failure**.
- `rotational_speed_rpm` = `1312.0` has SHAP `0.8857`, pushing toward **failure**.
- `air_temperature_k` = `300.8` has SHAP `-0.6725`, pushing toward **normal**.
- `tool_wear_min` = `192.0` has SHAP `0.3529`, pushing toward **failure**.
- `process_temperature_k` = `309.9` has SHAP `0.2660`, pushing toward **failure**.

## Presentation Memo

This example connects the model output to sensor-level evidence. For the next stage, these top SHAP factors can be converted into a grounded LLM prompt, but no LLM is used in Stage 4.