from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


def card(title: str, value: str, note: str = "") -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    frame.setMinimumHeight(116)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(8)
    title_label = QLabel(title)
    title_label.setObjectName("cardTitle")
    value_label = QLabel(value)
    value_label.setObjectName("cardValue")
    value_label.setWordWrap(True)
    layout.addWidget(title_label)
    layout.addWidget(value_label)
    if note:
        note_label = QLabel(note)
        note_label.setObjectName("muted")
        note_label.setWordWrap(True)
        layout.addWidget(note_label)
    return frame


def empty_state(title: str, message: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("emptyState")
    frame.setMinimumHeight(140)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(8)
    title_label = QLabel(title)
    title_label.setObjectName("sectionTitle")
    message_label = QLabel(message)
    message_label.setWordWrap(True)
    message_label.setObjectName("muted")
    layout.addWidget(title_label)
    layout.addWidget(message_label)
    return frame


def button_row(*buttons: QWidget) -> QWidget:
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    for button in buttons:
        layout.addWidget(button)
    layout.addStretch(1)
    return widget


def _display_value(key: str, value: Any) -> str:
    if key == "risk_status":
        return {"High Risk": "고위험", "Low Risk": "정상", "Normal": "정상", "Medium Risk": "주의"}.get(str(value), str(value))
    if key == "decision":
        return {"approve": "승인", "needs_review": "검토 필요", "reject": "반려"}.get(str(value), str(value))
    if key in {"failure_probability", "risk_priority_score", "selected_threshold"}:
        try:
            return f"{float(value):.3f}"
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def set_table(table: QTableWidget, rows: list[dict[str, Any]], columns: list[tuple[str, str]], limit: int = 200) -> None:
    visible_rows = rows[:limit]
    table.clear()
    table.setColumnCount(len(columns))
    table.setRowCount(len(visible_rows))
    table.setHorizontalHeaderLabels([label for _, label in columns])
    for row_index, row in enumerate(visible_rows):
        risk_value = str(row.get("risk_status", ""))
        for column_index, (key, _) in enumerate(columns):
            raw_value = row.get(key, "")
            item = QTableWidgetItem(_display_value(key, raw_value))
            if risk_value == "High Risk":
                item.setBackground(QColor("#fff1f2"))
            if key in {"failure_probability", "risk_priority_score"}:
                try:
                    numeric = float(raw_value)
                    if numeric >= 0.75:
                        item.setBackground(QColor("#fee2e2"))
                    elif numeric >= 0.5:
                        item.setBackground(QColor("#fef3c7"))
                except (TypeError, ValueError):
                    pass
            table.setItem(row_index, column_index, item)
    table.resizeColumnsToContents()


class LiteBarChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.values: list[float] = []
        self.setMinimumHeight(210)

    def set_values(self, values: list[float]) -> None:
        self.values = [max(0.0, min(float(value), 1.0)) for value in values[:80]]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(18, 18, -18, -30)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.setPen(QPen(QColor("#d8e2ef"), 1))
        painter.drawRect(rect)
        if not self.values:
            painter.setPen(QColor("#64748b"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "CSV를 불러오고 예측을 실행하면 위험 점수 그래프가 표시됩니다.")
            return
        bar_count = max(1, len(self.values))
        gap = 3
        width = max(4, int((rect.width() - gap * (bar_count - 1)) / bar_count))
        baseline = rect.bottom()
        for index, value in enumerate(self.values):
            height = int(rect.height() * value)
            x = rect.left() + index * (width + gap)
            y = baseline - height
            color = QColor("#dc2626") if value >= 0.75 else QColor("#f59e0b") if value >= 0.5 else QColor("#2563eb")
            painter.fillRect(x, y, width, height, color)
        painter.setPen(QColor("#475569"))
        painter.drawText(rect.adjusted(0, rect.height() + 4, 0, 26), Qt.AlignmentFlag.AlignLeft, "행별 위험 점수")


def open_folder(path: Path) -> None:
    target = path if path.is_dir() else path.parent
    QDesktopServices.openUrl(target.resolve().as_uri())
