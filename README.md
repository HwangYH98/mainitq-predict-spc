# Capstone Predictive SPC Baseline

## 현재 실행 기준

현재 프로젝트 폴더명은 아래 경로를 기준으로 합니다.

```text
C:\Users\hoon9\Documents\capstone design
```

이 프로젝트는 전역 `python`이나 전역 `py -3` 환경이 아니라, 프로젝트 안의 `.venv` 가상환경을 우선 사용합니다. 이 PC에서는 필요한 패키지가 `.venv`에 설치되어 있으므로 실행 명령은 기본적으로 아래 형식을 사용합니다.

```powershell
.\.venv\Scripts\python.exe src\train_baseline.py
```

## 실시간형 PoC 확장 기준

최종발표용 데모 흐름은 `AI4I row playback -> XGBoost 현재 고장 위험 예측 -> 미래 10-step 이탈 예측 -> SHAP 원인 설명 -> Gemini/OpenAI GenAI 관리자 리포트 -> Stage 19 field-event API -> Stage 20 operator decision logging -> Streamlit 대시보드 시연`입니다.

여기서 실시간 스트리밍은 실제 공장 센서 feed가 아니라 AI4I 2020 데이터의 `UDI` 순서를 시간축처럼 재생하는 simulated real-time stream입니다. 미래 이탈 예측도 실제 운영 forecast가 아니라 UDI 순서 기반 lag/rolling feature로 다음 10 step의 위험 이탈 후보를 예측하는 local PoC입니다.

Stage 1~20 전체 결과를 GenAI API 필수 모드로 다시 만들고 싶으면 기본 경로인 `run_stage1_20_gemini.ps1`을 실행합니다. OpenAI 경로가 필요하면 `run_stage1_20_openai.ps1`도 사용할 수 있습니다. 두 스크립트 모두 key를 파일에 저장하지 않고, 실행 중 환경변수로만 사용합니다.

Gemini/OpenAI 없이 로컬 산출물만 빠르게 다시 만들고 싶으면 `run_all.bat`을 실행할 수 있습니다. 단, 이 경로는 full Stage 1~20 검증 기준이 아니라 fallback 리포트가 포함될 수 있습니다.

기존 코드와 산출물이 정상인지 한 번에 확인하려면 `run_verify.bat`을 실행합니다. 이 배치 파일은 Stage 14 회사 데이터 재학습, Stage 15~18 로컬 운영 검증, Stage 19~20 로컬 field-event/decision 검증, Stage 19~20 문서 검증까지 포함합니다. `verify_project.py`는 GenAI 리포트가 fallback이면 실패합니다.

## 프로젝트 목적

이 프로젝트는 AI4I 2020 Predictive Maintenance Dataset을 사용해 제조 설비의 고장 여부를 예측하고, 그 결과를 사람이 이해할 수 있는 대시보드로 보여주는 predictive maintenance / Predictive SPC PoC입니다. 현재 단계에서는 데이터 로드, 전처리, Logistic Regression 학습, XGBoost 학습, 성능 평가, threshold 조정, SHAP 기반 해석, Streamlit 대시보드, Row 시뮬레이션, 현장 CSV 입력 MVP, Stage 9 실제 적용성 정리, Stage 10 운영 요약, AI4I 시간축 시뮬레이션, Predictive SPC chart, Gemini/OpenAI GenAI 관리자 리포트, Stage 19 field-event API, Stage 20 operator decision logging까지 로컬에서 실제 실행되도록 구현합니다.

현재 시스템은 완성된 상용 제품이 아니라, 중소 제조 현장에서 확장 가능한 연구용 PoC입니다. Time-Series는 실제 센서 스트리밍이 아니라 AI4I row playback 기반 시뮬레이션입니다. Stage 1~20 full run에서는 Gemini 또는 OpenAI 기반 GenAI 관리자 리포트가 필수이며, fallback 리포트는 full 검증 통과로 인정하지 않습니다.

## GenAI API 연결

API key는 코드, README, `.bat`, `.env` 파일에 저장하지 않습니다. Stage 1~20 full run의 기본 경로는 Gemini API입니다.

```powershell
.\run_stage1_20_gemini.ps1
```

이 스크립트는 `GEMINI_API_KEY`를 숨김 입력으로 받은 뒤, 먼저 `src\check_gemini_connection.py`로 짧은 Gemini `generateContent` preflight를 실행합니다. preflight가 성공할 때만 baseline 학습부터 Stage 20 검증까지 진행합니다. 성공하면 `outputs\ai_report_context.json`의 `report_generation_mode`가 `gemini_generate_content:gemini-2.5-flash` 형태로 바뀝니다.

preflight만 따로 확인하고 싶으면 같은 PowerShell 창에서 아래처럼 실행합니다. key는 현재 터미널 환경변수로만 둡니다.

```powershell
$env:GEMINI_API_KEY = "..."
.\.venv\Scripts\python.exe src\check_gemini_connection.py
Remove-Item Env:\GEMINI_API_KEY
```

기본 Gemini 모델은 `gemini-2.5-flash`입니다. 수요 급증으로 `503 UNAVAILABLE`이 나오면 스크립트가 자동으로 `gemini-2.5-flash-lite`도 시도합니다. 다른 모델 순서를 쓰려면 실행 전에 `GEMINI_MODEL_CANDIDATES`를 쉼표로 구분해 지정할 수 있습니다.

```powershell
$env:GEMINI_MODEL_CANDIDATES = "gemini-2.5-flash-lite,gemini-2.5-flash"
.\run_stage1_20_gemini.ps1
```

OpenAI 경로도 보존되어 있습니다. OpenAI로 full run을 하고 싶으면 아래 명령을 사용합니다.

```powershell
.\run_stage1_20_openai.ps1
```

OpenAI 기본 모델은 `gpt-5-mini`입니다. project 또는 organization 헤더가 필요한 계정이면 `OPENAI_PROJECT_ID`, `OPENAI_ORG_ID`를 실행 전에 지정할 수 있습니다.

Gemini 또는 OpenAI 오류가 발생하면 터미널에 출력되는 `error_message`, `error_status`, `error_type`, `error_code`, `error_param`, `x-request-id`를 확인합니다. 주로 모델 접근 권한, project/org 설정, key 유효성, 현재 계정에서 허용되지 않는 모델 ID 때문에 실패할 수 있습니다. API key 값은 오류 출력에 포함하지 않습니다.

OpenAI API가 켜진 대시보드를 실행하려면 아래 명령을 사용합니다.

```powershell
.\run_openai_dashboard.ps1
```

노출된 key는 각 provider dashboard에서 폐기하고 새 key를 사용해야 합니다.

## 현재 연구 단계

전체 연구 파이프라인 중 현재 상태는 **Stage 1~20 로컬 통합 PoC 구현 완료**입니다. 단, 이는 실제 PLC/SCADA/클라우드 배포 완료가 아니라 로컬 field-event API, SQLite 이력, 작업지시 초안, operator decision logging까지 연결한 검증 가능한 PoC입니다.

- Stage 1 개발환경 세팅: Python 가상환경, requirements.txt, 프로젝트 폴더 구조 준비
- Stage 2 데이터 준비: AI4I 2020 CSV 로드, target 확인, 전처리 준비
- Stage 3 Baseline 모델링: Logistic Regression, XGBoost 학습, 성능 지표와 시각화 결과 저장
- Stage 4-lite 모델 개선 및 해석: XGBoost threshold 조정, SHAP summary plot, 개별 예측 사례 해석
- Stage 5 결과 대시보드 MVP: 모델 성능, threshold, SHAP, 발표 요약을 Streamlit에서 확인
- Stage 6-lite Row 시뮬레이션: 저장된 test row를 넘기며 고장 확률과 High Risk 여부 확인
- Stage 7-lite 현장 데이터 입력 MVP: 사용자가 CSV를 업로드하면 XGBoost 고장 확률과 위험 등급 계산
- Stage 8-lite 자연어 처방 초안: 실제 LLM 호출이 아니라 SHAP 근거를 바탕으로 관리자 참고용 점검 문장 생성
- Stage 9 실제 적용성 정리: 실제 사업장 적용 조건, 데이터 요구사항, 한계, 재검증 항목 문서화
- Stage 10-lite 운영 요약 MVP: 모델 상태, threshold, High Risk row 수, 주요 산출물 다운로드를 대시보드에서 통합 확인
- Stage 11 Predictive SPC: AI4I UDI 순서 기반 시간축 시뮬레이션, risk trend, rolling mean, control limit chart 생성
- Stage 12 GenAI 리포트: Stage 1~20 full run 기준 Gemini 또는 OpenAI API 관리자 리포트 생성
- Stage 13 미래 이탈 예측: UDI 순서 기반 lag/rolling feature로 미래 10-step 최대 risk와 이탈 여부 예측
- Stage 14-lite 회사 데이터 재학습 PoC: 라벨 있는 회사 CSV에 대해 컬럼 선택, 단위 표준화, 회사별 재학습, SHAP 요약 생성
- Stage 15-lite file-drop streaming: 새 CSV를 `outputs/realtime_stream/incoming`에 넣으면 로컬 예측 이벤트로 처리
- Stage 16-lite FastAPI 예측 서버: 외부 시스템이 센서 row를 POST하면 고장 확률과 risk label 반환
- Stage 17-lite SQLite 이력 저장: 예측 이벤트, SHAP 근거, 작업지시 초안을 `outputs/operations.db`에 저장
- Stage 18-lite 작업지시 초안: 자동 정비 명령이 아니라 관리자 승인용 JSON/Markdown 초안 생성
- Stage 19-lite 로컬 field-event API: `POST /field-event`로 equipment_id, timestamp, source_system, sensor row를 받아 예측 이벤트로 저장
- Stage 20-lite operator decision logging: `POST /work-order-decision`으로 approve/reject/needs_review 결정을 SQLite와 CSV에 기록

Stage 1~20은 발표용 로컬 통합 PoC입니다. 실제 공장 PLC/SCADA 연동, 클라우드 배포, 무인 자동 정비 실행은 구현 완료로 주장하지 않습니다.

## 폴더 구조

현재 작업 폴더를 아래 프로젝트 루트처럼 사용합니다.

```text
capstone design/
├─ data/
│  └─ ai4i2020.csv
├─ src/
│  ├─ data.py
│  ├─ evaluate.py
│  ├─ predictive_spc.py
│  ├─ future_deviation.py
│  ├─ stage4_explain.py
│  └─ train_baseline.py
├─ outputs/
│  ├─ metrics.json
│  ├─ confusion_matrix.png
│  ├─ pr_curve.png
│  ├─ baseline_predictions.csv
│  ├─ threshold_metrics.csv
│  ├─ threshold_summary.json
│  ├─ threshold_tuning.png
│  ├─ shap_summary.png
│  ├─ shap_bar.png
│  ├─ local_case_explanation.md
│  ├─ local_case_explanation.json
│  ├─ presentation_summary.md
│  ├─ research_plan_may11.md
│  ├─ midterm_presentation_guide.md
│  ├─ midterm_qna_may11.md
│  ├─ rehearsal_checklist_may11.md
│  ├─ presentation_day_backup_checklist.md
│  ├─ final_stage_roadmap.md
│  ├─ stage9_field_applicability.md
│  ├─ stage10_operations_summary.md
│  ├─ spc_timeseries.csv
│  ├─ spc_summary.json
│  ├─ spc_risk_chart.png
│  ├─ spc_control_chart.png
│  ├─ future_deviation_predictions.csv
│  ├─ future_deviation_metrics.json
│  ├─ future_deviation_chart.png
│  ├─ ai_report_context.json
│  ├─ ai_manager_report.md
│  ├─ final_paper_outline.md
│  ├─ final_presentation_plan.md
│  └─ demo_script_may11.md
├─ notebooks/
├─ app/
│  └─ dashboard.py
├─ requirements.txt
└─ README.md
```

## 데이터셋 위치

입력 데이터는 아래 경로에 둡니다.

```text
data/ai4i2020.csv
```

이 파일이 없으면 코드는 억지로 학습을 진행하지 않고 중단됩니다. 데이터 파일명은 `ai4i2020.csv`로 맞추고, 반드시 `data/` 폴더 안에 저장해야 합니다.

예측 대상 target 컬럼은 `Machine failure`입니다. 이 컬럼은 0이면 정상, 1이면 고장을 의미하므로 binary classification 문제로 처리합니다.

## 전처리 방식

`UDI`, `Product ID`는 단순 식별자에 가까운 컬럼이므로 모델 입력에서 제거합니다.

`TWF`, `HDF`, `PWF`, `OSF`, `RNF`는 고장 원인 라벨에 가까워 target 정보를 너무 직접적으로 알려줄 수 있습니다. 발표용 baseline이 실제 센서 기반 예측에 가깝도록 이 컬럼들도 제거합니다.

`Type` 컬럼은 문자값이므로 one-hot encoding으로 숫자 컬럼으로 바꿉니다.

train/test split은 `stratify=y`와 `random_state=42`를 사용합니다. 이렇게 하면 고장/정상 비율을 최대한 유지하면서 매번 같은 결과가 나오게 할 수 있습니다.

## 설치 명령어

아래 명령어는 현재 폴더에 `.venv` 가상환경을 만듭니다. 가상환경은 프로젝트 전용 Python 공간입니다.

```powershell
py -3 -m venv .venv
```

아래 명령어는 `.venv` 안의 pip를 최신 버전으로 업데이트합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

아래 명령어는 `requirements.txt`에 적힌 baseline 필수 패키지를 설치합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 실행 명령어

아래 명령어는 Stage 1~20 로컬 통합 PoC를 Gemini 기반 GenAI 필수 모드로 실행합니다. 실행 중 숨김 입력으로 `GEMINI_API_KEY`를 받고, key는 파일에 저장하지 않습니다.

```powershell
.\run_stage1_20_gemini.ps1
```

OpenAI Responses API로 같은 full run을 실행하려면 아래 명령어를 사용할 수 있습니다.

```powershell
.\run_stage1_20_openai.ps1
```

아래 명령어는 데이터 로드, 전처리, 모델 학습, 평가, 결과 저장을 한 번에 실행합니다.

```powershell
.\.venv\Scripts\python.exe src\train_baseline.py
```

아래 명령어는 Stage 4-lite를 실행합니다. XGBoost를 다시 학습한 뒤 threshold를 조정하고 SHAP 그림과 개별 사례 해석을 저장합니다.

```powershell
.\.venv\Scripts\python.exe src\stage4_explain.py
```

아래 명령어는 AI4I UDI 순서 기반 시간축 시뮬레이션, Predictive SPC chart, 관리자 참고용 AI 리포트 초안을 생성합니다. `REQUIRE_GENAI_REPORT=1`과 `AI_REPORT_PROVIDER=gemini`, `GEMINI_API_KEY`를 함께 설정하면 fallback 없이 실제 Gemini 리포트가 필요합니다. OpenAI를 쓰려면 `AI_REPORT_PROVIDER=openai`, `OPENAI_API_KEY`를 사용합니다.

```powershell
.\.venv\Scripts\python.exe src\predictive_spc.py
```

아래 명령어는 미래 10-step 이탈 예측을 실행합니다. UDI 순서 기반 simulated time axis에서 다음 10 step의 최대 risk와 이탈 여부를 예측합니다.

```powershell
.\.venv\Scripts\python.exe src\future_deviation.py
```

아래 명령어는 Stage 14-lite 회사 데이터 재학습 PoC를 검증합니다. 실제 회사 CSV가 없어도 AI4I를 회사 CSV처럼 변환한 데모 데이터로 재학습, threshold, SHAP bar, 예측 CSV, 모델 파일을 저장합니다.

```powershell
.\.venv\Scripts\python.exe src\verify_company_generalization.py
```

실제 라벨 있는 회사 CSV가 있을 때는 아래처럼 CSV 경로, target 컬럼, ID/time 컬럼, 단위 변환을 지정할 수 있습니다. 이 경우에도 같은 `outputs\custom_company_model` 폴더에 산출물이 저장됩니다.

```powershell
.\.venv\Scripts\python.exe src\verify_company_generalization.py --csv-path data\company_sample.csv --target-column quality_result --id-time-columns "asset_id,event_time" --unit-conversion "air_temp_celsius=Celsius -> Kelvin"
```

아래 명령어는 발표 요약, 연구계획, Stage 9 실제 적용성, Stage 10 운영 요약, Stage 19~20 운영 설계, 최종 논문/발표 구성안 Markdown을 다시 생성합니다.

```powershell
.\.venv\Scripts\python.exe src\create_presentation_summary.py
```

아래 명령어는 발표용 스크립트와 대시보드 코드에 문법 오류가 없는지 확인합니다.

```powershell
.\.venv\Scripts\python.exe -m compileall -q src app
```

아래 명령어는 Stage 15~18-lite의 file-drop streaming, FastAPI 예측, SQLite 저장, 관리자 승인용 작업지시 초안을 검증합니다.

```powershell
.\.venv\Scripts\python.exe src\verify_stage15_20.py
```

아래 명령어는 Stage 19~20 로컬 field-event API와 operator decision logging이 실제로 호출, 저장, CSV export까지 되는지 검증합니다.

```powershell
.\.venv\Scripts\python.exe src\verify_stage19_20_integration.py
```

아래 명령어는 Stage 19~20 운영 문서가 존재하는지, 필수 구현/guardrail 항목이 들어갔는지, 실제 배포 완료처럼 과장된 표현이 없는지 검증합니다.

```powershell
.\.venv\Scripts\python.exe src\verify_stage19_20_design.py
```

아래 명령어는 Stage 16-lite FastAPI 예측 서버를 실행합니다. 실행 후 `http://127.0.0.1:8000/docs`에서 API 문서를 볼 수 있습니다.

```powershell
.\run_api.bat
```

아래 명령어는 `outputs\realtime_stream\incoming` 폴더를 감시합니다. 새 CSV가 들어오면 예측하고 SQLite에 저장합니다.

```powershell
.\run_stream_watch.bat
```

아래 명령어는 Streamlit 대시보드를 실행합니다. 실행 후 브라우저에서 `http://127.0.0.1:8501`로 접속합니다.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app\dashboard.py --server.headless true --browser.gatherUsageStats false
```

## 생성되는 산출물

실행이 성공하면 `outputs/` 폴더에 아래 파일이 생성됩니다.

- `metrics.json`: Logistic Regression과 XGBoost의 precision, recall, f1-score, roc-auc, pr-auc 비교 결과
- `confusion_matrix.png`: 두 모델의 confusion matrix 비교 그림
- `pr_curve.png`: 두 모델의 precision-recall curve 비교 그림
- `baseline_predictions.csv`: test 데이터 기준 실제값, 예측값, 고장 예측 확률
- `threshold_metrics.csv`: XGBoost threshold별 precision, recall, f1-score
- `threshold_summary.json`: F1-score 기준으로 선택한 best threshold 요약
- `threshold_tuning.png`: threshold 변화에 따른 precision, recall, f1-score 그래프
- `shap_summary.png`: XGBoost SHAP summary plot
- `shap_bar.png`: 평균 절대 SHAP 값 기준 feature importance plot
- `local_case_explanation.md`: 개별 고장 예측 사례 1개의 해석 메모
- `local_case_explanation.json`: 같은 사례의 수치형 근거 저장 파일
- `presentation_summary.md`: 5월 11일 발표용 진행 요약
- `research_plan_may11.md`: Stage 1~10 연구계획과 실사업장 적용성 정리
- `midterm_presentation_guide.md`: PPT 없이 대시보드로 발표하는 클릭 순서와 멘트
- `midterm_qna_may11.md`: 중간발표 예상 질문과 짧은 답변
- `rehearsal_checklist_may11.md`: 3회 리허설 방식과 탭별 핵심 멘트
- `presentation_day_backup_checklist.md`: 발표 당일 실행/백업/장애 대응 체크리스트
- `final_stage_roadmap.md`: Stage 9, Stage 10-lite, 실제 LLM 연결 여부, 논문/보고서 작성 방향
- `stage9_field_applicability.md`: 실제 사업장 적용 조건, 한계, 재검증 항목 정리
- `stage10_operations_summary.md`: 모델 상태, threshold, High Risk row 수, 다운로드 산출물, 다음 운영 단계 정리
- `spc_timeseries.csv`: UDI 순서 시간축과 risk/SPC 계산 결과
- `spc_summary.json`: Predictive SPC 핵심 수치 요약
- `spc_risk_chart.png`: 고장 확률 trend, rolling mean, threshold, control limit 그림
- `spc_control_chart.png`: torque 기반 control chart
- `future_deviation_predictions.csv`: 미래 10-step 최대 risk와 이탈 여부 예측 결과
- `future_deviation_metrics.json`: 미래 이탈 예측 모델의 validation 성능 요약
- `future_deviation_chart.png`: 실제 미래 risk와 예측 미래 risk 비교 그림
- `custom_company_model/custom_metrics.json`: Stage 14-lite 회사 CSV 재학습 모델 성능 요약
- `custom_company_model/custom_predictions.csv`: Stage 14-lite 회사 CSV test row 예측 결과
- `custom_company_model/custom_threshold_summary.json`: Stage 14-lite XGBoost threshold 선택 요약
- `custom_company_model/custom_shap_bar.png`: Stage 14-lite 회사 데이터 SHAP feature importance 그림
- `custom_company_model/xgboost_model.joblib`, `custom_company_model/logistic_model.joblib`: Stage 14-lite 재학습 모델 파일
- `ai_report_context.json`: Gemini/OpenAI GenAI 관리자 리포트에 들어간 근거 JSON과 `report_generation_mode`
- `ai_manager_report.md`: 관리자 참고용 AI 리포트 초안
- `final_paper_outline.md`: 6월 최종 논문 작성 개요
- `final_presentation_plan.md`: 6월 최종발표 구성안
- `demo_script_may11.md`: 3분 대시보드 시연 스크립트
- `operations.db`: Stage 15~20-lite 예측 이벤트, 작업지시 초안, operator decision을 저장하는 SQLite DB
- `realtime_stream/latest_events.csv`: file-drop streaming과 field-event API의 최근 예측 이벤트 CSV
- `work_order_drafts/`: 관리자 승인용 작업지시 초안 Markdown 저장 폴더
- `work_order_decisions.csv`: Stage 20 operator decision 기록
- `stage15_20_architecture.md`: Stage 15~20 로컬 운영 통합 아키텍처와 한계 정리
- `stage19_20_operations_design.md`: Stage 19 field-event API와 Stage 20 operator decision logging 검증 조건

발표 문구는 **Stage 1~20 로컬 통합 PoC 구현 완료, 실제 PLC/SCADA/클라우드 배포 전 현장 데이터 재검증 필요**로 말합니다.

## 발표 전 준비 순서

1. `run_dashboard.bat`를 실행하고 `http://127.0.0.1:8501` 접속을 확인합니다.
2. `outputs/rehearsal_checklist_may11.md` 기준으로 3분 리허설을 2~3번 진행합니다.
3. `outputs/midterm_qna_may11.md`에서 실시간 여부, 실제 LLM 호출 여부, 실제 공장 적용 가능성 답변을 외웁니다.
4. `outputs/stage10_operations_summary.md`를 열어 운영 요약 수치와 다음 운영 단계를 확인합니다.
5. `outputs/presentation_day_backup_checklist.md` 기준으로 `outputs/*.png`, 발표 대본, Q&A 파일이 열리는지 확인합니다.
6. 발표에서는 현재 기능을 로컬 PoC로 설명하고, 실제 DB/API, 실제 LLM, 실시간 연동은 다음 단계로 제시합니다.

## 5월 11일에 보여줄 연구 결과물

- 실행 가능한 baseline 및 해석 코드: `src/data.py`, `src/evaluate.py`, `src/train_baseline.py`, `src/stage4_explain.py`
- 모델 성능표: `outputs/metrics.json`
- 모델 비교 그림: `outputs/confusion_matrix.png`, `outputs/pr_curve.png`
- 예측 결과 파일: `outputs/baseline_predictions.csv`
- threshold 조정 결과: `outputs/threshold_metrics.csv`, `outputs/threshold_tuning.png`
- SHAP 해석 결과: `outputs/shap_summary.png`, `outputs/shap_bar.png`
- 개별 사례 해석: `outputs/local_case_explanation.md`
- 연구계획 보완안: `outputs/research_plan_may11.md`
- PPT 없는 중간발표 진행안: `outputs/midterm_presentation_guide.md`
- 예상 질문 답변: `outputs/midterm_qna_may11.md`
- 리허설 체크리스트: `outputs/rehearsal_checklist_may11.md`
- 발표 당일 백업 체크리스트: `outputs/presentation_day_backup_checklist.md`
- Stage 9 실제 적용성 정리: `outputs/stage9_field_applicability.md`
- Stage 10 운영 요약: `outputs/stage10_operations_summary.md`
- Predictive SPC 산출물: `outputs/spc_risk_chart.png`, `outputs/spc_control_chart.png`, `outputs/spc_timeseries.csv`
- 미래 이탈 예측 산출물: `outputs/future_deviation_predictions.csv`, `outputs/future_deviation_metrics.json`, `outputs/future_deviation_chart.png`
- GenAI 관리자 리포트: `outputs/ai_manager_report.md`, `outputs/ai_report_context.json`
- 최종 논문/발표 구성안: `outputs/final_paper_outline.md`, `outputs/final_presentation_plan.md`
- 최종 단계 로드맵: `outputs/final_stage_roadmap.md`
- 발표용 대시보드: `app/dashboard.py`, `run_dashboard.bat`
- 재현 가능한 실행 설명: `README.md`

## 모델과 평가 지표

사용하는 baseline 모델은 `Logistic Regression`과 `XGBoost`입니다.

AI4I 데이터는 정상 데이터가 많고 고장 데이터가 적은 클래스 불균형 문제가 있습니다. 그래서 accuracy만 보면 모델이 좋아 보일 수 있습니다. 이 프로젝트에서는 precision, recall, f1-score, roc-auc, pr-auc를 함께 확인합니다.

## 보완된 연구 질문

- RQ1. 제조 설비 센서 데이터로 기계 고장을 사전에 예측할 수 있는가?
- RQ2. Logistic Regression 대비 XGBoost가 불균형 고장 데이터에서 더 나은 성능을 보이는가?
- RQ3. threshold 조정이 현장 경고 기준으로 의미 있는 성능 개선을 만드는가?
- RQ4. SHAP과 대시보드를 결합하면 비전문가도 예측 근거를 이해할 수 있는가?
- RQ5. CSV 업로드, Predictive SPC, 관리자 리포트로 확장하면 중소 제조 현장용 의사결정 지원 도구가 될 수 있는가?

## 다음 단계 TODO

- 실제 사업장 CSV 또는 DB/API 데이터로 모델 성능 재검증
- Gemini/OpenAI GenAI 관리자 리포트는 자동 정비 명령이 아니라 관리자 참고용 초안으로 제한
- 알림, 조치 이력, 재학습 관리가 포함된 운영형 대시보드 설계
- 논문 방법론/결과 작성
- 필요 시 SMOTE 등 클래스 불균형 처리 방법 비교

현재 단계에서는 로컬 field-event API까지 구현했지만, 실제 PLC/SCADA/클라우드 배포와 자동 정비 지시는 구현하지 않습니다. 발표에서는 AI4I row playback 기반 Predictive SPC, 실제 실행 provider에 맞춘 Gemini 또는 OpenAI GenAI 관리자 리포트, 로컬 API/SQLite/작업지시 결정 기록을 local PoC로 설명하고, 실제 운영망 연결은 다음 연구계획으로 제시합니다.
