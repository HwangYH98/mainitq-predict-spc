from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Any

os.environ["MAINTIQ_RUNTIME_PROFILE"] = "lite"

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from desktop_app import lite_engine
from desktop_app.config import PRODUCT_NAME
from desktop_app.lite_widgets import LiteBarChart, button_row, card, empty_state, open_folder, set_table
from desktop_app.report_history import append_report_history, read_report_history
from desktop_app.runtime import export_crash_logs, write_error_log
from desktop_app.runtime_profile import profile_note, score_method_label
from desktop_app.update_checker import check_for_update


PROJECT_ROOT = PROJECT_DIR
OUTPUT_DIR = lite_engine.OUTPUT_DIR
DEFAULT_RESULT_PATH = OUTPUT_DIR / "lite_prediction_results.csv"
NAV_LABELS = ["홈", "데이터 예측", "위험 분석", "AI 리포트", "작업지시"]


def show_lite_error(parent: QWidget, title: str, problem: str, action: str) -> None:
    QMessageBox.critical(parent, title, f"문제: {problem}\n\n해야 할 일: {action}")


def stylesheet() -> str:
    return """
        QMainWindow { background: #eef3f8; }
        QWidget { font-family: "Segoe UI", "Malgun Gothic"; font-size: 15px; color: #111827; }
        QScrollArea { background: #f4f7fb; border: 0; }
        QScrollArea > QWidget > QWidget { background: #f4f7fb; }
        #sidebar { background: #071a2e; }
        #brand { color: white; font-size: 29px; font-weight: 800; }
        #subtitle { color: #cbd5e1; font-size: 13px; }
        QPushButton { background: #2563eb; color: white; border: 0; border-radius: 12px; padding: 11px 16px; font-weight: 700; }
        QPushButton:hover { background: #1d4ed8; }
        QPushButton:disabled { background: #b6c3d1; color: #f8fafc; }
        QPushButton#secondary { background: #e8eef7; color: #1e3a5f; border: 1px solid #cad7e8; }
        QPushButton#secondary:hover { background: #dae7f7; }
        QPushButton#nav { text-align: left; background: transparent; border-radius: 14px; padding: 15px 18px; color: #e2e8f0; font-weight: 700; }
        QPushButton#nav:hover { background: #132f4d; }
        QPushButton#nav:checked { background: #2563eb; color: white; }
        QFrame#card, QFrame#emptyState { background: white; border: 1px solid #d8e2ef; border-radius: 16px; }
        QLabel#pageTitle { font-size: 31px; font-weight: 800; color: #071a2e; }
        QLabel#sectionTitle { font-size: 18px; font-weight: 800; }
        QLabel#cardTitle { color: #53657c; font-weight: 700; }
        QLabel#cardValue { font-size: 20px; font-weight: 600; color: #071a2e; }
        QLabel#muted { color: #64748b; }
        QLabel#statusNotice { color: #1e3a5f; background: #eaf3ff; border: 1px solid #bdd7ff; border-radius: 14px; padding: 13px 15px; }
        QLineEdit, QComboBox, QTextEdit, QTableWidget { background: white; border: 1px solid #ccd8e5; border-radius: 10px; padding: 7px; }
        QTableWidget { gridline-color: #e5ecf5; alternate-background-color: #f8fafc; selection-background-color: #dbeafe; selection-color: #0f172a; }
        QHeaderView::section { background: #eef4fb; padding: 8px; border: 1px solid #d8e2ef; font-weight: 700; }
    """


def wrap_page(page: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidget(page)
    return area


class HomePage(QWidget):
    def __init__(self, state: dict[str, Any]) -> None:
        super().__init__()
        self.state = state
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)
        title = QLabel(PRODUCT_NAME)
        title.setObjectName("pageTitle")
        subtitle = QLabel("센서 CSV 기반 위험 점수, AI 리포트, 작업지시 이력을 한 화면에서 관리합니다.")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        workflow = QGridLayout()
        workflow.setSpacing(14)
        workflow.addWidget(card("1. 데이터 불러오기", "센서 CSV 선택", "원본 파일은 앱에 별도로 저장하지 않습니다."), 0, 0)
        workflow.addWidget(card("2. 위험 분석", "점수와 우선순위 확인", "빠른 점검 모드는 경량 운영 점수를 사용합니다."), 0, 1)
        workflow.addWidget(card("3. AI 리포트", "세션 API key 사용", "API key는 파일로 저장하지 않습니다."), 1, 0)
        workflow.addWidget(card("4. 작업지시 기록", "승인, 검토, 반려", "자동 정비 명령은 실행하지 않습니다."), 1, 1)
        layout.addLayout(workflow)

        status = QGridLayout()
        status.setSpacing(14)
        status.addWidget(card("예측 방식", score_method_label(), profile_note()), 0, 0)
        status.addWidget(card("위험 판정 기준", f"{lite_engine.THRESHOLD:.2f}", "운영자가 검토할 기본 기준입니다."), 0, 1)
        status.addWidget(card("고위험 건수", str(self.state.get("high_risk_count", 0)), "현재 세션 결과"), 0, 2)
        status.addWidget(card("로컬 이력", "기록 가능", "센서 이벤트와 작업자 결정을 로컬에 저장합니다."), 0, 3)
        layout.addLayout(status)
        layout.addStretch(1)


class PredictionPage(QWidget):
    def __init__(self, state: dict[str, Any]) -> None:
        super().__init__()
        self.state = state
        self.csv_path: Path | None = None
        self.result: dict[str, Any] | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)
        title = QLabel("데이터 예측")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        intro = QLabel("CSV 선택, 컬럼 확인, 품질 진단, 예측 실행, 결과 저장 순서로 진행합니다.")
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        steps = QGridLayout()
        steps.setSpacing(12)
        for col, (step_title, value, note) in enumerate(
            [
                ("1. CSV 선택", "샘플 또는 회사 CSV", "입력 형식을 먼저 확인합니다."),
                ("2. 컬럼 확인", "자동 매핑 검토", "컬럼 별칭을 자동으로 매핑합니다."),
                ("3. 품질 진단", "결측값과 범위 확인", "입력 데이터의 품질 상태를 표시합니다."),
                ("4. 예측 실행", "위험도 계산", "위험 우선순위를 함께 생성합니다."),
                ("5. 결과 저장", "CSV 내보내기", "분석 결과를 파일로 저장합니다."),
            ]
        ):
            steps.addWidget(card(step_title, value, note), 0, col)
        layout.addLayout(steps)

        self.policy_box = QComboBox()
        self.policy_box.addItems(["균형 정책", "오경보 최소화", "놓친 고장 최소화"])
        self.policy_box.setItemData(0, "balanced")
        self.policy_box.setItemData(1, "precision_first")
        self.policy_box.setItemData(2, "recall_first")
        self.sample_button = QPushButton("샘플 CSV 저장")
        self.use_sample_button = QPushButton("샘플 바로 사용")
        self.load_button = QPushButton("CSV 불러오기")
        self.predict_button = QPushButton("예측 실행")
        self.quick_save_button = QPushButton("기본 위치 저장")
        self.save_button = QPushButton("결과 CSV 저장")
        self.open_button = QPushButton("결과 폴더 열기")
        self.sample_button.setObjectName("secondary")
        self.quick_save_button.setObjectName("secondary")
        self.save_button.setObjectName("secondary")
        self.open_button.setObjectName("secondary")
        self.predict_button.setEnabled(False)
        self.quick_save_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.sample_button.clicked.connect(self.save_sample)
        self.use_sample_button.clicked.connect(self.use_sample)
        self.load_button.clicked.connect(self.load_csv)
        self.predict_button.clicked.connect(self.run_prediction)
        self.quick_save_button.clicked.connect(self.save_result_default)
        self.save_button.clicked.connect(self.save_result)
        self.open_button.clicked.connect(lambda: open_folder(OUTPUT_DIR))
        layout.addWidget(
            button_row(
                self.sample_button,
                self.use_sample_button,
                self.load_button,
                self.policy_box,
                self.predict_button,
                self.quick_save_button,
                self.save_button,
                self.open_button,
            )
        )

        self.status_label = QLabel("CSV를 불러오면 컬럼 확인과 예측 실행이 활성화됩니다.")
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.empty_card = empty_state(
            "분석을 시작하려면 CSV를 선택하세요",
            "샘플 CSV를 바로 사용하거나 회사 센서 CSV를 불러온 뒤 예측 실행을 누르세요. 결과는 요약 카드, 상위 위험 행, 그래프, 표 순서로 표시됩니다.",
        )
        layout.addWidget(self.empty_card)

        self.summary_grid = QGridLayout()
        self.summary_grid.setSpacing(12)
        self.summary_widgets: list[QWidget] = []
        layout.addLayout(self.summary_grid)

        self.chart_label = QLabel("위험도 그래프")
        self.chart_label.setObjectName("sectionTitle")
        self.chart = LiteBarChart()
        layout.addWidget(self.chart_label)
        layout.addWidget(self.chart)
        self.chart_label.setVisible(False)
        self.chart.setVisible(False)

        self.priority_table = QTableWidget()
        self.result_table = QTableWidget()
        self.priority_label = QLabel("상위 위험 행")
        self.result_label = QLabel("예측 결과")
        layout.addWidget(self.priority_label)
        layout.addWidget(self.priority_table)
        layout.addWidget(self.result_label)
        layout.addWidget(self.result_table)
        self.priority_label.setVisible(False)
        self.priority_table.setVisible(False)
        self.result_label.setVisible(False)
        self.result_table.setVisible(False)

    def save_sample(self) -> None:
        sample_path = lite_engine.lite_sample_csv_path()
        target, _ = QFileDialog.getSaveFileName(self, "샘플 CSV 저장", "company_sensor_sample.csv", "CSV Files (*.csv)")
        if not target:
            return
        shutil.copyfile(sample_path, target)
        QMessageBox.information(self, "저장 완료", f"샘플 CSV를 저장했습니다.\n{target}")

    def use_sample(self) -> None:
        self.csv_path = lite_engine.lite_sample_csv_path()
        try:
            _, headers = lite_engine.read_csv_rows(self.csv_path)
            mapping = lite_engine.infer_mapping(headers)
            missing = [name for name, source in mapping.items() if not source]
            if missing:
                self.status_label.setText("필수 컬럼이 없습니다. 샘플 CSV를 확인하세요. 누락: " + ", ".join(missing))
                self.predict_button.setEnabled(False)
                return
            self.status_label.setText("샘플 CSV를 불러왔습니다. 예측 실행을 누르세요.")
            self.predict_button.setEnabled(True)
        except Exception as error:
            show_lite_error(self, "샘플 불러오기 실패", str(error), "샘플 CSV 파일이 배포 폴더에 있는지 확인한 뒤 다시 실행하세요.")

    def load_csv(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(self, "센서 CSV 불러오기", str(PROJECT_ROOT), "CSV Files (*.csv)")
        if not selected:
            return
        self.csv_path = Path(selected)
        try:
            _, headers = lite_engine.read_csv_rows(self.csv_path)
            mapping = lite_engine.infer_mapping(headers)
            missing = [name for name, source in mapping.items() if not source]
            if missing:
                self.status_label.setText("필수 컬럼이 없습니다. 샘플 CSV를 참고해 컬럼명을 맞춰주세요. 누락: " + ", ".join(missing))
            else:
                self.status_label.setText(f"CSV 불러오기 완료: {self.csv_path.name}. 예측을 실행할 수 있습니다.")
            self.predict_button.setEnabled(not missing)
            self.priority_label.setVisible(False)
            self.priority_table.setVisible(False)
            self.result_label.setVisible(False)
            self.result_table.setVisible(False)
        except Exception as error:
            self.predict_button.setEnabled(False)
            show_lite_error(self, "CSV 오류", str(error), "샘플 CSV를 참고해 컬럼명과 숫자 형식을 맞춘 뒤 다시 불러오세요.")

    def clear_summary(self) -> None:
        for widget in self.summary_widgets:
            widget.setParent(None)
        self.summary_widgets.clear()

    def add_summary(self, title: str, value: str, note: str, row: int, column: int) -> None:
        widget = card(title, value, note)
        self.summary_widgets.append(widget)
        self.summary_grid.addWidget(widget, row, column)

    def run_prediction(self) -> None:
        if self.csv_path is None:
            return
        self.predict_button.setEnabled(False)
        self.status_label.setText("경량 운영 점수를 계산하는 중입니다...")
        QApplication.processEvents()
        try:
            policy_id = self.policy_box.currentData() or "balanced"
            self.result = lite_engine.predict_csv(self.csv_path, policy_id=str(policy_id))
            summary = self.result["summary"]
            rows = self.result["rows"]
            self.state["last_prediction_summary"] = summary
            self.state["last_prediction_rows"] = rows
            self.state["high_risk_count"] = summary["high_risk_count"]
            self.clear_summary()
            self.add_summary("처리 행 수", str(summary["row_count"]), "예측 완료", 0, 0)
            self.add_summary("고위험 건수", str(summary["high_risk_count"]), "기준 초과", 0, 1)
            self.add_summary("최고 위험 점수", f"{summary['max_probability']:.3f}", "가장 높은 행", 0, 2)
            self.add_summary("예측 방식", score_method_label(), "정밀 분석 모드 결과와 다를 수 있습니다.", 0, 3)
            for index, row in enumerate(sorted(rows, key=lambda item: float(item["risk_priority_score"]), reverse=True)[:3]):
                self.add_summary(
                    f"상위 위험 row {row['input_row']}",
                    f"점수 {float(row['failure_probability']):.3f}",
                    f"우선순위 {float(row['risk_priority_score']):.2f}",
                    1,
                    index,
                )
            self.chart.set_values([float(row["failure_probability"]) for row in rows])
            self.empty_card.setVisible(False)
            self.chart_label.setVisible(True)
            self.chart.setVisible(True)
            set_table(
                self.priority_table,
                sorted(rows, key=lambda item: float(item["risk_priority_score"]), reverse=True),
                [
                    ("input_row", "행"),
                    ("risk_status", "상태"),
                    ("failure_probability", "위험 점수"),
                    ("risk_priority_score", "우선순위"),
                    ("key_signals", "주요 신호"),
                    ("recommendation", "권장 조치"),
                ],
                limit=20,
            )
            set_table(
                self.result_table,
                rows,
                [
                    ("input_row", "행"),
                    ("Type", "제품 등급"),
                    ("failure_probability", "위험 점수"),
                    ("risk_status", "상태"),
                    ("quality_warnings", "품질 경고"),
                    ("recommendation", "권장 조치"),
                ],
                limit=120,
            )
            self.priority_label.setVisible(True)
            self.priority_table.setVisible(True)
            self.result_label.setVisible(True)
            self.result_table.setVisible(True)
            self.status_label.setText("예측이 완료되었습니다. 필요한 경우 결과 CSV를 저장하세요.")
            self.save_button.setEnabled(True)
            self.quick_save_button.setEnabled(True)
        except Exception as error:
            show_lite_error(self, "예측 실패", str(error), "필수 컬럼, 숫자 형식, 파일 권한을 확인한 뒤 다시 실행하세요.")
            self.status_label.setText("예측에 실패했습니다. 컬럼명과 숫자 형식을 확인하세요.")
        finally:
            self.predict_button.setEnabled(True)

    def save_result_default(self) -> None:
        if self.result is None:
            return
        lite_engine.save_prediction_csv(self.result, DEFAULT_RESULT_PATH)
        self.status_label.setText(f"기본 결과 파일 저장 완료: {DEFAULT_RESULT_PATH}")

    def save_result(self) -> None:
        if self.result is None:
            return
        target, _ = QFileDialog.getSaveFileName(self, "예측 결과 CSV 저장", str(DEFAULT_RESULT_PATH), "CSV Files (*.csv)")
        if not target:
            return
        lite_engine.save_prediction_csv(self.result, Path(target))
        self.status_label.setText(f"결과 저장 완료: {target}")


class MonitoringPage(QWidget):
    def __init__(self, state: dict[str, Any]) -> None:
        super().__init__()
        self.state = state
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)
        title = QLabel("위험 분석")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        self.cards = QGridLayout()
        layout.addLayout(self.cards)
        self.chart = LiteBarChart()
        layout.addWidget(self.chart)
        self.table = QTableWidget()
        layout.addWidget(QLabel("최근 고위험 행"))
        layout.addWidget(self.table)
        refresh = QPushButton("새로고침")
        refresh.setObjectName("secondary")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        self.refresh()

    def refresh(self) -> None:
        rows = self.state.get("last_prediction_rows", [])
        for index in reversed(range(self.cards.count())):
            item = self.cards.itemAt(index)
            if item and item.widget():
                item.widget().setParent(None)
        high = [row for row in rows if row.get("risk_status") == "High Risk"]
        max_probability = max([float(row["failure_probability"]) for row in rows], default=0.0)
        self.cards.addWidget(card("처리 행 수", str(len(rows)), "현재 세션"), 0, 0)
        self.cards.addWidget(card("고위험 건수", str(len(high)), "기준 초과"), 0, 1)
        self.cards.addWidget(card("최고 위험 점수", f"{max_probability:.3f}", "가장 높은 관측 위험"), 0, 2)
        self.cards.addWidget(card("관리 상태", "작업자 검토", "자동 조치는 실행하지 않음"), 0, 3)
        self.chart.set_values([float(row["failure_probability"]) for row in rows])
        set_table(
            self.table,
            sorted(high, key=lambda item: float(item["risk_priority_score"]), reverse=True),
            [
                ("input_row", "행"),
                ("failure_probability", "위험 점수"),
                ("risk_priority_score", "우선순위"),
                ("key_signals", "주요 신호"),
                ("recommendation", "권장 조치"),
            ],
            limit=30,
        )


class AiReportPage(QWidget):
    def __init__(self, state: dict[str, Any]) -> None:
        super().__init__()
        self.state = state
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(14)
        title = QLabel("AI 리포트")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("현재 세션에서 사용할 Gemini 또는 OpenAI API key")
        self.template_box = QComboBox()
        self.template_box.addItems(["운영자용", "관리자용", "정비팀용"])
        self.length_box = QComboBox()
        self.length_box.addItems(["짧게", "표준", "상세"])
        self.status = QLabel("API key는 파일로 저장하지 않습니다.")
        self.status.setObjectName("muted")
        generate = QPushButton("리포트 생성")
        generate.clicked.connect(self.generate_report)
        layout.addWidget(QLabel("세션 API key"))
        layout.addWidget(self.api_key)
        layout.addWidget(QLabel("리포트 템플릿"))
        layout.addWidget(self.template_box)
        layout.addWidget(QLabel("리포트 길이"))
        layout.addWidget(self.length_box)
        layout.addWidget(self.status)
        layout.addWidget(generate)
        self.report_box = QTextEdit()
        self.report_box.setReadOnly(True)
        self.report_box.setPlainText("먼저 예측을 실행한 뒤 운영 참고 리포트를 생성하세요.")
        layout.addWidget(self.report_box)

    def generate_report(self) -> None:
        key = self.api_key.text().strip()
        template = self.template_box.currentText()
        length = self.length_box.currentText()
        if not key:
            append_report_history(
                status="error",
                template=template,
                length=length,
                error_type="missing_api_key",
                error_message="Lite app report generation was requested without an API key.",
            )
            QMessageBox.warning(self, "API key 필요", "현재 세션에서 사용할 Gemini 또는 OpenAI API key를 입력하세요.")
            return
        summary = self.state.get("last_prediction_summary") or {"row_count": 0, "high_risk_count": 0, "max_probability": 0}
        self.status.setText("연결을 확인하고 리포트를 생성하는 중입니다...")
        QApplication.processEvents()
        try:
            text, mode = lite_engine.generate_ai_report(key, summary)
            self.report_box.setPlainText(text)
            self.status.setText("운영 참고 리포트가 생성되었습니다.")
            append_report_history(
                status="success",
                provider=mode.split("_", 1)[0],
                mode="standard",
                model=mode,
                template=template,
                length=length,
                report_text=text,
            )
        except Exception as error:
            append_report_history(status="error", template=template, length=length, error_type="report_generation_failed", error_message=str(error))
            self.status.setText("리포트 생성 실패. API key는 저장하지 않았습니다.")
            QMessageBox.critical(self, "AI 리포트 실패", str(error))


class WorkOrderPage(QWidget):
    def __init__(self, state: dict[str, Any]) -> None:
        super().__init__()
        self.state = state
        self.last_event: dict[str, Any] | None = None
        self.last_draft: dict[str, Any] | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(12)
        title = QLabel("작업지시")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        form = QGridLayout()
        self.inputs: dict[str, QLineEdit | QComboBox] = {}
        fields: list[tuple[str, str, str]] = [
            ("equipment_id", "설비 ID", "EQ-001"),
            ("Air temperature [K]", "공기 온도 [K]", "298.1"),
            ("Process temperature [K]", "공정 온도 [K]", "308.6"),
            ("Rotational speed [rpm]", "회전 속도 [rpm]", "1551"),
            ("Torque [Nm]", "토크 [Nm]", "42.8"),
            ("Tool wear [min]", "공구 마모 [min]", "0"),
        ]
        type_box = QComboBox()
        type_box.addItems(["L", "M", "H"])
        self.inputs["Type"] = type_box
        form.addWidget(QLabel("제품 등급"), 0, 0)
        form.addWidget(type_box, 0, 1)
        for row_index, (key, label, default) in enumerate(fields, start=1):
            edit = QLineEdit(default)
            self.inputs[key] = edit
            form.addWidget(QLabel(label), row_index, 0)
            form.addWidget(edit, row_index, 1)
        layout.addLayout(form)

        normal = QPushButton("정상 샘플")
        high = QPushButton("고위험 샘플")
        self.event_button = QPushButton("센서 이벤트 생성")
        self.draft_button = QPushButton("작업지시 초안 생성")
        normal.setObjectName("secondary")
        self.decision_box = QComboBox()
        self.decision_box.addItems(["승인", "검토 필요", "반려"])
        self.decision_box.setItemData(0, "approve")
        self.decision_box.setItemData(1, "needs_review")
        self.decision_box.setItemData(2, "reject")
        self.note = QLineEdit()
        self.note.setPlaceholderText("결정 메모")
        self.decision_button = QPushButton("결정 저장")
        normal.clicked.connect(lambda: self.fill_sample(False))
        high.clicked.connect(lambda: self.fill_sample(True))
        self.event_button.clicked.connect(self.create_event)
        self.draft_button.clicked.connect(self.create_draft)
        self.decision_button.clicked.connect(self.create_decision)
        layout.addWidget(button_row(normal, high, self.event_button, self.draft_button, self.decision_box, self.note, self.decision_button))
        self.message = QLabel("센서 row를 입력한 뒤 이벤트를 생성하세요.")
        self.message.setObjectName("muted")
        layout.addWidget(self.message)
        self.event_table = QTableWidget()
        self.draft_table = QTableWidget()
        self.decision_table = QTableWidget()
        layout.addWidget(QLabel("최근 센서 이벤트"))
        layout.addWidget(self.event_table)
        layout.addWidget(QLabel("최근 작업지시 초안"))
        layout.addWidget(self.draft_table)
        layout.addWidget(QLabel("최근 결정 이력"))
        layout.addWidget(self.decision_table)
        self.refresh_tables()

    def fill_sample(self, high_risk: bool) -> None:
        values = {
            "Air temperature [K]": "304.8" if high_risk else "298.1",
            "Process temperature [K]": "318.5" if high_risk else "308.6",
            "Rotational speed [rpm]": "1280" if high_risk else "1551",
            "Torque [Nm]": "63.0" if high_risk else "42.8",
            "Tool wear [min]": "235" if high_risk else "0",
        }
        for key, value in values.items():
            widget = self.inputs[key]
            if isinstance(widget, QLineEdit):
                widget.setText(value)

    def sensor_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for key, widget in self.inputs.items():
            payload[key] = widget.currentText() if isinstance(widget, QComboBox) else widget.text()
        return payload

    def create_event(self) -> None:
        try:
            self.last_event = lite_engine.create_event(self.sensor_payload())
            self.message.setText(f"센서 이벤트 생성 완료. 위험 상태: {self.last_event['risk_status']}.")
            self.refresh_tables()
        except Exception as error:
            QMessageBox.critical(self, "이벤트 생성 실패", str(error))

    def create_draft(self) -> None:
        if self.last_event is None:
            QMessageBox.warning(self, "이벤트 필요", "작업지시 초안을 만들기 전에 센서 이벤트를 생성하세요.")
            return
        self.last_draft = lite_engine.create_draft(self.last_event)
        self.message.setText("작업지시 초안 생성 완료.")
        self.refresh_tables()

    def create_decision(self) -> None:
        if self.last_draft is None:
            QMessageBox.warning(self, "초안 필요", "결정을 저장하기 전에 작업지시 초안을 생성하세요.")
            return
        lite_engine.create_decision(self.last_draft, str(self.decision_box.currentData()), self.note.text())
        self.message.setText("작업자 결정 저장 완료.")
        self.refresh_tables()

    def refresh_tables(self) -> None:
        set_table(
            self.event_table,
            lite_engine.list_records("event", 10),
            [("created_at", "생성 시각"), ("equipment_id", "설비"), ("risk_status", "위험 상태"), ("failure_probability", "위험 점수")],
            limit=10,
        )
        set_table(
            self.draft_table,
            lite_engine.list_records("draft", 10),
            [("created_at", "생성 시각"), ("risk_status", "위험 상태"), ("draft_text", "초안")],
            limit=10,
        )
        set_table(
            self.decision_table,
            lite_engine.list_records("decision", 10),
            [("created_at", "생성 시각"), ("decision", "결정"), ("note", "메모")],
            limit=10,
        )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.state: dict[str, Any] = {}
        self.setWindowTitle(f"{PRODUCT_NAME} Lite")
        self.resize(1480, 900)
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(300)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(20, 28, 20, 22)
        side_layout.setSpacing(12)
        brand = QLabel(PRODUCT_NAME)
        brand.setObjectName("brand")
        brand.setWordWrap(True)
        subtitle = QLabel("빠른 점검 모드")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        side_layout.addWidget(brand)
        side_layout.addWidget(subtitle)
        side_layout.addSpacing(28)

        self.page_area = QVBoxLayout()
        page_container = QWidget()
        page_container.setLayout(self.page_area)
        self.pages: list[tuple[str, QWidget]] = [
            (NAV_LABELS[0], HomePage(self.state)),
            (NAV_LABELS[1], PredictionPage(self.state)),
            (NAV_LABELS[2], MonitoringPage(self.state)),
            (NAV_LABELS[3], AiReportPage(self.state)),
            (NAV_LABELS[4], WorkOrderPage(self.state)),
        ]
        self.nav_buttons: list[QPushButton] = []
        for index, (label, _) in enumerate(self.pages):
            button = QPushButton(label)
            button.setObjectName("nav")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self.show_page(i))
            side_layout.addWidget(button)
            self.nav_buttons.append(button)
        side_layout.addStretch(1)
        update_button = QPushButton("업데이트 확인")
        update_button.setObjectName("secondary")
        update_button.clicked.connect(self.check_updates)
        crash_button = QPushButton("오류 로그 내보내기")
        crash_button.setObjectName("secondary")
        crash_button.clicked.connect(self.export_crash_logs)
        side_layout.addWidget(update_button)
        side_layout.addWidget(crash_button)
        footer = QLabel("로컬 세션")
        footer.setObjectName("subtitle")
        side_layout.addWidget(footer)
        root_layout.addWidget(sidebar)
        root_layout.addWidget(page_container, 1)
        self.setCentralWidget(root)
        self.current_page: QWidget | None = None
        self.show_page(0)

    def show_page(self, index: int) -> None:
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)
        if self.current_page is not None:
            self.page_area.removeWidget(self.current_page)
            self.current_page.setParent(None)
        self.current_page = wrap_page(self.pages[index][1])
        self.page_area.addWidget(self.current_page)

    def check_updates(self) -> None:
        result = check_for_update()
        if result.has_update:
            message = (
                f"{result.message}\n\n"
                f"현재 버전: {result.current_version}\n"
                f"최신 버전: {result.latest_version}\n\n"
                "GitHub Release 페이지를 열어 설치파일을 내려받을 수 있습니다."
            )
            answer = QMessageBox.question(
                self,
                "업데이트 확인",
                message,
                QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Close,
            )
            if answer == QMessageBox.StandardButton.Open and result.release_url:
                QDesktopServices.openUrl(QUrl(result.release_url))
            return
        QMessageBox.information(self, "업데이트 확인", result.message)

    def export_crash_logs(self) -> None:
        path = export_crash_logs()
        QMessageBox.information(
            self,
            "오류 로그 내보내기",
            f"오류 로그 ZIP 파일을 만들었습니다.\n{path}\n\n"
            "API key와 비밀번호는 의도적으로 저장하지 않습니다.",
        )


def run_check() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sample = lite_engine.lite_sample_csv_path()
    if not sample.exists():
        raise FileNotFoundError(f"sample CSV was not found: {sample}")
    print(f"{PRODUCT_NAME} Lite check passed.")
    print(f"sample_csv={sample}")
    return 0


def run_engine_smoke_test() -> int:
    result = lite_engine.lite_smoke_test()
    if result["summary"]["row_count"] <= 0:
        raise RuntimeError("Lite smoke test produced no rows.")
    print("Lite engine smoke test passed.")
    print(f"rows={result['summary']['row_count']}")
    print(f"high_risk={result['summary']['high_risk_count']}")
    return 0


def run_workflow_smoke_test() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setStyleSheet(stylesheet())
    window = MainWindow()
    actual_nav = [button.text() for button in window.nav_buttons]
    if actual_nav != NAV_LABELS:
        raise RuntimeError(f"Unexpected Lite navigation labels: {actual_nav}")

    prediction_page = window.pages[1][1]
    if not isinstance(prediction_page, PredictionPage):
        raise RuntimeError("Lite prediction page was not found.")
    prediction_page.csv_path = lite_engine.lite_sample_csv_path()
    prediction_page.predict_button.setEnabled(True)
    prediction_page.run_prediction()
    if not prediction_page.result:
        raise RuntimeError("Lite prediction workflow did not produce a result.")
    if prediction_page.priority_table.rowCount() == 0:
        raise RuntimeError("Lite prediction workflow did not render priority rows.")

    work_order_page = window.pages[4][1]
    if not isinstance(work_order_page, WorkOrderPage):
        raise RuntimeError("Lite work-order page was not found.")
    work_order_page.fill_sample(True)
    work_order_page.create_event()
    if not work_order_page.last_event:
        raise RuntimeError("Lite work-order workflow did not create a sensor event.")
    work_order_page.create_draft()
    if not work_order_page.last_draft:
        raise RuntimeError("Lite work-order workflow did not create a draft.")
    work_order_page.decision_box.setCurrentIndex(1)
    work_order_page.note.setText("lite workflow smoke test")
    work_order_page.create_decision()

    ai_page = window.pages[3][1]
    if not isinstance(ai_page, AiReportPage):
        raise RuntimeError("Lite AI report page was not found.")
    if ai_page.api_key.text().strip():
        raise RuntimeError("Lite AI report key field should be empty during smoke test.")

    append_report_history(
        status="error",
        template="operator",
        length="standard",
        error_type="missing_api_key",
        error_message="lite workflow smoke test",
    )
    if not read_report_history(status_filter="error", limit=5):
        raise RuntimeError("Lite AI report failure history was not recorded.")

    window.close()
    app.processEvents()
    print("Lite GUI workflow smoke test passed.")
    return 0


def run_click_workflow_test() -> int:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setStyleSheet(stylesheet())
    window = MainWindow()
    window.show()
    app.processEvents()

    prediction_page = window.pages[1][1]
    if not isinstance(prediction_page, PredictionPage):
        raise RuntimeError("Lite prediction page was not found.")
    window.show_page(1)
    app.processEvents()
    QTest.mouseClick(prediction_page.use_sample_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    if not prediction_page.predict_button.isEnabled():
        raise RuntimeError("Lite sample click did not enable prediction.")
    QTest.mouseClick(prediction_page.predict_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    if not prediction_page.result:
        raise RuntimeError("Lite prediction click did not produce a result.")
    QTest.mouseClick(prediction_page.quick_save_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    if not DEFAULT_RESULT_PATH.exists():
        raise RuntimeError("Lite result-save click did not create a CSV file.")

    work_order_page = window.pages[4][1]
    if not isinstance(work_order_page, WorkOrderPage):
        raise RuntimeError("Lite work-order page was not found.")
    window.show_page(4)
    app.processEvents()
    work_order_page.fill_sample(True)
    QTest.mouseClick(work_order_page.event_button, Qt.MouseButton.LeftButton)
    if not work_order_page.last_event:
        raise RuntimeError("Lite click workflow did not create a sensor event.")
    QTest.mouseClick(work_order_page.draft_button, Qt.MouseButton.LeftButton)
    if not work_order_page.last_draft:
        raise RuntimeError("Lite click workflow did not create a draft.")
    work_order_page.decision_box.setCurrentIndex(1)
    work_order_page.note.setText("lite click workflow test")
    QTest.mouseClick(work_order_page.decision_button, Qt.MouseButton.LeftButton)

    ai_page = window.pages[3][1]
    if not isinstance(ai_page, AiReportPage):
        raise RuntimeError("Lite AI report page was not found.")
    window.show_page(3)
    app.processEvents()
    if ai_page.api_key.text().strip():
        raise RuntimeError("Lite API key field should be empty during click test.")

    window.close()
    app.processEvents()
    print("Lite GUI click workflow test passed.")
    return 0


def save_screenshot(path: Path) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setStyleSheet(stylesheet())
    window = MainWindow()
    window.show()

    def capture() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        pixmap = QPixmap(window.size())
        window.render(pixmap)
        pixmap.save(str(path))
        window.close()
        app.quit()

    QTimer.singleShot(800, capture)
    return app.exec()


def run_gui() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(stylesheet())
    window = MainWindow()
    window.show()
    return app.exec()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"{PRODUCT_NAME} Lite native desktop app.")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--engine-smoke-test", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--workflow-smoke-test", action="store_true")
    parser.add_argument("--click-workflow-test", action="store_true")
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--export-crash-logs", nargs="?", const="", type=str)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.check:
        return run_check()
    if args.engine_smoke_test or args.smoke_test:
        return run_engine_smoke_test()
    if args.workflow_smoke_test:
        return run_workflow_smoke_test()
    if args.click_workflow_test:
        return run_click_workflow_test()
    if args.screenshot:
        return save_screenshot(args.screenshot)
    if args.export_crash_logs is not None:
        output = Path(args.export_crash_logs) if args.export_crash_logs else None
        zip_path = export_crash_logs(output)
        print(f"Crash logs exported: {zip_path}")
        return 0
    return run_gui()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        write_error_log()
        raise
