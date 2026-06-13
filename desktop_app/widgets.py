from __future__ import annotations

import traceback
import uuid

import matplotlib
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtWidgets import QFrame, QLabel, QMessageBox, QVBoxLayout, QWidget

from desktop_app.runtime import now_iso

matplotlib.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False


def make_card(title: str, value: str, note: str = "", tone: str = "default") -> QFrame:
    frame = QFrame()
    frame.setFrameShape(QFrame.StyledPanel)
    frame.setMinimumHeight(118)
    object_names = {
        "default": "card",
        "subtle": "cardSubtle",
        "primary": "cardPrimary",
        "success": "cardSuccess",
        "warning": "cardWarning",
        "danger": "cardDanger",
    }
    frame.setObjectName(object_names.get(tone, "card"))
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 17, 20, 17)
    layout.setSpacing(8)
    title_label = QLabel(title)
    title_label.setObjectName("cardTitle")
    value_label = QLabel(value)
    value_label.setObjectName("cardValue")
    value_label.setWordWrap(True)
    note_label = QLabel(note)
    note_label.setObjectName("cardNote")
    note_label.setWordWrap(True)
    layout.addWidget(title_label)
    layout.addWidget(value_label)
    if note:
        layout.addWidget(note_label)
    return frame


def _operator_error_message(error: Exception) -> tuple[str, str]:
    message = str(error).strip() or error.__class__.__name__
    lowered = message.lower()
    if "insufficient_quota" in lowered or "quota" in lowered or "billing" in lowered:
        return message, "OpenAI billing/usage 한도를 확인하거나, 무료 사용 가능한 Gemini key로 다시 실행하세요."
    if isinstance(error, FileNotFoundError) or "not found" in lowered or "no such file" in lowered:
        return message, "파일 위치가 올바른지 확인하고, 샘플 CSV로 형식을 먼저 확인하세요."
    if "필수 컬럼" in message or "missing" in lowered or "column" in lowered:
        return message, "샘플 CSV를 참고해 컬럼명과 필수 센서값이 모두 있는지 확인하세요."
    if "api key" in lowered or "key" in lowered:
        return message, "API key 형식과 권한을 확인하세요. key는 저장되지 않으며 현재 세션에서만 사용됩니다."
    if "permission" in lowered or "access" in lowered or "권한" in message:
        return message, "저장 폴더 권한을 확인하거나 다른 폴더에 저장해 보세요."
    if "could not convert" in lowered or "invalid literal" in lowered or "numeric" in lowered:
        return message, "숫자 컬럼에 문자나 빈 값이 섞였는지 확인하고 다시 실행하세요."
    return message, "입력 파일 형식, 컬럼명, 저장 폴더 권한을 확인한 뒤 다시 실행하세요."


def show_error(parent: QWidget, title: str, error: Exception) -> None:
    problem, action = _operator_error_message(error)
    QMessageBox.critical(
        parent,
        title,
        f"문제: {problem}\n\n"
        f"해야 할 일: {action}\n\n"
        f"상세 오류:\n{traceback.format_exc(limit=4)}",
    )


def record_audit(
    actor: dict,
    action: str,
    status: str,
    target_type: str = "",
    target_id: str = "",
    detail: dict | None = None,
    error_message: str = "",
) -> None:
    try:
        from operations_store import insert_audit_log

        insert_audit_log(
            {
                "audit_id": str(uuid.uuid4()),
                "created_at": now_iso(),
                "actor_id": actor.get("actor_id", ""),
                "role": actor.get("role", ""),
                "action": action,
                "status": status,
                "target_type": target_type,
                "target_id": target_id,
                "detail": detail or {},
                "error_message": error_message,
            }
        )
    except Exception:
        # Audit logging must not break the operator workflow.
        pass


class ChartBox(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("chartBox")
        self.setMinimumHeight(300)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        self.figure = Figure(figsize=(8, 3), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

    def plot_probabilities(self, df: pd.DataFrame, column: str, threshold: float | None = None) -> None:
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        self.figure.patch.set_facecolor("#ffffff")
        if df.empty or column not in df.columns:
            axis.axis("off")
            axis.text(0.5, 0.5, "CSV를 불러오고 예측을 실행하면 위험 점수 그래프가 표시됩니다.", ha="center", va="center")
        else:
            values = pd.to_numeric(df[column], errors="coerce").fillna(0)
            threshold_value = float(threshold) if threshold is not None else 0.75
            colors = [
                "#dc2626" if value >= threshold_value else "#f59e0b" if value >= max(0.5, threshold_value * 0.7) else "#2563eb"
                for value in values
            ]
            axis.bar(range(len(values)), values, color=colors)
            if threshold is not None:
                axis.axhline(float(threshold), color="#b3261e", linestyle="--", linewidth=1.5, label="위험 판정 기준")
                axis.legend(loc="upper right")
            axis.set_xlabel("입력 행")
            axis.set_ylabel("위험 점수")
            axis.set_ylim(0, max(1.0, float(values.max()) * 1.1))
            axis.grid(axis="y", color="#e5e7eb", linewidth=0.8)
        self.canvas.draw()

    def plot_spc(self, df: pd.DataFrame) -> None:
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        self.figure.patch.set_facecolor("#ffffff")
        probability_column = "probability" if "probability" in df.columns else "xgboost_probability"
        if df.empty or probability_column not in df.columns:
            axis.axis("off")
            axis.text(0.5, 0.5, "위험 추세 데이터가 아직 없습니다.", ha="center", va="center")
        else:
            x_values = range(len(df))
            probability = pd.to_numeric(df[probability_column], errors="coerce")
            axis.plot(x_values, probability, color="#2563eb", linewidth=1.8, label="위험 점수")
            for column, label, color in [
                ("center_line", "중심선", "#666666"),
                ("risk_center_line", "중심선", "#666666"),
                ("ucl", "관리상한", "#b3261e"),
                ("risk_ucl", "관리상한", "#b3261e"),
                ("lcl", "관리하한", "#4d7c0f"),
                ("risk_lcl", "관리하한", "#4d7c0f"),
                ("selected_threshold", "위험 판정 기준", "#7c3aed"),
            ]:
                if column in df.columns:
                    series = pd.to_numeric(df[column], errors="coerce")
                    if series.notna().any():
                        axis.plot(x_values, series, linestyle="--", linewidth=1, label=label, color=color)
            axis.set_xlabel("관측 순서")
            axis.set_ylabel("위험 점수")
            axis.set_ylim(0, 1)
            axis.grid(axis="y", color="#e5e7eb", linewidth=0.8)
            axis.legend(loc="upper right")
        self.canvas.draw()


def stylesheet() -> str:
    return """
    QWidget { font-family: "Segoe UI", "Malgun Gothic"; font-size: 10.5pt; color: #111827; }
    QMainWindow, QDialog { background: #eef3f8; }
    QFrame#sidebar { background: #071a2e; border: 0; }
    QFrame#content, QScrollArea { background: #f4f7fb; border: 0; }
    QScrollArea > QWidget > QWidget { background: #f4f7fb; }
    QLabel#sidebarTitle { color: #ffffff; font-size: 22pt; font-weight: 800; letter-spacing: 0px; }
    QLabel#sidebarSubtitle { color: #b9c7dc; font-size: 9.5pt; line-height: 130%; }
    QPushButton#navButton {
        background: transparent; color: #d8e3f3; border: 0; border-radius: 14px;
        padding: 15px 18px; text-align: left; font-weight: 700;
    }
    QPushButton#navButton:hover { background: #132f4d; }
    QPushButton#navButton:checked { background: #2563eb; color: #ffffff; }
    QLabel#title { font-size: 28pt; font-weight: 800; color: #071a2e; }
    QLabel#sectionTitle { font-size: 22pt; font-weight: 800; color: #071a2e; }
    QLabel#muted { color: #64748b; }
    QLabel#statusNotice { color: #1e3a5f; background: #eaf3ff; border: 1px solid #bdd7ff; border-radius: 16px; padding: 14px 16px; }
    QLabel#cardTitle { color: #5f6c80; font-weight: 700; }
    QLabel#cardValue { color: #071a2e; font-size: 13pt; font-weight: 600; }
    QLabel#cardNote { color: #667085; }
    QFrame#card, QFrame#chartBox {
        background: #ffffff; border: 1px solid #d9e4f2; border-radius: 16px;
    }
    QFrame#cardSubtle { background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 16px; }
    QFrame#cardPrimary { background: #edf5ff; border: 1px solid #9dc3ff; border-radius: 16px; }
    QFrame#cardSuccess { background: #ecfdf5; border: 1px solid #9ee6be; border-radius: 16px; }
    QFrame#cardWarning { background: #fff8e6; border: 1px solid #f6d774; border-radius: 16px; }
    QFrame#cardDanger { background: #fff1f2; border: 1px solid #f8b4b4; border-radius: 16px; }
    QPushButton { background: #2563eb; color: white; border: 0; border-radius: 12px; padding: 11px 17px; font-weight: 700; }
    QPushButton:hover { background: #1d4ed8; }
    QPushButton:pressed { background: #1e40af; }
    QPushButton:disabled { background: #aab6c7; color: #f8fafc; }
    QPushButton#secondaryButton { background: #e8eef7; color: #1e3a5f; border: 1px solid #cad7e8; }
    QPushButton#secondaryButton:hover { background: #dae7f7; }
    QPushButton#successButton { background: #059669; color: #ffffff; }
    QPushButton#successButton:hover { background: #047857; }
    QPushButton#dangerButton { background: #dc2626; color: #ffffff; }
    QPushButton#dangerButton:hover { background: #b91c1c; }
    QPushButton#secondaryButton:disabled, QPushButton#successButton:disabled, QPushButton#dangerButton:disabled {
        background: #aab6c7; color: #f8fafc; border: 0;
    }
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QTableWidget, QListWidget {
        background: white; border: 1px solid #cfd8e3; border-radius: 10px; padding: 7px;
    }
    QListWidget { alternate-background-color: #f8fafc; }
    QListWidget::item { padding: 7px 8px; border-radius: 7px; }
    QListWidget::item:selected { background: #dbeafe; color: #0f172a; }
    QTableWidget {
        gridline-color: #e5ecf5; alternate-background-color: #f8fafc;
        selection-background-color: #dbeafe; selection-color: #0f172a;
    }
    QHeaderView::section { background: #eef4fb; padding: 8px; border: 1px solid #d9e1ec; font-weight: 700; }
    QGroupBox { background: white; border: 1px solid #d9e1ec; border-radius: 14px; margin-top: 12px; padding: 14px; font-weight: 700; }
    QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; color: #334155; }
    QScrollBar:vertical { background: #edf2f7; width: 12px; margin: 4px; border-radius: 6px; }
    QScrollBar::handle:vertical { background: #b9c6d6; border-radius: 6px; min-height: 36px; }
    QScrollBar::handle:vertical:hover { background: #94a3b8; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    """
