from __future__ import annotations

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from desktop_app.formatters import humanize_status, set_display_table
from desktop_app.runtime import now_iso
from desktop_app.widgets import make_card, record_audit, show_error


class WorkOrderPage(QWidget):
    def __init__(self, actor: dict) -> None:
        super().__init__()
        self.actor = actor
        self.latest_event: dict | None = None
        self.latest_draft: dict | None = None
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        title = QLabel("작업지시")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        intro = QLabel("단일 설비의 센서 row를 입력해 위험 이벤트를 만들고, 작업지시 초안과 작업자 결정을 기록합니다.")
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        steps = QGridLayout()
        steps.setHorizontalSpacing(14)
        steps.setVerticalSpacing(14)
        for index, (title_text, value, note, tone) in enumerate(
            [
                ("1. 센서 입력", "단일 설비 row", "설비 ID와 센서값을 확인합니다.", "primary"),
                ("2. 이벤트 생성", "위험도 계산", "입력 row를 예측 이벤트로 기록합니다.", "warning"),
                ("3. 초안 생성", "작업지시 제안", "자동 실행이 아니라 검토용 초안을 만듭니다.", "subtle"),
                ("4. 작업자 결정", "승인 / 검토 / 반려", "작업자 판단을 이력으로 남깁니다.", "success"),
            ]
        ):
            steps.addWidget(make_card(title_text, value, note, tone=tone), index // 4, index % 4)
        layout.addLayout(steps)

        self.form = QFormLayout()
        self.equipment_input = QLineEdit("EQ-001")
        self.timestamp_input = QLineEdit(now_iso())
        self.type_combo = QComboBox()
        self.type_combo.addItems(["L", "M", "H"])
        self.air_temp = QDoubleSpinBox()
        self.process_temp = QDoubleSpinBox()
        self.speed = QSpinBox()
        self.torque = QDoubleSpinBox()
        self.wear = QSpinBox()
        for spin, minimum, maximum, value in [
            (self.air_temp, 250, 400, 298.1),
            (self.process_temp, 250, 450, 308.6),
            (self.torque, 0, 150, 42.8),
        ]:
            spin.setRange(minimum, maximum)
            spin.setValue(value)
            spin.setDecimals(2)
        self.speed.setRange(0, 10000)
        self.speed.setValue(1551)
        self.wear.setRange(0, 100000)
        self.wear.setValue(0)
        self.form.addRow("설비 ID", self.equipment_input)
        self.form.addRow("이벤트 시각", self.timestamp_input)
        self.form.addRow("제품 등급", self.type_combo)
        self.form.addRow("공기 온도 [K]", self.air_temp)
        self.form.addRow("공정 온도 [K]", self.process_temp)
        self.form.addRow("회전 속도 [rpm]", self.speed)
        self.form.addRow("토크 [Nm]", self.torque)
        self.form.addRow("공구 마모 [min]", self.wear)
        layout.addLayout(self.form)

        preset_buttons = QHBoxLayout()
        self.normal_button = QPushButton("정상 샘플")
        self.high_button = QPushButton("고위험 샘플")
        self.normal_button.setObjectName("secondaryButton")
        self.high_button.setObjectName("dangerButton")
        self.normal_button.clicked.connect(lambda: self.apply_preset("normal"))
        self.high_button.clicked.connect(lambda: self.apply_preset("high"))
        preset_buttons.addWidget(self.normal_button)
        preset_buttons.addWidget(self.high_button)
        preset_buttons.addStretch()
        layout.addLayout(preset_buttons)

        action_buttons = QHBoxLayout()
        self.event_button = QPushButton("센서 이벤트 생성")
        self.draft_button = QPushButton("작업지시 초안 생성")
        self.event_button.setObjectName("successButton")
        self.draft_button.setObjectName("successButton")
        self.decision_button = QPushButton("결정 저장")
        self.decision_button.setObjectName("successButton")
        self.event_button.clicked.connect(self.create_event)
        self.draft_button.clicked.connect(self.create_draft)
        self.decision_button.clicked.connect(self.save_decision)
        self.decision_combo = QComboBox()
        self.decision_combo.addItem("승인", "approve")
        self.decision_combo.addItem("검토 필요", "needs_review")
        self.decision_combo.addItem("반려", "reject")
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("결정 메모")
        action_buttons.addWidget(self.event_button)
        action_buttons.addWidget(self.draft_button)
        action_buttons.addWidget(QLabel("작업자 결정"))
        action_buttons.addWidget(self.decision_combo)
        action_buttons.addWidget(self.note_input)
        action_buttons.addWidget(self.decision_button)
        layout.addLayout(action_buttons)

        self.result_label = QLabel("센서 row를 입력한 뒤 이벤트를 생성하세요.")
        self.result_label.setWordWrap(True)
        self.result_label.setObjectName("statusNotice")
        layout.addWidget(self.result_label)

        self.events_table = QTableWidget()
        self.drafts_table = QTableWidget()
        self.decisions_table = QTableWidget()
        for table in [self.events_table, self.drafts_table, self.decisions_table]:
            table.setAlternatingRowColors(True)
            table.setMinimumHeight(110)
            table.setMaximumHeight(150)
        layout.addWidget(QLabel("최근 센서 이벤트"))
        layout.addWidget(self.events_table)
        layout.addWidget(QLabel("최근 작업지시 초안"))
        layout.addWidget(self.drafts_table)
        layout.addWidget(QLabel("최근 결정 이력"))
        layout.addWidget(self.decisions_table)
        self.refresh_tables()

    def apply_preset(self, preset: str) -> None:
        if preset == "high":
            self.type_combo.setCurrentText("L")
            self.air_temp.setValue(303.8)
            self.process_temp.setValue(313.2)
            self.speed.setValue(1350)
            self.torque.setValue(62.0)
            self.wear.setValue(210)
        else:
            self.type_combo.setCurrentText("M")
            self.air_temp.setValue(298.1)
            self.process_temp.setValue(308.6)
            self.speed.setValue(1551)
            self.torque.setValue(42.8)
            self.wear.setValue(0)
        self.timestamp_input.setText(now_iso())

    def sensor_row(self) -> dict:
        return {
            "Type": self.type_combo.currentText(),
            "Air temperature [K]": self.air_temp.value(),
            "Process temperature [K]": self.process_temp.value(),
            "Rotational speed [rpm]": self.speed.value(),
            "Torque [Nm]": self.torque.value(),
            "Tool wear [min]": self.wear.value(),
        }

    def create_event(self) -> None:
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            from realtime_ops import predict_field_event

            self.latest_event = predict_field_event(
                self.equipment_input.text().strip(),
                self.timestamp_input.text().strip(),
                "MaintiQ Predict",
                self.sensor_row(),
                persist=True,
            )
            QApplication.restoreOverrideCursor()
            self.result_label.setText(
                f"센서 이벤트 생성 완료: 위험 상태 {humanize_status(self.latest_event['risk_status'])}, "
                f"고장 확률 {self.latest_event['probability']:.3f}"
            )
            record_audit(self.actor, "desktop_field_event_created", "success", "event", self.latest_event["event_id"])
            self.refresh_tables()
        except Exception as error:
            QApplication.restoreOverrideCursor()
            record_audit(self.actor, "desktop_field_event_created", "error", "event", "", error_message=str(error))
            show_error(self, "센서 이벤트 생성 실패", error)

    def create_draft(self) -> None:
        if not self.latest_event:
            QMessageBox.warning(self, "이벤트 필요", "먼저 센서 이벤트를 생성하세요.")
            return
        try:
            from realtime_ops import create_work_order_draft

            self.latest_draft = create_work_order_draft(self.latest_event)
            self.result_label.setText("작업지시 초안 생성 완료")
            record_audit(self.actor, "desktop_work_order_draft_created", "success", "draft", self.latest_draft["draft_id"])
            self.refresh_tables()
        except Exception as error:
            record_audit(self.actor, "desktop_work_order_draft_created", "error", "draft", "", error_message=str(error))
            show_error(self, "작업지시 초안 생성 실패", error)

    def save_decision(self) -> None:
        if not self.latest_draft:
            QMessageBox.warning(self, "초안 필요", "먼저 작업지시 초안을 생성하세요.")
            return
        try:
            from realtime_ops import create_work_order_decision

            decision = create_work_order_decision(
                self.latest_draft["draft_id"],
                str(self.decision_combo.currentData()),
                operator_id=self.actor.get("actor_id", "operator"),
                note=self.note_input.text().strip(),
            )
            self.result_label.setText(f"작업자 결정 저장 완료: {humanize_status(decision['decision'])}")
            record_audit(self.actor, "desktop_work_order_decision_saved", "success", "decision", decision["decision_id"])
            self.refresh_tables()
        except Exception as error:
            record_audit(self.actor, "desktop_work_order_decision_saved", "error", "decision", "", error_message=str(error))
            show_error(self, "결정 저장 실패", error)

    def refresh_tables(self) -> None:
        try:
            from operations_store import list_prediction_events, list_work_order_decisions, list_work_order_drafts

            events = pd.DataFrame(list_prediction_events(limit=10))
            drafts = pd.DataFrame(list_work_order_drafts(limit=10))
            decisions = pd.DataFrame(list_work_order_decisions(limit=10))
            set_display_table(self.events_table, events, ["created_at", "probability", "risk_status"], max_rows=10)
            set_display_table(self.drafts_table, drafts, ["created_at", "generation_mode"], max_rows=10)
            set_display_table(self.decisions_table, decisions, ["created_at", "decision", "note"], max_rows=10)
        except Exception:
            pass
