#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2018.5
# Email : muyanru345@163.com
###################################################################

# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtWidgets

# Import local modules
from .item_model import MSortFilterModel
from .item_model import MTableModel
from .item_view import MBigView
from .item_view import MListView
from .item_view import MTableView
from .item_view import MTreeView
from .line_edit import MLineEdit
from .tool_button import MToolButton


class MItemViewSet(QtWidgets.QWidget):
    sig_double_clicked = QtCore.Signal(QtCore.QModelIndex)
    sig_left_clicked = QtCore.Signal(QtCore.QModelIndex)
    TableViewType = MTableView
    BigViewType = MBigView
    TreeViewType = MTreeView
    ListViewType = MListView

    def __init__(self, view_type=None, parent=None):
        super(MItemViewSet, self).__init__(parent)
        self.main_lay = QtWidgets.QVBoxLayout()
        self.main_lay.setSpacing(5)
        self.main_lay.setContentsMargins(0, 0, 0, 0)

        self.sort_filter_model = MSortFilterModel()
        self.source_model = MTableModel()
        self.sort_filter_model.setSourceModel(self.source_model)
        view_class = view_type or MItemViewSet.TableViewType
        self.item_view = view_class()
        self.item_view.doubleClicked.connect(self.sig_double_clicked)
        self.item_view.pressed.connect(self.slot_left_clicked)
        self.item_view.setModel(self.sort_filter_model)

        self._search_line_edit = MLineEdit().search().small()
        self._search_attr_button = MToolButton().icon_only().svg("down_fill.svg").small()
        self._search_line_edit.set_prefix_widget(self._search_attr_button)
        self._search_line_edit.textChanged.connect(self.sort_filter_model.set_search_pattern)
        self._search_line_edit.setVisible(False)
        self._search_lay = QtWidgets.QHBoxLayout()
        self._search_lay.setContentsMargins(0, 0, 0, 0)
        self._search_lay.addStretch()
        self._search_lay.addWidget(self._search_line_edit)

        self.main_lay.addLayout(self._search_lay)
        self.main_lay.addWidget(self.item_view)
        self.setLayout(self.main_lay)

    @QtCore.Slot(QtCore.QModelIndex)
    def slot_left_clicked(self, start_index):
        button = QtWidgets.QApplication.mouseButtons()
        if button == QtCore.Qt.LeftButton:
            real_index = self.sort_filter_model.mapToSource(start_index)
            self.sig_left_clicked.emit(real_index)

    def set_header_list(self, header_list):
        self.source_model.set_header_list(header_list)
        self.sort_filter_model.set_header_list(header_list)
        self.sort_filter_model.setSourceModel(self.source_model)
        self.source_model.clear()
        self.item_view.set_header_list(header_list)

    @QtCore.Slot()
    def setup_data(self, data_list):
        self.source_model.clear()
        if data_list:
            self.source_model.set_data_list(data_list)

    def get_data(self):
        return self.source_model.get_data_list()

    def searchable(self):
        """Enable search line edit visible."""
        self._search_line_edit.setVisible(True)
        return self

    def insert_widget(self, widget):
        """Use can insert extra widget into search layout."""
        self._search_lay.insertWidget(0, widget)
