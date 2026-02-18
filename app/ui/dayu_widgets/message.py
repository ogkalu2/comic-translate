#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.2
# Email : muyanru345@163.com
###################################################################
"""MMessage"""
# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtWidgets

# Import local modules
from . import dayu_theme
from .avatar import MAvatar
from .label import MLabel
from .loading import MLoading
from .qt import MPixmap
from .tool_button import MToolButton

class MMessage(QtWidgets.QWidget):
    InfoType = "info"
    SuccessType = "success"
    WarningType = "warning"
    ErrorType = "error"
    LoadingType = "loading"

    default_config = {"duration": 2, "top": 24}

    sig_closed = QtCore.Signal()

    def __init__(self, text, duration=None, dayu_type=None, closable=False, parent=None):
        super(MMessage, self).__init__(parent)
        self.setObjectName("message")
        self._sig_closed_emitted = False
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.Dialog
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(QtCore.Qt.WA_StyledBackground)

        if dayu_type == MMessage.LoadingType:
            _icon_label = MLoading.tiny()
        else:
            _icon_label = MAvatar.tiny()
            current_type = dayu_type or MMessage.InfoType
            _icon_label.set_dayu_image(
                MPixmap(
                    "{}_fill.svg".format(current_type),
                    vars(dayu_theme).get(current_type + "_color"),
                )
            )

        self._content_label = MLabel(parent=self)
        self._content_label.setWordWrap(True)
        self._content_label.setText(text)
        self.setMaximumWidth(1000)

        self._close_button = MToolButton(parent=self).icon_only().svg("close_line.svg").tiny()
        self._close_button.clicked.connect(self.close)
        self._close_button.setVisible(closable or duration is None)

        self._main_lay = QtWidgets.QHBoxLayout()
        self._main_lay.addWidget(_icon_label)
        self._main_lay.addWidget(self._content_label)
        self._main_lay.addStretch()
        self._main_lay.addWidget(self._close_button)
        self.setLayout(self._main_lay)

        if duration is not None:
            _close_timer = QtCore.QTimer(self)
            _close_timer.setSingleShot(True)
            _close_timer.timeout.connect(self.close)
            _close_timer.setInterval(duration * 1000)

            _ani_timer = QtCore.QTimer(self)
            _ani_timer.timeout.connect(self._fade_out)
            _ani_timer.setInterval(duration * 1000 - 300)

            _close_timer.start()
            _ani_timer.start()

        self._pos_ani = QtCore.QPropertyAnimation(self)
        self._pos_ani.setTargetObject(self)
        self._pos_ani.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._pos_ani.setDuration(300)
        self._pos_ani.setPropertyName(b"pos")

        self._opacity_ani = QtCore.QPropertyAnimation()
        self._opacity_ani.setTargetObject(self)
        self._opacity_ani.setDuration(300)
        self._opacity_ani.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._opacity_ani.setPropertyName(b"windowOpacity")
        self._opacity_ani.setStartValue(0.0)
        self._opacity_ani.setEndValue(1.0)

        self._set_proper_position(parent)
        self._fade_int()

    def closeEvent(self, event):
        if not self._sig_closed_emitted:
            self._sig_closed_emitted = True
            self.sig_closed.emit()
        super(MMessage, self).closeEvent(event)

    def _fade_out(self):
        self._pos_ani.setDirection(QtCore.QAbstractAnimation.Backward)
        self._pos_ani.start()
        self._opacity_ani.setDirection(QtCore.QAbstractAnimation.Backward)
        self._opacity_ani.start()

    def _fade_int(self):
        self._pos_ani.start()
        self._opacity_ani.start()

    def _set_proper_position(self, parent):
        parent_geo = parent.geometry()
        if parent.isWindowType():
            # 其parent没有parent了，就是个完全独立的窗口
            pos = parent_geo.topLeft()
        elif parent in QtWidgets.QApplication.topLevelWidgets():
            # 其parent虽然是独立窗口，但却还有parent，常见情况，DCC中比如Maya我们开发的工具窗口，会将maya主窗口作为工具节目的parent
            pos = parent_geo.topLeft()
        else:
            pos = parent.mapToGlobal(parent_geo.topLeft())
        offset = 0
        for child in parent.children():
            if isinstance(child, MMessage) and child.isVisible():
                offset = max(offset, child.y())
        base = pos.y() + MMessage.default_config.get("top")
        target_x = pos.x() + parent_geo.width() / 2 - 100
        target_y = (offset + 50) if offset else base
        self._pos_ani.setStartValue(QtCore.QPoint(target_x, target_y - 40))
        self._pos_ani.setEndValue(QtCore.QPoint(target_x, target_y))

    @classmethod
    def info(cls, text, parent, duration=None, closable=None):
        """Show a normal message"""
        inst = cls(
            text,
            dayu_type=MMessage.InfoType,
            duration=duration,
            closable=closable if closable is not None else duration is None,
            parent=parent,
        )
        inst.show()
        return inst

    @classmethod
    def success(cls, text, parent, duration=None, closable=None):
        """Show a success message"""
        inst = cls(
            text,
            dayu_type=MMessage.SuccessType,
            duration=duration,
            closable=closable,
            parent=parent,
        )

        inst.show()
        return inst

    @classmethod
    def warning(cls, text, parent, duration=None, closable=None):
        """Show a warning message"""
        inst = cls(
            text,
            dayu_type=MMessage.WarningType,
            duration=duration,
            closable=closable,
            parent=parent,
        )
        inst.show()
        return inst

    @classmethod
    def error(cls, text, parent, duration=None, closable=None):
        """Show an error message"""
        inst = cls(
            text,
            dayu_type=MMessage.ErrorType,
            duration=duration,
            closable=closable,
            parent=parent,
        )
        inst.show()
        return inst

    @classmethod
    def loading(cls, text, parent):
        """Show a message with loading animation"""
        inst = cls(text, dayu_type=MMessage.LoadingType, parent=parent)
        inst.show()
        return inst

    @classmethod
    def config(cls, duration=None, top=None):
        """
        Config the global MMessage duration and top setting.
        :param duration: int (unit is second)
        :param top: int (unit is px)
        :return: None
        """
        if duration is not None:
            cls.default_config["duration"] = duration
        if top is not None:
            cls.default_config["top"] = top
