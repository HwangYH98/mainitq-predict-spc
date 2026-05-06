# Company CSV Preprocessing Report

## Scope

This report describes company CSV mapping and quality checks for prediction. It does not prove real company-data model performance unless labels are supplied and evaluated separately.

- Rows: 3
- Source columns: 6
- Quality score: 100.0
- Quality status: High

## Column Mapping

| Canonical column | Source column | Unit conversion |
|---|---|---|
| Type | product_grade |  |
| Air temperature [K] | air_temp_c | Celsius -> Kelvin |
| Process temperature [K] | process_temp_c | Celsius -> Kelvin |
| Rotational speed [rpm] | rpm | No conversion |
| Torque [Nm] | motor_torque_nm | No conversion |
| Tool wear [min] | wear_minutes | No conversion |

## Quality Issues

| Column | Issue | Severity | Affected rows | Detail |
|---|---|---|---:|---|
| all | no_blocking_issue | info | 0 | No blocking data-quality issue was found. |