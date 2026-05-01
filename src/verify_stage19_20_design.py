from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"
DESIGN_PATH = OUTPUT_DIR / "stage19_20_operations_design.md"

REQUIRED_PHRASES = [
    "Stage 1~20 로컬 통합 PoC 구현 완료",
    "Stage 19 field-event API",
    "Stage 20 operator decision logging",
    "`POST /field-event`",
    "`POST /work-order-decision`",
    "approve",
    "reject",
    "needs_review",
    "PLC/SCADA",
    "MQTT",
    "OPC UA",
    "MES",
    "데이터 계약",
    "SQLite",
    "work_order_decisions.csv",
    "자동 정비 명령으로 연결하지 않는다",
    "실제 PLC/SCADA/클라우드 배포가 아니라",
]

FORBIDDEN_CLAIMS = [
    "실제 공장 연동 완료",
    "클라우드 배포 완료",
    "무인 자동 정비 실행",
    "상용 운영 제품 완성",
    "real-time deployment 완료",
]


def pass_step(message: str) -> None:
    print(f"[OK] {message}")


def require_file(path: Path) -> None:
    if not path.exists():
        raise AssertionError(f"Missing required file: {path}")
    if path.is_file() and path.stat().st_size <= 0:
        raise AssertionError(f"File is empty: {path}")


def verify_stage19_20_design(path: Path = DESIGN_PATH) -> str:
    """Verify the Stage 19~20 design document stays presentation-safe."""
    require_file(path)
    text = path.read_text(encoding="utf-8")

    if "\ufffd" in text:
        raise AssertionError(f"Replacement character found in UTF-8 document: {path}")

    missing_phrases = [phrase for phrase in REQUIRED_PHRASES if phrase not in text]
    if missing_phrases:
        raise AssertionError(
            "stage19_20_operations_design.md is missing required phrases: "
            f"{missing_phrases}"
        )

    forbidden_hits = [phrase for phrase in FORBIDDEN_CLAIMS if phrase in text]
    if forbidden_hits:
        raise AssertionError(
            "stage19_20_operations_design.md contains forbidden production claims: "
            f"{forbidden_hits}"
        )

    pass_step("Stage 19~20 operations design document passed.")
    return text


def main() -> None:
    print(f"Verifying Stage 19~20 operations design at: {PROJECT_ROOT}")
    verify_stage19_20_design()
    print("All Stage 19~20 design checks passed.")


if __name__ == "__main__":
    main()
