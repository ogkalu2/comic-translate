#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.3
# Email : muyanru345@163.com
###################################################################

# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import built-in modules
import functools

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtGui
from PySide6 import QtWidgets

# Import local modules
from .menu import MMenu
from . import utils as utils


class MHeaderView(QtWidgets.QHeaderView):
    def __init__(self, orientation, parent=None):
        super(MHeaderView, self).__init__(orientation, parent)
        self.setMovable(True)
        self.setClickable(True)
        self.setSortIndicatorShown(True)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._slot_context_menu)
        self.setDefaultAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.setProperty(
            "orientation",
            "horizontal" if orientation == QtCore.Qt.Horizontal else "vertical",
        )

    # def enterEvent(self, *args, **kwargs):
    #     # 调整表头宽度的 cursor 就被覆盖了
    #     QApplication.setOverrideCursor(Qt.PointingHandCursor)
    #     return super(MHeaderViewPrivate, self).enterEvent(*args, **kwargs)
    #
    # def leaveEvent(self, *args, **kwargs):
    #     QApplication.restoreOverrideCursor()
    #     return super(MHeaderViewPrivate, self).leaveEvent(*args, **kwargs)

    @QtCore.Slot(QtCore.QPoint)
    def _slot_context_menu(self, point):
        context_menu = MMenu(parent=self)
        logical_column = self.logicalIndexAt(point)
        model = utils.real_model(self.model())
        if logical_column >= 0 and model.header_list[logical_column].get("checkable", False):
            action_select_all = context_menu.addAction(self.tr("Select All"))
            action_select_none = context_menu.addAction(self.tr("Select None"))
            action_select_invert = context_menu.addAction(self.tr("Select Invert"))
            action_select_all.triggered.connect(
                functools.partial(self._slot_set_select, logical_column, QtCore.Qt.Checked)
            )
            action_select_none.triggered.connect(
                functools.partial(self._slot_set_select, logical_column, QtCore.Qt.Unchecked)
            )
            action_select_invert.triggered.connect(functools.partial(self._slot_set_select, logical_column, None))
            context_menu.addSeparator()

        fit_action = context_menu.addAction(self.tr("Fit Size"))
        fit_action.triggered.connect(functools.partial(self._slot_set_resize_mode, True))
        context_menu.addSeparator()
        for column in range(self.count()):
            action = context_menu.addAction(model.headerData(column, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole))
            action.setCheckable(True)
            action.setChecked(not self.isSectionHidden(column))
            action.toggled.connect(functools.partial(self._slot_set_section_visible, column))
        context_menu.exec_(QtGui.QCursor.pos() + QtCore.QPoint(10, 10))

    @QtCore.Slot(int, int)
    def _slot_set_select(self, column, state):
        current_model = self.model()
        source_model = utils.real_model(current_model)
        source_model.beginResetModel()
        attr = "{}_checked".format(source_model.header_list[column].get("key"))
        for row in range(current_model.rowCount()):
            real_index = utils.real_index(current_model.index(row, column))
            data_obj = real_index.internalPointer()
            if state is None:
                old_state = utils.get_obj_value(data_obj, attr)
                utils.set_obj_value(
                    data_obj,
                    attr,
                    QtCore.Qt.Unchecked if old_state == QtCore.Qt.Checked else QtCore.Qt.Checked,
                )
            else:
                utils.set_obj_value(data_obj, attr, state)
        source_model.endResetModel()
        source_model.dataChanged.emit(None, None)

    @QtCore.Slot(QtCore.QModelIndex, int)
    def _slot_set_section_visible(self, index, flag):
        self.setSectionHidden(index, not flag)

    @QtCore.Slot(bool)
    def _slot_set_resize_mode(self, flag):
        if flag:
            self.resizeSections(QtWidgets.QHeaderView.ResizeToContents)
        else:
            self.resizeSections(QtWidgets.QHeaderView.Interactive)

    def setClickable(self, flag):
        try:
            QtWidgets.QHeaderView.setSectionsClickable(self, flag)
        except AttributeError:
            QtWidgets.QHeaderView.setClickable(self, flag)

    def setMovable(self, flag):
        try:
            QtWidgets.QHeaderView.setSectionsMovable(self, flag)
        except AttributeError:
            QtWidgets.QHeaderView.setMovable(self, flag)

    def resizeMode(self, index):
        try:
            QtWidgets.QHeaderView.sectionResizeMode(self, index)
        except AttributeError:
            QtWidgets.QHeaderView.resizeMode(self, index)

    def setResizeMode(self, mode):
        try:
            QtWidgets.QHeaderView.setResizeMode(self, mode)
        except AttributeError:
            QtWidgets.QHeaderView.setSectionResizeMode(self, mode)
