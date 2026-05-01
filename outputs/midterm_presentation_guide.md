# 중간발표 진행안: PPT 없이 대시보드로 발표

## 1. 가져갈 것

PPT가 따로 필요 없다면 **Streamlit 대시보드가 발표 자료**입니다.

- 대시보드: `http://127.0.0.1:8501`
- 실행 파일: `run_dashboard.bat`
- 발표 원고: `outputs/demo_script_may11.md`
- 예상 질문 답변: `outputs/midterm_qna_may11.md`
- 연구계획 정리: `outputs/research_plan_may11.md`
- 백업 결과물: `outputs/metrics.json`, `outputs/pr_curve.png`, `outputs/threshold_tuning.png`, `outputs/shap_summary.png`

## 2. 발표 첫 문장

> 제 연구는 제조 설비 센서 데이터를 이용해 기계 고장 가능성을 사전에 예측하고, 그 예측 결과와 판단 근거를 사람이 이해할 수 있도록 Streamlit 대시보드로 보여주는 predictive maintenance PoC입니다. 현재 Stage 1~9는 완료했고, Stage 10-lite는 발표용 운영 요약 MVP까지 구현했습니다.

## 3. 클릭 순서

1. **성과 요약**
   - 현재 구현 상태는 Stage 1~9 완료, Stage 10-lite 발표용 운영 요약 MVP 구현입니다.
   - 대표 모델은 XGBoost이고 PR-AUC는 0.8014입니다.

2. **모델 비교**
   - Logistic Regression과 XGBoost를 비교했습니다.
   - 고장 데이터가 적은 불균형 문제라 accuracy보다 PR-AUC, recall, F1-score를 봤습니다.

3. **Threshold 조정**
   - 기본 threshold 0.50 대신 0.87로 조정했습니다.
   - F1-score가 0.5911에서 0.7752로 개선됐습니다.
   - 이건 실제 현장에서 경고 기준을 어떻게 잡을지와 연결됩니다.

4. **SHAP 해석**
   - 모델이 왜 고장이라고 판단했는지 설명하기 위해 SHAP을 사용했습니다.
   - torque, rotational speed, tool wear 같은 센서 값이 주요 근거로 나타났습니다.

5. **개별 사례**
   - UDI 6498 사례는 실제 고장이고, XGBoost 고장 확률이 0.9936입니다.
   - 이 사례에서 torque와 rotational speed가 고장 판단의 주요 근거로 나타났습니다.

6. **Row 시뮬레이션**
   - 실시간 센서 연결은 아니고, test 결과를 row별로 넘겨보는 playback입니다.
   - row를 바꾸면 고장 확률과 High Risk 여부가 바뀝니다.

7. **현장 CSV MVP**
   - 중소기업 현장 CSV를 업로드한다고 가정한 Stage 7-lite 기능입니다.
   - CSV를 넣으면 고장 확률과 위험 등급을 계산할 수 있습니다.

8. **예상 질문 답변**
   - 실시간 여부, LLM 처방 구현 여부, 실제 공장 적용 가능성 질문에 대비합니다.
   - 핵심 답변은 현재는 로컬 PoC이고, 실제 연동과 배포는 다음 단계라는 것입니다.

9. **연구계획**
   - 최종 목표는 상용 제품 완성이 아니라 실사업장 확장 가능한 PoC입니다.
   - 다음 단계는 실제 현장 데이터 재검증, 실제 LLM 연결, DB/API 연동, 알림과 조치 이력 관리입니다.

## 4. 마무리 멘트

> 정리하면, 현재 연구는 단순히 모델 하나를 만든 것이 아니라 고장 예측, 성능 비교, threshold 의사결정, SHAP 설명, 대시보드 시각화, CSV 입력 PoC, 처방 초안까지 연결한 구조입니다. 아직 실시간 센서 연동이나 상용 배포 단계는 아니지만, 중소 제조 현장에서 실제 데이터로 확장할 수 있는 기반을 만든 것이 이번 중간발표의 핵심입니다.

## 5. 말하면 안 되는 것

- “실시간 시스템 완성했습니다”라고 말하지 않기
- “실제 공장에 바로 배포 가능합니다”라고 말하지 않기
- “LLM이 실제로 자동 처방합니다”라고 말하지 않기

대신 이렇게 말하세요.

> 현재는 로컬 PoC이며, 실시간 연동과 실제 LLM 처방은 다음 단계입니다.
