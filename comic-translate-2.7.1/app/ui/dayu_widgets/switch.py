#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.2
# Email : muyanru345@163.com
###################################################################
"""
MSwitch
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


@cursor_mixin
class MSwitch(QtWidgets.QRadioButton):
    """
    Switching Selector.

    Property:
        dayu_size: the size of switch widget. int
    """

    def __init__(self, parent=None):
        super(MSwitch, self).__init__(parent)
        self._dayu_size = dayu_theme.default_size
        self.setAutoExclusive(False)

    def minimumSizeHint(self):
        """
        Override the QRadioButton minimum size hint. We don't need the text space.
        :return:
        """
        height = self._dayu_size * 1.2
        return QtCore.QSize(int(height), int(height / 2))

    def get_dayu_size(self):
        """
        Get the switch size.
        :return: int
        """
        return self._dayu_size

    def set_dayu_size(self, value):
        """
        Set the switch size.
        :param value: int
        :return: None
        """
        self._dayu_size = value
        self.style().polish(self)

    dayu_size = QtCore.Property(int, get_dayu_size, set_dayu_size)

    def huge(self):
        """Set MSwitch to huge size"""
        self.set_dayu_size(dayu_theme.huge)
        return self

    def large(self):
        """Set MSwitch to large size"""
        self.set_dayu_size(dayu_theme.large)
        return self

    def medium(self):
        """Set MSwitch to medium size"""
        self.set_dayu_size(dayu_theme.medium)
        return self

    def small(self):
        """Set MSwitch to small size"""
        self.set_dayu_size(dayu_theme.small)
        return self

    def tiny(self):
        """Set MSwitch to tiny size"""
        self.set_dayu_size(dayu_theme.tiny)
        return self
