#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.2
# Email : muyanru345@163.com
###################################################################
"""
MAlert class.
"""
# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import built-in modules
import functools

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtWidgets
import six

# Import local modules
from . import dayu_theme
from .avatar import MAvatar
from .label import MLabel
from .mixin import property_mixin
from .qt import MPixmap
from .qt import get_scale_factor
from .tool_button import MToolButton


@property_mixin
class MAlert(QtWidgets.QWidget):
    """
    Alert component for feedback.

    Property:
        dayu_type: The feedback type with different color container.
        dayu_text: The feedback string showed in container.
    """

    InfoType = "info"
    SuccessType = "success"
    WarningType = "warning"
    ErrorType = "error"

    def __init__(self, text="", parent=None, flags=QtCore.Qt.Widget):
        super(MAlert, self).__init__(parent, flags)
        self.setAttribute(QtCore.Qt.WA_StyledBackground)
        self._icon_label = MAvatar()
        self._icon_label.set_dayu_size(dayu_theme.tiny)
        self._content_label = MLabel().secondary()
        self._close_button = MToolButton().svg("close_line.svg").tiny().icon_only()
        self._close_button.clicked.connect(functools.partial(self.setVisible, False))
        scale_x, _ = get_scale_factor()
        margin = 8 * scale_x
        self._main_lay = QtWidgets.QHBoxLayout()
        self._main_lay.setContentsMargins(margin, margin, margin, margin)
        self._main_lay.addWidget(self._icon_label)
        self._main_lay.addWidget(self._content_label)
        self._main_lay.addStretch()
        self._main_lay.addWidget(self._close_button)

        self.setLayout(self._main_lay)

        self.set_show_icon(True)
        self.set_closable(False)
        self._dayu_type = None
        self._dayu_text = None
        self.set_dayu_type(MAlert.InfoType)
        self.set_dayu_text(text)

    def set_closable(self, closable):
        """Display the close icon button or not."""
        self._close_button.setVisible(closable)

    def set_show_icon(self, show_icon):
        """Display the information type icon or not."""
        self._icon_label.setVisible(show_icon)

    def _set_dayu_text(self):
        self._content_label.setText(self._dayu_text)
        self.setVisible(bool(self._dayu_text))

    def set_dayu_text(self, value):
        """Set the feedback content."""
        if isinstance(value, six.string_types):
            self._dayu_text = value
        else:
            raise TypeError("Input argument 'value' should be string type, " "but get {}".format(type(value)))
        self._set_dayu_text()

    def _set_dayu_type(self):
        self._icon_label.set_dayu_image(
            MPixmap(
                "{}_fill.svg".format(self._dayu_type),
                vars(dayu_theme).get(self._dayu_type + "_color"),
            )
        )
        self.style().polish(self)

    def set_dayu_type(self, value):
        """Set feedback type."""
        if value in [
            MAlert.InfoType,
            MAlert.SuccessType,
            MAlert.WarningType,
            MAlert.ErrorType,
        ]:
            self._dayu_type = value
        else:
            raise ValueError("Input argument 'value' should be one of " "info/success/warning/error string.")
        self._set_dayu_type()

    def get_dayu_type(self):
        """
        Get MAlert feedback type.
        :return: str
        """
        return self._dayu_type

    def get_dayu_text(self):
        """
        Get MAlert feedback message.
        :return: six.string_types
        """
        return self._dayu_text

    dayu_text = QtCore.Property(six.text_type, get_dayu_text, set_dayu_text)
    dayu_type = QtCore.Property(str, get_dayu_type, set_dayu_type)

    def info(self):
        """Set MAlert to InfoType"""
        self.set_dayu_type(MAlert.InfoType)
        return self

    def success(self):
        """Set MAlert to SuccessType"""
        self.set_dayu_type(MAlert.SuccessType)
        return self

    def warning(self):
        """Set MAlert to  WarningType"""
        self.set_dayu_type(MAlert.WarningType)
        return self

    def error(self):
        """Set MAlert to ErrorType"""
        self.set_dayu_type(MAlert.ErrorType)
        return self

    def closable(self):
        """Set MAlert closebale is True"""
        self.set_closable(True)
        return self
