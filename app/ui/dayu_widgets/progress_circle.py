#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.2
# Email : muyanru345@163.com
###################################################################
"""MProgressCircle"""
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
from . import utils
from .label import MLabel


class MProgressCircle(QtWidgets.QProgressBar):
    """
    MProgressCircle: Display the current progress of an operation flow.
    When you need to display the completion percentage of an operation.

    Property:
        dayu_width: int
        dayu_color: str
    """

    def __init__(self, dashboard=False, parent=None):
        super(MProgressCircle, self).__init__(parent)
        self._main_lay = QtWidgets.QHBoxLayout()
        self._default_label = MLabel().h3()
        self._default_label.setAlignment(QtCore.Qt.AlignCenter)
        self._main_lay.addWidget(self._default_label)
        self.setLayout(self._main_lay)
        self._color = None
        self._width = None

        self._start_angle = 90 * 16
        self._max_delta_angle = 360 * 16
        self._height_factor = 1.0
        self._width_factor = 1.0
        if dashboard:
            self._start_angle = 225 * 16
            self._max_delta_angle = 270 * 16
            self._height_factor = (2 + pow(2, 0.5)) / 4 + 0.03

        self.set_dayu_width(dayu_theme.progress_circle_default_radius)
        self.set_dayu_color(dayu_theme.primary_color)

    def set_widget(self, widget):
        """
        Set a custom widget to show on the circle's inner center
         and replace the default percent label
        :param widget: QWidget
        :return: None
        """
        self.setTextVisible(False)
        if not widget.styleSheet():
            widget.setStyleSheet("background:transparent")
        self._main_lay.addWidget(widget)

    def get_dayu_width(self):
        """
        Get current circle fixed width
        :return: int
        """
        return self._width

    def set_dayu_width(self, value):
        """
        Set current circle fixed width
        :param value: int
        :return: None
        """
        self._width = value
        self.setFixedSize(QtCore.QSize(int(self._width * self._width_factor), int(self._width * self._height_factor)))

    def get_dayu_color(self):
        """
        Get current circle foreground color
        :return: str
        """
        return self._color

    def set_dayu_color(self, value):
        """
        Set current circle's foreground color
        :param value: str
        :return:
        """
        self._color = value
        self.update()

    dayu_color = QtCore.Property(str, get_dayu_color, set_dayu_color)
    dayu_width = QtCore.Property(int, get_dayu_width, set_dayu_width)

    def paintEvent(self, event):
        """Override QProgressBar's paintEvent."""
        if self.text() != self._default_label.text():
            self._default_label.setText(self.text())
        if self.isTextVisible() != self._default_label.isVisible():
            self._default_label.setVisible(self.isTextVisible())

        percent = utils.get_percent(self.value(), self.minimum(), self.maximum())
        total_width = self.get_dayu_width()
        pen_width = int(3 * total_width / 50.0)
        radius = total_width - pen_width - 1

        painter = QtGui.QPainter(self)
        painter.setRenderHints(QtGui.QPainter.Antialiasing)

        # draw background circle
        pen_background = QtGui.QPen()
        pen_background.setWidth(pen_width)
        pen_background.setColor(QtGui.QColor(dayu_theme.background_selected_color))
        pen_background.setCapStyle(QtCore.Qt.RoundCap)
        painter.setPen(pen_background)
        painter.drawArc(
            pen_width / 2.0 + 1,
            pen_width / 2.0 + 1,
            radius,
            radius,
            self._start_angle,
            -self._max_delta_angle,
        )

        # draw foreground circle
        pen_foreground = QtGui.QPen()
        pen_foreground.setWidth(pen_width)
        pen_foreground.setColor(QtGui.QColor(self._color))
        pen_foreground.setCapStyle(QtCore.Qt.RoundCap)
        painter.setPen(pen_foreground)
        painter.drawArc(
            pen_width / 2.0 + 1,
            pen_width / 2.0 + 1,
            radius,
            radius,
            self._start_angle,
            -percent * 0.01 * self._max_delta_angle,
        )
        painter.end()

    @classmethod
    def dashboard(cls, parent=None):
        """Create a dashboard style MCircle"""
        return MProgressCircle(dashboard=True, parent=parent)
