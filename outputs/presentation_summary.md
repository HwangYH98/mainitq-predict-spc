# 5월 11일 연구 진행 요약

## 1. 현재 완료 단계

- Stage 1 개발환경 세팅, Stage 2 AI4I 데이터 준비, Stage 3 Baseline 모델링, Stage 4-lite 해석 산출물 생성을 완료했습니다.
- Stage 5 Streamlit 결과뷰어 MVP와 Stage 6-lite Row 시뮬레이션을 완료했습니다.
- Stage 7-lite 현장 CSV 입력과 Stage 8-lite 처방 초안은 발표용 MVP 수준으로 구현했습니다.
- Stage 9 실제 적용성 정리를 추가해 현장 데이터 요구사항, 한계, 재검증 항목을 문서화했습니다.
- Stage 10-lite 운영 요약 MVP를 추가해 모델 상태, threshold, High Risk row 수, 다운로드 산출물을 한 화면에서 확인할 수 있게 했습니다.
- Stage 11~12로 AI4I 시간축 시뮬레이션, Predictive SPC chart, Gemini/OpenAI GenAI 관리자 리포트를 추가해 1차 발표 원안을 회복했습니다.
- 데이터 분할은 train `8000`개, test `2000`개이며 target은 `Machine failure`입니다.
- 현재 발표 대표 모델은 PR-AUC 기준 `xgboost`입니다.
- 현재 시스템은 완성된 상용 제품이 아니라 실사업장 확장 가능성을 보여주는 predictive maintenance PoC입니다.

## 2. Baseline 모델 비교

| Model | Precision | Recall | F1-score | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|---:|
| Logistic Regression | 0.1418 | 0.8235 | 0.2419 | 0.9069 | 0.3817 |
| XGBoost | 0.4444 | 0.8824 | 0.5911 | 0.9736 | 0.8014 |

- XGBoost는 PR-AUC `0.8014`, ROC-AUC `0.9736`로 Logistic Regression보다 발표용 대표 모델에 적합합니다.

## 3. Threshold 조정 결과

| Threshold | Precision | Recall | F1-score |
|---|---:|---:|---:|
| 0.50 (default) | 0.4444 | 0.8824 | 0.5911 |
| 0.87 (selected by F1) | 0.8197 | 0.7353 | 0.7752 |

- 기본 threshold 0.50 대비, F1 기준 선택 threshold `0.87`에서 F1-score가 `0.7752`로 개선되었습니다.
- 이 결과는 고장 예측에서 threshold가 단순 기본값이 아니라 의사결정 기준으로 조정될 수 있음을 보여줍니다.

## 4. SHAP 기반 개별 사례 해석

- SHAP은 XGBoost가 왜 고장이라고 예측했는지 센서 변수 단위로 설명하기 위해 사용했습니다.

- Test row index: `6497`
- Actual Machine failure: `1`
- XGBoost prediction using threshold 0.87: `1`
- XGBoost failure probability: `0.9936`
- `torque_nm` = `65.3` has SHAP `3.9352`, pushing toward **failure**.
- `rotational_speed_rpm` = `1312.0` has SHAP `0.8857`, pushing toward **failure**.
- `air_temperature_k` = `300.8` has SHAP `-0.6725`, pushing toward **normal**.
- `tool_wear_min` = `192.0` has SHAP `0.3529`, pushing toward **failure**.
- `process_temperature_k` = `309.9` has SHAP `0.2660`, pushing toward **failure**.

## 5. 발표에서 보여줄 산출물

- `outputs/metrics.json`: Logistic Regression과 XGBoost 성능 비교
- `outputs/confusion_matrix.png`: 두 모델의 confusion matrix
- `outputs/pr_curve.png`: 두 모델의 PR curve
- `outputs/threshold_tuning.png`: threshold별 precision, recall, f1-score 변화
- `outputs/shap_summary.png`, `outputs/shap_bar.png`: XGBoost SHAP 해석 그림
- `outputs/local_case_explanation.md`: 개별 고장 예측 사례 해석
- `outputs/research_plan_may11.md`: Stage 1~10 연구계획과 실사업장 적용성 정리
- `outputs/stage9_field_applicability.md`: 실제 사업장 적용 조건과 한계 정리
- `outputs/stage10_operations_summary.md`: Stage 10-lite 운영 요약과 다음 운영 단계
- `outputs/spc_risk_chart.png`, `outputs/spc_control_chart.png`: Predictive SPC 시간축 시뮬레이션 그림
- `outputs/future_deviation_predictions.csv`, `outputs/future_deviation_metrics.json`, `outputs/future_deviation_chart.png`: 미래 10-step 이탈 예측 산출물
- `outputs/ai_manager_report.md`: Gemini/OpenAI API 기반 관리자 참고 리포트
- `outputs/model_strategy_comparison.csv`, `outputs/model_strategy_summary.md`: Logistic/XGBoost, SMOTE, threshold tuning 비교
- `outputs/spc_vs_ml_comparison.csv`, `outputs/spc_vs_ml_summary.md`: SPC-only rule 대비 ML+SPC alert 비교
- `outputs/mock_field_bridge_summary.md`: MQTT/OPC UA style local mock bridge 실행 요약
- `outputs/stage19_20_operations_design.md`: 실제 현장 연동과 운영 시스템화를 위한 설계 및 검증 조건
- `outputs/final_paper_outline.md`, `outputs/final_presentation_plan.md`: 6월 최종 논문/발표 구성안
- `outputs/midterm_presentation_guide.md`: PPT 없는 중간발표 진행안

## 6. 다음 단계

- 실제 사업장 CSV 또는 DB/API 데이터로 모델 성능 재검증
- 실제 현장 데이터로 Predictive SPC control limit과 threshold 재검증
- LLM 기반 리포트를 관리자 참고용으로 제한해 운영 검토
- 알림, 조치 이력, 재학습 관리가 포함된 운영형 대시보드로 확장
