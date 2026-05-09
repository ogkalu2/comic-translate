#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.3
# Email : muyanru345@163.com
###################################################################

# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import built-in modules
import functools

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtGui
from PySide6 import QtWidgets

# Import local modules
from . import dayu_theme
from .mixin import property_mixin


class MGuidPrivate(QtWidgets.QFrame):
    sig_go_to_page = QtCore.Signal()

    def __init__(self, parent=None):
        super(MGuidPrivate, self).__init__(parent)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.set_checked(False)

    def set_checked(self, value):
        self.setStyleSheet(
            "background-color:{}".format(dayu_theme.primary_color if value else dayu_theme.background_color)
        )
        self.setFixedSize(20 if value else 16, 4)

    def mousePressEvent(self, event):
        if event.buttons() == QtCore.Qt.LeftButton:
            self.sig_go_to_page.emit()
        return super(MGuidPrivate, self).mousePressEvent(event)


@property_mixin
class MCarousel(QtWidgets.QGraphicsView):
    def __init__(self, pix_list, autoplay=True, width=500, height=500, parent=None):
        super(MCarousel, self).__init__(parent)
        self.scene = QtWidgets.QGraphicsScene()
        self.scene.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(dayu_theme.background_color)))
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setScene(self.scene)
        self.setRenderHints(QtGui.QPainter.Antialiasing)
        self.hor_bar = self.horizontalScrollBar()
        self.carousel_width = width
        self.carousel_height = height

        pos = QtCore.QPoint(0, 0)
        pen = QtGui.QPen(QtCore.Qt.red)
        pen.setWidth(5)
        self.page_count = len(pix_list)
        line_width = 20
        total_width = self.page_count * (line_width + 5)
        self.scene.setSceneRect(0, 0, self.page_count * width, height)

        self.navigate_lay = QtWidgets.QHBoxLayout()
        self.navigate_lay.setSpacing(5)
        target_size = min(width, height)
        for index, pix in enumerate(pix_list):
            if pix.width() > pix.height():
                new_pix = pix.scaledToWidth(target_size, QtCore.Qt.SmoothTransformation)
            else:
                new_pix = pix.scaledToHeight(target_size, QtCore.Qt.SmoothTransformation)
            pix_item = QtWidgets.QGraphicsPixmapItem(new_pix)
            pix_item.setPos(pos)
            pix_item.setTransformationMode(QtCore.Qt.SmoothTransformation)
            pos.setX(pos.x() + width)
            line_item = MGuidPrivate()
            line_item.sig_go_to_page.connect(functools.partial(self.go_to_page, index))
            self.navigate_lay.addWidget(line_item)
            self.scene.addItem(pix_item)

        hud_widget = QtWidgets.QWidget(self)
        hud_widget.setLayout(self.navigate_lay)
        hud_widget.setStyleSheet("background:transparent")
        hud_widget.move(int(width / 2 - total_width / 2), height - 30)

        self.setFixedWidth(width + 2)
        self.setFixedHeight(height + 2)
        self.loading_ani = QtCore.QPropertyAnimation()
        self.loading_ani.setTargetObject(self.hor_bar)
        self.loading_ani.setEasingCurve(QtCore.QEasingCurve.InOutQuad)
        self.loading_ani.setDuration(500)
        self.loading_ani.setPropertyName(b"value")
        self.autoplay_timer = QtCore.QTimer(self)
        self.autoplay_timer.setInterval(2000)
        self.autoplay_timer.timeout.connect(self.next_page)

        self.current_index = 0
        self.go_to_page(0)
        self.set_autoplay(autoplay)

    def set_autoplay(self, value):
        self.setProperty("autoplay", value)

    def _set_autoplay(self, value):
        if value:
            self.autoplay_timer.start()
        else:
            self.autoplay_timer.stop()

    def set_interval(self, ms):
        self.autoplay_timer.setInterval(ms)

    def next_page(self):
        index = self.current_index + 1 if self.current_index + 1 < self.page_count else 0
        self.go_to_page(index)

    def pre_page(self):
        index = self.current_index - 1 if self.current_index > 0 else self.page_count - 1
        self.go_to_page(index)

    def go_to_page(self, index):
        self.loading_ani.setStartValue(self.current_index * self.carousel_width)
        self.loading_ani.setEndValue(index * self.carousel_width)
        self.loading_ani.start()
        self.current_index = index
        for i in range(self.navigate_lay.count()):
            frame = self.navigate_lay.itemAt(i).widget()
            frame.set_checked(i == self.current_index)
