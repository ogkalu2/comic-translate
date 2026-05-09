#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: TimmyLiang
# Date  : 2021.12
# Email : 820472580@qq.com
###################################################################
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
from .mixin import property_mixin


@property_mixin
class MCompleter(QtWidgets.QCompleter):
    ITEM_HEIGHT = 28

    def __init__(self, parent=None):
        super(MCompleter, self).__init__(parent)
        self.setProperty("animatable", True)

        popup = self.popup()
        dayu_theme.apply(popup)

        self._opacity_anim = QtCore.QPropertyAnimation(popup, b"windowOpacity")
        self.setProperty("anim_opacity_duration", 300)
        self.setProperty("anim_opacity_curve", "OutCubic")
        self.setProperty("anim_opacity_start", 0)
        self.setProperty("anim_opacity_end", 1)

        self._size_anim = QtCore.QPropertyAnimation(popup, b"size")
        self.setProperty("anim_size_duration", 300)
        self.setProperty("anim_size_curve", "OutCubic")

        popup.installEventFilter(self)

    def _set_anim_opacity_duration(self, value):
        self._opacity_anim.setDuration(value)

    def _set_anim_opacity_curve(self, value):
        curve = getattr(QtCore.QEasingCurve, value, None)
        assert curve, "invalid QEasingCurve"
        self._opacity_anim.setEasingCurve(curve)

    def _set_anim_opacity_start(self, value):
        self._opacity_anim.setStartValue(value)

    def _set_anim_opacity_end(self, value):
        self._opacity_anim.setEndValue(value)

    def _set_anim_size_duration(self, value):
        self._size_anim.setDuration(value)

    def _set_anim_size_curve(self, value):
        curve = getattr(QtCore.QEasingCurve, value, None)
        assert curve, "invalid QEasingCurve"
        self._size_anim.setEasingCurve(curve)

    def _set_anim_size_start(self, value):
        self._size_anim.setStartValue(value)

    def _set_anim_size_end(self, value):
        self._size_anim.setEndValue(value)

    def init_size(self):
        popup = self.popup()

        model = popup.model()

        width = self.widget().width()
        max_height = popup.sizeHint().height()
        item_height = model.data(model.index(0, 0), QtCore.Qt.SizeHintRole)
        height = (item_height or self.ITEM_HEIGHT) * model.rowCount()
        height = height if height < max_height else max_height

        start_size = self.property("anim_size_start")
        start_size = start_size if start_size else QtCore.QSize(0, 0)
        end_size = self.property("anim_size_end")
        end_size = end_size if end_size else QtCore.QSize(width, height)
        self._size_anim.setStartValue(start_size)
        self._size_anim.setEndValue(end_size)

    def start_anim(self):
        self.init_size()
        self._opacity_anim.start()
        self._size_anim.start()

    def eventFilter(self, widget, event):
        if event.type() == QtCore.QEvent.Show and self.property("animatable"):
            self.start_anim()
        return super(MCompleter, self).eventFilter(widget, event)
