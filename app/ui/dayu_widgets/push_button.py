#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.2
# Email : muyanru345@163.com
###################################################################
"""
MPushButton.
"""
# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtWidgets

# Import local modules
from . import dayu_theme
from .mixin import cursor_mixin
from .mixin import focus_shadow_mixin


@cursor_mixin
@focus_shadow_mixin
class MPushButton(QtWidgets.QPushButton):
    """
    QPushButton.

    Property:
        dayu_size: The size of push button
        dayu_type: The type of push button.
    """

    DefaultType = "default"
    PrimaryType = "primary"
    SuccessType = "success"
    WarningType = "warning"
    DangerType = "danger"

    def __init__(self, text="", icon=None, parent=None):
        if icon is None:
            super(MPushButton, self).__init__(text=text, parent=parent)
        else:
            super(MPushButton, self).__init__(icon=icon, text=text, parent=parent)
        self._dayu_type = MPushButton.DefaultType
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
        self.style().polish(self)

    def get_dayu_type(self):
        """
        Get the push button type.
        :return: string.
        """
        return self._dayu_type

    def set_dayu_type(self, value):
        """
        Set the push button type.
        :return: None
        """
        if value in [
            MPushButton.DefaultType,
            MPushButton.PrimaryType,
            MPushButton.SuccessType,
            MPushButton.WarningType,
            MPushButton.DangerType,
        ]:
            self._dayu_type = value
        else:
            raise ValueError(
                "Input argument 'value' should be one of " "default/primary/success/warning/danger string."
            )
        self.style().polish(self)

    dayu_type = QtCore.Property(str, get_dayu_type, set_dayu_type)
    dayu_size = QtCore.Property(int, get_dayu_size, set_dayu_size)

    def primary(self):
        """Set MPushButton to PrimaryType"""
        self.set_dayu_type(MPushButton.PrimaryType)
        return self

    def success(self):
        """Set MPushButton to SuccessType"""
        self.set_dayu_type(MPushButton.SuccessType)
        return self

    def warning(self):
        """Set MPushButton to  WarningType"""
        self.set_dayu_type(MPushButton.WarningType)
        return self

    def danger(self):
        """Set MPushButton to DangerType"""
        self.set_dayu_type(MPushButton.DangerType)
        return self

    def huge(self):
        """Set MPushButton to huge size"""
        self.set_dayu_size(dayu_theme.huge)
        return self

    def large(self):
        """Set MPushButton to large size"""
        self.set_dayu_size(dayu_theme.large)
        return self

    def medium(self):
        """Set MPushButton to  medium"""
        self.set_dayu_size(dayu_theme.medium)
        return self

    def small(self):
        """Set MPushButton to small size"""
        self.set_dayu_size(dayu_theme.small)
        return self

    def tiny(self):
        """Set MPushButton to tiny size"""
        self.set_dayu_size(dayu_theme.tiny)
        return self
