#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.2
# Email : muyanru345@163.com
###################################################################
"""
MRadioButton
"""
# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import third-party modules
from PySide6 import QtWidgets

# Import local modules
from .mixin import cursor_mixin


@cursor_mixin
class MRadioButton(QtWidgets.QRadioButton):
    """
    MRadioButton just use stylesheet and set cursor shape when hover. No more extend.
    """

    def __init__(self, text="", parent=None):
        super(MRadioButton, self).__init__(text=text, parent=parent)
