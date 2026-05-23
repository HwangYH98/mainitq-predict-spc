from __future__ import annotations

import os
import re
import shutil
import stat
import zipfile
from pathlib import Path

import create_chatgpt_thesis_packet as thesis_packet


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
PPT_PACKET = OUT / "final_ppt_build_packet"
PPT_ZIP = OUT / "final_ppt_build_packet.zip"


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8-sig")


def reset_dir(path: Path) -> None:
    if path.exists():
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def clean_common_mojibake(text: str) -> str:
    replacements = {
        "Alcal찼": "Alcalá",
        "Magn첬sson": "Magnússon",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def validate_bundle(folder: Path, zip_path: Path, expected_slide_count: int | None = None) -> None:
    combined = ""
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() not in {".txt", ".md"}:
            raise RuntimeError(f"Unexpected file type in packet folder: {path.name}")
        text = read_text(path)
        combined += text + "\n"
        if "\ufffd" in text:
            raise RuntimeError(f"Replacement character found: {path.name}")
        for marker in ["?쇰", "?곌", "媛", "紐", "諛", "Alcal찼", "Magn첬"]:
            if marker in text:
                raise RuntimeError(f"Mojibake marker found in {path.name}: {marker}")

    key_patterns = [
        r"AIza[0-9A-Za-z_\-]{20,}",
        r"sk-[0-9A-Za-z_\-]{20,}",
        r"OPENAI_API_KEY\s*=\s*[^\s]+",
        r"GEMINI_API_KEY\s*=\s*[^\s]+",
    ]
    for pattern in key_patterns:
        if re.search(pattern, combined):
            raise RuntimeError(f"API key-like pattern found: {pattern}")

    forbidden_claims = [
        "실제 비용 절감 실증 완료",
        "실제 PLC/SCADA 배포 완료",
        "실제 회사 데이터 검증 완료",
        "실제 회사 데이터 성능 재검증 완료",
        "자동 정비 명령 실행 완료",
    ]
    for phrase in forbidden_claims:
        if phrase in combined:
            raise RuntimeError(f"Forbidden claim phrase found: {phrase}")

    if expected_slide_count is not None:
        slide_file = folder / "01_슬라이드별_구성안.md"
        slide_text = read_text(slide_file)
        matches = re.findall(r"^###\s+(\d+)\.", slide_text, flags=re.MULTILINE)
        if len(matches) != expected_slide_count:
            raise RuntimeError(f"Expected {expected_slide_count} slides, found {len(matches)}")
        if matches != [str(i) for i in range(1, expected_slide_count + 1)]:
            raise RuntimeError(f"Slide numbering mismatch: {matches}")

    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(folder.iterdir()):
            zf.write(path, arcname=path.name)

    forbidden_ext = {".hwpx", ".hwp", ".docx", ".exe", ".db", ".png", ".csv", ".json", ".joblib"}
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if Path(name).suffix.lower() in forbidden_ext:
                raise RuntimeError(f"Forbidden file type in ZIP: {name}")


SLIDES = [
    (
        "표지",
        "MaintiQ Predict가 예측, 모니터링, AI 리포트, 작업지시를 하나의 운영 흐름으로 연결한 시스템임을 첫 화면에서 제시한다.",
        "제품명, 연구 제목, 학과/발표자 정보. 배경은 흰색, 진녹색 제목선.",
        "안녕하십니까. 본 발표에서는 ML 예측, Predictive SPC, GenAI 리포트, 승인형 작업지시를 결합한 스마트 제조 예지보전 시스템 MaintiQ Predict를 설명드리겠습니다.",
        "질문: 제품명 중심인가 연구 방법 중심인가? 답변: 제품명은 구현체이고, 연구 핵심은 예측-SPC-리포트-작업지시 통합입니다.",
    ),
    (
        "목차",
        "발표는 문제 정의, 선행연구, 시스템, 실험, 결론 순서로 진행된다.",
        "7개 항목 목차: Motivation, Contributions, Review, Main Part, 실험 설계, 실험 결과, 결론.",
        "발표는 먼저 제조 설비 고장 문제와 기존 보전 방식의 한계를 설명하고, 그다음 제안 시스템과 실험 결과, 주장 경계를 말씀드리겠습니다.",
        "질문: 왜 목차가 7개인가? 답변: 예시 최종발표 흐름에 맞춰 학술 발표에서 읽히기 쉬운 단위로 나눴습니다.",
    ),
    (
        "Motivation 1: 제조 설비 고장 문제",
        "설비 고장은 downtime, 품질 손실, 정비 비용 증가로 이어진다.",
        "간단한 문제 흐름도: 센서 이상 → 고장 위험 증가 → 생산 중단/정비 비용.",
        "제조 설비 고장은 단순한 장비 문제에 그치지 않고 생산 중단, 품질 손실, 납기 지연으로 이어집니다. 따라서 고장 가능성을 사전에 파악하고 의사결정으로 연결하는 구조가 필요합니다.",
        "질문: 실제 공장 데이터를 썼는가? 답변: 기본 모델은 AI4I, 공개 산업 검증은 SCANIA 등 공개 benchmark를 사용했습니다.",
    ),
    (
        "Motivation 2: 기존 보전 방식 한계",
        "사후보전과 예방보전은 놓치는 고장과 과잉 정비라는 trade-off를 갖는다.",
        "사후보전/예방보전/예지보전 비교표.",
        "사후보전은 고장 후 대응이므로 downtime이 커질 수 있고, 예방보전은 정해진 주기에 따라 정비해 과잉 정비가 발생할 수 있습니다. 본 연구는 센서 데이터 기반 예지보전을 통해 이 간격을 줄이는 방향을 다룹니다.",
        "질문: 예지보전이 항상 좋은가? 답변: 아닙니다. false alarm과 missed failure trade-off를 함께 봐야 합니다.",
    ),
    (
        "Contributions",
        "본 연구의 기여는 단일 모델보다 운영 흐름 통합에 있다.",
        "4개 기여 카드: 예측, SPC, GenAI, 작업지시.",
        "본 연구의 차별점은 예측 모델 하나에 그치지 않고, threshold 정책, Predictive SPC, GenAI 리포트, 승인형 작업지시를 하나의 로컬 제품형 MVP로 구현했다는 점입니다.",
        "질문: Something new는 무엇인가? 답변: 모델 자체보다 예측 결과를 운영 의사결정 흐름으로 연결한 통합성이 핵심입니다.",
    ),
    (
        "Review 1: 예지보전 / CBM",
        "CBM 선행연구는 상태 기반 정비의 필요성을 제시하지만 운영 workflow 연결은 별도 과제다.",
        "Jardine et al., Carvalho et al., Montgomery 핵심 요약표.",
        "선행연구는 상태 기반 정비와 예지보전의 필요성을 강조합니다. 본 연구는 이 흐름을 따라가되, 예측 결과를 관리자 리포트와 작업지시로 연결하는 구현에 초점을 두었습니다.",
        "질문: 산업공학 지식은 어떻게 반영됐는가? 답변: SPC, OEE/MTBF/MTTR 배경, FMEA/RPN식 위험 우선순위, cost simulation을 반영했습니다.",
    ),
    (
        "Review 2: ML 기반 예지보전",
        "ML 예지보전은 불균형 데이터와 threshold 정책이 성능 해석의 핵심이다.",
        "AI4I, XGBoost, SMOTE 관련 참고문헌 요약.",
        "ML 기반 예지보전에서는 고장 클래스가 매우 적은 불균형 문제가 중요합니다. 따라서 본 연구는 PR-AUC, recall, precision, threshold tuning을 함께 확인했습니다.",
        "질문: 왜 accuracy만 보지 않는가? 답변: 고장이 적은 데이터에서는 accuracy가 높아도 고장 탐지가 약할 수 있어 PR-AUC와 recall이 중요합니다.",
    ),
    (
        "Review 3: SPC / SHAP / Cost-sensitive Learning",
        "예측 결과는 관리도, 설명성, 비용 민감 의사결정과 결합될 때 운영 가치가 커진다.",
        "SPC, SHAP, cost-sensitive learning 연결 다이어그램.",
        "SPC는 위험 추세와 관리한계를 보는 관점이고, SHAP은 위험 요인을 설명하며, cost-sensitive learning은 false alarm과 missed failure의 비용 차이를 반영합니다.",
        "질문: 비용 절감 실증인가? 답변: 실제 비용 실증이 아니라 공식 cost metric과 normalized cost simulation입니다.",
    ),
    (
        "Main Part: 전체 시스템 구조",
        "입력 CSV부터 예측, SPC, 리포트, 작업지시까지 연결된다.",
        "시스템 아키텍처 다이어그램.",
        "제안 시스템은 센서 CSV를 입력받아 전처리와 예측을 수행하고, 위험 확률을 SPC 관점으로 모니터링하며, GenAI 리포트와 승인형 작업지시로 이어집니다.",
        "질문: 실시간 설비 연결인가? 답변: 현재는 CSV/로컬 기반 MVP이며 실제 설비망 연결은 향후 과제입니다.",
    ),
    (
        "Main Part: MaintiQ Predict 제품 화면",
        "운영자는 데스크톱 앱에서 CSV 예측, 위험 확인, 리포트, 작업지시를 처리한다.",
        "삽입 그림: outputs/maintiq_predict_screenshot.png",
        "이 화면은 사용자용 데스크톱 앱입니다. 연구 용어를 숨기고 운영자가 바로 사용할 수 있도록 데이터 예측, 위험 모니터링, AI 리포트, 작업지시 메뉴로 구성했습니다.",
        "질문: Streamlit인가? 답변: 사용자 앱은 PySide6 네이티브 데스크톱이고, 연구 검증은 별도 Admin 콘솔입니다.",
    ),
    (
        "Main Part: 데이터 입력 및 전처리",
        "AI4I 데이터는 ID와 leakage 컬럼을 제거하고 Type을 one-hot encoding한다.",
        "전처리 표: 제거 컬럼, 인코딩, split.",
        "학습에서는 UDI와 Product ID 같은 식별 컬럼을 제거했고, TWF/HDF/PWF/OSF/RNF처럼 target과 직접 연결되는 leakage 컬럼도 제거했습니다. Type은 one-hot encoding했습니다.",
        "질문: 왜 failure-type 컬럼을 제거했나? 답변: 해당 컬럼은 고장 원인 라벨에 가까워 실제 예측 시 데이터 누수를 만들 수 있기 때문입니다.",
    ),
    (
        "Main Part: 예측 모델 구조",
        "Logistic Regression을 기준선으로 두고 XGBoost를 주 예측 모델로 비교했다.",
        "모델 비교 구조도 또는 간단 표.",
        "baseline으로 Logistic Regression을 사용했고, 비선형 센서 조합을 반영하기 위해 XGBoost를 주 모델로 사용했습니다. 성능 비교는 precision, recall, F1, ROC-AUC, PR-AUC로 수행했습니다.",
        "질문: 최종 모델은 무엇인가? 답변: AI4I 기준 주 모델은 XGBoost이며 PR-AUC가 0.8014입니다.",
    ),
    (
        "Main Part: Threshold Policy",
        "고정 0.5 기준 대신 F1 기준 threshold 0.87을 선택했다.",
        "삽입 그림: outputs/threshold_tuning.png",
        "예측 확률은 0.5 기준으로만 판단하지 않았습니다. threshold를 0.05부터 0.95까지 탐색했고, F1 기준으로 0.87을 선택했습니다.",
        "질문: 왜 0.87인가? 답변: 해당 test split에서 precision과 recall의 균형인 F1-score가 가장 높았기 때문입니다.",
    ),
    (
        "Main Part: Predictive SPC",
        "예측 확률을 시계열 관리도처럼 보아 위험 흐름을 관리한다.",
        "삽입 그림: outputs/spc_risk_chart.png, outputs/spc_control_chart.png",
        "Predictive SPC는 단일 행 예측을 넘어서 위험 확률의 흐름을 보는 구조입니다. 고위험 구간과 관리한계를 함께 보여주어 운영자가 위험 추세를 판단할 수 있게 했습니다.",
        "질문: 기존 SPC와 차이는? 답변: 단일 센서 control limit만 보는 것이 아니라 ML 위험 확률을 함께 사용합니다.",
    ),
    (
        "Main Part: GenAI 관리자 리포트",
        "Gemini API가 위험 context를 관리자 참고 리포트로 요약한다.",
        "GenAI 검증표: mode, probability 0.993616, threshold 0.87, High Risk.",
        "Gemini generateContent API를 사용해 예측 확률 0.993616, 기준 0.87, High Risk 상태를 관리자 참고 리포트로 변환했습니다. 이 리포트는 조치 검토를 돕는 설명 자료입니다.",
        "질문: AI가 정비 명령을 내리나? 답변: 아닙니다. AI 리포트는 참고용이고 최종 결정은 승인형 작업지시에서 사람이 기록합니다.",
    ),
    (
        "Main Part: 승인형 작업지시 Workflow",
        "예측 결과는 자동 실행이 아니라 작업자 승인/검토/반려로 이어진다.",
        "workflow 다이어그램: 센서 이벤트 → 초안 → 작업자 결정 → 이력.",
        "시스템은 고위험 이벤트를 만들고 작업지시 초안을 생성하지만, 정비를 자동 실행하지 않습니다. 작업자가 승인, 검토 필요, 반려를 선택하고 이력이 저장됩니다.",
        "질문: 현장 안전 관점에서 괜찮은가? 답변: 자동 제어가 아니라 사람 승인 구조라 안전한 MVP 경계에 맞습니다.",
    ),
    (
        "실험 설계",
        "AI4I, 공개 benchmark, cost simulation을 분리해 검증했다.",
        "실험 설계 표: 데이터셋, 비교군, 지표.",
        "실험은 AI4I baseline, threshold tuning, SMOTE 비교, SPC-only vs ML+SPC, cost simulation, SCANIA official cost metric으로 나누어 진행했습니다.",
        "질문: 실제 회사 데이터 검증인가? 답변: 아닙니다. 실제 회사 실증은 별도 로그가 필요하며, 본 연구는 공개 데이터와 simulation 검증입니다.",
    ),
    (
        "실험 결과 1: AI4I Baseline",
        "XGBoost가 PR-AUC 0.8014로 Logistic Regression보다 우수했다.",
        "AI4I baseline 성능표, outputs/pr_curve.png.",
        "AI4I 기준 XGBoost는 PR-AUC 0.8014, ROC-AUC 0.9736을 기록했습니다. Logistic Regression보다 고장 탐지 ranking 성능이 높았습니다.",
        "질문: 왜 PR-AUC를 강조하나? 답변: 고장이 적은 불균형 데이터에서는 positive class 탐지 성능을 더 직접적으로 보여주기 때문입니다.",
    ),
    (
        "실험 결과 2: Threshold Tuning",
        "Threshold 0.87에서 F1-score 0.7752를 얻었다.",
        "threshold 결과표와 tuning plot.",
        "기본 threshold 0.5와 비교해 F1 기준 threshold 0.87을 선택했습니다. 이때 precision은 0.8197, recall은 0.7353, F1은 0.7752입니다.",
        "질문: recall이 낮아지는 것 아닌가? 답변: 맞습니다. false alarm을 줄이는 대신 missed failure가 늘 수 있어 운영 정책에 따라 조정해야 합니다.",
    ),
    (
        "실험 결과 3: SMOTE / 모델 전략 비교",
        "SMOTE는 무조건 개선이 아니라 precision-recall trade-off로 해석해야 한다.",
        "model_strategy_comparison 요약표, outputs/model_strategy_pr_curve.png.",
        "불균형 처리를 위해 SMOTE 적용 모델도 비교했습니다. 결과는 SMOTE가 항상 우수하다는 식이 아니라, precision과 recall의 trade-off로 해석했습니다.",
        "질문: 최종적으로 SMOTE를 쓰나? 답변: 논문에서는 비교 실험 근거로 사용하고, 최종 운영 판단은 지표별 trade-off를 보고 결정합니다.",
    ),
    (
        "실험 결과 4: SPC-only vs ML+SPC",
        "SPC-only는 alert가 적고 recall이 낮았으며, ML+SPC는 recall을 높였다.",
        "SPC 비교표: SPC-only F1 0.1600, ML threshold F1 0.7752, ML+SPC F1 0.7051.",
        "SPC-only torque rule은 alert가 7개로 적지만 recall이 0.0882였습니다. ML threshold는 F1 0.7752, ML+SPC는 recall 0.8088로 더 적극적인 탐지 특성을 보였습니다.",
        "질문: 어떤 전략이 최선인가? 답변: F1은 ML threshold가 높고, recall-first 운영이면 ML+SPC를 고려할 수 있습니다.",
    ),
    (
        "실험 결과 5: Operational Cost Simulation",
        "false alarm과 missed failure 비용 가중치로 운영 정책을 비교했다.",
        "삽입 그림: outputs/operational_value_simulation.png",
        "운영 비용은 실제 원화가 아니라 normalized cost simulation으로 평가했습니다. false alarm과 missed failure의 상대 비용을 두고 정책별 의사결정 가능성을 비교했습니다.",
        "질문: 비용 절감 증명인가? 답변: 실제 비용 실증이 아니라 비용 민감 정책 비교 시뮬레이션입니다.",
    ),
    (
        "실험 결과 6: SCANIA Official Cost Metric",
        "SCANIA 공개 benchmark에서 official cost metric 기준 rule 대비 17.02% 개선 가능성을 확인했다.",
        "삽입 그림: outputs/scania_official_cost_comparison.png",
        "SCANIA Component X는 실제 SCANIA fleet에서 수집된 공개 benchmark입니다. official cost matrix 기준 XGBoost cost-optimized 전략이 rule baseline 대비 17.02% 낮은 cost metric을 보였습니다.",
        "질문: 실제 회사 비용 절감인가? 답변: 아닙니다. SCANIA official cost metric 기준 공개 benchmark 결과입니다.",
    ),
    (
        "실험 결과 7: Public Benchmark Extension",
        "MetroPT-3, C-MAPSS, IMS/FEMTO는 확장 검증 경로로 정리했다.",
        "public benchmark 표와 outputs/public_industrial_cost_chart.png.",
        "AI4I와 SCANIA 외에도 MetroPT-3, NASA C-MAPSS, IMS/FEMTO 데이터를 고려할 수 있는 adapter와 검증 산출물을 정리했습니다. 이는 실제 회사 실증 전 공개 benchmark 확장 근거입니다.",
        "질문: 전부 full benchmark인가? 답변: 원본 데이터 유무에 따라 sample smoke와 full benchmark가 구분됩니다.",
    ),
    (
        "제품 구현 결과: Full/Lite 데스크톱 앱",
        "정밀 분석 모드와 빠른 점검 모드를 분리해 설치성과 분석성을 모두 고려했다.",
        "삽입 그림: outputs/maintiq_predict_screenshot.png, outputs/maintiq_predict_lite_screenshot.png",
        "Full은 XGBoost/SHAP 기반 정밀 분석 모드이고, Lite는 작은 설치본과 경량 운영 점수를 사용하는 빠른 점검 모드입니다. 두 모드는 목적이 달라 결과가 다를 수 있습니다.",
        "질문: 왜 두 버전인가? 답변: 연구 검증과 일반 배포의 의존성/용량 요구가 다르기 때문입니다.",
    ),
    (
        "Claim Boundary: 가능한 주장 / 금지 주장",
        "본 연구는 공개 데이터와 로컬 MVP 검증이며 실제 현장 실증은 별도 데이터가 필요하다.",
        "가능한 주장/금지 주장 2열 표.",
        "발표에서 가장 중요한 경계는 과장하지 않는 것입니다. 공개 benchmark와 로컬 simulation은 주장할 수 있지만, 실제 회사 비용 절감이나 PLC 운영망 배포는 주장하지 않습니다.",
        "질문: 실제 현장 실증은 어떻게 하나? 답변: labeled sensor CSV, maintenance history, downtime/cost log가 필요합니다.",
    ),
    (
        "결론 및 향후 연구",
        "예측에서 운영 의사결정까지 연결한 제품형 MVP를 구현했다.",
        "결론 3줄: 구현 성과, 검증 성과, 향후 연구.",
        "결론적으로 본 연구는 고장 확률 예측, SPC 모니터링, GenAI 리포트, 승인형 작업지시를 연결한 제품형 MVP를 구현했습니다. 향후 실제 회사 로그로 성능과 비용 효과를 검증하는 것이 다음 단계입니다.",
        "질문: 지금 바로 현장 적용 가능한가? 답변: CSV 기반 MVP로는 가능하지만, 현장 운영 적용은 데이터 계약과 설비 연동 검증이 필요합니다.",
    ),
    (
        "References",
        "핵심 참고문헌은 예지보전, SPC, ML, 설명가능성, 공개 benchmark를 포괄한다.",
        "축약 참고문헌 목록.",
        "참고문헌은 예지보전/CBM, SPC, XGBoost, SMOTE, SHAP, SCANIA Component X, AI4I 2020, Gemini API 문서를 중심으로 구성했습니다.",
        "질문: 참고문헌은 충분한가? 답변: 이론, 데이터셋, 모델, 구현 API를 모두 포함하도록 구성했습니다.",
    ),
]


def slide_markdown() -> str:
    lines = ["# 28슬라이드 최종발표 구성안", ""]
    for idx, (title, message, visual, talk, qa) in enumerate(SLIDES, start=1):
        lines.extend(
            [
                f"### {idx}. {title}",
                f"- 핵심 메시지: {message}",
                f"- 넣을 표/그림: {visual}",
                f"- 발표 대본: {talk}",
                f"- 예상 질문 대응: {qa}",
                "",
            ]
        )
    return "\n".join(lines)


def talk_script() -> str:
    lines = ["# 슬라이드별 발표 대본", ""]
    for idx, (title, _, _, talk, qa) in enumerate(SLIDES, start=1):
        lines.extend([f"## {idx}. {title}", "", talk, "", f"예상 질문 대응: {qa}", ""])
    return "\n".join(lines)


def create_ppt_packet() -> None:
    reset_dir(PPT_PACKET)
    write_text(
        PPT_PACKET / "00_PPT_제작_가이드.txt",
        """
# PPT 제작 가이드

## 기본 조건
- 최종발표용 PPT는 28슬라이드로 구성한다.
- 발표 흐름은 Motivation, Contributions, Review, Main Part, 실험 설계, 실험 결과, 결론 순서다.
- 디자인은 흰 배경, 진녹색 제목선, 표/그림 중심의 학술 발표 스타일을 사용한다.
- 한 슬라이드에는 하나의 메시지만 둔다.

## 금지 표현
- PLC/SCADA 운영망을 실제로 배포했다는 표현 금지.
- 회사 실제 라벨 데이터로 성능을 최종 확인했다는 표현 금지.
- 회사 현장에서 비용 절감률이나 탐지 시간 단축률을 입증했다는 표현 금지.
- 시스템이 정비 명령을 자동 실행한다고 쓰는 표현 금지.

## 사용 방법
1. `01_슬라이드별_구성안.md`로 PPT 목차와 슬라이드 내용을 잡는다.
2. `02_슬라이드별_발표대본.md`로 발표 대본을 만든다.
3. `03_PPT_삽입_그림표_목록.md`의 그림 경로를 PPT에 삽입한다.
4. `04_표_요약본.md`의 표는 슬라이드에 맞게 3~5행으로 줄인다.
""",
    )
    write_text(PPT_PACKET / "01_슬라이드별_구성안.md", slide_markdown())
    write_text(PPT_PACKET / "02_슬라이드별_발표대본.md", talk_script())
    write_text(
        PPT_PACKET / "03_PPT_삽입_그림표_목록.md",
        """
# PPT 삽입 그림/표 목록

| 사용 슬라이드 | 자료 | 파일 경로 | 비고 |
|---:|---|---|---|
| 10 | 제품 메인 화면 | `outputs/maintiq_predict_screenshot.png` | MaintiQ Predict 사용자 앱 |
| 25 | Lite 화면 | `outputs/maintiq_predict_lite_screenshot.png` | 빠른 점검 모드 설명 |
| 18 | PR curve | `outputs/pr_curve.png` | AI4I baseline |
| 19 | Threshold tuning | `outputs/threshold_tuning.png` | threshold 0.87 근거 |
| 14, 21 | SPC risk chart | `outputs/spc_risk_chart.png` | 위험 확률 흐름 |
| 14 | SPC control chart | `outputs/spc_control_chart.png` | 관리도 시각화 |
| 20 | Model strategy PR curve | `outputs/model_strategy_pr_curve.png` | SMOTE/전략 비교 |
| 22 | Cost simulation | `outputs/operational_value_simulation.png` | normalized cost |
| 23 | SCANIA cost comparison | `outputs/scania_official_cost_comparison.png` | official cost metric |
| 24 | Public benchmark cost | `outputs/public_industrial_cost_chart.png` | benchmark 확장 |
| 12 | SHAP summary | `outputs/shap_summary.png` | 위험 요인 설명 |
| 12 | SHAP bar | `outputs/shap_bar.png` | feature importance |
""",
    )
    write_text(
        PPT_PACKET / "04_표_요약본.md",
        """
# PPT용 표 요약본

## AI4I Baseline
| 모델 | Precision | Recall | F1 | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|---:|
| Logistic Regression | 0.1418 | 0.8235 | 0.2419 | 0.9069 | 0.3817 |
| XGBoost | 0.4444 | 0.8824 | 0.5911 | 0.9736 | 0.8014 |

## Threshold Tuning
| 기준 | Precision | Recall | F1 |
|---|---:|---:|---:|
| default 0.5 | 0.4444 | 0.8824 | 0.5911 |
| selected 0.87 | 0.8197 | 0.7353 | 0.7752 |

## SPC-only vs ML+SPC
| 전략 | Precision | Recall | F1 | Alerts | FP | FN |
|---|---:|---:|---:|---:|---:|---:|
| SPC-only | 0.8571 | 0.0882 | 0.1600 | 7 | 1 | 62 |
| ML threshold | 0.8197 | 0.7353 | 0.7752 | 61 | 11 | 18 |
| ML+SPC | 0.6250 | 0.8088 | 0.7051 | 88 | 33 | 13 |

## GenAI Report
| 항목 | 값 |
|---|---|
| mode | gemini_generate_content:gemini-2.5-flash |
| probability | 0.993616 |
| threshold | 0.87 |
| status | High Risk |
| factors | torque, rotational speed, air temperature |

## SCANIA Official Cost Metric
| 전략 | Official cost | Normalized cost | Rule 대비 개선 |
|---|---:|---:|---:|
| Rule baseline | 59709 | 1.0402 | 0 |
| XGBoost cost-optimized | 49548 | 0.8632 | 17.02% |
""",
    )
    write_text(
        PPT_PACKET / "05_작동화면_시연순서.md",
        """
# 작동화면 시연 순서

## 1. 홈 화면
- 보여줄 화면: `outputs/maintiq_predict_screenshot.png`
- 말할 내용: 운영자가 CSV 예측, 위험 모니터링, AI 리포트, 작업지시를 한 앱에서 처리한다.

## 2. 데이터 예측
- CSV 선택 → 컬럼 확인 → 품질 진단 → 예측 실행 → 결과 저장 흐름을 설명한다.
- 강조: 사용자 원본 데이터와 API key는 파일에 저장하지 않는다.

## 3. 위험 모니터링
- SPC chart와 high-risk count를 보여준다.
- 강조: 단일 row 예측이 아니라 위험 흐름을 확인한다.

## 4. AI 리포트
- Gemini 리포트 검증값을 보여준다.
- 강조: 관리자 참고 리포트이며 최종 조치는 사람이 승인한다.

## 5. 작업지시
- 센서 이벤트 → 작업지시 초안 → 승인/검토/반려 → 이력 저장.
- 강조: 장비 제어를 자동 수행하지 않는다.
""",
    )
    write_text(
        PPT_PACKET / "06_참고문헌_Review_슬라이드.md",
        """
# 참고문헌 Review 슬라이드 구성

## Review 1: 예지보전 / CBM
- Jardine et al. (2006): condition-based maintenance와 prognostics의 필요성.
- Carvalho et al. (2019): ML 기반 예지보전 연구 동향.
- Montgomery (2019): SPC 관리도와 품질관리 이론.
- 본 연구 반영점: 예측 결과를 SPC와 운영 workflow에 연결.

## Review 2: ML 기반 예지보전
- AI4I 2020 / Matzka (2020): 예지보전 실험용 공개 데이터.
- Chen & Guestrin (2016): XGBoost.
- Chawla et al. (2002): SMOTE.
- 본 연구 반영점: Logistic Regression, XGBoost, SMOTE, threshold tuning 비교.

## Review 3: SPC / SHAP / Cost-sensitive Learning
- Lundberg & Lee (2017): SHAP 설명가능성.
- Elkan (2001): cost-sensitive learning.
- SCANIA Component X: real-world multivariate time-series benchmark.
- 본 연구 반영점: 설명가능성, 공식 cost metric, normalized cost simulation.
""",
    )
    write_text(
        PPT_PACKET / "07_PPT_금지주장_체크리스트.md",
        """
# PPT 금지 주장 체크리스트

## 쓰면 안 되는 방향
- PLC/SCADA 운영망을 실제로 배포했다는 표현.
- 회사 실제 라벨 데이터로 성능을 최종 확인했다는 표현.
- 회사 현장에서 비용 절감률이나 탐지 시간 단축률을 입증했다는 표현.
- 시스템이 정비 명령을 자동 실행한다고 쓰는 표현.

## 대신 쓸 표현
- CSV 기반 제품형 MVP.
- 공개 benchmark official cost metric 검증.
- normalized cost simulation.
- 관리자 참고 리포트.
- 승인형 작업지시 workflow.
- 실제 현장 적용을 위한 데이터 수집 템플릿 준비.
""",
    )
    validate_bundle(PPT_PACKET, PPT_ZIP, expected_slide_count=28)


def append_thesis_materials() -> None:
    # Recreate the base thesis packet first, then append the 29-page focused files.
    thesis_packet.main()
    packet = thesis_packet.PACKET

    # Clean a few known mojibake fragments inherited from citation metadata.
    for path in packet.iterdir():
        if path.suffix.lower() in {".txt", ".md"}:
            write_text(path, clean_common_mojibake(read_text(path)))

    write_text(
        packet / "11_서론_본론_결론_작성지침.md",
        """
# 서론·본론·결론 작성지침

## 서론
- 제조 설비 고장 문제가 downtime, 품질 손실, 정비 비용 증가로 이어진다는 점을 설명한다.
- 사후보전과 예방보전의 한계를 설명한다.
- 본 연구의 목적을 `예측 결과를 운영 의사결정으로 연결하는 제품형 MVP 구현`으로 정리한다.
- 연구 범위는 공개 데이터와 로컬 MVP 검증이며, 회사 현장 로그 기반 실증은 향후 과제로 둔다.

## 본론
- 이론적 배경: 예지보전, CBM, SPC, FMEA/RPN, cost-sensitive learning.
- 연구 방법: AI4I 전처리, XGBoost, threshold tuning, SPC 비교, SCANIA official cost metric.
- 시스템 구현: 데스크톱 앱, Admin 콘솔, GenAI 리포트, 승인형 작업지시.
- 실험 검증: AI4I baseline, SMOTE/threshold, SPC-only vs ML+SPC, cost simulation, SCANIA benchmark.

## 결론
- 구현 성과: 예측, SPC, 리포트, 작업지시 workflow 통합.
- 검증 성과: AI4I PR-AUC, threshold 0.87, Gemini 리포트, SCANIA official cost metric.
- 한계: 회사 실제 로그, PLC/SCADA 운영망, 원화 비용 실증은 미포함.
- 향후 연구: 실제 회사 labeled sensor CSV, maintenance history, downtime/cost log 확보 후 field validation.
""",
    )
    write_text(
        packet / "12_장별_필수내용_체크리스트.md",
        """
# 장별 필수 내용 체크리스트

## 1장 서론
- 연구 배경: 제조 설비 downtime과 보전 전략 문제.
- 연구 목적: 예측, SPC, GenAI, 작업지시 통합.
- 연구 범위: 공개 데이터와 로컬 제품형 MVP.

## 2장 이론적 배경 및 선행연구
- 사후보전/예방보전/예지보전 비교.
- CBM, OEE, MTBF, MTTR 연결.
- SPC 관리도, UCL/LCL.
- XGBoost, SMOTE, SHAP, cost-sensitive learning.

## 3장 연구 방법
- AI4I 2020 전처리.
- Logistic Regression과 XGBoost 비교.
- threshold tuning.
- SPC-only vs ML+SPC 비교 설계.
- SCANIA official cost metric 검증 설계.

## 4장 시스템 구현
- MaintiQ Predict 데스크톱 앱.
- Full/Lite 모드 구분.
- GenAI 리포트 생성.
- 승인형 작업지시 workflow.

## 5장 실험 및 검증
- AI4I baseline 결과.
- threshold 0.87 결과.
- SMOTE/전략 비교.
- SPC-only vs ML+SPC.
- Gemini report 검증.
- SCANIA official cost metric.
- 실제 현장 실증 한계.

## 6장 결론 및 향후 연구
- 연구 결과 요약.
- 한계.
- 실제 회사 데이터 기반 검증 계획.
""",
    )
    write_text(
        packet / "13_논문_그림표_삽입계획.md",
        """
# 논문 그림/표 삽입계획

## 표
- 표 1: 사후보전, 예방보전, 예지보전 비교.
- 표 2: AI4I 2020 전처리 기준.
- 표 3: Logistic Regression vs XGBoost baseline.
- 표 4: threshold tuning 결과.
- 표 5: SPC-only vs ML+SPC 비교.
- 표 6: GenAI 리포트 검증 결과.
- 표 7: SCANIA official cost metric 비교.
- 표 8: 가능한 주장과 금지 주장.

## 그림
- 그림 1: 전체 시스템 아키텍처.
- 그림 2: MaintiQ Predict 메인 화면.
- 그림 3: PR curve.
- 그림 4: threshold tuning plot.
- 그림 5: SPC risk chart.
- 그림 6: SHAP summary.
- 그림 7: operational cost simulation.
- 그림 8: SCANIA official cost comparison.
""",
    )
    write_text(
        packet / "14_메인화면_및_시스템화면_설명문.md",
        """
# 메인화면 및 시스템화면 설명문

## 홈 화면
MaintiQ Predict의 홈 화면은 데이터 예측, 위험 모니터링, AI 리포트, 작업지시 메뉴를 제공한다. 사용자 앱에서는 연구/검증 용어를 숨기고 운영 화면처럼 구성했다.

## 데이터 예측 화면
사용자는 센서 CSV를 선택하고, 컬럼 확인과 품질 진단을 거친 뒤 예측을 실행한다. 결과는 고장 확률, High Risk 판정, 위험 우선순위, 결과 CSV 저장으로 이어진다.

## 위험 모니터링 화면
예측 확률과 high-risk count를 SPC 관점으로 확인한다. 이는 단일 row 판정이 아니라 위험 흐름을 보는 기능이다.

## AI 리포트 화면
Gemini/OpenAI API key를 세션에서 입력해 관리자 참고 리포트를 생성할 수 있다. key는 파일에 저장하지 않는다.

## 작업지시 화면
센서 이벤트를 생성하고 작업지시 초안을 만든 뒤, 작업자가 승인/검토/반려 결정을 저장한다. 장비 제어 자동 수행은 하지 않는다.
""",
    )
    write_text(
        packet / "15_논문_질문방어_QA.md",
        """
# 논문 질문방어 Q&A

## Q1. 왜 threshold가 0.87인가?
AI4I test split에서 threshold를 0.05부터 0.95까지 탐색했고, F1-score 기준으로 0.87이 선택되었다. 이때 precision은 0.8197, recall은 0.7353, F1-score는 0.7752다.

## Q2. rule baseline은 무엇인가?
rule baseline은 단일 feature threshold 또는 SPC-style control limit처럼 사람이 정한 규칙 기반 판정이다. 본 연구에서는 ML 기반 판정과 비교하기 위한 기준선으로 사용했다.

## Q3. SCANIA 17.02%는 실제 비용 절감인가?
아니다. SCANIA Component X의 official cost matrix 기준 rule baseline 대비 cost metric 개선이다. 회사 현장의 원화 비용 절감 실증으로 표현하면 안 된다.

## Q4. 실제 회사 데이터가 없는데 연구 의미가 있는가?
있다. 공개 데이터와 공개 benchmark를 통해 재현 가능한 모델/정책 비교를 수행했고, 실제 회사 실증에 필요한 데이터 템플릿과 workflow를 준비했다.

## Q5. GenAI 리포트는 어떤 의미인가?
예측 context를 관리자 참고 문장으로 바꾸는 기능이다. 자동 조치가 아니라 사람이 승인형 작업지시에서 최종 판단하도록 돕는다.
""",
    )
    write_text(
        packet / "16_최종_논문작성_프롬프트.txt",
        """
첨부된 자료 패킷을 기반으로 한국어 학부 캡스톤 논문 초안을 29쪽 내외로 작성해줘.

조건:
- 장 구성은 서론, 이론적 배경 및 선행연구, 연구 방법, 시스템 구현, 실험 및 검증, 결론 및 향후 연구, 참고문헌 순서로 한다.
- 표와 그림 삽입 위치를 본문에 표시한다.
- AI4I 2020, XGBoost, threshold 0.87, Predictive SPC, Gemini 리포트, 승인형 작업지시, SCANIA official cost metric을 반드시 포함한다.
- 실제 회사 비용 절감률이나 탐지 시간 단축률을 입증한 것처럼 쓰지 않는다.
- PLC/SCADA 운영망을 실제로 배포한 것처럼 쓰지 않는다.
- 시스템이 정비 명령을 자동 실행한다고 쓰지 않는다.
- 문체는 학부 졸업논문/캡스톤 논문체로 한다.

먼저 전체 목차와 각 장의 분량 계획을 제시한 뒤, 장별 본문을 작성해줘.
""",
    )
    thesis_packet.validate_packet()
    thesis_packet.create_zip()


def main() -> None:
    create_ppt_packet()
    append_thesis_materials()
    validate_bundle(PPT_PACKET, PPT_ZIP, expected_slide_count=28)
    validate_bundle(thesis_packet.PACKET, thesis_packet.ZIP_PATH)

    print(f"ppt_packet={PPT_PACKET}")
    print(f"ppt_zip={PPT_ZIP} size={PPT_ZIP.stat().st_size}")
    print(f"thesis_packet={thesis_packet.PACKET}")
    print(f"thesis_zip={thesis_packet.ZIP_PATH} size={thesis_packet.ZIP_PATH.stat().st_size}")


if __name__ == "__main__":
    main()
