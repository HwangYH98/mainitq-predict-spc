# MaintiQ Predict

MaintiQ Predict는 제조 설비 센서 CSV를 입력받아 고장 위험도, 위험 우선순위, AI 관리자 리포트, 승인형 작업지시 이력을 관리하는 Windows 데스크톱 예지보전 MVP입니다.

이 저장소는 코드, 샘플 데이터, 검증 스크립트, 설치파일 빌드 스크립트를 포함합니다. 설치파일 자체는 Git에 커밋하지 않고 GitHub Release 첨부 파일로 관리합니다.

## 핵심 기능

- AI4I형 CSV 자동 감지 및 기본 고장확률 예측
- SCANIA형 CSV 자동 감지 및 공식 cost matrix 기반 비용 최적화 예측
- 제품 앱에서 `자동 감지`, `기본 센서 모델`, `SCANIA 비용 모델` 선택
- CSV 품질 진단, 위험 우선순위, 결과 CSV 저장
- Gemini 또는 OpenAI API key를 세션에서만 입력해 AI 관리자 리포트 생성
- 작업지시 초안 생성과 승인/검토/반려 기록
- Streamlit Admin 콘솔에서 모델 검증, 공개 benchmark, 회사 데이터 실증 템플릿 확인

## 실행 모드

| 구분 | 용도 | 설명 |
| --- | --- | --- |
| 빠른 점검 모드 | 작은 설치본, 일상 점검, 시연 | 경량 운영 점수 기반입니다. 정밀 분석 결과와 다를 수 있습니다. |
| 정밀 분석 모드 | XGBoost/SHAP 기반 정밀 분석 | 기본 센서 모델과 SCANIA 비용 모델을 사용합니다. |
| Admin 콘솔 | 연구/검증/benchmark 확인 | 제품 앱에는 보이지 않는 검증 자료와 실증 리포트를 확인합니다. |

## 데이터 스키마

### AI4I형 CSV

기본 입력 컬럼은 AI4I 2020 형식입니다.

```text
Type
Air temperature [K]
Process temperature [K]
Rotational speed [rpm]
Torque [Nm]
Tool wear [min]
```

제품 앱은 일부 회사식 컬럼명과 단위 변환을 지원합니다. 예를 들어 `air_temp`, `온도`, `rpm`, `회전속도` 같은 컬럼명은 가능한 범위에서 자동 매핑합니다.

### SCANIA형 CSV

SCANIA Component X 형식은 `vehicle_id`, `time_step`, 다수의 익명 센서/상태 컬럼을 포함합니다. 제품 앱은 SCANIA형 컬럼 구조를 감지하면 SCANIA cost-sensitive 모델 경로로 예측합니다.

SCANIA 모델 artifact는 아래 명령으로 생성합니다.

```powershell
.\.venv\Scripts\python.exe src\scania_official_cost_validation.py
```

생성 파일:

```text
outputs/scania_cost_optimized_model.joblib
```

이 파일이 없으면 SCANIA 비용 최적화 예측은 실행할 수 없습니다.

## 개발 환경 설치

Windows PowerShell에서 저장소 루트로 이동한 뒤 실행합니다.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 데스크톱 앱 실행

운영자용 사용 절차는 [docs/USER_MANUAL.md](docs/USER_MANUAL.md)에 정리되어 있습니다.

정밀 분석 모드:

```powershell
.\.venv\Scripts\python.exe desktop_app\main.py
```

또는:

```powershell
.\run_desktop_app.bat
```

빠른 점검 모드:

```powershell
.\.venv\Scripts\python.exe desktop_app\lite_main.py
```

## Streamlit Admin 콘솔

Admin 콘솔은 연구/검증/benchmark/회사 데이터 실증 템플릿 확인용입니다.

```powershell
.\run_admin_dashboard.bat
```

기본 주소:

```text
http://127.0.0.1:8502
```

## 설치파일 빌드

Full 설치본:

```powershell
.\build_desktop_app.bat
.\build_desktop_installer.bat
```

Lite 설치본:

```powershell
.\build_desktop_lite_app.bat
.\build_desktop_lite_installer.bat
```

생성되는 `release/*.exe` 파일은 Git 커밋 대상이 아닙니다. GitHub Release 첨부 파일로만 배포합니다.

## 업데이트와 오류 로그

데스크톱 앱의 좌측 하단 `업데이트 확인` 버튼은 GitHub Release의 최신 버전을 확인하고, 새 버전이 있으면 Release 페이지를 열도록 안내합니다. v1에서는 무인 자동 설치나 백그라운드 교체를 하지 않습니다.

오류가 발생했을 때는 앱의 `오류 로그 내보내기` 버튼 또는 아래 명령으로 crash log ZIP을 만들 수 있습니다.

```powershell
.\.venv\Scripts\python.exe desktop_app\main.py --export-crash-logs
.\.venv\Scripts\python.exe desktop_app\lite_main.py --export-crash-logs
```

오류 로그 위치는 `%LOCALAPPDATA%\MaintiQ Predict\logs\`입니다. API key와 비밀번호는 의도적으로 저장하지 않습니다.

## 검증 명령

```powershell
.\.venv\Scripts\python.exe -m compileall -q src app desktop_app tools streamlit_app.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe desktop_app\main.py --check
.\.venv\Scripts\python.exe desktop_app\main.py --engine-smoke-test
.\.venv\Scripts\python.exe desktop_app\main.py --workflow-smoke-test
.\.venv\Scripts\python.exe desktop_app\main.py --click-workflow-test
.\.venv\Scripts\python.exe desktop_app\lite_main.py --workflow-smoke-test
.\.venv\Scripts\python.exe desktop_app\lite_main.py --click-workflow-test
.\.venv\Scripts\python.exe src\verify_project.py
cmd /c "run_verify.bat < NUL"
```

GitHub 업로드 전 범위 확인:

```powershell
.\.venv\Scripts\python.exe tools\check_github_upload_scope.py
.\.venv\Scripts\python.exe tools\list_github_upload_candidates.py
```

## GitHub 업로드 범위

Git에 포함:

- `src/`, `app/`, `desktop_app/`, `tools/`, `installer/`, `tests/`
- `samples/`
- `data/ai4i2020.csv`
- `README.md`, `AGENTS.md`, `GITHUB_UPLOAD_SCOPE.md`, `CHANGELOG.md`
- 실행 및 빌드 스크립트

Git에 포함하지 않음:

- `.venv/`
- `build/`, `dist/`, `release/`, `*.spec`
- `.env`, key 파일, secret 파일
- `outputs/operations.db`
- `outputs/realtime_stream/`
- `outputs/work_order_drafts/`
- 대량 또는 재생성 가능한 `outputs/` 산출물
- `data_external/`
- 실제 회사 원본 데이터
- `local_presentation_notes/`

대부분의 `outputs/`는 재생성 산출물이므로 저장소에 커밋하지 않습니다. GitHub에는 코드, 샘플, 템플릿, 핵심 문서만 남기고, 예측 CSV/그래프/스크린샷/benchmark dump는 로컬에서 검증 명령으로 다시 생성합니다.

업로드 전 권장 커밋 메시지:

```text
Finalize MaintiQ Predict desktop MVP packaging and validation tooling
```

## 주장 범위

현재 구현으로 말할 수 있는 것:

- 공개 데이터 기반 예지보전 데스크톱 MVP를 구현했습니다.
- AI4I형 CSV와 SCANIA형 CSV를 구분해 서로 다른 예측 경로를 실행합니다.
- SCANIA 공개 benchmark에서는 공식 cost matrix 기준으로 rule baseline 대비 비용 metric 개선을 계산할 수 있습니다.
- 회사 데이터 실증용 입력 템플릿과 리포트 export 구조를 제공합니다.

현재 구현만으로 말하면 안 되는 것:

- 실제 PLC/SCADA 운영망 연결 완료
- 실제 공장 센서 실시간 운영 배포
- 실제 회사 데이터 성능 재검증 완료
- 실제 비용 절감률 또는 탐지 시간 단축률 실증 완료
- 자동 정비 명령 실행
- 완성된 상용 SaaS 플랫폼

실제 비용 절감이나 탐지 시간 단축을 주장하려면 회사의 labeled sensor CSV, 정비 이력, downtime, 비용 로그가 필요합니다.
