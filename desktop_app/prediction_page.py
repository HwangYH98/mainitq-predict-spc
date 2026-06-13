from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop_app.formatters import set_display_table
from desktop_app.runtime import OUTPUT_DIR, PROJECT_ROOT
from desktop_app.runtime_profile import profile_label, score_method_label
from desktop_app.widgets import ChartBox, make_card, record_audit, show_error


MODEL_AUTO = "auto"
MODEL_AI4I = "ai4i"
MODEL_SCANIA = "scania"


def detect_public_benchmark_csv(df: pd.DataFrame) -> str:
    """Identify raw research benchmark files that are not product upload rows."""
    columns = [str(column).strip() for column in df.columns]
    normalized = {column.lower().replace(" ", "_") for column in columns}
    if "vehicle_id" in normalized:
        scania_metadata = (
            {"class_label", "length_of_study_time_step", "in_study_repair"} & normalized
        )
        scania_spec_columns = [column for column in normalized if column.startswith("spec_")]
        if scania_metadata or scania_spec_columns:
            return "SCANIA Component X benchmark metadata/specification file"

    metropt_hits = {"tp2", "tp3", "oil_temperature", "motor_current", "caudal_impulses"} & normalized
    if len(metropt_hits) >= 2:
        return "MetroPT-3 compressor benchmark"

    numeric_header_count = 0
    for column in columns:
        try:
            float(column)
            numeric_header_count += 1
        except ValueError:
            pass
    if len(columns) == 6 and numeric_header_count >= 4:
        return "FEMTO/PRONOSTIA bearing benchmark"

    return ""


class DataPredictionPage(QWidget):
    prediction_completed = Signal()
    monitoring_requested = Signal()

    def __init__(self, actor: dict) -> None:
        super().__init__()
        self.actor = actor
        self.input_df: pd.DataFrame | None = None
        self.prediction_result: dict | None = None
        self.current_csv_path: Path | None = None
        self.detected_schema: str = MODEL_AI4I
        self.mapping_widgets: dict[str, QComboBox] = {}
        self.unit_widgets: dict[str, QComboBox] = {}
        self.last_saved_path: Path | None = None
        self.step_cards: list[QWidget] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        title = QLabel("데이터 예측")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        intro = QLabel(
            "회사 센서 CSV 또는 SCANIA Component X 형식 CSV를 불러오면 스키마를 확인하고 위험도를 계산합니다. "
            f"현재 실행 모드: {profile_label()} · {score_method_label()}"
        )
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        steps = QGridLayout()
        steps.setHorizontalSpacing(14)
        steps.setVerticalSpacing(14)
        for title_text, value, note, tone in [
            ("1. CSV 선택", "샘플 또는 회사 CSV", "처음 사용 시 샘플로 형식을 확인하세요.", "primary"),
            ("2. 컬럼 확인", "자동 스키마 감지", "AI4I형은 컬럼 매핑, SCANIA형은 전용 스키마를 사용합니다.", "subtle"),
            ("3. 품질 진단", "누락/형식 확인", "예측 전 데이터 품질을 확인합니다.", "subtle"),
            ("4. 예측 실행", "위험도 계산", "확률 그래프와 우선순위를 확인합니다.", "subtle"),
            ("5. 결과 저장", "CSV 내보내기", "분석 결과를 파일로 저장할 수 있습니다.", "subtle"),
        ]:
            index = steps.count()
            step_card = make_card(title_text, value, note, tone=tone)
            self.step_cards.append(step_card)
            steps.addWidget(step_card, index // 3, index % 3)
        layout.addLayout(steps)

        controls = QGridLayout()
        controls.setHorizontalSpacing(10)
        controls.setVerticalSpacing(10)
        self.sample_button = QPushButton("샘플 저장")
        self.use_sample_button = QPushButton("샘플 사용")
        self.load_button = QPushButton("CSV 불러오기")
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(210)
        self.model_combo.addItem("자동 감지", MODEL_AUTO)
        self.model_combo.addItem("기본 센서 모델", MODEL_AI4I)
        self.model_combo.addItem("SCANIA 비용 모델", MODEL_SCANIA)
        self.model_combo.currentIndexChanged.connect(self.on_model_selection_changed)
        self.policy_combo = QComboBox()
        self.policy_combo.setMinimumWidth(180)
        self.policy_combo.addItem("균형 정책", "balanced")
        self.policy_combo.addItem("오경보 최소화", "precision_first")
        self.policy_combo.addItem("놓친 고장 최소화", "recall_first")
        self.predict_button = QPushButton("예측 실행")
        self.quick_export_button = QPushButton("기본 위치 저장")
        self.export_button = QPushButton("결과 CSV 저장")
        self.open_folder_button = QPushButton("저장 폴더 열기")
        self.open_monitoring_button = QPushButton("위험 모니터링으로 이동")
        self.sample_button.setObjectName("secondaryButton")
        self.use_sample_button.setObjectName("successButton")
        self.load_button.setObjectName("successButton")
        self.predict_button.setObjectName("successButton")
        self.quick_export_button.setObjectName("secondaryButton")
        self.export_button.setObjectName("secondaryButton")
        self.open_folder_button.setObjectName("secondaryButton")
        self.open_monitoring_button.setObjectName("successButton")
        self.predict_button.setEnabled(False)
        self.quick_export_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.open_folder_button.setEnabled(False)
        self.open_monitoring_button.setEnabled(False)
        self.sample_button.clicked.connect(self.save_sample_csv)
        self.use_sample_button.clicked.connect(self.use_sample_csv)
        self.load_button.clicked.connect(self.load_csv)
        self.predict_button.clicked.connect(self.run_prediction)
        self.quick_export_button.clicked.connect(self.export_results_to_default)
        self.export_button.clicked.connect(self.export_results)
        self.open_folder_button.clicked.connect(self.open_saved_folder)
        self.open_monitoring_button.clicked.connect(self.monitoring_requested.emit)
        controls.addWidget(self.sample_button, 0, 0)
        controls.addWidget(self.use_sample_button, 0, 1)
        controls.addWidget(self.load_button, 0, 2)
        controls.addWidget(QLabel("예측 모델"), 0, 3)
        controls.addWidget(self.model_combo, 0, 4)
        controls.addWidget(QLabel("운영 정책"), 0, 5)
        controls.addWidget(self.policy_combo, 0, 6)
        controls.addWidget(self.predict_button, 1, 0)
        controls.addWidget(self.quick_export_button, 1, 1)
        controls.addWidget(self.export_button, 1, 2)
        controls.addWidget(self.open_folder_button, 1, 3)
        controls.addWidget(self.open_monitoring_button, 1, 4)
        controls.setColumnStretch(7, 1)
        layout.addLayout(controls)

        self.message_label = QLabel(
            "처음이면 '샘플 사용'으로 흐름을 확인하세요. CSV를 불러오면 컬럼 확인 뒤 예측 실행이 활성화됩니다."
        )
        self.message_label.setWordWrap(True)
        self.message_label.setObjectName("statusNotice")
        layout.addWidget(self.message_label)

        self.workflow_status_label = QLabel(
            "현재 상태: CSV 대기 · 비활성 버튼은 입력 또는 예측 결과가 생기면 자동으로 켜집니다."
        )
        self.workflow_status_label.setObjectName("muted")
        self.workflow_status_label.setWordWrap(True)
        layout.addWidget(self.workflow_status_label)

        self.empty_state = make_card(
            "분석 대기",
            "CSV를 먼저 선택하세요",
            "AI4I형 센서 CSV는 컬럼 매핑 후 예측하고, SCANIA형 CSV는 전용 비용 최적화 모델로 예측합니다.",
            tone="subtle",
        )
        layout.addWidget(self.empty_state)

        self.mapping_label = QLabel("컬럼 확인")
        self.mapping_table = QTableWidget()
        self.mapping_table.setAlternatingRowColors(True)
        self.mapping_table.setMinimumHeight(150)
        self.mapping_table.setMaximumHeight(190)
        layout.addWidget(self.mapping_label)
        layout.addWidget(self.mapping_table)
        self.mapping_label.setVisible(False)
        self.mapping_table.setVisible(False)

        self.summary_grid = QGridLayout()
        self.summary_grid.setHorizontalSpacing(14)
        self.summary_grid.setVerticalSpacing(18)
        layout.addLayout(self.summary_grid)

        self.chart = ChartBox()
        layout.addWidget(self.chart)
        self.chart.setVisible(False)

        self.priority_label = QLabel("위험 우선순위")
        self.priority_table = QTableWidget()
        self.priority_table.setAlternatingRowColors(True)
        self.priority_table.setMinimumHeight(160)
        self.result_label = QLabel("예측 결과")
        self.result_table = QTableWidget()
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setMinimumHeight(190)
        self.output_hint_label = QLabel("")
        self.output_hint_label.setObjectName("muted")
        self.output_hint_label.setWordWrap(True)
        for widget in [self.priority_label, self.priority_table, self.result_label, self.result_table, self.output_hint_label]:
            layout.addWidget(widget)
            widget.setVisible(False)

    def selected_model(self) -> str:
        selected = str(self.model_combo.currentData())
        if self.detected_schema == MODEL_SCANIA:
            return MODEL_SCANIA
        if selected == MODEL_AUTO:
            return self.detected_schema
        return selected

    def on_model_selection_changed(self) -> None:
        if self.input_df is not None:
            self.configure_schema_ui()

    def save_sample_csv(self) -> None:
        selected = str(self.model_combo.currentData())
        if selected == MODEL_SCANIA:
            default_name = "sample_scania_component_x.csv"
        else:
            default_name = "sample_company_sensor.csv"
        path, _ = QFileDialog.getSaveFileName(self, "샘플 CSV 저장", str(PROJECT_ROOT / default_name), "CSV Files (*.csv)")
        if not path:
            return
        try:
            if selected == MODEL_SCANIA:
                from scania_product_engine import sample_scania_dataframe

                sample_scania_dataframe().to_csv(path, index=False, encoding="utf-8-sig")
            else:
                from preprocessing_prediction_engine import sample_company_alias_dataframe

                sample_company_alias_dataframe().to_csv(path, index=False, encoding="utf-8-sig")
            QMessageBox.information(self, "저장 완료", f"샘플 CSV를 저장했습니다.\n{path}")
        except Exception as error:
            show_error(self, "샘플 저장 실패", error)

    def use_sample_csv(self) -> None:
        """Load a built-in sample without opening a file dialog.

        This is mainly for first-run usability and automated click-flow tests.
        The sample is kept in memory until the operator explicitly saves results.
        """
        try:
            selected = str(self.model_combo.currentData())
            if selected == MODEL_SCANIA:
                from scania_product_engine import sample_scania_dataframe

                self.input_df = sample_scania_dataframe()
                self.detected_schema = MODEL_SCANIA
            else:
                from preprocessing_prediction_engine import sample_company_alias_dataframe

                self.input_df = sample_company_alias_dataframe()
                self.detected_schema = MODEL_AI4I
            self.current_csv_path = None
            for card in self.step_cards:
                card.setVisible(True)
            self.configure_schema_ui()
            self.empty_state.setVisible(False)
            self.predict_button.setEnabled(True)
            self.open_monitoring_button.setEnabled(False)
            self.message_label.setText("샘플 CSV를 불러왔습니다. 컬럼 확인 후 예측 실행을 누르세요.")
            self.workflow_status_label.setText(
                f"현재 상태: 샘플 데이터 준비 완료 · {len(self.input_df)}개 행, {len(self.input_df.columns)}개 컬럼 · 다음 행동: 예측 실행"
            )
            record_audit(
                self.actor,
                "desktop_sample_loaded",
                "success",
                "csv",
                self.schema_label(self.detected_schema),
                {"rows": len(self.input_df), "schema": self.detected_schema},
            )
        except Exception as error:
            record_audit(self.actor, "desktop_sample_loaded", "error", "csv", "", error_message=str(error))
            show_error(self, "샘플 불러오기 실패", error)

    def load_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "센서 CSV 선택", str(PROJECT_ROOT), "CSV Files (*.csv)")
        if not path:
            return
        try:
            self.input_df = pd.read_csv(path)
            self.current_csv_path = Path(path)
            public_benchmark = detect_public_benchmark_csv(self.input_df)
            if public_benchmark:
                self.input_df = None
                self.current_csv_path = None
                self.detected_schema = MODEL_AI4I
                self.predict_button.setEnabled(False)
                self.open_monitoring_button.setEnabled(False)
                self.mapping_label.setVisible(False)
                self.mapping_table.setVisible(False)
                self.empty_state.setVisible(True)
                message = (
                    f"문제: {public_benchmark} 원본 CSV는 제품 예측 업로드 형식이 아닙니다.\n"
                    "원인 후보: spec/label/tte 또는 공개 벤치마크 원본 파일을 운영 예측 화면에 넣었습니다.\n"
                    "해결 방법: 기본 센서 CSV 또는 SCANIA readout CSV를 사용하고, 공개 데이터 검증은 Admin 콘솔에서 실행하세요."
                )
                self.message_label.setText(message)
                self.workflow_status_label.setText("제품 예측에는 기본 센서 CSV 또는 SCANIA readout CSV를 사용하세요.")
                QMessageBox.warning(self, "제품 업로드에서 지원하지 않는 CSV", message)
                record_audit(self.actor, "desktop_csv_loaded", "blocked", "csv", Path(path).name, {"reason": public_benchmark})
                return
            for card in self.step_cards:
                card.setVisible(True)
            from scania_product_engine import detect_input_schema

            self.detected_schema = detect_input_schema(self.input_df)
            self.configure_schema_ui()
            self.empty_state.setVisible(False)
            self.predict_button.setEnabled(True)
            self.open_monitoring_button.setEnabled(False)
            self.message_label.setText(
                f"CSV를 불러왔습니다: {Path(path).name}. 감지된 형식: {self.schema_label(self.detected_schema)}. 예측을 실행하세요."
            )
            self.workflow_status_label.setText(
                f"현재 상태: 컬럼 확인 완료 · {len(self.input_df)}개 행, {len(self.input_df.columns)}개 컬럼 · 다음 행동: 예측 실행"
            )
            record_audit(self.actor, "desktop_csv_loaded", "success", "csv", Path(path).name, {"rows": len(self.input_df), "schema": self.detected_schema})
        except Exception as error:
            record_audit(self.actor, "desktop_csv_loaded", "error", "csv", Path(path).name, error_message=str(error))
            self.message_label.setText(
                "문제: CSV 파일을 읽지 못했습니다.\n"
                "원인 후보: 파일 인코딩, 비어 있는 CSV, 깨진 구분자, 숫자 컬럼의 잘못된 값.\n"
                "해결 방법: 샘플 CSV 형식과 컬럼명을 맞춘 뒤 다시 불러오세요."
            )
            show_error(self, "CSV 불러오기 실패", error)

    def schema_label(self, schema: str) -> str:
        return "SCANIA Component X" if schema == MODEL_SCANIA else "AI4I 센서 CSV"

    def configure_schema_ui(self) -> None:
        if self.input_df is None:
            return
        selected = self.selected_model()
        if selected == MODEL_SCANIA:
            self.mapping_label.setVisible(True)
            self.mapping_label.setText("SCANIA 스키마 확인")
            preview = pd.DataFrame(
                [
                    {"항목": "감지 결과", "값": "SCANIA Component X 형식"},
                    {"항목": "필수 컬럼", "값": "vehicle_id, time_step, 익명화 센서 컬럼"},
                    {"항목": "처리 방식", "값": "차량별 마지막 readout을 사용해 class 0~4를 예측"},
                ]
            )
            set_display_table(self.mapping_table, preview, max_rows=10)
            self.mapping_table.setVisible(True)
            return

        from preprocessing_prediction_engine import infer_column_mapping

        mapping_df = infer_column_mapping(self.input_df)
        self.populate_mapping_table(mapping_df)
        self.mapping_label.setText("컬럼 확인")
        self.mapping_label.setVisible(True)
        self.mapping_table.setVisible(True)

    def populate_mapping_table(self, mapping_df: pd.DataFrame) -> None:
        if self.input_df is None:
            return
        self.mapping_widgets.clear()
        self.unit_widgets.clear()
        source_columns = [""] + [str(column) for column in self.input_df.columns]
        unit_options = ["Auto", "No conversion", "Celsius -> Kelvin", "Seconds -> Minutes", "Percent -> Ratio"]
        self.mapping_table.clear()
        self.mapping_table.setRowCount(len(mapping_df))
        self.mapping_table.setColumnCount(3)
        self.mapping_table.setHorizontalHeaderLabels(["기준 컬럼", "CSV 컬럼", "단위 처리"])
        for row_index, row in mapping_df.iterrows():
            canonical = str(row["canonical_column"])
            self.mapping_table.setItem(row_index, 0, QTableWidgetItem(canonical))
            source_combo = QComboBox()
            source_combo.addItems(source_columns)
            suggested = str(row.get("suggested_source_column", ""))
            if suggested in source_columns:
                source_combo.setCurrentText(suggested)
            unit_combo = QComboBox()
            unit_combo.addItems(unit_options)
            unit_combo.setCurrentText("Auto" if "temperature" in canonical.lower() else "No conversion")
            self.mapping_widgets[canonical] = source_combo
            self.unit_widgets[canonical] = unit_combo
            self.mapping_table.setCellWidget(row_index, 1, source_combo)
            self.mapping_table.setCellWidget(row_index, 2, unit_combo)
        self.mapping_table.resizeColumnsToContents()

    def collect_mapping(self) -> tuple[dict[str, str], dict[str, str]]:
        mapping = {column: widget.currentText().strip() for column, widget in self.mapping_widgets.items()}
        units = {column: widget.currentText().strip() for column, widget in self.unit_widgets.items()}
        missing = [column for column, source in mapping.items() if not source and column != "Type"]
        if missing:
            raise ValueError("필수 컬럼이 없습니다. 샘플 CSV를 참고해 컬럼명을 맞춰주세요. 누락: " + ", ".join(missing))
        return mapping, units

    def run_prediction(self) -> None:
        if self.input_df is None:
            QMessageBox.warning(self, "CSV 필요", "먼저 샘플을 사용하거나 CSV를 불러오세요.")
            return
        cursor_active = False
        selected = self.selected_model()
        try:
            self.empty_state.setVisible(False)
            self.message_label.setText("예측 실행 중입니다. 데이터 품질 진단, 위험 확률 계산, 우선순위 정렬을 처리하고 있습니다...")
            QApplication.processEvents()
            QApplication.setOverrideCursor(Qt.WaitCursor)
            cursor_active = True
            if selected == MODEL_SCANIA:
                from scania_product_engine import predict_scania_csv

                self.prediction_result = predict_scania_csv(self.input_df, write_outputs=True)
            else:
                mapping, units = self.collect_mapping()
                from preprocessing_prediction_engine import predict_company_sensor_csv

                self.prediction_result = predict_company_sensor_csv(
                    self.input_df,
                    mapping=mapping,
                    unit_conversions=units,
                    policy_id=str(self.policy_combo.currentData()),
                    write_outputs=True,
                )
                self.prediction_result["schema"] = MODEL_AI4I
            self.render_prediction_result()
            record_audit(
                self.actor,
                "desktop_prediction_completed",
                "success",
                "prediction",
                selected,
                {"rows": len(self.prediction_result["result_df"]), "schema": selected},
            )
            self.prediction_completed.emit()
        except Exception as error:
            record_audit(self.actor, "desktop_prediction_completed", "error", "prediction", selected, error_message=str(error))
            self.message_label.setText(
                "문제: 예측을 완료하지 못했습니다.\n"
                "원인 후보: 필수 센서 컬럼 누락, 잘못된 단위 선택, 숫자 형식 오류, 지원하지 않는 CSV 구조.\n"
                "해결 방법: 컬럼 확인 표에서 매핑을 고치거나 샘플 CSV 형식으로 다시 시도하세요."
            )
            show_error(self, "예측 실패", error)
        finally:
            if cursor_active:
                QApplication.restoreOverrideCursor()

    def render_prediction_result(self) -> None:
        if not self.prediction_result:
            return
        for card in self.step_cards:
            card.setVisible(True)
        self.mapping_label.setVisible(False)
        self.mapping_table.setVisible(False)
        while self.summary_grid.count():
            item = self.summary_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        result_df = self.prediction_result["result_df"]
        priority_df = self.prediction_result["priority_df"]
        quality = self.prediction_result.get("quality_report", {})
        threshold = float(self.prediction_result.get("policy", {}).get("threshold", 0.5))
        probability_column = "raw_probability" if "raw_probability" in result_df.columns else "failure_window_probability"
        high_risk = int((result_df["risk_status"] == "High Risk").sum()) if "risk_status" in result_df.columns else 0
        max_probability = float(pd.to_numeric(result_df[probability_column]).max()) if len(result_df) else 0.0
        schema = str(self.prediction_result.get("schema", self.selected_model()))
        output_path = self.prediction_result.get("output_path") or OUTPUT_DIR / "company_prediction_results.csv"
        quality_status = str(quality.get("quality_status", "OK"))
        quality_note = f"품질 점수 {quality.get('quality_score', '-')}"
        cards = [
            ("고위험 건수", str(high_risk), f"총 {len(result_df)}개 행 중", "warning" if high_risk else "success"),
            ("최고 위험 확률", f"{max_probability:.3f}", "모델 출력 기준", "danger" if max_probability >= threshold else "primary"),
            ("판정 기준", f"{threshold:.2f}", "운영 임계값", "primary"),
            ("입력 품질", quality_status, quality_note, "success" if quality_status == "OK" else "warning"),
        ]
        for index, (title, value, note, tone) in enumerate(cards):
            self.summary_grid.addWidget(make_card(title, value, note, tone=tone), index // 4, index % 4)
        risk_row_start = 1
        for index, (_, row) in enumerate(priority_df.head(3).iterrows()):
            probability = pd.to_numeric(pd.Series([row.get(probability_column, 0)]), errors="coerce").fillna(0).iloc[0]
            score = pd.to_numeric(pd.Series([row.get("risk_priority_score", 0)]), errors="coerce").fillna(0).iloc[0]
            input_row = row.get("input_row", index)
            tone = "danger" if float(probability) >= threshold else "warning" if float(probability) >= max(0.5, threshold * 0.7) else "primary"
            self.summary_grid.addWidget(
                make_card(
                    f"위험 우선순위 {index + 1}",
                    f"입력 행 {input_row} · 위험 {float(probability):.3f}",
                    f"우선순위 점수 {float(score):.2f}",
                    tone=tone,
                ),
                risk_row_start,
                index,
            )
        self.summary_grid.setRowMinimumHeight(0, 128)
        self.summary_grid.setRowMinimumHeight(1, 132)
        self.chart.plot_probabilities(result_df, probability_column, threshold=threshold)
        self.chart.setVisible(True)
        priority_columns = [
            "priority_rank",
            "vehicle_id",
            "input_row",
            "predicted_class",
            "class_meaning",
            probability_column,
            "risk_status",
            "risk_priority_score",
            "recommendation",
        ]
        result_columns = [
            "vehicle_id",
            "time_step",
            "predicted_class",
            "class_meaning",
            "failure_window_probability",
            "expected_cost_min",
            "risk_status",
            "recommendation",
        ]
        if schema != MODEL_SCANIA:
            priority_columns = [
                "priority_rank",
                "input_row",
                "raw_probability",
                "calibrated_probability",
                "risk_status",
                "risk_priority_score",
                "data_quality_status",
                "recommendation",
            ]
            result_columns = [
                "input_row",
                "Type",
                "Air temperature [K]",
                "Process temperature [K]",
                "Rotational speed [rpm]",
                "Torque [Nm]",
                "Tool wear [min]",
                "raw_probability",
                "calibrated_probability",
                "risk_status",
                "recommendation",
            ]
        set_display_table(self.priority_table, priority_df.head(10), priority_columns)
        set_display_table(self.result_table, result_df, result_columns)
        self.priority_label.setVisible(True)
        self.priority_label.setText("위험 우선순위 Top 10")
        self.priority_table.setVisible(True)
        self.result_label.setVisible(True)
        self.result_table.setVisible(True)
        self.last_saved_path = Path(output_path)
        self.output_hint_label.setText(f"기본 결과 파일: {self.last_saved_path}\n다른 위치에 저장하려면 '결과 CSV 저장'을 누르세요.")
        self.output_hint_label.setVisible(True)
        self.export_button.setEnabled(True)
        self.quick_export_button.setEnabled(True)
        self.open_folder_button.setEnabled(True)
        self.open_monitoring_button.setEnabled(True)
        self.message_label.setText("예측이 완료되었습니다. 바로 '위험 모니터링으로 이동'해 최신 위험 추세를 확인하세요.")
        self.workflow_status_label.setText(
            f"현재 상태: 예측 완료 · 고위험 {high_risk}건 · 최고 위험 확률 {max_probability:.3f} · 선택 모델 {self.schema_label(schema)}"
        )

    def export_results(self) -> None:
        if not self.prediction_result:
            return
        path, _ = QFileDialog.getSaveFileName(self, "예측 결과 저장", str(PROJECT_ROOT / "prediction_results.csv"), "CSV Files (*.csv)")
        if not path:
            return
        self.prediction_result["result_df"].to_csv(path, index=False, encoding="utf-8-sig")
        self.last_saved_path = Path(path)
        self.output_hint_label.setText(f"결과 CSV 저장 완료: {path}")
        self.output_hint_label.setVisible(True)
        self.open_folder_button.setEnabled(True)
        QMessageBox.information(self, "저장 완료", f"예측 결과를 저장했습니다.\n{path}")

    def export_results_to_default(self) -> None:
        if not self.prediction_result:
            return
        default_path = OUTPUT_DIR / "desktop_prediction_results.csv"
        default_path.parent.mkdir(parents=True, exist_ok=True)
        self.prediction_result["result_df"].to_csv(default_path, index=False, encoding="utf-8-sig")
        self.last_saved_path = default_path
        self.output_hint_label.setText(f"기본 결과 파일 저장 완료: {default_path}")
        self.output_hint_label.setVisible(True)
        self.open_folder_button.setEnabled(True)
        record_audit(self.actor, "desktop_prediction_exported", "success", "prediction", str(default_path))

    def open_saved_folder(self) -> None:
        if self.last_saved_path:
            os.startfile(str(self.last_saved_path.parent))  # type: ignore[attr-defined]
        else:
            os.startfile(str(OUTPUT_DIR))  # type: ignore[attr-defined]
