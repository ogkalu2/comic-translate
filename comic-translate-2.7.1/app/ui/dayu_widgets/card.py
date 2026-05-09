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
from . import dayu_theme
from .avatar import MAvatar
from .divider import MDivider
from .label import MLabel
from .mixin import cursor_mixin
from .mixin import hover_shadow_mixin
from .tool_button import MToolButton


@hover_shadow_mixin
@cursor_mixin
class MCard(QtWidgets.QWidget):
    def __init__(self, title=None, image=None, size=None, extra=None, type=None, parent=None):
        super(MCard, self).__init__(parent=parent)
        self.setAttribute(QtCore.Qt.WA_StyledBackground)
        self.setProperty("border", False)
        size = size or dayu_theme.default_size
        map_label = {
            dayu_theme.large: (MLabel.H2Level, 20),
            dayu_theme.medium: (MLabel.H3Level, 15),
            dayu_theme.small: (MLabel.H4Level, 10),
        }
        self._title_label = MLabel(text=title)
        self._title_label.set_dayu_level(map_label.get(size)[0])

        padding = map_label.get(size)[-1]
        self._title_layout = QtWidgets.QHBoxLayout()
        self._title_layout.setContentsMargins(padding, padding, padding, padding)
        if image:
            self._title_icon = MAvatar()
            self._title_icon.set_dayu_image(image)
            self._title_icon.set_dayu_size(size)
            self._title_layout.addWidget(self._title_icon)
        self._title_layout.addWidget(self._title_label)
        self._title_layout.addStretch()
        if extra:
            self._extra_button = MToolButton().icon_only().svg("more.svg")
            self._title_layout.addWidget(self._extra_button)

        self._content_layout = QtWidgets.QVBoxLayout()

        self._main_lay = QtWidgets.QVBoxLayout()
        self._main_lay.setSpacing(0)
        self._main_lay.setContentsMargins(1, 1, 1, 1)
        if title:
            self._main_lay.addLayout(self._title_layout)
            self._main_lay.addWidget(MDivider())
        self._main_lay.addLayout(self._content_layout)
        self.setLayout(self._main_lay)

    def get_more_button(self):
        return self._extra_button

    def set_widget(self, widget):
        self._content_layout.addWidget(widget)

    def border(self):
        self.setProperty("border", True)
        self.style().polish(self)
        return self


@hover_shadow_mixin
@cursor_mixin
class MMeta(QtWidgets.QWidget):
    def __init__(
        self,
        cover=None,
        avatar=None,
        title=None,
        description=None,
        extra=False,
        parent=None,
    ):
        super(MMeta, self).__init__(parent)
        self.setAttribute(QtCore.Qt.WA_StyledBackground)
        self._cover_label = QtWidgets.QLabel()
        self._avatar = MAvatar()
        self._title_label = MLabel().h4()
        self._description_label = MLabel().secondary()
        self._description_label.setWordWrap(True)
        self._description_label.set_elide_mode(QtCore.Qt.ElideRight)
        self._title_layout = QtWidgets.QHBoxLayout()
        self._title_layout.addWidget(self._title_label)
        self._title_layout.addStretch()
        self._extra_button = MToolButton(parent=self).icon_only().svg("more.svg")
        self._title_layout.addWidget(self._extra_button)
        self._extra_button.setVisible(extra)

        content_lay = QtWidgets.QFormLayout()
        content_lay.setContentsMargins(5, 5, 5, 5)
        content_lay.addRow(self._avatar, self._title_layout)
        content_lay.addRow(self._description_label)

        self._button_layout = QtWidgets.QHBoxLayout()

        main_lay = QtWidgets.QVBoxLayout()
        main_lay.setSpacing(0)
        main_lay.setContentsMargins(1, 1, 1, 1)
        main_lay.addWidget(self._cover_label)
        main_lay.addLayout(content_lay)
        main_lay.addLayout(self._button_layout)
        main_lay.addStretch()
        self.setLayout(main_lay)
        self._cover_label.setFixedSize(QtCore.QSize(200, 200))
        # self.setFixedWidth(200)

    def get_more_button(self):
        return self._extra_button

    def setup_data(self, data_dict):
        if data_dict.get("title"):
            self._title_label.setText(data_dict.get("title"))
            self._title_label.setVisible(True)
        else:
            self._title_label.setVisible(False)

        if data_dict.get("description"):
            self._description_label.setText(data_dict.get("description"))
            self._description_label.setVisible(True)
        else:
            self._description_label.setVisible(False)

        if data_dict.get("avatar"):
            self._avatar.set_dayu_image(data_dict.get("avatar"))
            self._avatar.setVisible(True)
        else:
            self._avatar.setVisible(False)

        if data_dict.get("cover"):
            fixed_height = self._cover_label.width()
            self._cover_label.setPixmap(
                data_dict.get("cover").scaledToWidth(fixed_height, QtCore.Qt.SmoothTransformation)
            )
            self._cover_label.setVisible(True)
        else:
            self._cover_label.setVisible(False)