# AI Predictive SPC Dashboard

AI4I 2020 공개 데이터를 기반으로 제조 설비 고장 가능성을 예측하고, Predictive SPC 그래프, SHAP 위험요인, GenAI 관리자 리포트, 승인형 작업지시 이력을 연결한 제품형 MVP입니다.

이 저장소는 실제 PLC/SCADA 운영 제품이 아닙니다. 센서 CSV, 로컬 FastAPI, SQLite, Streamlit을 이용해 현장 시스템으로 확장 가능한 데이터 흐름을 검증합니다.

## 주요 기능

- 센서 CSV 업로드 예측
- XGBoost 기반 고장 확률 및 High Risk 판정
- Predictive SPC risk trend / control chart
- SHAP 기반 row별 위험요인 요약
- Gemini 또는 OpenAI 기반 GenAI 관리자 참고 리포트
- field-event 입력, 작업지시 초안, 승인/검토/반려 기록
- 별도 Admin 콘솔에서 모델/검증/연구 산출물 확인
- SMOTE, threshold tuning, SPC-only 대비 ML+SPC 비교 실험

## 폴더 구조

```text
.
├─ app/
│  ├─ dashboard.py          # 사용자용 제품형 MVP Streamlit 앱
│  └─ admin_dashboard.py    # 관리자/검증용 Streamlit 콘솔
├─ data/
│  └─ ai4i2020.csv
├─ outputs/
│  ├─ metrics.json
│  ├─ baseline_predictions.csv
│  ├─ threshold_summary.json
│  ├─ spc_summary.json
│  ├─ spc_timeseries.csv
│  ├─ ai_manager_report.md
│  └─ ...
├─ src/
│  ├─ train_baseline.py
│  ├─ stage4_explain.py
│  ├─ predictive_spc.py
│  ├─ future_deviation.py
│  ├─ api_server.py
│  ├─ realtime_ops.py
│  ├─ compare_model_strategies.py
│  ├─ compare_spc_ml_alerts.py
│  └─ verify_project.py
├─ streamlit_app.py         # Streamlit Cloud/Hugging Face 기본 entrypoint
├─ run_dashboard.bat
├─ run_admin_dashboard.bat
├─ run_stage1_20_gemini.ps1
├─ run_stage1_20_openai.ps1
├─ run_verify.bat
└─ requirements.txt
```

## 설치

Windows PowerShell 또는 명령 프롬프트에서 저장소 폴더로 이동한 뒤 실행합니다.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

이미 `.venv`가 준비되어 있다면 설치 단계는 다시 실행하지 않아도 됩니다.

## 사용자 앱 실행

사용자 앱은 operator 로그인을 요구합니다. 비밀번호는 환경변수나 Streamlit secrets로만 설정하고 Git에 저장하지 않습니다.

PowerShell 예시:

```powershell
$env:APP_OPERATOR_PASSWORD="your-operator-password"
```

```powershell
.\run_dashboard.bat
```

브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:8501
```

사용자 앱은 제품형 MVP 화면만 보여줍니다.

1. `시작하기`
2. `성과 요약`
3. `CSV 예측`
4. `SPC 그래프`
5. `GenAI 리포트`
6. `작업지시`
7. `적용 범위`

## Admin 콘솔 실행

개발/검증용 상세 탭은 사용자 앱에서 숨기지 않고 별도 앱으로 분리했습니다.

Admin 콘솔은 admin 로그인을 요구합니다.

```powershell
$env:APP_ADMIN_PASSWORD="your-admin-password"
```

```powershell
.\run_admin_dashboard.bat
```

브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:8502
```

Admin 콘솔에서는 모델 비교, threshold 조정, SHAP, row 시뮬레이션, 비교 실험, 연구 문서, 검증 산출물을 확인합니다.

Admin 콘솔 상단의 운영 모니터링 영역에서는 DB 상태, 최근 event/draft/decision 수, 감사 로그, 주요 산출물 상태, API key 패턴 스캔 결과를 확인합니다.

## CSV 입력 형식

사용자 앱의 `CSV 예측` 탭에서 샘플 CSV를 다운로드할 수 있습니다. 업로드 CSV는 아래 컬럼을 포함해야 합니다.

```csv
Type,Air temperature [K],Process temperature [K],Rotational speed [rpm],Torque [Nm],Tool wear [min]
L,298.1,308.6,1551,42.8,0
M,298.2,308.7,1408,46.3,3
H,299.4,309.2,1320,58.2,120
```

처리 흐름:

```text
CSV 업로드
→ 컬럼명, Type 값, 숫자 형식 검증
→ AI4I 기준 전처리 및 one-hot feature 정렬
→ XGBoost predict_proba
→ threshold 기준 High Risk 판정
→ 확률 그래프, 예측표, 위험요인, CSV 다운로드 제공
```

## GenAI API key

사용자 앱 왼쪽 사이드바에서 Gemini 또는 OpenAI를 선택하고 API key를 입력하면 `GenAI 리포트` 탭에서 새 관리자 참고 리포트를 생성할 수 있습니다.

- API key는 현재 Streamlit 세션에서만 사용합니다.
- API key는 파일, `.env`, Git 기록에 저장하지 않습니다.
- API key가 없으면 저장된 기본 리포트만 표시합니다.

전체 파이프라인을 Gemini API로 다시 실행하려면:

```powershell
.\run_stage1_20_gemini.ps1
```

OpenAI API로 실행하려면:

```powershell
.\run_stage1_20_openai.ps1
```

성공 시 `outputs/ai_report_context.json`의 `report_generation_mode`는 아래 중 하나로 저장됩니다.

```text
gemini_generate_content:<model>
openai_responses_api:<model>
```

## 로컬 API

FastAPI 서버를 실행합니다.

```powershell
.\run_api.bat
```

문서 UI:

```text
http://127.0.0.1:8000/docs
```

주요 endpoint:

- `GET /health`
- `GET /model-info`
- `POST /predict`
- `POST /predict-batch`
- `POST /field-event`
- `POST /work-order-draft`
- `POST /work-order-decision`

`/work-order-decision`은 `approve`, `reject`, `needs_review` 중 하나를 기록합니다. 자동 정비 명령을 실행하지 않고, 사람이 승인하는 작업지시 workflow만 저장합니다.

## 논문 검증 근거 생성

모델 전략, alert 전략, 운영 가치 시뮬레이션, 제품 기능 비교, workflow traceability를 생성하려면 아래 명령을 실행합니다.

```powershell
.\.venv\Scripts\python.exe src\compare_model_strategies.py
.\.venv\Scripts\python.exe src\compare_spc_ml_alerts.py
.\.venv\Scripts\python.exe src\evaluate_operational_value.py
.\.venv\Scripts\python.exe src\evaluate_workflow_traceability.py
.\.venv\Scripts\python.exe src\create_product_comparison_summary.py
```

주요 산출물:

- `outputs/model_strategy_comparison.csv`
- `outputs/model_strategy_summary.md`
- `outputs/model_strategy_pr_curve.png`
- `outputs/spc_vs_ml_comparison.csv`
- `outputs/spc_vs_ml_summary.md`
- `outputs/operational_value_simulation.csv`
- `outputs/operational_value_simulation.png`
- `outputs/product_capability_comparison.md`
- `outputs/workflow_traceability_summary.md`
- `outputs/thesis_evidence_pack.md`

비교 결과는 SMOTE나 특정 threshold가 항상 좋다는 주장을 강제하지 않습니다. precision, recall, F1-score, PR-AUC, alert count, false alarm count의 trade-off를 확인하기 위한 근거입니다.

운영 가치 시뮬레이션은 실제 원화 비용 절감 실증이 아니라 false alarm, missed failure, planned action에 상대 가중치를 둔 normalized cost simulation입니다. 논문에서는 `85% 시간 단축`, `30% 비용 절감`, `실제 공장 ROI 검증`처럼 쓰지 않습니다.

상용 제품 비교는 IBM Maximo, AWS IoT SiteWise, Azure IoT Operations, Siemens Insights Hub를 기능적 참조 시스템으로 둡니다. 본 시스템이 상용 플랫폼보다 전체적으로 우월하다고 주장하지 않고, 연구 재현성, ML+SPC 비교, SHAP/GenAI 설명, 승인형 작업지시 workflow 연결성을 차별점으로 설명합니다.

## 검증

기본 검증:

```powershell
.\run_verify.bat
```

개별 검증:

```powershell
.\.venv\Scripts\python.exe -m compileall -q src app
.\.venv\Scripts\python.exe src\verify_project.py
.\.venv\Scripts\python.exe src\verify_stage19_20_integration.py
```

정상 상태에서는 `All project verification checks passed.`가 출력됩니다.

## Streamlit Cloud / Hugging Face Spaces 배포

배포 플랫폼의 app file은 기본적으로 아래 파일을 사용합니다.

```text
streamlit_app.py
```

Streamlit Cloud:

1. GitHub에 저장소를 push합니다.
2. Streamlit Cloud에서 새 app을 만들고 repository를 선택합니다.
3. app file을 `streamlit_app.py`로 지정합니다.
4. platform secrets에 `APP_OPERATOR_PASSWORD`를 등록합니다.
5. Gemini/OpenAI API를 사용할 경우 platform secrets에 `GEMINI_API_KEY` 또는 `OPENAI_API_KEY`를 등록합니다.

Hugging Face Spaces:

1. 새 Space를 만들고 SDK를 `Streamlit`으로 선택합니다.
2. 저장소 파일을 업로드하거나 GitHub 저장소를 연결합니다.
3. secrets에 `APP_OPERATOR_PASSWORD`를 등록합니다.
4. Gemini/OpenAI API를 사용할 경우 secrets에 API key를 등록합니다.
5. 운영 DB, `.venv`, `.env`, 실제 회사 원본 데이터는 업로드하지 않습니다.

클라우드에서 화면이 열린다는 것은 웹 데모 배포를 의미합니다. 실제 공장 센서 연결, PLC/SCADA 운영, 자동 정비 명령 실행이 완료되었다는 뜻은 아닙니다.

## 보안 및 적용 범위

- API key를 코드, README, `.env`, Git 기록에 저장하지 않습니다.
- operator/admin password를 코드, README, `.env`, Git 기록에 저장하지 않습니다.
- GenAI 출력은 관리자 참고용입니다. 자동 정비 명령으로 사용하지 않습니다.
- AI4I row playback은 실제 실시간 센서 스트림이 아니라 공개 데이터 기반 시뮬레이션입니다.
- 실제 현장 적용 전에는 회사 데이터 계약, 단위 표준화, 보안 승인, 접근 제어, 운영 DB, 감사 로그, threshold 재검증이 필요합니다.
