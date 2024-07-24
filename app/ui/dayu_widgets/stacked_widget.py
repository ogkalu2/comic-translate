#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.4
# Email : muyanru345@163.com
###################################################################
"""MStackedWidget"""

# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import third-party modules
from PySide6 import QtWidgets

# Import local modules
from .mixin import stacked_animation_mixin


@stacked_animation_mixin
class MStackedWidget(QtWidgets.QStackedWidget):
    """Just active animation when current index changed."""

    def __init__(self, parent=None):
        super(MStackedWidget, self).__init__(parent)

    def disable_animation(self):
        self.currentChanged.disconnect(self._play_anim)
