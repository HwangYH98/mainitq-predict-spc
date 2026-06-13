from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from desktop_app.ai_report_page import AIReportPage
from desktop_app.config import PRODUCT_NAME, PRODUCT_SUBTITLE, PRODUCT_WINDOW_TITLE
from desktop_app.formatters import default_actor
from desktop_app.home_page import HomePage
from desktop_app.monitoring_page import RiskMonitoringPage
from desktop_app.prediction_page import DataPredictionPage
from desktop_app.runtime import DATA_PATH, OUTPUT_DIR, PROJECT_ROOT, export_crash_logs, now_iso
from desktop_app.update_checker import check_for_update
from desktop_app.widgets import stylesheet
from desktop_app.work_order_page import WorkOrderPage


NAV_LABELS = ["홈", "데이터 예측", "위험 모니터링", "AI 리포트", "작업지시"]


class MainWindow(QMainWindow):
    def __init__(self, actor: dict) -> None:
        super().__init__()
        self.actor = actor
        self.setWindowTitle(PRODUCT_WINDOW_TITLE)
        self.resize(1540, 960)
        self.setMinimumSize(1180, 780)
        self.nav_buttons: list[QPushButton] = []

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(282)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(24, 30, 24, 24)
        sidebar_layout.setSpacing(13)

        product = QLabel(PRODUCT_NAME)
        product.setObjectName("sidebarTitle")
        product.setWordWrap(True)
        subtitle = QLabel(PRODUCT_SUBTITLE)
        subtitle.setObjectName("sidebarSubtitle")
        subtitle.setWordWrap(True)
        sidebar_layout.addWidget(product)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addSpacing(24)

        self.stack = QStackedWidget()
        self.page_instances = {
            "home": HomePage(actor),
            "prediction": DataPredictionPage(actor),
            "monitoring": RiskMonitoringPage(),
            "ai_report": AIReportPage(actor),
            "work_order": WorkOrderPage(actor),
        }
        self.page_order = ["home", "prediction", "monitoring", "ai_report", "work_order"]
        self.page_instances["prediction"].prediction_completed.connect(self.refresh_related_pages)
        self.page_instances["prediction"].monitoring_requested.connect(lambda: self.set_page(2))
        pages = [
            (NAV_LABELS[0], self.page_instances["home"]),
            (NAV_LABELS[1], self.page_instances["prediction"]),
            (NAV_LABELS[2], self.page_instances["monitoring"]),
            (NAV_LABELS[3], self.page_instances["ai_report"]),
            (NAV_LABELS[4], self.page_instances["work_order"]),
        ]
        for index, (label, page) in enumerate(pages):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setObjectName("navButton")
            button.clicked.connect(lambda checked=False, page_index=index: self.set_page(page_index))
            self.nav_buttons.append(button)
            sidebar_layout.addWidget(button)
            self.stack.addWidget(self._wrap_page(page))
        sidebar_layout.addStretch()
        update_button = QPushButton("업데이트 확인")
        update_button.setObjectName("secondaryButton")
        update_button.clicked.connect(self.check_updates)
        crash_button = QPushButton("오류 로그 내보내기")
        crash_button.setObjectName("secondaryButton")
        crash_button.clicked.connect(self.export_crash_logs)
        sidebar_layout.addWidget(update_button)
        sidebar_layout.addWidget(crash_button)
        session_label = QLabel("로컬 워크스테이션 · 운영자 화면")
        session_label.setObjectName("sidebarSubtitle")
        session_label.setWordWrap(True)
        sidebar_layout.addWidget(session_label)

        content = QFrame()
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(34, 30, 34, 30)
        content_layout.setSpacing(16)
        content_layout.addWidget(self.stack)

        root_layout.addWidget(sidebar)
        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)
        self.set_page(0)

    def _wrap_page(self, page: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.setWidget(page)
        return area

    def set_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)
        if 0 <= index < len(self.page_order):
            self.refresh_page(self.page_order[index])

    def refresh_page(self, page_key: str) -> None:
        page = self.page_instances.get(page_key)
        if page_key == "home" and hasattr(page, "refresh"):
            page.refresh()
        elif page_key == "monitoring" and hasattr(page, "render"):
            page.render()
        elif page_key == "ai_report":
            if hasattr(page, "load_saved_report"):
                page.load_saved_report()
            if hasattr(page, "refresh_history"):
                page.refresh_history()
        elif page_key == "work_order" and hasattr(page, "refresh_tables"):
            page.refresh_tables()

    def refresh_related_pages(self) -> None:
        for page_key in ["home", "monitoring", "ai_report", "work_order"]:
            self.refresh_page(page_key)

    def check_updates(self) -> None:
        result = check_for_update()
        if result.has_update:
            message = (
                f"{result.message}\n\n"
                f"현재 버전: {result.current_version}\n"
                f"최신 버전: {result.latest_version}\n\n"
                "GitHub Release 페이지에서 설치파일을 내려받을 수 있습니다."
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
    missing = []
    for path in [DATA_PATH, OUTPUT_DIR]:
        if not path.exists():
            missing.append(str(path))
    if missing:
        print("Desktop app check failed. Missing:")
        for path in missing:
            print(f"- {path}")
        return 1
    print("Desktop app check passed.")
    print(f"project_root: {PROJECT_ROOT}")
    return 0


def run_engine_smoke_test() -> int:
    """Exercise the prediction engines without opening the desktop UI."""
    from preprocessing_prediction_engine import (
        infer_column_mapping,
        predict_company_sensor_csv,
        sample_company_alias_dataframe,
    )
    from realtime_ops import predict_field_event

    sample = sample_company_alias_dataframe()
    mapping_df = infer_column_mapping(sample)
    mapping = dict(zip(mapping_df["canonical_column"], mapping_df["suggested_source_column"]))
    result = predict_company_sensor_csv(sample, mapping=mapping, policy_id="balanced", write_outputs=False)
    if len(result["result_df"]) != len(sample):
        raise RuntimeError("Smart CSV prediction smoke test returned an unexpected row count.")

    event = predict_field_event(
        "EQ-SMOKE",
        now_iso(),
        "desktop_engine_smoke",
        {
            "Type": "M",
            "Air temperature [K]": 298.1,
            "Process temperature [K]": 308.6,
            "Rotational speed [rpm]": 1551,
            "Torque [Nm]": 42.8,
            "Tool wear [min]": 0,
        },
        persist=False,
    )
    if "probability" not in event:
        raise RuntimeError("Realtime field-event smoke test did not return a probability.")
    print("Desktop engine smoke test passed.")
    return 0


def run_workflow_smoke_test() -> int:
    """Run a non-interactive GUI workflow smoke test for the main operator path."""
    from PySide6.QtWidgets import QApplication
    from preprocessing_prediction_engine import infer_column_mapping, sample_company_alias_dataframe

    app = QApplication.instance() or QApplication([])
    window = MainWindow(default_actor())
    actual_nav = [button.text() for button in window.nav_buttons]
    if actual_nav != NAV_LABELS:
        raise RuntimeError(f"Unexpected navigation labels: {actual_nav}")

    prediction_page: DataPredictionPage = window.page_instances["prediction"]  # type: ignore[assignment]
    prediction_page.input_df = sample_company_alias_dataframe()
    prediction_page.detected_schema = "ai4i"
    prediction_page.model_combo.setCurrentIndex(0)
    mapping_df = infer_column_mapping(prediction_page.input_df)
    prediction_page.populate_mapping_table(mapping_df)
    prediction_page.mapping_label.setVisible(True)
    prediction_page.mapping_table.setVisible(True)
    prediction_page.predict_button.setEnabled(True)
    prediction_page.run_prediction()
    if not prediction_page.prediction_result:
        raise RuntimeError("Prediction page did not produce a result.")
    if prediction_page.priority_table.rowCount() == 0:
        raise RuntimeError("Prediction page did not render priority rows.")

    work_order_page: WorkOrderPage = window.page_instances["work_order"]  # type: ignore[assignment]
    work_order_page.apply_preset("high")
    work_order_page.create_event()
    if not work_order_page.latest_event:
        raise RuntimeError("Work-order page did not create a sensor event.")
    work_order_page.create_draft()
    if not work_order_page.latest_draft:
        raise RuntimeError("Work-order page did not create a draft.")
    work_order_page.decision_combo.setCurrentIndex(1)
    work_order_page.note_input.setText("workflow smoke test")
    work_order_page.save_decision()

    ai_page: AIReportPage = window.page_instances["ai_report"]  # type: ignore[assignment]
    if ai_page.generate_button.isEnabled():
        raise RuntimeError("AI report generation should be disabled before an API key is entered.")
    from desktop_app.report_history import append_report_history, read_report_history

    append_report_history(
        status="error",
        template="operator",
        length="standard",
        error_type="missing_api_key",
        error_message="workflow smoke test",
    )
    if not read_report_history(status_filter="error", limit=5):
        raise RuntimeError("AI report failure history was not recorded.")

    window.close()
    app.processEvents()
    print("Desktop GUI workflow smoke test passed.")
    return 0


def run_click_workflow_test() -> int:
    """Exercise the operator workflow through actual QPushButton clicks."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    window = MainWindow(default_actor())
    window.show()
    app.processEvents()

    prediction_page: DataPredictionPage = window.page_instances["prediction"]  # type: ignore[assignment]
    window.set_page(1)
    app.processEvents()
    QTest.mouseClick(prediction_page.use_sample_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    if not prediction_page.predict_button.isEnabled():
        raise RuntimeError("Sample load click did not enable prediction.")
    if not prediction_page.mapping_table.isVisible() or prediction_page.mapping_table.rowCount() < 6:
        raise RuntimeError("Sample load click did not show the column-mapping table.")
    if prediction_page.quick_export_button.isEnabled():
        raise RuntimeError("Default result-save button should stay disabled before prediction.")
    QTest.mouseClick(prediction_page.predict_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    if not prediction_page.prediction_result:
        raise RuntimeError("Prediction click did not produce a result.")
    if prediction_page.mapping_table.isVisible():
        raise RuntimeError("Prediction result should replace the mapping table after a successful run.")
    if not prediction_page.quick_export_button.isEnabled() or not prediction_page.export_button.isEnabled():
        raise RuntimeError("Prediction click did not enable result-save buttons.")
    QTest.mouseClick(prediction_page.quick_export_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    if not prediction_page.last_saved_path or not prediction_page.last_saved_path.exists():
        raise RuntimeError("Default result-save click did not create a CSV file.")
    if prediction_page.last_saved_path.stat().st_size == 0:
        raise RuntimeError("Default result-save click created an empty CSV file.")

    work_order_page: WorkOrderPage = window.page_instances["work_order"]  # type: ignore[assignment]
    window.set_page(4)
    app.processEvents()
    QTest.mouseClick(work_order_page.high_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(work_order_page.event_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    if not work_order_page.latest_event:
        raise RuntimeError("Sensor-event click did not create an event.")
    QTest.mouseClick(work_order_page.draft_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    if not work_order_page.latest_draft:
        raise RuntimeError("Draft click did not create a work-order draft.")
    work_order_page.decision_combo.setCurrentIndex(1)
    work_order_page.note_input.setText("click workflow test")
    QTest.mouseClick(work_order_page.decision_button, Qt.MouseButton.LeftButton)
    app.processEvents()

    ai_page: AIReportPage = window.page_instances["ai_report"]  # type: ignore[assignment]
    window.set_page(3)
    app.processEvents()
    if ai_page.generate_button.isEnabled():
        raise RuntimeError("AI report button should stay disabled without an API key.")

    window.close()
    app.processEvents()
    print("Desktop GUI click workflow test passed.")
    return 0
