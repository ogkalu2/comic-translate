#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.2
# Email : muyanru345@163.com
###################################################################

# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtWidgets

# Import local modules
from .mixin import cursor_mixin
from .mixin import stacked_animation_mixin


@cursor_mixin
class MTabBar(QtWidgets.QTabBar):
    def __init__(self, parent=None):
        super(MTabBar, self).__init__(parent=parent)
        self.setDrawBase(False)

    def tabSizeHint(self, index):
        tab_text = self.tabText(index)
        if self.tabsClosable():
            return QtCore.QSize(
                self.fontMetrics().horizontalAdvance(tab_text) + 70,
                self.fontMetrics().height() + 20,
            )
        else:
            return QtCore.QSize(
                self.fontMetrics().horizontalAdvance(tab_text) + 50,
                self.fontMetrics().height() + 20,
            )


@stacked_animation_mixin
class MTabWidget(QtWidgets.QTabWidget):
    def __init__(self, parent=None):
        super(MTabWidget, self).__init__(parent=parent)
        self.bar = MTabBar()
        self.setTabBar(self.bar)

    def disable_animation(self):
        self.currentChanged.disconnect(self._play_anim)
