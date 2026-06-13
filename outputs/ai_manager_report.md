# AI 관리자 점검 리포트 초안

- 생성 방식: 로컬 템플릿 fallback (GEMINI_API_KEY not set)
- 대상 row: UDI `3936`, time step `792`
- 위험 상태: `High Risk`
- 고장 확률: `0.9966` / threshold `0.86`
- SPC 이상 여부: risk limit `True`, torque limit `True`

## 1. 요약

선택된 row는 XGBoost 고장 확률이 threshold를 넘는 High Risk 후보입니다. 이 결과는 실제 센서 스트리밍이 아니라 AI4I 공개 데이터의 UDI 순서를 이용한 시간축 시뮬레이션입니다.

## 2. 주요 근거

- SHAP 기반 주요 요인: torque_nm, air_temperature_k, rotational_speed_rpm
- Torque [Nm]: `68.2`
- Rotational speed [rpm]: `1227.0`
- Tool wear [min]: `187.0`

## 3. 미래 10-step 이탈 예측

- 예측 horizon: `10` simulated steps
- 미래 최대 위험 예측값: `0.7546`
- 미래 이탈 확률: `0.9677`
- 판단: `미래 이탈 후보`

## 4. 관리자 참고 조치

1. 해당 row의 토크, 회전 속도, 공구 마모 조건이 정상 운전 범위와 다른지 우선 확인합니다.
2. 같은 조건이 반복되는지 최근 High Risk row와 함께 비교합니다.
3. 미래 이탈 후보로 표시되면 다음 10 step 구간을 우선 모니터링 대상으로 둡니다.
4. 실제 정비 지시는 현장 담당자의 설비 상태 확인 후 확정합니다.

## 5. 한계

이 리포트는 자동 정비 명령이 아니라 운영 관리자 참고 초안입니다.
