# MaintiQ Predict - Smart Manufacturing Predictive Maintenance Dashboard

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![UI](https://img.shields.io/badge/UI-PySide6%20Desktop-orange)
![ML](https://img.shields.io/badge/ML-XGBoost%20%7C%20Logistic%20Regression-green)
![Data](https://img.shields.io/badge/Data-AI4I%202020%20%7C%20SCANIA%20%7C%20MetroPT--3-informational)

MaintiQ Predict는 제조 설비 센서 CSV를 불러와 고장 위험도, 위험 우선순위, AI 관리자 리포트, 작업지시 이력을 확인할 수 있는 Windows 데스크톱 예지보전 MVP입니다.

`MaintiQ`는 **Maintenance**, **Intelligence**, **Quality**를 결합한 이름입니다. 유지보수 데이터를 지능적으로 분석해 설비 고장 위험을 예측하고, 품질 및 운영 안정성을 높이는 시스템이라는 의미를 담고 있습니다.

## 한눈에 보기

| 구분 | 내용 |
| --- | --- |
| 목적 | 스마트 제조 설비의 고장 위험 예측과 점검 우선순위 확인 |
| 입력 | AI4I 형식 또는 회사식 센서 CSV |
| 모델 | Logistic Regression baseline, XGBoost baseline, SCANIA cost-sensitive model |
| 앱 | Windows PySide6 데스크톱 앱, Streamlit 관리자 검증 콘솔 |
| 결과 | 고장 확률, 위험 등급, 우선순위 CSV, 선택형 AI 관리자 리포트 |
| 데이터 | AI4I 2020 메인 학습 데이터, SCANIA/MetroPT-3/FEMTO 공개 benchmark |

## 주요 화면 흐름

1. 센서 CSV 불러오기
2. 컬럼 자동 매핑 및 데이터 품질 확인
3. 고장 위험도 예측 실행
4. 위험 우선순위 확인
5. 결과 CSV 저장 및 작업지시 검토

## 설치 순서

Windows 기준입니다. PowerShell에서 아래 순서대로 실행합니다.

### 1. 코드 다운로드

Git이 설치되어 있으면:

```powershell
git clone https://github.com/HwangYH98/mainitq-predict-spc.git
cd mainitq-predict-spc
```

Git이 없으면 GitHub 화면에서 **Code > Download ZIP**을 눌러 압축을 풀고, PowerShell에서 압축을 푼 폴더로 이동합니다.

```powershell
cd "압축을_푼_폴더_경로"
```

### 2. Python 가상환경 만들기

```powershell
py -3 -m venv .venv
```

### 3. 필요한 패키지 설치

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. 데스크톱 앱 실행

```powershell
.\run_desktop_app.bat
```

정상 실행되면 MaintiQ Predict 데스크톱 앱이 열립니다.

설치가 제대로 되었는지 먼저 확인하려면 아래 명령을 실행합니다.

```powershell
.\.venv\Scripts\python.exe desktop_app\main.py --check
```

## 데스크톱 앱 실행

정밀 분석 모드:

```powershell
.\run_desktop_app.bat
```

또는 직접 실행:

```powershell
.\.venv\Scripts\python.exe desktop_app\main.py
```

빠른 점검 모드:

```powershell
.\.venv\Scripts\python.exe desktop_app\lite_main.py
```

관리자 검증 콘솔:

```powershell
.\run_admin_dashboard.bat
```

기본 주소:

```text
http://127.0.0.1:8502
```

## 샘플 CSV 시연

시연용 샘플 파일은 `samples/company_sensor_sample.csv`입니다.

1. MaintiQ Predict를 실행합니다.
2. 데이터 예측 화면으로 이동합니다.
3. `samples/company_sensor_sample.csv`를 불러옵니다.
4. 자동 컬럼 매핑 결과를 확인합니다.
5. 예측을 실행하고 고장 위험도, 위험 우선순위, 결과 CSV 저장 기능을 확인합니다.

사용자용 자세한 절차는 [docs/USER_MANUAL.md](docs/USER_MANUAL.md)에 정리되어 있습니다.

## 사용 데이터

### AI4I 2020

- 위치: `data/ai4i2020.csv`
- 용도: 기본 고장 예측 모델 학습, 평가, 제품 시연
- target: `Machine failure`
- 주요 입력 컬럼:

```text
Type
Air temperature [K]
Process temperature [K]
Rotational speed [rpm]
Torque [Nm]
Tool wear [min]
```

전처리 흐름:

- `UDI`, `Product ID` 같은 식별자 컬럼 제거
- `TWF`, `HDF`, `PWF`, `OSF`, `RNF` 같은 정답 누수 가능 컬럼 제거
- `Type` one-hot encoding
- stratified train/test split
- Logistic Regression, XGBoost baseline 학습 및 평가

기본 학습 파이프라인 실행:

```powershell
.\.venv\Scripts\python.exe src\train_baseline.py
```

생성 파일:

```text
outputs/metrics.json
outputs/confusion_matrix.png
outputs/pr_curve.png
outputs/baseline_predictions.csv
```

### SCANIA Component X

- 용도: 추가 공개 산업 benchmark와 비용 기반 검증
- 로컬 위치: `data_external/scania_component_x/`
- 원본 데이터는 외부 공개 데이터이므로 별도로 내려받아 `data_external/` 아래에 둡니다.
- SCANIA 데이터가 준비되어 있으면 아래 명령으로 비용 최적화 검증 산출물을 만들 수 있습니다.

```powershell
.\.venv\Scripts\python.exe src\scania_official_cost_validation.py --data-dir data_external\scania_component_x
```

## 핵심 기능

- AI4I형 CSV 자동 감지 및 기본 고장확률 예측
- SCANIA형 CSV 자동 감지 및 비용 기반 예측
- CSV 품질 진단과 컬럼 자동 매핑
- 고장 위험도와 위험 우선순위 확인
- Gemini 또는 OpenAI API key를 세션에서만 입력해 AI 관리자 리포트 생성
- 작업지시 초안 생성과 승인/검토/반려 기록
- Streamlit 관리자 콘솔에서 모델 검증과 공개 benchmark 확인

## 검증 명령

기본 학습 파이프라인 검증:

```powershell
.\.venv\Scripts\python.exe src\train_baseline.py
```

테스트 실행:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

문법 검사:

```powershell
.\.venv\Scripts\python.exe -m compileall -q src app desktop_app streamlit_app.py
```

데스크톱 앱 점검:

```powershell
.\.venv\Scripts\python.exe desktop_app\main.py --check
.\.venv\Scripts\python.exe desktop_app\main.py --engine-smoke-test
```

전체 재현 검증:

```powershell
cmd /c "run_verify.bat < NUL"
```

`run_verify.bat`는 로컬에서 여러 검증 산출물을 다시 생성합니다. 생성된 `outputs/` 파일은 GitHub에 올리지 않고 필요할 때 재생성합니다.

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

## 주요 폴더 구조

```text
app/           Streamlit 관리자 콘솔
data/          기본 AI4I 2020 CSV
desktop_app/   Windows 데스크톱 앱
docs/          사용자 매뉴얼과 배포 문서
samples/       시연용 샘플 CSV
src/           학습, 예측, SPC, GenAI, 검증 엔진
tests/         자동 테스트
```

## 오류 로그

오류가 발생했을 때는 앱의 `오류 로그 내보내기` 버튼을 사용하거나 아래 명령을 실행합니다.

```powershell
.\.venv\Scripts\python.exe desktop_app\main.py --export-crash-logs
.\.venv\Scripts\python.exe desktop_app\lite_main.py --export-crash-logs
```

오류 로그 위치는 `%LOCALAPPDATA%\MaintiQ Predict\logs\`입니다. API key와 비밀번호는 저장하지 않습니다.
