from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from desktop_app.config import PRODUCT_NAME
from desktop_app.formatters import status_from_report_mode
from desktop_app.runtime import OUTPUT_DIR, read_json
from desktop_app.runtime_profile import profile_label, profile_note, score_method_label
from desktop_app.widgets import make_card


class HomePage(QWidget):
    def __init__(self, actor: dict) -> None:
        super().__init__()
        self.actor = actor
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(18)
        self.render()

    def render(self) -> None:
        title = QLabel(PRODUCT_NAME)
        title.setObjectName("title")
        subtitle = QLabel("센서 CSV에서 고장 위험을 계산하고, 리포트와 작업지시 의사결정을 한 화면에서 관리합니다.")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("muted")
        self.layout.addWidget(title)
        self.layout.addWidget(subtitle)

        workflow = QGridLayout()
        workflow.setHorizontalSpacing(16)
        workflow.setVerticalSpacing(18)
        cards = [
            ("데이터 업로드", "센서 CSV를 선택해 위험도를 계산합니다.", "컬럼 매핑과 품질 진단을 함께 처리합니다.", "primary"),
            ("위험 분석", "고장 확률과 우선순위를 확인합니다.", "운영 정책에 따라 판정 기준을 조정할 수 있습니다.", "warning"),
            ("AI 리포트", "관리자 참고 리포트를 생성합니다.", "API key는 현재 세션에서만 사용합니다.", "success"),
            ("작업지시", "초안 생성 후 작업자 결정을 기록합니다.", "자동 정비 명령은 실행하지 않습니다.", "subtle"),
        ]
        for index, (card_title, value, note, tone) in enumerate(cards):
            workflow.addWidget(make_card(card_title, value, note, tone=tone), index // 2, index % 2)
        self.layout.addLayout(workflow)

        mode_box = QGroupBox("현재 실행 모드")
        mode_layout = QVBoxLayout(mode_box)
        mode_text = QLabel(
            f"{profile_label()} · {score_method_label()}\n"
            f"{profile_note()}\n"
            "빠른 점검 모드와 정밀 분석 모드는 계산 방식이 달라 결과가 다를 수 있습니다. "
            "보고서나 운영 기록에는 하나의 모드를 일관되게 사용하세요."
        )
        mode_text.setWordWrap(True)
        mode_layout.addWidget(mode_text)
        self.layout.addWidget(mode_box)

        self.status_grid = QGridLayout()
        self.status_grid.setHorizontalSpacing(16)
        self.status_grid.setVerticalSpacing(18)
        self.layout.addLayout(self.status_grid)
        self.refresh_status()

        notice = QGroupBox("사용 전 확인사항")
        notice_layout = QVBoxLayout(notice)
        notice_text = QLabel(
            "실제 설비 적용 전에는 회사 labeled CSV와 정비 이력으로 성능 재평가가 필요합니다.\n"
            "이 앱은 승인형 작업지시를 지원하며 자동 정비 명령을 실행하지 않습니다.\n"
            "API key와 원본 업로드 데이터는 앱 파일로 저장하지 않습니다."
        )
        notice_text.setWordWrap(True)
        notice_layout.addWidget(notice_text)
        self.layout.addWidget(notice)
        self.layout.addStretch()

    def refresh_status(self) -> None:
        threshold = read_json(OUTPUT_DIR / "threshold_summary.json", {}).get("selected_threshold", "N/A")
        spc_summary = read_json(OUTPUT_DIR / "spc_summary.json", {})
        ai_context = read_json(OUTPUT_DIR / "ai_report_context.json", {})
        high_risk = spc_summary.get("high_risk_count", spc_summary.get("risk_summary", {}).get("high_risk_count", "N/A"))
        db_status = "준비됨" if (OUTPUT_DIR / "operations.db").exists() else "새 이력 생성 가능"
        audit_status = "기록 가능"
        try:
            from operations_store import list_audit_logs

            audit_status = f"최근 {len(list_audit_logs(limit=20))}건"
        except Exception:
            pass

        values = [
            ("예측 방식", score_method_label(), profile_label(), "primary"),
            ("위험 판정 기준", str(threshold), "운영 정책에 따라 조정 가능", "default"),
            ("고위험 건수", str(high_risk), "기준 데이터 평가 결과", "warning"),
            ("AI 리포트 상태", status_from_report_mode(str(ai_context.get("report_generation_mode", ""))), "새 리포트는 API key 입력 후 생성", "success"),
            ("운영 이력", db_status, "센서 이벤트와 작업지시 이력 저장", "default"),
            ("감사 로그 상태", audit_status, "주요 조작 이력 기록", "subtle"),
        ]
        for index, (title, value, note, tone) in enumerate(values):
            self.status_grid.addWidget(make_card(title, value, note, tone=tone), index // 3, index % 3)
