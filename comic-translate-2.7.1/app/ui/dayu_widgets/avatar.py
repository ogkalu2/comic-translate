#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.2
# Email : muyanru345@163.com
###################################################################
"""
MAvatar.
"""
# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtGui
from PySide6 import QtWidgets

# Import local modules
from . import dayu_theme
from .qt import MPixmap


class MAvatar(QtWidgets.QLabel):
    """
    Avatar component. It can be used to represent people or object.

    Property:
        image: avatar image, should be QPixmap.
        dayu_size: the size of image.
    """

    def __init__(self, parent=None, flags=QtCore.Qt.Widget):
        super(MAvatar, self).__init__(parent, flags)
        self._default_pix = MPixmap("user_fill.svg")
        self._pixmap = self._default_pix
        self._dayu_size = 0
        self.set_dayu_size(dayu_theme.default_size)

    def set_dayu_size(self, value):
        """
        Set the avatar size.
        :param value: integer
        :return: None
        """
        self._dayu_size = value
        self._set_dayu_size()

    def _set_dayu_size(self):
        self.setFixedSize(QtCore.QSize(self._dayu_size, self._dayu_size)) # w, h
        self._set_dayu_image()

    def _set_dayu_image(self):
        self._pixmap = self._pixmap.scaled(self.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.setPixmap(self._pixmap)
        # self.setPixmap(self._pixmap.scaledToWidth(self.width(), QtCore.Qt.SmoothTransformation))

    def set_dayu_image(self, value):
        """
        Set avatar image.
        :param value: QPixmap or None.
        :return: None
        """
        if value is None:
            self._pixmap = self._default_pix
        elif isinstance(value, QtGui.QPixmap):
            self._pixmap = self._default_pix if value.isNull() else value
        else:
            raise TypeError("Input argument 'value' should be QPixmap or None, " "but get {}".format(type(value)))
        self._set_dayu_image()

    def get_dayu_image(self):
        """
        Get the avatar image.
        :return: QPixmap
        """
        return self._pixmap

    def get_dayu_size(self):
        """
        Get the avatar size
        :return: integer
        """
        return self._dayu_size

    dayu_image = QtCore.Property(QtGui.QPixmap, get_dayu_image, set_dayu_image)
    dayu_size = QtCore.Property(int, get_dayu_size, set_dayu_size)

    @classmethod
    def huge(cls, image=None):
        """Create a MAvatar with huge size"""
        inst = cls()
        inst.set_dayu_size(dayu_theme.huge)
        inst.set_dayu_image(image)
        return inst

    @classmethod
    def large(cls, image=None):
        """Create a MAvatar with large size"""
        inst = cls()
        inst.set_dayu_size(dayu_theme.large)
        inst.set_dayu_image(image)
        return inst

    @classmethod
    def medium(cls, image=None):
        """Create a MAvatar with medium size"""
        inst = cls()
        inst.set_dayu_size(dayu_theme.medium)
        inst.set_dayu_image(image)
        return inst

    @classmethod
    def small(cls, image=None):
        """Create a MAvatar with small size"""
        inst = cls()
        inst.set_dayu_size(dayu_theme.small)
        inst.set_dayu_image(image)
        return inst

    @classmethod
    def tiny(cls, image=None):
        """Create a MAvatar with tiny size"""
        inst = cls()
        inst.set_dayu_size(dayu_theme.tiny)
        inst.set_dayu_image(image)
        return inst
    