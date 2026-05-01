# Stage 19~20 로컬 연동 및 운영 승인 PoC

## 1. 문서 목적

이 문서는 Stage 14~18 local PoC 이후 Stage 19 field-event API와 Stage 20 operator decision logging을 로컬에서 어떻게 실제 호출/저장 흐름으로 검증했는지 정리합니다.

> Stage 1~20 로컬 통합 PoC 구현 완료입니다. Stage 19~20은 실제 PLC/SCADA/클라우드 배포가 아니라 로컬 field-event API와 operator decision logging으로 검증합니다.

현재 단계에서는 실제 PLC/SCADA/MQTT/OPC UA/클라우드 연동을 완료했다고 말하지 않습니다. 외부 장비 접근 권한이 없으므로 현장 connector 앞단의 로컬 API 계약, SQLite 이력, 작업지시 승인 기록까지를 검증 가능한 구현 범위로 둡니다.

## 2. 현재 구현 완료 범위

| Stage | 상태 | 설명 |
|---|---|---|
| Stage 14-lite | 구현 완료 | 라벨 있는 회사 CSV 또는 AI4I 기반 데모 회사 CSV로 재학습, threshold, SHAP bar, 예측 CSV, 모델 파일 생성 |
| Stage 15-lite | 구현 완료 | `outputs/realtime_stream/incoming` CSV file-drop streaming simulation 처리 |
| Stage 16-lite | 구현 완료 | 로컬 FastAPI 예측 endpoint 구조 검증 |
| Stage 17-lite | 구현 완료 | SQLite 기반 prediction event와 work-order draft 저장 |
| Stage 18-lite | 구현 완료 | 관리자 승인용 작업지시 초안 JSON/Markdown 생성 |
| Stage 19-lite | 구현 완료 | `POST /field-event`로 equipment_id, event_timestamp, source_system, sensor row를 받아 예측 이벤트로 저장 |
| Stage 20-lite | 구현 완료 | `POST /work-order-decision`으로 approve/reject/needs_review 결정을 SQLite와 CSV에 기록 |

## 3. Stage 19 로컬 field-event API

Stage 19의 목표는 공장 시스템 대신 로컬 API 계약을 먼저 고정하는 것입니다. 외부 PLC/SCADA/MES connector는 나중에 이 API로 payload를 보내면 됩니다.

| 항목 | 로컬 구현 | 현장 확장 조건 |
|---|---|---|
| API endpoint | `POST /field-event` | PLC/SCADA/MQTT/OPC UA bridge가 같은 JSON payload를 보낼 수 있어야 함 |
| 식별자 | `equipment_id`, `event_timestamp`, `source_system` 필수 | 설비 ID와 timestamp 품질이 안정적으로 들어와야 함 |
| 센서 row | AI4I-compatible `Type`, temperature, speed, torque, tool wear 입력 | 실제 tag와 AI4I feature mapping/단위 변환 필요 |
| 저장 | 예측 이벤트를 `outputs/operations.db`와 `latest_events.csv`에 기록 | 운영 DB, 권한, 감사 로그 정책으로 확장 필요 |
| 안전 경계 | 로컬 API는 예측과 기록만 수행 | 실제 장비 제어 명령은 보내지 않음 |

## 4. Stage 19 데이터 계약 초안

| 필드 | 필요성 | 예시 |
|---|---|---|
| `equipment_id` | 설비별 성능과 drift를 분리하기 위해 필요 | `MACHINE_01` |
| `timestamp` | row 순서와 지연 시간을 검증하기 위해 필요 | `2026-05-11T09:00:00+09:00` |
| `product_type` | AI4I `Type`에 대응되는 제품/작업 조건 | `L`, `M`, `H` 또는 현장 제품군 |
| `air_temperature` | 주변 온도 또는 설비 주변 온도 | 섭씨 또는 켈빈, 단위 명시 필요 |
| `process_temperature` | 공정 온도 | 섭씨 또는 켈빈, 단위 명시 필요 |
| `rotational_speed` | 회전수/속도 조건 | rpm 또는 현장 단위 |
| `torque` | 부하 또는 토크 조건 | Nm 또는 현장 단위 |
| `tool_wear` | 공구 사용 시간 또는 누적 사용량 | minute 또는 cycle count |
| `failure_label` | 재검증용 실제 고장 여부 | 정상/고장, ok/failure, 0/1 |

## 5. Stage 20 operator decision logging

Stage 20의 목표는 작업지시 초안을 사람이 검토한 뒤 approve/reject/needs_review 결정을 남기는 것입니다.

| 항목 | 로컬 구현 | 운영 확장 조건 |
|---|---|---|
| Decision API | `POST /work-order-decision` | 로그인 사용자 ID와 권한 체계 연결 필요 |
| 허용 결정 | `approve`, `reject`, `needs_review` | 실제 현장 승인 workflow와 상태값 합의 필요 |
| 감사 기록 | SQLite `work_order_decisions`와 `work_order_decisions.csv`에 저장 | 운영 DB, immutable audit log, 백업/복구 필요 |
| 작업 이력 | draft_id와 event_id로 예측 근거와 연결 | 실제 점검 결과, 부품 교체, false alarm 여부 추가 필요 |
| 안전 경계 | 결정 기록은 사람 승인 로그이며 자동 정비 명령이 아님 | 설비 제어 시스템과 연결 전 별도 승인 필요 |

## 6. 배포 전 검증 체크리스트

- 실제 현장 CSV로 Stage 14 재학습을 실행하고 `custom_metrics.json`을 확인한다.
- 실제 현장 데이터의 단위 변환과 필수 컬럼 mapping을 문서화한다.
- Stage 15 file-drop simulation으로 현장 row가 예측 이벤트로 저장되는지 확인한다.
- `/field-event`로 현장 row가 예측 이벤트와 SQLite 기록으로 이어지는지 확인한다.
- `/work-order-decision`으로 작업지시 초안에 대한 사람 결정이 SQLite와 CSV에 저장되는지 확인한다.
- FastAPI endpoint는 운영망 연결 전 테스트망에서만 검증한다.
- SQLite PoC를 운영 DB로 바꾸기 전 감사 로그, 권한, 백업 정책을 설계한다.
- 작업지시 초안과 decision log는 관리자 승인용 기록으로만 사용하고 자동 정비 명령으로 연결하지 않는다.
- threshold는 AI4I 기준값을 그대로 쓰지 않고 현장 false alarm 비용과 missed failure 비용으로 재조정한다.
- 클라우드 배포 전 비밀값 관리, 접근 제어, 로그 보관, 장애 대응 절차를 확인한다.

## 7. 발표 및 논문 guardrail

- 말해도 되는 표현: `Stage 1~20 로컬 통합 PoC 구현 완료`, `Stage 19 field-event API 구현`, `Stage 20 operator decision logging 구현`, `실제 현장 적용 전 데이터 재검증 필요`.
- 아직 실제 PLC/SCADA/클라우드 운영 제품은 아니며, 현장 endpoint와 보안 승인 없이 운영 배포를 완료했다고 말하지 않는다.
- 피해야 할 표현: 공장 연동이 이미 끝났다는 표현, 클라우드에 배포됐다는 표현, 사람이 승인하지 않는 자동 정비 실행 표현, 상용 제품이 완성됐다는 표현.
- 본 시스템은 현재 local PoC이며, 실제 배포 가능 제품이라고 주장하지 않는다.

## 8. 결론

Stage 19~20은 외부 공장 배포 완료가 아니라, Stage 14~18 local PoC 뒤에 field-event API와 operator decision logging을 붙여 실제 데이터 흐름의 마지막 연결부를 로컬에서 검증한 단계입니다. 이 문서는 발표와 논문에서 구현 범위와 실제 현장 확장 조건을 분리해 설명하기 위한 기준 문서입니다.
