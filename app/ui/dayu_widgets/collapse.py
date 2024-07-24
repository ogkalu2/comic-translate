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
from PySide6 import QtWidgets

# Import local modules
from .label import MLabel
from .mixin import property_mixin
from .qt import MPixmap
from .tool_button import MToolButton
from .button_group import MRadioButtonGroup
from .avatar import MAvatar
from . import dayu_theme


@property_mixin
class MSectionItem(QtWidgets.QWidget):
    sig_context_menu = QtCore.Signal(object)

    def __init__(self, title="", description="", expand=False, widget=None, closable=False, icon=None, parent=None):
        super(MSectionItem, self).__init__(parent)

        self._central_widget = None
        self.setAttribute(QtCore.Qt.WA_StyledBackground)
        self.title_label = MLabel().strong()

        self.desc_label = MLabel().secondary()

        self.icon = MAvatar(parent=self)
        self.icon.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)

        self.expand_icon = MLabel(parent=self)
        self.expand_icon.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)

        self._close_button = MToolButton().icon_only().tiny().svg("close_line.svg")
        self._close_button.clicked.connect(self.close)

        header_lay = QtWidgets.QHBoxLayout()
        header_lay.addWidget(self.icon)

        self.text_lay = QtWidgets.QVBoxLayout()
        self.text_lay.addWidget(self.title_label)
        self.text_lay.setSpacing(0)
        self.text_lay.setContentsMargins(0, 0, 0, 0)

        header_lay.addLayout(self.text_lay)
        header_lay.addStretch()
        header_lay.addWidget(self.expand_icon)
        header_lay.addWidget(self._close_button)


        # Add a new label for displaying the selected value
        self.selected_value_label = MLabel().secondary()
        self.selected_value_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        header_lay.insertWidget(header_lay.count() - 2, self.selected_value_label)

        self.header_widget = QtWidgets.QWidget(parent=self)
        self.header_widget.setAttribute(QtCore.Qt.WA_StyledBackground)
        self.header_widget.setObjectName("title")
        self.header_widget.setLayout(header_lay)
        self.header_widget.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self.header_widget.setCursor(QtCore.Qt.PointingHandCursor)
        self.title_label.setCursor(QtCore.Qt.PointingHandCursor)
        self.header_widget.installEventFilter(self)
        self.title_label.installEventFilter(self)

        self.content_widget = QtWidgets.QWidget(parent=self)
        self.content_layout = QtWidgets.QHBoxLayout()
        self.content_widget.setLayout(self.content_layout)

        self.main_lay = QtWidgets.QVBoxLayout()
        self.main_lay.setContentsMargins(0, 0, 0, 0)
        self.main_lay.setSpacing(0)
        self.main_lay.addWidget(self.header_widget)
        self.main_lay.addWidget(self.content_widget)
        self.setLayout(self.main_lay)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.setMouseTracking(True)
        self.set_title(title)
        self.set_description(description)
        self.set_closable(closable)

        if icon is not None:
            self.icon.set_dayu_image(icon)
            self.icon.set_dayu_size(dayu_theme.small)
            self.icon.setVisible(True)
        else:
            self.icon.setVisible(False)

        if widget:
            self.set_content(widget)
        self.set_expand(expand)

    def set_content(self, widget):
        if self._central_widget:
            self.content_layout.removeWidget(self._central_widget)
            self._central_widget.close()
        self.content_layout.addWidget(widget)
        self._central_widget = widget

    def get_content(self):
        return self._central_widget

    def set_closable(self, value):
        self.setProperty("closable", value)

    def _set_closable(self, value):
        self.content_widget.setVisible(value)
        self._close_button.setVisible(value)

    def set_expand(self, value):
        self.setProperty("expand", value)

    def _set_expand(self, value):
        self.content_widget.setVisible(value)
        self.expand_icon.setPixmap(MPixmap("up_line.svg" if value else "down_line.svg").scaledToHeight(12))

    def set_title(self, value):
        self.setProperty("title", value)

    def _set_title(self, value):
        self.title_label.setText(value)

    def set_description(self, value):
        self.setProperty("description", value)

    def _set_description(self, value):
        self.desc_label.setText(value)
        if value:
            self._add_description_to_layout()
        else:
            self._remove_description_from_layout()

    def _add_description_to_layout(self):
        if self.desc_label not in self.text_lay.children():
            self.text_lay.addWidget(self.desc_label)

    def _remove_description_from_layout(self):
        if self.desc_label in self.text_lay.children():
            self.text_lay.removeWidget(self.desc_label)
            self.desc_label.setParent(None)

    def eventFilter(self, widget, event):
        if widget in [self.header_widget, self.title_label]:
            if event.type() == QtCore.QEvent.MouseButtonRelease:
                self.set_expand(not self.property("expand"))
        return super(QtWidgets.QWidget, self).eventFilter(widget, event)
    
    def set_selected_value(self, value):
        self.selected_value_label.setText(value)


class MCollapse(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(MCollapse, self).__init__(parent)
        self._section_list = []
        self._main_layout = QtWidgets.QVBoxLayout()
        self.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self._main_layout.setSpacing(1)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._main_layout)

    def add_section(self, section_data):
        section_widget = MSectionItem(
            title=section_data.get("title"),
            expand=section_data.get("expand", False),
            widget=section_data.get("widget"),
            closable=section_data.get("closable", False),
            icon=section_data.get("icon"),
            description=section_data.get("description")
        )
        self._main_layout.insertWidget(self._main_layout.count(), section_widget)

        if isinstance(section_data.get("widget"), MRadioButtonGroup):
            radio_group = section_data["widget"]
            radio_group.sig_checked_changed.connect(
                lambda index, text: self.update_section_value(section_widget, text)
            )
            
            # Set default selection if provided
            default_selection = section_data.get("default_selection")
            id, string = default_selection
            if default_selection is not None:
                radio_group.set_dayu_checked(id, string)
                # Update the section item with the default selection
                default_button = radio_group.get_button_group().button(id)
                if default_button:
                    self.update_section_value(section_widget, default_button.text())

        return section_widget

    def update_section_value(self, section_widget, text):
        section_widget.set_selected_value(text)

    def add_section_list(self, section_list):
        for section_data in section_list:
            section_widget = self.add_section(section_data)
            section_widget._close_button.clicked.connect(functools.partial(self.remove_section, section_widget))
            self._section_list.append(section_widget)

    def remove_section(self, widget):
        self._section_list.remove(widget)

    def sections(self):
        return self._section_list

    def clear(self):
        for widget in self._section_list:
            self._main_layout.removeWidget(widget)
            del widget
