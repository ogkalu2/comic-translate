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
            "skipped": {},
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

    def _localize_batch_skip_action(self, skip_reason: str, error: str) -> str:
        summary = self._sanitize_batch_skip_error(error)
        lowered = summary.lower()

        if self._is_content_flagged_error_text(summary):
            if "ocr" in (skip_reason or "").lower():
                return self.main.tr("Try another text recognition tool")
            if "translator" in (skip_reason or "").lower() or "translation" in (
                skip_reason or ""
            ).lower():
                return self.main.tr("Try another translator")
            return self.main.tr("Try another tool")
        if "insufficient credit" in lowered:
            return self.main.tr("Buy more credits")
        if "timed out" in lowered or "timeout" in lowered:
            return self.main.tr("Try again")
        if (
            "too many requests" in lowered
            or "rate limit" in lowered
            or "429" in lowered
        ):
            return self.main.tr("Wait and try again")
        if (
            "unauthorized" in lowered
            or "invalid api key" in lowered
            or "401" in lowered
            or "403" in lowered
        ):
            return self.main.tr("Check API settings")
        if (
            "connection" in lowered
            or "network" in lowered
            or "name or service not known" in lowered
            or "failed to establish" in lowered
        ):
            return self.main.tr("Check your connection")
        if (
            "bad gateway" in lowered
            or "service unavailable" in lowered
            or "gateway timeout" in lowered
            or "502" in lowered
            or "503" in lowered
            or "504" in lowered
        ):
            return self.main.tr("Try again later")
        if (
            "jsondecodeerror" in lowered
            or "empty json" in lowered
            or "expecting value" in lowered
        ):
            return self.main.tr("Try again")

        if skip_reason == "Text Blocks":
            return ""
        if "ocr" in (skip_reason or "").lower():
            return self.main.tr("Try another text recognition tool")
        if "translator" in (skip_reason or "").lower() or "translation" in (
            skip_reason or ""
        ).lower():
            return self.main.tr("Try another translator")
        return self.main.tr("Try again")

    def _format_batch_skip_reason(self, skip_reason: str, error: str) -> str:
        detail = self._localize_batch_skip_detail(error)
        action = self._localize_batch_skip_action(skip_reason, error)
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
        reason = base_reason
        if detail:
            reason = f"{base_reason}: {detail}"
        if action:
            reason = f"{reason}. {action}."
        return reason

    def register_batch_skip(self, image_path: str, skip_reason: str, error: str):
        report = self._current_batch_report
        if not report:
            return
        if image_path not in report["path_set"]:
            return
        if self._is_user_skip_reason(skip_reason, error):
            return
        if self._is_no_text_detection_skip(skip_reason):
            return

        reason_text = self._format_batch_skip_reason(skip_reason, error)
        existing = report["skipped"].get(image_path)
        if existing is None:
            report["skipped"][image_path] = {
                "image_path": image_path,
                "image_name": os.path.basename(image_path),
                "reasons": [reason_text] if reason_text else [],
            }
            return

        if reason_text and reason_text not in existing["reasons"]:
            existing["reasons"].append(reason_text)

    def finalize_batch_report(self, was_cancelled: bool):
        report = self._current_batch_report
        self._current_batch_report = None
        if not report:
            return None

        total_images = len(report["paths"])
        skipped_entries = sorted(
            report["skipped"].values(),
            key=lambda entry: entry["image_name"].lower(),
        )
        skipped_count = len(skipped_entries)

        finalized = {
            "started_at": report["started_at"],
            "finished_at": datetime.now(),
            "was_cancelled": bool(was_cancelled),
            "total_images": total_images,
            "skipped_count": skipped_count,
            "completed_count": max(0, total_images - skipped_count),
            "skipped_entries": skipped_entries,
        }
        self._latest_batch_report = finalized
        self.main.batch_report_button.setEnabled(True)
        return finalized

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
        item = table.item(row, 0)
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
            self.main.tr("Skipped Images ({0})").format(report["skipped_count"])
        )
        header_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(header_label)

        skipped_entries = report["skipped_entries"]
        if skipped_entries:
            hint = QtWidgets.QLabel(self.main.tr("Double-click a row to open that page."))
            hint.setWordWrap(True)
            layout.addWidget(hint)

            table = QtWidgets.QTableWidget(len(skipped_entries), 2)
            table.setHorizontalHeaderLabels([self.main.tr("Image"), self.main.tr("Reason")])
            table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
            table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setStretchLastSection(True)
            table.horizontalHeader().setSectionResizeMode(
                0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
            table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
            table.setWordWrap(False)
            table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
            table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            visible_rows = min(max(len(skipped_entries), 4), 12)
            table_height = (visible_rows * 28) + 36
            table.setMinimumHeight(table_height)
            table.setMaximumHeight(table_height)

            for row, entry in enumerate(skipped_entries):
                image_item = QtWidgets.QTableWidgetItem(entry["image_name"])
                image_item.setData(QtCore.Qt.ItemDataRole.UserRole, entry["image_path"])
                image_item.setToolTip(entry["image_path"])
                table.setItem(row, 0, image_item)
                reason_item = QtWidgets.QTableWidgetItem(
                    "; ".join(entry["reasons"]) or self.main.tr("Skipped")
                )
                reason_item.setToolTip(reason_item.text())
                table.setItem(row, 1, reason_item)

            table.itemDoubleClicked.connect(
                lambda item, t=table: self._open_report_row_image(t, item.row())
            )
            layout.addWidget(table)
        else:
            empty_label = QtWidgets.QLabel(self.main.tr("No skipped images in this batch."))
            empty_label.setWordWrap(True)
            layout.addWidget(empty_label)

        layout.addStretch()
        return container

    def show_latest_batch_report(self):
        report = self._latest_batch_report
        if report is None:
            MMessage.info(
                text=self.main.tr("No batch report is available yet."),
                parent=self.main,
                duration=5,
                closable=True,
            )
            return

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

    def shutdown(self):
        try:
            if self._batch_report_drawer is not None:
                self._batch_report_drawer.close()
                self._batch_report_drawer = None
        except Exception:
            pass
