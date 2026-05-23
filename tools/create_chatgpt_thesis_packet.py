from __future__ import annotations

import csv
import json
import os
import re
import shutil
import stat
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
PACKET = OUT / "chatgpt_thesis_packet"
ZIP_PATH = OUT / "chatgpt_thesis_packet.zip"


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def load_json(name: str, default):
    path = OUT / name
    if not path.exists():
        return default
    return json.loads(read_text(path))


def load_csv_dicts(name: str) -> list[dict[str, str]]:
    path = OUT / name
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_packet(name: str, text: str) -> None:
    # UTF-8 BOM keeps Korean text readable in common Windows editors.
    (PACKET / name).write_text(text.strip() + "\n", encoding="utf-8-sig")


def fmt(value, default: str = "N/A") -> str:
    return default if value in (None, "") else str(value)


def pct(value) -> str:
    try:
        return f"{float(value) * 100:.2f}%"
    except Exception:
        return "N/A"


def table_rows(rows: list[dict[str, str]], cols: list[str]) -> str:
    if not rows:
        return "| 결과 파일 없음 | " + " | ".join(["N/A"] * (len(cols) - 1)) + " |"
    return "\n".join("| " + " | ".join(fmt(row.get(col)) for col in cols) + " |" for row in rows)


def validate_packet() -> None:
    combined = "\n".join(read_text(path) for path in sorted(PACKET.iterdir()) if path.is_file())

    key_patterns = [
        r"AIza[0-9A-Za-z_\-]{20,}",
        r"sk-[0-9A-Za-z_\-]{20,}",
        r"OPENAI_API_KEY\s*=\s*[^\s]+",
        r"GEMINI_API_KEY\s*=\s*[^\s]+",
    ]
    for pattern in key_patterns:
        if re.search(pattern, combined):
            raise RuntimeError(f"API key-like pattern found in packet: {pattern}")

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

    if "�" in combined:
        raise RuntimeError("Replacement character found in packet")

    mojibake_markers = ["?쇰", "?곌", "媛", "紐", "諛"]
    for marker in mojibake_markers:
        if marker in combined:
            raise RuntimeError(f"Mojibake marker found in packet: {marker}")


def create_zip() -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(PACKET.iterdir()):
            if path.suffix.lower() not in {".txt", ".md"}:
                raise RuntimeError(f"Unexpected file type for ZIP: {path.name}")
            zf.write(path, arcname=path.name)

    forbidden_ext = {".hwpx", ".hwp", ".docx", ".exe", ".db", ".png", ".csv", ".json"}
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        for name in zf.namelist():
            if Path(name).suffix.lower() in forbidden_ext:
                raise RuntimeError(f"Forbidden file type in ZIP: {name}")


def main() -> None:
    if PACKET.exists():
        os.chmod(PACKET, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        shutil.rmtree(PACKET)
    PACKET.mkdir(parents=True, exist_ok=True)

    metrics = load_json("metrics.json", {})
    threshold = load_json("threshold_summary.json", {})
    scania = load_json("scania_official_cost_metrics.json", {})
    spc_rows = load_csv_dicts("spc_vs_ml_comparison.csv")
    model_rows = load_csv_dicts("model_strategy_comparison.csv")

    genai_evidence = read_text(OUT / "genai_report_evidence.md")
    references = read_text(OUT / "research_references.md")

    xgb = metrics.get("models", {}).get("xgboost", {})
    logreg = metrics.get("models", {}).get("logistic_regression", {})
    selected = threshold.get("selected_metrics", {})
    selected_threshold = threshold.get("selected_threshold", 0.87)

    scania_metrics = scania.get("metrics", [])
    scania_best = next((m for m in scania_metrics if m.get("strategy_id") == "xgboost_cost_optimized"), {})
    scania_rule = next((m for m in scania_metrics if m.get("strategy_id") == "rule_based_threshold"), {})
    scania_improve = scania_best.get("cost_improvement_vs_rule")

    model_table = table_rows(
        model_rows,
        ["display_name", "precision", "recall", "f1_score", "pr_auc"],
    )
    spc_table = table_rows(
        spc_rows,
        ["display_name", "precision", "recall", "f1_score", "alert_count", "false_positive", "false_negative"],
    )

    write_packet(
        "00_README_먼저읽기.txt",
        f"""
# ChatGPT 논문 작성용 자료 패킷

이 폴더는 ChatGPT에 논문 초안을 작성시킬 때 바로 업로드하거나 복사해서 사용할 수 있도록 정리한 자료 묶음이다.
기존 HWPX/DOCX 파일은 넣지 않았다. HWPX는 내부적으로 압축 패키지라 텍스트 편집기로 열면 `PK`로 시작하는 원시 ZIP 구조가 보일 수 있기 때문이다.

## 사용 순서

1. `01_CHATGPT_논문작성_마스터프롬프트.txt` 내용을 ChatGPT에 먼저 붙여넣는다.
2. 이 폴더 전체 또는 `chatgpt_thesis_packet.zip`을 첨부한다.
3. ChatGPT에게 `03_논문목차_29쪽구성안.md`의 장별 분량을 우선 지키라고 지시한다.
4. 논문 초안이 나오면 한글/HWP 양식에 직접 붙여넣어 표지, 목차, 쪽번호, 줄간격을 최종 편집한다.

## 반드시 지킬 주장 경계

- PLC/SCADA 운영망을 실제로 배포했다는 식으로 쓰면 안 된다.
- 회사 실제 라벨 데이터로 성능을 최종 확인했다는 식으로 쓰면 안 된다.
- 회사 현장에서 비용 절감률이나 탐지 시간 단축률을 입증했다는 식으로 쓰면 안 된다.
- 시스템이 정비 명령을 자동 실행한다고 쓰면 안 된다.
- 본 시스템은 CSV 기반 예측, 공개 데이터 검증, GenAI 관리자 참고 리포트, 승인형 작업지시 흐름을 통합한 제품형 MVP로 서술한다.

## 주요 실험 수치 요약

- AI4I 2020 test rows: {metrics.get("test_rows", "N/A")}
- Best baseline model: {metrics.get("best_model_by_pr_auc", "N/A")}
- XGBoost PR-AUC: {xgb.get("pr_auc", "N/A")}
- XGBoost ROC-AUC: {xgb.get("roc_auc", "N/A")}
- Threshold tuning 기준: {selected_threshold}
- Threshold tuning F1: {selected.get("f1_score", "N/A")}
- Gemini report mode: gemini_generate_content:gemini-2.5-flash
- SCANIA official cost improvement vs rule baseline: {pct(scania_improve)}
""",
    )

    write_packet(
        "01_CHATGPT_논문작성_마스터프롬프트.txt",
        f"""
너는 한국어 학부 캡스톤 논문 작성 보조자다. 첨부된 자료 패킷을 기반으로 29쪽 내외의 논문 초안을 작성해라.

논문 주제는 `MaintiQ Predict: ML 예측, Predictive SPC, GenAI 리포트, 승인형 작업지시를 결합한 스마트 제조 예지보전 시스템`이다.

작성 조건:
- 한국어 논문체로 작성한다.
- 장 구성은 `서론`, `이론적 배경 및 선행연구`, `연구 방법`, `시스템 구현`, `실험 및 검증`, `결론 및 향후 연구`, `참고문헌` 순서로 한다.
- 분량은 29쪽 내외를 목표로 한다.
- 표와 그림 위치를 본문에 제안한다.
- 참고문헌은 첨부된 `07_참고문헌_정리.md`를 사용한다.
- 회사 현장 로그 기반 실증, PLC/SCADA 운영망 배포, 비용 절감 입증은 주장하지 않는다.
- AI 리포트는 실제 Gemini API 호출 결과가 있으나, 관리자 참고 리포트로만 표현하고 정비 명령 자동 실행이라고 쓰지 않는다.

반드시 포함할 내용:
1. AI4I 2020 데이터셋 기반 전처리: ID 컬럼 제거, leakage failure-type 컬럼 제거, Type one-hot encoding, stratified split.
2. Logistic Regression과 XGBoost baseline 비교.
3. XGBoost PR-AUC {xgb.get("pr_auc", "N/A")} 및 threshold {selected_threshold}에서 F1 {selected.get("f1_score", "N/A")}.
4. SMOTE/threshold 비교는 trade-off 관점으로 서술한다.
5. SPC-only, ML threshold, ML+SPC 비교를 precision, recall, false alarm, missed failure 관점으로 설명한다.
6. normalized cost simulation은 실제 원화 절감이 아니라 운영 정책 비교용 시뮬레이션으로 설명한다.
7. SCANIA Component X 공개 benchmark는 official cost metric 기준 개선 가능성으로 서술한다. 회사 현장 원화 비용 절감을 입증한 것처럼 쓰지 않는다.
8. Gemini 리포트 검증: `gemini_generate_content:gemini-2.5-flash`, 예측 확률 0.993616, 기준 0.87, 상태 High Risk.
9. 작업지시는 자동 명령이 아니라 승인형 workflow로 설명한다.
10. 결론에서는 제품형 MVP의 구현 성과와 실제 현장 적용을 위한 추가 데이터 요구사항을 명확히 쓴다.

출력 형식:
- 먼저 전체 목차를 보여준다.
- 그다음 장별 본문을 작성한다.
- 각 장 말미에 넣을 표/그림 후보를 표시한다.
- 마지막에 참고문헌을 번호식으로 정리한다.
""",
    )

    write_packet(
        "02_연구개요_및_something_new.md",
        """
# 연구개요 및 Something New

## 연구 제목 후보
ML 예측, Predictive SPC, GenAI 리포트 및 승인형 작업지시를 결합한 스마트 제조 예지보전 운영 시스템 구현

## 연구 배경
스마트 제조 환경에서는 센서 데이터가 지속적으로 축적되지만, 고장 예측 결과가 실제 운영 의사결정으로 연결되지 않으면 현장 활용성이 떨어진다. 기존 방식은 사후보전 또는 일정 기반 예방보전에 의존하는 경우가 많아 downtime, 과잉 정비, missed failure 문제가 발생할 수 있다.

## 연구 목적
본 연구는 CSV 기반 설비 센서 데이터를 입력받아 고장 확률을 계산하고, 위험 판정 기준과 SPC 관점의 모니터링을 결합하며, GenAI 관리자 참고 리포트와 승인형 작업지시 workflow까지 연결하는 제품형 MVP를 구현하는 것을 목표로 한다.

## Something New
본 연구의 차별점은 단일 예측 모델 성능 향상만이 아니라 다음 요소를 하나의 재현 가능한 흐름으로 통합했다는 점이다.

1. AI4I 2020 기반 고장 확률 예측과 threshold tuning.
2. SPC-only와 ML+SPC 위험 판정 비교.
3. normalized cost simulation을 통한 운영 정책 trade-off 평가.
4. Gemini 기반 관리자 참고 리포트 생성.
5. 자동 정비 명령이 아닌 승인형 작업지시 workflow.
6. SCANIA Component X 공개 산업 benchmark의 official cost metric 검증.
7. 실제 회사 데이터 실증을 위한 sensor/maintenance/cost template과 claim boundary 정리.

## 안전한 주장
- 공개 데이터 기반 모델/정책 비교를 수행했다.
- AI4I 기준 XGBoost가 Logistic Regression보다 PR-AUC에서 우수했다.
- threshold tuning으로 precision-recall trade-off를 조정했다.
- Gemini API로 관리자 참고 리포트를 생성할 수 있음을 검증했다.
- SCANIA 공개 benchmark에서 official cost metric 기준 rule baseline 대비 개선 가능성을 확인했다.
""",
    )

    write_packet(
        "03_논문목차_29쪽구성안.md",
        """
# 논문 목차 및 29쪽 내외 구성안

## 앞부분
- 표지, 내표지, 인준서: 학교 양식 사용
- 목차: 1쪽
- 국문초록: 1쪽

## 본문 구성

### 1. 서론: 3쪽
1.1 연구 배경  
1.2 문제 정의  
1.3 연구 목적  
1.4 연구 범위와 주장 경계  

### 2. 이론적 배경 및 선행연구: 5쪽
2.1 사후보전, 예방보전, 예지보전  
2.2 Condition-Based Maintenance와 산업공학 지표  
2.3 SPC 관리도와 UCL/LCL  
2.4 머신러닝 기반 예지보전 선행연구  
2.5 설명가능 AI와 GenAI 리포트  

### 3. 연구 방법: 5쪽
3.1 전체 연구 절차  
3.2 AI4I 2020 데이터 전처리  
3.3 모델 학습 및 평가 지표  
3.4 Threshold tuning 및 운영 정책  
3.5 SPC-only, ML threshold, ML+SPC 비교 방법  
3.6 공개 benchmark 및 cost simulation 방법  

### 4. 시스템 구현: 5쪽
4.1 MaintiQ Predict 구성  
4.2 데스크톱 앱과 Admin 콘솔 분리  
4.3 CSV 예측 workflow  
4.4 GenAI 관리자 리포트 생성 구조  
4.5 승인형 작업지시 workflow  
4.6 Full/Lite 설치본 구조  

### 5. 실험 및 검증: 8쪽
5.1 AI4I baseline 결과  
5.2 Threshold tuning 결과  
5.3 SMOTE 및 모델 전략 비교  
5.4 SPC-only vs ML+SPC 결과  
5.5 Operational cost simulation  
5.6 Gemini 리포트 생성 검증  
5.7 SCANIA official cost metric 검증  
5.8 실제 회사 데이터 실증 준비성  

### 6. 결론 및 향후 연구: 2쪽
6.1 연구 결과 요약  
6.2 연구의 한계  
6.3 향후 연구 방향  

### 참고문헌: 2쪽
번호식 또는 APA 형식으로 통일한다.

### 부록: 선택
- Gemini 리포트 전문
- field validation template
- 실행 명령 및 검증 명령
""",
    )

    write_packet(
        "04_실험결과_핵심표.md",
        f"""
# 실험결과 핵심표

## 1. AI4I 2020 baseline

| 모델 | Precision | Recall | F1-score | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|---:|
| Logistic Regression | {logreg.get("precision", "N/A")} | {logreg.get("recall", "N/A")} | {logreg.get("f1_score", "N/A")} | {logreg.get("roc_auc", "N/A")} | {logreg.get("pr_auc", "N/A")} |
| XGBoost | {xgb.get("precision", "N/A")} | {xgb.get("recall", "N/A")} | {xgb.get("f1_score", "N/A")} | {xgb.get("roc_auc", "N/A")} | {xgb.get("pr_auc", "N/A")} |

## 2. Threshold tuning

| 항목 | 값 |
|---|---:|
| 선택 threshold | {selected_threshold} |
| Precision | {selected.get("precision", "N/A")} |
| Recall | {selected.get("recall", "N/A")} |
| F1-score | {selected.get("f1_score", "N/A")} |
| Test failures | {threshold.get("test_failures", "N/A")} |

## 3. 모델 전략/SMOTE 비교

| 전략 | Precision | Recall | F1-score | PR-AUC |
|---|---:|---:|---:|---:|
{model_table}

## 4. SPC-only vs ML+SPC

| 전략 | Precision | Recall | F1-score | Alert count | False positive | False negative |
|---|---:|---:|---:|---:|---:|---:|
{spc_table}

## 5. SCANIA official cost metric

| 전략 | Official cost | Normalized cost | Rule 대비 개선율 |
|---|---:|---:|---:|
| Rule-based threshold | {scania_rule.get("official_cost", "N/A")} | {scania_rule.get("normalized_cost", "N/A")} | 0 |
| XGBoost cost-optimized | {scania_best.get("official_cost", "N/A")} | {scania_best.get("normalized_cost", "N/A")} | {pct(scania_improve)} |

## 해석 주의
SCANIA Component X는 실제 회사의 공개 benchmark 데이터이지만, 여기서 말하는 개선율은 official cost metric 기준의 공개 데이터 검증이다. 회사 현장 원화 비용 절감을 입증한 것처럼 표현하면 안 된다.
""",
    )

    write_packet(
        "05_시스템구현_설명.md",
        f"""
# 시스템 구현 설명

## 1. 입력 데이터와 전처리
기본 학습 데이터는 AI4I 2020 Predictive Maintenance Dataset이다. 목표 변수는 `Machine failure`이며, 모델 학습 시 다음 전처리를 적용한다.

- 제거 컬럼: `UDI`, `Product ID`
- leakage 방지를 위해 제거한 failure-type 컬럼: `TWF`, `HDF`, `PWF`, `OSF`, `RNF`
- 범주형 변수 `Type`은 one-hot encoding 적용
- stratified train/test split 적용
- 평가 데이터는 전체 10,000행 중 test 2,000행

## 2. 예측 모델
Logistic Regression을 baseline으로 두고, XGBoost를 주 모델로 사용한다. XGBoost는 비선형 센서 조합을 반영할 수 있어 AI4I 기준 PR-AUC {xgb.get("pr_auc", "N/A")}를 기록했다.

## 3. Threshold policy
모델 확률을 그대로 사용하는 대신 threshold search를 수행했다. 본 연구에서 선택된 기준은 {selected_threshold}이며, 이때 F1-score는 {selected.get("f1_score", "N/A")}이다.

## 4. Predictive SPC
SPC는 기존 품질관리의 관리도 개념을 예측 확률 시계열에 적용한 구조다. 본 시스템은 위험 확률 흐름, 관리상한/하한, high-risk count를 함께 보여주어 예측 결과가 단일 행 판정에 머물지 않게 한다.

## 5. GenAI 관리자 리포트
Gemini generateContent API를 사용해 예측 context를 관리자 참고 리포트로 변환했다. 리포트는 예측 확률, threshold, 위험 상태, 주요 위험 요인, 권장 조치 방향을 요약한다. 단, 이 리포트는 정비 명령 자동 실행이 아니라 승인형 작업지시 검토를 위한 참고 자료다.

## 6. 승인형 작업지시 workflow
시스템은 센서 이벤트를 생성하고, 작업지시 초안을 만든 뒤, 작업자가 승인/검토/반려 결정을 저장하는 구조다. 실제 장비를 자동으로 제어하지 않는다.

## 7. 제품 구현
- 사용자 앱: PySide6 기반 Windows 데스크톱 앱
- Admin 콘솔: Streamlit 기반 연구/검증 콘솔
- Full 모드: 정밀 분석 모드, XGBoost/SHAP 기반
- Lite 모드: 빠른 점검 모드, 경량 운영 점수 기반
- 설치본: GitHub Release 첨부용, 코드 저장소에는 commit하지 않음
""",
    )

    write_packet(
        "06_GenAI리포트_근거.md",
        (genai_evidence or "# Gemini AI 리포트 검증 근거\n\n근거 파일을 찾지 못했습니다.")
        + """

## 논문 작성 시 넣을 위치
- 4장 시스템 구현: GenAI 관리자 리포트 생성 구조.
- 5장 실험 및 검증: Gemini API 기반 리포트 생성 검증.
- 부록: AI 리포트 원문 또는 축약본.
""",
    )

    write_packet(
        "07_참고문헌_정리.md",
        (references or "# 참고문헌\n\n참고문헌 파일을 찾지 못했습니다.")
        + """

## 본문 인용 위치 제안
- Jardine et al. (2006): 예지보전/CBM 개념 설명.
- Carvalho et al. (2019): ML 기반 예지보전 선행연구 정리.
- Montgomery (2019): SPC, 관리도, UCL/LCL 이론.
- Elkan (2001): cost-sensitive learning과 비용 민감 의사결정.
- AI4I 2020 / Matzka (2020): 기본 실험 데이터 설명.
- Chen & Guestrin (2016): XGBoost 모델 설명.
- Chawla et al. (2002): SMOTE 설명.
- Lundberg & Lee (2017): SHAP 설명가능성.
- SCANIA Component X: 공개 실제 산업 benchmark 검증.
- Gemini generateContent API: GenAI 리포트 생성 구현 근거.
""",
    )

    write_packet(
        "08_가능한주장_금지주장.md",
        """
# 가능한 주장 / 금지 주장

## 가능한 주장

| 구분 | 표현 가능 문장 |
|---|---|
| AI4I 모델 성능 | AI4I 2020 데이터셋에서 XGBoost가 Logistic Regression보다 PR-AUC 기준 높은 성능을 보였다. |
| Threshold tuning | F1 기준 threshold 0.87을 선택해 precision-recall 균형을 조정했다. |
| SPC 결합 | SPC-only와 ML+SPC를 비교해 alert count, false alarm, missed failure trade-off를 분석했다. |
| GenAI 리포트 | Gemini API를 통해 위험 context를 관리자 참고 리포트로 변환하는 기능을 검증했다. |
| 작업지시 | 정비 명령 자동 실행이 아니라 승인형 작업지시 workflow를 구현했다. |
| SCANIA 검증 | SCANIA Component X 공개 benchmark에서 official cost metric 기준 rule baseline 대비 개선 가능성을 확인했다. |
| 현장실증 준비 | 실제 회사 실증을 위해 sensor, maintenance, downtime/cost template을 준비했다. |

## 금지 주장

| 금지 표현 | 이유 |
|---|---|
| PLC/SCADA 운영망 연결을 완료했다는 표현 | 실제 설비망 연결 증거가 없다. |
| 실제 공장 센서 실시간 운영 배포 완료 | 현재는 CSV/로컬/공개 데이터 기반 MVP다. |
| 회사 실제 라벨 데이터로 성능을 최종 확인했다는 표현 | 실제 회사 labeled sensor CSV가 없다. |
| 회사 현장에서 특정 비율의 비용 절감을 입증했다는 표현 | 실제 downtime/cost before-after 로그가 없다. |
| 고장 탐지 시간 85% 단축 실증 완료 | 실제 현장 failure timestamp 기반 before-after 검증이 없다. |
| 정비 명령을 시스템이 자동 실행한다는 표현 | 시스템은 승인형 workflow이며 장비 제어를 하지 않는다. |

## 실제 회사 실증에 필요한 데이터
- 설비 ID
- timestamp
- 센서값
- 실제 고장 여부 또는 고장 class
- 정비 시작/종료 시각
- downtime
- 부품비, 인건비
- 기존 rule 또는 기존 점검 결과
""",
    )

    write_packet(
        "09_그림표_삽입목록.md",
        """
# 그림/표 삽입 목록

## 논문 표 후보

1. AI4I baseline 성능표
   - 근거: `outputs/metrics.json`
   - 내용: Logistic Regression vs XGBoost precision, recall, F1, ROC-AUC, PR-AUC

2. Threshold tuning 결과표
   - 근거: `outputs/threshold_summary.json`
   - 내용: selected threshold 0.87, precision, recall, F1

3. SPC-only vs ML+SPC 비교표
   - 근거: `outputs/spc_vs_ml_comparison.csv`
   - 내용: alert count, false positive, false negative

4. SCANIA official cost metric 비교표
   - 근거: `outputs/scania_official_cost_metrics.json`
   - 내용: rule baseline, XGBoost cost-optimized, official cost, normalized cost

5. GenAI 리포트 검증표
   - 근거: `outputs/genai_report_evidence.md`
   - 내용: report mode, probability, threshold, risk status, main factors

## 논문 그림 후보

1. Confusion matrix: `outputs/confusion_matrix.png`
2. Precision-recall curve: `outputs/pr_curve.png`
3. Threshold tuning plot: `outputs/threshold_tuning.png`
4. SPC risk chart: `outputs/spc_risk_chart.png`
5. SPC control chart: `outputs/spc_control_chart.png`
6. SHAP summary/bar plot: `outputs/shap_summary.png`, `outputs/shap_bar.png`
7. Operational value simulation chart: `outputs/operational_value_simulation.png`
8. SCANIA cost comparison chart: `outputs/scania_official_cost_comparison.png`

## 주의
그림 파일 자체는 이 ChatGPT 자료 패킷 ZIP에 넣지 않는다. 필요하면 별도로 첨부한다.
""",
    )

    write_packet(
        "10_산업공학_설명보조.md",
        """
# 산업공학/운영 가치 설명 보조자료

## OEE, MTBF, MTTR 연결
본 시스템은 OEE, MTBF, MTTR을 실제 현장 로그로 직접 계산한 것은 아니다. 다만 예지보전 시스템이 downtime 감소, 고장 간격 증가, 평균 수리 시간 감소와 연결될 수 있다는 이론적 배경을 설명하는 데 사용할 수 있다. 실제 수치화에는 회사별 downtime, repair start/end, cost log가 필요하다.

## FMEA/RPN 관점
risk priority score는 FMEA의 severity, occurrence, detection 개념과 연결해 설명할 수 있다. calibrated probability는 occurrence에, 데이터 품질 및 탐지 가능성은 detection에, 비용 가중치는 severity에 대응한다. 다만 본 연구의 점수는 전통적 RPN 그대로가 아니라 예측 기반 운영 우선순위 점수다.

## Cost simulation
normalized operating cost는 false alarm과 missed failure에 서로 다른 비용 가중치를 두어 정책을 비교하는 지표다. 실제 원화 비용 절감률이 아니라 운영 정책 비교용 simulation이다.

## 논문 연결 위치
- 2장 이론적 배경: OEE, MTBF, MTTR, FMEA/RPN, SPC.
- 3장 연구 방법: risk priority score와 cost simulation 수식.
- 5장 실험 및 검증: cost simulation 결과와 실제 현장 실증 한계.
""",
    )

    validate_packet()
    create_zip()

    print(f"packet_dir={PACKET}")
    print(f"zip_path={ZIP_PATH}")
    print("files=")
    for path in sorted(PACKET.iterdir()):
        print(f" - {path.name} ({path.stat().st_size} bytes)")
    print(f"zip_size={ZIP_PATH.stat().st_size} bytes")


if __name__ == "__main__":
    main()
