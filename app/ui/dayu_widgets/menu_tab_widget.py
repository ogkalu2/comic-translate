#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.3
# Email : muyanru345@163.com
###################################################################
"""A Navigation menu"""

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
from .tool_button import MToolButton


class MBlockButton(MToolButton):
    """MBlockButton"""

    def __init__(self, parent=None):
        super(MBlockButton, self).__init__(parent)
        self.setCheckable(True)


class MBlockButtonGroup(MButtonGroupBase):
    """MBlockButtonGroup"""

    sig_checked_changed = QtCore.Signal(int)

    def __init__(self, tab, orientation=QtCore.Qt.Horizontal, parent=None):
        super(MBlockButtonGroup, self).__init__(orientation=orientation, parent=parent)
        self.set_spacing(1)
        self._menu_tab = tab
        self._button_group.setExclusive(True)
        self._button_group.buttonClicked.connect(self._on_button_clicked)

    def _on_button_clicked(self, button):
        # Get the id of the clicked button and emit it
        button_id = self._button_group.id(button)
        self.sig_checked_changed.emit(button_id)

    def create_button(self, data_dict):
        button = MBlockButton()
        if data_dict.get("svg"):
            button.svg(data_dict.get("svg"))
        if data_dict.get("text"):
            if data_dict.get("svg") or data_dict.get("icon"):
                button.text_beside_icon()
            else:
                button.text_only()
        else:
            button.icon_only()
        button.set_dayu_size(self._menu_tab.get_dayu_size())
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

class MMenuTabWidget(QtWidgets.QWidget):
    """MMenuTabWidget"""

    def __init__(self, orientation=QtCore.Qt.Horizontal, parent=None):
        super(MMenuTabWidget, self).__init__(parent=parent)
        self.tool_button_group = MBlockButtonGroup(tab=self, orientation=orientation)

        if orientation == QtCore.Qt.Horizontal:
            self._bar_layout = QtWidgets.QHBoxLayout()
            self._bar_layout.setContentsMargins(10, 0, 10, 0)
        else:
            self._bar_layout = QtWidgets.QVBoxLayout()
            self._bar_layout.setContentsMargins(0, 0, 0, 0)

        self._bar_layout.addWidget(self.tool_button_group)
        self._bar_layout.addStretch()
        bar_widget = QtWidgets.QWidget()
        bar_widget.setObjectName("bar_widget")
        bar_widget.setLayout(self._bar_layout)
        bar_widget.setAttribute(QtCore.Qt.WA_StyledBackground)
        main_lay = QtWidgets.QVBoxLayout()
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        main_lay.addWidget(bar_widget)

        if orientation == QtCore.Qt.Horizontal:
            main_lay.addWidget(MDivider())

        main_lay.addSpacing(5)
        self.setLayout(main_lay)
        self._dayu_size = dayu_theme.large

    def tool_bar_append_widget(self, widget):
        """Add the widget too menubar's right position."""
        self._bar_layout.addWidget(widget)

    def tool_bar_insert_widget(self, widget):
        """Insert the widget to menubar's left position."""
        self._bar_layout.insertWidget(0, widget)

    def add_menu(self, data_dict, index=None):
        """Add a menu"""
        self.tool_button_group.add_button(data_dict, index)

    def get_dayu_size(self):
        """
        Get the menu tab size.
        :return: integer
        """
        return self._dayu_size

    def set_dayu_size(self, value):
        """
        Set the menu tab size.
        :param value: integer
        :return: None
        """
        self._dayu_size = value
        self.tool_button_group.update_size(self._dayu_size)
        self.style().polish(self)

    dayu_size = QtCore.Property(int, get_dayu_size, set_dayu_size)
