import csv
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    """Read a JSON output file and explain what to run if it is missing."""
    if not path.exists():
        raise FileNotFoundError(
            f"Missing required file: {path}\n"
            "Please run these commands first:\n"
            "  .\\.venv\\Scripts\\python.exe src\\train_baseline.py\n"
            "  .\\.venv\\Scripts\\python.exe src\\stage4_explain.py"
        )

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_text(path: Path) -> str:
    """Read a Markdown output file and explain what to run if it is missing."""
    if not path.exists():
        raise FileNotFoundError(
            f"Missing required file: {path}\n"
            "Please run this command first:\n"
            "  .\\.venv\\Scripts\\python.exe src\\stage4_explain.py"
        )

    return path.read_text(encoding="utf-8")


def load_csv_rows(path: Path) -> list[dict]:
    """Read a saved CSV artifact into simple dictionaries."""
    if not path.exists():
        raise FileNotFoundError(
            f"Missing required file: {path}\n"
            "Please run this command first:\n"
            "  .\\.venv\\Scripts\\python.exe src\\train_baseline.py"
        )

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def metric_cell(value: float) -> str:
    """Format metric numbers consistently for a presentation table."""
    return f"{float(value):.4f}"


FEATURE_DISPLAY_NAMES = {
    "air_temperature_k": "air temperature",
    "process_temperature_k": "process temperature",
    "rotational_speed_rpm": "rotational speed",
    "torque_nm": "torque",
    "tool_wear_min": "tool wear",
    "type_h": "Type H",
    "type_l": "Type L",
    "type_m": "Type M",
}


def local_case_udi(local_case_details: dict) -> str:
    """Return the UDI for the selected SHAP case."""
    raw_case = local_case_details.get("raw_case", {})
    return str(raw_case.get("UDI", "selected case"))


def local_case_probability(local_case_details: dict) -> float:
    """Return the XGBoost failure probability for the selected SHAP case."""
    return float(local_case_details.get("probability", 0.0))


def local_case_feature_text(local_case_details: dict, limit: int = 2) -> str:
    """Summarize the strongest SHAP factors in short presentation language."""
    top_features = local_case_details.get("top_features", [])
    feature_names = [
        FEATURE_DISPLAY_NAMES.get(item.get("feature"), item.get("feature", "sensor factor"))
        for item in top_features[:limit]
    ]
    return "와 ".join(feature_names) if feature_names else "주요 센서 변수"


def prediction_summary(prediction_rows: list[dict], selected_threshold: float) -> dict:
    """Summarize saved test predictions for the Stage 10-lite operations view."""
    probabilities = [
        float(row["xgboost_probability"])
        for row in prediction_rows
        if row.get("xgboost_probability") not in (None, "")
    ]
    actual_failures = [
        int(float(row["actual_machine_failure"]))
        for row in prediction_rows
        if row.get("actual_machine_failure") not in (None, "")
    ]
    high_risk_count = sum(probability >= selected_threshold for probability in probabilities)

    return {
        "total_rows": len(prediction_rows),
        "high_risk_count": high_risk_count,
        "actual_failures": sum(actual_failures),
        "max_probability": max(probabilities) if probabilities else 0.0,
    }


def build_model_table(metrics: dict) -> list[str]:
    """Create a Markdown table comparing Logistic Regression and XGBoost."""
    models = metrics["models"]
    rows = [
        "| Model | Precision | Recall | F1-score | ROC-AUC | PR-AUC |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    display_names = {
        "logistic_regression": "Logistic Regression",
        "xgboost": "XGBoost",
    }

    for model_key in ["logistic_regression", "xgboost"]:
        model_metrics = models[model_key]
        rows.append(
            "| "
            f"{display_names[model_key]} | "
            f"{metric_cell(model_metrics['precision'])} | "
            f"{metric_cell(model_metrics['recall'])} | "
            f"{metric_cell(model_metrics['f1_score'])} | "
            f"{metric_cell(model_metrics['roc_auc'])} | "
            f"{metric_cell(model_metrics['pr_auc'])} |"
        )

    return rows


def build_threshold_table(threshold_summary: dict) -> list[str]:
    """Create a Markdown table comparing default and tuned thresholds."""
    default_metrics = threshold_summary["default_0_5_metrics"]
    selected_metrics = threshold_summary["selected_metrics"]
    selected_threshold = threshold_summary["selected_threshold"]

    return [
        "| Threshold | Precision | Recall | F1-score |",
        "|---|---:|---:|---:|",
        "| 0.50 (default) | "
        f"{metric_cell(default_metrics['precision'])} | "
        f"{metric_cell(default_metrics['recall'])} | "
        f"{metric_cell(default_metrics['f1_score'])} |",
        f"| {selected_threshold:.2f} (selected by F1) | "
        f"{metric_cell(selected_metrics['precision'])} | "
        f"{metric_cell(selected_metrics['recall'])} | "
        f"{metric_cell(selected_metrics['f1_score'])} |",
    ]


def extract_local_case_summary(local_case_markdown: str) -> list[str]:
    """Keep the useful selected-case and SHAP-factor bullets for a 1-page summary."""
    lines = local_case_markdown.splitlines()
    keep_prefixes = (
        "- Test row index:",
        "- Actual Machine failure:",
        "- XGBoost prediction",
        "- XGBoost failure probability:",
        "- `",
    )

    selected_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(keep_prefixes):
            selected_lines.append(stripped)

    # Keep the selected-case bullets and top SHAP factor bullets.
    return selected_lines[:9]


def build_research_plan(metrics: dict, threshold_summary: dict) -> str:
    """Build the presentation-ready revised stage plan Markdown."""
    selected_threshold = threshold_summary["selected_threshold"]

    lines = [
        "# 캡스톤 연구 Stage 보완안",
        "",
        "## 1. 연구 정체성",
        "",
        "현재 연구는 **AI4I 2020 기반 제조 설비 고장 예측 baseline + 설명 가능한 결과 대시보드 PoC**입니다.",
        "",
        "> 제조 설비 센서 데이터를 이용해 고장 위험을 예측하고, threshold와 SHAP 해석을 통해 현장 의사결정에 쓸 수 있는 설명 가능한 predictive maintenance 대시보드 구조를 설계한다.",
        "",
        "## 2. Revised Stages",
        "",
        "| Stage | 상태 | 핵심 내용 |",
        "|---|---|---|",
        "| Stage 1 | 완료 | 개발환경, 폴더 구조, 실행 스크립트 구성 |",
        "| Stage 2 | 완료 | AI4I 2020 데이터 준비, target 설정, ID/leakage 컬럼 제거, Type one-hot encoding |",
        "| Stage 3 | 완료 | Logistic Regression과 XGBoost baseline 모델 비교 |",
        f"| Stage 4-lite | 완료 | threshold {selected_threshold:.2f} 조정, SHAP 기반 설명 가능성 산출물 생성 |",
        "| Stage 5 | 완료 | Streamlit 결과 대시보드 MVP 구성 |",
        "| Stage 6-lite | 완료 | 저장된 test row 기반 고장 위험 playback 시뮬레이션 |",
        "| Stage 7-lite | MVP 구현 | 현장 CSV 업로드 기반 고장 확률/위험 등급 예측 MVP |",
        "| Stage 8-lite | 초안 구현 | 실제 LLM 호출이 아닌 SHAP 근거 기반 관리자 참고용 자연어 처방 초안 |",
        "| Stage 9 | 정리 완료 | 실제 사업장 적용 조건, 장점, 한계 정리 |",
        "| Stage 10-lite | MVP 구현 | 기존 산출물을 통합한 로컬 운영 요약과 다운로드 대시보드 |",
        "| Stage 11 | 구현 | AI4I UDI 순서 기반 시간축 시뮬레이션과 Predictive SPC chart 생성 |",
        "| Stage 12 | 구현 | Stage 1~20 full run 기준 Gemini 또는 OpenAI API 관리자 리포트 생성 |",
        "",
        "## 3. 보완된 연구 질문",
        "",
        "- **RQ1.** 제조 설비 센서 데이터로 기계 고장을 사전에 예측할 수 있는가?",
        "- **RQ2.** Logistic Regression 대비 XGBoost가 불균형 고장 데이터에서 더 나은 성능을 보이는가?",
        "- **RQ3.** threshold 조정이 현장 경고 기준으로 의미 있는 성능 개선을 만드는가?",
        "- **RQ4.** SHAP과 대시보드를 결합하면 비전문가도 예측 근거를 이해할 수 있는가?",
        "- **RQ5.** CSV 업로드, Predictive SPC, 관리자 리포트로 확장하면 중소 제조 현장용 의사결정 지원 도구가 될 수 있는가?",
        "",
        "## 4. 발표에서 말할 연구계획 문장",
        "",
        "> 현재까지는 AI4I 2020 공개 데이터를 기반으로 고장 예측 baseline, threshold 조정, SHAP 해석, Streamlit 결과 대시보드, CSV 업로드 예측 MVP, Stage 9 실제 적용성 정리, Stage 10 운영 요약, Predictive SPC 시간축 시뮬레이션, Gemini/OpenAI GenAI 관리자 리포트, Stage 19 field-event API, Stage 20 operator decision logging까지 구현했습니다. 이는 완성된 상용 시스템이 아니라, ML + XAI + LLM + SPC + 운영 승인 흐름을 로컬 PoC로 연결한 결과입니다.",
        "",
        "## 5. 실사업장 적용성",
        "",
        "| 구분 | 내용 |",
        "|---|---|",
        "| 적용 가능성 | CSV 기반으로 시작할 수 있어 중소기업 PoC에 적합 |",
        "| 필요한 데이터 | Type, 온도, 회전 속도, 토크, 공구 마모 등 설비 센서 컬럼 |",
        "| 장점 | 저비용 실험, 설명 가능한 경고, 결과 CSV 다운로드 가능 |",
        "| 한계 | 현재 모델은 AI4I 공개 데이터 기반이라 실제 설비 데이터로 재검증 필요 |",
        "| 다음 확장 | 실제 현장 데이터 재검증, DB/API 연결, 알림, 조치 이력, 재학습 관리 |",
        "",
        "## 6. 발표 시 주의 문장",
        "",
        "- 현재 기능은 실시간 센서 연동이 아니라 로컬 CSV 입력과 저장된 test playback입니다.",
        "- 처방 문장은 자동 정비 지시가 아니라 관리자 참고용 초안입니다.",
        "- 연구 중심은 LLM 자체가 아니라 **고장 예측 -> 설명 가능성 -> 의사결정 지원 -> 대시보드 자동화** 흐름입니다.",
        "",
    ]
    return "\n".join(lines)


def build_midterm_presentation_guide(
    metrics: dict,
    threshold_summary: dict,
    local_case_details: dict,
) -> str:
    """Build the no-PPT midterm presentation guide for the dashboard."""
    logistic_metrics = metrics["models"]["logistic_regression"]
    xgboost_metrics = metrics["models"]["xgboost"]
    selected_threshold = threshold_summary["selected_threshold"]
    selected_metrics = threshold_summary["selected_metrics"]
    default_metrics = threshold_summary["default_0_5_metrics"]
    case_udi = local_case_udi(local_case_details)
    case_probability = local_case_probability(local_case_details)
    case_features = local_case_feature_text(local_case_details)

    lines = [
        "# 중간발표 진행안: PPT 없이 대시보드로 발표",
        "",
        "## 1. 가져갈 것",
        "",
        "PPT가 따로 필요 없다면 **Streamlit 대시보드가 발표 자료**입니다.",
        "",
        "- 대시보드: `http://127.0.0.1:8501`",
        "- 실행 파일: `run_dashboard.bat`",
        "- 발표 원고: `outputs/demo_script_may11.md`",
        "- 예상 질문 답변: `outputs/midterm_qna_may11.md`",
        "- 연구계획 정리: `outputs/research_plan_may11.md`",
        "- 백업 결과물: `outputs/metrics.json`, `outputs/pr_curve.png`, `outputs/threshold_tuning.png`, `outputs/shap_summary.png`",
        "",
        "## 2. 발표 첫 문장",
        "",
        "> 제 연구는 제조 설비 센서 데이터를 이용해 기계 고장 가능성을 사전에 예측하고, 그 예측 결과와 판단 근거를 사람이 이해할 수 있도록 Streamlit 대시보드로 보여주는 predictive maintenance PoC입니다. 현재 Stage 1~9는 완료했고, Stage 10-lite는 발표용 운영 요약 MVP까지 구현했습니다.",
        "",
        "## 3. 클릭 순서",
        "",
        "1. **성과 요약**",
        "   - 현재 구현 상태는 Stage 1~9 완료, Stage 10-lite 발표용 운영 요약 MVP 구현입니다.",
        f"   - 대표 모델은 XGBoost이고 PR-AUC는 {xgboost_metrics['pr_auc']:.4f}입니다.",
        "",
        "2. **모델 비교**",
        "   - Logistic Regression과 XGBoost를 비교했습니다.",
        "   - 고장 데이터가 적은 불균형 문제라 accuracy보다 PR-AUC, recall, F1-score를 봤습니다.",
        "",
        "3. **Threshold 조정**",
        f"   - 기본 threshold 0.50 대신 {selected_threshold:.2f}로 조정했습니다.",
        f"   - F1-score가 {default_metrics['f1_score']:.4f}에서 {selected_metrics['f1_score']:.4f}로 개선됐습니다.",
        "   - 이건 실제 현장에서 경고 기준을 어떻게 잡을지와 연결됩니다.",
        "",
        "4. **SHAP 해석**",
        "   - 모델이 왜 고장이라고 판단했는지 설명하기 위해 SHAP을 사용했습니다.",
        "   - torque, rotational speed, tool wear 같은 센서 값이 주요 근거로 나타났습니다.",
        "",
        "5. **개별 사례**",
        f"   - UDI {case_udi} 사례는 실제 고장이고, XGBoost 고장 확률이 {case_probability:.4f}입니다.",
        f"   - 이 사례에서 {case_features}가 고장 판단의 주요 근거로 나타났습니다.",
        "",
        "6. **Row 시뮬레이션**",
        "   - 실시간 센서 연결은 아니고, test 결과를 row별로 넘겨보는 playback입니다.",
        "   - row를 바꾸면 고장 확률과 High Risk 여부가 바뀝니다.",
        "",
        "7. **현장 CSV MVP**",
        "   - 중소기업 현장 CSV를 업로드한다고 가정한 Stage 7-lite 기능입니다.",
        "   - CSV를 넣으면 고장 확률과 위험 등급을 계산할 수 있습니다.",
        "",
        "8. **예상 질문 답변**",
        "   - 실시간 여부, LLM 처방 구현 여부, 실제 공장 적용 가능성 질문에 대비합니다.",
        "   - 핵심 답변은 현재는 로컬 PoC이고, 실제 연동과 배포는 다음 단계라는 것입니다.",
        "",
        "9. **연구계획**",
        "   - 최종 목표는 상용 제품 완성이 아니라 실사업장 확장 가능한 PoC입니다.",
        "   - 다음 단계는 실제 현장 데이터 재검증, 실제 LLM 연결, DB/API 연동, 알림과 조치 이력 관리입니다.",
        "",
        "## 4. 마무리 멘트",
        "",
        "> 정리하면, 현재 연구는 단순히 모델 하나를 만든 것이 아니라 고장 예측, 성능 비교, threshold 의사결정, SHAP 설명, 대시보드 시각화, CSV 입력 PoC, 처방 초안까지 연결한 구조입니다. 아직 실시간 센서 연동이나 상용 배포 단계는 아니지만, 중소 제조 현장에서 실제 데이터로 확장할 수 있는 기반을 만든 것이 이번 중간발표의 핵심입니다.",
        "",
        "## 5. 말하면 안 되는 것",
        "",
        "- “실시간 시스템 완성했습니다”라고 말하지 않기",
        "- “실제 공장에 바로 배포 가능합니다”라고 말하지 않기",
        "- “LLM이 실제로 자동 처방합니다”라고 말하지 않기",
        "",
        "대신 이렇게 말하세요.",
        "",
        "> 현재는 로컬 PoC이며, 실시간 연동과 실제 LLM 처방은 다음 단계입니다.",
        "",
    ]
    return "\n".join(lines)


def build_midterm_qna(metrics: dict, threshold_summary: dict) -> str:
    """Build rehearsal Q&A answers for the no-PPT Streamlit presentation."""
    logistic_metrics = metrics["models"]["logistic_regression"]
    xgboost_metrics = metrics["models"]["xgboost"]
    selected_threshold = threshold_summary["selected_threshold"]
    selected_metrics = threshold_summary["selected_metrics"]
    default_metrics = threshold_summary["default_0_5_metrics"]

    lines = [
        "# 5월 11일 중간발표 예상 질문 답변",
        "",
        "## 1. 현재 stage는 어디까지 구현됐나요?",
        "",
        "답변:",
        "현재는 **Stage 1~9는 완료**, **Stage 10-lite는 발표용 통합 운영 요약 MVP까지 구현**한 상태입니다. 즉 개발환경, 데이터 준비, baseline 모델링, threshold 조정, SHAP 해석, Streamlit 대시보드, row playback, CSV 업로드 예측, 처방 초안, 실제 적용성 정리, 운영 요약 탭까지 연결했습니다. 다만 실제 DB/API 연동, 실시간 센서 스트리밍, 실제 LLM 호출, 클라우드 배포는 아직 다음 단계입니다.",
        "",
        "짧게 말하기:",
        "> Stage 1~9는 완료했고, Stage 10-lite 운영 요약 MVP까지 구현했습니다. 실시간 연동과 실제 LLM 처방은 다음 단계입니다.",
        "",
        "## 2. 왜 XGBoost를 선택했나요?",
        "",
        "답변:",
        f"Logistic Regression은 기준선을 잡기 위한 baseline이고, XGBoost는 센서 변수 사이의 비선형 관계를 더 잘 잡을 수 있는 비교 모델입니다. 이번 test 결과에서 XGBoost는 PR-AUC `{xgboost_metrics['pr_auc']:.4f}`로 Logistic Regression의 `{logistic_metrics['pr_auc']:.4f}`보다 높았기 때문에 발표 대표 모델로 선택했습니다.",
        "",
        "짧게 말하기:",
        "> 불균형 고장 데이터에서 PR-AUC가 더 높았기 때문에 XGBoost를 대표 모델로 선택했습니다.",
        "",
        "## 3. 왜 accuracy가 아니라 PR-AUC와 F1-score를 봤나요?",
        "",
        "답변:",
        f"test set은 `{threshold_summary['test_rows']}`개 row 중 실제 고장이 `{threshold_summary['test_failures']}`개뿐이라 정상 데이터가 훨씬 많습니다. 이런 불균형 데이터에서는 대부분을 정상이라고만 예측해도 accuracy가 높아 보일 수 있습니다. 그래서 고장으로 예측한 것의 정확도인 precision, 실제 고장을 잡아내는 recall, 둘의 균형인 F1-score, 그리고 불균형 데이터에 유용한 PR-AUC를 함께 봤습니다.",
        "",
        "짧게 말하기:",
        "> 고장 row가 적기 때문에 accuracy만 보면 모델이 좋아 보일 수 있어서 PR-AUC, recall, F1-score를 같이 봤습니다.",
        "",
        f"## 4. threshold `{selected_threshold:.2f}`는 어떤 의미인가요?",
        "",
        "답변:",
        f"모델은 고장 확률을 출력하고, threshold는 그 확률을 High Risk로 볼 기준입니다. 기본값 0.50에서는 F1-score가 `{default_metrics['f1_score']:.4f}`였고, F1 기준으로 `{selected_threshold:.2f}`를 선택했을 때 F1-score가 `{selected_metrics['f1_score']:.4f}`로 개선됐습니다. 현장에서는 이 기준을 조정하면서 false alarm과 놓치는 고장 사이의 균형을 정할 수 있습니다.",
        "",
        "짧게 말하기:",
        f"> threshold `{selected_threshold:.2f}`는 이번 데이터에서 F1-score가 가장 좋았던 경고 기준입니다.",
        "",
        "## 5. SHAP은 무엇을 설명하나요?",
        "",
        "답변:",
        "SHAP은 XGBoost가 특정 row를 고장 또는 정상으로 판단할 때 어떤 센서 변수가 어느 방향으로 영향을 줬는지 보여줍니다. 이번 결과에서는 torque, rotational speed, tool wear 같은 값이 주요 근거로 나타났습니다. 그래서 단순히 '고장 확률이 높다'에서 끝나지 않고, 어떤 센서 상태가 위험 판단에 기여했는지 설명할 수 있습니다.",
        "",
        "짧게 말하기:",
        "> SHAP은 모델의 고장 판단 근거를 센서 변수 단위로 설명해 주는 도구입니다.",
        "",
        "## 6. 이건 실시간 시스템인가요?",
        "",
        "답변:",
        "아직 실시간 시스템은 아닙니다. 현재 Row 시뮬레이션은 저장된 test 예측 결과를 한 row씩 넘겨보는 playback이고, CSV MVP도 파일을 업로드해 로컬에서 예측하는 구조입니다. 실제 센서 스트리밍, DB/API 연결, 알림 기능은 다음 단계에서 확장할 부분입니다.",
        "",
        "짧게 말하기:",
        "> 지금은 실시간 스트리밍이 아니라 로컬 test playback과 CSV 업로드 PoC입니다.",
        "",
        "## 7. LLM 처방이 실제 구현된 건가요?",
        "",
        "답변:",
        "실제 LLM API 호출은 아직 구현하지 않았습니다. 현재 Stage 8-lite는 SHAP으로 나온 주요 원인을 바탕으로 관리자 참고용 처방 초안을 만드는 단계입니다. 발표에서는 이 부분을 '실제 자동 정비 지시'가 아니라 'LLM 처방으로 확장하기 전의 grounded draft'라고 설명하는 것이 정확합니다.",
        "",
        "짧게 말하기:",
        "> 실제 LLM 호출은 아직 아니고, SHAP 근거를 바탕으로 만든 처방 초안입니다.",
        "",
        "## 8. 실제 공장 데이터에도 바로 적용 가능한가요?",
        "",
        "답변:",
        "바로 운영 배포할 수 있다고 말하기는 어렵습니다. 현재 모델은 AI4I 2020 공개 데이터로 학습했기 때문에 실제 공장 데이터에 적용하려면 같은 센서 컬럼을 확보하고, 데이터 분포가 비슷한지 확인하고, 현장 데이터로 성능을 재검증해야 합니다. 다만 CSV 기반으로 시작할 수 있어 중소 제조 현장의 PoC로 확장하기 좋은 구조입니다.",
        "",
        "짧게 말하기:",
        "> 바로 배포가 아니라, 실제 현장 데이터로 재검증해야 하는 PoC 단계입니다.",
        "",
        "## 9. PPT 없이 대시보드로 발표해도 충분한가요?",
        "",
        "답변:",
        "이번 발표 목적이 구현 진행 상황과 결과를 보여주는 것이라면 Streamlit 대시보드만으로도 충분합니다. 대시보드 안에 성과 요약, 모델 비교, threshold 조정, SHAP 해석, row 시뮬레이션, CSV MVP, 연구계획이 들어 있기 때문에 발표 흐름 자체가 화면에 준비되어 있습니다. 다만 발표 전에는 `run_dashboard.bat`로 미리 실행하고, 백업용으로 주요 PNG와 Markdown 파일 위치를 알고 있으면 안전합니다.",
        "",
        "짧게 말하기:",
        "> 대시보드가 곧 발표 자료입니다. 결과와 시연을 한 화면에서 보여줄 수 있습니다.",
        "",
        "## 마지막 방어 문장",
        "",
        "> 현재 연구는 완성된 상용 시스템이 아니라, AI4I 2020 공개 데이터를 기반으로 고장 예측, 설명 가능성, CSV 입력, 처방 초안까지 연결한 로컬 predictive maintenance PoC입니다.",
        "",
    ]
    return "\n".join(lines)


def build_rehearsal_checklist(
    metrics: dict,
    threshold_summary: dict,
    local_case_details: dict,
) -> str:
    """Build a practical rehearsal checklist for the dashboard presentation."""
    logistic_metrics = metrics["models"]["logistic_regression"]
    xgboost_metrics = metrics["models"]["xgboost"]
    selected_threshold = threshold_summary["selected_threshold"]
    selected_metrics = threshold_summary["selected_metrics"]
    default_metrics = threshold_summary["default_0_5_metrics"]
    case_udi = local_case_udi(local_case_details)
    case_probability = local_case_probability(local_case_details)
    test_failures = threshold_summary["test_failures"]

    lines = [
        "# 5월 11일 대시보드 리허설 체크리스트",
        "",
        "## 1. 현재 상태 한 문장",
        "",
        "> Stage 1~9는 완료했고, Stage 10-lite 운영 요약 MVP까지 구현했습니다. 현재 시스템은 실시간 운영 제품이 아니라 AI4I 2020 공개 데이터 기반 로컬 predictive maintenance PoC입니다.",
        "",
        "## 2. 3회 리허설 방식",
        "",
        "| 회차 | 방식 | 목표 |",
        "|---|---|---|",
        "| 1회차 | `outputs/demo_script_may11.md`를 보면서 읽기 | 시간과 클릭 순서 익히기 |",
        "| 2회차 | 대시보드 화면만 보고 말하기 | 탭별 핵심 문장 외우기 |",
        "| 3회차 | 발표 후 질문까지 붙여서 연습 | 실시간/LLM/현장 적용 질문 방어 |",
        "",
        "## 3. 3분 클릭 순서",
        "",
        "| 시간 | 클릭 탭 | 말할 핵심 1문장 | 넘어갈 때 연결 멘트 |",
        "|---|---|---|---|",
        "| 0:00-0:25 | 성과 요약 | 제조 설비 고장 위험을 예측하고 판단 근거를 대시보드로 보여주는 PoC입니다. | 먼저 모델 성능을 비교해 보겠습니다. |",
        f"| 0:25-0:55 | 모델 비교 | XGBoost PR-AUC `{xgboost_metrics['pr_auc']:.4f}`가 Logistic Regression `{logistic_metrics['pr_auc']:.4f}`보다 높아 대표 모델로 선택했습니다. | 다음은 경고 기준인 threshold를 보겠습니다. |",
        f"| 0:55-1:25 | Threshold 조정 | threshold `{selected_threshold:.2f}`를 선택해 F1-score가 `{default_metrics['f1_score']:.4f}`에서 `{selected_metrics['f1_score']:.4f}`로 개선됐습니다. | 성능 숫자 다음에는 왜 그런 예측을 했는지 보겠습니다. |",
        "| 1:25-1:50 | SHAP 해석 | SHAP은 torque, rotational speed, tool wear 같은 센서 변수가 고장 판단에 미친 영향을 설명합니다. | 이제 실제 고장 사례 하나로 연결해 보겠습니다. |",
        f"| 1:50-2:15 | 개별 사례 | UDI {case_udi} 사례는 실제 고장이며 XGBoost 고장 확률이 `{case_probability:.4f}`입니다. | 이 결과를 row별 playback으로도 볼 수 있습니다. |",
        "| 2:15-2:40 | Row 시뮬레이션 | 이 탭은 실시간 센서가 아니라 저장된 test row를 넘겨보는 발표용 playback입니다. | 마지막으로 전체 의미를 정리하겠습니다. |",
        "| 2:40-3:00 | 발표 요약 | 현재 결과는 실제 현장 데이터로 확장 가능한 로컬 predictive maintenance PoC입니다. | 질문을 받으면 현재 한계와 다음 단계를 분명히 말합니다. |",
        "",
        "## 4. 꼭 외울 방어 문장",
        "",
        "- 실시간 여부: 현재는 실시간 스트리밍이 아니라 저장된 test playback과 CSV 업로드 PoC입니다.",
        "- LLM 여부: 실제 LLM API 호출은 아직 아니고, SHAP 근거를 바탕으로 만든 관리자 참고용 처방 초안입니다.",
        "- 현장 적용 여부: 바로 배포가 아니라 실제 현장 데이터로 재검증해야 하는 PoC 단계입니다.",
        "",
        "## 5. 리허설 성공 기준",
        "",
        "- 3분 안에 핵심 탭 6개를 모두 설명할 수 있습니다.",
        f"- PR-AUC `{xgboost_metrics['pr_auc']:.4f}`, threshold `{selected_threshold:.2f}`, F1-score `{selected_metrics['f1_score']:.4f}`, test failures `{test_failures}`을 틀리지 않고 말할 수 있습니다.",
        "- 질문이 들어와도 현재 구현과 다음 단계를 과장 없이 구분할 수 있습니다.",
        "",
    ]
    return "\n".join(lines)


def build_backup_checklist(
    threshold_summary: dict,
    local_case_details: dict,
) -> str:
    """Build a presentation-day backup checklist."""
    selected_threshold = threshold_summary["selected_threshold"]
    case_udi = local_case_udi(local_case_details)

    lines = [
        "# 발표 당일 백업 체크리스트",
        "",
        "## 1. 발표 직전 실행",
        "",
        "1. 프로젝트 폴더에서 `run_dashboard.bat`를 실행합니다.",
        "2. 브라우저에서 `http://127.0.0.1:8501`이 열리는지 확인합니다.",
        "3. 탭이 한 줄에 최대한 보이도록 브라우저 창을 넓게 둡니다.",
        "4. 첫 화면은 `성과 요약` 탭에 맞춰 둡니다.",
        "",
        "## 2. 반드시 챙길 백업 파일",
        "",
        "- 대시보드 실행 파일: `run_dashboard.bat`",
        "- 발표 대본: `outputs/demo_script_may11.md`",
        "- 예상 질문 답변: `outputs/midterm_qna_may11.md`",
        "- 발표 요약: `outputs/presentation_summary.md`",
        "- 리허설 체크리스트: `outputs/rehearsal_checklist_may11.md`",
        "- Stage 10 운영 요약: `outputs/stage10_operations_summary.md`",
        "- 주요 그림: `outputs/confusion_matrix.png`, `outputs/pr_curve.png`, `outputs/threshold_tuning.png`, `outputs/shap_summary.png`, `outputs/shap_bar.png`",
        "- 주요 수치 파일: `outputs/metrics.json`, `outputs/threshold_summary.json`",
        "",
        "## 3. Streamlit이 안 뜰 때 설명 순서",
        "",
        "1. `outputs/presentation_summary.md`로 전체 연구 흐름을 설명합니다.",
        "2. `outputs/metrics.json` 또는 `outputs/pr_curve.png`로 XGBoost가 대표 모델인 이유를 설명합니다.",
        f"3. `outputs/threshold_tuning.png`와 `outputs/threshold_summary.json`으로 threshold {selected_threshold:.2f} 선택 이유를 설명합니다.",
        "4. `outputs/shap_summary.png`와 `outputs/shap_bar.png`로 SHAP 해석을 설명합니다.",
        f"5. `outputs/local_case_explanation.md`로 UDI {case_udi} 개별 사례를 설명합니다.",
        "6. `outputs/stage10_operations_summary.md`로 최종 통합 MVP와 다음 운영 단계를 설명합니다.",
        "7. `outputs/midterm_qna_may11.md`로 실시간/LLM/현장 적용 질문에 답합니다.",
        "",
        "## 4. 장애 대응 멘트",
        "",
        "> 대시보드는 로컬 Streamlit으로 실행되는 발표용 PoC입니다. 혹시 실행 환경 문제로 화면이 늦게 뜨면, 같은 결과가 저장된 Markdown과 PNG 산출물로 설명드리겠습니다.",
        "",
        "## 5. 발표 전 최종 체크",
        "",
        "- `run_dashboard.bat` 실행 확인",
        "- `outputs/*.png` 그림 파일 확인",
        "- `outputs/demo_script_may11.md`와 `outputs/midterm_qna_may11.md` 열람 가능 여부 확인",
        "- 인터넷 없이도 설명할 수 있는지 확인",
        "",
    ]
    return "\n".join(lines)


def build_final_stage_roadmap(metrics: dict, threshold_summary: dict) -> str:
    """Build the final-stage roadmap and paper-writing direction."""
    xgboost_metrics = metrics["models"]["xgboost"]
    selected_threshold = threshold_summary["selected_threshold"]
    selected_metrics = threshold_summary["selected_metrics"]

    lines = [
        "# 최종 단계 로드맵",
        "",
        "## 1. 현재 출발점",
        "",
        f"현재 프로젝트는 XGBoost PR-AUC `{xgboost_metrics['pr_auc']:.4f}`, selected threshold `{selected_threshold:.2f}`, tuned F1-score `{selected_metrics['f1_score']:.4f}`를 기준으로 발표 가능한 predictive maintenance PoC까지 도달했습니다.",
        "",
        "구현 상태는 **Stage 1~20 로컬 통합 PoC 구현 완료**입니다. 단, 실제 PLC/SCADA/클라우드 배포 완료가 아니라 로컬 field-event API, SQLite 이력, human decision logging까지 연결한 검증 가능한 PoC입니다.",
        "",
        "## 2. Stage 9: 실제 적용 조건과 한계 정리",
        "",
        "상세 정리는 `outputs/stage9_field_applicability.md`에 별도 산출물로 저장합니다.",
        "",
        "| 항목 | 해야 할 일 |",
        "|---|---|",
        "| 현장 데이터 필요 컬럼 | Type, Air temperature, Process temperature, Rotational speed, Torque, Tool wear 같은 센서 컬럼 확보 |",
        "| 데이터 차이 확인 | AI4I 공개 데이터와 실제 설비 데이터의 분포, 단위, 결측치, 고장 비율 비교 |",
        "| 성능 재검증 | 실제 현장 데이터에서 precision, recall, F1-score, ROC-AUC, PR-AUC 재측정 |",
        "| 운영 한계 정리 | 고장 원인 라벨 부재, 센서 품질, 설비별 차이, false alarm 비용 정리 |",
        "| 적용 방식 | 처음부터 실시간이 아니라 CSV 기반 파일 업로드 PoC로 시작 |",
        "",
        "## 3. Stage 10~20: 로컬 통합 운영 PoC",
        "",
        "- Stage 10~13: 모델 성능, threshold, Predictive SPC, 미래 10-step 이탈 예측, 관리자 참고 리포트 정리",
        "- Stage 14-lite: 라벨 있는 회사 CSV 또는 AI4I 기반 데모 회사 CSV로 재학습, threshold, SHAP bar, 예측 CSV, 모델 파일 저장",
        "- Stage 15~18-lite: file-drop streaming, FastAPI 예측, SQLite event history, 관리자 승인용 작업지시 초안 생성",
        "- Stage 19-lite: `POST /field-event`로 equipment_id, timestamp, source_system, sensor row를 받아 로컬 예측 이벤트로 저장",
        "- Stage 20-lite: `POST /work-order-decision`으로 approve/reject/needs_review 결정을 SQLite와 CSV에 기록",
        "- 비교 실험: Logistic/XGBoost, SMOTE, threshold tuning, SPC-only vs ML+SPC alert 전략을 같은 test split에서 비교",
        "- mock bridge: 실제 PLC/SCADA가 아닌 MQTT/OPC UA style local bridge로 field-event payload 계약 검증",
        "- 다운로드: 모델 지표, 예측 결과 CSV, Stage 9/10 문서, Stage 14 회사 재학습 산출물, 운영 PoC 산출물 제공",
        "- 운영 요약: 모델 성능, threshold 기준, High Risk row 수, field-event 수, 작업지시 결정 기록, 현재 한계를 한 화면에 정리",
        "",
        "Stage 14~20-lite는 실제 공장 운영 제품이 아니라, 회사 CSV 재학습부터 field-event API와 operator decision logging까지 로컬에서 검증하는 통합 PoC입니다. 실제 PLC/SCADA/클라우드 운영은 별도 현장 endpoint와 보안 승인이 필요합니다.",
        "",
        "## 4. 실제 LLM 연결 여부 결정",
        "",
        "LLM을 연결한다면 역할은 `자동 정비 명령`이 아니라 `관리자 참고용 문장 생성`으로 제한합니다. 입력은 SHAP 상위 요인, 고장 확률, threshold, 센서 값으로 제한하고, 출력에는 반드시 `최종 판단은 현장 담당자가 확정`한다는 문장을 포함합니다.",
        "",
        "## 5. 논문/보고서 작성 순서",
        "",
        "1. Codex로 실제 산출물 기반 초안을 만듭니다: 데이터, 전처리, 모델, 평가 지표, 결과 수치, 대시보드 구조.",
        "2. ChatGPT로 문장을 다듬습니다: 서론, 연구 배경, 결론, 문장 자연스러움.",
        "3. 사람이 최종 검토합니다: 과장 표현 제거, 수치 확인, 교수님 요구 형식 반영.",
        "",
        "## 6. 논문에 쓰기 좋은 핵심 문장",
        "",
        "> 본 연구는 AI4I 2020 공개 데이터를 기반으로 제조 설비 고장 예측 모델을 구축하고, threshold 조정, SHAP 기반 설명, Predictive SPC, Gemini/OpenAI GenAI 관리자 리포트, SMOTE/threshold/SPC-only 비교 실험, 회사 CSV 재학습, local mock bridge, FastAPI, SQLite event history, field-event API, 관리자 승인용 작업지시 초안과 operator decision logging을 Stage 1~20 로컬 통합 PoC로 연결한다. 실제 PLC/SCADA/클라우드 운영에는 현장 endpoint, 보안 승인, 현장 데이터 재검증이 추가로 필요하다.",
        "",
    ]
    return "\n".join(lines)


def build_stage9_field_applicability(metrics: dict, threshold_summary: dict) -> str:
    """Build the Stage 9 field applicability document for presentation and paper use."""
    logistic_metrics = metrics["models"]["logistic_regression"]
    xgboost_metrics = metrics["models"]["xgboost"]
    selected_threshold = threshold_summary["selected_threshold"]
    selected_metrics = threshold_summary["selected_metrics"]
    default_metrics = threshold_summary["default_0_5_metrics"]
    test_rows = threshold_summary["test_rows"]
    test_failures = threshold_summary["test_failures"]

    lines = [
        "# Stage 9 실제 적용성 정리",
        "",
        "## 1. Stage 9의 목적",
        "",
        "Stage 9는 새 모델을 추가로 개발하는 단계가 아니라, 현재 AI4I 2020 기반 로컬 PoC를 실제 중소 제조 사업장에 적용하려면 무엇이 필요한지 정리하는 단계입니다.",
        "",
        "> 현재 시스템은 바로 배포 가능한 상용 시스템이 아니라, 실제 현장 데이터 재검증 필요 조건을 정리한 predictive maintenance PoC입니다.",
        "",
        "## 2. 현재 구현 상태",
        "",
        "- Stage 1~6-lite 완료: 데이터 준비, baseline 모델링, threshold 조정, SHAP 해석, Streamlit 대시보드, row playback",
        "- Stage 7~8-lite 발표용 MVP: CSV 업로드 예측, 실제 LLM 호출이 아닌 SHAP 기반 처방 초안",
        "- Stage 9 실제 적용성 정리: 현장 적용 조건, 데이터 요구사항, 한계, 단계적 확장 순서 정리",
        "- Stage 10-lite 운영 요약 MVP: 모델 상태, High Risk row 수, 다운로드 산출물을 통합 표시",
        f"- 대표 성능: XGBoost PR-AUC `{xgboost_metrics['pr_auc']:.4f}`, threshold `{selected_threshold:.2f}`, F1-score `{selected_metrics['f1_score']:.4f}`",
        "",
        "## 3. 실제 현장 적용 전 필요 데이터 컬럼",
        "",
        "| 구분 | 필요 컬럼 또는 정보 | 설명 |",
        "|---|---|---|",
        "| 제품/설비 조건 | `Type` 또는 설비/제품군 구분값 | AI4I의 Type처럼 운전 조건 차이를 구분할 수 있어야 합니다. |",
        "| 온도 센서 | `Air temperature [K]`, `Process temperature [K]`에 대응되는 온도값 | 단위가 K가 아니면 단위 변환 또는 별도 전처리 기준이 필요합니다. |",
        "| 회전 조건 | `Rotational speed [rpm]` | 모터/축 회전 속도 또는 유사한 운전 속도 지표가 필요합니다. |",
        "| 부하 조건 | `Torque [Nm]` | 실제 설비에서 토크 또는 부하를 나타내는 센서가 필요합니다. |",
        "| 마모 조건 | `Tool wear [min]` | 공구 사용 시간, 누적 가동 시간, 교체 주기 등으로 대체할 수 있습니다. |",
        "| 정답 라벨 | `Machine failure`에 대응되는 고장 여부 | 모델 재검증을 위해 실제 고장 이력과 시간 기준 정렬이 필요합니다. |",
        "",
        "## 4. AI4I 공개 데이터와 실제 설비 데이터의 차이",
        "",
        "| 비교 항목 | AI4I 2020 데이터 | 실제 사업장 데이터에서 확인할 점 |",
        "|---|---|---|",
        "| 데이터 출처 | 공개된 교육/연구용 데이터 | 설비, 공정, 센서 설치 위치에 따라 분포가 달라질 수 있습니다. |",
        "| 컬럼 구조 | 정리된 센서 컬럼과 고장 라벨이 있음 | 컬럼명이 다르거나 일부 센서가 없을 수 있습니다. |",
        "| 결측/이상값 | 학습에 바로 쓰기 쉬운 형태 | 센서 누락, 비정상값, 단위 혼용을 먼저 처리해야 합니다. |",
        f"| 고장 비율 | test set `{test_rows}`개 중 고장 `{test_failures}`개 | 현장마다 고장 비율이 달라 precision/recall 균형이 달라질 수 있습니다. |",
        "| 운영 맥락 | 실제 비용/정비 이력은 없음 | false alarm 비용, 정비 가능 시간, 담당자 대응 절차가 필요합니다. |",
        "",
        "## 5. 재검증해야 할 성능 지표",
        "",
        "| 지표 | 왜 필요한가 | 현재 기준값 |",
        "|---|---|---:|",
        f"| PR-AUC | 고장 데이터가 적은 불균형 상황에서 대표 모델을 고를 때 중요 | XGBoost `{xgboost_metrics['pr_auc']:.4f}` / Logistic Regression `{logistic_metrics['pr_auc']:.4f}` |",
        f"| Precision | High Risk로 띄운 경고가 실제 고장인지 확인 | threshold 0.50 `{default_metrics['precision']:.4f}` / {selected_threshold:.2f} `{selected_metrics['precision']:.4f}` |",
        f"| Recall | 실제 고장을 얼마나 놓치지 않는지 확인 | threshold 0.50 `{default_metrics['recall']:.4f}` / {selected_threshold:.2f} `{selected_metrics['recall']:.4f}` |",
        f"| F1-score | precision과 recall의 균형 확인 | threshold 0.50 `{default_metrics['f1_score']:.4f}` / {selected_threshold:.2f} `{selected_metrics['f1_score']:.4f}` |",
        "| False alarm 수 | 현장 담당자의 불필요한 점검 부담 확인 | 실제 현장 비용 기준으로 재계산 필요 |",
        "| Missed failure 수 | 고장을 놓쳤을 때의 생산 손실 위험 확인 | 실제 현장 고장 이력 기준으로 재계산 필요 |",
        "",
        "## 6. 운영 리스크",
        "",
        "| 리스크 | 설명 | 대응 방향 |",
        "|---|---|---|",
        "| false alarm | 정상 설비를 High Risk로 자주 표시하면 현장 피로도가 커집니다. | threshold를 현장 비용 기준으로 다시 조정합니다. |",
        "| 고장 라벨 부족 | 실제 고장 데이터가 적으면 성능 추정이 불안정합니다. | 기간을 늘려 데이터를 모으고 고장 이력을 정리합니다. |",
        "| 센서 품질 | 결측, 노이즈, 단위 오류가 모델 입력을 흔들 수 있습니다. | 업로드 전 데이터 품질 점검 규칙을 둡니다. |",
        "| 설비별 차이 | 설비 종류나 제품군이 바뀌면 AI4I 모델 성능이 유지되지 않을 수 있습니다. | 설비별/라인별 성능을 따로 검증합니다. |",
        "| 책임 소재 | 예측 결과를 자동 정비 지시로 오해하면 위험합니다. | 관리자 참고용 의사결정 지원 도구로 제한합니다. |",
        "",
        "## 7. 중소 제조 현장용 단계적 적용 순서",
        "",
        "1. CSV PoC: 현장 센서 CSV를 받아 현재 Stage 7-lite 방식으로 고장 확률과 High Risk 여부를 계산합니다.",
        "2. 현장 데이터 검증: 실제 고장 이력과 예측 결과를 비교해 PR-AUC, precision, recall, F1-score를 다시 측정합니다.",
        "3. Threshold 재조정: false alarm 비용과 missed failure 비용을 반영해 현장 기준 threshold를 정합니다.",
        "4. 알림/이력 관리: High Risk row, 담당자 확인, 조치 결과를 기록합니다.",
        "5. 운영 대시보드: 예측, SHAP 설명, 처방 초안, 다운로드, 운영 요약을 통합합니다.",
        "",
        "## 8. 발표에서 말할 문장",
        "",
        "> Stage 9에서는 현재 PoC가 실제 사업장에 바로 배포된다고 말하지 않고, 어떤 센서 데이터와 고장 이력이 필요하며 어떤 성능 지표를 재검증해야 하는지 정리했습니다. 즉 현재 결과는 실사업장 적용을 위한 기반이고, 실제 적용 전에는 현장 데이터로 성능과 threshold를 다시 확인해야 합니다.",
        "",
        "## 9. Stage 9 결론",
        "",
        "- 현재 PoC는 실제 적용 가능성을 보여주는 구조입니다.",
        "- 하지만 실제 현장 데이터 재검증 필요 조건이 남아 있습니다.",
        "- 가장 현실적인 다음 단계는 실시간 연동이 아니라 CSV 기반 현장 데이터 검증입니다.",
        "- LLM 처방은 자동 정비 지시가 아니라 관리자 참고용 문장 생성으로 제한해야 합니다.",
        "",
    ]
    return "\n".join(lines)


def build_stage10_operations_summary(
    metrics: dict,
    threshold_summary: dict,
    prediction_rows: list[dict],
    spc_summary: dict | None = None,
    future_metrics: dict | None = None,
) -> str:
    """Build the Stage 10-lite local operations summary."""
    xgboost_metrics = metrics["models"]["xgboost"]
    selected_threshold = threshold_summary["selected_threshold"]
    selected_metrics = threshold_summary["selected_metrics"]
    summary = prediction_summary(prediction_rows, selected_threshold)

    lines = [
        "# Stage 10-lite 운영 요약",
        "",
        "## 1. Stage 10-lite의 목적",
        "",
        "Stage 10-lite는 실제 운영 시스템을 새로 만드는 단계가 아니라, 지금까지 만든 예측, 설명, 처방 초안, 적용성 문서, 다운로드 산출물을 하나의 발표용 운영 요약으로 묶는 단계입니다. 현재 프로젝트는 여기서 더 나아가 Stage 14~20 로컬 통합 PoC까지 검증합니다.",
        "",
        "> 현재 기능은 로컬 파일 기반 통합 MVP이며, AI4I row playback 기반 시간축 시뮬레이션, Predictive SPC chart, 필수 Gemini/OpenAI GenAI 관리자 리포트, Stage 14 회사 CSV 재학습, Stage 15~18 file-drop/FastAPI/SQLite/work-order draft, Stage 19 field-event API, Stage 20 operator decision logging까지 포함합니다. 실제 PLC/SCADA 연동, 클라우드 배포, 무인 자동 정비 명령은 아직 구현 완료로 주장하지 않습니다.",
        "",
        "## 2. 현재 모델 상태",
        "",
        "| 항목 | 현재 값 | 발표에서 말할 의미 |",
        "|---|---:|---|",
        f"| 대표 모델 | XGBoost | PR-AUC 기준 Logistic Regression보다 좋은 baseline |",
        f"| XGBoost PR-AUC | `{xgboost_metrics['pr_auc']:.4f}` | 불균형 고장 데이터에서 대표 성능 지표 |",
        f"| 선택 threshold | `{selected_threshold:.2f}` | F1-score 기준으로 선택한 경고 기준 |",
        f"| tuned F1-score | `{selected_metrics['f1_score']:.4f}` | precision과 recall의 균형 결과 |",
        f"| test 예측 row 수 | `{summary['total_rows']}` | 저장된 test prediction 기반 운영 요약 |",
        f"| High Risk row 수 | `{summary['high_risk_count']}` | threshold 이상으로 표시되는 점검 후보 |",
        f"| 실제 고장 row 수 | `{summary['actual_failures']}` | test set 안의 실제 고장 라벨 수 |",
        f"| 최대 고장 확률 | `{summary['max_probability']:.4f}` | 가장 위험하게 예측된 row의 확률 |",
        *(
            [
                f"| SPC alert row 수 | `{spc_summary['spc_risk_alert_count']}` | risk control limit 또는 threshold 기준 이상 후보 |",
                f"| risk UCL | `{spc_summary['risk_ucl']:.4f}` | 고장 확률 risk signal의 3-sigma 관리 상한 |",
            ]
            if spc_summary
            else []
        ),
        *(
            [
                f"| 미래 예측 horizon | `{future_metrics['horizon_steps']}` step | UDI 순서 기반 simulated future deviation prediction |",
                f"| 미래 이탈 예측 row 수 | `{future_metrics['summary']['predicted_future_deviation_rows']}` | 다음 10 step 이탈 후보로 예측된 row |",
                f"| 미래 이탈 예측 F1 | `{future_metrics['classification']['f1_score']:.4f}` | chronological validation 기준 |",
            ]
            if future_metrics
            else []
        ),
        "",
        "## 3. 대시보드에서 통합되는 기능",
        "",
        "- 예측: baseline prediction CSV와 현장 CSV 업로드 결과를 사용해 고장 확률을 보여줍니다.",
        "- 설명: SHAP summary plot과 개별 사례 설명으로 왜 위험하게 판단했는지 보여줍니다.",
        "- Predictive SPC: AI4I UDI 순서를 시간축으로 두고 고장 확률 trend, rolling mean, control limit을 보여줍니다.",
        "- 회사 재학습: 라벨 있는 회사 CSV 또는 AI4I 기반 데모 회사 CSV로 Stage 14-lite 재학습 산출물을 만듭니다.",
        "- 로컬 운영: file-drop streaming, FastAPI 예측, SQLite 이력 저장, 관리자 승인용 작업지시 초안을 Stage 15~18-lite로 검증합니다.",
        "- 현장 연동 PoC: Stage 19 `/field-event` API로 설비 ID, timestamp, source system, sensor row를 받아 예측 이벤트로 저장합니다.",
        "- 운영 승인 PoC: Stage 20 `/work-order-decision` API로 approve/reject/needs_review 결정을 SQLite와 CSV에 기록합니다.",
        "- GenAI 리포트: Stage 1~20 full run에서는 GEMINI_API_KEY 또는 OPENAI_API_KEY가 필수이며 Gemini 또는 OpenAI API로 관리자 참고 리포트를 생성합니다.",
        "- 다운로드: metrics, prediction CSV, SPC CSV, 발표 요약, Stage 9/10 문서, AI 리포트를 받을 수 있게 합니다.",
        "- 운영 요약: 모델 상태, threshold, High Risk row 수, SPC alert 수, 현재 한계와 다음 단계를 한 탭에 정리합니다.",
        "",
        "## 4. 현재 한계",
        "",
        "- 실제 공장 센서 스트리밍이 아니라 저장된 test prediction에 UDI 순서 시간축을 부여한 시뮬레이션입니다.",
        "- 현재 모델은 AI4I 2020 공개 데이터로 검증했으므로 실제 현장 데이터로 성능을 다시 확인해야 합니다.",
        "- LLM 리포트는 자동 정비 지시가 아니라 관리자 참고용 초안입니다.",
        "- 실제 PLC/SCADA 연동, 클라우드 배포, 권한/알림/재학습 스케줄은 별도 현장 시스템이 필요하며 아직 운영 제품으로 구현하지 않았습니다.",
        "",
        "## 5. 다음 운영 단계",
        "",
        "1. 실제 현장 CSV를 받아 현재 입력 컬럼과 단위가 맞는지 확인합니다.",
        "2. 실제 고장 이력과 예측 결과를 비교해 PR-AUC, precision, recall, F1-score를 재측정합니다.",
        "3. false alarm 비용과 missed failure 비용을 기준으로 현장 threshold를 다시 조정합니다.",
        "4. High Risk row 확인 여부와 조치 결과를 기록하는 간단한 이력 테이블을 설계합니다.",
        "5. 실제 LLM 리포트는 SHAP/SPC 근거 기반 관리자 참고 문장 생성으로 범위를 제한합니다.",
        "",
        "## 6. 발표에서 말할 문장",
        "",
        "> Stage 14~20에서는 회사 CSV 재학습, file-drop streaming, FastAPI 예측, SQLite event history, field-event API, 관리자 승인용 작업지시 초안, operator decision logging을 local PoC로 구현했습니다. 아직 실제 PLC/SCADA/클라우드 운영 제품은 아니며, 현장 endpoint와 보안 승인이 있어야 실제 운영으로 확장할 수 있습니다.",
        "",
    ]
    return "\n".join(lines)


def build_stage19_20_operations_design() -> str:
    """Build the Stage 19~20 operations design and verification document."""
    lines = [
        "# Stage 19~20 로컬 연동 및 운영 승인 PoC",
        "",
        "## 1. 문서 목적",
        "",
        "이 문서는 Stage 14~18 local PoC 이후 Stage 19 field-event API와 Stage 20 operator decision logging을 로컬에서 어떻게 실제 호출/저장 흐름으로 검증했는지 정리합니다.",
        "",
        "> Stage 1~20 로컬 통합 PoC 구현 완료입니다. Stage 19~20은 실제 PLC/SCADA/클라우드 배포가 아니라 로컬 field-event API와 operator decision logging으로 검증합니다.",
        "",
        "현재 단계에서는 실제 PLC/SCADA/MQTT/OPC UA/클라우드 연동을 완료했다고 말하지 않습니다. 외부 장비 접근 권한이 없으므로 현장 connector 앞단의 로컬 API 계약, SQLite 이력, 작업지시 승인 기록까지를 검증 가능한 구현 범위로 둡니다.",
        "",
        "## 2. 현재 구현 완료 범위",
        "",
        "| Stage | 상태 | 설명 |",
        "|---|---|---|",
        "| Stage 14-lite | 구현 완료 | 라벨 있는 회사 CSV 또는 AI4I 기반 데모 회사 CSV로 재학습, threshold, SHAP bar, 예측 CSV, 모델 파일 생성 |",
        "| Stage 15-lite | 구현 완료 | `outputs/realtime_stream/incoming` CSV file-drop streaming simulation 처리 |",
        "| Stage 16-lite | 구현 완료 | 로컬 FastAPI 예측 endpoint 구조 검증 |",
        "| Stage 17-lite | 구현 완료 | SQLite 기반 prediction event와 work-order draft 저장 |",
        "| Stage 18-lite | 구현 완료 | 관리자 승인용 작업지시 초안 JSON/Markdown 생성 |",
        "| Stage 19-lite | 구현 완료 | `POST /field-event`로 equipment_id, event_timestamp, source_system, sensor row를 받아 예측 이벤트로 저장 |",
        "| Stage 20-lite | 구현 완료 | `POST /work-order-decision`으로 approve/reject/needs_review 결정을 SQLite와 CSV에 기록 |",
        "",
        "## 3. Stage 19 로컬 field-event API",
        "",
        "Stage 19의 목표는 공장 시스템 대신 로컬 API 계약을 먼저 고정하는 것입니다. 외부 PLC/SCADA/MES connector는 나중에 이 API로 payload를 보내면 됩니다.",
        "",
        "| 항목 | 로컬 구현 | 현장 확장 조건 |",
        "|---|---|---|",
        "| API endpoint | `POST /field-event` | PLC/SCADA/MQTT/OPC UA bridge가 같은 JSON payload를 보낼 수 있어야 함 |",
        "| 식별자 | `equipment_id`, `event_timestamp`, `source_system` 필수 | 설비 ID와 timestamp 품질이 안정적으로 들어와야 함 |",
        "| 센서 row | AI4I-compatible `Type`, temperature, speed, torque, tool wear 입력 | 실제 tag와 AI4I feature mapping/단위 변환 필요 |",
        "| 저장 | 예측 이벤트를 `outputs/operations.db`와 `latest_events.csv`에 기록 | 운영 DB, 권한, 감사 로그 정책으로 확장 필요 |",
        "| 안전 경계 | 로컬 API는 예측과 기록만 수행 | 실제 장비 제어 명령은 보내지 않음 |",
        "",
        "## 4. Stage 19 데이터 계약 초안",
        "",
        "| 필드 | 필요성 | 예시 |",
        "|---|---|---|",
        "| `equipment_id` | 설비별 성능과 drift를 분리하기 위해 필요 | `MACHINE_01` |",
        "| `timestamp` | row 순서와 지연 시간을 검증하기 위해 필요 | `2026-05-11T09:00:00+09:00` |",
        "| `product_type` | AI4I `Type`에 대응되는 제품/작업 조건 | `L`, `M`, `H` 또는 현장 제품군 |",
        "| `air_temperature` | 주변 온도 또는 설비 주변 온도 | 섭씨 또는 켈빈, 단위 명시 필요 |",
        "| `process_temperature` | 공정 온도 | 섭씨 또는 켈빈, 단위 명시 필요 |",
        "| `rotational_speed` | 회전수/속도 조건 | rpm 또는 현장 단위 |",
        "| `torque` | 부하 또는 토크 조건 | Nm 또는 현장 단위 |",
        "| `tool_wear` | 공구 사용 시간 또는 누적 사용량 | minute 또는 cycle count |",
        "| `failure_label` | 재검증용 실제 고장 여부 | 정상/고장, ok/failure, 0/1 |",
        "",
        "## 5. Stage 20 operator decision logging",
        "",
        "Stage 20의 목표는 작업지시 초안을 사람이 검토한 뒤 approve/reject/needs_review 결정을 남기는 것입니다.",
        "",
        "| 항목 | 로컬 구현 | 운영 확장 조건 |",
        "|---|---|---|",
        "| Decision API | `POST /work-order-decision` | 로그인 사용자 ID와 권한 체계 연결 필요 |",
        "| 허용 결정 | `approve`, `reject`, `needs_review` | 실제 현장 승인 workflow와 상태값 합의 필요 |",
        "| 감사 기록 | SQLite `work_order_decisions`와 `work_order_decisions.csv`에 저장 | 운영 DB, immutable audit log, 백업/복구 필요 |",
        "| 작업 이력 | draft_id와 event_id로 예측 근거와 연결 | 실제 점검 결과, 부품 교체, false alarm 여부 추가 필요 |",
        "| 안전 경계 | 결정 기록은 사람 승인 로그이며 자동 정비 명령이 아님 | 설비 제어 시스템과 연결 전 별도 승인 필요 |",
        "",
        "## 6. 배포 전 검증 체크리스트",
        "",
        "- 실제 현장 CSV로 Stage 14 재학습을 실행하고 `custom_metrics.json`을 확인한다.",
        "- 실제 현장 데이터의 단위 변환과 필수 컬럼 mapping을 문서화한다.",
        "- Stage 15 file-drop simulation으로 현장 row가 예측 이벤트로 저장되는지 확인한다.",
        "- `/field-event`로 현장 row가 예측 이벤트와 SQLite 기록으로 이어지는지 확인한다.",
        "- `/work-order-decision`으로 작업지시 초안에 대한 사람 결정이 SQLite와 CSV에 저장되는지 확인한다.",
        "- FastAPI endpoint는 운영망 연결 전 테스트망에서만 검증한다.",
        "- SQLite PoC를 운영 DB로 바꾸기 전 감사 로그, 권한, 백업 정책을 설계한다.",
        "- 작업지시 초안과 decision log는 관리자 승인용 기록으로만 사용하고 자동 정비 명령으로 연결하지 않는다.",
        "- threshold는 AI4I 기준값을 그대로 쓰지 않고 현장 false alarm 비용과 missed failure 비용으로 재조정한다.",
        "- 클라우드 배포 전 비밀값 관리, 접근 제어, 로그 보관, 장애 대응 절차를 확인한다.",
        "",
        "## 7. 발표 및 논문 guardrail",
        "",
        "- 말해도 되는 표현: `Stage 1~20 로컬 통합 PoC 구현 완료`, `Stage 19 field-event API 구현`, `Stage 20 operator decision logging 구현`, `실제 현장 적용 전 데이터 재검증 필요`.",
        "- 아직 실제 PLC/SCADA/클라우드 운영 제품은 아니며, 현장 endpoint와 보안 승인 없이 운영 배포를 완료했다고 말하지 않는다.",
        "- 피해야 할 표현: 공장 연동이 이미 끝났다는 표현, 클라우드에 배포됐다는 표현, 사람이 승인하지 않는 자동 정비 실행 표현, 상용 제품이 완성됐다는 표현.",
        "- 본 시스템은 현재 local PoC이며, 실제 배포 가능 제품이라고 주장하지 않는다.",
        "",
        "## 8. 결론",
        "",
        "Stage 19~20은 외부 공장 배포 완료가 아니라, Stage 14~18 local PoC 뒤에 field-event API와 operator decision logging을 붙여 실제 데이터 흐름의 마지막 연결부를 로컬에서 검증한 단계입니다. 이 문서는 발표와 논문에서 구현 범위와 실제 현장 확장 조건을 분리해 설명하기 위한 기준 문서입니다.",
        "",
    ]
    return "\n".join(lines)


def build_final_paper_outline(
    metrics: dict,
    threshold_summary: dict,
    spc_summary: dict,
    future_metrics: dict | None = None,
) -> str:
    """Build a final-paper outline aligned with the original first presentation."""
    xgboost = metrics["models"]["xgboost"]
    logistic = metrics["models"]["logistic_regression"]
    selected_threshold = threshold_summary["selected_threshold"]
    selected_metrics = threshold_summary["selected_metrics"]
    future_horizon = future_metrics["horizon_steps"] if future_metrics else 10

    lines = [
        "# 최종 논문 작성 개요",
        "",
        "## 논문 제목",
        "",
        "생성형 AI 확장을 고려한 설명가능한 스마트 제조 Predictive SPC 대시보드 구축: AI4I 2020 기반 PoC",
        "",
        "## 1. 서론",
        "",
        "- 스마트 제조 현장에서 설비 고장과 품질 이상을 사후 대응하는 한계를 설명합니다.",
        "- 본 연구는 고장 예측, 설명 가능성, Predictive SPC, 관리자용 AI 리포트를 하나의 로컬 PoC로 연결합니다.",
        "- 실제 센서 스트리밍이 아니라 AI4I 2020 공개 데이터의 UDI 순서를 사용한 시간축 시뮬레이션임을 명확히 씁니다.",
        "",
        "## 2. 선행연구",
        "",
        "- 머신러닝 기반 예지보전",
        "- SHAP/LIME 기반 설명가능 AI",
        "- 제조 대시보드와 LLM 기반 의사결정 지원",
        "- 본 연구의 차별성: ML 성능 비교에서 끝나지 않고 threshold, SHAP, SPC chart, AI 리포트, dashboard를 연결합니다.",
        "",
        "## 3. 방법론",
        "",
        "- 데이터: AI4I 2020, 10,000 samples, target `Machine failure`.",
        "- 전처리: `UDI`, `Product ID` 제거, `Type` one-hot encoding, `TWF/HDF/PWF/OSF/RNF` leakage column 제거.",
        "- 모델: Logistic Regression baseline과 XGBoost 비교.",
        "- 평가: precision, recall, F1-score, ROC-AUC, PR-AUC.",
        f"- threshold: 0.05~0.95 탐색 후 F1 기준 `{selected_threshold:.2f}` 선택.",
        "- Predictive SPC: saved prediction을 UDI 순서로 정렬해 simulated time axis를 만들고 risk signal, rolling mean, control limit을 계산합니다.",
        f"- 미래 이탈 예측: UDI 순서 기반 lag/rolling feature로 다음 `{future_horizon}` step의 최대 risk와 이탈 여부를 예측합니다.",
        "- GenAI 리포트: High Risk/SPC 이상 row의 수치 근거와 SHAP 요인을 Gemini 또는 OpenAI API에 전달합니다.",
        "",
        "## 4. 결과",
        "",
        f"- Logistic Regression PR-AUC: `{logistic['pr_auc']:.4f}`.",
        f"- XGBoost PR-AUC: `{xgboost['pr_auc']:.4f}`, ROC-AUC: `{xgboost['roc_auc']:.4f}`.",
        f"- 선택 threshold `{selected_threshold:.2f}`에서 F1-score `{selected_metrics['f1_score']:.4f}`.",
        f"- SPC 시뮬레이션 row `{spc_summary['total_rows']}`개, High Risk row `{spc_summary['high_risk_count']}`개, SPC alert row `{spc_summary['spc_risk_alert_count']}`개.",
        *(
            [
                f"- 미래 `{future_metrics['horizon_steps']}` step 이탈 예측 F1-score `{future_metrics['classification']['f1_score']:.4f}`, regression RMSE `{future_metrics['regression']['rmse']:.4f}`.",
            ]
            if future_metrics
            else []
        ),
        "- 주요 그림: confusion matrix, PR curve, threshold tuning, SHAP summary/bar, SPC risk chart, SPC control chart.",
        "",
        "## 5. 시스템 구현",
        "",
        "- Streamlit dashboard에서 모델 성능, threshold, SHAP, row playback, 미래 이탈 예측, Predictive SPC, AI report를 확인합니다.",
        "- `run_all.bat`로 학습, 해석, SPC, AI 리포트, 발표 문서 생성을 자동화합니다.",
        "",
        "## 6. 한계 및 향후 연구",
        "",
        "- AI4I 기반 시간축은 실제 센서 스트리밍이 아니라 발표용 시뮬레이션입니다.",
        "- 실제 현장 데이터로 성능과 threshold를 재검증해야 합니다.",
        "- LLM 리포트는 관리자 참고용이며 자동 정비 지시로 사용하지 않습니다.",
        "- 향후에는 실제 DB/API, 센서 스트리밍, 알림/조치 이력, 재학습 관리로 확장합니다.",
        "",
    ]
    return "\n".join(lines)


def build_final_presentation_plan(
    metrics: dict,
    threshold_summary: dict,
    spc_summary: dict,
    future_metrics: dict | None = None,
) -> str:
    """Build the final-presentation flow that recovers the first-presentation promise."""
    xgboost = metrics["models"]["xgboost"]
    selected_threshold = threshold_summary["selected_threshold"]
    selected_metrics = threshold_summary["selected_metrics"]
    future_horizon = future_metrics["horizon_steps"] if future_metrics else 10

    lines = [
        "# 6월 최종발표 구성안",
        "",
        "## 1. Motivation",
        "",
        "- 고장이 난 뒤 대응하는 reactive 방식의 한계를 말합니다.",
        "- 목표는 고장 위험을 미리 예측하고, 근거와 관리자 참고 리포트를 함께 제공하는 것입니다.",
        "",
        "## 2. Literature Review",
        "",
        "- ML 기반 예지보전, SHAP 기반 XAI, LLM 기반 보고서 생성 흐름을 짧게 정리합니다.",
        "",
        "## 3. Something New",
        "",
        "- 1차 발표 원안의 핵심을 `ML + SHAP + Predictive SPC + GenAI report + Streamlit dashboard + local operations API`로 회복했습니다.",
        "- 실제 정비 명령이 아니라 관리자 참고용 리포트라는 안전한 범위를 둡니다.",
        "",
        "## 4. System Architecture",
        "",
        "1. AI4I data ingestion",
        "2. Logistic Regression / XGBoost training",
        "3. Threshold tuning",
        "4. SHAP explanation",
        "5. UDI-order time-series playback",
        f"6. Future {future_horizon}-step deviation prediction",
        "7. Predictive SPC chart generation",
        "8. Required Gemini/OpenAI GenAI manager report for the full Stage 1~20 run",
        "9. SMOTE / threshold / SPC-only vs ML+SPC comparison artifacts",
        "10. MQTT/OPC UA style local mock bridge",
        "11. Streamlit dashboard",
        "",
        "## 5. Experiment Results",
        "",
        f"- XGBoost PR-AUC `{xgboost['pr_auc']:.4f}`.",
        f"- selected threshold `{selected_threshold:.2f}`, tuned F1-score `{selected_metrics['f1_score']:.4f}`.",
        f"- SPC High Risk row `{spc_summary['high_risk_count']}`, SPC alert row `{spc_summary['spc_risk_alert_count']}`.",
        "- Comparison artifacts summarize SMOTE and SPC-only vs ML+SPC trade-offs without claiming real cost reduction.",
        *(
            [
                f"- future {future_metrics['horizon_steps']}-step deviation F1-score `{future_metrics['classification']['f1_score']:.4f}`.",
            ]
            if future_metrics
            else []
        ),
        "",
        "## 6. Dashboard Demonstration",
        "",
        "- 성과 요약 -> 모델 비교 -> threshold -> SHAP -> 실시간 처방 PoC -> Predictive SPC -> AI Report 순서로 시연합니다.",
        "- `실시간 처방 PoC` 탭에서 현재 위험, 미래 10-step 이탈 예측, SHAP 근거, 자연어 권고를 한 화면에서 보여줍니다.",
        "- `Predictive SPC` 탭에서 시간축 시뮬레이션과 관리한계선을 보여줍니다.",
        "- `AI Report` 탭에서 High Risk row의 관리자 참고 리포트를 보여줍니다.",
        "",
        "## 7. Limitations and Future Work",
        "",
        "- 실제 센서 스트리밍이 아니라 AI4I row playback입니다.",
        "- 실제 현장 데이터 검증이 필요합니다.",
        "- LLM 출력은 최종 판단이 아니라 참고 초안입니다.",
        "- 1차 발표의 85%, 30% 기대효과 수치는 본 실험 결과로 주장하지 않습니다.",
        "",
    ]
    return "\n".join(lines)


def build_summary(metrics: dict, threshold_summary: dict, local_case_markdown: str) -> str:
    """Build the final 5월 11일 presentation summary Markdown."""
    best_model = metrics["best_model_by_pr_auc"]
    xgboost_metrics = metrics["models"]["xgboost"]
    selected_threshold = threshold_summary["selected_threshold"]
    selected_metrics = threshold_summary["selected_metrics"]
    local_case_lines = extract_local_case_summary(local_case_markdown)

    lines = [
        "# 5월 11일 연구 진행 요약",
        "",
        "## 1. 현재 완료 단계",
        "",
        "- Stage 1 개발환경 세팅, Stage 2 AI4I 데이터 준비, Stage 3 Baseline 모델링, Stage 4-lite 해석 산출물 생성을 완료했습니다.",
        "- Stage 5 Streamlit 결과뷰어 MVP와 Stage 6-lite Row 시뮬레이션을 완료했습니다.",
        "- Stage 7-lite 현장 CSV 입력과 Stage 8-lite 처방 초안은 발표용 MVP 수준으로 구현했습니다.",
        "- Stage 9 실제 적용성 정리를 추가해 현장 데이터 요구사항, 한계, 재검증 항목을 문서화했습니다.",
        "- Stage 10-lite 운영 요약 MVP를 추가해 모델 상태, threshold, High Risk row 수, 다운로드 산출물을 한 화면에서 확인할 수 있게 했습니다.",
        "- Stage 11~12로 AI4I 시간축 시뮬레이션, Predictive SPC chart, Gemini/OpenAI GenAI 관리자 리포트를 추가해 1차 발표 원안을 회복했습니다.",
        f"- 데이터 분할은 train `{metrics['train_rows']}`개, test `{metrics['test_rows']}`개이며 target은 `Machine failure`입니다.",
        f"- 현재 발표 대표 모델은 PR-AUC 기준 `{best_model}`입니다.",
        "- 현재 시스템은 완성된 상용 제품이 아니라 실사업장 확장 가능성을 보여주는 predictive maintenance PoC입니다.",
        "",
        "## 2. Baseline 모델 비교",
        "",
        *build_model_table(metrics),
        "",
        f"- XGBoost는 PR-AUC `{xgboost_metrics['pr_auc']:.4f}`, ROC-AUC `{xgboost_metrics['roc_auc']:.4f}`로 Logistic Regression보다 발표용 대표 모델에 적합합니다.",
        "",
        "## 3. Threshold 조정 결과",
        "",
        *build_threshold_table(threshold_summary),
        "",
        f"- 기본 threshold 0.50 대비, F1 기준 선택 threshold `{selected_threshold:.2f}`에서 F1-score가 `{selected_metrics['f1_score']:.4f}`로 개선되었습니다.",
        "- 이 결과는 고장 예측에서 threshold가 단순 기본값이 아니라 의사결정 기준으로 조정될 수 있음을 보여줍니다.",
        "",
        "## 4. SHAP 기반 개별 사례 해석",
        "",
        "- SHAP은 XGBoost가 왜 고장이라고 예측했는지 센서 변수 단위로 설명하기 위해 사용했습니다.",
        "",
    ]

    if local_case_lines:
        lines.extend(local_case_lines)
    else:
        lines.append("- 개별 사례 요약을 찾지 못했습니다. `outputs/local_case_explanation.md`를 확인하세요.")

    lines += [
        "",
        "## 5. 발표에서 보여줄 산출물",
        "",
        "- `outputs/metrics.json`: Logistic Regression과 XGBoost 성능 비교",
        "- `outputs/confusion_matrix.png`: 두 모델의 confusion matrix",
        "- `outputs/pr_curve.png`: 두 모델의 PR curve",
        "- `outputs/threshold_tuning.png`: threshold별 precision, recall, f1-score 변화",
        "- `outputs/shap_summary.png`, `outputs/shap_bar.png`: XGBoost SHAP 해석 그림",
        "- `outputs/local_case_explanation.md`: 개별 고장 예측 사례 해석",
        "- `outputs/research_plan_may11.md`: Stage 1~10 연구계획과 실사업장 적용성 정리",
        "- `outputs/stage9_field_applicability.md`: 실제 사업장 적용 조건과 한계 정리",
        "- `outputs/stage10_operations_summary.md`: Stage 10-lite 운영 요약과 다음 운영 단계",
        "- `outputs/spc_risk_chart.png`, `outputs/spc_control_chart.png`: Predictive SPC 시간축 시뮬레이션 그림",
        "- `outputs/future_deviation_predictions.csv`, `outputs/future_deviation_metrics.json`, `outputs/future_deviation_chart.png`: 미래 10-step 이탈 예측 산출물",
        "- `outputs/ai_manager_report.md`: Gemini/OpenAI API 기반 관리자 참고 리포트",
        "- `outputs/model_strategy_comparison.csv`, `outputs/model_strategy_summary.md`: Logistic/XGBoost, SMOTE, threshold tuning 비교",
        "- `outputs/spc_vs_ml_comparison.csv`, `outputs/spc_vs_ml_summary.md`: SPC-only rule 대비 ML+SPC alert 비교",
        "- `outputs/mock_field_bridge_summary.md`: MQTT/OPC UA style local mock bridge 실행 요약",
        "- `outputs/stage19_20_operations_design.md`: 실제 현장 연동과 운영 시스템화를 위한 설계 및 검증 조건",
        "- `outputs/final_paper_outline.md`, `outputs/final_presentation_plan.md`: 6월 최종 논문/발표 구성안",
        "- `outputs/midterm_presentation_guide.md`: PPT 없는 중간발표 진행안",
        "",
        "## 6. 다음 단계",
        "",
        "- 실제 사업장 CSV 또는 DB/API 데이터로 모델 성능 재검증",
        "- 실제 현장 데이터로 Predictive SPC control limit과 threshold 재검증",
        "- LLM 기반 리포트를 관리자 참고용으로 제한해 운영 검토",
        "- 알림, 조치 이력, 재학습 관리가 포함된 운영형 대시보드로 확장",
        "",
    ]

    return "\n".join(lines)


def main() -> None:
    """Create a one-page Markdown summary for the May 11 presentation."""
    project_root = Path(__file__).resolve().parents[1]
    output_dir = project_root / "outputs"

    metrics = load_json(output_dir / "metrics.json")
    threshold_summary = load_json(output_dir / "threshold_summary.json")
    local_case_details = load_json(output_dir / "local_case_explanation.json")
    local_case_markdown = load_text(output_dir / "local_case_explanation.md")
    prediction_rows = load_csv_rows(output_dir / "baseline_predictions.csv")
    spc_summary = load_json(output_dir / "spc_summary.json")
    future_metrics = load_json(output_dir / "future_deviation_metrics.json")

    summary = build_summary(metrics, threshold_summary, local_case_markdown)
    summary_path = output_dir / "presentation_summary.md"
    summary_path.write_text(summary, encoding="utf-8")

    research_plan = build_research_plan(metrics, threshold_summary)
    research_plan_path = output_dir / "research_plan_may11.md"
    research_plan_path.write_text(research_plan, encoding="utf-8")

    midterm_guide = build_midterm_presentation_guide(metrics, threshold_summary, local_case_details)
    midterm_guide_path = output_dir / "midterm_presentation_guide.md"
    midterm_guide_path.write_text(midterm_guide, encoding="utf-8")

    midterm_qna = build_midterm_qna(metrics, threshold_summary)
    midterm_qna_path = output_dir / "midterm_qna_may11.md"
    midterm_qna_path.write_text(midterm_qna, encoding="utf-8")

    rehearsal_checklist = build_rehearsal_checklist(metrics, threshold_summary, local_case_details)
    rehearsal_checklist_path = output_dir / "rehearsal_checklist_may11.md"
    rehearsal_checklist_path.write_text(rehearsal_checklist, encoding="utf-8")

    backup_checklist = build_backup_checklist(threshold_summary, local_case_details)
    backup_checklist_path = output_dir / "presentation_day_backup_checklist.md"
    backup_checklist_path.write_text(backup_checklist, encoding="utf-8")

    final_roadmap = build_final_stage_roadmap(metrics, threshold_summary)
    final_roadmap_path = output_dir / "final_stage_roadmap.md"
    final_roadmap_path.write_text(final_roadmap, encoding="utf-8")

    stage9_applicability = build_stage9_field_applicability(metrics, threshold_summary)
    stage9_applicability_path = output_dir / "stage9_field_applicability.md"
    stage9_applicability_path.write_text(stage9_applicability, encoding="utf-8")

    stage10_operations_summary = build_stage10_operations_summary(
        metrics,
        threshold_summary,
        prediction_rows,
        spc_summary,
        future_metrics,
    )
    stage10_operations_summary_path = output_dir / "stage10_operations_summary.md"
    stage10_operations_summary_path.write_text(stage10_operations_summary, encoding="utf-8")

    stage19_20_operations_design = build_stage19_20_operations_design()
    stage19_20_operations_design_path = output_dir / "stage19_20_operations_design.md"
    stage19_20_operations_design_path.write_text(
        stage19_20_operations_design,
        encoding="utf-8",
    )

    final_paper_outline = build_final_paper_outline(
        metrics,
        threshold_summary,
        spc_summary,
        future_metrics,
    )
    final_paper_outline_path = output_dir / "final_paper_outline.md"
    final_paper_outline_path.write_text(final_paper_outline, encoding="utf-8")

    final_presentation_plan = build_final_presentation_plan(
        metrics,
        threshold_summary,
        spc_summary,
        future_metrics,
    )
    final_presentation_plan_path = output_dir / "final_presentation_plan.md"
    final_presentation_plan_path.write_text(final_presentation_plan, encoding="utf-8")

    print("Presentation summary created successfully.")
    print(f"Summary saved to: {summary_path}")
    print(f"Research plan saved to: {research_plan_path}")
    print(f"Midterm presentation guide saved to: {midterm_guide_path}")
    print(f"Midterm Q&A saved to: {midterm_qna_path}")
    print(f"Rehearsal checklist saved to: {rehearsal_checklist_path}")
    print(f"Presentation day backup checklist saved to: {backup_checklist_path}")
    print(f"Final stage roadmap saved to: {final_roadmap_path}")
    print(f"Stage 9 field applicability saved to: {stage9_applicability_path}")
    print(f"Stage 10 operations summary saved to: {stage10_operations_summary_path}")
    print(f"Stage 19~20 operations design saved to: {stage19_20_operations_design_path}")
    print(f"Final paper outline saved to: {final_paper_outline_path}")
    print(f"Final presentation plan saved to: {final_presentation_plan_path}")


if __name__ == "__main__":
    main()
