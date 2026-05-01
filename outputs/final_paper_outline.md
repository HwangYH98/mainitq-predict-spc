# 최종 논문 작성 개요

## 논문 제목

생성형 AI 확장을 고려한 설명가능한 스마트 제조 Predictive SPC 대시보드 구축: AI4I 2020 기반 PoC

## 1. 서론

- 스마트 제조 현장에서 설비 고장과 품질 이상을 사후 대응하는 한계를 설명합니다.
- 본 연구는 고장 예측, 설명 가능성, Predictive SPC, 관리자용 AI 리포트를 하나의 로컬 PoC로 연결합니다.
- 실제 센서 스트리밍이 아니라 AI4I 2020 공개 데이터의 UDI 순서를 사용한 시간축 시뮬레이션임을 명확히 씁니다.

## 2. 선행연구

- 머신러닝 기반 예지보전
- SHAP/LIME 기반 설명가능 AI
- 제조 대시보드와 LLM 기반 의사결정 지원
- 본 연구의 차별성: ML 성능 비교에서 끝나지 않고 threshold, SHAP, SPC chart, AI 리포트, dashboard를 연결합니다.

## 3. 방법론

- 데이터: AI4I 2020, 10,000 samples, target `Machine failure`.
- 전처리: `UDI`, `Product ID` 제거, `Type` one-hot encoding, `TWF/HDF/PWF/OSF/RNF` leakage column 제거.
- 모델: Logistic Regression baseline과 XGBoost 비교.
- 평가: precision, recall, F1-score, ROC-AUC, PR-AUC.
- threshold: 0.05~0.95 탐색 후 F1 기준 `0.87` 선택.
- Predictive SPC: saved prediction을 UDI 순서로 정렬해 simulated time axis를 만들고 risk signal, rolling mean, control limit을 계산합니다.
- 미래 이탈 예측: UDI 순서 기반 lag/rolling feature로 다음 `10` step의 최대 risk와 이탈 여부를 예측합니다.
- GenAI 리포트: High Risk/SPC 이상 row의 수치 근거와 SHAP 요인을 Gemini 또는 OpenAI API에 전달합니다.

## 4. 결과

- Logistic Regression PR-AUC: `0.3817`.
- XGBoost PR-AUC: `0.8014`, ROC-AUC: `0.9736`.
- 선택 threshold `0.87`에서 F1-score `0.7752`.
- SPC 시뮬레이션 row `2000`개, High Risk row `61`개, SPC alert row `88`개.
- 미래 `10` step 이탈 예측 F1-score `0.4142`, regression RMSE `0.3849`.
- 주요 그림: confusion matrix, PR curve, threshold tuning, SHAP summary/bar, SPC risk chart, SPC control chart.

## 5. 시스템 구현

- Streamlit dashboard에서 모델 성능, threshold, SHAP, row playback, 미래 이탈 예측, Predictive SPC, AI report를 확인합니다.
- `run_all.bat`로 학습, 해석, SPC, AI 리포트, 발표 문서 생성을 자동화합니다.

## 6. 한계 및 향후 연구

- AI4I 기반 시간축은 실제 센서 스트리밍이 아니라 발표용 시뮬레이션입니다.
- 실제 현장 데이터로 성능과 threshold를 재검증해야 합니다.
- LLM 리포트는 관리자 참고용이며 자동 정비 지시로 사용하지 않습니다.
- 향후에는 실제 DB/API, 센서 스트리밍, 알림/조치 이력, 재학습 관리로 확장합니다.
