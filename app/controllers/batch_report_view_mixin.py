from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from app.ui.dayu_widgets.drawer import MDrawer
from app.ui.dayu_widgets.message import MMessage


class BatchReportViewMixin:
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
        meta_label = QtWidgets.QLabel(self.main.tr("{0}  |  Updated {1}").format(status_text, finished))
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

        header_label = QtWidgets.QLabel(self.main.tr("Pages With Errors ({0})").format(report["skipped_count"]))
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
            table.setHorizontalHeaderLabels([self.main.tr("Page"), self.main.tr("Image"), self.main.tr("Error")])
            table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
            table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setStretchLastSection(True)
            table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
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
                page_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row, 0, page_item)
                image_item = QtWidgets.QTableWidgetItem(entry["image_name"])
                image_item.setData(QtCore.Qt.ItemDataRole.UserRole, entry["image_path"])
                image_item.setToolTip(entry["image_path"])
                table.setItem(row, 1, image_item)
                reason_item = QtWidgets.QTableWidgetItem("; ".join(entry["reasons"]) or self.main.tr("Skipped"))
                reason_item.setToolTip(reason_item.text())
                table.setItem(row, 2, reason_item)

            table.itemDoubleClicked.connect(lambda item, t=table: self._open_report_row_image(t, item.row()))
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
