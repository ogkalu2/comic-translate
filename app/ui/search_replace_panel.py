from __future__ import annotations

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt

from app.ui.dayu_widgets.combo_box import MComboBox
from app.ui.dayu_widgets.line_edit import MLineEdit
from app.ui.dayu_widgets.tool_button import MToolButton
from app.ui.settings.utils import set_combo_box_width


class SearchReplacePanel(QtWidgets.QWidget):
    """
    VS Code-inspired search/replace sidebar for MTPE.

    Public attributes used by controllers:
      - find_input, replace_input
      - match_case_btn, whole_word_btn, regex_btn
      - scope_combo, field_combo
      - summary_label, status_label, results_tree
    """

    search_requested = QtCore.Signal()
    next_requested = QtCore.Signal()
    prev_requested = QtCore.Signal()
    replace_requested = QtCore.Signal()
    replace_all_requested = QtCore.Signal()
    result_activated = QtCore.Signal(object)  # SearchMatch

    def __init__(self, parent=None):
        super().__init__(parent)
        self._live_timer = QtCore.QTimer(self)
        self._live_timer.setSingleShot(True)
        self._live_timer.setInterval(250)
        self._live_timer.timeout.connect(self.search_requested)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        find_row = QtWidgets.QHBoxLayout()
        find_row.setContentsMargins(6, 6, 6, 0)
        find_row.setSpacing(4)

        self.find_input = MLineEdit().small()
        self.find_input.setPlaceholderText(self.tr("Find"))
        self.find_input.returnPressed.connect(self.search_requested)
        self.find_input.textChanged.connect(self._schedule_live_search)

        self.match_case_btn = MToolButton().text_only().small()
        self.match_case_btn.setText("Aa")
        self.match_case_btn.setCheckable(True)
        self.match_case_btn.setToolTip(self.tr("Match case"))
        self.match_case_btn.toggled.connect(lambda _v: self._schedule_live_search())

        self.whole_word_btn = MToolButton().text_only().small()
        self.whole_word_btn.setText("ab")
        self.whole_word_btn.setCheckable(True)
        self.whole_word_btn.setToolTip(self.tr("Match whole word"))
        self.whole_word_btn.toggled.connect(lambda _v: self._schedule_live_search())

        self.regex_btn = MToolButton().text_only().small()
        self.regex_btn.setText(".*")
        self.regex_btn.setCheckable(True)
        self.regex_btn.setToolTip(self.tr("Use regular expression"))
        self.regex_btn.toggled.connect(lambda _v: self._schedule_live_search())

        self.prev_btn = MToolButton().icon_only().svg("up_fill.svg").small()
        self.prev_btn.setToolTip(self.tr("Previous match (Shift+F3)"))
        self.prev_btn.clicked.connect(self.prev_requested)

        self.next_btn = MToolButton().icon_only().svg("down_fill.svg").small()
        self.next_btn.setToolTip(self.tr("Next match (F3)"))
        self.next_btn.clicked.connect(self.next_requested)

        self.clear_btn = MToolButton().icon_only().svg("close_line.svg").small()
        self.clear_btn.setToolTip(self.tr("Clear"))
        self.clear_btn.clicked.connect(self._clear_find)

        find_row.addWidget(self.find_input, 1)
        find_row.addWidget(self.match_case_btn)
        find_row.addWidget(self.whole_word_btn)
        find_row.addWidget(self.regex_btn)
        find_row.addWidget(self.prev_btn)
        find_row.addWidget(self.next_btn)
        find_row.addWidget(self.clear_btn)
        layout.addLayout(find_row)

        replace_row = QtWidgets.QHBoxLayout()
        replace_row.setContentsMargins(6, 0, 6, 0)
        replace_row.setSpacing(4)

        self.replace_input = MLineEdit().small()
        self.replace_input.setPlaceholderText(self.tr("Replace"))
        self.replace_input.returnPressed.connect(self.replace_requested)

        self.replace_btn = MToolButton().text_only().small()
        self.replace_btn.setText(self.tr("Replace"))
        self.replace_btn.clicked.connect(self.replace_requested)

        self.replace_all_btn = MToolButton().text_only().small()
        self.replace_all_btn.setText(self.tr("All"))
        self.replace_all_btn.clicked.connect(self.replace_all_requested)

        replace_row.addWidget(self.replace_input, 1)
        replace_row.addWidget(self.replace_btn)
        replace_row.addWidget(self.replace_all_btn)
        layout.addLayout(replace_row)

        meta_row = QtWidgets.QHBoxLayout()
        meta_row.setContentsMargins(6, 0, 6, 0)

        self.scope_combo = MComboBox().small()
        self.scope_combo.addItem(self.tr("Current image"), userData="current")
        self.scope_combo.addItem(self.tr("All images"), userData="all")
        self.scope_combo.setToolTip(self.tr("Search scope"))
        self.scope_combo.currentIndexChanged.connect(lambda _i: self._schedule_live_search())

        self.field_combo = MComboBox().small()
        self.field_combo.addItem(self.tr("Target"), userData="target")
        self.field_combo.addItem(self.tr("Source"), userData="source")
        self.field_combo.setToolTip(self.tr("Search field"))
        self.field_combo.currentIndexChanged.connect(lambda _i: self._schedule_live_search())

        self.summary_label = QtWidgets.QLabel(self.tr("0 results"))
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        meta_row.addWidget(self.scope_combo)
        meta_row.addWidget(self.field_combo)
        meta_row.addWidget(self.summary_label, 1)
        layout.addLayout(meta_row)

        self.status_label = QtWidgets.QLabel(self.tr("Ready"))
        self.status_label.setStyleSheet("color: #999999;")
        self.status_label.setContentsMargins(6, 0, 6, 0)
        layout.addWidget(self.status_label)

        self.results_tree = QtWidgets.QTreeWidget()
        self.results_tree.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.results_tree.setHeaderHidden(True)
        self.results_tree.setRootIsDecorated(True)
        self.results_tree.setUniformRowHeights(True)
        self.results_tree.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.results_tree.itemActivated.connect(self._emit_activated)
        self.results_tree.itemClicked.connect(self._emit_activated)
        self.results_tree.setMinimumHeight(90)
        self.results_tree.setMaximumHeight(220)
        layout.addWidget(self.results_tree)

        # Make combos wide enough for their longest entries.
        set_combo_box_width(
            self.scope_combo, [self.scope_combo.itemText(i) for i in range(self.scope_combo.count())], padding=40
        )
        set_combo_box_width(
            self.field_combo, [self.field_combo.itemText(i) for i in range(self.field_combo.count())], padding=40
        )

    def _schedule_live_search(self, *_args):
        if self._live_timer.isActive():
            self._live_timer.stop()
        self._live_timer.start()

    def _clear_find(self):
        self.find_input.clear()
        self.set_results([], 0, 0)
        self.set_status(self.tr("Ready"))

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_results(self, matches: list, images_with_hits: int, total_hits: int):
        self.results_tree.clear()
        if total_hits == 0:
            self.summary_label.setText(self.tr("0 results"))
            return
        self.summary_label.setText(self.tr("{0} results in {1} image(s)").format(total_hits, images_with_hits))

        by_file: dict[str, list] = {}
        for m in matches:
            by_file.setdefault(m.key.file_path, []).append(m)

        for file_path, file_matches in by_file.items():
            top = QtWidgets.QTreeWidgetItem([f"{QtCore.QFileInfo(file_path).fileName()} ({len(file_matches)})"])
            top.setData(0, Qt.ItemDataRole.UserRole, None)
            self.results_tree.addTopLevelItem(top)

            for m in file_matches:
                child = QtWidgets.QTreeWidgetItem([f"{self.tr('Block')} {m.block_index_hint + 1}: {m.preview}"])
                child.setData(0, Qt.ItemDataRole.UserRole, m)
                top.addChild(child)

            top.setExpanded(True)

        self.results_tree.resizeColumnToContents(0)

    def select_match(self, match):
        root_count = self.results_tree.topLevelItemCount()
        for i in range(root_count):
            top = self.results_tree.topLevelItem(i)
            for j in range(top.childCount()):
                child = top.child(j)
                m = child.data(0, Qt.ItemDataRole.UserRole)
                if m == match:
                    self.results_tree.setCurrentItem(child)
                    self.results_tree.scrollToItem(child)
                    return

    def _emit_activated(self, item, *_args):
        m = item.data(0, Qt.ItemDataRole.UserRole)
        if m is not None:
            self.result_activated.emit(m)
