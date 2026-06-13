from __future__ import annotations

import pandas as pd
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from desktop_app.formatters import set_display_table
from desktop_app.runtime import OUTPUT_DIR, read_json
from desktop_app.widgets import ChartBox, make_card

PREDICTION_SOURCES = [
    ("회사/기본 센서 예측", OUTPUT_DIR / "company_prediction_results.csv"),
    ("SCANIA 예측", OUTPUT_DIR / "scania_product_predictions.csv"),
    ("데스크톱 저장 결과", OUTPUT_DIR / "desktop_prediction_results.csv"),
]
PROBABILITY_COLUMNS = [
    "raw_probability",
    "calibrated_probability",
    "failure_window_probability",
    "xgboost_probability",
    "probability",
]


def latest_prediction_source() -> tuple[str, Path] | None:
    existing = [(label, path) for label, path in PREDICTION_SOURCES if path.exists()]
    if not existing:
        return None
    return max(existing, key=lambda item: item[1].stat().st_mtime)


def normalize_monitoring_frame(df: pd.DataFrame, source_label: str) -> pd.DataFrame:
    """Create one monitoring shape from AI4I, SCANIA, or saved desktop results."""
    if df.empty:
        return pd.DataFrame()

    probability_column = next((column for column in PROBABILITY_COLUMNS if column in df.columns), "")
    if not probability_column:
        return pd.DataFrame()

    shown = df.copy()
    shown["probability"] = pd.to_numeric(shown[probability_column], errors="coerce").fillna(0)
    if "input_row" not in shown.columns:
        shown.insert(0, "input_row", range(len(shown)))
    if "time_step" not in shown.columns:
        shown["time_step"] = range(len(shown))

    threshold = 0.5
    if "selected_threshold" in shown.columns:
        threshold_series = pd.to_numeric(shown["selected_threshold"], errors="coerce").dropna()
        if not threshold_series.empty:
            threshold = float(threshold_series.iloc[0])
    shown["selected_threshold"] = threshold
    if "risk_status" not in shown.columns:
        shown["risk_status"] = shown["probability"].map(lambda value: "High Risk" if float(value) >= threshold else "Normal")
    shown["source"] = source_label
    return shown

class RiskMonitoringPage(QWidget):
    work_order_requested = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._top_rows = pd.DataFrame()
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("위험 모니터링")
        title.setObjectName("sectionTitle")
        refresh = QPushButton("최신 예측 결과 불러오기")
        refresh.setObjectName("secondaryButton")
        refresh.clicked.connect(self.render)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(refresh)
        layout.addLayout(header)

        intro = QLabel("가장 최근 예측 결과를 기준으로 고위험 행, 위험 확률 추세, 추천 조치를 한 화면에서 확인합니다.")
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusNotice")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.summary_grid = QGridLayout()
        self.summary_grid.setHorizontalSpacing(16)
        self.summary_grid.setVerticalSpacing(16)
        layout.addLayout(self.summary_grid)

        self.chart = ChartBox()
        layout.addWidget(self.chart)

        self.table_label = QLabel("고위험 Top rows")
        self.table_label.setObjectName("cardTitle")
        table_actions = QHBoxLayout()
        self.work_order_button = QPushButton("선택 row로 작업지시 준비")
        self.work_order_button.setObjectName("successButton")
        self.work_order_button.setEnabled(False)
        self.work_order_button.clicked.connect(self.request_work_order_for_selected_row)
        table_actions.addWidget(self.table_label)
        table_actions.addStretch()
        table_actions.addWidget(self.work_order_button)
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(190)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addLayout(table_actions)
        layout.addWidget(self.table)
        self.render()

    def request_work_order_for_selected_row(self) -> None:
        if self._top_rows.empty:
            return
        selected_row = self.table.currentRow()
        if selected_row < 0 or selected_row >= len(self._top_rows):
            selected_row = 0
        self.work_order_requested.emit(self._top_rows.iloc[selected_row].to_dict())

    def render(self) -> None:
        for index in reversed(range(self.summary_grid.count())):
            widget = self.summary_grid.itemAt(index).widget()
            if widget:
                widget.setParent(None)

        source = latest_prediction_source()
        source_label = "SPC 기준 데이터"
        source_path: Path | None = None
        if source:
            source_label, prediction_path = source
            source_path = prediction_path
            df = normalize_monitoring_frame(pd.read_csv(prediction_path), source_label)
        else:
            spc_path = OUTPUT_DIR / "spc_timeseries.csv"
            df = pd.read_csv(spc_path) if spc_path.exists() else pd.DataFrame()
            if not df.empty and "probability" not in df.columns and "xgboost_probability" in df.columns:
                df["probability"] = pd.to_numeric(df["xgboost_probability"], errors="coerce").fillna(0)

        summary = read_json(OUTPUT_DIR / "spc_summary.json", {})
        high_risk = summary.get("high_risk_count", summary.get("risk_summary", {}).get("high_risk_count", "N/A"))
        ucl = summary.get("risk_ucl", "N/A")
        lcl = summary.get("risk_lcl", "N/A")
        max_probability: float | str = "N/A"
        threshold: float | str = "N/A"
        if not df.empty and "risk_status" in df.columns:
            high_risk = int((df["risk_status"].astype(str) == "High Risk").sum())
        if not df.empty and "probability" in df.columns:
            values = pd.to_numeric(df["probability"], errors="coerce").dropna()
            if not values.empty:
                max_probability = round(float(values.max()), 4)
                ucl = round(min(1.0, float(values.mean() + 3 * values.std(ddof=0))), 4)
                lcl = round(max(0.0, float(values.mean() - 3 * values.std(ddof=0))), 4)
        if not df.empty and "selected_threshold" in df.columns:
            threshold_values = pd.to_numeric(df["selected_threshold"], errors="coerce").dropna()
            if not threshold_values.empty:
                threshold = round(float(threshold_values.iloc[0]), 4)

        if df.empty:
            self.status_label.setText("아직 표시할 위험 추세 데이터가 없습니다. 데이터 예측을 먼저 실행하면 이 화면에 추세가 표시됩니다.")
        else:
            path_note = f" · 파일: {source_path.name}" if source_path else ""
            self.status_label.setText(
                f"현재 표시 중: {source_label}{path_note} · 최근 {min(len(df), 200)}개 관측치 기준 · 다음 행동: 고위험 Top rows부터 확인"
            )

        cards = [
            ("관측 행 수", str(len(df)), "기준 데이터", "primary"),
            ("고위험 건수", str(high_risk), "위험 판정 기준 초과", "warning" if high_risk not in ["N/A", 0, "0"] else "success"),
            ("최고 위험 확률", str(max_probability), "최신 예측 결과", "danger" if isinstance(max_probability, float) and max_probability >= 0.86 else "primary"),
            ("판정 기준", str(threshold), "결과 파일 기준", "subtle"),
        ]
        for index, (title, value, note, tone) in enumerate(cards):
            self.summary_grid.addWidget(make_card(title, value, note, tone=tone), index // 4, index % 4)

        self.chart.plot_spc(df.tail(200))
        top_view = df.sort_values("probability", ascending=False) if "probability" in df.columns else df
        if "risk_status" in top_view.columns:
            high_risk_view = top_view[top_view["risk_status"].astype(str) == "High Risk"]
            if not high_risk_view.empty:
                top_view = high_risk_view
        self._top_rows = top_view.head(50).reset_index(drop=True) if not top_view.empty else pd.DataFrame()
        self.work_order_button.setEnabled(not self._top_rows.empty)
        set_display_table(
            self.table,
            self._top_rows,
            ["source", "input_row", "vehicle_id", "time_step", "probability", "selected_threshold", "risk_status", "risk_priority_score", "recommendation"],
            max_rows=50,
        )
        if self.table.rowCount() > 0:
            self.table.selectRow(0)
