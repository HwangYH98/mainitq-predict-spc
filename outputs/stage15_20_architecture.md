# Stage 15~20 확장 아키텍처

## 구현된 local PoC 범위

- Stage 15-lite: `outputs/realtime_stream/incoming` 폴더에 들어온 CSV를 file-drop streaming simulation으로 처리한다.
- Stage 16-lite: FastAPI 서버가 `POST /predict`, `POST /predict-batch`, `GET /health`, `GET /model-info`, `GET /events`, `POST /work-order-draft`를 제공한다.
- Stage 17-lite: 예측 event, 고장 확률, risk label, SHAP 근거, 작업지시 초안을 `outputs/operations.db` SQLite DB에 저장한다.
- Stage 18-lite: 자동 정비 명령이 아니라 관리자 승인용 작업지시 초안을 JSON/Markdown으로 생성한다.
- Stage 19-lite: `POST /field-event`로 equipment_id, timestamp, source_system, sensor row를 받아 로컬 예측 이벤트로 저장한다.
- Stage 20-lite: `POST /work-order-decision`으로 approve/reject/needs_review 결정을 SQLite와 CSV에 기록한다.

## 아직 구현하지 않는 외부 운영 범위

- Stage 19 실제 현장 연동은 OPC UA, MQTT, Modbus, SCADA 또는 MES/PLC API가 필요하다.
- Stage 20 운영 시스템화는 로그인, 권한, 알림, 감사 로그, 재학습 관리, 배포 환경, 보안 검토가 필요하다.
- 현재 결과는 Stage 1~20 로컬 통합 PoC이며 실제 공장 배포 완료 또는 무인 자동 정비 실행으로 표현하지 않는다.

## 논문 표현

본 연구는 real-time deployment를 완료한 것이 아니라, file-drop streaming simulation, local FastAPI inference, SQLite event history, human-approved work-order draft, local operator decision logging을 통해 실제 운영 시스템으로 확장 가능한 구조를 검증했다.
