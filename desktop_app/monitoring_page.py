from __future__ import annotations

import pandas as pd
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QVBoxLayout, QWidget

from desktop_app.formatters import set_display_table
from desktop_app.runtime import OUTPUT_DIR, read_json
from desktop_app.widgets import ChartBox, make_card

PREDICTION_SOURCES = [
    ("회사/기본 센서 예측", OUTPUT_DIR / "company_prediction_results.csv"),
    ("SCANIA 예측", OUTPUT_DIR / "scania_product_predictions.csv"),
    ("데스크톱 저장 결과", OUTPUT_DIR / "desktop_prediction_results.csv"),
]
PROBABILITY_COLUMNS = [
    "calibrated_probability",
    "failure_window_probability",
    "xgboost_probability",
    "probability",
    "raw_probability",
]


def latest_prediction_source() -> tuple[str, object] | None:
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
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("위험 분석")
        title.setObjectName("sectionTitle")
        refresh = QPushButton("새로고침")
        refresh.setObjectName("secondaryButton")
        refresh.clicked.connect(self.render)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(refresh)
        layout.addLayout(header)

        intro = QLabel("최근 예측 결과를 기준으로 고위험 건수, 관리한계, 위험 추세를 확인합니다.")
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

        self.table_label = QLabel("최근 위험 추세")
        self.table_label.setObjectName("cardTitle")
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(190)
        layout.addWidget(self.table_label)
        layout.addWidget(self.table)
        self.render()

    def render(self) -> None:
        for index in reversed(range(self.summary_grid.count())):
            widget = self.summary_grid.itemAt(index).widget()
            if widget:
                widget.setParent(None)

        source = latest_prediction_source()
        source_label = "SPC 기준 데이터"
        if source:
            source_label, prediction_path = source
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
        if not df.empty and "risk_status" in df.columns:
            high_risk = int((df["risk_status"].astype(str) == "High Risk").sum())
        if not df.empty and "probability" in df.columns:
            values = pd.to_numeric(df["probability"], errors="coerce").dropna()
            if not values.empty:
                ucl = round(min(1.0, float(values.mean() + 3 * values.std(ddof=0))), 4)
                lcl = round(max(0.0, float(values.mean() - 3 * values.std(ddof=0))), 4)

        if df.empty:
            self.status_label.setText("아직 표시할 위험 추세 데이터가 없습니다. 데이터 예측을 먼저 실행하면 이 화면에 추세가 표시됩니다.")
        else:
            self.status_label.setText(f"{source_label}의 최근 {min(len(df), 200)}개 관측치를 기준으로 위험 추세를 표시합니다.")

        cards = [
            ("관측 행 수", str(len(df)), "기준 데이터", "primary"),
            ("고위험 건수", str(high_risk), "위험 판정 기준 초과", "warning" if high_risk not in ["N/A", 0, "0"] else "success"),
            ("관리상한", str(ucl), "고장 확률 UCL", "subtle"),
            ("입력 출처", source_label, "최신 예측 결과 우선", "subtle"),
        ]
        for index, (title, value, note, tone) in enumerate(cards):
            self.summary_grid.addWidget(make_card(title, value, note, tone=tone), index // 4, index % 4)

        self.chart.plot_spc(df.tail(200))
        set_display_table(
            self.table,
            df.tail(50),
            ["source", "input_row", "vehicle_id", "time_step", "probability", "selected_threshold", "risk_status", "risk_priority_score"],
            max_rows=50,
        )
