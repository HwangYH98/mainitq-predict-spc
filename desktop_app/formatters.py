from __future__ import annotations

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from desktop_app.config import DISPLAY_COLUMN_NAMES


def humanize_status(value: str) -> str:
    mapping = {
        "High Risk": "고위험",
        "Low Risk": "정상",
        "Normal": "정상",
        "Medium Risk": "주의",
        "approve": "승인",
        "needs_review": "검토 필요",
        "reject": "반려",
    }
    return mapping.get(str(value), str(value))


def status_from_report_mode(mode: str) -> str:
    if not mode:
        return "저장된 리포트 없음"
    if mode.startswith("fallback"):
        return "저장 리포트 사용 중"
    return "AI 리포트 생성 완료"


def default_actor() -> dict:
    """Desktop app runs as a local operator workstation without a login gate."""
    return {"actor_id": "local_operator", "role": "operator"}


def _format_cell(value: object, header: str) -> str:
    if pd.isna(value):
        return ""
    numeric_headers = {
        "고장 확률",
        "보정 확률",
        "원 확률",
        "고장 window 확률",
        "위험 우선순위 점수",
        "판정 기준",
        "위험 점수",
        "예상 비용",
    }
    if header in numeric_headers:
        try:
            return f"{float(value):.3f}"
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def set_table_dataframe(table: QTableWidget, df: pd.DataFrame, max_rows: int = 200) -> None:
    table.clear()
    if df is None or df.empty:
        table.setRowCount(0)
        table.setColumnCount(0)
        return
    shown = df.head(max_rows).copy()
    table.setRowCount(len(shown))
    table.setColumnCount(len(shown.columns))
    table.setHorizontalHeaderLabels([str(column) for column in shown.columns])
    for row_index, (_, row) in enumerate(shown.iterrows()):
        row_values = {str(column): row[column] for column in shown.columns}
        risk_value = str(row_values.get("위험 상태", row_values.get("risk_status", "")))
        for col_index, value in enumerate(row):
            header = str(shown.columns[col_index])
            item = QTableWidgetItem(_format_cell(value, header))
            item.setFlags(item.flags() ^ Qt.ItemIsEditable)
            if risk_value == "고위험":
                item.setBackground(QColor("#fff1f2"))
            elif risk_value == "주의":
                item.setBackground(QColor("#fffbeb"))
            if header in {"고장 확률", "보정 확률", "원 확률", "고장 window 확률", "위험 우선순위 점수", "위험 점수"}:
                try:
                    numeric = float(value)
                    if numeric >= 0.75:
                        item.setBackground(QColor("#fee2e2"))
                    elif numeric >= 0.5:
                        item.setBackground(QColor("#fef3c7"))
                except (TypeError, ValueError):
                    pass
            table.setItem(row_index, col_index, item)
    table.resizeColumnsToContents()


def set_display_table(
    table: QTableWidget,
    df: pd.DataFrame,
    columns: list[str] | None = None,
    max_rows: int = 200,
) -> None:
    """Show a DataFrame with operator-facing Korean column labels."""
    if df is None or df.empty:
        set_table_dataframe(table, df)
        return
    shown = df.copy()
    if columns:
        shown = shown[[column for column in columns if column in shown.columns]]
    for column in ["risk_status", "decision"]:
        if column in shown.columns:
            shown[column] = shown[column].map(humanize_status)
    shown = shown.rename(columns=DISPLAY_COLUMN_NAMES)
    set_table_dataframe(table, shown, max_rows=max_rows)
