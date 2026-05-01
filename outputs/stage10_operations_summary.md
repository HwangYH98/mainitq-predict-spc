# Stage 10-lite 운영 요약

## 1. Stage 10-lite의 목적

Stage 10-lite는 실제 운영 시스템을 새로 만드는 단계가 아니라, 지금까지 만든 예측, 설명, 처방 초안, 적용성 문서, 다운로드 산출물을 하나의 발표용 운영 요약으로 묶는 단계입니다. 현재 프로젝트는 여기서 더 나아가 Stage 14~20 로컬 통합 PoC까지 검증합니다.

> 현재 기능은 로컬 파일 기반 통합 MVP이며, AI4I row playback 기반 시간축 시뮬레이션, Predictive SPC chart, 필수 Gemini/OpenAI GenAI 관리자 리포트, Stage 14 회사 CSV 재학습, Stage 15~18 file-drop/FastAPI/SQLite/work-order draft, Stage 19 field-event API, Stage 20 operator decision logging까지 포함합니다. 실제 PLC/SCADA 연동, 클라우드 배포, 무인 자동 정비 명령은 아직 구현 완료로 주장하지 않습니다.

## 2. 현재 모델 상태

| 항목 | 현재 값 | 발표에서 말할 의미 |
|---|---:|---|
| 대표 모델 | XGBoost | PR-AUC 기준 Logistic Regression보다 좋은 baseline |
| XGBoost PR-AUC | `0.8014` | 불균형 고장 데이터에서 대표 성능 지표 |
| 선택 threshold | `0.87` | F1-score 기준으로 선택한 경고 기준 |
| tuned F1-score | `0.7752` | precision과 recall의 균형 결과 |
| test 예측 row 수 | `2000` | 저장된 test prediction 기반 운영 요약 |
| High Risk row 수 | `61` | threshold 이상으로 표시되는 점검 후보 |
| 실제 고장 row 수 | `68` | test set 안의 실제 고장 라벨 수 |
| 최대 고장 확률 | `0.9936` | 가장 위험하게 예측된 row의 확률 |
| SPC alert row 수 | `88` | risk control limit 또는 threshold 기준 이상 후보 |
| risk UCL | `0.7130` | 고장 확률 risk signal의 3-sigma 관리 상한 |
| 미래 예측 horizon | `10` step | UDI 순서 기반 simulated future deviation prediction |
| 미래 이탈 예측 row 수 | `1406` | 다음 10 step 이탈 후보로 예측된 row |
| 미래 이탈 예측 F1 | `0.4142` | chronological validation 기준 |

## 3. 대시보드에서 통합되는 기능

- 예측: baseline prediction CSV와 현장 CSV 업로드 결과를 사용해 고장 확률을 보여줍니다.
- 설명: SHAP summary plot과 개별 사례 설명으로 왜 위험하게 판단했는지 보여줍니다.
- Predictive SPC: AI4I UDI 순서를 시간축으로 두고 고장 확률 trend, rolling mean, control limit을 보여줍니다.
- 회사 재학습: 라벨 있는 회사 CSV 또는 AI4I 기반 데모 회사 CSV로 Stage 14-lite 재학습 산출물을 만듭니다.
- 로컬 운영: file-drop streaming, FastAPI 예측, SQLite 이력 저장, 관리자 승인용 작업지시 초안을 Stage 15~18-lite로 검증합니다.
- 현장 연동 PoC: Stage 19 `/field-event` API로 설비 ID, timestamp, source system, sensor row를 받아 예측 이벤트로 저장합니다.
- 운영 승인 PoC: Stage 20 `/work-order-decision` API로 approve/reject/needs_review 결정을 SQLite와 CSV에 기록합니다.
- GenAI 리포트: Stage 1~20 full run에서는 GEMINI_API_KEY 또는 OPENAI_API_KEY가 필수이며 Gemini 또는 OpenAI API로 관리자 참고 리포트를 생성합니다.
- 다운로드: metrics, prediction CSV, SPC CSV, 발표 요약, Stage 9/10 문서, AI 리포트를 받을 수 있게 합니다.
- 운영 요약: 모델 상태, threshold, High Risk row 수, SPC alert 수, 현재 한계와 다음 단계를 한 탭에 정리합니다.

## 4. 현재 한계

- 실제 공장 센서 스트리밍이 아니라 저장된 test prediction에 UDI 순서 시간축을 부여한 시뮬레이션입니다.
- 현재 모델은 AI4I 2020 공개 데이터로 검증했으므로 실제 현장 데이터로 성능을 다시 확인해야 합니다.
- LLM 리포트는 자동 정비 지시가 아니라 관리자 참고용 초안입니다.
- 실제 PLC/SCADA 연동, 클라우드 배포, 권한/알림/재학습 스케줄은 별도 현장 시스템이 필요하며 아직 운영 제품으로 구현하지 않았습니다.

## 5. 다음 운영 단계

1. 실제 현장 CSV를 받아 현재 입력 컬럼과 단위가 맞는지 확인합니다.
2. 실제 고장 이력과 예측 결과를 비교해 PR-AUC, precision, recall, F1-score를 재측정합니다.
3. false alarm 비용과 missed failure 비용을 기준으로 현장 threshold를 다시 조정합니다.
4. High Risk row 확인 여부와 조치 결과를 기록하는 간단한 이력 테이블을 설계합니다.
5. 실제 LLM 리포트는 SHAP/SPC 근거 기반 관리자 참고 문장 생성으로 범위를 제한합니다.

## 6. 발표에서 말할 문장

> Stage 14~20에서는 회사 CSV 재학습, file-drop streaming, FastAPI 예측, SQLite event history, field-event API, 관리자 승인용 작업지시 초안, operator decision logging을 local PoC로 구현했습니다. 아직 실제 PLC/SCADA/클라우드 운영 제품은 아니며, 현장 endpoint와 보안 승인이 있어야 실제 운영으로 확장할 수 있습니다.
