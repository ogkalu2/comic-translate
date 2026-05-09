#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.3
# Email : muyanru345@163.com
###################################################################
"""MLineTabWidget"""

# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtWidgets

# Import local modules
from . import dayu_theme
from .button_group import MButtonGroupBase
from .divider import MDivider
from .stacked_widget import MStackedWidget
from .tool_button import MToolButton


class MUnderlineButton(MToolButton):
    """MUnderlineButton"""

    def __init__(self, parent=None):
        super(MUnderlineButton, self).__init__(parent)
        self.setCheckable(True)


class MUnderlineButtonGroup(MButtonGroupBase):
    """MUnderlineButtonGroup"""

    sig_checked_changed = QtCore.Signal(int)

    def __init__(self, tab, parent=None):
        super(MUnderlineButtonGroup, self).__init__(parent=parent)
        self._line_tab = tab
        self.set_spacing(1)
        self._button_group.setExclusive(True)
        self._button_group.buttonClicked[int].connect(self.sig_checked_changed)

    def create_button(self, data_dict):
        button = MUnderlineButton(parent=self)
        if data_dict.get("svg"):
            button.svg(data_dict.get("svg"))
        if data_dict.get("text"):
            if data_dict.get("svg") or data_dict.get("icon"):
                button.text_beside_icon()
            else:
                button.text_only()
        else:
            button.icon_only()
        button.set_dayu_size(self._line_tab.get_dayu_size())
        return button

    def update_size(self, size):
        for button in self._button_group.buttons():
            button.set_dayu_size(size)

    def set_dayu_checked(self, value):
        """Set current checked button's id"""
        button = self._button_group.button(value)
        button.setChecked(True)
        self.sig_checked_changed.emit(value)

    def get_dayu_checked(self):
        """Get current checked button's id"""
        return self._button_group.checkedId()

    dayu_checked = QtCore.Property(int, get_dayu_checked, set_dayu_checked, notify=sig_checked_changed)


class MLineTabWidget(QtWidgets.QWidget):
    """MLineTabWidget"""

    def __init__(self, alignment=QtCore.Qt.AlignCenter, parent=None):
        super(MLineTabWidget, self).__init__(parent=parent)
        self.tool_button_group = MUnderlineButtonGroup(tab=self)
        self.bar_layout = QtWidgets.QHBoxLayout()
        self.bar_layout.setContentsMargins(0, 0, 0, 0)
        if alignment == QtCore.Qt.AlignCenter:
            self.bar_layout.addStretch()
            self.bar_layout.addWidget(self.tool_button_group)
            self.bar_layout.addStretch()
        elif alignment == QtCore.Qt.AlignLeft:
            self.bar_layout.addWidget(self.tool_button_group)
            self.bar_layout.addStretch()
        elif alignment == QtCore.Qt.AlignRight:
            self.bar_layout.addStretch()
            self.bar_layout.addWidget(self.tool_button_group)
        self.stack_widget = MStackedWidget()
        self.tool_button_group.sig_checked_changed.connect(self.stack_widget.setCurrentIndex)
        main_lay = QtWidgets.QVBoxLayout()
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        main_lay.addLayout(self.bar_layout)
        main_lay.addWidget(MDivider())
        main_lay.addSpacing(5)
        main_lay.addWidget(self.stack_widget)
        self.setLayout(main_lay)
        self._dayu_size = dayu_theme.default

    def append_widget(self, widget):
        """Add the widget to line tab's right position."""
        self.bar_layout.addWidget(widget)

    def insert_widget(self, widget):
        """Insert the widget to line tab's left position."""
        self.bar_layout.insertWidget(0, widget)

    def add_tab(self, widget, data_dict):
        """Add a tab"""
        self.stack_widget.addWidget(widget)
        self.tool_button_group.add_button(data_dict, self.stack_widget.count() - 1)

    def get_dayu_size(self):
        """
        Get the line tab size.
        :return: integer
        """
        return self._dayu_size

    def set_dayu_size(self, value):
        """
        Set the line tab size.
        :param value: integer
        :return: None
        """
        self._dayu_size = value
        self.tool_button_group.update_size(self._dayu_size)
        self.style().polish(self)

    dayu_size = QtCore.Property(int, get_dayu_size, set_dayu_size)
