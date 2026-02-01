from __future__ import annotations

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt

from app.ui.dayu_widgets.combo_box import MComboBox
from app.ui.dayu_widgets.expanding_text_edit import MExpandingTextEdit
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

        # ─── FIND ROW ───────────────────────────────────────────────────────
        find_row = QtWidgets.QHBoxLayout()
        find_row.setContentsMargins(6, 6, 6, 0)
        find_row.setSpacing(2)

        # Container for find input + inline toggle buttons
        find_container = QtWidgets.QFrame()
        find_container.setObjectName("findContainer")
        find_container.setStyleSheet("""
            #findContainer {
                border: 1px solid rgba(127, 127, 127, 0.3);
                border-radius: 4px;
                background: transparent;
            }
        """)
        find_container_layout = QtWidgets.QHBoxLayout(find_container)
        find_container_layout.setContentsMargins(4, 2, 4, 2)
        find_container_layout.setSpacing(2)

        self.find_input = MExpandingTextEdit(max_lines=4)
        self.find_input.setPlaceholderText(self.tr("Find"))
        self.find_input.setStyleSheet("""
            QPlainTextEdit {
                border: none;
                background: transparent;
                padding: 0;
                margin: 0;
            }
        """)
        self.find_input.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        # VS Code-like: Enter navigates matches; searching is live as you type.
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

        # Toggle buttons inline to the right of input (stays at top when input expands)
        find_toggles = QtWidgets.QWidget()
        find_toggles.setStyleSheet("background: transparent;")
        find_toggles_lay = QtWidgets.QHBoxLayout(find_toggles)
        find_toggles_lay.setContentsMargins(0, 0, 0, 0)
        find_toggles_lay.setSpacing(2)
        find_toggles_lay.addWidget(self.match_case_btn)
        find_toggles_lay.addWidget(self.whole_word_btn)
        find_toggles_lay.addWidget(self.regex_btn)

        find_container_layout.addWidget(self.find_input, 1)
        find_container_layout.addWidget(find_toggles, 0, Qt.AlignmentFlag.AlignTop)

        self.prev_btn = MToolButton().icon_only().svg("up_fill.svg").small()
        self.prev_btn.setToolTip(self.tr("Previous match (Shift+Enter)"))
        self.prev_btn.clicked.connect(self.prev_requested)
        self.prev_btn.clicked.connect(lambda: self.find_input.setFocus())

        self.next_btn = MToolButton().icon_only().svg("down_fill.svg").small()
        self.next_btn.setToolTip(self.tr("Next match (Enter)"))
        self.next_btn.clicked.connect(self.next_requested)
        self.next_btn.clicked.connect(lambda: self.find_input.setFocus())

        self.clear_btn = MToolButton().icon_only().svg("close_line.svg").small()
        self.clear_btn.setToolTip(self.tr("Clear (Esc)"))
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

        find_row.addWidget(find_container, 1)
        find_row.addWidget(find_nav, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(find_row)

        self.summary_label = QtWidgets.QLabel(self.tr("0 results"))
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.summary_label.setStyleSheet("color: #999999;")

        # ─── REPLACE ROW ────────────────────────────────────────────────────
        replace_row = QtWidgets.QHBoxLayout()
        replace_row.setContentsMargins(6, 0, 6, 0)
        replace_row.setSpacing(2)

        # Container for replace input + inline action buttons
        replace_container = QtWidgets.QFrame()
        replace_container.setObjectName("replaceContainer")
        replace_container.setStyleSheet("""
            #replaceContainer {
                border: 1px solid rgba(127, 127, 127, 0.3);
                border-radius: 4px;
                background: transparent;
            }
        """)
        replace_container_layout = QtWidgets.QHBoxLayout(replace_container)
        replace_container_layout.setContentsMargins(4, 2, 4, 2)
        replace_container_layout.setSpacing(2)

        self.replace_input = MExpandingTextEdit(max_lines=4)
        self.replace_input.setPlaceholderText(self.tr("Replace"))
        self.replace_input.setStyleSheet("""
            QPlainTextEdit {
                border: none;
                background: transparent;
                padding: 0;
                margin: 0;
            }
        """)
        self.replace_input.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
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

        # Action buttons inline to the right of input (stays at top when input expands)
        replace_actions = QtWidgets.QWidget()
        replace_actions.setStyleSheet("background: transparent;")
        replace_actions_lay = QtWidgets.QHBoxLayout(replace_actions)
        replace_actions_lay.setContentsMargins(0, 0, 0, 0)
        replace_actions_lay.setSpacing(2)
        replace_actions_lay.addWidget(self.replace_btn)
        replace_actions_lay.addWidget(self.replace_all_btn)

        replace_container_layout.addWidget(self.replace_input, 1)
        replace_container_layout.addWidget(replace_actions, 0, Qt.AlignmentFlag.AlignTop)

        replace_row.addWidget(replace_container, 1)

        # Nav placeholder to align with find row
        replace_nav_placeholder = QtWidgets.QWidget()
        replace_nav_placeholder.setFixedWidth(find_nav_width)
        replace_row.addWidget(replace_nav_placeholder, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(replace_row)

        # Summary label on its own row so it doesn't get cut off
        summary_row = QtWidgets.QHBoxLayout()
        summary_row.setContentsMargins(6, 2, 6, 0)
        summary_row.addWidget(self.summary_label)
        summary_row.addStretch()
        layout.addLayout(summary_row)

        meta_row = QtWidgets.QHBoxLayout()
        meta_row.setContentsMargins(6, 0, 6, 0)

        self.scope_combo = MComboBox().small()
        self.scope_combo.addItem(self.tr("Current Image"), userData="current")
        self.scope_combo.addItem(self.tr("All Images"), userData="all")
        self.scope_combo.setToolTip(self.tr("Search scope (Webtoon: Current image searches visible area + buffer)"))
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
        self.results_tree.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.results_tree.setHeaderHidden(True)
        self.results_tree.setRootIsDecorated(True)
        self.results_tree.setUniformRowHeights(True)
        self.results_tree.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.results_tree.itemActivated.connect(self._emit_activated)
        self.results_tree.itemClicked.connect(self._emit_activated)
        self.results_tree.setMinimumHeight(90)
        layout.addWidget(self.results_tree, 1)

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
