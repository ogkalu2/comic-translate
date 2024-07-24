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

# Import built-in modules
import functools

# Import third-party modules
from PySide6 import QtCore
from PySide6 import QtWidgets
from dayu_path import DayuPath

# Import local modules
from . import dayu_theme
from .check_box import MCheckBox
from .field_mixin import MFieldMixin
from .label import MLabel
from .line_edit import MLineEdit
from .mixin import property_mixin


@property_mixin
class MSequenceFile(QtWidgets.QWidget, MFieldMixin):
    """
    这个类必须依赖 DayuPath
    props:
        path: six.string_types
        sequence: bool
    """

    sig_is_sequence_changed = QtCore.Signal(bool)

    def __init__(self, size=None, parent=None):
        super(MSequenceFile, self).__init__(parent)
        self.sequence_obj = None
        size = size or dayu_theme.small
        self._file_label = MLineEdit()
        self._file_label.set_dayu_size(size)
        self._file_label.setReadOnly(True)
        self._is_sequence_check_box = MCheckBox(self.tr("Sequence"))
        self._is_sequence_check_box.toggled.connect(functools.partial(self.setProperty, "sequence"))
        self._is_sequence_check_box.toggled.connect(self.sig_is_sequence_changed)

        self._info_label = MLabel().secondary()
        self._error_label = MLabel().secondary()
        self._error_label.setProperty("error", True)
        self._error_label.setMinimumWidth(100)
        self._error_label.set_elide_mode(QtCore.Qt.ElideMiddle)

        seq_lay = QtWidgets.QHBoxLayout()
        seq_lay.addWidget(self._is_sequence_check_box)
        seq_lay.addWidget(self._info_label)
        seq_lay.addWidget(self._error_label)
        seq_lay.setStretchFactor(self._is_sequence_check_box, 0)
        seq_lay.setStretchFactor(self._info_label, 0)
        seq_lay.setStretchFactor(self._error_label, 100)

        self._main_lay = QtWidgets.QVBoxLayout()
        self._main_lay.setContentsMargins(0, 0, 0, 0)
        self._main_lay.addWidget(self._file_label)
        self._main_lay.addLayout(seq_lay)
        self.setLayout(self._main_lay)
        self.set_sequence(True)

    def _set_path(self, value):
        path = DayuPath(value)
        for seq_obj in path.scan():
            self.sequence_obj = seq_obj
        self._update_info()

    def set_path(self, value):
        self.setProperty("path", value)

    def set_sequence(self, value):
        assert isinstance(value, bool)
        self.setProperty("sequence", value)

    def _set_sequence(self, value):
        if value != self._is_sequence_check_box.isChecked():
            # 更新来自代码
            self._is_sequence_check_box.setChecked(value)
            self.sig_is_sequence_changed.emit(value)
        self._update_info()

    def _update_info(self):
        self._file_label.setProperty(
            "text",
            self.sequence_obj if self.property("sequence") else self.property("path"),
        )
        if self.sequence_obj:
            self._info_label.setText(
                "Format: {ext}  "
                "Total: {count}  "
                "Range: {start}-{end}".format(
                    ext=self.sequence_obj.ext,
                    count=len(self.sequence_obj.frames),
                    start=self.sequence_obj.frames[0] if self.sequence_obj.frames else "/",
                    end=self.sequence_obj.frames[-1] if self.sequence_obj.frames else "/",
                )
            )
            error_info = "Missing: {}".format(self.sequence_obj.missing) if self.sequence_obj.missing else ""
            self._error_label.setText(error_info)
            self._error_label.setToolTip(error_info)
        self._info_label.setVisible(self.property("sequence"))
        self._error_label.setVisible(self.property("sequence"))
