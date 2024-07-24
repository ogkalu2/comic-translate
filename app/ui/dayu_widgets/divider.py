#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.2
# Email : muyanru345@163.com
###################################################################
"""
MDivider
"""
# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtWidgets
import six

# Import local modules
from .label import MLabel


class MDivider(QtWidgets.QWidget):
    """
    A divider line separates different content.

    Property:
        dayu_text: six.string_types
    """

    _alignment_map = {
        QtCore.Qt.AlignCenter: 50,
        QtCore.Qt.AlignLeft: 20,
        QtCore.Qt.AlignRight: 80,
    }

    def __init__(
        self,
        text="",
        orientation=QtCore.Qt.Horizontal,
        alignment=QtCore.Qt.AlignCenter,
        parent=None,
    ):
        super(MDivider, self).__init__(parent)
        self._orient = orientation
        self._text_label = MLabel().secondary()
        self._left_frame = QtWidgets.QFrame()
        self._right_frame = QtWidgets.QFrame()
        self._main_lay = QtWidgets.QHBoxLayout()
        self._main_lay.setContentsMargins(0, 0, 0, 0)
        self._main_lay.setSpacing(0)
        self._main_lay.addWidget(self._left_frame)
        self._main_lay.addWidget(self._text_label)
        self._main_lay.addWidget(self._right_frame)
        self.setLayout(self._main_lay)

        if orientation == QtCore.Qt.Horizontal:
            self._left_frame.setFrameShape(QtWidgets.QFrame.HLine)
            self._left_frame.setFrameShadow(QtWidgets.QFrame.Sunken)
            self._right_frame.setFrameShape(QtWidgets.QFrame.HLine)
            self._right_frame.setFrameShadow(QtWidgets.QFrame.Sunken)
        else:
            self._text_label.setVisible(False)
            self._right_frame.setVisible(False)
            self._left_frame.setFrameShape(QtWidgets.QFrame.VLine)
            self._left_frame.setFrameShadow(QtWidgets.QFrame.Sunken)
            #self._left_frame.setFrameShadow(QtWidgets.QFrame.Plain)
            self.setFixedWidth(5)
        self._main_lay.setStretchFactor(self._left_frame, self._alignment_map.get(alignment, 50))
        self._main_lay.setStretchFactor(self._right_frame, 100 - self._alignment_map.get(alignment, 50))
        self._text = None
        self.set_dayu_text(text)

    def set_dayu_text(self, value):
        """
        Set the divider's text.
        When text is empty, hide the text_label and right_frame to ensure the divider not has a gap.

        :param value: six.string_types
        :return: None
        """
        self._text = value
        self._text_label.setText(value)
        if self._orient == QtCore.Qt.Horizontal:
            self._text_label.setVisible(bool(value))
            self._right_frame.setVisible(bool(value))

    def get_dayu_text(self):
        """
        Get current text
        :return: six.string_types
        """
        return self._text

    dayu_text = QtCore.Property(six.string_types[0], get_dayu_text, set_dayu_text)

    @classmethod
    def left(cls, text=""):
        """Create a horizontal divider with text at left."""
        return cls(text, alignment=QtCore.Qt.AlignLeft)

    @classmethod
    def right(cls, text=""):
        """Create a horizontal divider with text at right."""
        return cls(text, alignment=QtCore.Qt.AlignRight)

    @classmethod
    def center(cls, text=""):
        """Create a horizontal divider with text at center."""
        return cls(text, alignment=QtCore.Qt.AlignCenter)

    @classmethod
    def vertical(cls):
        """Create a vertical divider"""
        return cls(orientation=QtCore.Qt.Vertical)
