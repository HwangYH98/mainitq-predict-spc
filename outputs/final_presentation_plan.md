# 6월 최종발표 구성안

## 1. Motivation

- 고장이 난 뒤 대응하는 reactive 방식의 한계를 말합니다.
- 목표는 고장 위험을 미리 예측하고, 근거와 관리자 참고 리포트를 함께 제공하는 것입니다.

## 2. Literature Review

- ML 기반 예지보전, SHAP 기반 XAI, LLM 기반 보고서 생성 흐름을 짧게 정리합니다.

## 3. Something New

- 1차 발표 원안의 핵심을 `ML + SHAP + Predictive SPC + GenAI report + Streamlit dashboard + local operations API`로 회복했습니다.
- 실제 정비 명령이 아니라 관리자 참고용 리포트라는 안전한 범위를 둡니다.

## 4. System Architecture

1. AI4I data ingestion
2. Logistic Regression / XGBoost training
3. Threshold tuning
4. SHAP explanation
5. UDI-order time-series playback
6. Future 10-step deviation prediction
7. Predictive SPC chart generation
8. Required Gemini/OpenAI GenAI manager report for the full Stage 1~20 run
9. Streamlit dashboard

## 5. Experiment Results

- XGBoost PR-AUC `0.8014`.
- selected threshold `0.87`, tuned F1-score `0.7752`.
- SPC High Risk row `61`, SPC alert row `88`.
- future 10-step deviation F1-score `0.4142`.

## 6. Dashboard Demonstration

- 성과 요약 -> 모델 비교 -> threshold -> SHAP -> 실시간 처방 PoC -> Predictive SPC -> AI Report 순서로 시연합니다.
- `실시간 처방 PoC` 탭에서 현재 위험, 미래 10-step 이탈 예측, SHAP 근거, 자연어 권고를 한 화면에서 보여줍니다.
- `Predictive SPC` 탭에서 시간축 시뮬레이션과 관리한계선을 보여줍니다.
- `AI Report` 탭에서 High Risk row의 관리자 참고 리포트를 보여줍니다.

## 7. Limitations and Future Work

- 실제 센서 스트리밍이 아니라 AI4I row playback입니다.
- 실제 현장 데이터 검증이 필요합니다.
- LLM 출력은 최종 판단이 아니라 참고 초안입니다.
- 1차 발표의 85%, 30% 기대효과 수치는 본 실험 결과로 주장하지 않습니다.
