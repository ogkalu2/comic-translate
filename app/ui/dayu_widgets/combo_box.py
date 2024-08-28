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

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtWidgets

# Import local modules
from . import dayu_theme
from .completer import MCompleter
from .mixin import cursor_mixin
from .mixin import focus_shadow_mixin
from .mixin import property_mixin
from . import utils as utils


@property_mixin
class MComboBoxSearchMixin(object):
    def __init__(self, *args, **kwargs):
        super(MComboBoxSearchMixin, self).__init__(*args, **kwargs)
        self.filter_model = QtCore.QSortFilterProxyModel(self)
        self.filter_model.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.filter_model.setSourceModel(self.model())
        self.completer = MCompleter(self)
        self.completer.setCompletionMode(QtWidgets.QCompleter.UnfilteredPopupCompletion)
        self.completer.setModel(self.filter_model)

    def search(self):
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setEditable(True)

        self.setCompleter(self.completer)

        edit = self.lineEdit()
        edit.setReadOnly(False)
        edit.returnPressed.disconnect()
        edit.textEdited.connect(self.filter_model.setFilterFixedString)
        self.completer.activated.connect(lambda t: t and self.setCurrentIndex(self.findText(t)))

    def _set_searchable(self, value):
        """search property to True then trigger search"""
        value and self.search()

    def setModel(self, model):
        super(MComboBoxSearchMixin, self).setModel(model)
        self.filter_model.setSourceModel(model)
        self.completer.setModel(self.filter_model)

    def setModelColumn(self, column):
        self.completer.setCompletionColumn(column)
        self.filter_model.setFilterKeyColumn(column)
        super(MComboBoxSearchMixin, self).setModelColumn(column)


@cursor_mixin
@focus_shadow_mixin
class MComboBox(MComboBoxSearchMixin, QtWidgets.QComboBox):
    Separator = "/"
    sig_value_changed = QtCore.Signal(object)

    def __init__(self, parent=None):
        super(MComboBox, self).__init__(parent)

        self._root_menu = None
        self._display_formatter = utils.display_formatter
        self.setEditable(True)
        line_edit = self.lineEdit()
        line_edit.setReadOnly(True)
        line_edit.setTextMargins(4, 0, 4, 0)
        line_edit.setStyleSheet("background-color:transparent")
        line_edit.setCursor(QtCore.Qt.PointingHandCursor)
        line_edit.installEventFilter(self)
        self._has_custom_view = False
        self.set_value("")
        self.set_placeholder(self.tr("Please Select"))
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self._dayu_size = dayu_theme.default_size

    def get_dayu_size(self):
        """
        Get the push button height
        :return: integer
        """
        return self._dayu_size

    def set_dayu_size(self, value):
        """
        Set the avatar size.
        :param value: integer
        :return: None
        """
        self._dayu_size = value
        self.lineEdit().setProperty("dayu_size", value)
        self.style().polish(self)

    dayu_size = QtCore.Property(int, get_dayu_size, set_dayu_size)

    def set_formatter(self, func):
        self._display_formatter = func

    def set_placeholder(self, text):
        """Display the text when no item selected."""
        self.lineEdit().setPlaceholderText(text)

    def set_value(self, value):
        self.setProperty("value", value)

    def _set_value(self, value):
        self.lineEdit().setProperty("text", self._display_formatter(value))
        if self._root_menu:
            self._root_menu.set_value(value)

    def set_menu(self, menu):
        self._root_menu = menu
        self._root_menu.sig_value_changed.connect(self.sig_value_changed)
        self._root_menu.sig_value_changed.connect(self.set_value)

    def setView(self, *args, **kwargs):
        """Override setView to flag _has_custom_view variable."""
        self._has_custom_view = True
        super(MComboBox, self).setView(*args, **kwargs)

    def showPopup(self):
        """Override default showPopup. When set custom menu, show the menu instead."""
        if self._has_custom_view or self._root_menu is None:
            super(MComboBox, self).showPopup()
        else:
            super(MComboBox, self).hidePopup()
            self._root_menu.popup(self.mapToGlobal(QtCore.QPoint(0, self.height())))

    # def setCurrentIndex(self, index):
    #     raise NotImplementedError

    def eventFilter(self, widget, event):
        if widget is self.lineEdit() and widget.isReadOnly():
            if event.type() == QtCore.QEvent.MouseButtonPress:
                self.showPopup()
        return super(MComboBox, self).eventFilter(widget, event)

    def huge(self):
        """Set MComboBox to huge size"""
        self.set_dayu_size(dayu_theme.huge)
        return self

    def large(self):
        """Set MComboBox to large size"""
        self.set_dayu_size(dayu_theme.large)
        return self

    def medium(self):
        """Set MComboBox to  medium"""
        self.set_dayu_size(dayu_theme.medium)
        return self

    def small(self):
        """Set MComboBox to small size"""
        self.set_dayu_size(dayu_theme.small)
        return self

    def tiny(self):
        """Set MComboBox to tiny size"""
        self.set_dayu_size(dayu_theme.tiny)
        return self


@cursor_mixin
@focus_shadow_mixin
class MFontComboBox(MComboBoxSearchMixin, QtWidgets.QFontComboBox):
    Separator = "/"
    sig_value_changed = QtCore.Signal(object)

    def __init__(self, parent=None):
        super(MFontComboBox, self).__init__(parent)

        self._root_menu = None
        self._display_formatter = utils.display_formatter
        self.setEditable(True)
        line_edit = self.lineEdit()
        line_edit.setReadOnly(True)
        line_edit.setTextMargins(4, 0, 4, 0)
        line_edit.setStyleSheet("background-color:transparent")
        line_edit.setCursor(QtCore.Qt.PointingHandCursor)
        line_edit.installEventFilter(self)
        self._has_custom_view = False
        self.set_value("")
        self.set_placeholder(self.tr("Please Select"))
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self._dayu_size = dayu_theme.default_size

    def get_dayu_size(self):
        """
        Get the push button height
        :return: integer
        """
        return self._dayu_size

    def set_dayu_size(self, value):
        """
        Set the avatar size.
        :param value: integer
        :return: None
        """
        self._dayu_size = value
        self.lineEdit().setProperty("dayu_size", value)
        self.style().polish(self)

    dayu_size = QtCore.Property(int, get_dayu_size, set_dayu_size)

    def set_formatter(self, func):
        self._display_formatter = func

    def set_placeholder(self, text):
        """Display the text when no item selected."""
        self.lineEdit().setPlaceholderText(text)

    def set_value(self, value):
        self.setProperty("value", value)

    def _set_value(self, value):
        self.lineEdit().setProperty("text", self._display_formatter(value))
        if self._root_menu:
            self._root_menu.set_value(value)

    def set_menu(self, menu):
        self._root_menu = menu
        self._root_menu.sig_value_changed.connect(self.sig_value_changed)
        self._root_menu.sig_value_changed.connect(self.set_value)

    def setView(self, *args, **kwargs):
        """Override setView to flag _has_custom_view variable."""
        self._has_custom_view = True
        super(MFontComboBox, self).setView(*args, **kwargs)

    def showPopup(self):
        """Override default showPopup. When set custom menu, show the menu instead."""
        if self._has_custom_view or self._root_menu is None:
            super(MFontComboBox, self).showPopup()
        else:
            super(MFontComboBox, self).hidePopup()
            self._root_menu.popup(self.mapToGlobal(QtCore.QPoint(0, self.height())))

    # def setCurrentIndex(self, index):
    #     raise NotImplementedError

    def eventFilter(self, widget, event):
        if widget is self.lineEdit() and widget.isReadOnly():
            if event.type() == QtCore.QEvent.MouseButtonPress:
                self.showPopup()
        return super(MFontComboBox, self).eventFilter(widget, event)

    def huge(self):
        """Set MComboBox to huge size"""
        self.set_dayu_size(dayu_theme.huge)
        return self

    def large(self):
        """Set MComboBox to large size"""
        self.set_dayu_size(dayu_theme.large)
        return self

    def medium(self):
        """Set MComboBox to  medium"""
        self.set_dayu_size(dayu_theme.medium)
        return self

    def small(self):
        """Set MComboBox to small size"""
        self.set_dayu_size(dayu_theme.small)
        return self

    def tiny(self):
        """Set MComboBox to tiny size"""
        self.set_dayu_size(dayu_theme.tiny)
        return self
