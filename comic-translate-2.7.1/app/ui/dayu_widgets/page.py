#!/usr/bin/env python
# -*- coding: utf-8 -*-
###################################################################
# Author: Mu yanru
# Date  : 2019.3
# Email : muyanru345@163.com
###################################################################
"""MPage"""
# Import future modules
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Import built-in modules
import functools

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtWidgets

# Import local modules
from . import dayu_theme
from . import utils
from .combo_box import MComboBox
from .field_mixin import MFieldMixin
from .label import MLabel
from .menu import MMenu
from .spin_box import MSpinBox
from .tool_button import MToolButton


class MPage(QtWidgets.QWidget, MFieldMixin):
    """
    MPage
    A long list can be divided into several pages by MPage,
    and only one page will be loaded at a time.
    """

    sig_page_changed = QtCore.Signal(int, int)

    def __init__(self, parent=None):
        super(MPage, self).__init__(parent)
        self.register_field("page_size_selected", 25)
        self.register_field(
            "page_size_list",
            [
                {"label": "25 - Fastest", "value": 25},
                {"label": "50 - Fast", "value": 50},
                {"label": "75 - Medium", "value": 75},
                {"label": "100 - Slow", "value": 100},
            ],
        )
        self.register_field("total", 0)
        self.register_field("current_page", 0)
        self.register_field(
            "total_page",
            lambda: utils.get_total_page(self.field("total"), self.field("page_size_selected")),
        )
        self.register_field("total_page_text", lambda: str(self.field("total_page")))
        self.register_field(
            "display_text",
            lambda: utils.get_page_display_string(
                self.field("current_page"),
                self.field("page_size_selected"),
                self.field("total"),
            ),
        )
        self.register_field("can_pre", lambda: self.field("current_page") > 1)
        self.register_field("can_next", lambda: self.field("current_page") < self.field("total_page"))
        page_setting_menu = MMenu(parent=self)
        self._display_label = MLabel()
        self._display_label.setAlignment(QtCore.Qt.AlignCenter)
        self._change_page_size_button = MComboBox().small()
        self._change_page_size_button.set_menu(page_setting_menu)
        self._change_page_size_button.set_formatter(lambda x: "{} per page".format(x))

        self._pre_button = MToolButton().icon_only().svg("left_fill.svg").small()
        self._pre_button.clicked.connect(functools.partial(self._slot_change_current_page, -1))
        self._next_button = MToolButton().small().icon_only().svg("right_fill.svg")
        self._next_button.clicked.connect(functools.partial(self._slot_change_current_page, 1))
        self._current_page_spin_box = MSpinBox()
        self._current_page_spin_box.setMinimum(1)
        self._current_page_spin_box.set_dayu_size(dayu_theme.small)
        self._current_page_spin_box.valueChanged.connect(self._emit_page_changed)
        self._total_page_label = MLabel()

        self.bind("page_size_list", page_setting_menu, "data")
        self.bind("page_size_selected", page_setting_menu, "value", signal="sig_value_changed")
        self.bind(
            "page_size_selected",
            self._change_page_size_button,
            "value",
            signal="sig_value_changed",
        )
        self.bind("current_page", self._current_page_spin_box, "value", signal="valueChanged")
        self.bind("total_page", self._current_page_spin_box, "maximum")
        self.bind("total_page_text", self._total_page_label, "dayu_text")
        self.bind("display_text", self._display_label, "dayu_text")
        self.bind("can_pre", self._pre_button, "enabled")
        self.bind("can_next", self._next_button, "enabled")

        self._change_page_size_button.sig_value_changed.connect(self._emit_page_changed)

        main_lay = QtWidgets.QHBoxLayout()
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(2)
        main_lay.addStretch()
        main_lay.addWidget(self._display_label)
        main_lay.addStretch()
        main_lay.addWidget(MLabel("|").secondary())
        main_lay.addWidget(self._change_page_size_button)
        main_lay.addWidget(MLabel("|").secondary())
        main_lay.addWidget(self._pre_button)
        main_lay.addWidget(MLabel("Page"))
        main_lay.addWidget(self._current_page_spin_box)
        main_lay.addWidget(MLabel("/"))
        main_lay.addWidget(self._total_page_label)
        main_lay.addWidget(self._next_button)
        self.setLayout(main_lay)

    def set_total(self, value):
        """Set page component total count."""
        self.set_field("total", value)
        self.set_field("current_page", 1)

    def _slot_change_current_page(self, offset):
        self.set_field("current_page", self.field("current_page") + offset)
        self._emit_page_changed()

    def set_page_config(self, data_list):
        """Set page component per page settings."""
        self.set_field(
            "page_size_list",
            [{"label": str(data), "value": data} if isinstance(data, int) else data for data in data_list],
        )

    def _emit_page_changed(self):
        self.sig_page_changed.emit(self.field("page_size_selected"), self.field("current_page"))
