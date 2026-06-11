from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from desktop_app.formatters import status_from_report_mode
from desktop_app.genai import mode_label, provider_label, resolve_genai_connection, restore_env, with_restored_env
from desktop_app.report_history import (
    append_report_history,
    classify_report_error,
    latest_successful_report,
    read_report_history,
    save_report_snapshot,
)
from desktop_app.runtime import OUTPUT_DIR, read_json, read_text
from desktop_app.widgets import make_card, record_audit, show_error


TEMPLATE_NOTES = {
    "operator": "운영자가 바로 확인할 수 있게 위험과 다음 행동을 짧게 정리합니다.",
    "manager": "관리자가 볼 수 있게 위험 규모, 근거, 한계를 균형 있게 정리합니다.",
    "maintenance": "정비팀이 볼 수 있게 작업지시 판단 근거와 확인 항목을 중심으로 정리합니다.",
}

LENGTH_NOTES = {
    "short": "짧게",
    "standard": "표준",
    "detailed": "상세",
}

TEMPLATE_LABELS = {
    "operator": "운영자용",
    "manager": "관리자용",
    "maintenance": "정비팀용",
}

LENGTH_LABELS = {
    "short": "짧게",
    "standard": "표준",
    "detailed": "상세",
}


class AIReportPage(QWidget):
    def __init__(self, actor: dict) -> None:
        super().__init__()
        self.actor = actor
        self.resolved_connection: dict | None = None
        self.current_report_path: Path | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        title = QLabel("AI 리포트")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        intro = QLabel(
            "API key를 입력하면 사용 가능한 모델을 자동 확인하고 운영 참고 리포트를 생성합니다. "
            "API key는 파일로 저장하지 않습니다."
        )
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        guide = QLabel("사용 흐름: API key 입력 → 연결 확인 → 리포트 생성 → 이력에서 다시 열기. API key는 파일에 저장하지 않습니다.")
        guide.setObjectName("statusNotice")
        guide.setWordWrap(True)
        layout.addWidget(guide)

        status_row = QHBoxLayout()
        status_row.setSpacing(14)
        self.saved_status_card = make_card("마지막 성공 리포트", "확인 중", "최근 정상 생성된 리포트")
        self.connection_card = make_card("AI 연결", "대기 중", "API key 입력 후 확인")
        self.template_card = make_card("리포트 형식", "운영자용 · 표준", "생성 전 선택 가능")
        status_row.addWidget(self.saved_status_card)
        status_row.addWidget(self.connection_card)
        status_row.addWidget(self.template_card)
        layout.addLayout(status_row)

        form = QFormLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("표준 모드", "standard")
        self.mode_combo.addItem("고성능 모드", "advanced")
        self.template_combo = QComboBox()
        self.template_combo.addItem("운영자용", "operator")
        self.template_combo.addItem("관리자용", "manager")
        self.template_combo.addItem("정비팀용", "maintenance")
        self.length_combo = QComboBox()
        self.length_combo.addItem("짧게", "short")
        self.length_combo.addItem("표준", "standard")
        self.length_combo.addItem("상세", "detailed")
        self.length_combo.setCurrentIndex(1)
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("Gemini 또는 OpenAI API key")
        self.key_input.textChanged.connect(self.on_key_changed)
        self.mode_combo.currentIndexChanged.connect(self.clear_connection)
        self.template_combo.currentIndexChanged.connect(self.update_template_card)
        self.length_combo.currentIndexChanged.connect(self.update_template_card)
        form.addRow("AI 모드", self.mode_combo)
        form.addRow("리포트 대상", self.template_combo)
        form.addRow("리포트 길이", self.length_combo)
        form.addRow("API key", self.key_input)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.status_label = QLabel("API key 없음: 마지막 성공 리포트와 이력만 표시합니다.")
        self.status_label.setObjectName("muted")
        self.detail_label = QLabel("")
        self.detail_label.setObjectName("muted")
        self.load_button = QPushButton("저장 리포트 불러오기")
        self.check_button = QPushButton("연결 확인")
        self.generate_button = QPushButton("새 리포트 생성")
        self.export_button = QPushButton("Markdown 내보내기")
        self.detail_button = QPushButton("상세 보기")
        self.load_button.setObjectName("secondaryButton")
        self.check_button.setObjectName("secondaryButton")
        self.generate_button.setObjectName("successButton")
        self.export_button.setObjectName("secondaryButton")
        self.detail_button.setObjectName("secondaryButton")
        self.check_button.setEnabled(False)
        self.generate_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.load_button.clicked.connect(self.load_saved_report)
        self.check_button.clicked.connect(self.check_connection)
        self.generate_button.clicked.connect(self.generate_report)
        self.export_button.clicked.connect(self.export_current_report)
        self.detail_button.clicked.connect(self.toggle_details)
        buttons.addWidget(self.status_label)
        buttons.addStretch()
        buttons.addWidget(self.load_button)
        buttons.addWidget(self.check_button)
        buttons.addWidget(self.generate_button)
        buttons.addWidget(self.export_button)
        buttons.addWidget(self.detail_button)
        layout.addLayout(buttons)

        self.detail_label.setVisible(False)
        layout.addWidget(self.detail_label)

        history_row = QHBoxLayout()
        history_label = QLabel("리포트 이력")
        history_label.setObjectName("cardTitle")
        self.history_filter = QComboBox()
        self.history_filter.addItem("전체", "all")
        self.history_filter.addItem("성공", "success")
        self.history_filter.addItem("실패", "error")
        self.history_filter.currentIndexChanged.connect(self.refresh_history)
        history_row.addWidget(history_label)
        history_row.addStretch()
        history_row.addWidget(self.history_filter)
        layout.addLayout(history_row)

        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(130)
        self.history_list.itemClicked.connect(self.load_history_item)
        layout.addWidget(self.history_list)

        body_label = QLabel("리포트 본문")
        body_label.setObjectName("cardTitle")
        layout.addWidget(body_label)
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setMinimumHeight(300)
        layout.addWidget(self.report_text)
        self.load_saved_report()
        self.update_template_card()
        self.refresh_history()

    def _set_card_value(self, card, value: str, note: str | None = None) -> None:
        labels = card.findChildren(QLabel)
        if len(labels) >= 2:
            labels[1].setText(value)
        if note is not None and len(labels) >= 3:
            labels[2].setText(note)

    def update_template_card(self) -> None:
        template = self.template_combo.currentText()
        length = self.length_combo.currentText()
        self._set_card_value(self.template_card, f"{template} · {length}", TEMPLATE_NOTES[str(self.template_combo.currentData())])

    def on_key_changed(self) -> None:
        has_key = bool(self.key_input.text().strip())
        self.check_button.setEnabled(has_key)
        self.generate_button.setEnabled(has_key)
        self.clear_connection()
        if has_key:
            self.status_label.setText("API key 입력됨. 연결 확인 후 리포트를 생성할 수 있습니다.")
        else:
            self.status_label.setText("API key 없음: 저장된 리포트만 표시합니다.")

    def clear_connection(self) -> None:
        self.resolved_connection = None
        self._set_card_value(self.connection_card, "대기 중", "API key 입력 후 확인")
        self.detail_label.setText("")

    def toggle_details(self) -> None:
        self.detail_label.setVisible(not self.detail_label.isVisible())

    def refresh_history(self) -> None:
        selected_status = str(self.history_filter.currentData()) if hasattr(self, "history_filter") else "all"
        self.history_list.clear()
        records = read_report_history(status_filter=selected_status)
        if not records:
            item = QListWidgetItem("리포트 이력이 없습니다.")
            item.setData(Qt.UserRole, None)
            self.history_list.addItem(item)
            return
        for record in records:
            status_label = "성공" if record.get("status") == "success" else "실패"
            template = TEMPLATE_LABELS.get(str(record.get("template") or ""), str(record.get("template") or "리포트"))
            length = LENGTH_LABELS.get(str(record.get("length") or ""), str(record.get("length") or ""))
            provider = str(record.get("provider") or "AI")
            mode = mode_label(str(record.get("mode") or "")) if record.get("mode") else ""
            created_at = str(record.get("created_at") or "")
            item = QListWidgetItem(f"[{status_label}] {created_at} · {provider} {mode} · {template} {length}")
            item.setData(Qt.UserRole, record)
            self.history_list.addItem(item)

    def load_saved_report(self) -> None:
        latest_record = latest_successful_report()
        if latest_record and latest_record.get("report_path"):
            path = Path(str(latest_record["report_path"]))
            report = read_text(path, "저장된 리포트 파일을 찾을 수 없습니다.")
            self.current_report_path = path if path.exists() else None
            self._set_card_value(self.saved_status_card, "AI 리포트 생성 완료", "마지막 성공 이력")
            self.report_text.setPlainText(report)
            self.export_button.setEnabled(bool(report.strip()))
            return

        context = read_json(OUTPUT_DIR / "ai_report_context.json", {})
        report = read_text(OUTPUT_DIR / "ai_manager_report.md", "저장된 리포트가 없습니다.")
        status = status_from_report_mode(str(context.get("report_generation_mode", "")))
        self.current_report_path = OUTPUT_DIR / "ai_manager_report.md" if (OUTPUT_DIR / "ai_manager_report.md").exists() else None
        self._set_card_value(self.saved_status_card, status, "저장된 리포트 상태")
        self.report_text.setPlainText(report)
        self.export_button.setEnabled(bool(report.strip()) and report != "저장된 리포트가 없습니다.")

    def load_history_item(self, item: QListWidgetItem) -> None:
        record = item.data(Qt.UserRole)
        if not record:
            return
        report_path = Path(str(record.get("report_path") or ""))
        if report_path.exists():
            self.current_report_path = report_path
            self.report_text.setPlainText(report_path.read_text(encoding="utf-8"))
            self.export_button.setEnabled(True)
        else:
            self.current_report_path = None
            preview = str(record.get("report_preview") or "")
            error = str(record.get("error_message") or "")
            self.report_text.setPlainText(preview or error or "이력에는 열 수 있는 리포트 본문이 없습니다.")
            self.export_button.setEnabled(bool(preview))
        self.status_label.setText("선택한 리포트 이력을 표시했습니다.")

    def export_current_report(self) -> None:
        report = self.report_text.toPlainText().strip()
        if not report:
            QMessageBox.warning(self, "내보내기 불가", "내보낼 리포트 내용이 없습니다.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "리포트 Markdown 저장", str(OUTPUT_DIR / "ai_manager_report_export.md"), "Markdown Files (*.md)")
        if not path:
            return
        Path(path).write_text(report, encoding="utf-8")
        QMessageBox.information(self, "저장 완료", f"리포트를 저장했습니다.\n{path}")

    def friendly_error_message(self, error_type: str, raw_message: str) -> str:
        if error_type == "quota_error":
            return "OpenAI 사용량 한도 또는 결제 크레딧이 부족합니다. OpenAI billing/usage를 확인하거나 Gemini key로 실행하세요."
        messages = {
            "key_format_error": "API key 형식을 인식하지 못했습니다. Gemini 또는 OpenAI key인지 확인하세요.",
            "connection_failed": "네트워크 또는 API 연결에 실패했습니다. 인터넷 연결과 서비스 상태를 확인하세요.",
            "model_access_error": "현재 key로 선택 모델에 접근할 수 없습니다. 다른 모드로 다시 시도하세요.",
            "empty_response": "AI 응답이 비어 있습니다. 잠시 후 다시 시도하세요.",
            "report_save_failed": "리포트 저장에 실패했습니다. outputs 폴더 권한을 확인하세요.",
        }
        return messages.get(error_type, raw_message)

    def check_connection(self) -> dict:
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "API key 필요", "연결 확인을 위해 API key를 입력하세요.")
            raise ValueError("API key가 입력되지 않았습니다.")
        mode = str(self.mode_combo.currentData())
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            connection = resolve_genai_connection(
                key,
                mode,
                prompt="Reply with exactly this short phrase: MaintiQ connection ok",
            )
            self.resolved_connection = connection
            public_status = f"연결됨: {provider_label(connection['provider'])} {mode_label(connection['mode'])}"
            self._set_card_value(self.connection_card, public_status, "사용 가능한 모델 자동 선택 완료")
            self.detail_label.setText(
                f"상세 연결 정보: AI 제공자={provider_label(connection['provider'])}, 선택 모델={connection['model']}, 모드={mode_label(connection['mode'])}"
            )
            self.status_label.setText("연결 확인 완료: 새 리포트를 생성할 수 있습니다.")
            record_audit(
                self.actor,
                "desktop_genai_connection_checked",
                "success",
                "ai_report",
                connection["provider"],
                {"provider": connection["provider"], "model": connection["model"], "mode": connection["mode"]},
            )
            return connection
        except Exception as error:
            self.resolved_connection = None
            error_type = classify_report_error(error)
            self._set_card_value(self.connection_card, "연결 실패", "API key, 권한, 모델 접근 가능 여부를 확인하세요.")
            self.detail_label.setText(f"마지막 오류: {self.friendly_error_message(error_type, str(error))}")
            self.status_label.setText("연결 확인 실패: 상세 보기를 눌러 원인을 확인하세요.")
            append_report_history(
                status="error",
                mode=mode,
                template=str(self.template_combo.currentData()),
                length=str(self.length_combo.currentData()),
                error_type=error_type,
                error_message=str(error),
            )
            self.refresh_history()
            record_audit(self.actor, "desktop_genai_connection_checked", "error", "ai_report", "", error_message=str(error))
            show_error(self, "AI 연결 확인 실패", error)
            raise
        finally:
            QApplication.restoreOverrideCursor()

    def _top_risk_context(self) -> list[dict]:
        candidates = [
            OUTPUT_DIR / "scania_product_priority_queue.csv",
            OUTPUT_DIR / "company_risk_priority_queue.csv",
            OUTPUT_DIR / "company_prediction_results.csv",
        ]
        for path in candidates:
            if not path.exists():
                continue
            try:
                df = pd.read_csv(path).head(3)
            except Exception:
                continue
            rows = []
            for _, row in df.iterrows():
                rows.append(
                    {
                        "input_row": row.get("input_row", row.get("priority_rank", "")),
                        "risk_status": row.get("risk_status", ""),
                        "probability": row.get("raw_probability", row.get("failure_window_probability", row.get("calibrated_probability", ""))),
                        "risk_priority_score": row.get("risk_priority_score", ""),
                        "recommendation": row.get("recommendation", ""),
                    }
                )
            return rows
        return []

    def generate_report(self) -> None:
        key = self.key_input.text().strip()
        selected_template = str(self.template_combo.currentData())
        selected_length = str(self.length_combo.currentData())
        if not key:
            QMessageBox.warning(self, "API key 필요", "새 리포트를 생성하려면 API key를 입력하세요.")
            append_report_history(
                status="error",
                template=selected_template,
                length=selected_length,
                error_type="missing_api_key",
                error_message="API key가 입력되지 않았습니다.",
            )
            self.refresh_history()
            return
        context = read_json(OUTPUT_DIR / "ai_report_context.json", {})
        if not context:
            QMessageBox.warning(self, "근거 데이터 없음", "outputs/ai_report_context.json이 필요합니다.")
            append_report_history(
                status="error",
                template=selected_template,
                length=selected_length,
                error_type="missing_context",
                error_message="outputs/ai_report_context.json이 필요합니다.",
            )
            self.refresh_history()
            return
        connection = self.resolved_connection
        if not connection:
            try:
                connection = self.check_connection()
            except Exception:
                return
        provider = str(connection["provider"])
        model = str(connection["model"])
        old_env = with_restored_env(
            ["AI_REPORT_PROVIDER", "GEMINI_API_KEY", "OPENAI_API_KEY", "GEMINI_MODEL", "OPENAI_MODEL", "GEMINI_MODEL_CANDIDATES"]
        )
        report_context = dict(context)
        report_context["report_template"] = selected_template
        report_context["report_length"] = selected_length
        report_context["report_template_note"] = TEMPLATE_NOTES.get(selected_template, "")
        report_context["report_length_note"] = LENGTH_NOTES.get(selected_length, "")
        report_context["top_risk_rows"] = self._top_risk_context()
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            os.environ["AI_REPORT_PROVIDER"] = provider
            if provider == "gemini":
                os.environ["GEMINI_API_KEY"] = key
                os.environ["GEMINI_MODEL_CANDIDATES"] = model
                from predictive_spc import gemini_ai_report

                report, generation_mode = gemini_ai_report(report_context, require_gemini=True)
            else:
                os.environ["OPENAI_API_KEY"] = key
                os.environ["OPENAI_MODEL"] = model
                from predictive_spc import openai_ai_report

                report, generation_mode = openai_ai_report(report_context, require_openai=True)
            if not report.strip():
                raise RuntimeError("빈 응답이 반환되었습니다.")
            snapshot_path = save_report_snapshot(report)
            append_report_history(
                status="success",
                provider=provider,
                mode=str(connection["mode"]),
                model=model,
                template=selected_template,
                length=selected_length,
                report_path=snapshot_path,
                report_text=report,
            )
            self.current_report_path = snapshot_path
            self.report_text.setPlainText(report)
            self.export_button.setEnabled(True)
            self._set_card_value(self.saved_status_card, "AI 리포트 생성 완료", "방금 생성한 리포트")
            self.status_label.setText("새 리포트 생성 완료: 아래 본문과 이력에 저장되었습니다.")
            self.detail_label.setText(
                f"생성 방식: {generation_mode}, 템플릿={self.template_combo.currentText()}, 길이={self.length_combo.currentText()}"
            )
            record_audit(self.actor, "desktop_genai_report_generated", "success", "ai_report", provider, {"model": model})
        except Exception as error:
            error_type = classify_report_error(error)
            append_report_history(
                status="error",
                provider=provider,
                mode=str(connection.get("mode", "")),
                model=model,
                template=selected_template,
                length=selected_length,
                error_type=error_type,
                error_message=str(error),
            )
            self.status_label.setText(f"리포트 생성 실패: {self.friendly_error_message(error_type, str(error))}")
            record_audit(self.actor, "desktop_genai_report_generated", "error", "ai_report", provider, error_message=str(error))
            show_error(self, "AI 리포트 생성 실패", error)
        finally:
            QApplication.restoreOverrideCursor()
            restore_env(old_env)
            self.refresh_history()
