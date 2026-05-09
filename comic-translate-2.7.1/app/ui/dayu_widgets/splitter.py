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

# Import built-in modules
from functools import partial

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtGui
from PySide6 import QtWidgets

# Import local modules
from . import dayu_theme
from .mixin import property_mixin


@property_mixin
class MSplitter(QtWidgets.QSplitter):
    def __init__(self, Orientation=QtCore.Qt.Horizontal, parent=None):
        super(MSplitter, self).__init__(Orientation, parent=parent)
        self.setHandleWidth(10)
        self.setProperty("animatable", True)
        self.setProperty("default_size", 100)
        self.setProperty("anim_move_duration", 300)
        dayu_theme.apply(self)

    def slot_splitter_click(self, index, first=True):
        size_list = self.sizes()
        prev = index - 1
        prev_size = size_list[prev]
        next_size = size_list[index]
        default_size = self.property("default_size")
        if not prev_size:
            size_list[prev] = default_size
            size_list[index] -= default_size
        elif not next_size:
            size_list[index] = default_size
            size_list[prev] -= default_size
        else:

            if first:
                size_list[index] += prev_size
                size_list[prev] = 0
            else:
                size_list[prev] += next_size
                size_list[index] = 0

        if self.property("animatable"):
            anim = QtCore.QVariantAnimation(self)

            def anim_size(index, size_list, v):
                size_list[index - 1] += size_list[index] - v
                size_list[index] = v
                self.setSizes(size_list)

            anim.valueChanged.connect(partial(anim_size, index, size_list))
            anim.setDuration(self.property("anim_move_duration"))
            anim.setStartValue(next_size)
            anim.setEndValue(size_list[index])
            anim.start()
        else:
            self.setSizes(size_list)

    def createHandle(self):
        count = self.count()

        orient = self.orientation()
        is_horizontal = orient is QtCore.Qt.Horizontal
        handle = QtWidgets.QSplitterHandle(orient, self)

        # NOTES: double click average size
        handle.mouseDoubleClickEvent = lambda e: self.setSizes([1 for i in range(self.count())])

        layout = QtWidgets.QVBoxLayout() if is_horizontal else QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        handle.setLayout(layout)

        button = QtWidgets.QToolButton(handle)
        button.setArrowType(QtCore.Qt.LeftArrow if is_horizontal else QtCore.Qt.UpArrow)
        button.clicked.connect(lambda: self.slot_splitter_click(count, True))
        layout.addWidget(button)
        button = QtWidgets.QToolButton(handle)
        arrow = QtCore.Qt.RightArrow if is_horizontal else QtCore.Qt.DownArrow
        button.setArrowType(arrow)
        button.clicked.connect(lambda: self.slot_splitter_click(count, False))
        layout.addWidget(button)

        return handle
