# 발표 당일 백업 체크리스트

## 1. 발표 직전 실행

1. 프로젝트 폴더에서 `run_dashboard.bat`를 실행합니다.
2. 브라우저에서 `http://127.0.0.1:8501`이 열리는지 확인합니다.
3. 탭이 한 줄에 최대한 보이도록 브라우저 창을 넓게 둡니다.
4. 첫 화면은 `성과 요약` 탭에 맞춰 둡니다.

## 2. 반드시 챙길 백업 파일

- 대시보드 실행 파일: `run_dashboard.bat`
- 발표 대본: `outputs/demo_script_may11.md`
- 예상 질문 답변: `outputs/midterm_qna_may11.md`
- 발표 요약: `outputs/presentation_summary.md`
- 리허설 체크리스트: `outputs/rehearsal_checklist_may11.md`
- Stage 10 운영 요약: `outputs/stage10_operations_summary.md`
- 주요 그림: `outputs/confusion_matrix.png`, `outputs/pr_curve.png`, `outputs/threshold_tuning.png`, `outputs/shap_summary.png`, `outputs/shap_bar.png`
- 주요 수치 파일: `outputs/metrics.json`, `outputs/threshold_summary.json`

## 3. Streamlit이 안 뜰 때 설명 순서

1. `outputs/presentation_summary.md`로 전체 연구 흐름을 설명합니다.
2. `outputs/metrics.json` 또는 `outputs/pr_curve.png`로 XGBoost가 대표 모델인 이유를 설명합니다.
3. `outputs/threshold_tuning.png`와 `outputs/threshold_summary.json`으로 threshold 0.87 선택 이유를 설명합니다.
4. `outputs/shap_summary.png`와 `outputs/shap_bar.png`로 SHAP 해석을 설명합니다.
5. `outputs/local_case_explanation.md`로 UDI 6498 개별 사례를 설명합니다.
6. `outputs/stage10_operations_summary.md`로 최종 통합 MVP와 다음 운영 단계를 설명합니다.
7. `outputs/midterm_qna_may11.md`로 실시간/LLM/현장 적용 질문에 답합니다.

## 4. 장애 대응 멘트

> 대시보드는 로컬 Streamlit으로 실행되는 발표용 PoC입니다. 혹시 실행 환경 문제로 화면이 늦게 뜨면, 같은 결과가 저장된 Markdown과 PNG 산출물로 설명드리겠습니다.

## 5. 발표 전 최종 체크

- `run_dashboard.bat` 실행 확인
- `outputs/*.png` 그림 파일 확인
- `outputs/demo_script_may11.md`와 `outputs/midterm_qna_may11.md` 열람 가능 여부 확인
- 인터넷 없이도 설명할 수 있는지 확인
