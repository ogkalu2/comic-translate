#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.2
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
import six

# Import local modules
from . import dayu_theme
from .check_box import MCheckBox
from .menu import MMenu
from .push_button import MPushButton
from .qt import get_scale_factor
from .radio_button import MRadioButton
from .tool_button import MToolButton


class MButtonGroupBase(QtWidgets.QWidget):
    def __init__(self, orientation=QtCore.Qt.Horizontal, parent=None):
        super(MButtonGroupBase, self).__init__(parent=parent)
        self._main_layout = QtWidgets.QBoxLayout(
            QtWidgets.QBoxLayout.LeftToRight
            if orientation == QtCore.Qt.Horizontal
            else QtWidgets.QBoxLayout.TopToBottom
        )
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._main_layout)
        self.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self._button_group = QtWidgets.QButtonGroup()
        self._orientation = "horizontal" if orientation == QtCore.Qt.Horizontal else "vertical"

    def set_spacing(self, value):
        self._main_layout.setSpacing(value)

    def get_button_group(self):
        return self._button_group

    def create_button(self, data_dict):
        raise NotImplementedError()

    def add_button(self, data_dict, index=None):
        if isinstance(data_dict, six.string_types):
            data_dict = {"text": data_dict}
        elif isinstance(data_dict, QtGui.QIcon):
            data_dict = {"icon": data_dict}
        button = self.create_button(data_dict)
        button.setProperty("combine", self._orientation)
        if data_dict.get("text"):
            button.setProperty("text", data_dict.get("text"))
        if data_dict.get("icon"):
            button.setProperty("icon", data_dict.get("icon"))
        if data_dict.get("data"):
            button.setProperty("data", data_dict.get("data"))
        if data_dict.get("checked"):
            button.setProperty("checked", data_dict.get("checked"))
        if data_dict.get("shortcut"):
            button.setProperty("shortcut", data_dict.get("shortcut"))
        if data_dict.get("tooltip"):
            button.setProperty("toolTip", data_dict.get("tooltip"))
        if data_dict.get("checkable"):
            button.setProperty("checkable", data_dict.get("checkable"))
        if data_dict.get("enabled") is not None:
            button.setEnabled(data_dict.get("enabled"))
        if data_dict.get("clicked"):
            button.clicked.connect(data_dict.get("clicked"))
        if data_dict.get("toggled"):
            button.toggled.connect(data_dict.get("toggled"))

        if index is None:
            self._button_group.addButton(button)
        else:
            self._button_group.addButton(button, index)
        self._main_layout.insertWidget(self._main_layout.count(), button)
        return button

    def set_button_list(self, button_list):
        for button in self._button_group.buttons():
            self._button_group.removeButton(button)
            self._main_layout.removeWidget(button)
            button.setVisible(False)
        for index, data_dict in enumerate(button_list):
            button = self.add_button(data_dict, index)


class MPushButtonGroup(MButtonGroupBase):
    def __init__(self, orientation=QtCore.Qt.Horizontal, parent=None):
        super(MPushButtonGroup, self).__init__(orientation=orientation, parent=parent)
        self.set_spacing(1)
        self._dayu_type = MPushButton.PrimaryType
        self._dayu_size = dayu_theme.default_size
        self._button_group.setExclusive(False)

    def create_button(self, data_dict):
        button = MPushButton()
        button.set_dayu_size(data_dict.get("dayu_size", self._dayu_size))
        button.set_dayu_type(data_dict.get("dayu_type", self._dayu_type))
        return button

    def get_dayu_size(self):
        return self._dayu_size

    def get_dayu_type(self):
        return self._dayu_type

    def set_dayu_size(self, value):
        self._dayu_size = value

    def set_dayu_type(self, value):
        self._dayu_type = value

    dayu_size = QtCore.Property(int, get_dayu_size, set_dayu_size)
    dayu_type = QtCore.Property(str, get_dayu_type, set_dayu_type)


class MCheckBoxGroup(MButtonGroupBase):
    sig_checked_changed = QtCore.Signal(list)

    def __init__(self, orientation=QtCore.Qt.Horizontal, parent=None):
        super(MCheckBoxGroup, self).__init__(orientation=orientation, parent=parent)
        scale_x, _ = get_scale_factor()
        self.set_spacing(15 * scale_x)
        self._button_group.setExclusive(False)

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._slot_context_menu)

        self._button_group.buttonClicked.connect(self._slot_map_signal)
        self._dayu_checked = []

    def create_button(self, data_dict):
        return MCheckBox()

    @QtCore.Slot(QtCore.QPoint)
    def _slot_context_menu(self, point):
        context_menu = MMenu(parent=self)
        action_select_all = context_menu.addAction("Select All")
        action_select_none = context_menu.addAction("Select None")
        action_select_invert = context_menu.addAction("Select Invert")
        action_select_all.triggered.connect(functools.partial(self._slot_set_select, True))
        action_select_none.triggered.connect(functools.partial(self._slot_set_select, False))
        action_select_invert.triggered.connect(functools.partial(self._slot_set_select, None))
        context_menu.exec_(QtGui.QCursor.pos() + QtCore.QPoint(10, 10))

    @QtCore.Slot(bool)
    def _slot_set_select(self, state):
        for check_box in self._button_group.buttons():
            if state is None:
                old_state = check_box.isChecked()
                check_box.setChecked(not old_state)
            else:
                check_box.setChecked(state)
        self._slot_map_signal()

    @QtCore.Slot(QtWidgets.QAbstractButton)
    def _slot_map_signal(self, button=None):
        self.sig_checked_changed.emit(
            [check_box.text() for check_box in self._button_group.buttons() if check_box.isChecked()]
        )

    def set_dayu_checked(self, value):
        if not isinstance(value, list):
            value = [value]
        if value == self.get_dayu_checked():
            return

        self._dayu_checked = value
        for check_box in self._button_group.buttons():
            flag = QtCore.Qt.Checked if check_box.text() in value else QtCore.Qt.Unchecked
            if flag != check_box.checkState():
                check_box.setCheckState(flag)
        self.sig_checked_changed.emit(value)

    def get_dayu_checked(self):
        return [check_box.text() for check_box in self._button_group.buttons() if check_box.isChecked()]

    dayu_checked = QtCore.Property("QVariantList", get_dayu_checked, set_dayu_checked, notify=sig_checked_changed)


class MRadioButtonGroup(MButtonGroupBase):
    """
    Property:
        dayu_checked
    """

    sig_checked_changed = QtCore.Signal(int, str)

    def __init__(self, orientation=QtCore.Qt.Horizontal, parent=None):
        super(MRadioButtonGroup, self).__init__(orientation=orientation, parent=parent)
        scale_x, _ = get_scale_factor()
        self.set_spacing(15 * scale_x)
        self._button_group.setExclusive(True)
        self._button_group.buttonClicked.connect(self._on_button_clicked)

    def _on_button_clicked(self, button):
        self.sig_checked_changed.emit(self._button_group.id(button), button.text())

    def create_button(self, data_dict):
        return MRadioButton()

    def set_dayu_checked(self, value, str):
        if value == self.get_dayu_checked():
            return
        button = self._button_group.button(value)
        if button:
            button.setChecked(True)
            self.sig_checked_changed.emit(value, button.text())
        else:
            print("error")

    def get_dayu_checked(self):
        return self._button_group.checkedId()
    
    def get_current_value(self):
        checked_button = self._button_group.checkedButton()
        if checked_button:
            return checked_button.text()
        return None

    dayu_checked = QtCore.Property(int, get_dayu_checked, set_dayu_checked, notify=sig_checked_changed)


from PySide6 import QtCore, QtWidgets

class MToolButtonGroup(MButtonGroupBase):
    sig_checked_changed = QtCore.Signal(int)

    def __init__(
        self,
        size=None,
        type=None,
        exclusive=False,
        orientation=QtCore.Qt.Horizontal,
        parent=None,
    ):
        super(MToolButtonGroup, self).__init__(orientation=orientation, parent=parent)
        self.set_spacing(1)
        self._button_group.setExclusive(exclusive)
        self._size = size
        self._type = type
        self._button_group.buttonClicked.connect(self._on_button_clicked)

    def _on_button_clicked(self, button):
        # Get the id of the clicked button and emit it
        button_id = self._button_group.id(button)
        self.sig_checked_changed.emit(button_id)

    def create_button(self, data_dict):
        button = MToolButton()
        if data_dict.get("svg"):
            button.svg(data_dict.get("svg"))
        if data_dict.get("text"):
            if data_dict.get("svg") or data_dict.get("icon"):
                button.text_beside_icon()
            else:
                button.text_only()
        else:
            button.icon_only()
        return button

    def set_dayu_checked(self, value):
        if value == self.get_dayu_checked():
            return
        button = self._button_group.button(value)
        if button:
            button.setChecked(True)
            self.sig_checked_changed.emit(value)
        else:
            print(f"Error: No button found with id {value}")

    def get_dayu_checked(self):
        return self._button_group.checkedId()

    dayu_checked = QtCore.Property(int, get_dayu_checked, set_dayu_checked, notify=sig_checked_changed)