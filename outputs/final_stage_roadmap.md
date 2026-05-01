# 최종 단계 로드맵

## 1. 현재 출발점

현재 프로젝트는 XGBoost PR-AUC `0.8014`, selected threshold `0.87`, tuned F1-score `0.7752`를 기준으로 발표 가능한 predictive maintenance PoC까지 도달했습니다.

구현 상태는 **Stage 1~20 로컬 통합 PoC 구현 완료**입니다. 단, 실제 PLC/SCADA/클라우드 배포 완료가 아니라 로컬 field-event API, SQLite 이력, human decision logging까지 연결한 검증 가능한 PoC입니다.

## 2. Stage 9: 실제 적용 조건과 한계 정리

상세 정리는 `outputs/stage9_field_applicability.md`에 별도 산출물로 저장합니다.

| 항목 | 해야 할 일 |
|---|---|
| 현장 데이터 필요 컬럼 | Type, Air temperature, Process temperature, Rotational speed, Torque, Tool wear 같은 센서 컬럼 확보 |
| 데이터 차이 확인 | AI4I 공개 데이터와 실제 설비 데이터의 분포, 단위, 결측치, 고장 비율 비교 |
| 성능 재검증 | 실제 현장 데이터에서 precision, recall, F1-score, ROC-AUC, PR-AUC 재측정 |
| 운영 한계 정리 | 고장 원인 라벨 부재, 센서 품질, 설비별 차이, false alarm 비용 정리 |
| 적용 방식 | 처음부터 실시간이 아니라 CSV 기반 파일 업로드 PoC로 시작 |

## 3. Stage 10~20: 로컬 통합 운영 PoC

- Stage 10~13: 모델 성능, threshold, Predictive SPC, 미래 10-step 이탈 예측, 관리자 참고 리포트 정리
- Stage 14-lite: 라벨 있는 회사 CSV 또는 AI4I 기반 데모 회사 CSV로 재학습, threshold, SHAP bar, 예측 CSV, 모델 파일 저장
- Stage 15~18-lite: file-drop streaming, FastAPI 예측, SQLite event history, 관리자 승인용 작업지시 초안 생성
- Stage 19-lite: `POST /field-event`로 equipment_id, timestamp, source_system, sensor row를 받아 로컬 예측 이벤트로 저장
- Stage 20-lite: `POST /work-order-decision`으로 approve/reject/needs_review 결정을 SQLite와 CSV에 기록
- 다운로드: 모델 지표, 예측 결과 CSV, Stage 9/10 문서, Stage 14 회사 재학습 산출물, 운영 PoC 산출물 제공
- 운영 요약: 모델 성능, threshold 기준, High Risk row 수, field-event 수, 작업지시 결정 기록, 현재 한계를 한 화면에 정리

Stage 14~20-lite는 실제 공장 운영 제품이 아니라, 회사 CSV 재학습부터 field-event API와 operator decision logging까지 로컬에서 검증하는 통합 PoC입니다. 실제 PLC/SCADA/클라우드 운영은 별도 현장 endpoint와 보안 승인이 필요합니다.

## 4. 실제 LLM 연결 여부 결정

LLM을 연결한다면 역할은 `자동 정비 명령`이 아니라 `관리자 참고용 문장 생성`으로 제한합니다. 입력은 SHAP 상위 요인, 고장 확률, threshold, 센서 값으로 제한하고, 출력에는 반드시 `최종 판단은 현장 담당자가 확정`한다는 문장을 포함합니다.

## 5. 논문/보고서 작성 순서

1. Codex로 실제 산출물 기반 초안을 만듭니다: 데이터, 전처리, 모델, 평가 지표, 결과 수치, 대시보드 구조.
2. ChatGPT로 문장을 다듬습니다: 서론, 연구 배경, 결론, 문장 자연스러움.
3. 사람이 최종 검토합니다: 과장 표현 제거, 수치 확인, 교수님 요구 형식 반영.

## 6. 논문에 쓰기 좋은 핵심 문장

> 본 연구는 AI4I 2020 공개 데이터를 기반으로 제조 설비 고장 예측 모델을 구축하고, threshold 조정, SHAP 기반 설명, Gemini/OpenAI GenAI 관리자 리포트, 회사 CSV 재학습, file-drop streaming, FastAPI, SQLite event history, field-event API, 관리자 승인용 작업지시 초안과 operator decision logging을 Stage 1~20 로컬 통합 PoC로 연결한다. 실제 PLC/SCADA/클라우드 운영에는 현장 endpoint, 보안 승인, 현장 데이터 재검증이 추가로 필요하다.
