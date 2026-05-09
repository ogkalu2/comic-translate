#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: timmyliang
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
from .mixin import hover_shadow_mixin
from .mixin import property_mixin


@hover_shadow_mixin
@property_mixin
class MPopup(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super(MPopup, self).__init__(parent)
        self.setWindowFlags(QtCore.Qt.Popup)
        self.mouse_pos = None
        self.setProperty("movable", True)
        self.setProperty("animatable", True)
        QtCore.QTimer.singleShot(0, self.post_init)

        self._opacity_anim = QtCore.QPropertyAnimation(self, b"windowOpacity")
        self.setProperty("anim_opacity_duration", 300)
        self.setProperty("anim_opacity_curve", "OutCubic")
        self.setProperty("anim_opacity_start", 0)
        self.setProperty("anim_opacity_end", 1)

        self._size_anim = QtCore.QPropertyAnimation(self, b"size")
        self.setProperty("anim_size_duration", 300)
        self.setProperty("anim_size_curve", "OutCubic")
        self.setProperty("border_radius", 15)

    def post_init(self):
        start_size = self.property("anim_size_start")
        size = self.sizeHint()
        start_size = start_size if start_size else QtCore.QSize(0, size.height())
        end_size = self.property("anim_size_end")
        end_size = end_size if end_size else size
        self.setProperty("anim_size_start", start_size)
        self.setProperty("anim_size_end", end_size)

    def update_mask(self):
        rectPath = QtGui.QPainterPath()
        end_size = self.property("anim_size_end")
        rect = QtCore.QRectF(0, 0, end_size.width(), end_size.height())
        radius = self.property("border_radius")
        rectPath.addRoundedRect(rect, radius, radius)
        self.setMask(QtGui.QRegion(rectPath.toFillPolygon().toPolygon()))

    def _get_curve(self, value):
        curve = getattr(QtCore.QEasingCurve, value, None)
        if not curve:
            raise TypeError("Invalid QEasingCurve")
        return curve

    def _set_border_radius(self, value):
        QtCore.QTimer.singleShot(0, self.update_mask)

    def _set_anim_opacity_duration(self, value):
        self._opacity_anim.setDuration(value)

    def _set_anim_opacity_curve(self, value):
        self._opacity_anim.setEasingCurve(self._get_curve(value))

    def _set_anim_opacity_start(self, value):
        self._opacity_anim.setStartValue(value)

    def _set_anim_opacity_end(self, value):
        self._opacity_anim.setEndValue(value)

    def _set_anim_size_duration(self, value):
        self._size_anim.setDuration(value)

    def _set_anim_size_curve(self, value):
        self._size_anim.setEasingCurve(self._get_curve(value))

    def _set_anim_size_start(self, value):
        self._size_anim.setStartValue(value)

    def _set_anim_size_end(self, value):
        self._size_anim.setEndValue(value)
        QtCore.QTimer.singleShot(0, self.update_mask)

    def start_anim(self):
        self._size_anim.start()
        self._opacity_anim.start()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.mouse_pos = event.pos()
        return super(MPopup, self).mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.mouse_pos = None
        return super(MPopup, self).mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == QtCore.Qt.LeftButton and self.mouse_pos and self.property("movable"):
            self.move(self.mapToGlobal(event.pos() - self.mouse_pos))
        return super(MPopup, self).mouseMoveEvent(event)

    def show(self):
        if self.property("animatable"):
            self.start_anim()
        self.move(QtGui.QCursor.pos())
        super(MPopup, self).show()
        # NOTES(timmyliang): for chinese input
        self.activateWindow()
