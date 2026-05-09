#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.3
# Email : muyanru345@163.com
###################################################################
"""
mixin decorators to add Qt class feature.
"""

# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtGui
from PySide6 import QtWidgets


def property_mixin(cls):
    """Run function after dynamic property value changed"""

    def _new_event(self, event):
        if event.type() == QtCore.QEvent.DynamicPropertyChange:
            prp = event.propertyName().data().decode()
            if hasattr(self, "_set_{}".format(prp)):
                callback = getattr(self, "_set_{}".format(prp))
                callback(self.property(str(prp)))
        return super(cls, self).event(event)

    setattr(cls, "event", _new_event)
    return cls


def cursor_mixin(cls):
    """
    Change Widget cursor:
    when user mouse in: Qt.PointingHandCursor;
    when widget is disabled and mouse in: Qt.ForbiddenCursor
    """

    old_enter_event = cls.enterEvent
    old_leave_event = cls.leaveEvent
    old_hide_event = cls.hideEvent
    old_focus_out_event = cls.focusOutEvent

    def _revert_cursor(self):
        if self.__dict__.get("__dayu_enter", False):
            while self.__dict__.get("__dayu_enter_count", 0) > 0:
                QtWidgets.QApplication.restoreOverrideCursor()
                self.__dict__.update({"__dayu_enter_count": self.__dict__.get("__dayu_enter_count", 0) - 1})
            self.__dict__.update({"__dayu_enter": False})

    def _new_enter_event(self, *args, **kwargs):
        self.__dict__.update({"__dayu_enter": True})
        self.__dict__.update({"__dayu_enter_count": self.__dict__.get("__dayu_enter_count", 0) + 1})
        QtWidgets.QApplication.setOverrideCursor(
            QtCore.Qt.PointingHandCursor if self.isEnabled() else QtCore.Qt.ForbiddenCursor
        )
        return old_enter_event(self, *args, **kwargs)

    def _new_leave_event(self, *args, **kwargs):
        _revert_cursor(self)
        return old_leave_event(self, *args, **kwargs)

    def _new_hide_event(self, *args, **kwargs):
        _revert_cursor(self)
        return old_hide_event(self, *args, **kwargs)

    def _new_focus_out_event(self, *args, **kwargs):
        _revert_cursor(self)
        return old_focus_out_event(self, *args, **kwargs)

    cls.enterEvent = _new_enter_event
    cls.leaveEvent = _new_leave_event
    cls.hideEvent = _new_hide_event
    cls.focusOutEvent = _new_focus_out_event
    return cls


def focus_shadow_mixin(cls):
    """
    Add shadow effect for decorated class when widget focused
    When focus in target widget, enable shadow effect.
    When focus out target widget, disable shadow effect.
    """
    old_focus_in_event = cls.focusInEvent
    old_focus_out_event = cls.focusOutEvent

    def _new_focus_in_event(self, *args, **kwargs):
        old_focus_in_event(self, *args, **kwargs)
        if not self.graphicsEffect():
            # Import local modules
            from . import dayu_theme

            shadow_effect = QtWidgets.QGraphicsDropShadowEffect(self)
            dayu_type = self.property("dayu_type")
            color = vars(dayu_theme).get("{}_color".format(dayu_type or "primary"))
            shadow_effect.setColor(QtGui.QColor(color))
            shadow_effect.setOffset(0, 0)
            shadow_effect.setBlurRadius(5)
            shadow_effect.setEnabled(False)
            self.setGraphicsEffect(shadow_effect)
        if self.isEnabled():
            self.graphicsEffect().setEnabled(True)

    def _new_focus_out_event(self, *args, **kwargs):
        old_focus_out_event(self, *args, **kwargs)
        if self.graphicsEffect():
            self.graphicsEffect().setEnabled(False)

    setattr(cls, "focusInEvent", _new_focus_in_event)
    setattr(cls, "focusOutEvent", _new_focus_out_event)
    return cls


def hover_shadow_mixin(cls):
    """
    Add shadow effect for decorated class when widget hovered
    When mouse enter target widget, enable shadow effect.
    When mouse leave target widget, disable shadow effect.
    """
    old_enter_event = cls.enterEvent
    old_leave_event = cls.leaveEvent

    def _new_enter_event(self, *args, **kwargs):
        old_enter_event(self, *args, **kwargs)
        if not self.graphicsEffect():
            # Import local modules
            from . import dayu_theme

            shadow_effect = QtWidgets.QGraphicsDropShadowEffect(self)
            dayu_type = self.property("type")
            color = vars(dayu_theme).get("{}_color".format(dayu_type or "primary"))
            shadow_effect.setColor(QtGui.QColor(color))
            shadow_effect.setOffset(0, 0)
            shadow_effect.setBlurRadius(5)
            shadow_effect.setEnabled(False)
            self.setGraphicsEffect(shadow_effect)
        if self.isEnabled():
            self.graphicsEffect().setEnabled(True)

    def _new_leave_event(self, *args, **kwargs):
        old_leave_event(self, *args, **kwargs)
        if self.graphicsEffect():
            self.graphicsEffect().setEnabled(False)

    setattr(cls, "enterEvent", _new_enter_event)
    setattr(cls, "leaveEvent", _new_leave_event)
    return cls


def _stackable(widget):
    """Used for stacked_animation_mixin to only add mixin for widget who can stacked."""
    # We use widget() to get currentWidget, use currentChanged to play the animation.
    # For now just QTabWidget and QStackedWidget can use this decorator.
    return issubclass(widget, QtWidgets.QWidget) and hasattr(widget, "widget") and hasattr(widget, "currentChanged")


def stacked_animation_mixin(cls):
    """
    Decorator for stacked widget.
    When Stacked widget currentChanged, show opacity and position animation for current widget.
    """
    if not _stackable(cls):  # If widget can't stack, return the original widget class
        return cls
    old_init = cls.__init__

    def _new_init(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        self._previous_index = 0
        self._to_show_pos_ani = QtCore.QPropertyAnimation()
        self._to_show_pos_ani.setDuration(400)
        self._to_show_pos_ani.setPropertyName(b"pos")
        self._to_show_pos_ani.setEndValue(QtCore.QPoint(0, 0))
        self._to_show_pos_ani.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        self._to_hide_pos_ani = QtCore.QPropertyAnimation()
        self._to_hide_pos_ani.setDuration(400)
        self._to_hide_pos_ani.setPropertyName(b"pos")
        self._to_hide_pos_ani.setEndValue(QtCore.QPoint(0, 0))
        self._to_hide_pos_ani.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        self._opacity_eff = QtWidgets.QGraphicsOpacityEffect()
        self._opacity_ani = QtCore.QPropertyAnimation()
        self._opacity_ani.setDuration(400)
        self._opacity_ani.setEasingCurve(QtCore.QEasingCurve.InCubic)
        self._opacity_ani.setPropertyName(b"opacity")
        self._opacity_ani.setStartValue(0.0)
        self._opacity_ani.setEndValue(1.0)
        self._opacity_ani.setTargetObject(self._opacity_eff)
        self._opacity_ani.finished.connect(self._disable_opacity)
        self.currentChanged.connect(self._play_anim)

    def _play_anim(self, index):
        current_widget = self.widget(index)
        if self._previous_index < index:
            self._to_show_pos_ani.setStartValue(QtCore.QPoint(self.width(), 0))
            self._to_show_pos_ani.setTargetObject(current_widget)
            self._to_show_pos_ani.start()
        else:
            self._to_hide_pos_ani.setStartValue(QtCore.QPoint(-self.width(), 0))
            self._to_hide_pos_ani.setTargetObject(current_widget)
            self._to_hide_pos_ani.start()
        current_widget.setGraphicsEffect(self._opacity_eff)
        current_widget.graphicsEffect().setEnabled(True)
        self._opacity_ani.start()
        self._previous_index = index

    def _disable_opacity(self):
        # 如果不关掉effect，会跟子控件的 effect 或 paintEvent 冲突引起 crash
        # QPainter::begin: A paint device can only be painted by one painter at a time.
        self.currentWidget().graphicsEffect().setEnabled(False)

    setattr(cls, "__init__", _new_init)
    setattr(cls, "_play_anim", _play_anim)
    setattr(cls, "_disable_opacity", _disable_opacity)
    return cls
