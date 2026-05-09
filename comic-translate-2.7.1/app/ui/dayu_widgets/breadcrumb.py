#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.3
# Email : muyanru345@163.com
###################################################################
"""
MBreadcrumb
"""

# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import third-party modules
from PySide6 import QtWidgets

# Import local modules
from .label import MLabel
from .tool_button import MToolButton


class MBreadcrumb(QtWidgets.QWidget):
    """
    MBreadcrumb

    A breadcrumb displays the current location within a hierarchy.
    It allows going back to states higher up in the hierarchy.
    """

    def __init__(self, separator="/", parent=None):
        super(MBreadcrumb, self).__init__(parent)
        self._separator = separator
        self._main_layout = QtWidgets.QHBoxLayout()
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)
        self._main_layout.addStretch()
        self.setLayout(self._main_layout)
        self.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self._button_group = QtWidgets.QButtonGroup()
        self._label_list = []

    def set_item_list(self, data_list):
        """Set the whole breadcrumb items. It will clear the old widgets."""
        for button in self._button_group.buttons():
            self._button_group.removeButton(button)
            self._main_layout.removeWidget(button)
            button.setVisible(False)
        for sep in self._label_list:
            self._main_layout.removeWidget(sep)
            sep.setVisible(False)

        for index, data_dict in enumerate(data_list):
            self.add_item(data_dict, index)

    def add_item(self, data_dict, index=None):
        """Add a item"""
        button = MToolButton()
        button.setText(data_dict.get("text"))
        if data_dict.get("svg"):
            button.svg(data_dict.get("svg"))
        if data_dict.get("tooltip"):
            button.setProperty("toolTip", data_dict.get("tooltip"))
        if data_dict.get("clicked"):
            button.clicked.connect(data_dict.get("clicked"))
        if data_dict.get("text"):
            if data_dict.get("svg") or data_dict.get("icon"):
                button.text_beside_icon()
            else:
                button.text_only()
        else:
            button.icon_only()

        if self._button_group.buttons():
            separator = MLabel(self._separator).secondary()
            self._label_list.append(separator)
            self._main_layout.insertWidget(self._main_layout.count() - 1, separator)
        self._main_layout.insertWidget(self._main_layout.count() - 1, button)

        if index is None:
            self._button_group.addButton(button)
        else:
            self._button_group.addButton(button, index)
