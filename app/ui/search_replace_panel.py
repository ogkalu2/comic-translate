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
        QtCore.QTimer.singleShot(0, self._sync_summary_x)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in {
            QtCore.QEvent.Type.Polish,
            QtCore.QEvent.Type.PolishRequest,
            QtCore.QEvent.Type.StyleChange,
            QtCore.QEvent.Type.FontChange,
            QtCore.QEvent.Type.PaletteChange,
        }:
            QtCore.QTimer.singleShot(0, self._sync_summary_x)

    def _sync_summary_x(self):
        """
        Align the *text* in the summary label with the (centered) icon in the
        Find "Previous" button. Dayu theme uses a smaller iconSize than the
        toolbutton size, so the icon is visually inset.
        """
        if not hasattr(self, "summary_label") or not hasattr(self, "prev_btn"):
            return

        contents = self.prev_btn.contentsRect()
        icon = self.prev_btn.iconSize()
        icon_left = contents.left() + max(0, (contents.width() - icon.width()) // 2)
        self.summary_label.setIndent(max(0, int(icon_left)))

    def _apply_latching_toggle_style(self, btn: QtWidgets.QToolButton):
        # Ensure check state is visually persistent (VS Code-like "latched" toggles).
        btn.setAutoRaise(True)
        btn.setStyleSheet(
            """
            QToolButton { padding: 0 4px; border-radius: 4px; }
            QToolButton:hover { background-color: rgba(127, 127, 127, 0.18); }
            QToolButton:checked { background-color: rgba(127, 127, 127, 0.35); }
            """
        )

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        find_row = QtWidgets.QHBoxLayout()
        find_row.setContentsMargins(6, 6, 6, 0)
        find_row.setSpacing(2)

        self.find_input = MLineEdit().small()
        self.find_input.setPlaceholderText(self.tr("Find"))
        self.find_input.returnPressed.connect(self.search_requested)
        self.find_input.textChanged.connect(self._schedule_live_search)

        self.match_case_btn = MToolButton().text_only().small()
        self.match_case_btn.setText("Aa")
        self.match_case_btn.setCheckable(True)
        self.match_case_btn.setToolTip(self.tr("Match case"))
        self._apply_latching_toggle_style(self.match_case_btn)
        self.match_case_btn.toggled.connect(lambda _v: self._schedule_live_search())
        self.match_case_btn.toggled.connect(lambda _v: self.find_input.setFocus())

        self.whole_word_btn = MToolButton().text_only().small()
        self.whole_word_btn.setText("ab")
        self.whole_word_btn.setCheckable(True)
        self.whole_word_btn.setToolTip(self.tr("Match whole word"))
        self._apply_latching_toggle_style(self.whole_word_btn)
        self.whole_word_btn.toggled.connect(lambda _v: self._schedule_live_search())
        self.whole_word_btn.toggled.connect(lambda _v: self.find_input.setFocus())

        self.regex_btn = MToolButton().text_only().small()
        self.regex_btn.setText(".*")
        self.regex_btn.setCheckable(True)
        self.regex_btn.setToolTip(self.tr("Use regular expression"))
        self._apply_latching_toggle_style(self.regex_btn)
        self.regex_btn.toggled.connect(lambda _v: self._schedule_live_search())
        self.regex_btn.toggled.connect(lambda _v: self.find_input.setFocus())

        # Put ONLY the toggles inside the Find bar (VS Code-like).
        find_suffix = QtWidgets.QWidget()
        find_suffix.setStyleSheet("background: transparent;")
        find_suffix_lay = QtWidgets.QHBoxLayout(find_suffix)
        find_suffix_lay.setContentsMargins(0, 0, 0, 0)
        find_suffix_lay.setSpacing(2)
        find_suffix_lay.addWidget(self.match_case_btn)
        find_suffix_lay.addWidget(self.whole_word_btn)
        find_suffix_lay.addWidget(self.regex_btn)
        find_suffix.setFixedWidth(find_suffix.sizeHint().width())
        self.find_input.set_suffix_widget(find_suffix)

        self.prev_btn = MToolButton().icon_only().svg("up_fill.svg").small()
        self.prev_btn.setToolTip(self.tr("Previous match (Shift+F3)"))
        self.prev_btn.clicked.connect(self.prev_requested)
        self.prev_btn.clicked.connect(lambda: self.find_input.setFocus())

        self.next_btn = MToolButton().icon_only().svg("down_fill.svg").small()
        self.next_btn.setToolTip(self.tr("Next match (F3)"))
        self.next_btn.clicked.connect(self.next_requested)
        self.next_btn.clicked.connect(lambda: self.find_input.setFocus())

        self.clear_btn = MToolButton().icon_only().svg("close_line.svg").small()
        self.clear_btn.setToolTip(self.tr("Clear"))
        self.clear_btn.clicked.connect(self._clear_find)
        self.clear_btn.clicked.connect(lambda: self.find_input.setFocus())

        find_nav = QtWidgets.QWidget()
        find_nav.setStyleSheet("background: transparent;")
        find_nav_lay = QtWidgets.QHBoxLayout(find_nav)
        find_nav_lay.setContentsMargins(0, 0, 0, 0)
        find_nav_lay.setSpacing(2)
        find_nav_lay.addWidget(self.prev_btn)
        find_nav_lay.addWidget(self.next_btn)
        find_nav_lay.addWidget(self.clear_btn)
        find_nav_width = find_nav.sizeHint().width()
        find_nav.setFixedWidth(find_nav_width)

        find_row.addWidget(self.find_input, 1)
        find_row.addWidget(find_nav)
        layout.addLayout(find_row)

        self.summary_label = QtWidgets.QLabel(self.tr("0 results"))
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.summary_label.setStyleSheet("color: #999999;")

        replace_row = QtWidgets.QHBoxLayout()
        replace_row.setContentsMargins(6, 0, 6, 0)
        replace_row.setSpacing(2)

        self.replace_input = MLineEdit().small()
        self.replace_input.setPlaceholderText(self.tr("Replace"))
        self.replace_input.returnPressed.connect(self.replace_requested)

        self.replace_btn = MToolButton().icon_only().svg("replace.svg").small()
        self.replace_btn.setToolTip(self.tr("Replace"))
        self._apply_latching_toggle_style(self.replace_btn)
        self.replace_btn.clicked.connect(self.replace_requested)
        self.replace_btn.clicked.connect(lambda: self.replace_input.setFocus())

        self.replace_all_btn = MToolButton().icon_only().svg("replace-all.svg").small()
        self.replace_all_btn.setToolTip(self.tr("Replace All"))
        self._apply_latching_toggle_style(self.replace_all_btn)
        self.replace_all_btn.clicked.connect(self.replace_all_requested)
        self.replace_all_btn.clicked.connect(lambda: self.replace_input.setFocus())

        # Put the replace actions inside the Replace bar (VS Code-like).
        replace_suffix = QtWidgets.QWidget()
        replace_suffix.setStyleSheet("background: transparent;")
        replace_suffix_lay = QtWidgets.QHBoxLayout(replace_suffix)
        replace_suffix_lay.setContentsMargins(0, 0, 0, 0)
        replace_suffix_lay.setSpacing(2)
        replace_suffix_lay.addWidget(self.replace_btn)
        replace_suffix_lay.addWidget(self.replace_all_btn)
        replace_suffix.setFixedWidth(replace_suffix.sizeHint().width())
        self.replace_input.set_suffix_widget(replace_suffix)

        replace_row.addWidget(self.replace_input, 1)

        # Keep Find and Replace bars the same width by reserving space for the
        # find nav buttons (prev/next/clear) on the replace row, and show the
        # results count there.
        replace_right = QtWidgets.QWidget()
        # Use the same fixed width as the Find nav so the left edge (x position)
        # aligns between rows.
        replace_right.setFixedWidth(find_nav_width)
        replace_right_lay = QtWidgets.QVBoxLayout(replace_right)
        replace_right_lay.setContentsMargins(0, 0, 0, 0)
        replace_right_lay.setSpacing(0)
        replace_right_lay.addWidget(self.summary_label)
        replace_right_lay.addStretch(1)
        replace_row.addWidget(replace_right)
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

        meta_row.addWidget(self.scope_combo)
        meta_row.addWidget(self.field_combo)
        meta_row.addStretch(1)
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
