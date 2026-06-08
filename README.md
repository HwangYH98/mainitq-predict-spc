# MaintiQ Predict

MaintiQ Predict는 제조 설비 센서 CSV를 불러와 고장 위험도, 위험 우선순위, AI 리포트, 작업지시 이력을 확인하는 Windows 데스크톱 예지보전 앱입니다.

실제 사용자 배포 기준은 **Full Windows installer**입니다. Streamlit 화면은 로컬 운영 확인과 Admin 검증용으로 유지합니다.

## Quick Start

### 1. 개발 환경 준비

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. 로컬 데스크톱 앱 실행

```powershell
.\01_Run_MaintiQ_Predict.bat
```

직접 실행하려면:

```powershell
.\.venv\Scripts\python.exe desktop_app\main.py
```

### 3. Admin 콘솔 실행

```powershell
.\02_Run_Admin_Console.bat
```

Admin 콘솔은 `http://127.0.0.1:8502`에서 열립니다. 비밀번호는 `APP_ADMIN_PASSWORD` 환경변수 또는 실행 중 입력값으로만 사용하며 파일에 저장하지 않습니다.

## Streamlit 실행 기준

Streamlit은 GitHub에 소스가 올라가는 로컬 운영/Admin 검증 화면입니다. 최종 사용자가 설치해서 쓰는 배포물은 Windows installer입니다.

사용자 운영 화면:

```powershell
$env:APP_OPERATOR_PASSWORD="your-operator-password"
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py --server.port 8501
```

Admin 검증 콘솔:

```powershell
$env:APP_ADMIN_PASSWORD="your-admin-password"
.\.venv\Scripts\python.exe -m streamlit run app\admin_dashboard.py --server.port 8502
```

`APP_OPERATOR_PASSWORD`와 `APP_ADMIN_PASSWORD`는 현재 세션 인증에만 사용합니다. `.env`, README, outputs, Git 기록에 저장하지 않습니다.

## 사용자 설치 패키지

공식 사용자 배포 파일:

```text
release\MaintiQ_Predict_Setup.exe
```

installer를 다시 만들려면:

```powershell
.\03_Build_User_Installer.bat
```

이 명령은 내부적으로 portable app 생성, 배포 폴더 검증, Inno Setup installer 생성, checksum 생성을 수행합니다. `release\MaintiQ_Predict_Setup.exe`는 GitHub 코드 저장소에 커밋하지 않고 GitHub Release 첨부 파일로 배포합니다.

Lite build는 공식 사용자 배포 기준에서 제외했습니다. 필요할 때만 `scripts\dev\lite\` 아래 개발용 스크립트로 실행합니다.

## 데이터 입력

기본 예측 입력 컬럼:

```text
Type
Air temperature [K]
Process temperature [K]
Rotational speed [rpm]
Torque [Nm]
Tool wear [min]
```

한국어/현장식 컬럼명도 자동 매핑됩니다. 예: `제품등급`, `공기온도`, `공정온도`, `회전속도`, `모터토크`, `공구마모`.

기본 샘플:

```text
samples\company_sensor_sample.csv
```

AI4I 원본 데이터:

```text
data\ai4i2020.csv
```

`data_external\`의 SCANIA, MetroPT3, FEMTO 같은 공개 benchmark 데이터는 Admin 검증 또는 별도 benchmark script용입니다. 사용자 예측 업로드 화면에 그대로 넣는 데이터 형식이 아닐 수 있습니다.

## 검증 명령

문법/정적 검증:

```powershell
.\.venv\Scripts\python.exe -m compileall -q src app desktop_app tools streamlit_app.py
```

데스크톱 앱 핵심 검증:

```powershell
.\.venv\Scripts\python.exe desktop_app\main.py --check
.\.venv\Scripts\python.exe desktop_app\main.py --engine-smoke-test
.\.venv\Scripts\python.exe desktop_app\main.py --click-workflow-test
```

테스트:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp outputs\pytest_basetemp_local
```

일부 Windows 환경에서는 기본 pytest 임시 폴더(`%LOCALAPPDATA%\Temp\pytest-of-*`) 권한 문제로 테스트 준비 단계가 실패할 수 있습니다. 위 명령처럼 `--basetemp`를 지정하면 같은 테스트를 저장소 로컬 임시 경로에서 재현할 수 있습니다.

배포 폴더 검증:

```powershell
.\.venv\Scripts\python.exe tools\validate_desktop_distribution.py dist\MaintiQ_Predict
```

전체 로컬 검증 스크립트는 개발용으로 이동했습니다:

```powershell
.\scripts\dev\run_verify.bat
```

## GitHub 업로드 기준

GitHub 코드 저장소에 포함:

- `src/`, `desktop_app/`, `app/`, `tests/`
- `streamlit_app.py`
- `installer/`
- 공식 루트 실행 파일 `01_*.bat`, `02_*.bat`, `03_*.bat`
- 재현 가능한 샘플과 문서

GitHub 코드 저장소에 포함하지 않음:

- `.venv/`
- `build/`, `dist/`, `release/`
- `outputs/`
- `data_external/`
- API key, `.env`, 비밀번호 파일
- 실제 회사 원본 데이터

## 연구와 발표 주장 범위

이 저장소는 공개 데이터 기반 예지보전 MVP와 로컬 실행 검증 자료입니다. 발표와 README에서는 다음 범위로만 주장합니다.

- 주장 가능: AI4I 2020 기반 모델 학습과 평가, SCANIA 공개 benchmark의 official cost metric 검증, 로컬 Desktop/Admin 실행, GenAI 관리자 참고 리포트, 작업자 승인형 workflow.
- 주장 금지: 실제 회사 원화 비용 절감 입증, 실제 PLC/SCADA 생산망 실시간 연동 완료, 실제 회사 데이터 기반 field validation 완료, 자동 정비 명령 실행.
- 배포 기준: `release\MaintiQ_Predict_Setup.exe`는 GitHub Release 첨부 파일로 배포하고, 코드 저장소에는 커밋하지 않습니다.

## 폴더 구조

```text
app/            Streamlit 사용자/Admin 화면
data/           AI4I 기본 데이터
desktop_app/    Windows 데스크톱 앱
installer/      Inno Setup installer 설정
samples/        사용자 예측 샘플 CSV
scripts/dev/    개발, 검증, Lite, 로컬 보조 스크립트
src/            학습, 예측, SPC, GenAI, 검증 엔진
tests/          자동 테스트
tools/          배포 검증과 runtime snapshot 도구
```

오류 로그는 `%LOCALAPPDATA%\MaintiQ Predict\logs\`에 저장됩니다. API key와 비밀번호는 저장하지 않습니다.
