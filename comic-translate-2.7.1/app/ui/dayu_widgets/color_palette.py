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
from .divider import MDivider
from .label import MLabel
from .message import MMessage
from . import utils as utils


class MColorChart(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(MColorChart, self).__init__(parent)
        main_lay = QtWidgets.QVBoxLayout()
        main_lay.setSpacing(0)
        self.button_list = []
        for index in range(10):
            button = QtWidgets.QPushButton()
            button.setCursor(QtCore.Qt.PointingHandCursor)
            button.setToolTip(self.tr("Click to Copy Color"))
            button.clicked.connect(functools.partial(self.slot_copy_color, button))
            button.setFixedSize(QtCore.QSize(250, 45))
            button.setText("color-{}".format(index + 1))
            main_lay.addWidget(button)
            self.button_list.append(button)
        self.setLayout(main_lay)

    def set_colors(self, color_list):
        for index, button in enumerate(self.button_list):
            target = color_list[index]
            button.setText("color-{}\t{}".format(index + 1, target))
            button.setProperty("color", target)
            button.setStyleSheet(
                "QPushButton{{background-color:{};color:{};border: 0 solid black}}"
                "QPushButton:hover{{font-weight:bold;}}".format(target, "#000" if index < 5 else "#fff")
            )

    def slot_copy_color(self, button):
        color = button.property("color")
        QtWidgets.QApplication.clipboard().setText(color)
        MMessage.success("copied: {}".format(color), parent=self)


class MColorPaletteDialog(QtWidgets.QDialog):
    def __init__(self, init_color, parent=None):
        super(MColorPaletteDialog, self).__init__(parent)
        self.setWindowTitle("DAYU Color Palette")
        self.primary_color = QtGui.QColor(init_color)
        self.color_chart = MColorChart()
        self.choose_color_button = QtWidgets.QPushButton()
        self.choose_color_button.setFixedSize(QtCore.QSize(100, 30))
        self.color_label = QtWidgets.QLabel()
        self.info_label = MLabel()
        self.info_label.setProperty("error", True)
        color_lay = QtWidgets.QHBoxLayout()
        color_lay.addWidget(MLabel("Primary Color:"))
        color_lay.addWidget(self.choose_color_button)
        color_lay.addWidget(self.color_label)
        color_lay.addWidget(self.info_label)
        color_lay.addStretch()
        dialog = QtWidgets.QColorDialog(self.primary_color, parent=self)
        dialog.setWindowFlags(QtCore.Qt.Widget)
        dialog.setOption(QtWidgets.QColorDialog.NoButtons)
        dialog.currentColorChanged.connect(self.slot_color_changed)
        setting_lay = QtWidgets.QVBoxLayout()
        setting_lay.addLayout(color_lay)
        setting_lay.addWidget(MDivider())
        setting_lay.addWidget(dialog)

        main_lay = QtWidgets.QHBoxLayout()
        main_lay.addWidget(self.color_chart)
        main_lay.addLayout(setting_lay)
        self.setLayout(main_lay)
        self.update_color()

    @QtCore.Slot(QtGui.QColor)
    def slot_color_changed(self, color):
        self.primary_color = color
        light = self.primary_color.lightness()
        saturation = self.primary_color.saturation()
        self.info_label.setText("")
        if light <= 70:
            self.info_label.setText("亮度建议不低于70（现在 {}）".format(light))
        if saturation <= 70:
            self.info_label.setText("饱和度建议不低于70（现在 {}）".format(saturation))

        self.update_color()

    def update_color(self):
        self.choose_color_button.setStyleSheet(
            "border-radius: 0;border: none;border:1px solid gray;"
            "background-color:{};".format(self.primary_color.name())
        )
        self.color_label.setText(self.primary_color.name())
        self.color_chart.set_colors([utils.generate_color(self.primary_color, index + 1) for index in range(10)])


if __name__ == "__main__":
    # Import built-in modules
    import sys

    # Import local modules
    from . import dayu_theme

    app = QtWidgets.QApplication(sys.argv)
    test = MColorPaletteDialog(init_color="#1890ff")
    dayu_theme.apply(test)
    test.show()
    sys.exit(app.exec_())
