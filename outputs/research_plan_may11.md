# 캡스톤 연구 Stage 보완안

## 1. 연구 정체성

현재 연구는 **AI4I 2020 기반 제조 설비 고장 예측 baseline + 설명 가능한 결과 대시보드 PoC**입니다.

> 제조 설비 센서 데이터를 이용해 고장 위험을 예측하고, threshold와 SHAP 해석을 통해 현장 의사결정에 쓸 수 있는 설명 가능한 predictive maintenance 대시보드 구조를 설계한다.

## 2. Revised Stages

| Stage | 상태 | 핵심 내용 |
|---|---|---|
| Stage 1 | 완료 | 개발환경, 폴더 구조, 실행 스크립트 구성 |
| Stage 2 | 완료 | AI4I 2020 데이터 준비, target 설정, ID/leakage 컬럼 제거, Type one-hot encoding |
| Stage 3 | 완료 | Logistic Regression과 XGBoost baseline 모델 비교 |
| Stage 4-lite | 완료 | threshold 0.87 조정, SHAP 기반 설명 가능성 산출물 생성 |
| Stage 5 | 완료 | Streamlit 결과 대시보드 MVP 구성 |
| Stage 6-lite | 완료 | 저장된 test row 기반 고장 위험 playback 시뮬레이션 |
| Stage 7-lite | MVP 구현 | 현장 CSV 업로드 기반 고장 확률/위험 등급 예측 MVP |
| Stage 8-lite | 초안 구현 | 실제 LLM 호출이 아닌 SHAP 근거 기반 관리자 참고용 자연어 처방 초안 |
| Stage 9 | 정리 완료 | 실제 사업장 적용 조건, 장점, 한계 정리 |
| Stage 10-lite | MVP 구현 | 기존 산출물을 통합한 로컬 운영 요약과 다운로드 대시보드 |
| Stage 11 | 구현 | AI4I UDI 순서 기반 시간축 시뮬레이션과 Predictive SPC chart 생성 |
| Stage 12 | 구현 | Stage 1~20 full run 기준 Gemini 또는 OpenAI API 관리자 리포트 생성 |

## 3. 보완된 연구 질문

- **RQ1.** 제조 설비 센서 데이터로 기계 고장을 사전에 예측할 수 있는가?
- **RQ2.** Logistic Regression 대비 XGBoost가 불균형 고장 데이터에서 더 나은 성능을 보이는가?
- **RQ3.** threshold 조정이 현장 경고 기준으로 의미 있는 성능 개선을 만드는가?
- **RQ4.** SHAP과 대시보드를 결합하면 비전문가도 예측 근거를 이해할 수 있는가?
- **RQ5.** CSV 업로드, Predictive SPC, 관리자 리포트로 확장하면 중소 제조 현장용 의사결정 지원 도구가 될 수 있는가?

## 4. 발표에서 말할 연구계획 문장

> 현재까지는 AI4I 2020 공개 데이터를 기반으로 고장 예측 baseline, threshold 조정, SHAP 해석, Streamlit 결과 대시보드, CSV 업로드 예측 MVP, Stage 9 실제 적용성 정리, Stage 10 운영 요약, Predictive SPC 시간축 시뮬레이션, Gemini/OpenAI GenAI 관리자 리포트, Stage 19 field-event API, Stage 20 operator decision logging까지 구현했습니다. 이는 완성된 상용 시스템이 아니라, ML + XAI + LLM + SPC + 운영 승인 흐름을 로컬 PoC로 연결한 결과입니다.

## 5. 실사업장 적용성

| 구분 | 내용 |
|---|---|
| 적용 가능성 | CSV 기반으로 시작할 수 있어 중소기업 PoC에 적합 |
| 필요한 데이터 | Type, 온도, 회전 속도, 토크, 공구 마모 등 설비 센서 컬럼 |
| 장점 | 저비용 실험, 설명 가능한 경고, 결과 CSV 다운로드 가능 |
| 한계 | 현재 모델은 AI4I 공개 데이터 기반이라 실제 설비 데이터로 재검증 필요 |
| 다음 확장 | 실제 현장 데이터 재검증, DB/API 연결, 알림, 조치 이력, 재학습 관리 |

## 6. 발표 시 주의 문장

- 현재 기능은 실시간 센서 연동이 아니라 로컬 CSV 입력과 저장된 test playback입니다.
- 처방 문장은 자동 정비 지시가 아니라 관리자 참고용 초안입니다.
- 연구 중심은 LLM 자체가 아니라 **고장 예측 -> 설명 가능성 -> 의사결정 지원 -> 대시보드 자동화** 흐름입니다.
