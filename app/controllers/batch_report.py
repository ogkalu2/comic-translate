from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6 import QtCore, QtWidgets

from app.ui.dayu_widgets.drawer import MDrawer
from app.ui.dayu_widgets.message import MMessage

if TYPE_CHECKING:
    from controller import ComicTranslate


class BatchReportController:
    def __init__(self, main: ComicTranslate):
        self.main = main
        self._current_batch_report = None
        self._latest_batch_report = None
        self._batch_report_drawer: MDrawer | None = None
        self._error_registry: dict[str, dict] = {}

    def _refresh_latest_report(
        self,
        *,
        update_buttons: bool,
        was_cancelled: bool | None = None,
    ) -> dict:
        now = datetime.now()
        current_report = self._current_batch_report or {}
        latest_report = self._latest_batch_report or {}
        skipped_entries = self._build_current_error_entries()
        skipped_count = len(skipped_entries)

        report = {
            "started_at": current_report.get(
                "started_at",
                latest_report.get("started_at", now),
            ),
            "finished_at": now,
            "was_cancelled": bool(
                latest_report.get("was_cancelled", False)
                if was_cancelled is None else was_cancelled
            ),
            "total_images": len(self.main.image_files),
            "batch_total_images": len(current_report.get("paths", [])),
            "skipped_count": skipped_count,
            "completed_count": max(0, len(self.main.image_files) - skipped_count),
            "skipped_entries": skipped_entries,
        }
        self._latest_batch_report = report

        if update_buttons:
            self.main.batch_report_button.setEnabled(True)
            self.main.error_pages_button.setEnabled(skipped_count > 0)

        if self._batch_report_drawer is not None:
            try:
                self._batch_report_drawer.set_widget(
                    self._build_batch_report_widget(report)
                )
            except Exception:
                pass

        return report

    def start_batch_report(self, batch_paths: list[str]):
        tracked_paths = [
            path
            for path in batch_paths
            if not self.main.image_states.get(path, {}).get("skip", False)
        ]
        self._current_batch_report = {
            "started_at": datetime.now(),
            "paths": tracked_paths,
            "path_set": set(tracked_paths),
            "path_to_page_number": {
                path: index + 1 for index, path in enumerate(tracked_paths)
            },
            "skipped": {},
        }
        self.main.batch_report_button.setEnabled(False)
        self.main.error_pages_button.setEnabled(False)

    def _make_error_entry(self, image_path: str, reasons: list[str]) -> dict:
        page_number = 0
        if image_path in self.main.image_files:
            page_number = self.main.image_files.index(image_path) + 1
        return {
            "image_path": image_path,
            "image_name": os.path.basename(image_path),
            "page_number": page_number,
            "reasons": list(reasons),
        }

    def _sanitize_batch_skip_error(self, error: str) -> str:
        if not error:
            return ""
        for raw_line in str(error).splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.lower().startswith("traceback"):
                break
            if line.startswith('File "') or line.startswith("File '"):
                continue
            if line.startswith("During handling of the above exception"):
                continue
            if len(line) > 180:
                return f"{line[:177]}..."
            return line
        return ""

    def _is_content_flagged_error_text(self, error: str) -> bool:
        lowered = (error or "").lower()
        return (
            "flagged as unsafe" in lowered
            or "content was flagged" in lowered
            or "safety filters" in lowered
        )

    def _is_user_skip_reason(self, skip_reason: str, error: str = "") -> bool:
        text = f"{skip_reason} {error}".lower()
        return ("user-skipped" in text) or ("user skipped" in text)

    def _is_no_text_detection_skip(self, skip_reason: str) -> bool:
        return skip_reason == "Text Blocks"

    def _localize_batch_skip_detail(self, error: str) -> str:
        summary = self._sanitize_batch_skip_error(error)
        if not summary:
            return ""

        lowered = summary.lower()
        if self._is_content_flagged_error_text(summary):
            return self.main.tr("The AI provider flagged this content")
        if "insufficient credit" in lowered:
            return self.main.tr("Insufficient credits")
        if "timed out" in lowered or "timeout" in lowered:
            return self.main.tr("Request timed out")
        if (
            "too many requests" in lowered
            or "rate limit" in lowered
            or "429" in lowered
        ):
            return self.main.tr("Rate limited by provider")
        if (
            "unauthorized" in lowered
            or "invalid api key" in lowered
            or "401" in lowered
            or "403" in lowered
        ):
            return self.main.tr("Authentication failed")
        if (
            "connection" in lowered
            or "network" in lowered
            or "name or service not known" in lowered
            or "failed to establish" in lowered
        ):
            return self.main.tr("Network or connection error")
        if (
            "bad gateway" in lowered
            or "service unavailable" in lowered
            or "gateway timeout" in lowered
            or "502" in lowered
            or "503" in lowered
            or "504" in lowered
        ):
            return self.main.tr("Provider unavailable")
        if (
            "jsondecodeerror" in lowered
            or "empty json" in lowered
            or "expecting value" in lowered
        ):
            return self.main.tr("Invalid translation response")
        return self.main.tr("Unexpected tool error")

    def _format_batch_skip_reason(self, skip_reason: str, error: str) -> str:
        detail = self._localize_batch_skip_detail(error)
        reason_map = {
            "Text Blocks": self.main.tr("No text blocks detected"),
            "OCR": self.main.tr("Text recognition failed"),
            "Translator": self.main.tr("Translation failed"),
            "OCR Chunk Failed": self.main.tr("Webtoon text recognition chunk failed"),
            "Translation Chunk Failed": self.main.tr(
                "Webtoon translation chunk failed"
            ),
        }
        base_reason = reason_map.get(skip_reason, self.main.tr("Page processing failed"))
        return f"{base_reason}: {detail}" if detail else base_reason

    def register_batch_skip(self, image_path: str, skip_reason: str, error: str):
        report = self._current_batch_report
        if not report:
            return
        if image_path not in report["path_set"]:
            return
        if self._is_user_skip_reason(skip_reason, error):
            return
        if self._is_no_text_detection_skip(skip_reason):
            self._error_registry.pop(image_path, None)
            self._refresh_latest_report(update_buttons=False)
            return

        reason_text = self._format_batch_skip_reason(skip_reason, error)
        existing = report["skipped"].get(image_path)
        if existing is None:
            entry = self._make_error_entry(
                image_path,
                [reason_text] if reason_text else [],
            )
            entry["page_number"] = report["path_to_page_number"].get(image_path, 0)
            report["skipped"][image_path] = entry
            self._error_registry[image_path] = self._make_error_entry(
                image_path,
                [reason_text] if reason_text else [],
            )
            self._refresh_latest_report(update_buttons=False)
            return

        if reason_text and reason_text not in existing["reasons"]:
            existing["reasons"].append(reason_text)
        self._error_registry[image_path] = self._make_error_entry(
            image_path,
            existing["reasons"],
        )
        self._refresh_latest_report(update_buttons=False)

    def register_batch_success(self, image_path: str):
        if not image_path:
            return
        self._error_registry.pop(image_path, None)
        image_ctrl = getattr(self.main, "image_ctrl", None)
        if image_ctrl is not None:
            try:
                image_ctrl.clear_page_skip_errors_for_paths([image_path])
            except Exception:
                pass
        self._refresh_latest_report(update_buttons=not bool(self._current_batch_report))

    def _build_current_error_entries(self) -> list[dict]:
        active_entries: list[dict] = []
        stale_paths: list[str] = []

        for image_path, entry in self._error_registry.items():
            if image_path not in self.main.image_files:
                stale_paths.append(image_path)
                continue
            active_entries.append(
                self._make_error_entry(image_path, entry.get("reasons", []))
            )

        for image_path in stale_paths:
            self._error_registry.pop(image_path, None)

        active_entries.sort(
            key=lambda entry: (entry.get("page_number", 0), entry["image_name"].lower())
        )
        return active_entries

    def finalize_batch_report(self, was_cancelled: bool):
        report = self._current_batch_report
        self._current_batch_report = None
        if not report:
            return None

        return self._refresh_latest_report(
            update_buttons=True,
            was_cancelled=was_cancelled,
        )

    def _open_image_from_batch_report(self, image_path: str):
        if image_path not in self.main.image_files:
            MMessage.warning(
                text=self.main.tr("This image is not in the current project."),
                parent=self.main,
                duration=5,
                closable=True,
            )
            return

        index = self.main.image_files.index(image_path)
        self.main.show_main_page()
        self.main.page_list.setCurrentRow(index)

    def _open_report_row_image(self, table: QtWidgets.QTableWidget, row: int):
        item = table.item(row, 1)
        if item is None:
            return
        image_path = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not image_path:
            return
        self._open_image_from_batch_report(image_path)

    def _build_batch_report_widget(self, report: dict) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        status_text = self.main.tr("Cancelled") if report["was_cancelled"] else self.main.tr("Completed")
        finished = report["finished_at"].strftime("%Y-%m-%d %H:%M")
        meta_label = QtWidgets.QLabel(
            self.main.tr("{0}  |  Updated {1}").format(status_text, finished)
        )
        meta_label.setStyleSheet("color: rgba(130,130,130,0.95);")
        layout.addWidget(meta_label)

        stats_layout = QtWidgets.QHBoxLayout()
        stats_layout.setSpacing(8)

        def make_stat_card(label: str, value: str) -> QtWidgets.QFrame:
            card = QtWidgets.QFrame()
            card.setObjectName("batchStatCard")
            card_layout = QtWidgets.QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setSpacing(2)

            value_label = QtWidgets.QLabel(value)
            value_label.setObjectName("batchStatValue")
            value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

            label_widget = QtWidgets.QLabel(label)
            label_widget.setObjectName("batchStatLabel")
            label_widget.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

            card_layout.addWidget(value_label)
            card_layout.addWidget(label_widget)
            return card

        stats_layout.addWidget(make_stat_card(self.main.tr("Total"), str(report["total_images"])))
        stats_layout.addWidget(make_stat_card(self.main.tr("Skipped"), str(report["skipped_count"])))
        layout.addLayout(stats_layout)

        container.setStyleSheet(
            "QFrame#batchStatCard { border: 1px solid rgba(128,128,128,0.35); border-radius: 8px; }"
            "QLabel#batchStatValue { font-size: 18px; font-weight: 600; }"
            "QLabel#batchStatLabel { color: rgba(140,140,140,0.95); font-size: 11px; }"
        )

        header_label = QtWidgets.QLabel(
            self.main.tr("Pages With Errors ({0})").format(report["skipped_count"])
        )
        header_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(header_label)

        skipped_entries = report["skipped_entries"]
        if skipped_entries:
            hint = QtWidgets.QLabel(
                self.main.tr("Double-click a row to open that page, or use the error-pages button.")
            )
            hint.setWordWrap(True)
            layout.addWidget(hint)

            table = QtWidgets.QTableWidget(len(skipped_entries), 3)
            table.setHorizontalHeaderLabels(
                [self.main.tr("Page"), self.main.tr("Image"), self.main.tr("Error")]
            )
            table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
            table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setStretchLastSection(True)
            table.horizontalHeader().setSectionResizeMode(
                0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(
                1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
            table.setWordWrap(False)
            table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
            table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            visible_rows = min(max(len(skipped_entries), 4), 12)
            table_height = (visible_rows * 28) + 36
            table.setMinimumHeight(table_height)
            table.setMaximumHeight(table_height)

            for row, entry in enumerate(skipped_entries):
                page_item = QtWidgets.QTableWidgetItem(str(entry.get("page_number", "")))
                page_item.setTextAlignment(
                    QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter
                )
                table.setItem(row, 0, page_item)
                image_item = QtWidgets.QTableWidgetItem(entry["image_name"])
                image_item.setData(QtCore.Qt.ItemDataRole.UserRole, entry["image_path"])
                image_item.setToolTip(entry["image_path"])
                table.setItem(row, 1, image_item)
                reason_item = QtWidgets.QTableWidgetItem(
                    "; ".join(entry["reasons"]) or self.main.tr("Skipped")
                )
                reason_item.setToolTip(reason_item.text())
                table.setItem(row, 2, reason_item)

            table.itemDoubleClicked.connect(
                lambda item, t=table: self._open_report_row_image(t, item.row())
            )
            layout.addWidget(table)
        else:
            empty_label = QtWidgets.QLabel(self.main.tr("No pages with errors right now."))
            empty_label.setWordWrap(True)
            layout.addWidget(empty_label)

        layout.addStretch()
        return container

    def show_latest_batch_report(self):
        report = self._refresh_latest_report(update_buttons=True)

        if self._batch_report_drawer is not None:
            try:
                self._batch_report_drawer.close()
            except Exception:
                pass
            self._batch_report_drawer = None

        drawer = MDrawer(self.main.tr("Batch Report"), parent=self.main).right()
        drawer.setFixedWidth(max(460, int(self.main.width() * 0.42)))
        drawer.set_widget(self._build_batch_report_widget(report))
        drawer.sig_closed.connect(lambda: setattr(self, "_batch_report_drawer", None))
        self._batch_report_drawer = drawer
        drawer.show()

    def select_pages_with_errors(self):
        report = self._refresh_latest_report(update_buttons=True)
        if not report["skipped_entries"]:
            MMessage.info(
                text=self.main.tr("No pages with errors are available."),
                parent=self.main,
                duration=5,
                closable=True,
            )
            return

        selected_rows: list[int] = []
        for entry in report["skipped_entries"]:
            image_path = entry["image_path"]
            if image_path in self.main.image_files:
                selected_rows.append(self.main.image_files.index(image_path))

        if not selected_rows:
            MMessage.info(
                text=self.main.tr("The error pages are not in the current project."),
                parent=self.main,
                duration=5,
                closable=True,
            )
            return

        self.main.show_main_page()
        self.main.page_list.blockSignals(True)
        self.main.page_list.clearSelection()
        for row in selected_rows:
            item = self.main.page_list.item(row)
            if item is not None:
                item.setSelected(True)
        first_row = selected_rows[0]
        self.main.page_list.setCurrentRow(first_row)
        self.main.page_list.blockSignals(False)

        self.main.image_ctrl.on_selection_changed(selected_rows)
        self.main.image_ctrl.on_card_selected(self.main.page_list.item(first_row), None)

    def reset(self):
        self._current_batch_report = None
        self._latest_batch_report = None
        self._error_registry = {}
        try:
            if self._batch_report_drawer is not None:
                self._batch_report_drawer.close()
        except Exception:
            pass
        self._batch_report_drawer = None
        self.main.batch_report_button.setEnabled(False)
        self.main.error_pages_button.setEnabled(False)

    def shutdown(self):
        self.reset()
