#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.4
# Email : muyanru345@163.com
###################################################################
"""
MLoading
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


class MLoading(QtWidgets.QWidget):
    """
    Show a loading animation image.
    """

    def __init__(self, size=None, color=None, parent=None):
        super(MLoading, self).__init__(parent)
        size = size or dayu_theme.default_size
        self.setFixedSize(QtCore.QSize(size, size))
        self.pix = MPixmap("loading.svg", color or dayu_theme.primary_color).scaledToWidth(
            size, QtCore.Qt.SmoothTransformation
        )
        self._rotation = 0
        self._loading_ani = QtCore.QPropertyAnimation()
        self._loading_ani.setTargetObject(self)
        # self.loading_ani.setEasingCurve(QEasingCurve.InOutQuad)
        self._loading_ani.setDuration(1000)
        self._loading_ani.setPropertyName(b"rotation")
        self._loading_ani.setStartValue(0)
        self._loading_ani.setEndValue(360)
        self._loading_ani.setLoopCount(-1)
        self._loading_ani.start()

    def _set_rotation(self, value):
        self._rotation = value
        self.update()

    def _get_rotation(self):
        return self._rotation

    rotation = QtCore.Property(int, _get_rotation, _set_rotation)

    def paintEvent(self, event):
        """override the paint event to paint the 1/4 circle image."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        painter.translate(self.pix.width() / 2, self.pix.height() / 2)
        painter.rotate(self._rotation)
        painter.drawPixmap(
            -self.pix.width() / 2,
            -self.pix.height() / 2,
            self.pix.width(),
            self.pix.height(),
            self.pix,
        )
        painter.end()
        return super(MLoading, self).paintEvent(event)

    @classmethod
    def huge(cls, color=None):
        """Create a MLoading with huge size"""
        return cls(dayu_theme.huge, color)

    @classmethod
    def large(cls, color=None):
        """Create a MLoading with large size"""
        return cls(dayu_theme.large, color)

    @classmethod
    def medium(cls, color=None):
        """Create a MLoading with medium size"""
        return cls(dayu_theme.medium, color)

    @classmethod
    def small(cls, color=None):
        """Create a MLoading with small size"""
        return cls(dayu_theme.small, color)

    @classmethod
    def tiny(cls, color=None):
        """Create a MLoading with tiny size"""
        return cls(dayu_theme.tiny, color)


class MLoadingWrapper(QtWidgets.QWidget):
    """
    A wrapper widget to show the loading widget or hide.
    Property:
        dayu_loading: bool. current loading state.
    """

    def __init__(self, widget, loading=True, parent=None):
        super(MLoadingWrapper, self).__init__(parent)
        self._widget = widget
        self._mask_widget = QtWidgets.QFrame()
        self._mask_widget.setObjectName("mask")
        self._mask_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self._loading_widget = MLoading()
        self._loading_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        self._main_lay = QtWidgets.QGridLayout()
        self._main_lay.setContentsMargins(0, 0, 0, 0)
        self._main_lay.addWidget(widget, 0, 0)
        self._main_lay.addWidget(self._mask_widget, 0, 0)
        self._main_lay.addWidget(self._loading_widget, 0, 0, QtCore.Qt.AlignCenter)
        self.setLayout(self._main_lay)
        self._loading = None
        self.set_dayu_loading(loading)

    def _set_loading(self):
        self._loading_widget.setVisible(self._loading)
        self._mask_widget.setVisible(self._loading)

    def set_dayu_loading(self, loading):
        """
        Set current state to loading or not
        :param loading: bool
        :return: None
        """
        self._loading = loading
        self._set_loading()

    def get_dayu_loading(self):
        """
        Get current loading widget is loading or not.
        :return: bool
        """
        return self._loading

    dayu_loading = QtCore.Property(bool, get_dayu_loading, set_dayu_loading)
