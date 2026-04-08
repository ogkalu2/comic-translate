from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass

from PySide6 import QtCore, QtWidgets


@dataclass
class ExportChapterRow:
    page_index: int
    file_path: str
    file_name: str
    group_name: str


class ExportChaptersDialog(QtWidgets.QDialog):
    def __init__(
        self,
        rows: list[ExportChapterRow],
        output_dir: str,
        extension: str,
        filename_builder,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Partition Export"))
        self.resize(820, 500)
        self._rows = rows
        self._initial_groups = [row.group_name for row in rows]
        self._output_dir = output_dir
        self._extension = extension
        self._filename_builder = filename_builder
        self._updating_table = False

        layout = QtWidgets.QVBoxLayout(self)

        note = QtWidgets.QLabel(
            self.tr(
                "Pages with the same chapter name are exported together. "
                "Edit the Chapter column to merge or split chapters."
            )
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        folder_row = QtWidgets.QHBoxLayout()
        folder_row.addWidget(QtWidgets.QLabel(self.tr("Output folder"), self))
        self.output_dir_edit = QtWidgets.QLineEdit(output_dir or os.path.expanduser("~"), self)
        self.output_dir_edit.setReadOnly(True)
        folder_row.addWidget(self.output_dir_edit, 1)
        self.browse_folder_button = QtWidgets.QPushButton(self.tr("Browse"), self)
        self.browse_folder_button.clicked.connect(self._browse_output_dir)
        folder_row.addWidget(self.browse_folder_button)
        layout.addLayout(folder_row)

        bulk_row = QtWidgets.QHBoxLayout()
        bulk_row.addWidget(QtWidgets.QLabel(self.tr("Selected pages"), self))
        self.bulk_group_edit = QtWidgets.QLineEdit(self)
        self.bulk_group_edit.setPlaceholderText(self.tr("New chapter name"))
        bulk_row.addWidget(self.bulk_group_edit, 1)
        self.apply_bulk_button = QtWidgets.QPushButton(self.tr("Apply"), self)
        self.apply_bulk_button.clicked.connect(self._apply_group_to_selected_rows)
        bulk_row.addWidget(self.apply_bulk_button)
        layout.addLayout(bulk_row)

        self.table = QtWidgets.QTableWidget(len(rows), 3, self)
        self.table.setHorizontalHeaderLabels([
            self.tr("Page"),
            self.tr("File"),
            self.tr("Chapter"),
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table, 1)

        summary_label = QtWidgets.QLabel(self.tr("Export targets"))
        layout.addWidget(summary_label)

        self.summary_list = QtWidgets.QListWidget(self)
        self.summary_list.setMinimumHeight(64)
        self.summary_list.setMaximumHeight(110)
        layout.addWidget(self.summary_list)

        button_row = QtWidgets.QHBoxLayout()
        self.reset_button = QtWidgets.QPushButton(self.tr("Reset Chapters"), self)
        self.reset_button.clicked.connect(self._reset_groups)
        button_row.addWidget(self.reset_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._populate_table()
        self._refresh_summary()

    def _populate_table(self) -> None:
        self._updating_table = True
        try:
            for row_idx, row in enumerate(self._rows):
                page_item = QtWidgets.QTableWidgetItem(str(row.page_index + 1))
                page_item.setFlags(page_item.flags() & ~QtCore.Qt.ItemIsEditable)
                file_item = QtWidgets.QTableWidgetItem(row.file_name)
                file_item.setFlags(file_item.flags() & ~QtCore.Qt.ItemIsEditable)
                chapter_item = QtWidgets.QTableWidgetItem(row.group_name)

                self.table.setItem(row_idx, 0, page_item)
                self.table.setItem(row_idx, 1, file_item)
                self.table.setItem(row_idx, 2, chapter_item)
        finally:
            self._updating_table = False

    def _on_item_changed(self, item: QtWidgets.QTableWidgetItem) -> None:
        if self._updating_table or item.column() != 2:
            return
        row = item.row()
        self._rows[row].group_name = item.text().strip()
        self._refresh_summary()

    def _browse_output_dir(self) -> None:
        selected_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("Select Export Folder"),
            self.output_dir_edit.text() or os.path.expanduser("~"),
        )
        if selected_dir:
            self.output_dir_edit.setText(selected_dir)

    def _apply_group_to_selected_rows(self) -> None:
        chapter_name = self.bulk_group_edit.text().strip()
        if not chapter_name:
            return
        selected_rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        if not selected_rows:
            return
        self._updating_table = True
        try:
            for row_idx in selected_rows:
                self.table.item(row_idx, 2).setText(chapter_name)
                self._rows[row_idx].group_name = chapter_name
        finally:
            self._updating_table = False
        self._refresh_summary()

    def _chapter_names(self) -> list[str]:
        names: list[str] = []
        for row_idx, row in enumerate(self._rows):
            item = self.table.item(row_idx, 2)
            names.append((item.text() if item else row.group_name).strip())
        return names

    def _refresh_summary(self) -> None:
        self.summary_list.clear()
        chapter_names = self._chapter_names()
        counts = Counter(name for name in chapter_names if name)
        used_names: set[str] = set()
        for chapter_name in sorted(counts):
            output_name = self._filename_builder(chapter_name, self._extension, used_names)
            self.summary_list.addItem(f"{output_name} ({counts[chapter_name]} pages)")

    def _reset_groups(self) -> None:
        self._updating_table = True
        try:
            for row_idx, group_name in enumerate(self._initial_groups):
                self.table.item(row_idx, 2).setText(group_name)
                self._rows[row_idx].group_name = group_name
        finally:
            self._updating_table = False
        self._refresh_summary()

    def _accept_if_valid(self) -> None:
        output_dir = self.output_dir_edit.text().strip()
        if not output_dir or not os.path.isdir(output_dir):
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("Output Folder Required"),
                self.tr("Choose an existing output folder."),
            )
            return
        for row_idx, chapter_name in enumerate(self._chapter_names()):
            if chapter_name:
                continue
            self.table.setCurrentCell(row_idx, 2)
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("Chapter Name Required"),
                self.tr("Each page must belong to a non-empty chapter."),
            )
            return
        self.accept()

    def chapter_names_by_path(self) -> dict[str, str]:
        return {
            row.file_path: chapter_name
            for row, chapter_name in zip(self._rows, self._chapter_names())
        }

    def selected_output_dir(self) -> str:
        return self.output_dir_edit.text().strip()
